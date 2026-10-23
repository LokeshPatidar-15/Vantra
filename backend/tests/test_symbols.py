PASSWORD = "Str0ngPass!23"


def test_symbols_include_label_precision_and_volume_flag(client):
    client.post("/api/auth/signup", json={"email": "viewer@vantra.dev", "password": PASSWORD})
    login = client.post("/api/auth/login", json={"email": "viewer@vantra.dev", "password": PASSWORD})
    token = login.json()["access_token"]

    response = client.get("/api/market/symbols", headers={"Authorization": f"Bearer {token}"})

    by_symbol = {item["symbol"]: item for item in response.json()}
    assert by_symbol["EURUSD"]["price_precision"] == 5
    assert by_symbol["BTCUSDT"]["has_volume"] is True
    assert by_symbol["XAUUSD"]["has_volume"] is False
    assert by_symbol["XAUUSD"]["label"]
