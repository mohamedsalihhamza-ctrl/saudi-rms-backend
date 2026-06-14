from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base
import uuid
import enum


class InvoiceStatus(enum.Enum):
    draft = "draft"
    submitted = "submitted"
    cleared = "cleared"
    reported = "reported"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    hotel_id = Column(UUID(as_uuid=True), ForeignKey("hotels.id"), nullable=True)
    invoice_number = Column(String(50), unique=True, nullable=False)
    invoice_type = Column(String(20), default="standard")

    seller_name = Column(String(200), nullable=False)
    seller_vat_number = Column(String(20), nullable=False)
    buyer_name = Column(String(200), nullable=False)
    buyer_vat_number = Column(String(20), nullable=True)

    total_excluding_vat = Column(Float, nullable=False)
    total_vat = Column(Float, nullable=False)
    total_including_vat = Column(Float, nullable=False)
    currency = Column(String(3), default="SAR")

    qr_code_base64 = Column(Text, nullable=True)
    invoice_hash = Column(String(64), nullable=True)
    digital_signature = Column(Text, nullable=True)
    zatca_status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.draft)
    zatca_uuid = Column(String(36), nullable=True)
    signed_timestamp = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", backref="invoices")
    hotel = relationship("Hotel", backref="invoices")
