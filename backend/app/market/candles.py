"""Pure candle rules (no network, no database), so they are easy to test."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.market.catalog import TIMEFRAME_SECONDS

NEW_YORK = ZoneInfo("America/New_York")


def is_valid_candle(candle):
    """A candle is valid if prices are positive and high/low really contain open and close."""
    prices = (candle["open"], candle["high"], candle["low"], candle["close"])
    return (
        all(price > 0 for price in prices)
        and candle["high"] >= max(candle["open"], candle["close"])
        and candle["low"] <= min(candle["open"], candle["close"])
    )


def weekend_filter_applies(timeframe):
    """The weekend rule is only used for candles up to 1 hour long.

    A longer candle (4h, 1d) can straddle the weekly open or close, so its open time
    alone cannot tell us if it is real. Those timeframes will be built from clean
    1h candles when we write the resampling code.
    """
    return TIMEFRAME_SECONDS[timeframe] <= 3600


def is_market_closed(open_time):
    """True if a forex/gold candle that opens at `open_time` falls in the weekend closure.

    The closure runs from Friday 18:00 to Sunday 18:00 New York time (daylight saving
    is handled automatically). Data providers fill this period with flat, made-up
    candles even though nobody is trading.
    """
    local = open_time.astimezone(NEW_YORK)
    weekday, hour = local.weekday(), local.hour  # Monday = 0 ... Sunday = 6
    return (
        weekday == 5  # Saturday
        or (weekday == 4 and hour >= 18)  # Friday from 18:00
        or (weekday == 6 and hour < 18)  # Sunday before 18:00
    )


def split_candles(candles, timeframe, now=None, weekend_closure=False):
    """Return (usable, forming, invalid, market_closed).

    Only closed, valid candles that belong to real trading hours are usable.
    Set weekend_closure=True for forex and gold (not for crypto).
    """
    now = now or datetime.now(timezone.utc)
    length = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    check_weekend = weekend_closure and weekend_filter_applies(timeframe)

    usable, forming, invalid, market_closed = [], 0, 0, 0
    for candle in candles:
        if candle["open_time"] + length > now:
            forming += 1  # still open: its close price is not final yet
        elif check_weekend and is_market_closed(candle["open_time"]):
            market_closed += 1
        elif not is_valid_candle(candle):
            invalid += 1
        else:
            usable.append(candle)
    return usable, forming, invalid, market_closed
