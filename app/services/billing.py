"""
Stripe billing service for subscription management, customer creation,
and webhook handling. Supports three tiers with per-hotel limits.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol
import stripe
import logging

from app.config import get_settings

logger = logging.getLogger("billing")
settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class SubscriptionTier(str, Enum):
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class SubscriptionPlan:
    tier: SubscriptionTier
    name: str
    monthly_price_usd: Decimal
    max_hotels: int
    max_rooms_per_hotel: int
    forecast_days: int
    features: list[str]
    stripe_price_id: str


PLAN_CONFIGS = {
    SubscriptionTier.BASIC: SubscriptionPlan(
        tier=SubscriptionTier.BASIC,
        name="Basic",
        monthly_price_usd=Decimal("99.00"),
        max_hotels=2,
        max_rooms_per_hotel=50,
        forecast_days=30,
        features=[
            "AI rate recommendations (30-day lookahead)",
            "Basic dashboard & reports",
            "Email support",
            "Single PMS integration",
        ],
        stripe_price_id=settings.stripe_basic_price_id,
    ),
    SubscriptionTier.PROFESSIONAL: SubscriptionPlan(
        tier=SubscriptionTier.PROFESSIONAL,
        name="Professional",
        monthly_price_usd=Decimal("249.00"),
        max_hotels=10,
        max_rooms_per_hotel=200,
        forecast_days=90,
        features=[
            "AI rate recommendations (90-day lookahead)",
            "Advanced dashboard & analytics",
            "ZATCA e-invoicing compliance",
            "Opera PMS + Cloudbeds integration",
            "Priority email & chat support",
            "Multi-property management",
        ],
        stripe_price_id=settings.stripe_pro_price_id,
    ),
    SubscriptionTier.ENTERPRISE: SubscriptionPlan(
        tier=SubscriptionTier.ENTERPRISE,
        name="Enterprise",
        monthly_price_usd=Decimal("749.00"),
        max_hotels=50,
        max_rooms_per_hotel=1000,
        forecast_days=180,
        features=[
            "All Professional features",
            "Custom ML model training",
            "Unlimited integrations",
            "Dedicated account manager",
            "SLA guarantee (99.9% uptime)",
            "Custom onboarding & training",
            "API rate limit exemptions",
        ],
        stripe_price_id=settings.stripe_enterprise_price_id,
    ),
}


def get_plan(tier: SubscriptionTier) -> SubscriptionPlan:
    return PLAN_CONFIGS[tier]


class BillingService:
    async def create_customer(self, email: str, name: str, organization_id: str) -> str:
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"organization_id": organization_id},
            )
            return customer.id
        except stripe.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise

    async def create_subscription(
        self, customer_id: str, price_id: str, trial_days: int = 14
    ) -> stripe.Subscription:
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                trial_period_days=trial_days,
                metadata={"source": "saudi_rms"},
            )
            return subscription
        except stripe.StripeError as e:
            logger.error(f"Failed to create subscription: {e}")
            raise

    async def cancel_subscription(self, subscription_id: str) -> stripe.Subscription:
        try:
            return stripe.Subscription.cancel(subscription_id)
        except stripe.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise

    async def update_subscription(
        self, subscription_id: str, new_price_id: str
    ) -> stripe.Subscription:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            item_id = sub["items"]["data"][0]["id"]
            return stripe.Subscription.modify(
                subscription_id,
                items=[{"id": item_id, "price": new_price_id}],
                proration_behavior="always_invoice",
            )
        except stripe.StripeError as e:
            logger.error(f"Failed to update subscription: {e}")
            raise

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        try:
            return stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except stripe.StripeError as e:
            logger.error(f"Webhook verification failed: {e}")
            raise

    def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.StripeError as e:
            logger.error(f"Failed to retrieve subscription: {e}")
            raise

    async def get_checkout_session(
        self, customer_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> stripe.checkout.Session:
        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={"source": "saudi_rms"},
            )
            return session
        except stripe.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise
