"""Shared fixtures for the Backoffice API tests.

A throwaway SQLite database is created for the test session and every test
gets a fresh schema + seed. The external Product API is not required: the
product client is stubbed in the stock tests.
"""
import os
import tempfile
from pathlib import Path

# Set BEFORE importing the app modules (they read the env at import time).
_tmpdir = Path(tempfile.mkdtemp(prefix="hbntory-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789"
os.environ["SERVICE_API_KEY"] = "test-service-key"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import models
from app.database import Base, SessionLocal, engine
from app.deps import get_db
from app.init_db import seed_if_missing
from app.main import app
from app.security import create_token, hash_password


def _branch(session, name):
    return session.scalar(select(models.Branch).where(models.Branch.name == name))


@pytest.fixture()
def db():
    """Fresh schema + seed (admin, 2 branches, sample stock, 2 common users)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seed_if_missing(session)
        paris = _branch(session, "Paris")
        lyon = _branch(session, "Lyon")
        session.add(
            models.User(
                username="paris_user", password_hash=hash_password("pw"),
                role="common", branch_id=paris.id,
            )
        )
        session.add(
            models.User(
                username="lyon_user", password_hash=hash_password("pw"),
                role="common", branch_id=lyon.id,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    """TestClient with the test DB session injected via dependency override."""
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def login(client):
    """Log in and return the Bearer token for a given user."""
    def _login(username, password="pw"):
        resp = client.post(
            "/api/login", json={"username": username, "password": password}
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["token"]
    return _login


@pytest.fixture()
def auth_headers():
    return lambda token: {"Authorization": f"Bearer {token}"}
