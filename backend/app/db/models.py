from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ItemMapping(Base):
    __tablename__ = "item_mapping"

    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    members: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lowalch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    highalch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    examine: Mapped[str | None] = mapped_column(Text, nullable=True)
    mapping_fetched_at: Mapped[int] = mapped_column(BigInteger)


class Bucket5m(Base):
    __tablename__ = "bucket_5m"

    bucket_ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ingested_at: Mapped[int] = mapped_column(BigInteger)


class ItemBucket5m(Base):
    __tablename__ = "item_bucket_5m"

    bucket_ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    item_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    avg_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_vol: Mapped[int] = mapped_column(Integer)
    avg_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    low_vol: Mapped[int] = mapped_column(Integer)


