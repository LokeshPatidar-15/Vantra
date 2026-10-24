"""Building bigger candles (4h, 1d) from smaller ones (1h). Pure code: no network, no database."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo


def _to_utc(wall_clock, tz):
    """A naive 'wall clock' time in the market's timezone -> a UTC time."""
    return wall_clock.replace(tzinfo=tz).astimezone(timezone.utc)


def bucket_bounds(open_time, target_seconds, tz, day_start_hour):
    """Start and end (UTC) of the bigger candle that a small candle opening at `open_time` belongs to.

    The market's trading day starts at `day_start_hour` in its own timezone, and the bigger
    candles tile that day exactly. We count in wall-clock time, so daylight saving never
    shifts a candle away from its 18:00 (or 00:00) start.
    """
    local = open_time.astimezone(tz).replace(tzinfo=None)  # wall-clock time in the market's timezone
    day_start = (local - timedelta(hours=day_start_hour)).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(hours=day_start_hour)
    slot = int((local - day_start).total_seconds() // target_seconds)
    start = day_start + timedelta(seconds=slot * target_seconds)
    end = start + timedelta(seconds=target_seconds)
    return _to_utc(start, tz), _to_utc(end, tz)


def resample_candles(candles, base_seconds, target_seconds, day_timezone="UTC", day_start_hour=0):
    """Merge small candles (oldest first) into bigger ones.

    open = first open, high = highest high, low = lowest low, close = last close,
    volume = sum of volumes (None when no small candle has a volume).

    A bigger candle is only returned when we hold ALL of it: the first one is dropped if
    our data starts in the middle of it, and the last one is dropped if it is still
    forming (or our data has not reached its end yet).
    """
    if not candles:
        return []

    tz = ZoneInfo(day_timezone)
    first_open = candles[0]["open_time"]
    last_close = candles[-1]["open_time"] + timedelta(seconds=base_seconds)

    buckets = {}  # bucket start -> (bucket end, small candles inside it)
    for candle in candles:
        start, end = bucket_bounds(candle["open_time"], target_seconds, tz, day_start_hour)
        buckets.setdefault(start, (end, []))[1].append(candle)

    result = []
    for start in sorted(buckets):
        end, members = buckets[start]
        if start < first_open or end > last_close:
            continue
        volumes = [member["volume"] for member in members if member["volume"] is not None]
        result.append(
            {
                "open_time": start,
                "open": members[0]["open"],
                "high": max(member["high"] for member in members),
                "low": min(member["low"] for member in members),
                "close": members[-1]["close"],
                "volume": sum(volumes) if volumes else None,
            }
        )
    return result
