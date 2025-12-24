from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Bucket5m, ItemBucket5m, ItemMapping
from app.osrs.client import OsrsPricesClient


def now_ts() -> int:
    return int(time.time())


def floor_to_5m(ts: int) -> int:
    return ts - (ts % 300)


async def ensure_mapping_cached(db: Session, client: OsrsPricesClient, *, max_age_seconds: int = 24 * 3600) -> None:
    latest = db.execute(select(ItemMapping.mapping_fetched_at).order_by(ItemMapping.mapping_fetched_at.desc()).limit(1)).scalar_one_or_none()
    if latest is not None and (now_ts() - int(latest)) < max_age_seconds:
        return

    mapping = await client.get_mapping()
    fetched_at = now_ts()

    # Upsert rows
    for row in mapping:
        item_id = row.get("id")
        name = row.get("name")
        if not isinstance(item_id, int) or not isinstance(name, str):
            continue
        stmt = insert(ItemMapping).values(
            item_id=item_id,
            name=name,
            limit=row.get("limit"),
            members=row.get("members"),
            value=row.get("value"),
            lowalch=row.get("lowalch"),
            highalch=row.get("highalch"),
            icon=row.get("icon"),
            examine=row.get("examine"),
            mapping_fetched_at=fetched_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ItemMapping.item_id],
            set_={
                "name": stmt.excluded.name,
                "limit": stmt.excluded.limit,
                "members": stmt.excluded.members,
                "value": stmt.excluded.value,
                "lowalch": stmt.excluded.lowalch,
                "highalch": stmt.excluded.highalch,
                "icon": stmt.excluded.icon,
                "examine": stmt.excluded.examine,
                "mapping_fetched_at": stmt.excluded.mapping_fetched_at,
            },
        )
        db.execute(stmt)

    db.commit()


def missing_bucket_ts(db: Session, bucket_ts_list: list[int]) -> list[int]:
    if not bucket_ts_list:
        return []
    existing = set(
        db.execute(select(Bucket5m.bucket_ts).where(Bucket5m.bucket_ts.in_(bucket_ts_list))).scalars().all()
    )
    return [ts for ts in bucket_ts_list if ts not in existing]


async def ingest_5m_bucket(db: Session, client: OsrsPricesClient, bucket_ts: int) -> None:
    payload = await client.get_5m_bucket(bucket_ts)
    data = payload.get("data")
    if not isinstance(data, dict):
        return

    ingested_at = now_ts()

    db.execute(
        insert(Bucket5m)
        .values(bucket_ts=bucket_ts, ingested_at=ingested_at)
        .on_conflict_do_nothing(index_elements=[Bucket5m.bucket_ts])
    )

    # Insert per-item bucket rows. Keys are item IDs as strings in practice.
    rows: list[dict[str, Any]] = []
    for k, v in data.items():
        try:
            item_id = int(k)
        except Exception:
            continue
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "bucket_ts": bucket_ts,
                "item_id": item_id,
                "avg_high": v.get("avgHighPrice"),
                "high_vol": int(v.get("highPriceVolume") or 0),
                "avg_low": v.get("avgLowPrice"),
                "low_vol": int(v.get("lowPriceVolume") or 0),
            }
        )

    if rows:
        stmt = insert(ItemBucket5m).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ItemBucket5m.bucket_ts, ItemBucket5m.item_id],
            set_={
                "avg_high": stmt.excluded.avg_high,
                "high_vol": stmt.excluded.high_vol,
                "avg_low": stmt.excluded.avg_low,
                "low_vol": stmt.excluded.low_vol,
            },
        )
        db.execute(stmt)

    db.commit()


async def ensure_buckets_cached(db: Session, client: OsrsPricesClient, bucket_ts_list: list[int]) -> dict[str, Any]:
    missing = missing_bucket_ts(db, bucket_ts_list)
    for ts in sorted(missing):
        await ingest_5m_bucket(db, client, ts)
    return {"requested": len(bucket_ts_list), "missing": len(missing)}


