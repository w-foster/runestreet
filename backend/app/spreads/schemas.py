from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SpreadsScanRequest(BaseModel):
    # Filters
    min_daily_volume_24h: int | None = Field(default=None, ge=0)
    max_daily_volume_24h: int | None = Field(default=None, ge=0)
    min_avg_price: float | None = Field(default=None, ge=0)
    max_avg_price: float | None = Field(default=None, ge=0)
    min_buy_limit: int | None = Field(default=None, ge=0)

    # Scoring / ranking
    sort_by: Literal["score", "spread_pct", "spread_abs", "stability_1y"] = "score"
    limit: int = Field(50, ge=1, le=200)

    # How many items to enrich with 1y stability (per-item /timeseries 24h).
    # We shortlist by daily spread first, then fetch stability for this many.
    stability_top_k: int = Field(150, ge=10, le=500)


class SpreadsScanResult(BaseModel):
    item_id: int
    name: str
    buy_limit: int | None = None

    daily_volume_24h: int
    daily_mid_price: float | None = None

    spread_abs_median: float | None = None
    spread_pct_median: float | None = None

    stability_cv_1d: float | None = None
    stability_cv_7d: float | None = None
    stability_cv_30d: float | None = None
    stability_cv_1y: float | None = None

    score: float


class SpreadsScanResponse(BaseModel):
    results: list[SpreadsScanResult]
    meta: dict[str, object] = {}


