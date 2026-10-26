import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from app.market import live

EMAIL = "viewer@vantra.dev"
PASSWORD = "Str0ngPass!23"


def get_token(client):
    client.post("/api/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    return response.json()["access_token"]


async def fake_feed(hub, key):
    """Stands in for Binance: one status message and one candle, then silence."""
    symbol, timeframe = key
    hub.publish(key, live.status_message(key, "live", "test feed"))
    hub.publish(
        key,
        {
            "type": "candle", "symbol": symbol, "timeframe": timeframe, "time": 1700000000,
            "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 3.0, "closed": False,
        },
    )
    await asyncio.Event().wait()


@pytest.fixture()
def fake_hub(monkeypatch):
    test_hub = live.LiveHub(fake_feed)
    monkeypatch.setattr(live, "hub", test_hub)
    return test_hub


def test_websocket_rejects_a_foreign_origin(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/market", headers={"origin": "http://evil.example"}):
            pass


def test_websocket_rejects_a_bad_token(client):
    with client.websocket_connect("/ws/market") as websocket:
        websocket.send_json({"type": "auth", "token": "not-a-token"})
        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_rejects_a_first_message_that_is_not_auth(client):
    with client.websocket_connect("/ws/market") as websocket:
        websocket.send_json({"type": "subscribe", "symbol": "BTCUSDT", "timeframe": "1m"})
        with pytest.raises(WebSocketDisconnect) as excinfo:
            websocket.receive_json()
    assert excinfo.value.code == 1008


def test_websocket_streams_candles_after_auth_and_subscribe(client, fake_hub):
    token = get_token(client)

    with client.websocket_connect("/ws/market") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        assert websocket.receive_json() == {"type": "ready"}
        websocket.send_json({"type": "subscribe", "symbol": "btcusdt", "timeframe": "1m"})
        messages = [websocket.receive_json() for _ in range(3)]

    assert {message["type"] for message in messages} == {"subscribed", "status", "candle"}
    candle = next(message for message in messages if message["type"] == "candle")
    assert candle["symbol"] == "BTCUSDT" and candle["close"] == 1.5


def test_websocket_reports_an_unknown_symbol(client, fake_hub):
    token = get_token(client)

    with client.websocket_connect("/ws/market") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        websocket.receive_json()
        websocket.send_json({"type": "subscribe", "symbol": "DOGEUSD", "timeframe": "1m"})
        message = websocket.receive_json()

    assert message["type"] == "error"
