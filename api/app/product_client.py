# Client for Tom's Product MCP server (HTTP bridge).
# Contract (Tom's README): GET {base}/tools/list_products and
# GET {base}/tools/products/{id} return {"success": bool, ...}.
# Never raises: connection problems come back as a structured error dict.
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("MCP_SERVER_URL", "http://localhost:8002").rstrip("/")
TIMEOUT = 10.0


def _get(path: str) -> dict:
    """GET a tool endpoint; return its JSON or a connection-error dict."""
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network, timeout, or invalid JSON
        return {
            "success": False,
            "error_type": "connection_error",
            "message": f"MCP server unreachable at {BASE}: {exc}",
        }


def list_products() -> dict:
    """Ask the MCP server for the full product catalog."""
    return _get("/tools/list_products")


def get_product(product_id: str) -> dict:
    """Ask the MCP server for one product's details."""
    return _get(f"/tools/products/{urllib.parse.quote(product_id, safe='')}")
