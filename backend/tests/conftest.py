import os
from pathlib import Path

from dotenv import dotenv_values

# 1) Point the app at the TEST database BEFORE any app module is imported.
#    config.py reads these environment variables, and python-dotenv never
#    overrides variables that are already set.
_env = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
_dev_url = _env.get("DATABASE_URL") or ""
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or (
    _dev_url.rsplit("/", 1)[0] + "/vantra_test" if _dev_url else ""
)

if not TEST_DATABASE_URL.endswith("_test"):
    raise RuntimeError(
        "Tests need a database whose name ends with '_test'. "
        "Set TEST_DATABASE_URL or check backend/.env."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["CORS_ORIGINS"] = "http://localhost:5180"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _check_test_database():
    """Safety net: refuse to run against the wrong database."""
    with engine.connect() as conn:
        db_name = conn.execute(text("select current_database()")).scalar()
        assert db_name.endswith("_test"), f"Refusing to run tests against '{db_name}'"
        tables = conn.execute(
            text(
                "select count(*) from information_schema.tables "
                "where table_schema = 'public' and table_name = 'users'"
            )
        ).scalar()
        assert tables == 1, "users table missing. Run: psql vantra_test -f db/schema.sql"


@pytest.fixture(autouse=True)
def _clean_users():
    """Every test starts with an empty users table."""
    with engine.begin() as conn:
        conn.execute(text("truncate table users"))
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
