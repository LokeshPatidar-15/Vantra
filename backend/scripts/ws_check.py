"""Check the live WebSocket from the terminal (no browser needed).

Run from the backend/ folder while the API is running:
    python -m scripts.ws_check BTCUSDT 1m 4
    python -m scripts.ws_check XAUUSD 1h 1

Prints the messages until N candle messages arrive. Uses the local test account.
"""
import asyncio
import json
import os
import sys

import requests
import websockets

API = os.getenv("VANTRA_API", "http://localhost:8001")
EMAIL = os.getenv("VANTRA_EMAIL", "lokesh@vantra.dev")
PASSWORD = os.getenv("VANTRA_PASSWORD", "Str0ngPass!23")


async def watch(symbol, timeframe, wanted):
    login = requests.post(f"{API}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=10)
    if login.status_code != 200:
        raise SystemExit(f"Login failed (HTTP {login.status_code}). Check VANTRA_EMAIL and VANTRA_PASSWORD.")
    token = login.json()["access_token"]

    async with websockets.connect(API.replace("http", "ws", 1) + "/ws/market") as socket:
        await socket.send(json.dumps({"type": "auth", "token": token}))
        await socket.send(json.dumps({"type": "subscribe", "symbol": symbol, "timeframe": timeframe}))

        candles = 0
        while candles < wanted:
            try:
                message = json.loads(await asyncio.wait_for(socket.recv(), timeout=45))
            except asyncio.TimeoutError:
                print("No message for 45 seconds, stopping.")
                return
            print(message)
            if message["type"] == "candle":
                candles += 1
            elif message["type"] == "status" and message["mode"] in ("unavailable", "closed_market"):
                return  # nothing more will come (for example 4h on forex, or a weekend)


def main():
    args = sys.argv[1:]
    if len(args) != 3 or not args[2].isdigit():
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(watch(args[0].upper(), args[1].lower(), int(args[2])))


if __name__ == "__main__":
    main()
