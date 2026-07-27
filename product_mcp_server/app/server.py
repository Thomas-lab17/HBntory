"""
server.py
---------
MCP server entrypoint. Wires the tool logic in product_tools.py to the
MCP protocol using the official MCP Python SDK (`pip install mcp`).

Run with:
    pip install mcp
    python server.py
or, for local dev with the MCP inspector:
    mcp dev server.py

Configuration (env vars):
    PRODUCT_API_BASE_URL   base URL of the external Product API
                            (default: http://localhost:8000)
    PRODUCT_API_KEY        optional bearer token sent as Authorization header
"""

from mcp.server.fastmcp import FastMCP
from product_tools import list_products_impl, get_product_impl

mcp = FastMCP("product-api-server")


@mcp.tool()
def list_products() -> dict:
    """
    List all available products from the Product API.

    Returns:
        On success: {"success": true, "count": int, "products": [
            {"id": str, "name": str, "price": number, "category": str,
             "in_stock": bool, "description": str}, ...
        ]}
        On failure: {"success": false, "error_type": "connection_error" |
            "api_error", "message": str, "status_code": int|None}
    """
    return list_products_impl()


@mcp.tool()
def get_product(product_id: str) -> dict:
    """
    Get details for a single product by its unique identifier.

    Args:
        product_id: The unique identifier of the product to retrieve.

    Returns:
        On success: {"success": true, "product": {"id": str, "name": str,
            "price": number, "category": str, "in_stock": bool,
            "description": str}}
        On not-found: {"success": false, "error_type": "not_found",
            "message": str, "status_code": 404}
        On other failure: {"success": false, "error_type":
            "connection_error" | "api_error" | "invalid_input",
            "message": str, "status_code": int|None}
    """
    return get_product_impl(product_id)


if __name__ == "__main__":
    mcp.run()
