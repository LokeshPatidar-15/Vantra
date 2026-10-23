import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """What the client is allowed to send to /signup."""

    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def check_bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value


class UserLogin(BaseModel):
    """What the client sends to /login. No password rules here on purpose."""

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserOut(BaseModel):
    """What we send back. No password, no hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- market data (Day 10) ----------

class SymbolOut(BaseModel):
    symbol: str
    label: str
    provider: str
    price_precision: int
    has_volume: bool
    timeframes: list[str]


class CandleOut(BaseModel):
    """Chart-ready candle. `time` is the candle's OPEN time in UNIX seconds (UTC)."""

    time: int
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class IngestRequest(BaseModel):
    symbol: str
    timeframe: str
    count: int = Field(default=1000, ge=1, le=5000)


class IngestResult(BaseModel):
    symbol: str
    timeframe: str
    source: str
    fetched: int
    inserted: int
    already_present: int
    forming_dropped: int
    market_closed_dropped: int
    invalid_dropped: int
    first_time: Optional[int] = None
    last_time: Optional[int] = None
