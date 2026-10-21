from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.market.candles import is_market_closed, split_candles, weekend_filter_applies
from app.market.service import ingest_candles


def utc(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def count_candles():
    with engine.connect() as conn:
        return conn.execute(text("select count(*) from candles")).scalar()


def use_fake_provider(monkeypatch, candles):
    monkeypatch.setattr(
        "app.market.service.fetch_recent_candles", lambda info, timeframe, count: list(candles)
    )


def candle_at(when):
    return {"open_time": utc(when), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": None}


# The closure runs from Friday 18:00 to Sunday 18:00 New York time.
# October 2026 is summer time (UTC-4), December 2026 is winter time (UTC-5).
@pytest.mark.parametrize(
    "utc_time, closed",
    [
        ("2026-10-16 21:00", False),  # Friday 17:00 New York
        ("2026-10-16 22:00", True),  # Friday 18:00 New York
        ("2026-10-17 12:00", True),  # Saturday
        ("2026-10-18 21:00", True),  # Sunday 17:00 New York
        ("2026-10-18 22:00", False),  # Sunday 18:00 New York: the market reopens
        ("2026-10-19 00:00", False),  # Monday
        ("2026-12-04 22:00", False),  # winter: Friday 17:00 New York
        ("2026-12-04 23:00", True),  # winter: Friday 18:00 New York
        ("2026-12-06 22:00", True),  # winter: Sunday 17:00 New York
        ("2026-12-06 23:00", False),  # winter: Sunday 18:00 New York
        ("2026-11-01 22:00", True),  # the day the clocks go back: 17:00 New York
        ("2026-11-01 23:00", False),  # the day the clocks go back: 18:00 New York
    ],
)
def test_is_market_closed_follows_new_york_time(utc_time, closed):
    assert is_market_closed(utc(utc_time)) == closed


def test_weekend_rule_only_applies_to_timeframes_up_to_one_hour():
    assert weekend_filter_applies("1m") and weekend_filter_applies("1h")
    assert not weekend_filter_applies("4h") and not weekend_filter_applies("1d")


def test_split_candles_drops_weekend_candles_only_when_asked():
    saturday, monday = candle_at("2026-10-17 12:00"), candle_at("2026-10-19 12:00")
    now = utc("2026-10-21 12:00")

    usable, _, _, market_closed = split_candles([saturday, monday], "1h", now=now, weekend_closure=True)
    assert usable == [monday] and market_closed == 1

    usable, _, _, market_closed = split_candles([saturday, monday], "1h", now=now, weekend_closure=False)
    assert len(usable) == 2 and market_closed == 0

    usable, _, _, market_closed = split_candles([saturday, monday], "1d", now=now, weekend_closure=True)
    assert len(usable) == 2 and market_closed == 0  # the rule is not used for 1d candles


WEEK = [
    "2026-10-17 00:00", "2026-10-17 01:00", "2026-10-17 02:00",  # Saturday: market closed
    "2026-10-19 10:00", "2026-10-19 11:00",  # Monday: market open
]


def test_forex_ingest_drops_weekend_candles(monkeypatch):
    use_fake_provider(monkeypatch, [candle_at(when) for when in WEEK])

    with SessionLocal() as db:
        result = ingest_candles(db, "XAUUSD", "1h", 5)

    assert result["inserted"] == 2 and result["market_closed_dropped"] == 3
    assert count_candles() == 2


def test_crypto_ingest_keeps_weekend_candles(monkeypatch):
    use_fake_provider(monkeypatch, [candle_at(when) for when in WEEK])

    with SessionLocal() as db:
        result = ingest_candles(db, "BTCUSDT", "1h", 5)

    assert result["inserted"] == 5 and result["market_closed_dropped"] == 0
    assert count_candles() == 5
