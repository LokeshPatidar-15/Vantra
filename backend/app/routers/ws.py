import asyncio
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import CORS_ORIGINS
from app.database import SessionLocal
from app.market import live
from app.market.catalog import SYMBOLS, TIMEFRAME_SECONDS
from app.models import User
from app.security import decode_access_token

router = APIRouter()

AUTH_TIMEOUT_SECONDS = 10
POLICY_VIOLATION = 1008  # the standard WebSocket close code for "you broke the rules"


def _token_is_valid(token) -> bool:
    """Blocking check (run it in a thread): a valid access token of an existing user?"""
    try:
        user_id = uuid.UUID(decode_access_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return False
    with SessionLocal() as db:
        return db.get(User, user_id) is not None


@router.websocket("/ws/market")
async def market_socket(websocket: WebSocket):
    """Live candle updates.

    Protocol (JSON messages):
      client -> {"type": "auth", "token": "<access token>"}          must be the first message
      server -> {"type": "ready"}
      client -> {"type": "subscribe", "symbol": "BTCUSDT", "timeframe": "1m"}   (send again to switch)
      server -> {"type": "subscribed", ...}, {"type": "status", ...}, {"type": "candle", ...} ...
    """
    # CORS does not apply to WebSockets, so we check the Origin header ourselves.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in CORS_ORIGINS:
        await websocket.close(code=POLICY_VIOLATION)
        return

    await websocket.accept()

    # Browsers cannot add an Authorization header to a WebSocket, so the token is the first message.
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
        authenticated = first.get("type") == "auth" and await asyncio.to_thread(_token_is_valid, first.get("token"))
    except (asyncio.TimeoutError, WebSocketDisconnect, ValueError, AttributeError):
        authenticated = False
    if not authenticated:
        await websocket.close(code=POLICY_VIOLATION)
        return

    hub = live.hub
    outbox = asyncio.Queue(maxsize=live.OUTBOX_SIZE)
    current_key = None

    async def forward():
        """The only task that writes to the socket: everything goes through the outbox."""
        while True:
            await websocket.send_json(await outbox.get())

    sender = asyncio.create_task(forward())
    outbox.put_nowait({"type": "ready"})
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                outbox.put_nowait({"type": "error", "detail": "Messages must be valid JSON"})
                continue

            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "subscribe":
                symbol = str(message.get("symbol", "")).upper()
                timeframe = str(message.get("timeframe", "")).lower()
                if symbol not in SYMBOLS or timeframe not in TIMEFRAME_SECONDS:
                    outbox.put_nowait({"type": "error", "detail": "Unknown symbol or timeframe"})
                    continue
                if current_key:
                    hub.unsubscribe(current_key, outbox)
                current_key = (symbol, timeframe)
                outbox.put_nowait({"type": "subscribed", "symbol": symbol, "timeframe": timeframe})
                hub.subscribe(current_key, outbox)
            elif kind == "unsubscribe":
                if current_key:
                    hub.unsubscribe(current_key, outbox)
                    current_key = None
            else:
                outbox.put_nowait({"type": "error", "detail": "Unknown message type"})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        if current_key:
            hub.unsubscribe(current_key, outbox)
