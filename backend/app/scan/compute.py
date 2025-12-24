from __future__ import annotations

import numpy as np

from app.scan.schemas import BaselineStat, EventPriceMode, ScanRequest, ScanResult, VolumeMode


def _baseline_stat(arr: np.ndarray, stat: BaselineStat) -> float:
    if arr.size == 0:
        return float("nan")
    if stat == BaselineStat.mean:
        return float(np.nanmean(arr))
    return float(np.nanmedian(arr))


def _event_price(arr: np.ndarray, mode: EventPriceMode) -> float:
    if arr.size == 0:
        return float("nan")
    if mode == EventPriceMode.mean:
        return float(np.nanmean(arr))
    return float(np.nanmin(arr))


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

    Arrays must be aligned: same length, ordered by time ascending.
    """
    n = bucket_ts.size
    L = req.baseline_hours * 12
    M = req.event_window_blocks
    S = req.still_low_blocks

    if n < L + M + S + 1:
        return None

    best: ScanResult | None = None

    # Candidate start index t: need baseline [t-L, t-1], dump [t, t+M-1], stilllow [t+M, t+M+S-1]
    for t in range(L, n - (M + S)):
        baseline_slice = slice(t - L, t)
        event_slice = slice(t, t + M)
        post_slice = slice(t + M, t + M + S)

        base_prices = avg_low[baseline_slice]
        base_vols = low_vol[baseline_slice]
        event_prices = avg_low[event_slice]
        event_vols = low_vol[event_slice]

        baseline_price = _baseline_stat(base_prices, req.baseline_stat)
        if not np.isfinite(baseline_price) or baseline_price <= 0:
            continue

        event_price = _event_price(event_prices, req.event_price_mode)
        if not np.isfinite(event_price) or event_price <= 0:
            continue

        price_drop_pct = (event_price - baseline_price) / baseline_price
        if price_drop_pct > -req.min_drop_pct:
            continue

        event_volume = int(np.nansum(event_vols))

        baseline_mean_5m_vol = float(np.nanmean(base_vols)) if base_vols.size else float("nan")

        if req.volume_mode == VolumeMode.absolute:
            if event_volume < req.min_event_volume:
                continue
        else:
            # relative_to_baseline
            if not np.isfinite(baseline_mean_5m_vol) or baseline_mean_5m_vol <= 0:
                continue
            if event_volume < baseline_mean_5m_vol * req.volume_multiplier:
                continue

        # still-low check
        still_low = True
        if S > 0:
            threshold = baseline_price * (1 - req.still_low_pct)
            post_prices = avg_low[post_slice]
            still_low = bool(np.all(post_prices <= threshold))

        if not still_low:
            continue

        dump_bucket_ts = int(bucket_ts[t])

        cand = ScanResult(
            item_id=item_id,
            name=name,
            dump_bucket_ts=dump_bucket_ts,
            baseline_price=float(baseline_price),
            event_price=float(event_price),
            price_drop_pct=float(price_drop_pct),
            event_volume=event_volume,
            baseline_mean_5m_volume=None if not np.isfinite(baseline_mean_5m_vol) else float(baseline_mean_5m_vol),
            still_low=True,
            latest_price=None,
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
            else:
                # biggest_drop
                if cand.price_drop_pct < best.price_drop_pct:
                    best = cand

    return best


