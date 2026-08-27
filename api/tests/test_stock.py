"""Stock-rule tests for the Backoffice API (common-user role).

The external Product API is not required: product_client.get_product is
stubbed so that stock operations only exercise the local business rules.
"""
from unittest import mock

import pytest

VALID_PRODUCT = {
    "success": True,
    "product": {"id": 1, "sku": "HB-LAP-1001", "name": "Holberton Student Laptop 14"},
}

# Products that are NOT part of the seed stock, so quantity assertions are stable.
P_AVAILABLE = "HB-MSE-4201"   # Wireless Mouse
P_OTHER = "HB-CAM-5101"       # HD Webcam


@pytest.fixture(autouse=True)
def _catalog_stub():
    with mock.patch(
        "app.main.product_client.get_product", return_value=VALID_PRODUCT
    ):
        yield


def _add(client, headers, product_id, quantity):
    return client.post(
        "/api/stock/add",
        headers=headers,
        json={"product_id": product_id, "quantity": quantity},
    )


def _remove(client, headers, product_id, quantity):
    return client.post(
        "/api/stock/remove",
        headers=headers,
        json={"product_id": product_id, "quantity": quantity},
    )


def test_common_adds_stock(client, login, auth_headers):
    token = login("paris_user")
    resp = _add(client, auth_headers(token), P_AVAILABLE, 3)
    assert resp.status_code == 201
    assert resp.json()["stock"]["quantity"] == 3


def test_add_merges_same_product(client, login, auth_headers):
    token = login("paris_user")
    _add(client, auth_headers(token), P_AVAILABLE, 2)
    resp = _add(client, auth_headers(token), P_AVAILABLE, 5)
    assert resp.status_code == 201
    assert resp.json()["stock"]["quantity"] == 7


def test_add_rejects_non_positive_quantity(client, login, auth_headers):
    token = login("paris_user")
    assert _add(client, auth_headers(token), P_AVAILABLE, 0).status_code == 400
    assert _add(client, auth_headers(token), P_AVAILABLE, -4).status_code == 400


def test_add_rejects_unknown_product(client, login, auth_headers):
    token = login("paris_user")
    with mock.patch(
        "app.main.product_client.get_product",
        return_value={"success": False, "error_type": "not_found", "message": "not found"},
    ):
        resp = _add(client, auth_headers(token), "HB-UNKNOWN-9999", 1)
    assert resp.status_code == 400


def test_remove_stock(client, login, auth_headers):
    token = login("paris_user")
    _add(client, auth_headers(token), P_AVAILABLE, 10)
    resp = _remove(client, auth_headers(token), P_AVAILABLE, 4)
    assert resp.status_code == 200
    assert resp.json()["stock"]["quantity"] == 6


def test_remove_more_than_available(client, login, auth_headers):
    token = login("paris_user")
    _add(client, auth_headers(token), P_AVAILABLE, 3)
    resp = _remove(client, auth_headers(token), P_AVAILABLE, 10)
    assert resp.status_code == 400


def test_remove_missing_product(client, login, auth_headers):
    token = login("paris_user")
    resp = _remove(client, auth_headers(token), P_AVAILABLE, 1)
    assert resp.status_code == 404


def test_common_user_scoped_to_own_branch(client, login, auth_headers):
    paris = login("paris_user")
    lyon = login("lyon_user")
    _add(client, auth_headers(paris), P_AVAILABLE, 5)
    _add(client, auth_headers(lyon), P_OTHER, 9)

    paris_items = {
        s["product_id"]: s["quantity"]
        for s in client.get("/api/stock", headers=auth_headers(paris)).json()["stock"]
    }
    lyon_items = {
        s["product_id"]: s["quantity"]
        for s in client.get("/api/stock", headers=auth_headers(lyon)).json()["stock"]
    }

    assert paris_items[P_AVAILABLE] == 5
    assert P_OTHER not in paris_items
    assert lyon_items[P_OTHER] == 9
    assert P_AVAILABLE not in lyon_items


# ---- Internal endpoints (X-API-Key, for the AI service) ----

SERVICE_KEY_HEADER = {"X-API-Key": "test-service-key"}


def test_stock_by_branch_internal_endpoint(client):
    resp = client.get("/api/stock/branch/lyon", headers=SERVICE_KEY_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["branch"] == "Lyon"
    items = {s["product_id"]: s["quantity"] for s in body["stock"]}
    assert items["HB-LAP-1001"] == 7
    assert items["HB-MON-2101"] == 12


def test_stock_by_branch_unknown(client):
    resp = client.get("/api/stock/branch/Atlantis", headers=SERVICE_KEY_HEADER)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error_type"] == "not_found"


def test_stock_by_branch_requires_key(client):
    assert client.get("/api/stock/branch/Lyon").status_code == 401
