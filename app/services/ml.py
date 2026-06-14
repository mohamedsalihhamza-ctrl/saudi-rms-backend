import logging
from datetime import date, timedelta
from decimal import Decimal

import numpy as np
from sklearn.ensemble import RandomForestRegressor

logger = logging.getLogger("ml")

FORECAST_DAYS = 90


class DemandForecaster:
    def __init__(self):
        self._models: dict[str, RandomForestRegressor] = {}

    def is_trained(self, hotel_id: str) -> bool:
        return hotel_id in self._models

    def train(self, hotel_id: str, bookings: list[dict]) -> dict:
        if len(bookings) < 14:
            return {"status": "skipped", "reason": f"Insufficient data ({len(bookings)} days, need 14+)", "samples": len(bookings)}

        dates_raw = [b["date"] for b in bookings]
        occupancies = np.array([b["occupancy"] for b in bookings], dtype=float)

        features = []
        for d in dates_raw:
            dt = d if isinstance(d, date) else date.fromisoformat(str(d))
            features.append([dt.weekday(), dt.month, 1 if dt.weekday() >= 4 else 0])

        X = np.array(features)
        y = occupancies

        model = RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42)
        model.fit(X, y)

        self._models[hotel_id] = model
        return {"status": "trained", "samples": len(bookings), "hotel_id": hotel_id}

    def predict(self, hotel_id: str, target_date: date) -> float | None:
        model = self._models.get(hotel_id)
        if model is None:
            return None

        features = np.array([[target_date.weekday(), target_date.month, 1 if target_date.weekday() >= 4 else 0]])
        pred = model.predict(features)[0]
        return float(np.clip(pred, 0, 1))

    def predict_bulk(self, hotel_id: str, days: int = FORECAST_DAYS) -> dict[str, float] | None:
        model = self._models.get(hotel_id)
        if model is None:
            return None

        today = date.today()
        results = {}
        for i in range(days):
            target = today + timedelta(days=i)
            features = np.array([[target.weekday(), target.month, 1 if target.weekday() >= 4 else 0]])
            pred = model.predict(features)[0]
            results[target.isoformat()] = float(np.clip(pred, 0, 1))

        return results


class PriceOptimizer:
    def compute_rate(
        self,
        base_rate: float,
        occupancy: float | None,
        min_rate: float,
        max_rate: float,
        confidence: float | None = None,
    ) -> float:
        if occupancy is None:
            return base_rate

        multiplier = 1.0 + (occupancy - 0.6) * 0.5
        multiplier = max(0.7, min(multiplier, 1.5))

        if confidence is not None and confidence > 0.7:
            multiplier *= 1.1

        rate = base_rate * multiplier
        return round(max(min_rate, min(rate, max_rate)), 2)


forecaster = DemandForecaster()
optimizer = PriceOptimizer()
