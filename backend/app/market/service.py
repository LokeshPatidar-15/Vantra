"""Candle storage: ingest from a provider into PostgreSQL, and read candles back for the API."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market.candles import split_candles
from app.market.catalog import DERIVED_FROM, SYMBOLS, TIMEFRAME_SECONDS
from app.market.providers import fetch_recent_candles
from app.market.resample import resample_candles
from app.models import Candle

INSERT_CHUNK = 1000  # rows per INSERT statement
CANDLES = Candle.__table__  # plain table object, used for the bulk INSERT below


class DerivedTimeframeError(ValueError):
    """Someone tried to ingest a timeframe that Vantra builds itself."""


def ingest_candles(db: Session, symbol: str, timeframe: str, count: int) -> dict:
    """Fetch the latest `count` candles, keep only real, closed, valid ones, and store them.

    Safe to run again and again: a candle that is already stored is skipped
    (ON CONFLICT DO NOTHING on the primary key), never duplicated.
    """
    if timeframe in DERIVED_FROM:
        base = DERIVED_FROM[timeframe]
        raise DerivedTimeframeError(f"{timeframe} candles are built from {base} candles. Ingest {base} instead.")

    info = SYMBOLS[symbol]
    fetched = fetch_recent_candles(info, timeframe, count)
    usable, forming, invalid, market_closed = split_candles(
        fetched, timeframe, weekend_closure=not info.is_24_7
    )

    inserted = 0
    for start in range(0, len(usable), INSERT_CHUNK):
        rows = [
            {**candle, "symbol": symbol, "timeframe": timeframe, "source": info.provider}
            for candle in usable[start : start + INSERT_CHUNK]
        ]
        # rowcount is unreliable for bulk inserts, so we ask the database to RETURN
        # the rows it really inserted (skipped duplicates are not returned) and count them.
        statement = (
            insert(CANDLES)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["symbol", "timeframe", "open_time"])
            .returning(CANDLES.c.open_time)
        )
        inserted += len(db.execute(statement).all())
    db.commit()

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source": info.provider,
        "fetched": len(fetched),
        "inserted": inserted,
        "already_present": len(usable) - inserted,
        "forming_dropped": forming,
        "market_closed_dropped": market_closed,
        "invalid_dropped": invalid,
        "first_time": int(usable[0]["open_time"].timestamp()) if usable else None,
        "last_time": int(usable[-1]["open_time"].timestamp()) if usable else None,
    }


def _load_stored(db: Session, symbol: str, timeframe: str, limit: int) -> list:
    """The latest `limit` stored candles as plain dicts, oldest first."""
    rows = db.execute(
        select(Candle.open_time, Candle.open, Candle.high, Candle.low, Candle.close, Candle.volume)
        .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
        .order_by(Candle.open_time.desc())
        .limit(limit)
    ).all()
    return [
        {
            "open_time": row.open_time,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
        }
        for row in reversed(rows)
    ]


def get_candles(db: Session, symbol: str, timeframe: str, limit: int) -> list:
    """The latest `limit` candles as plain dicts, oldest first (the order charts and backtests need).

    4h and 1d candles are not stored: they are built here from 1h candles.
    """
    base = DERIVED_FROM.get(timeframe)
    if base is None:
        return _load_stored(db, symbol, timeframe, limit)

    info = SYMBOLS[symbol]
    base_seconds, target_seconds = TIMEFRAME_SECONDS[base], TIMEFRAME_SECONDS[timeframe]
    ratio = target_seconds // base_seconds
    # a little extra, because the oldest and newest big candles may be incomplete and get dropped
    base_candles = _load_stored(db, symbol, base, limit * ratio + 2 * ratio)
    derived = resample_candles(base_candles, base_seconds, target_seconds, info.day_timezone, info.day_start_hour)
    return derived[-limit:]
