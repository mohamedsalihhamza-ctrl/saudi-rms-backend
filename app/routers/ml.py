from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID
from datetime import date, timedelta

from app.database import get_db
from app.models.hotel import Hotel
from app.models.booking import Booking
from app.models.rate import RateRecommendation
from app.routers.deps import get_current_org_id
from app.services.ml import forecaster

router = APIRouter()


@router.post("/train/{hotel_id}")
async def train_model(
    hotel_id: UUID,
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    rows = await db.execute(
        text("""
            SELECT
                check_in AS date,
                COUNT(*) AS occupancy,
                AVG(booking_rate) AS adr
            FROM bookings
            WHERE hotel_id = :hotel_id
                AND status = 'confirmed'
                AND check_in >= CURRENT_DATE - 365
            GROUP BY check_in
            ORDER BY date
        """),
        {"hotel_id": str(hotel_id)},
    )
    bookings_data = [{"date": r.date, "occupancy": r.occupancy, "adr": r.adr} for r in rows.fetchall()]

    result = forecaster.train(str(hotel_id), bookings_data)

    if result["status"] == "skipped":
        return {"status": "skipped", "message": result["reason"], "hotel_id": str(hotel_id)}

    forecasts = forecaster.predict_bulk(str(hotel_id))
    return {
        "status": "trained",
        "hotel_id": str(hotel_id),
        "samples": result["samples"],
        "forecast_days": len(forecasts) if forecasts else 0,
    }


@router.get("/status")
async def ml_status(
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    hotels_result = await db.execute(
        select(Hotel).where(Hotel.organization_id == org_id)
    )
    hotels = hotels_result.scalars().all()

    return {
        "engine": "sklearn (RandomForestRegressor)",
        "hotels": [
            {
                "id": str(h.id),
                "name": h.name,
                "model_trained": forecaster.is_trained(str(h.id)),
            }
            for h in hotels
        ],
    }


@router.get("/forecast/{hotel_id}")
async def get_forecast(
    hotel_id: UUID,
    days: int = Query(default=30, le=90, ge=1),
    org_id: UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    hotel = await db.get(Hotel, hotel_id)
    if not hotel or hotel.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if not forecaster.is_trained(str(hotel_id)):
        raise HTTPException(status_code=400, detail="Model not trained yet. POST /api/v1/ml/train/{hotel_id} first")

    forecasts = forecaster.predict_bulk(str(hotel_id), days)
    if not forecasts:
        raise HTTPException(status_code=500, detail="Forecast failed")

    return {
        "hotel_id": str(hotel_id),
        "days": [
            {"date": d, "forecasted_occupancy": round(v * 100, 1)}
            for d, v in sorted(forecasts.items())
        ],
    }
