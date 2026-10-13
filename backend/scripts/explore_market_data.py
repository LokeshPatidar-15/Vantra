"""Explore OHLCV candles from Binance (no key needed) and Twelve Data (free key).

Run from the backend/ folder:
    python -m scripts.explore_market_data binance BTCUSDT 1h
    python -m scripts.explore_market_data twelvedata XAU/USD 1h

Supported intervals: 1m 5m 15m 30m 1h 4h 1d
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

BINANCE_HOSTS = ["https://api.binance.com", "https://data-api.binance.vision"]
TWELVE_DATA_URL = "https://api.twelvedata.com/time_series"

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}
TWELVE_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
PRICE_COLUMNS = ["open", "high", "low", "close"]


def fetch_binance(symbol, interval, limit=500):
    """Public klines endpoint: no account and no API key. Max 1000 candles per request."""
    rows = None
    last_error = None
    for host in BINANCE_HOSTS:
        try:
            response = requests.get(
                f"{host}/api/v3/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=15,
            )
            response.raise_for_status()
            rows = response.json()
            break
        except requests.RequestException as exc:
            last_error = exc
            print(f"[binance] {host} failed: {exc}")
    if rows is None:
        raise SystemExit(f"All Binance hosts failed. Last error: {last_error}")

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
        ],
    )
    df["time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)  # candle OPEN time, UTC
    for column in PRICE_COLUMNS + ["volume"]:
        df[column] = df[column].astype(float)  # Binance sends numbers as strings
    return df[["time"] + PRICE_COLUMNS + ["volume"]]


def fetch_twelve_data(symbol, interval, outputsize=500):
    """Needs TWELVE_DATA_API_KEY in backend/.env. Costs 1 API credit per call."""
    if not TWELVE_DATA_API_KEY:
        raise SystemExit("TWELVE_DATA_API_KEY is empty. Add it to backend/.env first.")
    try:
        response = requests.get(
            TWELVE_DATA_URL,
            params={
                "symbol": symbol,
                "interval": TWELVE_INTERVALS[interval],
                "outputsize": outputsize,
                "timezone": "UTC",
                "order": "asc",
                "apikey": TWELVE_DATA_API_KEY,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        # Do not print the exception text: it can contain the URL, and the URL contains the key.
        raise SystemExit(f"Could not reach Twelve Data ({type(exc).__name__}). Check your internet connection.")

    print(
        f"[twelvedata] HTTP {response.status_code}, "
        f"credits used: {response.headers.get('api-credits-used')}, "
        f"credits left: {response.headers.get('api-credits-left')}"
    )
    data = response.json()
    if data.get("status") == "error" or "values" not in data:
        raise SystemExit(f"Twelve Data error {data.get('code')}: {data.get('message')}")

    df = pd.DataFrame(data["values"])
    df["time"] = pd.to_datetime(df["datetime"], utc=True)
    for column in PRICE_COLUMNS:
        df[column] = df[column].astype(float)
    if "volume" in df:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = float("nan")
    return df[["time"] + PRICE_COLUMNS + ["volume"]]


def check_candles(df, interval):
    """Return (problems, gaps) for candles that should be sorted oldest to newest."""
    problems = []

    if df[PRICE_COLUMNS].isna().any().any():
        problems.append("NaN values in prices")
    if (df[PRICE_COLUMNS] <= 0).any().any():
        problems.append("zero or negative prices")
    if not df["time"].is_monotonic_increasing:
        problems.append("timestamps are not sorted oldest to newest")
    if df["time"].duplicated().any():
        problems.append("duplicate timestamps")

    bad_high = df["high"] < df[["open", "close"]].max(axis=1)
    if bad_high.any():
        problems.append(f"{int(bad_high.sum())} candles where high is below open/close")
    bad_low = df["low"] > df[["open", "close"]].min(axis=1)
    if bad_low.any():
        problems.append(f"{int(bad_low.sum())} candles where low is above open/close")

    step = pd.Timedelta(seconds=INTERVAL_SECONDS[interval])
    deltas = df["time"].diff()
    gaps = deltas[deltas > step]
    return problems, gaps


def report(df, interval, source, symbol):
    df = df.reset_index(drop=True)
    seconds = INTERVAL_SECONDS[interval]
    now = datetime.now(timezone.utc)

    print(f"\n=== {source} {symbol} {interval}: {len(df)} candles ===")
    print(f"First candle opens : {df['time'].iloc[0]}")
    print(f"Last candle opens  : {df['time'].iloc[-1]}")
    print(f"Time now (UTC)     : {now:%Y-%m-%d %H:%M:%S}")

    print("\nFirst 3 candles:")
    print(df.head(3).to_string(index=False))
    print("\nLast 3 candles:")
    print(df.tail(3).to_string(index=False))

    last_close = df["time"].iloc[-1] + pd.Timedelta(seconds=seconds)
    if last_close > now:
        print(f"\nLast candle is STILL FORMING (closes at {last_close:%Y-%m-%d %H:%M:%S} UTC). A backtest must not use it.")
    else:
        print("\nLast candle is already closed.")

    problems, gaps = check_candles(df, interval)
    print("\nSanity checks:")
    if problems:
        for problem in problems:
            print(f"  PROBLEM: {problem}")
    else:
        print("  OK: no NaN, sorted, no duplicates, high/low consistent with open/close")

    print(f"\nGaps larger than one {interval} candle: {len(gaps)}")
    for position in list(gaps.index)[:5]:
        before = df["time"].iloc[position - 1]
        after = df["time"].iloc[position]
        print(f"  {before} -> {after}  (jump of {after - before})")

    zero_volume = int((df["volume"].fillna(0) == 0).sum())
    print(f"\nCandles with zero or missing volume: {zero_volume} of {len(df)}")
    median_range = ((df["high"] - df["low"]) / df["close"] * 100).median()
    print(f"Median candle range (high - low): {median_range:.3f}% of price")


def main():
    args = sys.argv[1:]
    if len(args) != 3 or args[0] not in ("binance", "twelvedata") or args[2] not in INTERVAL_SECONDS:
        print(__doc__)
        raise SystemExit(1)
    source, symbol, interval = args
    df = fetch_binance(symbol, interval) if source == "binance" else fetch_twelve_data(symbol, interval)
    report(df, interval, source, symbol)


if __name__ == "__main__":
    main()
