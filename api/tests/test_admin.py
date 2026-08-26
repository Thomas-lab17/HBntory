"""Admin user-management tests."""
from sqlalchemy import select

from app import models


def test_admin_creates_common_user(client, login, auth_headers):
    token = login("admin", "admin")
    resp = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={"username": "newbie", "password": "secret", "branch_id": 1},
    )
    assert resp.status_code == 201
    body = resp.json()["user"]
    assert body["role"] == "common"
    assert body["branch_id"] == 1
    assert body["is_deleted"] is False


def test_create_user_duplicate(client, login, auth_headers):
    token = login("admin", "admin")
    client.post(
        "/api/users",
        headers=auth_headers(token),
        json={"username": "newbie", "password": "s", "branch_id": 1},
    )
    resp = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={"username": "newbie", "password": "s", "branch_id": 2},
    )
    assert resp.status_code == 409


def test_create_user_invalid_branch(client, login, auth_headers):
    token = login("admin", "admin")
    resp = client.post(
        "/api/users",
        headers=auth_headers(token),
        json={"username": "newbie", "password": "s", "branch_id": 999},
    )
    assert resp.status_code == 400


def test_admin_soft_deletes_user(client, db, login, auth_headers):
    token = login("admin", "admin")
    user = db.scalar(select(models.User).where(models.User.username == "paris_user"))
    resp = client.delete(f"/api/users/{user.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["user"]["is_deleted"] is True


def test_admin_cannot_edit_or_delete_self(client, db, login, auth_headers):
    token = login("admin", "admin")
    admin = db.scalar(select(models.User).where(models.User.username == "admin"))
    assert (
        client.patch(
            f"/api/users/{admin.id}", headers=auth_headers(token),
            json={"username": "root"},
        ).status_code == 400
    )
    assert client.delete(f"/api/users/{admin.id}", headers=auth_headers(token)).status_code == 400


def test_admin_changes_password_and_branch(client, db, login, auth_headers):
    token = login("admin", "admin")
    user = db.scalar(select(models.User).where(models.User.username == "paris_user"))
    resp = client.patch(
        f"/api/users/{user.id}",
        headers=auth_headers(token),
        json={"branch_id": 2, "password": "newpass"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["branch_id"] == 2
    assert client.post(
        "/api/login", json={"username": "paris_user", "password": "newpass"}
    ).status_code == 200
    assert client.post(
        "/api/login", json={"username": "paris_user", "password": "pw"}
    ).status_code == 401
