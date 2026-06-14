"""
Demand forecasting for hotel room types.
Uses XGBoost for point forecasts with feature engineering for
seasonality (Hajj, Ramadan), day-of-week, events, and price elasticity.
"""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ForecastResult:
    target_date: date
    predicted_occupancy: float
    predicted_adr: float
    lower_bound: float
    upper_bound: float
    confidence_score: float


class DemandForecaster:
    def __init__(self):
        self.model: XGBRegressor | None = None
        self._fitted = False

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        dates = pd.to_datetime(df["date"])
        features = df.copy()

        features["day_of_week"] = dates.dt.dayofweek
        features["month"] = dates.dt.month
        features["day_of_year"] = dates.dt.dayofyear
        features["is_weekend"] = features["day_of_week"].isin([4, 5]).astype(int)
        features["quarter"] = dates.dt.quarter
        features["days_to_hajj"] = df.get("days_to_hajj", 365)
        features["is_ramadan"] = df.get("is_ramadan", 0).astype(int)
        features["days_to_ramadan"] = df.get("days_to_ramadan", 365)

        features["occupancy_lag_7"] = df["occupancy"].shift(7)
        features["occupancy_lag_14"] = df["occupancy"].shift(14)
        features["occupancy_lag_28"] = df["occupancy"].shift(28)
        features["occupancy_rolling_7"] = df["occupancy"].rolling(7).mean()
        features["occupancy_rolling_28"] = df["occupancy"].rolling(28).mean()
        features["adr_lag_7"] = df["adr"].shift(7)
        features["adr_rolling_7"] = df["adr"].rolling(7).mean()

        return features

    def fit(self, historical_data: pd.DataFrame):
        required = ["date", "occupancy", "adr"]
        for col in required:
            if col not in historical_data.columns:
                raise ValueError(f"Missing required column: {col}")

        df = self._build_features(historical_data)
        df = df.dropna()

        feature_cols = [c for c in df.columns if c not in ["date", "occupancy", "adr", "revenue"]]

        X = df[feature_cols].values
        y_occ = df["occupancy"].values
        y_adr = df["adr"].values

        self.occ_model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        self.adr_model = XGBRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )

        self.occ_model.fit(X, y_occ)
        self.adr_model.fit(X, y_adr)
        self._fitted = True
        self._feature_cols = feature_cols

    def predict(
        self,
        future_features: pd.DataFrame,
        n_days: int = 90,
        uncertainty: bool = True,
    ) -> list[ForecastResult]:
        if not self._fitted:
            raise RuntimeError("Model must be fitted before prediction")

        results = []
        for i in range(n_days):
            row = future_features.iloc[[i]]
            X = row[self._feature_cols].values

            occ = float(self.occ_model.predict(X)[0])
            adr = float(self.adr_model.predict(X)[0])

            occ = max(0.0, min(occ, 1.0))
            adr = max(0.0, adr)

            uncertainty_margin = 0.05 * (1 + i / n_days)
            confidence_score = max(0.5, 1.0 - uncertainty_margin)

            target_date = date.today() + timedelta(days=i + 1)

            results.append(
                ForecastResult(
                    target_date=target_date,
                    predicted_occupancy=round(occ * 100, 1),
                    predicted_adr=round(adr, 2),
                    lower_bound=round(max(0, occ - uncertainty_margin) * 100, 1),
                    upper_bound=round(min(1, occ + uncertainty_margin) * 100, 1),
                    confidence_score=round(confidence_score, 3),
                )
            )

        return results
