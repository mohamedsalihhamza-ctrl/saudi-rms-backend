from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.database import get_db
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.schemas.hotel import HotelCreate, HotelResponse, RoomTypeCreate, RoomTypeResponse
from app.routers.deps import get_current_user, get_current_org_id

router = APIRouter()


@router.get("/", response_model=list[HotelResponse])
async def list_hotels(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Hotel).where(Hotel.organization_id == org_id))
    return result.scalars().all()


@router.post("/", response_model=HotelResponse, status_code=201)
async def create_hotel(
    hotel_data: HotelCreate,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    hotel = Hotel(**hotel_data.model_dump(), organization_id=org_id)
    db.add(hotel)
    await db.commit()
    await db.refresh(hotel)
    return hotel


@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.organization_id == org_id)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.delete("/{hotel_id}", status_code=204)
async def delete_hotel(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Hotel).where(Hotel.id == hotel_id, Hotel.organization_id == org_id)
    )
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    await db.delete(hotel)
    await db.commit()


@router.post("/{hotel_id}/room-types", response_model=RoomTypeResponse, status_code=201)
async def create_room_type(
    hotel_id: UUID,
    room_data: RoomTypeCreate,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    room = RoomType(**room_data.model_dump(), hotel_id=hotel_id)
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/{hotel_id}/room-types", response_model=list[RoomTypeResponse])
async def list_room_types(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")
    result = await db.execute(select(RoomType).where(RoomType.hotel_id == hotel_id))
    return result.scalars().all()
