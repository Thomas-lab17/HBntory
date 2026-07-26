"""Tests du module JWT indépendant de la base."""

from dataclasses import dataclass
from typing import Dict, Generator, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME, create_auth_router, hash_password, verify_password


@dataclass
class FakeUser:
    id: int
    username: str
    password_hash: str
    role: str = "common"
    branch_id: int = 1
    deleted: bool = False


@pytest.fixture
def users() -> Dict[str, FakeUser]:
    return {
        "personne1": FakeUser(
            1, "personne1", hash_password("correct-password")
        )
    }


@pytest.fixture
def client(users: Dict[str, FakeUser]) -> Generator[TestClient, None, None]:
    def find_by_id(user_id: int) -> Optional[FakeUser]:
        return next((user for user in users.values() if user.id == user_id), None)

    app = FastAPI()
    app.include_router(
        create_auth_router(users.get, find_by_id, secret="test-secret")
    )
    with TestClient(app) as test_client:
        yield test_client


def test_password_hash() -> None:
    password_hash = hash_password("password")
    assert password_hash.startswith("$argon2id$")
    assert verify_password("password", password_hash)
    assert not verify_password("wrong", password_hash)


def test_login_me_logout(client: TestClient) -> None:
    login = client.post(
        "/auth/login",
        json={"username": "Personne1", "password": "correct-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "common"
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "samesite=lax" in login.headers["set-cookie"].lower()

    client.cookies.set(COOKIE_NAME, login.cookies[COOKIE_NAME])
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204


def test_invalid_credentials_are_refused(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"username": "personne1", "password": "wrong"},
    )
    assert response.status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_deleted_user_is_refused(
    client: TestClient, users: Dict[str, FakeUser]
) -> None:
    users["personne1"].deleted = True
    response = client.post(
        "/auth/login",
        json={"username": "personne1", "password": "correct-password"},
    )
    assert response.status_code == 401
