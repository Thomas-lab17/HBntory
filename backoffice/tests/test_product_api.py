"""Tests de l'intégration avec l'API Product externe."""

from typing import Any

import pytest
import requests

from app import product_api
from app.routers.products import _response


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self.payload


def test_list_products_reads_paginated_results(monkeypatch) -> None:
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        return FakeResponse(
            200,
            {
                "count": 1,
                "limit": 100,
                "offset": 0,
                "results": [
                    {
                        "id": 6,
                        "sku": "HB-KBD-4101",
                        "name": "Mechanical Keyboard EN",
                    }
                ],
            },
        )

    monkeypatch.setenv("PRODUCT_API_URL", "http://catalog:5000/")
    monkeypatch.setattr(product_api.requests, "get", fake_get)

    products = product_api.list_products()

    assert products[0]["id"] == 6
    assert calls == [
        (
            "http://catalog:5000/api/v1/products",
            {"limit": 100, "sort": "name"},
            5,
        )
    ]


def test_list_products_fetches_the_entire_supplier_catalog(monkeypatch) -> None:
    calls = []
    supplier_products = [
        {"id": product_id, "name": f"Product {product_id}"}
        for product_id in range(1, 102)
    ]

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params, timeout))
        offset = params.get("offset", 0)
        limit = params["limit"]
        return FakeResponse(
            200,
            {
                "count": len(supplier_products),
                "limit": limit,
                "offset": offset,
                "results": supplier_products[offset:offset + limit],
            },
        )

    monkeypatch.setattr(product_api.requests, "get", fake_get)

    products = product_api.list_products()

    assert products == supplier_products
    assert [call[1] for call in calls] == [
        {"limit": 100, "sort": "name"},
        {"limit": 100, "sort": "name", "offset": 100},
    ]


def test_get_product_accepts_id_or_sku(monkeypatch) -> None:
    monkeypatch.setattr(
        product_api.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "id": 6,
                "sku": "HB-KBD-4101",
                "name": "Mechanical Keyboard EN",
            },
        ),
    )

    assert product_api.get_product(" HB-KBD-4101 ")["id"] == 6


def test_unknown_product_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(
        product_api.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(
            404,
            {"error": "not_found", "message": "Product not found."},
        ),
    )

    with pytest.raises(product_api.ProductNotFound):
        product_api.get_product("UNKNOWN")


def test_unavailable_product_api_is_explicit(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(product_api.requests, "get", unavailable)

    with pytest.raises(product_api.ProductAPIUnavailable):
        product_api.list_products()


def test_invalid_collection_payload_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(
        product_api.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(200, {"items": []}),
    )

    with pytest.raises(product_api.ProductAPIError):
        product_api.list_products()


def test_product_response_keeps_catalog_details() -> None:
    response = _response(
        {
            "id": 6,
            "sku": "HB-KBD-4101",
            "name": "Mechanical Keyboard EN",
            "category": "Accessories",
            "description": "Mechanical training keyboard.",
            "brand": "Campus",
            "supplier_id": "SUP-CMP-003",
            "supplier_name": "Campus Components",
            "unit_price": 74,
            "currency": "USD",
            "discontinued": False,
            "weight_kg": 0.91,
            "tags": ["keyboard", "mechanical", "english"],
            "updated_at": "2026-05-22T12:00:00Z",
        }
    )

    assert response.description == "Mechanical training keyboard."
    assert response.brand == "Campus"
    assert response.supplier_id == "SUP-CMP-003"
    assert response.supplier_name == "Campus Components"
    assert response.discontinued is False
    assert response.weight_kg == 0.91
    assert response.tags == ["keyboard", "mechanical", "english"]
    assert response.updated_at == "2026-05-22T12:00:00Z"
