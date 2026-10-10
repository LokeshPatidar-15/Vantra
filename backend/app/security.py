import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


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


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a signed JWT. 'sub' must be a string, so we convert the UUID."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Verify signature + expiry and return the payload. Raises jwt.PyJWTError if invalid."""
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
