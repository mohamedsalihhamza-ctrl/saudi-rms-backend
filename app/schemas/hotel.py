from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


class HotelCreate(BaseModel):
    name: str = Field(..., max_length=200)
    name_ar: str | None = Field(None, max_length=200)
    city: str = Field(..., max_length=100)
    city_ar: str | None = Field(None, max_length=100)
    star_rating: int = Field(default=3, ge=1, le=5)
    total_rooms: int = Field(default=0, ge=0)
    pms_type: str | None = None
    currency: str = "SAR"
    timezone: str = "Asia/Riyadh"


class HotelResponse(BaseModel):
    id: UUID
    name: str
    name_ar: str | None
    city: str
    city_ar: str | None
    star_rating: int
    total_rooms: int
    status: str
    pms_type: str | None
    currency: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomTypeCreate(BaseModel):
    name: str = Field(..., max_length=100)
    name_ar: str | None = Field(None, max_length=100)
    code: str = Field(..., max_length=20)
    total_rooms: int = Field(default=10, ge=1)
    base_rate: float = Field(..., gt=0)
    min_rate: float = Field(..., ge=0)
    max_rate: float = Field(..., gt=0)
    max_occupancy: int = Field(default=2, ge=1)


class RoomTypeResponse(BaseModel):
    id: UUID
    hotel_id: UUID
    name: str
    name_ar: str | None
    code: str
    total_rooms: int
    base_rate: float
    min_rate: float
    max_rate: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RateRecommendationResponse(BaseModel):
    id: UUID
    hotel_id: UUID
    room_type_id: UUID
    target_date: date
    recommended_rate: float
    min_rate: float
    max_rate: float
    forecasted_occupancy: float | None
    confidence_score: float | None
    status: str

    model_config = ConfigDict(from_attributes=True)


class DashboardMetrics(BaseModel):
    hotel_id: UUID
    hotel_name: str
    current_revpar: float
    current_occupancy: float
    current_adr: float
    projected_revpar: float
    revpar_change: float
    total_bookings_today: int
    active_recommendations: int
