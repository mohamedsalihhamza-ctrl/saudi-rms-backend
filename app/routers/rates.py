from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID
from datetime import date, datetime, timezone

from app.database import get_db
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.rate import RateRecommendation, RateHistory
from app.schemas.hotel import RateRecommendationResponse
from app.routers.deps import get_current_org_id
from app.services.pricing import PricingService

router = APIRouter()


@router.get("/recommendations", response_model=list[RateRecommendationResponse])
async def get_recommendations(
    hotel_id: UUID = Query(...),
    room_type_id: UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    query = select(RateRecommendation).where(RateRecommendation.hotel_id == hotel_id)
    if room_type_id:
        query = query.where(RateRecommendation.room_type_id == room_type_id)
    if start_date:
        query = query.where(RateRecommendation.target_date >= start_date)
    if end_date:
        query = query.where(RateRecommendation.target_date <= end_date)
    query = query.order_by(RateRecommendation.target_date)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/generate/{hotel_id}")
async def generate_recommendations(
    hotel_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    result = await db.execute(select(RoomType).where(RoomType.hotel_id == hotel_id))
    room_types = result.scalars().all()

    service = PricingService(db)
    count = 0
    for room_type in room_types:
        recs = await service.generate_rates(hotel, room_type)
        count += len(recs)

    return {"message": f"Generated {count} rate recommendations", "hotel_id": str(hotel_id)}


@router.post("/apply/{recommendation_id}")
async def apply_recommendation(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db),
    org_id: UUID = Depends(get_current_org_id),
):
    rec = await db.get(RateRecommendation, recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    hotel = await db.get(Hotel, rec.hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    rec.status = "applied"
    rec.applied_at = datetime.now(timezone.utc)

    history = RateHistory(
        room_type_id=rec.room_type_id,
        rate=rec.recommended_rate,
        source="ai",
        effective_date=rec.target_date,
    )
    db.add(history)
    await db.commit()

    return {"message": "Rate applied", "rate": rec.recommended_rate}
