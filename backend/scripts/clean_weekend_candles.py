"""Delete made-up weekend candles for forex and gold that were stored before the
market-hours filter existed. Uses the same rule as the ingestion code.

Dry run (the default, deletes nothing):
    python -m scripts.clean_weekend_candles

Delete for real:
    python -m scripts.clean_weekend_candles --apply
"""
import sys
from collections import Counter

from sqlalchemy import delete, select, tuple_

from app.database import SessionLocal
from app.market.candles import is_market_closed, weekend_filter_applies
from app.market.catalog import SYMBOLS
from app.models import Candle

CHUNK = 500


def main():
    apply = "--apply" in sys.argv[1:]
    forex_symbols = [info.symbol for info in SYMBOLS.values() if not info.is_24_7]

    with SessionLocal() as db:
        rows = db.execute(
            select(Candle.symbol, Candle.timeframe, Candle.open_time).where(Candle.symbol.in_(forex_symbols))
        ).all()
        doomed = [
            (symbol, timeframe, open_time)
            for symbol, timeframe, open_time in rows
            if weekend_filter_applies(timeframe) and is_market_closed(open_time)
        ]

        print(f"Forex/gold candles stored: {len(rows)}")
        print(f"Weekend candles found    : {len(doomed)}")
        for (symbol, timeframe), count in sorted(Counter((s, tf) for s, tf, _ in doomed).items()):
            print(f"  {symbol} {timeframe}: {count}")

        if not apply:
            print("\nDry run: nothing was deleted. Run again with --apply to delete them.")
            return

        for start in range(0, len(doomed), CHUNK):
            chunk = doomed[start : start + CHUNK]
            db.execute(
                delete(Candle)
                .where(tuple_(Candle.symbol, Candle.timeframe, Candle.open_time).in_(chunk))
                .execution_options(synchronize_session=False)
            )
        db.commit()
        print(f"\nDeleted {len(doomed)} candles.")


if __name__ == "__main__":
    main()
