import asyncio
from datetime import datetime, timezone

from app.market import live

KEY = ("BTCUSDT", "1m")

KLINE = {
    "e": "kline",
    "E": 1700000000000,
    "s": "BTCUSDT",
    "k": {"t": 1700000040000, "T": 1700000099999, "i": "1m", "o": "100.5", "c": "101.5", "h": "102.0", "l": "99.5", "v": "12.25", "x": False},
}


def test_binance_candle_converts_a_kline_message():
    candle = live.binance_candle(KEY, KLINE)

    assert candle == {
        "type": "candle", "symbol": "BTCUSDT", "timeframe": "1m", "time": 1700000040,
        "open": 100.5, "high": 102.0, "low": 99.5, "close": 101.5, "volume": 12.25, "closed": False,
    }


def test_binance_candle_ignores_other_messages():
    assert live.binance_candle(KEY, {"e": "trade"}) is None
    assert live.binance_candle(KEY, {"result": None, "id": 1}) is None
    assert live.binance_candle(KEY, ["not", "a", "dict"]) is None


def test_hub_sends_every_message_to_every_subscriber():
    async def scenario():
        async def idle_feed(hub, key):
            await asyncio.Event().wait()

        hub = live.LiveHub(idle_feed)
        first, second = asyncio.Queue(), asyncio.Queue()
        hub.subscribe(KEY, first)
        hub.subscribe(KEY, second)

        message = {"type": "candle", "close": 1.0}
        hub.publish(KEY, message)

        assert first.get_nowait() == message and second.get_nowait() == message
        hub.unsubscribe(KEY, first)
        hub.unsubscribe(KEY, second)

    asyncio.run(scenario())


def test_hub_replays_status_and_latest_candle_to_a_new_subscriber():
    async def scenario():
        async def idle_feed(hub, key):
            await asyncio.Event().wait()

        hub = live.LiveHub(idle_feed)
        early = asyncio.Queue()
        hub.subscribe(KEY, early)
        status = live.status_message(KEY, "live", "Live from Binance")
        candle = {"type": "candle", "close": 5.0}
        hub.publish(KEY, status)
        hub.publish(KEY, candle)

        late = asyncio.Queue()
        hub.subscribe(KEY, late)

        assert late.get_nowait() == status and late.get_nowait() == candle
        hub.unsubscribe(KEY, early)
        hub.unsubscribe(KEY, late)

    asyncio.run(scenario())


def test_hub_runs_one_feed_for_many_viewers_and_stops_it_after_the_last_one_leaves():
    async def scenario():
        started, cancelled = [], []

        async def feed(hub, key):
            started.append(key)
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.append(key)
                raise

        hub = live.LiveHub(feed)
        first, second = asyncio.Queue(), asyncio.Queue()
        hub.subscribe(KEY, first)
        hub.subscribe(KEY, second)
        await asyncio.sleep(0)
        assert started == [KEY]  # one feed, not two

        hub.unsubscribe(KEY, first)
        await asyncio.sleep(0.01)
        assert cancelled == []  # someone is still watching

        hub.unsubscribe(KEY, second)
        await asyncio.sleep(0.01)
        assert cancelled == [KEY]

    asyncio.run(scenario())


def test_a_slow_viewer_loses_its_oldest_messages_instead_of_blocking_the_feed():
    async def scenario():
        async def idle_feed(hub, key):
            await asyncio.Event().wait()

        hub = live.LiveHub(idle_feed)
        slow = asyncio.Queue(maxsize=2)
        hub.subscribe(KEY, slow)
        for close in (1.0, 2.0, 3.0):
            hub.publish(KEY, {"type": "candle", "close": close})

        assert [slow.get_nowait()["close"], slow.get_nowait()["close"]] == [2.0, 3.0]
        hub.unsubscribe(KEY, slow)

    asyncio.run(scenario())


def test_polling_feed_says_unavailable_for_forex_4h():
    async def scenario():
        hub = live.LiveHub(live.run_feed)
        outbox = asyncio.Queue()
        hub.subscribe(("XAUUSD", "4h"), outbox)

        message = await asyncio.wait_for(outbox.get(), timeout=1)

        assert message["type"] == "status" and message["mode"] == "unavailable"
        hub.unsubscribe(("XAUUSD", "4h"), outbox)

    asyncio.run(scenario())


def test_polling_feed_publishes_a_delayed_forming_candle(monkeypatch):
    now_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    forming = {"open_time": now_hour, "open": 4100.0, "high": 4105.0, "low": 4098.0, "close": 4102.0, "volume": None}
    monkeypatch.setattr(live, "is_market_closed", lambda when: False)
    monkeypatch.setattr(live.providers, "fetch_twelvedata", lambda symbol, timeframe, count: [forming])
    monkeypatch.setattr(live, "FOREX_POLL_SECONDS", 0.01)

    async def scenario():
        key = ("XAUUSD", "1h")
        hub = live.LiveHub(live.run_feed)
        outbox = asyncio.Queue()
        hub.subscribe(key, outbox)
        messages = [await asyncio.wait_for(outbox.get(), timeout=1) for _ in range(2)]
        hub.unsubscribe(key, outbox)
        return messages

    status, candle = asyncio.run(scenario())

    assert status["mode"] == "delayed"
    assert candle["type"] == "candle" and candle["close"] == 4102.0
    assert candle["time"] == int(now_hour.timestamp()) and candle["closed"] is False


def test_polling_feed_does_not_call_the_provider_while_the_market_is_closed(monkeypatch):
    calls = []
    monkeypatch.setattr(live, "is_market_closed", lambda when: True)
    monkeypatch.setattr(live.providers, "fetch_twelvedata", lambda *args: calls.append(args))
    monkeypatch.setattr(live, "FOREX_POLL_SECONDS", 0.01)

    async def scenario():
        key = ("EURUSD", "1h")
        hub = live.LiveHub(live.run_feed)
        outbox = asyncio.Queue()
        hub.subscribe(key, outbox)
        message = await asyncio.wait_for(outbox.get(), timeout=1)
        await asyncio.sleep(0.05)
        hub.unsubscribe(key, outbox)
        return message

    message = asyncio.run(scenario())

    assert message["mode"] == "closed_market" and calls == []
