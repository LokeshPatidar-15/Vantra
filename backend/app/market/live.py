"""Live (still forming) candle updates.

One upstream feed runs per (symbol, timeframe) and is shared by every viewer of that chart.
Crypto is live from Binance's WebSocket; forex and gold are delayed, polled from Twelve Data.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from app.config import FOREX_POLL_SECONDS
from app.market import providers
from app.market.candles import is_market_closed
from app.market.catalog import DERIVED_FROM, SYMBOLS, TIMEFRAME_SECONDS

logger = logging.getLogger("vantra.live")

BINANCE_STREAM_HOSTS = ["wss://stream.binance.com:9443", "wss://data-stream.binance.vision"]
RECONNECT_DELAYS = (1, 2, 5, 10, 30)  # seconds; the last delay repeats
OUTBOX_SIZE = 100  # messages a viewer may fall behind before the oldest are dropped


# ---------- messages ----------

def status_message(key, mode, detail):
    """mode: live | delayed | closed_market | unavailable"""
    symbol, timeframe = key
    return {"type": "status", "symbol": symbol, "timeframe": timeframe, "mode": mode, "detail": detail}


def candle_message(key, candle):
    """Our candle dict (open_time is a datetime) -> the JSON message sent to browsers."""
    symbol, timeframe = key
    length = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    return {
        "type": "candle",
        "symbol": symbol,
        "timeframe": timeframe,
        "time": int(candle["open_time"].timestamp()),  # UNIX seconds, the candle's OPEN time
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": candle["volume"],
        "closed": candle["open_time"] + length <= datetime.now(timezone.utc),
    }


def binance_candle(key, payload):
    """One Binance kline message -> our candle message (None if it is not a kline)."""
    kline = payload.get("k") if isinstance(payload, dict) else None
    if not kline or payload.get("e") != "kline":
        return None
    symbol, timeframe = key
    return {
        "type": "candle",
        "symbol": symbol,
        "timeframe": timeframe,
        "time": int(kline["t"]) // 1000,  # Binance sends milliseconds
        "open": float(kline["o"]),
        "high": float(kline["h"]),
        "low": float(kline["l"]),
        "close": float(kline["c"]),
        "volume": float(kline["v"]),
        "closed": bool(kline["x"]),
    }


# ---------- the hub ----------

class LiveHub:
    """Keeps one feed per (symbol, timeframe) and fans its messages out to every subscriber's outbox."""

    def __init__(self, run_feed):
        self._run_feed = run_feed
        self._outboxes = {}  # key -> set of asyncio.Queue
        self._tasks = {}  # key -> the running feed task
        self._latest = {}  # key -> last candle message (replayed to new subscribers)
        self._status = {}  # key -> last status message

    def subscribe(self, key, outbox):
        self._outboxes.setdefault(key, set()).add(outbox)
        for message in (self._status.get(key), self._latest.get(key)):
            if message:
                self._put(outbox, message)
        task = self._tasks.get(key)
        if task is None or task.done():
            self._tasks[key] = asyncio.create_task(self._run(key))

    def unsubscribe(self, key, outbox):
        outboxes = self._outboxes.get(key)
        if not outboxes:
            return
        outboxes.discard(outbox)
        if not outboxes:  # the last viewer left: stop the feed and forget its data
            del self._outboxes[key]
            task = self._tasks.pop(key, None)
            if task:
                task.cancel()
            self._latest.pop(key, None)
            self._status.pop(key, None)

    def publish(self, key, message):
        if message["type"] == "candle":
            self._latest[key] = message
        elif message["type"] == "status":
            self._status[key] = message
        for outbox in list(self._outboxes.get(key, ())):
            self._put(outbox, message)

    @staticmethod
    def _put(outbox, message):
        if outbox.full():
            try:
                outbox.get_nowait()  # a slow viewer loses its oldest message; it must never block the feed
            except asyncio.QueueEmpty:
                pass
        outbox.put_nowait(message)

    async def _run(self, key):
        try:
            await self._run_feed(self, key)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("live feed for %s crashed", key)
            self.publish(key, status_message(key, "unavailable", "The live feed stopped unexpectedly."))


# ---------- feeds ----------

async def run_binance_feed(hub, key, info):
    """Binance kline stream: pushes the forming candle every ~2 seconds. No API key needed."""
    import websockets  # imported here so the rest of the app still starts if it is missing

    symbol, timeframe = key
    stream = f"{info.provider_symbol.lower()}@kline_{timeframe}"
    attempt = 0
    host_index = 0
    while True:
        host = BINANCE_STREAM_HOSTS[host_index % len(BINANCE_STREAM_HOSTS)]
        try:
            async with websockets.connect(f"{host}/ws/{stream}", open_timeout=10) as upstream:
                attempt = 0
                hub.publish(key, status_message(key, "live", "Live from Binance"))
                async for raw in upstream:
                    candle = binance_candle(key, json.loads(raw))
                    if candle:
                        hub.publish(key, candle)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Binance stream %s failed (%s); reconnecting", stream, type(exc).__name__)
            hub.publish(key, status_message(key, "unavailable", "Reconnecting to Binance..."))
            host_index += 1  # next time try the other Binance host
        await asyncio.sleep(RECONNECT_DELAYS[min(attempt, len(RECONNECT_DELAYS) - 1)])
        attempt += 1  # (a stream that ends normally after its 24 hours reconnects the same way)


async def run_polling_feed(hub, key, info):
    """Forex and gold: ask Twelve Data for the newest candle every FOREX_POLL_SECONDS (1 credit each)."""
    symbol, timeframe = key

    if timeframe in DERIVED_FROM:  # 4h and 1d are built from 1h, so there is nothing to poll
        hub.publish(
            key,
            status_message(
                key, "unavailable", f"Live updates are not available for {timeframe} on {symbol} yet. Reload for the newest closed candles."
            ),
        )
        await asyncio.Event().wait()  # idle until the last viewer leaves and the task is cancelled
        return

    while True:
        if is_market_closed(datetime.now(timezone.utc)):
            hub.publish(key, status_message(key, "closed_market", "The market is closed for the weekend."))
        else:
            try:
                candles = await asyncio.to_thread(providers.fetch_twelvedata, info.provider_symbol, timeframe, 1)
            except providers.ProviderError as exc:
                hub.publish(key, status_message(key, "unavailable", str(exc)))
            else:
                if candles:
                    hub.publish(key, status_message(key, "delayed", f"Delayed: refreshed every {FOREX_POLL_SECONDS} seconds"))
                    hub.publish(key, candle_message(key, candles[-1]))
        await asyncio.sleep(FOREX_POLL_SECONDS)


async def run_feed(hub, key):
    info = SYMBOLS[key[0]]
    if info.provider == "binance":
        await run_binance_feed(hub, key, info)
    else:
        await run_polling_feed(hub, key, info)


hub = LiveHub(run_feed)  # the one hub of the running app
