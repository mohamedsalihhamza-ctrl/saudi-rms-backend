import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    city_ar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(100), default="Saudi Arabia")
    star_rating: Mapped[int] = mapped_column(Integer, default=3)
    total_rooms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    pms_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pms_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Riyadh")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    room_types = relationship("RoomType", back_populates="hotel", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="hotel", cascade="all, delete-orphan")
    rate_recommendations = relationship("RateRecommendation", back_populates="hotel", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="hotels")
