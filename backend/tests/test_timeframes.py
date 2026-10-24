from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.market.service import ingest_candles

API = "/api/market"
ADMIN_EMAIL = "admin@vantra.dev"  # listed in ADMIN_EMAILS by conftest.py
PASSWORD = "Str0ngPass!23"


def get_token(client):
    client.post("/api/auth/signup", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    response = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    return response.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def candles_every(start, count, step):
    return [
        {
            "open_time": start + step * i,
            "open": 100.0 + i,
            "high": 110.0 + i,
            "low": 90.0 + i,
            "close": 105.0 + i,
            "volume": 2.0,
        }
        for i in range(count)
    ]


def store(monkeypatch, symbol, timeframe, candles):
    monkeypatch.setattr(
        "app.market.service.fetch_recent_candles", lambda info, tf, count: list(candles)
    )
    with SessionLocal() as db:
        ingest_candles(db, symbol, timeframe, len(candles))


def read(client, token, symbol, timeframe, limit=500):
    params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
    return client.get(f"{API}/candles", params=params, headers=bearer(token))


def test_daily_candles_are_built_from_hourly_candles(client, monkeypatch):
    token = get_token(client)
    start = datetime(2026, 10, 12, 0, tzinfo=timezone.utc)  # two full UTC days
    hourly = candles_every(start, 48, timedelta(hours=1))
    store(monkeypatch, "BTCUSDT", "1h", hourly)

    response = read(client, token, "BTCUSDT", "1d")

    body = response.json()
    assert response.status_code == 200 and len(body) == 2
    assert body[0]["time"] == int(start.timestamp())
    assert body[1]["time"] == int((start + timedelta(days=1)).timestamp())
    assert body[0]["open"] == hourly[0]["open"]
    assert body[0]["close"] == hourly[23]["close"]
    assert body[0]["high"] == max(c["high"] for c in hourly[:24])
    assert body[0]["volume"] == 48.0


def test_four_hour_candles_are_built_from_hourly_candles(client, monkeypatch):
    token = get_token(client)
    start = datetime(2026, 10, 12, 0, tzinfo=timezone.utc)
    store(monkeypatch, "BTCUSDT", "1h", candles_every(start, 8, timedelta(hours=1)))

    body = read(client, token, "BTCUSDT", "4h").json()

    assert [item["time"] for item in body] == [
        int(start.timestamp()),
        int((start + timedelta(hours=4)).timestamp()),
    ]


def test_limit_keeps_only_the_newest_derived_candles(client, monkeypatch):
    token = get_token(client)
    start = datetime(2026, 10, 12, 0, tzinfo=timezone.utc)  # three full UTC days
    store(monkeypatch, "BTCUSDT", "1h", candles_every(start, 72, timedelta(hours=1)))

    body = read(client, token, "BTCUSDT", "1d", limit=2).json()

    assert [item["time"] for item in body] == [
        int((start + timedelta(days=1)).timestamp()),
        int((start + timedelta(days=2)).timestamp()),
    ]


def test_forex_daily_candle_starts_at_18_00_new_york_time(client, monkeypatch):
    token = get_token(client)
    start = datetime(2026, 10, 18, 22, tzinfo=timezone.utc)  # Sunday 18:00 New York (summer time)
    store(monkeypatch, "XAUUSD", "1h", candles_every(start, 24, timedelta(hours=1)))

    body = read(client, token, "XAUUSD", "1d").json()

    assert len(body) == 1 and body[0]["time"] == int(start.timestamp())


def test_small_timeframes_are_read_as_stored(client, monkeypatch):
    token = get_token(client)
    start = datetime(2026, 10, 12, 0, tzinfo=timezone.utc)
    store(monkeypatch, "BTCUSDT", "15m", candles_every(start, 4, timedelta(minutes=15)))

    body = read(client, token, "BTCUSDT", "15m").json()

    assert len(body) == 4 and body[0]["time"] == int(start.timestamp())


def test_ingest_rejects_timeframes_we_build_ourselves(client):
    token = get_token(client)

    response = client.post(
        f"{API}/ingest",
        json={"symbol": "BTCUSDT", "timeframe": "4h", "count": 10},
        headers=bearer(token),
    )

    assert response.status_code == 422
    assert "built from 1h" in response.json()["detail"]
