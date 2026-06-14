from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from pydantic import BaseModel

from app.database import get_db
from app.models.hotel import Hotel
from app.models.booking import Booking
from app.routers.deps import get_current_org_id

router = APIRouter()


class BookingImport(BaseModel):
    hotel_id: UUID
    room_type_code: str
    external_id: str
    check_in: str
    check_out: str
    booking_rate: float
    channel: str = "direct"
    status: str = "confirmed"


@router.post("/import-booking")
async def import_booking(
    data: BookingImport,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    from datetime import date
    from app.models.room_type import RoomType

    hotel = await db.get(Hotel, data.hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    rt_result = await db.execute(
        select(RoomType).where(
            RoomType.hotel_id == data.hotel_id,
            RoomType.code == data.room_type_code,
        )
    )
    room_type = rt_result.scalar_one_or_none()
    if not room_type:
        raise HTTPException(status_code=404, detail="Room type not found")

    existing = await db.execute(
        select(Booking).where(
            Booking.hotel_id == data.hotel_id,
            Booking.external_id == data.external_id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Booking already exists", "duplicate": True}

    booking = Booking(
        hotel_id=data.hotel_id,
        room_type_id=room_type.id,
        external_id=data.external_id,
        check_in=date.fromisoformat(data.check_in),
        check_out=date.fromisoformat(data.check_out),
        booking_rate=data.booking_rate,
        channel=data.channel,
        status=data.status,
    )
    db.add(booking)
    await db.commit()
    return {"message": "Booking imported", "id": str(booking.id)}
