from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from uuid import UUID


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., max_length=200)
    full_name_ar: str | None = Field(None, max_length=200)
    organization_name: str = Field(..., max_length=200)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    full_name_ar: str | None
    role: str
    preferred_language: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization_id: UUID
    subscription_tier: str


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    name_ar: str | None
    subscription_tier: str
    subscription_status: str
    vat_number: str | None
    commercial_registration: str | None
    city_ar: str | None
    max_hotels: int

    model_config = ConfigDict(from_attributes=True)


class SSOLoginResponse(BaseModel):
    id_token: str


class SSOStatus(BaseModel):
    google_enabled: bool
    apple_enabled: bool


class OrganizationUpdate(BaseModel):
    name: str | None = None
    name_ar: str | None = None
    vat_number: str | None = None
    commercial_registration: str | None = None
    city_ar: str | None = None
