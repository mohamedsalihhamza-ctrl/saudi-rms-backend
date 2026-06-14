from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.database import get_db
from app.config import get_settings
from app.models.user import User, Organization
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, OrganizationUpdate, OrganizationResponse
from app.routers.deps import get_current_user, get_current_org_id

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(name=user_data.organization_name)
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=user_data.email,
        password_hash=pwd_context.hash(user_data.password),
        full_name=user_data.full_name,
        full_name_ar=user_data.full_name_ar,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    token = create_access_token({"sub": str(user.id), "org_id": str(org.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        organization_id=org.id,
        subscription_tier=org.subscription_tier,
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    org = await db.get(Organization, user.organization_id)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token({"sub": str(user.id), "org_id": str(org.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        organization_id=org.id,
        subscription_tier=org.subscription_tier,
    )


@router.get("/organization", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/organization", response_model=OrganizationResponse)
async def update_organization(
    data: OrganizationUpdate,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    await db.commit()
    await db.refresh(org)
    return org
