"""Authentication and authorization tests for the Backoffice API."""
from sqlalchemy import select

from app import models


def test_login_admin_success(client):
    resp = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["user"]["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_login_rejects_deleted_user(client, db):
    user = db.scalar(select(models.User).where(models.User.username == "paris_user"))
    user.is_deleted = True
    db.commit()
    resp = client.post("/api/login", json={"username": "paris_user", "password": "pw"})
    assert resp.status_code == 401


def test_protected_routes_require_token(client):
    assert client.get("/api/branches").status_code == 401
    assert client.get("/api/stock").status_code == 401
    assert client.get("/api/users").status_code == 401


def test_invalid_token_rejected(client, auth_headers):
    resp = client.get("/api/branches", headers=auth_headers("not-a-token"))
    assert resp.status_code == 401


def test_soft_deleted_token_stops_working(client, db, login, auth_headers):
    token = login("paris_user")
    assert client.get("/api/stock", headers=auth_headers(token)).status_code == 200
    user = db.scalar(select(models.User).where(models.User.username == "paris_user"))
    user.is_deleted = True
    db.commit()
    assert client.get("/api/stock", headers=auth_headers(token)).status_code == 401


def test_admin_cannot_manage_stock(client, login, auth_headers):
    token = login("admin", "admin")
    assert client.get("/api/stock", headers=auth_headers(token)).status_code == 403
    resp = client.post(
        "/api/stock/add",
        headers=auth_headers(token),
        json={"product_id": "HB-LAP-1001", "quantity": 1},
    )
    assert resp.status_code == 403


def test_common_cannot_manage_users(client, login, auth_headers):
    token = login("paris_user")
    assert client.get("/api/users", headers=auth_headers(token)).status_code == 403
    resp = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={"username": "x", "password": "y", "branch_id": 1},
    )
    assert resp.status_code == 403
