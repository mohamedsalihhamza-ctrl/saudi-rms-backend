from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime, timezone

from app.database import get_db
from app.models.pms_connection import PMSConnection
from app.models.hotel import Hotel
from app.routers.deps import get_current_org_id
from app.integrations.pms import OperaCloudClient, OperaConfig

router = APIRouter()


class PMSConnectInput(BaseModel):
    hotel_id: UUID
    provider: str = Field(..., pattern="^(opera_cloud|cloudbeds|mews)$")
    property_code: str
    chain_code: str = ""
    enterprise_code: str = ""
    base_url: str | None = None
    client_id: str
    client_secret: str


class PMSConnectionResponse(BaseModel):
    id: UUID
    hotel_id: UUID
    provider: str
    property_code: str
    is_active: bool
    sync_status: str
    last_sync_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PMSSyncResult(BaseModel):
    reservations_imported: int
    rates_pushed: int
    errors: list[str]


@router.post("/connect", response_model=PMSConnectionResponse, status_code=201)
async def connect_pms(
    data: PMSConnectInput,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    existing = await db.execute(
        select(PMSConnection).where(
            PMSConnection.hotel_id == data.hotel_id,
            PMSConnection.provider == data.provider,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Connection already exists for this provider")

    conn = PMSConnection(
        organization_id=org_id,
        hotel_id=data.hotel_id,
        provider=data.provider,
        property_code=data.property_code,
        chain_code=data.chain_code,
        enterprise_code=data.enterprise_code,
        base_url=data.base_url,
        encrypted_client_id=data.client_id,
        encrypted_client_secret=data.client_secret,
        sync_status="connected",
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


@router.get("/connections", response_model=list[PMSConnectionResponse])
async def list_connections(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PMSConnection).where(PMSConnection.organization_id == org_id)
    )
    return result.scalars().all()


@router.get("/connections/{connection_id}/sync", response_model=PMSSyncResult)
async def sync_pms(
    connection_id: UUID,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(PMSConnection, connection_id)
    if not conn or conn.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    if conn.provider == "opera_cloud":
        config = OperaConfig(
            client_id=conn.encrypted_client_id,
            client_secret=conn.encrypted_client_secret,
            base_url=conn.base_url or "https://api-rsr.opera-api.com",
            property_code=conn.property_code,
            chain_code=conn.chain_code,
            enterprise_code=conn.enterprise_code,
        )
        client = OperaCloudClient(config)
        try:
            healthy = await client.health_check()
            if not healthy:
                conn.sync_status = "error"
                await db.commit()
                raise HTTPException(status_code=502, detail="Cannot connect to Opera Cloud")

            from datetime import date, timedelta
            start = date.today() - timedelta(days=7)
            end = date.today() + timedelta(days=90)
            reservations = await client.get_reservations(start, end)

            imported = 0
            from app.models.booking import Booking

            for res in reservations:
                existing = await db.execute(
                    select(Booking).where(
                        Booking.hotel_id == conn.hotel_id,
                        Booking.external_id == res.external_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                booking = Booking(
                    hotel_id=conn.hotel_id,
                    external_id=res.external_id,
                    check_in=res.check_in,
                    check_out=res.check_out,
                    booking_rate=res.booking_rate,
                    channel="opera",
                    status=res.status,
                )
                db.add(booking)
                imported += 1

            conn.last_sync_at = datetime.now(timezone.utc)
            conn.sync_status = "synced"
            await db.commit()

            return PMSSyncResult(
                reservations_imported=imported,
                rates_pushed=0,
                errors=[],
            )
        finally:
            await client.close()

    raise HTTPException(status_code=400, detail=f"Unsupported provider: {conn.provider}")


@router.delete("/connections/{connection_id}", status_code=204)
async def disconnect_pms(
    connection_id: UUID,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    conn = await db.get(PMSConnection, connection_id)
    if not conn or conn.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.commit()
