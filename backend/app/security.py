import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt hash (60 chars) of the given password."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against a stored hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # e.g. password longer than bcrypt's 72-byte limit, or a malformed hash
        return False


# Used to keep login timing the same when the email does not exist.
DUMMY_HASH = hash_password("not-a-real-password")


def _create_token(user_id: uuid.UUID, token_type: str, lifetime: timedelta) -> str:
    """Create a signed JWT. 'sub' must be a string; 'type' says what the token is for."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def _decode_token(token: str, expected_type: str) -> dict:
    """Verify signature + expiry, and that the token is of the expected type."""
    payload = jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload["type"] != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload


def decode_access_token(token: str) -> dict:
    return _decode_token(token, "access")


def decode_refresh_token(token: str) -> dict:
    return _decode_token(token, "refresh")
