from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter
from fastapi import Depends
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ItemBucket5m, ItemMapping
from app.osrs.client import OsrsPricesClient
from app.osrs.ingest import ensure_buckets_cached, ensure_mapping_cached, floor_to_5m
from app.scan.compute import scan_item_series
from app.scan.schemas import ScanRequest, ScanResponse

router = APIRouter()


@router.post("/scan", response_model=ScanResponse)
async def scan(req: ScanRequest, db: Session = Depends(get_db)) -> ScanResponse:
    # Compute needed bucket timestamps for the scan window (aligned to 5m).
    now = floor_to_5m(int(time.time()))
    # We need baseline window plus event+still-low windows plus a small buffer.
    blocks = req.baseline_hours * 12 + req.event_window_blocks + req.still_low_blocks + 4
    bucket_ts_list = [now - 300 * i for i in range(blocks)]

    client = OsrsPricesClient()
    try:
        await ensure_mapping_cached(db, client)
        ingest_meta = await ensure_buckets_cached(db, client, bucket_ts_list)
    finally:
        await client.aclose()

    # Load mapping and time window data from DB
    mapping_rows = db.execute(select(ItemMapping.item_id, ItemMapping.name, ItemMapping.limit)).all()
    id_to_meta = {int(r[0]): (str(r[1]), (int(r[2]) if r[2] is not None else None)) for r in mapping_rows}

    rows = db.execute(
        select(
            ItemBucket5m.item_id,
            ItemBucket5m.bucket_ts,
            ItemBucket5m.avg_low,
            ItemBucket5m.low_vol,
        ).where(ItemBucket5m.bucket_ts.in_(bucket_ts_list))
    ).all()

    per_item: dict[int, list[tuple[int, int | None, int]]] = defaultdict(list)
    for item_id, bucket_ts, avg_low, low_vol in rows:
        per_item[int(item_id)].append((int(bucket_ts), int(avg_low) if avg_low is not None else None, int(low_vol)))

    results = []
    for item_id, series in per_item.items():
        name, buy_limit = id_to_meta.get(item_id, (f"item_{item_id}", None))

        if req.min_buy_limit is not None:
            if buy_limit is None or buy_limit < req.min_buy_limit:
                continue
        if req.max_buy_limit is not None:
            if buy_limit is None or buy_limit > req.max_buy_limit:
                continue

        series.sort(key=lambda x: x[0])  # ascending time

        bucket_ts_arr = np.array([s[0] for s in series], dtype="int64")
        avg_low_arr = np.array([np.nan if s[1] is None else float(s[1]) for s in series], dtype="float64")
        low_vol_arr = np.array([float(s[2]) for s in series], dtype="float64")

        r = scan_item_series(
            item_id=item_id,
            name=name,
            bucket_ts=bucket_ts_arr,
            avg_low=avg_low_arr,
            low_vol=low_vol_arr,
            req=req,
        )
        if r is not None:
            if req.min_price is not None and r.baseline_price < req.min_price:
                continue
            if req.max_price is not None and r.baseline_price > req.max_price:
                continue
            results.append(r)

    # Sort and trim
    if req.sort_by == "most_recent":
        results.sort(key=lambda r: r.dump_bucket_ts, reverse=True)
    elif req.sort_by == "biggest_volume":
        results.sort(key=lambda r: r.event_volume, reverse=True)
    else:
        results.sort(key=lambda r: r.price_drop_pct)  # more negative first

    results = results[: req.limit]

    return ScanResponse(results=results, meta={"ingest": ingest_meta, "candidates": len(per_item)})


