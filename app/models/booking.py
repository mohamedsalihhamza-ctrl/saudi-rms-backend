import uuid
from datetime import datetime, date, timezone
from sqlalchemy import String, Integer, Float, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False)
    room_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("room_types.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    booking_rate: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(50), default="direct")
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    booked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    hotel = relationship("Hotel", back_populates="bookings")
