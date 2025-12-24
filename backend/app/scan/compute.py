from __future__ import annotations

import numpy as np

from app.scan.schemas import BaselineStat, EventPriceMode, ScanRequest, ScanResult, VolumeMode


def _baseline_stat(arr: np.ndarray, stat: BaselineStat) -> float:
    if arr.size == 0:
        return float("nan")
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")
    if stat == BaselineStat.mean:
        return float(np.mean(arr))
    return float(np.median(arr))


def _event_price(arr: np.ndarray, mode: EventPriceMode) -> float:
    if arr.size == 0:
        return float("nan")
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")
    if mode == EventPriceMode.mean:
        return float(np.mean(arr))
    return float(np.min(arr))


def scan_item_series(
    *,
    item_id: int,
    name: str,
    bucket_ts: np.ndarray,
    avg_low: np.ndarray,
    low_vol: np.ndarray,
    req: ScanRequest,
) -> ScanResult | None:
    """
    Find the best dump event for this item within the provided window.
    Arrays must be aligned (same length), ordered by time ascending.
    """

    n = bucket_ts.size
    L = req.baseline_hours * 12
    M = req.event_window_blocks
    S = req.still_low_blocks

    if n < max(L + M + 2, 288):  # need at least 24h for daily volume metrics
        return None

    # 24h daily volume anchored to NOW (latest 288 buckets). This is what you trade on.
    daily_window = low_vol[-288:] if n >= 288 else low_vol
    daily_volume_24h = int(np.nansum(daily_window))

    if req.min_daily_volume_24h is not None and daily_volume_24h < req.min_daily_volume_24h:
        return None
    if req.max_daily_volume_24h is not None and daily_volume_24h > req.max_daily_volume_24h:
        return None

    latest_valid = avg_low[np.isfinite(avg_low)]
    latest_price = float(latest_valid[-1]) if latest_valid.size else None

    best: ScanResult | None = None

    # Candidate start index t:
    # baseline [t-L, t-1], dump [t, t+M-1], and we require at least one bucket after dump.
    for t in range(L, n - (M + 1)):
        baseline_slice = slice(t - L, t)
        event_slice = slice(t, t + M)

        base_prices = avg_low[baseline_slice]
        base_vols = low_vol[baseline_slice]
        event_prices = avg_low[event_slice]
        event_vols = low_vol[event_slice]

        base_valid = base_prices[np.isfinite(base_prices)]
        if base_valid.size < req.min_valid_baseline_price_points:
            continue
        baseline_price = _baseline_stat(base_valid, req.baseline_stat)
        if not np.isfinite(baseline_price) or baseline_price <= 0:
            continue

        event_valid = event_prices[np.isfinite(event_prices)]
        if event_valid.size < req.min_valid_event_price_points:
            continue
        event_price = _event_price(event_valid, req.event_price_mode)
        if not np.isfinite(event_price) or event_price <= 0:
            continue

        price_drop_pct = (event_price - baseline_price) / baseline_price
        if price_drop_pct > -req.min_drop_pct:
            continue

        event_volume = int(np.nansum(event_vols))
        baseline_mean_5m_vol = float(np.nanmean(base_vols)) if base_vols.size else float("nan")

        event_daily_pct: float | None = None
        if daily_volume_24h > 0:
            event_daily_pct = float(event_volume) / float(daily_volume_24h)

        # Volume shock mode
        if req.volume_mode == VolumeMode.absolute:
            if event_volume < req.min_event_volume:
                continue
        elif req.volume_mode == VolumeMode.daily_pct:
            if event_daily_pct is None:
                continue
            if event_daily_pct < req.min_event_daily_pct:
                continue
        else:
            # relative_to_baseline
            if not np.isfinite(baseline_mean_5m_vol) or baseline_mean_5m_vol <= 0:
                continue
            if event_volume < baseline_mean_5m_vol * req.volume_multiplier:
                continue

        # Still-low NOW check: require the last max(S,1) buckets ending now to be <= threshold,
        # and ensure we are looking at *after* the dump window.
        threshold = baseline_price * (1 - req.still_low_pct)
        s_eff = max(S, 1)
        tail_start = max(t + M, n - s_eff)
        if tail_start >= n:
            continue
        tail_prices = avg_low[tail_start:n]
        tail_valid = tail_prices[np.isfinite(tail_prices)]
        if tail_valid.size < req.min_valid_still_low_price_points:
            continue
        if not bool(np.all(tail_valid <= threshold)):
            continue

        cand = ScanResult(
            item_id=item_id,
            name=name,
            dump_bucket_ts=int(bucket_ts[t]),
            baseline_price=float(baseline_price),
            event_price=float(event_price),
            price_drop_pct=float(price_drop_pct),
            event_volume=event_volume,
            baseline_mean_5m_volume=None if not np.isfinite(baseline_mean_5m_vol) else float(baseline_mean_5m_vol),
            daily_volume_24h=daily_volume_24h,
            event_daily_pct=event_daily_pct,
            still_low=True,
            latest_price=latest_price,
        )

        if best is None:
            best = cand
        else:
            if req.sort_by == "most_recent":
                if cand.dump_bucket_ts > best.dump_bucket_ts:
                    best = cand
            elif req.sort_by == "biggest_volume":
                if cand.event_volume > best.event_volume:
                    best = cand
            elif req.sort_by == "biggest_event_daily_pct":
                a = cand.event_daily_pct or -1.0
                b = best.event_daily_pct or -1.0
                if a > b:
                    best = cand
            else:
                # biggest_drop
                if cand.price_drop_pct < best.price_drop_pct:
                    best = cand

    return best


