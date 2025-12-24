from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class BaselineStat(str, Enum):
    mean = "mean"
    median = "median"


class EventPriceMode(str, Enum):
    min = "min"
    mean = "mean"


class VolumeMode(str, Enum):
    absolute = "absolute"
    relative_to_baseline = "relative_to_baseline"


class ScanRequest(BaseModel):
    baseline_hours: int = Field(6, ge=1, le=30)
    event_window_blocks: int = Field(1, ge=1, le=12)
    still_low_blocks: int = Field(3, ge=0, le=36)

    baseline_stat: BaselineStat = BaselineStat.median
    event_price_mode: EventPriceMode = EventPriceMode.min

    min_drop_pct: float = Field(0.07, ge=0.0, le=0.95)

    volume_mode: VolumeMode = VolumeMode.relative_to_baseline
    min_event_volume: int = Field(0, ge=0)
    volume_multiplier: float = Field(3.0, ge=0.0)

    still_low_pct: float = Field(0.05, ge=0.0, le=0.95)

    # Robustness against sparse trading (avgLowPrice can be null for many buckets).
    # These thresholds are counts of buckets WITH a finite avgLowPrice.
    min_valid_baseline_price_points: int = Field(12, ge=0)
    min_valid_event_price_points: int = Field(1, ge=0)
    min_valid_still_low_price_points: int = Field(1, ge=0)

    # Optional item filters
    min_buy_limit: int | None = Field(default=None, ge=0)
    max_buy_limit: int | None = Field(default=None, ge=0)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)

    # Behavior
    sort_by: Literal["biggest_drop", "most_recent", "biggest_volume"] = "biggest_drop"
    limit: int = Field(100, ge=1, le=500)


class ScanResult(BaseModel):
    item_id: int
    name: str
    dump_bucket_ts: int

    baseline_price: float
    event_price: float
    price_drop_pct: float

    event_volume: int
    baseline_mean_5m_volume: float | None = None

    still_low: bool
    latest_price: float | None = None


class ScanResponse(BaseModel):
    results: list[ScanResult]
    meta: dict[str, object] = {}


