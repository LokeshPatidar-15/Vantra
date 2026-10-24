from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.market.catalog import SYMBOLS, TIMEFRAME_SECONDS
from app.market.providers import ProviderError
from app.market.service import DerivedTimeframeError, get_candles, ingest_candles
from app.models import User
from app.schemas import CandleOut, IngestRequest, IngestResult, SymbolOut

router = APIRouter(prefix="/api/market", tags=["market"])


def _normalize(symbol: str, timeframe: str) -> tuple[str, str]:
    """Accept 'btcusdt' and 'BTCUSDT'; reject anything we do not support."""
    symbol, timeframe = symbol.upper(), timeframe.lower()
    if symbol not in SYMBOLS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported symbol '{symbol}'. Use one of: {', '.join(SYMBOLS)}",
        )
    if timeframe not in TIMEFRAME_SECONDS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported timeframe '{timeframe}'. Use one of: {', '.join(TIMEFRAME_SECONDS)}",
        )
    return symbol, timeframe


@router.get("/symbols", response_model=list[SymbolOut])
def list_symbols(current_user: User = Depends(get_current_user)):
    return [
        SymbolOut(
            symbol=info.symbol,
            label=info.label,
            provider=info.provider,
            price_precision=info.price_precision,
            has_volume=info.has_volume,
            day_start=info.day_start_label,
            timeframes=list(TIMEFRAME_SECONDS),
        )
        for info in SYMBOLS.values()
    ]


@router.get("/candles", response_model=list[CandleOut])
def read_candles(
    symbol: str,
    timeframe: str,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reads from OUR database only (fast, no provider call). Oldest candle first."""
    symbol, timeframe = _normalize(symbol, timeframe)
    return [
        CandleOut(
            time=int(candle["open_time"].timestamp()),
            open=candle["open"],
            high=candle["high"],
            low=candle["low"],
            close=candle["close"],
            volume=candle["volume"],
        )
        for candle in get_candles(db, symbol, timeframe, limit)
    ]


@router.post("/ingest", response_model=IngestResult)
def ingest(
    payload: IngestRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin only: fetch candles from the provider and store them."""
    symbol, timeframe = _normalize(payload.symbol, payload.timeframe)
    try:
        return ingest_candles(db, symbol, timeframe, payload.count)
    except DerivedTimeframeError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
