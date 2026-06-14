"""
ZATCA e-invoicing Phase 1 & Phase 2 compliance module.
Handles invoice generation, TLV QR code encoding, and validation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
import base64
import io
import struct

import qrcode


TLV_TAGS = {
    "seller_name": 1,
    "vat_number": 2,
    "timestamp": 3,
    "invoice_total": 4,
    "vat_total": 5,
}


def encode_tlv(tag: int, value: str) -> bytes:
    encoded = value.encode("utf-8")
    length = len(encoded)
    if length > 0xFF:
        raise ValueError("TLV value too long")
    return struct.pack("BB", tag, length) + encoded


@dataclass
class InvoiceLineItem:
    name: str
    quantity: Decimal
    unit_price: Decimal
    vat_rate: Decimal = Decimal("0.15")
    discount: Decimal = Decimal("0")

    @property
    def net_amount(self) -> Decimal:
        return self.quantity * self.unit_price - self.discount

    @property
    def vat_amount(self) -> Decimal:
        return (self.net_amount * self.vat_rate).quantize(Decimal("0.01"))


@dataclass
class ZATCAInvoice:
    seller_name: str
    seller_vat_number: str
    buyer_name: str
    buyer_vat_number: str | None = None
    invoice_number: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    currency: str = "SAR"
    notes: str = ""
    invoice_type: str = "standard"
    
    def __post_init__(self):
        if not self.invoice_number:
            self.invoice_number = f"INV-{int(self.timestamp.timestamp())}"

    @property
    def total_excluding_vat(self) -> Decimal:
        return sum(item.net_amount for item in self.line_items)

    @property
    def total_vat(self) -> Decimal:
        return sum(item.vat_amount for item in self.line_items)

    @property
    def total_including_vat(self) -> Decimal:
        return self.total_excluding_vat + self.total_vat

    def generate_qr_base64(self) -> str:
        tlv_data = b""
        tlv_data += encode_tlv(TLV_TAGS["seller_name"], self.seller_name)
        tlv_data += encode_tlv(TLV_TAGS["vat_number"], self.seller_vat_number)
        tlv_data += encode_tlv(TLV_TAGS["timestamp"], self.timestamp.isoformat())
        tlv_data += encode_tlv(TLV_TAGS["invoice_total"], f"{self.total_including_vat:.2f}")
        tlv_data += encode_tlv(TLV_TAGS["vat_total"], f"{self.total_vat:.2f}")

        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(tlv_data, optimize=0)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def validate(self) -> list[str]:
        errors = []
        if not self.seller_name.strip():
            errors.append("Seller name is required")
        if not self.seller_vat_number.strip():
            errors.append("Seller VAT number is required")
        if len(self.seller_vat_number.replace(" ", "")) != 15:
            errors.append("Seller VAT number must be 15 digits")
        if not self.line_items:
            errors.append("At least one line item is required")
        if any(item.quantity <= 0 for item in self.line_items):
            errors.append("All quantities must be positive")
        return errors

    def to_dict(self) -> dict:
        return {
            "invoice_number": self.invoice_number,
            "invoice_type": self.invoice_type,
            "timestamp": self.timestamp.isoformat(),
            "seller_name": self.seller_name,
            "seller_vat_number": self.seller_vat_number,
            "buyer_name": self.buyer_name,
            "buyer_vat_number": self.buyer_vat_number,
            "currency": self.currency,
            "line_items": [
                {
                    "name": item.name,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "vat_rate": float(item.vat_rate),
                    "net_amount": float(item.net_amount),
                    "vat_amount": float(item.vat_amount),
                }
                for item in self.line_items
            ],
            "total_excluding_vat": float(self.total_excluding_vat),
            "total_vat": float(self.total_vat),
            "total_including_vat": float(self.total_including_vat),
            "qr_code_base64": self.generate_qr_base64(),
        }


def generate_qr_code(tlv_data: bytes) -> str:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(tlv_data, optimize=0)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
