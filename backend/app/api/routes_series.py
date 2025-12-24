from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ItemBucket5m
from app.osrs.client import OsrsPricesClient
from app.osrs.ingest import ensure_buckets_cached, floor_to_5m

router = APIRouter()


class ItemSeriesResponse(BaseModel):
    item_id: int
    timestep_seconds: int = 300
    start_ts: int
    end_ts: int
    timestamps: list[int]
    avg_low: list[int | None]


@router.get("/items/{item_id}/series", response_model=ItemSeriesResponse)
async def item_series(
    item_id: int,
    hours: int = Query(24, ge=1, le=48),
    db: Session = Depends(get_db),
) -> ItemSeriesResponse:
    """
    Return a fixed-step 5m series for the last `hours` hours ending at 'now', aligned to 5m boundaries.
    """
    end_ts = floor_to_5m(int(time.time()))
    start_ts = end_ts - hours * 3600
    start_ts = floor_to_5m(start_ts)

    bucket_ts_list = list(range(start_ts, end_ts + 1, 300))

    # Ensure buckets are present (optional but makes charts work even if scan wasn't run yet).
    client = OsrsPricesClient()
    try:
        await ensure_buckets_cached(db, client, bucket_ts_list)
    finally:
        await client.aclose()

    rows = db.execute(
        select(ItemBucket5m.bucket_ts, ItemBucket5m.avg_low)
        .where(ItemBucket5m.item_id == item_id)
        .where(ItemBucket5m.bucket_ts.in_(bucket_ts_list))
    ).all()
    by_ts = {int(ts): (int(avg) if avg is not None else None) for ts, avg in rows}

    timestamps = bucket_ts_list
    avg_low = [by_ts.get(ts) for ts in bucket_ts_list]

    return ItemSeriesResponse(
        item_id=item_id,
        start_ts=start_ts,
        end_ts=end_ts,
        timestamps=timestamps,
        avg_low=avg_low,
    )


