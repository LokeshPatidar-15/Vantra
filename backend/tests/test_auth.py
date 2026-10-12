from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import ALGORITHM, SECRET_KEY
from app.database import engine
from app.security import create_refresh_token
from main import app

EMAIL = "tester@vantra.dev"
PASSWORD = "Str0ngPass!23"
API = "/api/auth"


# ---------- helpers ----------

def signup(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{API}/signup", json={"email": email, "password": password})


def login(client, email=EMAIL, password=PASSWORD):
    return client.post(f"{API}/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def signup_and_login(client):
    user = signup(client).json()
    token = login(client).json()["access_token"]
    return user, token


# ---------- signup ----------

def test_signup_creates_user_without_exposing_password(client):
    response = signup(client)
    body = response.json()
    assert response.status_code == 201
    assert body["email"] == EMAIL
    assert "id" in body and "created_at" in body
    assert "password" not in body and "password_hash" not in body


def test_signup_stores_a_bcrypt_hash_not_the_password(client):
    signup(client)
    with engine.connect() as conn:
        stored = conn.execute(
            text("select password_hash from users where email = :e"), {"e": EMAIL}
        ).scalar()
    assert stored != PASSWORD
    assert stored.startswith("$2b$") and len(stored) == 60


def test_signup_duplicate_email_returns_409(client):
    signup(client)
    assert signup(client).status_code == 409


def test_signup_email_is_case_insensitive(client):
    signup(client, email="tester@vantra.dev")
    assert signup(client, email="TESTER@Vantra.dev").status_code == 409


def test_signup_rejects_invalid_email(client):
    assert signup(client, email="notanemail").status_code == 422


def test_signup_rejects_short_password(client):
    assert signup(client, password="abc").status_code == 422


def test_signup_rejects_password_longer_than_72_bytes(client):
    assert signup(client, password="a" * 73).status_code == 422


# ---------- login ----------

def test_login_returns_access_token_and_refresh_cookie(client):
    signup(client)
    response = login(client)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]

    set_cookie = response.headers["set-cookie"].lower()
    assert "vantra_refresh_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "path=/api/auth" in set_cookie
    assert "samesite=lax" in set_cookie


def test_login_wrong_password_returns_401(client):
    signup(client)
    assert login(client, password="wrong-password").status_code == 401


def test_login_unknown_email_gives_same_error_as_wrong_password(client):
    signup(client)
    wrong_password = login(client, password="wrong-password")
    unknown_email = login(client, email="nobody@vantra.dev")
    assert unknown_email.status_code == wrong_password.status_code == 401
    assert unknown_email.json() == wrong_password.json()


# ---------- protected route: /me ----------

def test_me_requires_a_token(client):
    response = client.get(f"{API}/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_valid_token_returns_the_user(client):
    _, token = signup_and_login(client)
    response = client.get(f"{API}/me", headers=bearer(token))
    assert response.status_code == 200
    assert response.json()["email"] == EMAIL


def test_me_rejects_a_tampered_token(client):
    _, token = signup_and_login(client)
    assert client.get(f"{API}/me", headers=bearer(token + "x")).status_code == 401


def test_me_rejects_a_refresh_token_used_as_access_token(client):
    user, _ = signup_and_login(client)
    import uuid

    refresh_token = create_refresh_token(uuid.UUID(user["id"]))
    assert client.get(f"{API}/me", headers=bearer(refresh_token)).status_code == 401


def test_me_rejects_an_expired_token(client):
    user = signup(client).json()
    expired = jwt.encode(
        {
            "sub": user["id"],
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(seconds=5),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert client.get(f"{API}/me", headers=bearer(expired)).status_code == 401


def test_me_rejects_a_token_for_a_deleted_user(client):
    _, token = signup_and_login(client)
    with engine.begin() as conn:
        conn.execute(text("delete from users"))
    assert client.get(f"{API}/me", headers=bearer(token)).status_code == 401


# ---------- refresh + logout ----------

def test_refresh_without_cookie_returns_401(client):
    assert client.post(f"{API}/refresh").status_code == 401


def test_refresh_with_cookie_returns_a_working_access_token(client):
    signup_and_login(client)  # the client keeps the refresh cookie
    response = client.post(f"{API}/refresh")
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert client.get(f"{API}/me", headers=bearer(new_token)).status_code == 200


def test_refresh_rejects_an_access_token_placed_in_the_cookie(client):
    _, access_token = signup_and_login(client)
    with TestClient(app) as other_client:
        response = other_client.post(
            f"{API}/refresh", headers={"Cookie": f"vantra_refresh_token={access_token}"}
        )
    assert response.status_code == 401


def test_logout_clears_the_cookie_so_refresh_stops_working(client):
    signup_and_login(client)
    assert client.post(f"{API}/logout").status_code == 204
    assert client.post(f"{API}/refresh").status_code == 401


# ---------- CORS ----------

def test_cors_allows_the_frontend_origin_with_credentials(client):
    response = client.options(
        f"{API}/login",
        headers={
            "Origin": "http://localhost:5180",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5180"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_does_not_allow_an_unknown_origin(client):
    response = client.options(
        f"{API}/login",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


# ---------- health ----------

def test_health_reports_database_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "vantra-backend", "database": "ok"}
