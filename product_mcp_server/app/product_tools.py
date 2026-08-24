"""
product_tools.py
------------------
Behaviour behind each product tool. Never raises — always returns a structured dict.
"""

from __future__ import annotations

try:
    from app.product_client import (
        ProductAPIClient,
        ProductAPIConnectionError,
        ProductAPIError,
        ProductNotFoundError,
    )
except ImportError:  # script / MCP stdio entry
    from product_client import (
        ProductAPIClient,
        ProductAPIConnectionError,
        ProductAPIError,
        ProductNotFoundError,
    )

_client = ProductAPIClient()


def _normalize_product(p: dict) -> dict:
    price = p.get("price", p.get("unit_price"))
    sku = p.get("sku")
    return {
        "id": str(p.get("id")) if p.get("id") is not None else None,
        "sku": sku,
        "name": p.get("name"),
        "price": price,
        "category": p.get("category"),
        "in_stock": p.get("in_stock", p.get("inStock")),
        "description": p.get("description"),
        "currency": p.get("currency"),
    }


def list_products_impl() -> dict:
    try:
        raw_products = _client.list_products()
        products = [_normalize_product(p) for p in raw_products]
        return {"success": True, "count": len(products), "products": products}
    except ProductAPIConnectionError as e:
        return {
            "success": False,
            "error_type": "connection_error",
            "message": e.message,
            "status_code": e.status_code,
        }
    except ProductAPIError as e:
        return {
            "success": False,
            "error_type": "api_error",
            "message": e.message,
            "status_code": e.status_code,
        }


def get_product_impl(product_id: str) -> dict:
    if not product_id or not str(product_id).strip():
        return {
            "success": False,
            "error_type": "invalid_input",
            "message": "product_id must be a non-empty string.",
            "status_code": None,
        }

    try:
        raw = _client.get_product(product_id)
        return {"success": True, "product": _normalize_product(raw)}
    except ProductNotFoundError as e:
        return {
            "success": False,
            "error_type": "not_found",
            "message": e.message,
            "status_code": e.status_code,
        }
    except ProductAPIConnectionError as e:
        return {
            "success": False,
            "error_type": "connection_error",
            "message": e.message,
            "status_code": e.status_code,
        }
    except ProductAPIError as e:
        return {
            "success": False,
            "error_type": "api_error",
            "message": e.message,
            "status_code": e.status_code,
        }
