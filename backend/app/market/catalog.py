"""What Vantra can chart: our symbols, how each provider spells them, and the timeframes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolInfo:
    symbol: str  # our own name, used in the database and the API
    provider: str  # "binance" or "twelvedata"
    provider_symbol: str  # how that provider spells it
    is_24_7: bool  # crypto trades all week; forex and gold are closed on weekends
    label: str  # human-friendly name for the market selector
    price_precision: int  # decimals to show on the price axis
    has_volume: bool  # forex and gold have no real volume
    day_timezone: str  # the timezone in which this market's trading day is defined
    day_start_hour: int  # hour (in day_timezone) at which a new trading day starts

    @property
    def day_start_label(self) -> str:
        if self.day_timezone == "UTC":
            return f"{self.day_start_hour:02d}:00 UTC"
        return f"{self.day_start_hour:02d}:00 New York time"


SYMBOLS = {
    "BTCUSDT": SymbolInfo("BTCUSDT", "binance", "BTCUSDT", True, "Bitcoin / Tether", 2, True, "UTC", 0),
    "XAUUSD": SymbolInfo("XAUUSD", "twelvedata", "XAU/USD", False, "Gold / US Dollar", 2, False, "America/New_York", 18),
    "EURUSD": SymbolInfo("EURUSD", "twelvedata", "EUR/USD", False, "Euro / US Dollar", 5, False, "America/New_York", 18),
}

# timeframe -> length of one candle in seconds
TIMEFRAME_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400}

# Timeframes we build ourselves from smaller candles (never taken from a provider).
DERIVED_FROM = {"4h": "1h", "1d": "1h"}

# Twelve Data spells some timeframes differently (Binance accepts ours as they are)
TWELVEDATA_INTERVALS = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1day"}
