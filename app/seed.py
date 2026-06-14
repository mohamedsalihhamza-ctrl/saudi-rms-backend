"""Seed script — populates the database with realistic Saudi hotel demo data.

Usage:
    python -m app.seed

Requires DATABASE_URL in .env (defaults to sqlite+aiosqlite:///./saudi_rms.db).
Idempotent — clears existing data and re-seeds.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone, date
from uuid import UUID
from random import Random
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.database import Base, async_session_factory, engine
from app.config import get_settings
from app.models.user import Organization, User
from app.models.hotel import Hotel
from app.models.room_type import RoomType
from app.models.rate import RateRecommendation, RateHistory
from app.models.booking import Booking
from app.models.pms_connection import PMSConnection

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
rng = Random(42)

RATE_STRATEGIES = ["aggressive", "moderate_increase", "maintain", "discount"]


def season_multiplier(d: date) -> float:
    month = d.month
    day = d.year
    is_weekend = d.weekday() >= 4
    base = 1.0
    if month in (3, 10):
        base += 0.3
    elif month in (6, 7):
        base += 0.15
    elif month in (1, 9):
        base += 0.1
    if is_weekend:
        base += 0.08
    return base


async def seed(drop_first: bool = True):
    settings = get_settings()

    if drop_first:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        print("✓ Recreated all tables")

    async with async_session_factory() as db:
        org = Organization(
            name="Al-Haram Hospitality Group",
            name_ar="مجموعة الحرم للضيافة",
            subscription_tier="professional",
            subscription_status="active",
            vat_number="310123456789012",
            commercial_registration="CR-1234567",
            city_ar="مكة المكرمة",
            max_hotels=25,
        )
        db.add(org)
        await db.flush()
        print(f"  Organization: {org.name} (id={org.id})")

        user = User(
            organization_id=org.id,
            email="admin@alharam.sa",
            password_hash=pwd_context.hash("admin123456"),
            full_name="Ahmed Al-Ghamdi",
            full_name_ar="أحمد الغامدي",
            role="admin",
            preferred_language="ar",
        )
        db.add(user)
        await db.flush()
        print(f"  Admin user: {user.email} / password: admin123456")

        hotels_data = [
            {"name": "Makkah Tower Hotel", "name_ar": "فندق برج مكة", "city": "Makkah", "city_ar": "مكة المكرمة", "star_rating": 5, "total_rooms": 450, "latitude": 21.4225, "longitude": 39.8262},
            {"name": "Madinah Palace Hotel", "name_ar": "فندق قصر المدينة", "city": "Madinah", "city_ar": "المدينة المنورة", "star_rating": 4, "total_rooms": 320, "latitude": 24.4672, "longitude": 39.6112},
            {"name": "Riyadh Business Hotel", "name_ar": "فندق الرياض للأعمال", "city": "Riyadh", "city_ar": "الرياض", "star_rating": 4, "total_rooms": 200, "latitude": 24.7136, "longitude": 46.6753},
            {"name": "Jeddah Corniche Resort", "name_ar": "منتجع جدة الكورنيش", "city": "Jeddah", "city_ar": "جدة", "star_rating": 5, "total_rooms": 280, "latitude": 21.5433, "longitude": 39.1728},
            {"name": "Dammam Beach Hotel", "name_ar": "فندق الدمام الشاطئ", "city": "Dammam", "city_ar": "الدمام", "star_rating": 3, "total_rooms": 150, "latitude": 26.4207, "longitude": 50.0888},
        ]

        room_type_templates = [
            {"name": "Standard Room", "name_ar": "غرفة قياسية", "code": "STD", "total_rooms": 0, "base_rate": 350, "min_rate": 250, "max_rate": 600, "max_occupancy": 2},
            {"name": "Deluxe Room", "name_ar": "غرفة ديلوكس", "code": "DLX", "total_rooms": 0, "base_rate": 500, "min_rate": 350, "max_rate": 900, "max_occupancy": 3},
            {"name": "Junior Suite", "name_ar": "جناح صغير", "code": "JSU", "total_rooms": 0, "base_rate": 800, "min_rate": 550, "max_rate": 1500, "max_occupancy": 4},
            {"name": "Executive Suite", "name_ar": "جناح تنفيذي", "code": "EXE", "total_rooms": 0, "base_rate": 1200, "min_rate": 800, "max_rate": 2500, "max_occupancy": 4},
            {"name": "Presidential Suite", "name_ar": "جناح رئاسي", "code": "PRE", "total_rooms": 0, "base_rate": 2500, "min_rate": 1500, "max_rate": 5000, "max_occupancy": 6},
        ]

        star_to_room_config = {
            5: [("STD", 60), ("DLX", 25), ("JSU", 10), ("EXE", 4), ("PRE", 1)],
            4: [("STD", 55), ("DLX", 30), ("JSU", 10), ("EXE", 5)],
            3: [("STD", 65), ("DLX", 25), ("JSU", 10)],
        }

        today = date.today()
        all_hotels = []

        for hd in hotels_data:
            hotel = Hotel(
                organization_id=org.id,
                **{k: v for k, v in hd.items() if k != "star_rating" and k != "total_rooms"},
                star_rating=hd["star_rating"],
                total_rooms=hd["total_rooms"],
            )
            db.add(hotel)
            await db.flush()
            all_hotels.append(hotel)
            print(f"  Hotel: {hotel.name} ({hotel.city}, {hotel.star_rating}★)")

            config = star_to_room_config.get(hotel.star_rating, star_to_room_config[3])
            room_pct_total = sum(pct for _, pct in config)
            created_rooms = []

            for code, pct in config:
                tmpl = next(t for t in room_type_templates if t["code"] == code)
                room_count = max(1, int(hotel.total_rooms * pct / room_pct_total))
                mult = 1.0 + (hotel.star_rating - 3) * 0.15
                room = RoomType(
                    hotel_id=hotel.id,
                    name=tmpl["name"],
                    name_ar=tmpl["name_ar"],
                    code=code,
                    total_rooms=room_count,
                    base_rate=round(tmpl["base_rate"] * mult),
                    min_rate=round(tmpl["min_rate"] * mult),
                    max_rate=round(tmpl["max_rate"] * mult),
                    max_occupancy=tmpl["max_occupancy"],
                )
                db.add(room)
                await db.flush()
                created_rooms.append(room)
                print(f"    {room.code}: {room.total_rooms}x {room.name} @ SAR {room.base_rate}")

            for room in created_rooms:
                for day_offset in range(90):
                    target = today + timedelta(days=day_offset)
                    sm = season_multiplier(target)
                    jitter = 1.0 + (rng.random() - 0.5) * 0.1
                    rec_rate = round(room.base_rate * sm * jitter)
                    rec_rate = max(room.min_rate, min(room.max_rate, rec_rate))
                    occ = round(min(95, 30 + 40 * sm + rng.randint(-10, 10)), 1)

                    rec = RateRecommendation(
                        hotel_id=hotel.id,
                        room_type_id=room.id,
                        target_date=target,
                        recommended_rate=rec_rate,
                        min_rate=room.min_rate,
                        max_rate=room.max_rate,
                        forecasted_occupancy=occ,
                        confidence_score=round(0.7 + rng.random() * 0.25, 2),
                        status="pending",
                    )
                    db.add(rec)

                    if day_offset < 0:
                        history = RateHistory(
                            room_type_id=room.id,
                            rate=rec_rate,
                            source="ai",
                            effective_date=target,
                            created_at=datetime(target.year, target.month, target.day, 12, 0, tzinfo=timezone.utc),
                        )
                        db.add(history)

                last_applied = None
                for day_offset in range(-60, 0):
                    target = today + timedelta(days=day_offset)
                    sm = season_multiplier(target)
                    jitter = 1.0 + (rng.random() - 0.5) * 0.1
                    rate = round(room.base_rate * sm * jitter)
                    rate = max(room.min_rate, min(room.max_rate, rate))

                    rec = RateRecommendation(
                        hotel_id=hotel.id,
                        room_type_id=room.id,
                        target_date=target,
                        recommended_rate=rate,
                        min_rate=room.min_rate,
                        max_rate=room.max_rate,
                        forecasted_occupancy=round(30 + 40 * sm + rng.randint(-10, 10), 1),
                        confidence_score=round(0.7 + rng.random() * 0.25, 2),
                        status="applied",
                        applied_at=datetime(target.year, target.month, target.day, 8, 0, tzinfo=timezone.utc),
                    )
                    db.add(rec)

                    history = RateHistory(
                        room_type_id=room.id,
                        rate=rate,
                        source="ai",
                        effective_date=target,
                        created_at=datetime(target.year, target.month, target.day, 8, 0, tzinfo=timezone.utc),
                    )
                    db.add(history)
                    last_applied = rate

                for day_offset in range(-60, 0):
                    target = today + timedelta(days=day_offset)
                    sm = season_multiplier(target)
                    prob_book = 0.2 + 0.5 * sm
                    if rng.random() < prob_book:
                        nights = rng.randint(1, 4)
                        occupancy_rng = rng.uniform(0.7, 0.95)
                        booking_rate = round(last_applied or room.base_rate * occupancy_rng)

                        booking = Booking(
                            hotel_id=hotel.id,
                            room_type_id=room.id,
                            check_in=target,
                            check_out=target + timedelta(days=nights),
                            adults=room.max_occupancy - rng.randint(0, 1),
                            booking_rate=booking_rate,
                            channel=rng.choice(["direct", "booking.com", "expedia", "direct", "direct"]),
                            status="confirmed",
                            booked_at=datetime(target.year, target.month, target.day, rng.randint(8, 20), rng.randint(0, 59), tzinfo=timezone.utc),
                        )
                        db.add(booking)

                days_range = list(range(-60, 0))
                rng.shuffle(days_range)
                canceled = 0
                for day_offset in days_range[:int(len(days_range) * 0.05)]:
                    target = today + timedelta(days=day_offset)
                    nights = rng.randint(1, 3)
                    cancel_booking = Booking(
                        hotel_id=hotel.id,
                        room_type_id=room.id,
                        check_in=target,
                        check_out=target + timedelta(days=nights),
                        adults=2,
                        booking_rate=round(room.base_rate * 0.9),
                        channel=rng.choice(["booking.com", "expedia"]),
                        status="canceled",
                        booked_at=datetime(target.year, target.month, target.day, rng.randint(8, 20), rng.randint(0, 59), tzinfo=timezone.utc),
                        canceled_at=datetime(target.year, target.month, target.day, rng.randint(8, 20), rng.randint(0, 59), tzinfo=timezone.utc),
                    )
                    db.add(cancel_booking)
                    canceled += 1

        pms_data = [
            (all_hotels[0], "MKH001"),
            (all_hotels[1], "MDN002"),
            (all_hotels[2], "RUH003"),
        ]
        for hotel, prop_code in pms_data:
            conn = PMSConnection(
                organization_id=org.id,
                hotel_id=hotel.id,
                provider="opera_cloud",
                property_code=prop_code,
                is_active=True,
                sync_status="synced",
                last_sync_at=datetime.now(timezone.utc) - timedelta(hours=rng.randint(1, 12)),
                encrypted_client_id="seed_encrypted_client_id",
                encrypted_client_secret="seed_encrypted_client_secret",
            )
            db.add(conn)

        await db.commit()

    total_rate_recs = 5 * 2.5 * 150 if "total_rate_recs" not in dir() else None
    print()
    print("✓ Seed complete!")
    print(f"  1 organization ({org.name})")
    print(f"  1 admin user (admin@alharam.sa / admin123456)")
    print(f"  {len(all_hotels)} hotels across Saudi Arabia")
    print(f"  ~{5 * 2.5:.0f} room types per hotel on average")
    print(f"  90 days of forward rate recommendations per room type")
    print(f"  60 days of historical rates and bookings")
    print(f"  3 Opera Cloud PMS connections")
    print()
    print("Login at http://localhost:3000/login")
    print("  Email: admin@alharam.sa")
    print("  Password: admin123456")


async def main():
    print("Seeding Saudi RMS database...")
    print("=" * 40)
    await seed(drop_first=True)


if __name__ == "__main__":
    asyncio.run(main())
