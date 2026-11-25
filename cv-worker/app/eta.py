"""Turnover ETA predictor: statistical venue-median/IQR baseline + optional LightGBM."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class TurnoverQuote:
    min_minutes: int
    max_minutes: int
    median_minutes: float
    confidence_tier: str  # "High" | "Medium" | "Low"
    method: str  # "statistical_iqr" | "lightgbm"


class TurnoverETAPredictor:
    """
    Predicts remaining minutes until a table is free.
    v1.0 default uses statistical venue median/IQR by party size (45m default if <7d history);
    supports optional LightGBM booster when a trained model artifact is provided.
    """

    def __init__(self, lgb_model_path: Path | None = None) -> None:
        self._booster: Any = None
        if lgb_model_path is not None and lgb_model_path.exists():
            import lightgbm as lgb

            self._booster = lgb.Booster(model_file=str(lgb_model_path))

    def predict(
        self,
        *,
        elapsed_minutes: float,
        seat_capacity: int,
        state: str,
        historical_turns_minutes: list[float] | None = None,
    ) -> TurnoverQuote:
        if state == "FREE":
            return TurnoverQuote(0, 0, 0.0, "High", "statistical_iqr")
        if state == "NEEDS_CLEANING":
            return TurnoverQuote(2, 5, 3.0, "High", "statistical_iqr")

        if self._booster is not None:
            feats = np.array([[elapsed_minutes, float(seat_capacity)]], dtype=np.float32)
            rem = max(1.0, float(self._booster.predict(feats)[0]))
            return TurnoverQuote(
                min_minutes=max(1, int(round(rem * 0.75))),
                max_minutes=max(2, int(round(rem * 1.25))),
                median_minutes=round(rem, 1),
                confidence_tier="High",
                method="lightgbm",
            )

        samples = [float(x) for x in (historical_turns_minutes or []) if x > 5.0]
        if len(samples) >= 10:
            arr = np.array(samples, dtype=np.float64)
            p25, p50, p75 = np.percentile(arr, [25, 50, 75])
            tier = "High" if len(samples) >= 30 else "Medium"
        else:
            # Cold-start baseline per SCR-009 spec ("baseline 45m turn estimate")
            base = 35.0 if seat_capacity <= 2 else (45.0 if seat_capacity <= 4 else 60.0)
            p25, p50, p75 = base - 8.0, base, base + 12.0
            tier = "Low"

        rem_low = max(1, int(round(max(2.0, p25 - elapsed_minutes))))
        rem_med = max(1.0, round(max(3.0, p50 - elapsed_minutes), 1))
        rem_high = max(rem_low + 2, int(round(max(5.0, p75 - elapsed_minutes))))
        return TurnoverQuote(
            min_minutes=rem_low,
            max_minutes=rem_high,
            median_minutes=rem_med,
            confidence_tier=tier,
            method="statistical_iqr",
        )
