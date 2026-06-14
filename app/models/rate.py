import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RateRecommendation(Base):
    __tablename__ = "rate_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("room_types.id"), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_rate: Mapped[float] = mapped_column(Float, nullable=False)
    min_rate: Mapped[float] = mapped_column(Float, nullable=False)
    max_rate: Mapped[float] = mapped_column(Float, nullable=False)
    forecasted_occupancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    hotel = relationship("Hotel", back_populates="rate_recommendations")
    room_type = relationship("RoomType", back_populates="rate_recommendations")


class RateHistory(Base):
    __tablename__ = "rate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("room_types.id"), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    room_type = relationship("RoomType", back_populates="rate_history")
