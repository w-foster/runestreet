from __future__ import annotations

import numpy as np


def _cv(values: np.ndarray) -> float | None:
    v = values[np.isfinite(values)]
    if v.size < 3:
        return None
    mean = float(np.mean(v))
    if mean <= 0:
        return None
    std = float(np.std(v))
    return std / mean


def compute_daily_metrics_from_5m(
    avg_low: np.ndarray,
    avg_high: np.ndarray,
    low_vol: np.ndarray,
    high_vol: np.ndarray,
) -> dict[str, float | int | None]:
    """
    Inputs are last-24h 5m arrays (length ~288), may contain NaNs.
    """
    total_vol = int(np.nansum(low_vol) + np.nansum(high_vol))

    low = avg_low[np.isfinite(avg_low)]
    high = avg_high[np.isfinite(avg_high)]
    mid = None
    spread_abs_med = None
    spread_pct_med = None
    stability_1d = None

    # Mid/spread require both sides at same timestamps.
    both = np.isfinite(avg_low) & np.isfinite(avg_high)
    if np.any(both):
        mids = (avg_low[both] + avg_high[both]) / 2.0
        spreads = (avg_high[both] - avg_low[both]).astype("float64")
        if mids.size >= 3:
            mid = float(np.median(mids))
            spread_abs_med = float(np.median(spreads))
            denom = float(np.median(mids))
            if denom > 0:
                spread_pct_med = float(np.median(spreads / mids))
            stability_1d = _cv(mids)

    return {
        "daily_volume_24h": total_vol,
        "daily_mid_price": mid,
        "spread_abs_median": spread_abs_med,
        "spread_pct_median": spread_pct_med,
        "stability_cv_1d": stability_1d,
    }


def stability_from_daily_timeseries(mids: np.ndarray) -> dict[str, float | None]:
    """
    mids: daily mid prices (1 point per day), most-recent last.
    """
    def last_n(n: int) -> np.ndarray:
        if mids.size < n:
            return mids
        return mids[-n:]

    return {
        "stability_cv_7d": _cv(last_n(7)),
        "stability_cv_30d": _cv(last_n(30)),
        "stability_cv_1y": _cv(last_n(365)),
    }


def score_spread(
    spread_pct_median: float | None,
    spread_abs_median: float | None,
    stability_cv_1d: float | None,
    stability_cv_7d: float | None,
    stability_cv_30d: float | None,
    stability_cv_1y: float | None,
) -> float:
    """
    Higher is better.

    Intuition:
    - Reward larger spreads (prefer pct spread).
    - Penalize volatility (CV) across horizons (lower CV is better).
    """
    sp = float(spread_pct_median or 0.0)
    sa = float(spread_abs_median or 0.0)

    # Normalize volatility penalty; missing -> mild penalty.
    v1 = float(stability_cv_1d if stability_cv_1d is not None else 0.25)
    v7 = float(stability_cv_7d if stability_cv_7d is not None else 0.35)
    v30 = float(stability_cv_30d if stability_cv_30d is not None else 0.40)
    v1y = float(stability_cv_1y if stability_cv_1y is not None else 0.50)

    stability_factor = 1.0 / (1.0 + 2.0 * v1 + 1.0 * v7 + 0.7 * v30 + 0.5 * v1y)
    return (sp * 100.0 + min(sa / 1000.0, 50.0)) * stability_factor


