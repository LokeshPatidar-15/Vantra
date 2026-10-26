import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to backend/.env (see .env.example).")
    return value


DATABASE_URL = _require("DATABASE_URL")
SECRET_KEY = _require("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# The refresh token travels in an httpOnly cookie.
# COOKIE_SECURE must be true in production (HTTPS); false for local http.
REFRESH_COOKIE_NAME = "vantra_refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()

# Comma-separated list of frontend origins allowed to call this API.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5180").split(",")
    if origin.strip()
]

# Market data (Day 10). Binance public candles need no key; Twelve Data does.
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

# Emails (comma-separated) allowed to run admin actions such as candle ingestion.
ADMIN_EMAILS = [email.strip().lower() for email in os.getenv("ADMIN_EMAILS", "").split(",") if email.strip()]

# Live updates (Day 14). Forex and gold are polled from Twelve Data; each poll costs 1 API credit.
FOREX_POLL_SECONDS = max(30, int(os.getenv("FOREX_POLL_SECONDS", "120")))
