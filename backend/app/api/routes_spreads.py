from __future__ import annotations

import time
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ItemBucket5m, ItemMapping, ItemTimeseries24h
from app.osrs.client import OsrsPricesClient
from app.osrs.ingest import ensure_buckets_cached, ensure_mapping_cached, floor_to_5m
from app.osrs.timeseries_24h import ensure_timeseries_24h_cached
from app.spreads.compute import compute_daily_metrics_from_5m, score_spread, stability_from_daily_timeseries
from app.spreads.schemas import SpreadsScanRequest, SpreadsScanResponse, SpreadsScanResult

router = APIRouter()


@router.post("/spreads/scan", response_model=SpreadsScanResponse)
async def spreads_scan(req: SpreadsScanRequest, db: Session = Depends(get_db)) -> SpreadsScanResponse:
    # Ensure mapping + last 24h of 5m buckets cached
    now = floor_to_5m(int(time.time()))
    bucket_ts_list = [now - 300 * i for i in range(288)]

    client = OsrsPricesClient()
    try:
        await ensure_mapping_cached(db, client)
        ingest_meta = await ensure_buckets_cached(db, client, bucket_ts_list)
    finally:
        await client.aclose()

    mapping_rows = db.execute(select(ItemMapping.item_id, ItemMapping.name, ItemMapping.limit)).all()
    id_to_meta = {int(r[0]): (str(r[1]), (int(r[2]) if r[2] is not None else None)) for r in mapping_rows}

    rows = db.execute(
        select(
            ItemBucket5m.item_id,
            ItemBucket5m.bucket_ts,
            ItemBucket5m.avg_low,
            ItemBucket5m.avg_high,
            ItemBucket5m.low_vol,
            ItemBucket5m.high_vol,
        ).where(ItemBucket5m.bucket_ts.in_(bucket_ts_list))
    ).all()

    per_item: dict[int, list[tuple[int, int | None, int | None, int, int]]] = defaultdict(list)
    for item_id, bucket_ts, avg_low, avg_high, low_vol, high_vol in rows:
        per_item[int(item_id)].append(
            (int(bucket_ts), int(avg_low) if avg_low is not None else None, int(avg_high) if avg_high is not None else None, int(low_vol), int(high_vol))
        )

    prelim: list[SpreadsScanResult] = []
    for item_id, series in per_item.items():
        name, buy_limit = id_to_meta.get(item_id, (f"item_{item_id}", None))

        if req.min_buy_limit is not None:
            if buy_limit is None or buy_limit < req.min_buy_limit:
                continue

        series.sort(key=lambda x: x[0])
        avg_low = np.array([np.nan if s[1] is None else float(s[1]) for s in series], dtype="float64")
        avg_high = np.array([np.nan if s[2] is None else float(s[2]) for s in series], dtype="float64")
        low_vol = np.array([float(s[3]) for s in series], dtype="float64")
        high_vol = np.array([float(s[4]) for s in series], dtype="float64")

        m = compute_daily_metrics_from_5m(avg_low, avg_high, low_vol, high_vol)
        daily_vol = int(m["daily_volume_24h"] or 0)

        if req.min_daily_volume_24h is not None and daily_vol < req.min_daily_volume_24h:
            continue
        if req.max_daily_volume_24h is not None and daily_vol > req.max_daily_volume_24h:
            continue

        daily_mid = m["daily_mid_price"]
        if req.min_avg_price is not None and (daily_mid is None or daily_mid < req.min_avg_price):
            continue
        if req.max_avg_price is not None and (daily_mid is None or daily_mid > req.max_avg_price):
            continue

        prelim.append(
            SpreadsScanResult(
                item_id=item_id,
                name=name,
                buy_limit=buy_limit,
                daily_volume_24h=daily_vol,
                daily_mid_price=daily_mid if isinstance(daily_mid, float) else None,
                spread_abs_median=m["spread_abs_median"] if isinstance(m["spread_abs_median"], float) else None,
                spread_pct_median=m["spread_pct_median"] if isinstance(m["spread_pct_median"], float) else None,
                stability_cv_1d=m["stability_cv_1d"] if isinstance(m["stability_cv_1d"], float) else None,
                score=0.0,  # filled after stability enrichment
            )
        )

    # Shortlist by spread_pct for long-horizon stability (per-item /timeseries 24h).
    prelim.sort(key=lambda r: (r.spread_pct_median or 0.0), reverse=True)
    shortlist = prelim[: req.stability_top_k]
    shortlist_ids = [r.item_id for r in shortlist]

    client = OsrsPricesClient()
    try:
        ts_meta = await ensure_timeseries_24h_cached(db, client, shortlist_ids)
    finally:
        await client.aclose()

    # Load cached daily timeseries for shortlisted items and compute CV on last 7/30/365 daily points.
    ts_rows = db.execute(
        select(
            ItemTimeseries24h.item_id,
            ItemTimeseries24h.bucket_ts,
            ItemTimeseries24h.avg_low,
            ItemTimeseries24h.avg_high,
        ).where(ItemTimeseries24h.item_id.in_(shortlist_ids))
    ).all()

    per_ts: dict[int, list[tuple[int, int | None, int | None]]] = defaultdict(list)
    for item_id, bucket_ts, avg_low, avg_high in ts_rows:
        per_ts[int(item_id)].append((int(bucket_ts), int(avg_low) if avg_low is not None else None, int(avg_high) if avg_high is not None else None))

    st_by_item: dict[int, dict[str, float | None]] = {}
    for item_id, series in per_ts.items():
        series.sort(key=lambda x: x[0])
        lows = np.array([np.nan if s[1] is None else float(s[1]) for s in series], dtype="float64")
        highs = np.array([np.nan if s[2] is None else float(s[2]) for s in series], dtype="float64")
        both = np.isfinite(lows) & np.isfinite(highs)
        mids = (lows[both] + highs[both]) / 2.0 if np.any(both) else np.array([], dtype="float64")
        st_by_item[item_id] = stability_from_daily_timeseries(mids)

    # Merge stability + score
    enriched: list[SpreadsScanResult] = []
    for r in prelim:
        st = st_by_item.get(r.item_id, {})
        r.stability_cv_7d = st.get("stability_cv_7d")
        r.stability_cv_30d = st.get("stability_cv_30d")
        r.stability_cv_1y = st.get("stability_cv_1y")
        r.score = score_spread(
            r.spread_pct_median,
            r.spread_abs_median,
            r.stability_cv_1d,
            r.stability_cv_7d,
            r.stability_cv_30d,
            r.stability_cv_1y,
        )
        enriched.append(r)

    # Sort + limit
    if req.sort_by == "spread_pct":
        enriched.sort(key=lambda r: (r.spread_pct_median or 0.0), reverse=True)
    elif req.sort_by == "spread_abs":
        enriched.sort(key=lambda r: (r.spread_abs_median or 0.0), reverse=True)
    elif req.sort_by == "stability_1y":
        # lower CV is better; None goes last
        enriched.sort(key=lambda r: (r.stability_cv_1y is None, r.stability_cv_1y or 999.0))
    else:
        enriched.sort(key=lambda r: r.score, reverse=True)

    return SpreadsScanResponse(
        results=enriched[: req.limit],
        meta={"ingest_5m": ingest_meta, "timeseries_24h": ts_meta, "candidates": len(per_item), "shortlist": len(shortlist)},
    )


