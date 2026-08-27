# Client for the Backoffice read-only stock endpoint (api branch).
# Contract: GET {base}/api/stock/product/{id} with header X-API-Key ->
#   {"success": true, "product_id": str, "stock": [{"branch": str, "quantity": int}, ...]}
#   or {"success": false, "error_type": "not_found" | "unavailable", ...}
# Never raises: failures come back as structured dicts the agent relays.
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("BACKOFFICE_API_URL", "http://localhost:5000").rstrip("/")
API_KEY = os.environ.get("SERVICE_API_KEY", "dev-service-key")
TIMEOUT = 5.0


def stock_by_product(product_id: str, branch: str | None = None) -> dict:
    """Return stock of a product across branches (or one named branch)."""
    url = f"{BASE}/api/stock/product/{urllib.parse.quote(product_id, safe='')}"
    req = urllib.request.Request(
        url,
        headers={"X-API-Key": API_KEY, "User-Agent": "hbntory-ai/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {
            "success": False,
            "error_type": "unavailable",
            "message": "Stock information is currently unavailable.",
        }
    if branch:
        # Narrow to the requested branch (case-insensitive name match).
        data = {
            **data,
            "stock": [s for s in data.get("stock", []) if s["branch"].lower() == branch.lower()],
        }
    return data


def stock_by_branch(branch: str) -> dict:
    """Return the full stock of one named branch in a single call."""
    url = f"{BASE}/api/stock/branch/{urllib.parse.quote(branch, safe='')}"
    req = urllib.request.Request(
        url,
        headers={"X-API-Key": API_KEY, "User-Agent": "hbntory-ai/0.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {
            "success": False,
            "error_type": "unavailable",
            "message": "Stock information is currently unavailable.",
        }
