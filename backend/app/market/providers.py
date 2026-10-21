"""Fetching candles from the market data providers (Binance and Twelve Data)."""
import time
from datetime import datetime, timezone

import requests

from app.config import TWELVE_DATA_API_KEY
from app.market.catalog import TWELVEDATA_INTERVALS

BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]
BINANCE_PAGE_SIZE = 1000
TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"


class ProviderError(Exception):
    """A provider failed. The message is safe to show to users: it never contains an API key."""


# ---------- Binance (public data, no key) ----------

def _binance_request(symbol, interval, limit, end_time_ms):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    if end_time_ms is not None:
        params["endTime"] = end_time_ms

    failure = "unknown error"
    for host in BINANCE_HOSTS:
        try:
            response = requests.get(f"{host}/api/v3/klines", params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            failure = f"HTTP {status}" if status else type(exc).__name__
    raise ProviderError(f"Binance request failed ({failure})")


def _binance_candle(row):
    return {
        "open_time": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
        "open": float(row[1]),
        "high": float(row[2]),
        "low": float(row[3]),
        "close": float(row[4]),
        "volume": float(row[5]),
    }


def fetch_binance(provider_symbol, timeframe, count):
    """Latest `count` candles, oldest first. Binance returns at most 1000 per request, so we page backwards."""
    rows = {}
    end_time_ms = None
    while len(rows) < count:
        limit = min(BINANCE_PAGE_SIZE, count - len(rows))
        batch = _binance_request(provider_symbol, timeframe, limit, end_time_ms)
        for row in batch:
            rows[row[0]] = row  # keyed by open time, so overlapping pages can never create duplicates
        if len(batch) < limit:
            break  # the exchange has no older candles
        end_time_ms = min(row[0] for row in batch) - 1
        time.sleep(0.2)  # be polite to the API
    return [_binance_candle(rows[key]) for key in sorted(rows)]


# ---------- Twelve Data (free API key) ----------

def _utc(value):
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _optional_float(value):
    if value in (None, ""):
        return None
    return float(value)


def fetch_twelvedata(provider_symbol, timeframe, count):
    """Latest `count` candles (max 5000), oldest first. Costs 1 API credit."""
    if not TWELVE_DATA_API_KEY:
        raise ProviderError("TWELVE_DATA_API_KEY is not configured on the server")
    try:
        response = requests.get(
            TWELVE_DATA_URL,
            params={
                "symbol": provider_symbol,
                "interval": TWELVEDATA_INTERVALS[timeframe],
                "outputsize": count,
                "timezone": "UTC",
                "apikey": TWELVE_DATA_API_KEY,
            },
            timeout=20,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        # Never include the exception text: it can contain the URL, and the URL contains the key.
        raise ProviderError(f"Twelve Data is not reachable ({type(exc).__name__})")

    if data.get("status") == "error" or "values" not in data:
        raise ProviderError(f"Twelve Data error {data.get('code')}: {data.get('message')}")

    candles = [
        {
            "open_time": _utc(item["datetime"]),
            "open": float(item["open"]),
            "high": float(item["high"]),
            "low": float(item["low"]),
            "close": float(item["close"]),
            "volume": _optional_float(item.get("volume")),
        }
        for item in data["values"]
    ]
    candles.sort(key=lambda candle: candle["open_time"])  # the API returns newest first by default
    return candles


# ---------- one entry point ----------

def fetch_recent_candles(info, timeframe, count):
    """`info` is a SymbolInfo from catalog.py. Returns candle dicts, oldest first."""
    if info.provider == "binance":
        return fetch_binance(info.provider_symbol, timeframe, count)
    if info.provider == "twelvedata":
        return fetch_twelvedata(info.provider_symbol, timeframe, count)
    raise ProviderError(f"Unknown provider '{info.provider}'")
