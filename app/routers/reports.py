from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from uuid import UUID
from datetime import date, datetime, timedelta

from app.database import get_db
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.booking import Booking
from app.models.rate import RateRecommendation
from app.schemas.hotel import DashboardMetrics
from app.routers.deps import get_current_org_id

router = APIRouter()


@router.get("/dashboard/{hotel_id}", response_model=DashboardMetrics)
async def get_dashboard(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    today = date.today()
    month_start = today.replace(day=1)

    today_bookings = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.hotel_id == hotel_id,
            Booking.check_in <= today,
            Booking.check_out > today,
            Booking.status == "confirmed",
        )
    )
    occupied_rooms = today_bookings.scalar() or 0
    current_occupancy = (occupied_rooms / hotel.total_rooms * 100) if hotel.total_rooms > 0 else 0

    month_bookings = await db.execute(
        select(func.avg(Booking.booking_rate)).where(
            Booking.hotel_id == hotel_id,
            Booking.booked_at >= month_start,
            Booking.status == "confirmed",
        )
    )
    avg_rate = month_bookings.scalar() or 0
    current_adr = round(avg_rate, 2)
    current_revpar = round(current_adr * current_occupancy / 100, 2)

    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_bookings = await db.execute(
        select(func.avg(Booking.booking_rate)).where(
            Booking.hotel_id == hotel_id,
            Booking.booked_at >= last_month_start,
            Booking.booked_at < month_start,
            Booking.status == "confirmed",
        )
    )
    prev_avg_rate = prev_bookings.scalar() or 0
    prev_occupancy = await db.execute(
        select(func.count(Booking.id)).where(
            Booking.hotel_id == hotel_id,
            Booking.check_in >= last_month_start,
            Booking.check_in < month_start,
            Booking.status == "confirmed",
        )
    )
    prev_occ_rate = ((prev_occupancy.scalar() or 0) / hotel.total_rooms * 100) if hotel.total_rooms > 0 else 0
    prev_revpar = round(prev_avg_rate * prev_occ_rate / 100, 2)

    revpar_change = ((current_revpar - prev_revpar) / prev_revpar * 100) if prev_revpar > 0 else 0

    active_recs = await db.execute(
        select(func.count(RateRecommendation.id)).where(
            RateRecommendation.hotel_id == hotel_id,
            RateRecommendation.status == "pending",
        )
    )

    projections = await db.execute(
        select(func.avg(RateRecommendation.recommended_rate)).where(
            RateRecommendation.hotel_id == hotel_id,
            RateRecommendation.target_date >= today,
            RateRecommendation.target_date <= today + timedelta(days=30),
        )
    )
    projected_rate = projections.scalar() or current_adr
    projected_occ = await db.execute(
        select(func.avg(RateRecommendation.forecasted_occupancy)).where(
            RateRecommendation.hotel_id == hotel_id,
            RateRecommendation.target_date >= today,
            RateRecommendation.target_date <= today + timedelta(days=30),
        )
    )
    proj_occ = projected_occ.scalar() or current_occupancy
    projected_revpar = round(projected_rate * proj_occ / 100, 2)

    return DashboardMetrics(
        hotel_id=hotel_id,
        hotel_name=hotel.name,
        current_revpar=current_revpar,
        current_occupancy=round(current_occupancy, 1),
        current_adr=current_adr,
        projected_revpar=projected_revpar,
        revpar_change=round(revpar_change, 1),
        total_bookings_today=occupied_rooms,
        active_recommendations=active_recs.scalar() or 0,
    )
