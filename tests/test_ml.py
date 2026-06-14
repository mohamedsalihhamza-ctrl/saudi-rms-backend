import pytest
from datetime import date, timedelta
import numpy as np

from app.services.ml import DemandForecaster, PriceOptimizer


def test_forecaster_skips_with_insufficient_data():
    f = DemandForecaster()
    result = f.train("hotel-1", [{"date": date.today(), "occupancy": 5, "adr": 300}])
    assert result["status"] == "skipped"


def test_forecaster_trains_and_predicts():
    f = DemandForecaster()
    bookings = []
    today = date.today()
    for i in range(30):
        bookings.append({
            "date": today - timedelta(days=30 - i),
            "occupancy": 15 + 5 * np.sin(i * 0.5),
            "adr": 300 + 50 * np.sin(i * 0.3),
        })

    result = f.train("hotel-2", bookings)
    assert result["status"] == "trained"
    assert result["samples"] == 30
    assert f.is_trained("hotel-2")

    pred = f.predict("hotel-2", today + timedelta(days=5))
    assert pred is not None
    assert 0 <= pred <= 1

    bulk = f.predict_bulk("hotel-2", 10)
    assert bulk is not None
    assert len(bulk) == 10

    untrained = f.predict("unknown", today)
    assert untrained is None


def test_price_optimizer():
    opt = PriceOptimizer()
    rate = opt.compute_rate(base_rate=500, occupancy=0.8, min_rate=300, max_rate=800)
    assert 300 <= rate <= 800

    low = opt.compute_rate(base_rate=500, occupancy=0.2, min_rate=300, max_rate=800)
    assert low < rate

    high_confidence = opt.compute_rate(base_rate=500, occupancy=0.8, min_rate=300, max_rate=800, confidence=0.9)
    assert high_confidence >= rate

    no_occupancy = opt.compute_rate(base_rate=500, occupancy=None, min_rate=300, max_rate=800)
    assert no_occupancy == 500


@pytest.mark.asyncio
async def test_ml_train_endpoint(client):
    # Register first
    resp = await client.post(
        "/api/v1/users/register",
        json={"email": "ml-test@example.com", "password": "testpass123", "full_name": "ML User", "organization_name": "ML Test Org"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Train without hotels
    resp = await client.get("/api/v1/ml/status", headers=headers)
    assert resp.status_code == 200
    status = resp.json()
    assert status["engine"] == "sklearn (RandomForestRegressor)"
    assert len(status["hotels"]) == 0


@pytest.mark.asyncio
async def test_ml_train_and_forecast(client):
    # Register, create hotel, create room type, create booking data, then train
    resp = await client.post(
        "/api/v1/users/register",
        json={"email": "ml-full@example.com", "password": "testpass123", "full_name": "ML Full", "organization_name": "ML Full Org"},
    )
    assert resp.status_code == 201
    data = resp.json()
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/hotels/",
        json={"name": "ML Hotel", "city": "Riyadh", "star_rating": 4, "total_rooms": 50, "currency": "SAR"},
        headers=headers,
    )
    assert resp.status_code == 201
    hotel_id = resp.json()["id"]

    # Train with no booking data (will skip)
    resp = await client.post(f"/api/v1/ml/train/{hotel_id}", headers=headers)
    assert resp.status_code == 200
    result = resp.json()
    assert result["status"] == "skipped"
    assert "insufficient data" in result["message"].lower()

    # Check status shows untrained
    resp = await client.get("/api/v1/ml/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["hotels"][0]["model_trained"] is False


@pytest.mark.asyncio
async def test_ml_forecast_endpoint_needs_training(client):
    resp = await client.post(
        "/api/v1/users/register",
        json={"email": "ml-forecast@example.com", "password": "testpass123", "full_name": "ML Forecast", "organization_name": "ML Forecast Org"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/hotels/",
        json={"name": "Forecast Hotel", "city": "Jeddah", "star_rating": 3, "total_rooms": 30, "currency": "SAR"},
        headers=headers,
    )
    assert resp.status_code == 201
    hotel_id = resp.json()["id"]

    # Forecast without training should fail
    resp = await client.get(f"/api/v1/ml/forecast/{hotel_id}", headers=headers)
    assert resp.status_code == 400
    assert "not trained" in resp.json()["detail"].lower()
