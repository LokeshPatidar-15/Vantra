import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserOut
from app.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _set_refresh_cookie(response: Response, user_id: uuid.UUID) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=create_refresh_token(user_id),
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,  # JavaScript cannot read it
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,  # only sent to /api/auth/...
    )


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))

    # Always run exactly one bcrypt check, even for unknown emails, so the
    # response time does not reveal whether an email is registered.
    stored_hash = user.password_hash if user else DUMMY_HASH
    password_ok = verify_password(payload.password, stored_hash)

    if user is None or not password_ok:
        raise _unauthorized("Incorrect email or password")

    _set_refresh_cookie(response, user.id)
    return Token(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=Token)
def refresh(request: Request, db: Session = Depends(get_db)):
    """Exchange the refresh-token cookie for a new access token."""
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_refresh_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized("Invalid or expired refresh token")

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid or expired refresh token")

    return Token(access_token=create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    """Clear the refresh-token cookie."""
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=True,
        samesite=COOKIE_SAMESITE,
    )
    return response


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    """Protected route: only works with a valid Bearer token."""
    return current_user
