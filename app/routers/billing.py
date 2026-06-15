from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.database import get_db
from app.models.user import Organization, User
from app.models.hotel import Hotel
from app.config import get_settings
from app.routers.deps import get_current_user, get_current_org_id
from app.services.billing import BillingService, SubscriptionTier, PLAN_CONFIGS, get_plan
from app.services.moyasar import (
    configure as configure_moyasar,
    is_enabled as moyasar_enabled,
    get_publishable_key as moyasar_publishable_key,
    create_payment as moyasar_create_payment,
    verify_webhook as moyasar_verify_webhook,
)

router = APIRouter()
settings = get_settings()
billing = BillingService()

configure_moyasar(
    secret_key=settings.moyasar_secret_key or None,
    publishable_key=settings.moyasar_publishable_key or None,
)


class PlanResponse(BaseModel):
    tier: str
    name: str
    monthly_price_usd: float
    max_hotels: int
    features: list[str]


class SubscriptionStatus(BaseModel):
    tier: str
    status: str
    current_period_end: datetime | None
    trial_end: datetime | None
    hotels_used: int
    max_hotels: int


class CreateCheckoutInput(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CustomerPortalInput(BaseModel):
    return_url: str


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans():
    return [
        PlanResponse(
            tier=plan.tier.value,
            name=plan.name,
            monthly_price_usd=float(plan.monthly_price_usd),
            max_hotels=plan.max_hotels,
            features=plan.features,
        )
        for plan in PLAN_CONFIGS.values()
    ]


@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription_status(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    hotels_used = await db.scalar(
        select(func.count()).select_from(Hotel).where(Hotel.organization_id == org_id)
    ) or 0

    return SubscriptionStatus(
        tier=org.subscription_tier,
        status=org.subscription_status,
        current_period_end=None,
        trial_end=None,
        hotels_used=hotels_used,
        max_hotels=org.max_hotels,
    )


@router.post("/create-checkout-session")
async def create_checkout_session(
    data: CreateCheckoutInput,
    current_user: dict = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not settings.stripe_secret_key:
        return {
            "url": data.success_url + "?mock_checkout=true",
            "session_id": "mock_session_" + str(org.id),
        }

    if not org.stripe_customer_id:
        user = await db.get(User, current_user["user_id"])
        try:
            customer_id = await billing.create_customer(
                email=user.email,
                name=org.name,
                organization_id=str(org_id),
            )
            org.stripe_customer_id = customer_id
            await db.commit()
        except Exception:
            return {"url": data.success_url + "?mock_checkout=true", "session_id": "mock_session_" + str(org.id)}
    else:
        customer_id = org.stripe_customer_id

    session = await billing.get_checkout_session(
        customer_id=customer_id,
        price_id=data.price_id,
        success_url=data.success_url,
        cancel_url=data.cancel_url,
    )
    return {"url": session.url, "session_id": session.id}


@router.post("/customer-portal")
async def customer_portal(
    data: CustomerPortalInput,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    if not settings.stripe_secret_key:
        return {"url": data.return_url + "?mock_portal=true"}

    import stripe
    org = await db.get(Organization, org_id)
    if not org or not org.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No Stripe customer found")

    session = stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id,
        return_url=data.return_url,
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    payload = await request.body()

    try:
        event = billing.construct_webhook_event(payload, stripe_signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    from sqlalchemy.ext.asyncio import AsyncSession
    from app.database import async_session_factory

    async with async_session_factory() as db:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            customer_id = session["customer"]
            org_result = await db.execute(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
            org = org_result.scalar_one_or_none()
            if org and session.get("mode") == "subscription":
                org.subscription_status = "active"
                await db.commit()

        elif event["type"] == "customer.subscription.updated":
            sub = event["data"]["object"]
            customer_id = sub["customer"]
            org_result = await db.execute(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                status = sub.get("status", "active")
                org.subscription_status = status if status == "active" else "past_due" if status == "past_due" else "canceled"
                price_id = sub["items"]["data"][0]["price"]["id"]
                for tier, plan in PLAN_CONFIGS.items():
                    if plan.stripe_price_id == price_id:
                        org.subscription_tier = tier.value
                        org.max_hotels = plan.max_hotels
                        break
                await db.commit()

        elif event["type"] == "customer.subscription.deleted":
            sub = event["data"]["object"]
            customer_id = sub["customer"]
            org_result = await db.execute(
                select(Organization).where(Organization.stripe_customer_id == customer_id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                org.subscription_status = "canceled"
                org.subscription_tier = SubscriptionTier.BASIC.value
                org.max_hotels = get_plan(SubscriptionTier.BASIC).max_hotels
                await db.commit()

    return {"received": True}


class MoyasarCheckoutInput(BaseModel):
    tier: str
    success_url: str


class MoyasarPaymentResponse(BaseModel):
    payment_id: str
    payment_url: str
    publishable_key: str


class PaymentProviderResponse(BaseModel):
    provider: str
    moyasar_enabled: bool
    moyasar_publishable_key: str


@router.get("/provider", response_model=PaymentProviderResponse)
async def payment_provider():
    return PaymentProviderResponse(
        provider=settings.payment_provider,
        moyasar_enabled=moyasar_enabled(),
        moyasar_publishable_key=moyasar_publishable_key() if moyasar_enabled() else "",
    )


@router.post("/moyasar-checkout", response_model=MoyasarPaymentResponse)
async def moyasar_checkout(
    data: MoyasarCheckoutInput,
    current_user: dict = Depends(get_current_user),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not moyasar_enabled():
        if not settings.moyasar_secret_key:
            raise HTTPException(status_code=501, detail="Moyasar not configured")
        raise HTTPException(status_code=501, detail="Moyasar not configured")

    try:
        tier = SubscriptionTier(data.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tier")

    plan = get_plan(tier)
    callback_url = data.success_url + f"?moyasar_checkout=true&tier={data.tier}"

    result = await moyasar_create_payment(
        amount_halala=int(plan.monthly_price_usd * 100),
        description=f"{plan.name} - {settings.app_name}",
        callback_url=callback_url,
        metadata={
            "organization_id": str(org_id),
            "tier": data.tier,
        },
    )

    return MoyasarPaymentResponse(
        payment_id=result.id,
        payment_url=result.url,
        publishable_key=moyasar_publishable_key(),
    )


class PlanSelectInput(BaseModel):
    tier: str


@router.post("/subscribe-moyasar")
async def subscribe_moyasar(
    data: PlanSelectInput,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    try:
        tier = SubscriptionTier(data.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tier")

    plan = get_plan(tier)
    org.subscription_tier = tier.value
    org.subscription_status = "active"
    org.max_hotels = plan.max_hotels
    await db.commit()

    return {"success": True, "tier": tier.value}


@router.post("/moyasar-webhook")
async def moyasar_webhook(request: Request):
    payload = await request.json()
    try:
        payment = moyasar_verify_webhook(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    status = payment.get("status")
    metadata = payment.get("metadata", {}) or {}
    org_id_str = metadata.get("organization_id")
    tier_str = metadata.get("tier")

    if status == "paid" and org_id_str and tier_str:
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.database import async_session_factory

        async with async_session_factory() as db:
            org = await db.get(Organization, UUID(org_id_str))
            if org:
                try:
                    tier = SubscriptionTier(tier_str)
                    plan = get_plan(tier)
                    org.subscription_tier = tier.value
                    org.subscription_status = "active"
                    org.max_hotels = plan.max_hotels
                    await db.commit()
                    logger.info(f"Organization {org_id_str} upgraded to {tier_str} via Moyasar")
                except ValueError:
                    pass

    return {"received": True}
