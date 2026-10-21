"""Candle storage: ingest from a provider into PostgreSQL, and read candles back for the API."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market.candles import split_candles
from app.market.catalog import SYMBOLS
from app.market.providers import fetch_recent_candles
from app.models import Candle

INSERT_CHUNK = 1000  # rows per INSERT statement
CANDLES = Candle.__table__  # plain table object, used for the bulk INSERT below


def ingest_candles(db: Session, symbol: str, timeframe: str, count: int) -> dict:
    """Fetch the latest `count` candles, keep only real, closed, valid ones, and store them.

    Safe to run again and again: a candle that is already stored is skipped
    (ON CONFLICT DO NOTHING on the primary key), never duplicated.
    """
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


def get_candles(db: Session, symbol: str, timeframe: str, limit: int) -> list:
    """The latest `limit` stored candles, oldest first (the order charts and backtests need)."""
    rows = db.scalars(
        select(Candle)
        .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
        .order_by(Candle.open_time.desc())
        .limit(limit)
    ).all()
    rows.reverse()
    return rows
