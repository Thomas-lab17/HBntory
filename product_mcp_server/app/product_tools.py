"""
product_tools.py
------------------
The actual behaviour behind each MCP tool, kept separate from the MCP SDK
wiring (server.py) so it can be unit-/manually-tested with plain Python,
with no MCP runtime required.

Each function returns a plain JSON-serializable dict, and NEVER raises --
all Product API failures are converted into a clear, structured error
payload so the calling AI agent always gets an explicit answer instead of
a crash or a silent empty result.
"""

from product_client import (
    ProductAPIClient,
    ProductNotFoundError,
    ProductAPIConnectionError,
    ProductAPIError,
)

_client = ProductAPIClient()


def _normalize_product(p: dict) -> dict:
    """Map the raw API product shape to the stable shape we expose to the
    AI agent, so upstream API changes don't automatically leak through."""
    return {
        "id": str(p.get("id")),
        "name": p.get("name"),
        "price": p.get("price"),
        "category": p.get("category"),
        "in_stock": p.get("in_stock", p.get("inStock")),
        "description": p.get("description"),
    }


def list_products_impl() -> dict:
    """
    List all available products.

    Output (success):
        {"success": true, "count": <int>, "products": [ {id, name, price,
         category, in_stock, description}, ... ]}
    Output (failure):
        {"success": false, "error_type": "connection_error" | "api_error",
         "message": <str>, "status_code": <int|null>}
    """
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
    """
    Get details for a single product by id.

    Output (success):
        {"success": true, "product": {id, name, price, category,
         in_stock, description}}
    Output (not found):
        {"success": false, "error_type": "not_found", "message": <str>,
         "status_code": 404}
    Output (other failure):
        {"success": false, "error_type": "connection_error" | "api_error"
         | "invalid_input", "message": <str>, "status_code": <int|null>}
    """
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
