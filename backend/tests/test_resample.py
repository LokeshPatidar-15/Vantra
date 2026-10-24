from datetime import datetime, timedelta, timezone

from app.market.resample import resample_candles

HOUR, FOUR_HOURS, DAY = 3600, 14400, 86400
NEW_YORK = "America/New_York"


def utc(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


def hourly(start, count, volume=1.0):
    return [
        {
            "open_time": start + timedelta(hours=i),
            "open": 100.0 + i,
            "high": 110.0 + i,
            "low": 90.0 + i,
            "close": 105.0 + i,
            "volume": volume,
        }
        for i in range(count)
    ]


def test_four_hour_candles_merge_open_high_low_close_and_volume():
    candles = hourly(utc("2026-10-12 00:00"), 8)

    result = resample_candles(candles, HOUR, FOUR_HOURS)

    assert len(result) == 2
    first = result[0]
    assert first["open_time"] == utc("2026-10-12 00:00")
    assert first["open"] == candles[0]["open"]
    assert first["close"] == candles[3]["close"]
    assert first["high"] == max(c["high"] for c in candles[:4])
    assert first["low"] == min(c["low"] for c in candles[:4])
    assert first["volume"] == 4.0


def test_a_first_candle_that_starts_in_the_middle_is_dropped():
    candles = hourly(utc("2026-10-12 02:00"), 6)  # 02:00 to 07:00, so the 00:00 to 04:00 candle is partial

    result = resample_candles(candles, HOUR, FOUR_HOURS)

    assert [c["open_time"] for c in result] == [utc("2026-10-12 04:00")]


def test_a_last_candle_that_is_not_finished_is_dropped():
    candles = hourly(utc("2026-10-12 00:00"), 6)  # 00:00 to 05:00, so the 04:00 to 08:00 candle is unfinished

    result = resample_candles(candles, HOUR, FOUR_HOURS)

    assert [c["open_time"] for c in result] == [utc("2026-10-12 00:00")]


def test_volume_is_none_when_no_small_candle_has_volume():
    candles = hourly(utc("2026-10-12 00:00"), 4, volume=None)

    result = resample_candles(candles, HOUR, FOUR_HOURS)

    assert len(result) == 1 and result[0]["volume"] is None


def test_forex_daily_candle_starts_at_18_00_new_york_in_summer():
    candles = hourly(utc("2026-10-18 22:00"), 24)  # Sunday 18:00 New York (UTC-4)

    result = resample_candles(candles, HOUR, DAY, NEW_YORK, 18)

    assert [c["open_time"] for c in result] == [utc("2026-10-18 22:00")]


def test_forex_daily_candle_starts_at_18_00_new_york_in_winter():
    candles = hourly(utc("2026-12-06 23:00"), 24)  # Sunday 18:00 New York (UTC-5)

    result = resample_candles(candles, HOUR, DAY, NEW_YORK, 18)

    assert [c["open_time"] for c in result] == [utc("2026-12-06 23:00")]


def test_forex_four_hour_candles_follow_the_new_york_day():
    candles = hourly(utc("2026-10-18 22:00"), 12)

    result = resample_candles(candles, HOUR, FOUR_HOURS, NEW_YORK, 18)

    assert [c["open_time"] for c in result] == [
        utc("2026-10-18 22:00"),
        utc("2026-10-19 02:00"),
        utc("2026-10-19 06:00"),
    ]


def test_a_forex_trading_week_gives_five_daily_candles_and_none_for_the_weekend():
    candles = hourly(utc("2026-10-18 22:00"), 120)  # Sunday 18:00 New York until Friday 18:00 New York

    result = resample_candles(candles, HOUR, DAY, NEW_YORK, 18)

    assert len(result) == 5
    assert all(c["open_time"].hour == 22 for c in result)


def test_empty_input_gives_empty_output():
    assert resample_candles([], HOUR, DAY) == []
