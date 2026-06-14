import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RoomType(Base):
    __tablename__ = "room_types"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(100), nullable=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    total_rooms: Mapped[int] = mapped_column(Integer, default=10)
    base_rate: Mapped[float] = mapped_column(Float, nullable=False)
    min_rate: Mapped[float] = mapped_column(Float, nullable=False)
    max_rate: Mapped[float] = mapped_column(Float, nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    hotel = relationship("Hotel", back_populates="room_types")
    rate_recommendations = relationship("RateRecommendation", back_populates="room_type", cascade="all, delete-orphan")
    rate_history = relationship("RateHistory", back_populates="room_type", cascade="all, delete-orphan")
