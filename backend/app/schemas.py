import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """What the client is allowed to send to /signup."""

    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # "Lokesh@Vantra.dev" and "lokesh@vantra.dev" must be the same account.
        return value.lower()

    @field_validator("password")
    @classmethod
    def check_bcrypt_limit(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes, so we reject longer passwords.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value


class UserOut(BaseModel):
    """What we send back. No password, no hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
