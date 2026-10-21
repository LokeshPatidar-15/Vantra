from datetime import datetime, timedelta, timezone

import pytest
import requests
from sqlalchemy import text

import app.market.providers as providers
from app.database import SessionLocal, engine
from app.market.candles import is_valid_candle, split_candles
from app.market.catalog import TIMEFRAME_SECONDS
from app.market.providers import ProviderError
from app.market.service import ingest_candles

API = "/api/market"
ADMIN_EMAIL = "admin@vantra.dev"  # listed in ADMIN_EMAILS by conftest.py
USER_EMAIL = "viewer@vantra.dev"
PASSWORD = "Str0ngPass!23"


# ---------- helpers ----------

def get_token(client, email):
    client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    return response.json()["access_token"]


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def floor_hour():
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def make_candles(count, timeframe="1h"):
    """`count` closed candles; the newest one closed at the start of the current hour."""
    step = timedelta(seconds=TIMEFRAME_SECONDS[timeframe])
    end = floor_hour()
    return [
        {
            "open_time": end - step * (count - i),
            "open": 100.0 + i,
            "high": 102.0 + i,
            "low": 99.0 + i,
            "close": 101.0 + i,
            "volume": 10.0,
        }
        for i in range(count)
    ]


def count_candles():
    with engine.connect() as conn:
        return conn.execute(text("select count(*) from candles")).scalar()


def use_fake_provider(monkeypatch, candles):
    monkeypatch.setattr(
        "app.market.service.fetch_recent_candles", lambda info, timeframe, count: list(candles)
    )


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self._payload


def binance_rows(count):
    end = floor_hour()
    rows = []
    for i in range(count):
        ms = int((end - timedelta(hours=count - i)).timestamp() * 1000)
        price = 100 + i
        rows.append([ms, str(price), str(price + 2), str(price - 1), str(price + 1), "5.5", ms + 3599999])
    return rows


# ---------- pure candle rules ----------

def test_is_valid_candle_rules():
    good = {"open": 10, "high": 12, "low": 9, "close": 11}
    assert is_valid_candle(good)
    assert not is_valid_candle({**good, "high": 8})  # high below open/close
    assert not is_valid_candle({**good, "low": 10.5})  # low above open
    assert not is_valid_candle({**good, "low": -1})  # negative price
    assert not is_valid_candle({**good, "close": float("nan")})


def test_split_candles_drops_forming_and_invalid():
    now = floor_hour() + timedelta(minutes=5)
    closed = {"open_time": floor_hour() - timedelta(hours=2), "open": 10, "high": 12, "low": 9, "close": 11}
    forming = {**closed, "open_time": floor_hour()}
    broken = {**closed, "open_time": floor_hour() - timedelta(hours=3), "high": 1}

    usable, forming_count, invalid_count, _ = split_candles([closed, forming, broken], "1h", now=now)

    assert usable == [closed]
    assert forming_count == 1
    assert invalid_count == 1


# ---------- providers (network faked) ----------

def test_binance_pages_backwards_without_duplicates(monkeypatch):
    monkeypatch.setattr(providers.time, "sleep", lambda seconds: None)
    master = binance_rows(2500)
    page_sizes = []

    def fake_get(url, params=None, timeout=None):
        page_sizes.append(params["limit"])
        rows = master
        if "endTime" in params:
            rows = [row for row in master if row[0] <= params["endTime"]]
        return FakeResponse(rows[-params["limit"] :])

    monkeypatch.setattr(providers.requests, "get", fake_get)
    candles = providers.fetch_binance("BTCUSDT", "1h", 2300)

    times = [candle["open_time"] for candle in candles]
    assert len(candles) == 2300
    assert times == sorted(times) and len(set(times)) == 2300
    assert page_sizes == [1000, 1000, 300]


def test_binance_falls_back_to_the_second_host(monkeypatch):
    hosts_called = []

    def fake_get(url, params=None, timeout=None):
        hosts_called.append(url)
        if "api.binance.com" in url:
            return FakeResponse({}, status_code=451)
        return FakeResponse(binance_rows(3))

    monkeypatch.setattr(providers.requests, "get", fake_get)
    assert len(providers.fetch_binance("BTCUSDT", "1h", 3)) == 3
    assert len(hosts_called) == 2


def test_binance_error_mentions_the_http_status(monkeypatch):
    monkeypatch.setattr(providers.requests, "get", lambda *a, **k: FakeResponse({}, status_code=451))
    with pytest.raises(ProviderError, match="451"):
        providers.fetch_binance("BTCUSDT", "1h", 3)


def test_twelvedata_sorts_oldest_first_and_allows_missing_volume(monkeypatch):
    monkeypatch.setattr(providers, "TWELVE_DATA_API_KEY", "test-key")
    end = floor_hour()
    newest_first = [
        {
            "datetime": (end - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S"),
            "open": "2400", "high": "2403", "low": "2399", "close": "2401",
        }
        for h in (1, 2, 3)
    ]
    monkeypatch.setattr(
        providers.requests, "get", lambda *a, **k: FakeResponse({"status": "ok", "values": newest_first})
    )

    candles = providers.fetch_twelvedata("XAU/USD", "1h", 3)

    times = [candle["open_time"] for candle in candles]
    assert times == sorted(times)
    assert candles[0]["open_time"].tzinfo is not None  # timezone-aware UTC
    assert candles[0]["volume"] is None


def test_twelvedata_error_message_never_contains_the_key(monkeypatch):
    monkeypatch.setattr(providers, "TWELVE_DATA_API_KEY", "super-secret-key")
    error_json = {"code": 429, "message": "out of credits", "status": "error"}
    monkeypatch.setattr(providers.requests, "get", lambda *a, **k: FakeResponse(error_json))
    with pytest.raises(ProviderError) as excinfo:
        providers.fetch_twelvedata("XAU/USD", "1h", 3)
    assert "429" in str(excinfo.value)
    assert "super-secret-key" not in str(excinfo.value)


def test_twelvedata_network_error_does_not_leak_the_key(monkeypatch):
    monkeypatch.setattr(providers, "TWELVE_DATA_API_KEY", "super-secret-key")

    def fake_get(url, params=None, timeout=None):
        raise requests.ConnectionError(f"failed for url /time_series?apikey={params['apikey']}")

    monkeypatch.setattr(providers.requests, "get", fake_get)
    with pytest.raises(ProviderError) as excinfo:
        providers.fetch_twelvedata("XAU/USD", "1h", 3)
    assert "super-secret-key" not in str(excinfo.value)


def test_twelvedata_without_a_key_raises(monkeypatch):
    monkeypatch.setattr(providers, "TWELVE_DATA_API_KEY", "")
    with pytest.raises(ProviderError, match="not configured"):
        providers.fetch_twelvedata("XAU/USD", "1h", 3)


# ---------- ingestion into the database ----------

def test_ingest_stores_only_closed_candles_and_is_idempotent(monkeypatch):
    closed = make_candles(5)
    still_forming = {"open_time": floor_hour(), "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 1.0}
    use_fake_provider(monkeypatch, closed + [still_forming])

    with SessionLocal() as db:
        first = ingest_candles(db, "BTCUSDT", "1h", 6)
        second = ingest_candles(db, "BTCUSDT", "1h", 6)

    assert first["inserted"] == 5 and first["forming_dropped"] == 1
    assert second["inserted"] == 0 and second["already_present"] == 5
    assert count_candles() == 5


def test_ingest_skips_invalid_candles(monkeypatch):
    candles = make_candles(3)
    candles[1]["high"] = 1.0  # high below open/close
    use_fake_provider(monkeypatch, candles)

    with SessionLocal() as db:
        result = ingest_candles(db, "BTCUSDT", "1h", 3)

    assert result["inserted"] == 2 and result["invalid_dropped"] == 1


# ---------- API: reading candles ----------

def test_candles_requires_login(client):
    response = client.get(f"{API}/candles", params={"symbol": "BTCUSDT", "timeframe": "1h"})
    assert response.status_code == 401


def test_candles_returns_the_latest_candles_oldest_first_in_chart_format(client, monkeypatch):
    token = get_token(client, USER_EMAIL)
    candles = make_candles(10)
    use_fake_provider(monkeypatch, candles)
    with SessionLocal() as db:
        ingest_candles(db, "BTCUSDT", "1h", 10)

    response = client.get(
        f"{API}/candles", params={"symbol": "BTCUSDT", "timeframe": "1h", "limit": 3}, headers=bearer(token)
    )

    body = response.json()
    assert response.status_code == 200 and len(body) == 3
    assert [item["time"] for item in body] == [int(c["open_time"].timestamp()) for c in candles[-3:]]
    assert set(body[0]) == {"time", "open", "high", "low", "close", "volume"}


def test_candles_accepts_lowercase_symbol(client, monkeypatch):
    token = get_token(client, USER_EMAIL)
    use_fake_provider(monkeypatch, make_candles(2))
    with SessionLocal() as db:
        ingest_candles(db, "BTCUSDT", "1h", 2)

    response = client.get(
        f"{API}/candles", params={"symbol": "btcusdt", "timeframe": "1H"}, headers=bearer(token)
    )
    assert response.status_code == 200 and len(response.json()) == 2


@pytest.mark.parametrize(
    "params",
    [
        {"symbol": "DOGEUSD", "timeframe": "1h"},
        {"symbol": "BTCUSDT", "timeframe": "3h"},
        {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 0},
        {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 5001},
    ],
)
def test_candles_rejects_bad_parameters(client, params):
    token = get_token(client, USER_EMAIL)
    response = client.get(f"{API}/candles", params=params, headers=bearer(token))
    assert response.status_code == 422


def test_symbols_lists_the_supported_markets(client):
    token = get_token(client, USER_EMAIL)
    response = client.get(f"{API}/symbols", headers=bearer(token))
    assert response.status_code == 200
    assert {item["symbol"] for item in response.json()} == {"BTCUSDT", "XAUUSD", "EURUSD"}


# ---------- API: ingestion (admin only) ----------

INGEST_BODY = {"symbol": "BTCUSDT", "timeframe": "1h", "count": 5}


def test_ingest_requires_login(client):
    assert client.post(f"{API}/ingest", json=INGEST_BODY).status_code == 401


def test_ingest_is_forbidden_for_a_normal_user(client):
    token = get_token(client, USER_EMAIL)
    assert client.post(f"{API}/ingest", json=INGEST_BODY, headers=bearer(token)).status_code == 403


def test_ingest_as_admin_stores_candles_and_returns_a_summary(client, monkeypatch):
    token = get_token(client, ADMIN_EMAIL)
    use_fake_provider(monkeypatch, make_candles(5))

    response = client.post(f"{API}/ingest", json=INGEST_BODY, headers=bearer(token))

    body = response.json()
    assert response.status_code == 200
    assert body["inserted"] == 5 and body["source"] == "binance"
    assert count_candles() == 5


def test_ingest_rejects_unknown_symbol_and_huge_count(client):
    token = get_token(client, ADMIN_EMAIL)
    bad_symbol = client.post(f"{API}/ingest", json={**INGEST_BODY, "symbol": "DOGEUSD"}, headers=bearer(token))
    huge_count = client.post(f"{API}/ingest", json={**INGEST_BODY, "count": 5001}, headers=bearer(token))
    assert bad_symbol.status_code == 422
    assert huge_count.status_code == 422


def test_ingest_returns_502_when_the_provider_fails(client, monkeypatch):
    token = get_token(client, ADMIN_EMAIL)

    def broken_provider(info, timeframe, count):
        raise ProviderError("provider is down")

    monkeypatch.setattr("app.market.service.fetch_recent_candles", broken_provider)

    response = client.post(f"{API}/ingest", json=INGEST_BODY, headers=bearer(token))

    assert response.status_code == 502
    assert response.json()["detail"] == "provider is down"
