from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
from app.models.rate import RateRecommendation
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.services.ml import forecaster, optimizer

LOOKAHEAD_DAYS = 90


class PricingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_rates(self, hotel: Hotel, room_type: RoomType) -> list[RateRecommendation]:
        today = date.today()
        recs = []
        hotel_id = str(hotel.id)
        use_ml = forecaster.is_trained(hotel_id)

        for day_offset in range(LOOKAHEAD_DAYS):
            target = today + timedelta(days=day_offset)

            existing = await self.db.execute(
                select(RateRecommendation).where(
                    RateRecommendation.room_type_id == room_type.id,
                    RateRecommendation.target_date == target,
                )
            )
            if existing.scalar_one_or_none():
                continue

            if use_ml:
                ml_occupancy = forecaster.predict(hotel_id, target)
                if ml_occupancy is not None:
                    occupancy = round(ml_occupancy, 4)
                    confidence = 0.8
                else:
                    occupancy = await self._forecast_occupancy(hotel, room_type, target)
                    confidence = None
            else:
                occupancy = await self._forecast_occupancy(hotel, room_type, target)
                confidence = None

            rate = optimizer.compute_rate(
                base_rate=room_type.base_rate,
                occupancy=occupancy,
                min_rate=room_type.min_rate,
                max_rate=room_type.max_rate,
                confidence=confidence,
            )

            rec = RateRecommendation(
                hotel_id=hotel.id,
                room_type_id=room_type.id,
                target_date=target,
                recommended_rate=rate,
                min_rate=room_type.min_rate,
                max_rate=room_type.max_rate,
                forecasted_occupancy=occupancy * 100,
                confidence_score=confidence,
                status="pending",
            )
            self.db.add(rec)
            recs.append(rec)

        await self.db.commit()
        return recs

    async def _forecast_occupancy(self, hotel: Hotel, room_type: RoomType, target: date) -> float:
        day_of_week = target.weekday()

        result = await self.db.execute(
            select(func.count(Booking.id)).where(
                Booking.hotel_id == hotel.id,
                Booking.room_type_id == room_type.id,
                Booking.check_in <= target,
                Booking.check_out > target,
                Booking.status == "confirmed",
            )
        )
        current_bookings = result.scalar() or 0

        historical_result = await self.db.execute(
            select(func.count(Booking.id)).where(
                Booking.hotel_id == hotel.id,
                Booking.room_type_id == room_type.id,
                func.extract("dow", Booking.check_in) == day_of_week + 1,
                Booking.status == "confirmed",
            )
        )
        historical_avg = historical_result.scalar() or 0
        total = max(room_type.total_rooms, 1)

        historical_base = min(historical_avg / total, 1.0)
        current_base = min(current_bookings / total, 1.0)

        occupancy = current_base * 0.7 + historical_base * 0.3
        return round(min(occupancy, 0.95), 4)
