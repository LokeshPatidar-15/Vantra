"""What Vantra can chart: our symbols, how each provider spells them, and the timeframes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str  # our own name, used in the database and the API
    provider: str  # "binance" or "twelvedata"
    provider_symbol: str  # how that provider spells it
    is_24_7: bool  # crypto trades all week; forex and gold are closed on weekends


SYMBOLS = {
    "BTCUSDT": SymbolInfo("BTCUSDT", "binance", "BTCUSDT", True),
    "XAUUSD": SymbolInfo("XAUUSD", "twelvedata", "XAU/USD", False),
    "EURUSD": SymbolInfo("EURUSD", "twelvedata", "EUR/USD", False),
}

# timeframe -> length of one candle in seconds
TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}

# Twelve Data spells some timeframes differently (Binance accepts ours as they are)
TWELVEDATA_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
