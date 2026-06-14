"""
Revenue-maximizing price optimizer with constrained optimization.
Balances occupancy and ADR to maximize RevPAR.
"""

from dataclasses import dataclass
from typing import Callable
import numpy as np


@dataclass
class PriceRecommendation:
    room_type_id: str
    target_date: str
    base_rate: float
    recommended_rate: float
    min_rate: float
    max_rate: float
    expected_occupancy: float
    expected_revenue: float
    strategy: str


class PriceOptimizer:
    def __init__(self, demand_elasticity: float = -0.8):
        self.elasticity = demand_elasticity

    def optimize(
        self,
        base_rate: float,
        min_rate: float,
        max_rate: float,
        forecasted_occupancy: float,
        competitors: list[float] | None = None,
        event_multiplier: float = 1.0,
    ) -> dict:
        competitor_avg = np.mean(competitors) if competitors else base_rate
        competitor_floor = max(base_rate * 0.7, competitor_avg * 0.85)

        candidate_rates = np.linspace(max(min_rate, competitor_floor), max_rate, 50)
        best_rev = 0
        best_rate = base_rate
        best_occ = forecasted_occupancy

        for rate in candidate_rates:
            price_change = (rate - base_rate) / base_rate
            occ_change = self.elasticity * price_change
            expected_occ = forecasted_occupancy * (1 + occ_change)
            expected_occ = max(0.05, min(expected_occ, 0.95))

            expected_rev = rate * expected_occ * event_multiplier

            if expected_rev > best_rev:
                best_rev = expected_rev
                best_rate = rate
                best_occ = expected_occ

        occ_percent = round(best_occ * 100, 1)
        rev_per_room = round(best_rate * best_occ, 2)

        return {
            "recommended_rate": round(best_rate, 2),
            "expected_occupancy": occ_percent,
            "expected_revenue_per_room": rev_per_room,
            "strategy": self._classify_strategy(best_rate, base_rate, best_occ, forecasted_occupancy),
        }

    def _classify_strategy(
        self, recommended: float, base: float, expected_occ: float, forecasted_occ: float
    ) -> str:
        if recommended > base * 1.15 and expected_occ > forecasted_occ * 0.95:
            return "aggressive"
        elif recommended > base * 1.05:
            return "moderate_increase"
        elif recommended < base * 0.95:
            return "discount"
        else:
            return "maintain"

    def bulk_optimize(
        self,
        room_types: list[dict],
        forecast: dict[str, float],
        event_date: date | None = None,
    ) -> list[PriceRecommendation]:
        from datetime import date

        event_mul = 1.0
        if event_date:
            days_until = (event_date - date.today()).days
            if 0 <= days_until <= 30:
                event_mul = 1.0 + max(0, (30 - days_until) / 30 * 0.5)

        results = []
        for rt in room_types:
            occ_key = f"rt_{rt['id']}"
            forecasted_occ = forecast.get(occ_key, 0.6)
            opt = self.optimize(
                base_rate=rt["base_rate"],
                min_rate=rt["min_rate"],
                max_rate=rt["max_rate"],
                forecasted_occupancy=forecasted_occ,
                competitors=rt.get("competitor_rates"),
                event_multiplier=event_mul,
            )
            results.append(
                PriceRecommendation(
                    room_type_id=str(rt["id"]),
                    target_date=str(date.today()),
                    base_rate=rt["base_rate"],
                    recommended_rate=opt["recommended_rate"],
                    min_rate=rt["min_rate"],
                    max_rate=rt["max_rate"],
                    expected_occupancy=opt["expected_occupancy"],
                    expected_revenue=opt["expected_revenue_per_room"],
                    strategy=opt["strategy"],
                )
            )
        return results
