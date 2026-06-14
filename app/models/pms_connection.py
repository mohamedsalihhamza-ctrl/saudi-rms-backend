import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PMSConnection(Base):
    __tablename__ = "pms_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=False)

    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    property_code: Mapped[str] = mapped_column(String(50), nullable=False)
    chain_code: Mapped[str] = mapped_column(String(50), default="")
    enterprise_code: Mapped[str] = mapped_column(String(50), default="")
    base_url: Mapped[str] = mapped_column(String(255), nullable=True)

    encrypted_client_id: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_client_secret: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), default="disconnected")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    hotel = relationship("Hotel", backref="pms_connections")
