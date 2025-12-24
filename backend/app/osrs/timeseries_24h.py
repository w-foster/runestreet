from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import ItemTimeseries24h, ItemTimeseries24hMeta
from app.osrs.client import OsrsPricesClient


def now_ts() -> int:
    return int(time.time())


def _is_fresh(fetched_at: int | None, *, max_age_seconds: int) -> bool:
    return fetched_at is not None and (now_ts() - int(fetched_at)) < max_age_seconds


async def ensure_timeseries_24h_cached(
    db: Session,
    client: OsrsPricesClient,
    item_ids: list[int],
    *,
    max_age_seconds: int = 6 * 3600,
    max_concurrency: int = 8,
) -> dict[str, Any]:
    """
    Ensure we have reasonably fresh 24h-timeseries (daily points, up to 365) for the given items.
    This powers stability metrics for 7d/30d/1y by slicing the last N daily points.
    """
    if not item_ids:
        return {"requested": 0, "fetched": 0, "skipped_fresh": 0}

    meta_rows = db.execute(select(ItemTimeseries24hMeta.item_id, ItemTimeseries24hMeta.fetched_at).where(ItemTimeseries24hMeta.item_id.in_(item_ids))).all()
    meta = {int(i): int(ts) for i, ts in meta_rows}

    to_fetch = [i for i in item_ids if not _is_fresh(meta.get(i), max_age_seconds=max_age_seconds)]
    sem = asyncio.Semaphore(max_concurrency)
    fetched = 0

    async def _fetch_one(item_id: int) -> None:
        nonlocal fetched
        async with sem:
            payload = await client.get_timeseries(item_id, "24h")
            data = payload.get("data")
            if not isinstance(data, list):
                return
            rows = []
            for p in data:
                if not isinstance(p, dict):
                    continue
                ts = p.get("timestamp")
                if not isinstance(ts, int):
                    continue
                rows.append(
                    {
                        "item_id": item_id,
                        "bucket_ts": ts,
                        "avg_high": p.get("avgHighPrice"),
                        "high_vol": int(p.get("highPriceVolume") or 0),
                        "avg_low": p.get("avgLowPrice"),
                        "low_vol": int(p.get("lowPriceVolume") or 0),
                    }
                )
            if rows:
                stmt = insert(ItemTimeseries24h).values(rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[ItemTimeseries24h.item_id, ItemTimeseries24h.bucket_ts],
                    set_={
                        "avg_high": stmt.excluded.avg_high,
                        "high_vol": stmt.excluded.high_vol,
                        "avg_low": stmt.excluded.avg_low,
                        "low_vol": stmt.excluded.low_vol,
                    },
                )
                db.execute(stmt)
            db.execute(
                insert(ItemTimeseries24hMeta)
                .values(item_id=item_id, fetched_at=now_ts())
                .on_conflict_do_update(index_elements=[ItemTimeseries24hMeta.item_id], set_={"fetched_at": now_ts()})
            )
            db.commit()
            fetched += 1

    await asyncio.gather(*[_fetch_one(i) for i in to_fetch])

    return {"requested": len(item_ids), "fetched": fetched, "skipped_fresh": len(item_ids) - len(to_fetch)}


