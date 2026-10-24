"""Fetch candles from the market data provider and store them in the database.

Run from the backend/ folder:
    python -m scripts.ingest_candles BTCUSDT 1h 2000
    python -m scripts.ingest_candles XAUUSD 1h 1000

Arguments: SYMBOL TIMEFRAME COUNT   (COUNT from 1 to 5000)
4h and 1d are not ingested: they are built from 1h candles.
"""
import sys

from app.database import SessionLocal
from app.market.catalog import SYMBOLS, TIMEFRAME_SECONDS
from app.market.providers import ProviderError
from app.market.service import DerivedTimeframeError, ingest_candles


def main():
    args = sys.argv[1:]
    if (
        len(args) != 3
        or args[0].upper() not in SYMBOLS
        or args[1].lower() not in TIMEFRAME_SECONDS
        or not args[2].isdigit()
        or not 1 <= int(args[2]) <= 5000
    ):
        print(__doc__)
        print(f"Symbols: {', '.join(SYMBOLS)}")
        print(f"Timeframes: {', '.join(TIMEFRAME_SECONDS)}")
        raise SystemExit(1)

    symbol, timeframe, count = args[0].upper(), args[1].lower(), int(args[2])
    with SessionLocal() as db:
        try:
            result = ingest_candles(db, symbol, timeframe, count)
        except (ProviderError, DerivedTimeframeError) as exc:
            raise SystemExit(f"Error: {exc}")

    for key, value in result.items():
        print(f"{key:16}: {value}")


if __name__ == "__main__":
    main()
