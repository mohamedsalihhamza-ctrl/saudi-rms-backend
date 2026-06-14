from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal

from app.database import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.hotel import Hotel
from app.models.user import Organization
from app.routers.deps import get_current_user, get_current_org_id
from app.integrations.zatca import ZATCAInvoice, InvoiceLineItem, ZATCACertificateManager, InvoiceSigner

router = APIRouter()


class LineItemInput(BaseModel):
    name: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(gt=0)
    vat_rate: float = 0.15
    discount: float = 0


class InvoiceCreateInput(BaseModel):
    hotel_id: UUID
    buyer_name: str
    buyer_vat_number: str | None = None
    line_items: list[LineItemInput]
    notes: str = ""


class InvoiceResponse(BaseModel):
    id: UUID
    invoice_number: str
    seller_name: str
    seller_vat_number: str
    buyer_name: str
    total_excluding_vat: float
    total_vat: float
    total_including_vat: float
    qr_code_base64: str | None
    zatca_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(
    data: InvoiceCreateInput,
    org_id: UUID = Depends(get_current_org_id),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    items = [
        InvoiceLineItem(
            name=item.name,
            quantity=Decimal(str(item.quantity)),
            unit_price=Decimal(str(item.unit_price)),
            vat_rate=Decimal(str(item.vat_rate)),
            discount=Decimal(str(item.discount)),
        )
        for item in data.line_items
    ]

    zatca_invoice = ZATCAInvoice(
        seller_name=org.name,
        seller_vat_number=org.vat_number or "",
        buyer_name=data.buyer_name,
        buyer_vat_number=data.buyer_vat_number,
        line_items=items,
        notes=data.notes,
    )

    errors = zatca_invoice.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    invoice_dict = zatca_invoice.to_dict()

    db_invoice = Invoice(
        organization_id=org_id,
        hotel_id=data.hotel_id,
        invoice_number=invoice_dict["invoice_number"],
        invoice_type=invoice_dict["invoice_type"],
        seller_name=invoice_dict["seller_name"],
        seller_vat_number=invoice_dict["seller_vat_number"],
        buyer_name=invoice_dict["buyer_name"],
        buyer_vat_number=invoice_dict.get("buyer_vat_number"),
        total_excluding_vat=invoice_dict["total_excluding_vat"],
        total_vat=invoice_dict["total_vat"],
        total_including_vat=invoice_dict["total_including_vat"],
        currency=invoice_dict["currency"],
        qr_code_base64=invoice_dict.get("qr_code_base64"),
        zatca_status=InvoiceStatus.draft,
    )
    db.add(db_invoice)
    await db.commit()
    await db.refresh(db_invoice)

    return db_invoice


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    hotel_id: UUID | None = Query(None),
):
    query = select(Invoice).where(Invoice.organization_id == org_id)
    if hotel_id:
        query = query.where(Invoice.hotel_id == hotel_id)
    query = query.order_by(Invoice.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.organization_id == org_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/certificate/csr")
async def generate_csr(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    manager = ZATCACertificateManager()
    csr_pem, key_pem = manager.generate_csr(
        organization_name=org.name,
        common_name=f"{org.name}-ZATCA",
        vat_number=org.vat_number or "",
    )

    return {
        "csr_pem": csr_pem,
        "private_key": key_pem,
        "message": "Store the private key securely. Submit the CSR to ZATCA for signing.",
    }
