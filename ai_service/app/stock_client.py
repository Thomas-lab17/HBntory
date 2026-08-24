# Client for the Backoffice read-only stock endpoint (built on the api branch).
# Contract: GET {base}/stock?product_id=X[&branch=Y] ->
#   {"success": true, "stock": [{"branch": str, "quantity": int}, ...]}
# Until the api service exists the endpoint is unreachable, so the agent
# reports stock information as unavailable (project requirement: never invent).
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("BACKOFFICE_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 5.0


def stock_by_product(product_id: str, branch: str | None = None) -> dict:
    """Return stock of a product across branches (or one named branch)."""
    params = {"product_id": product_id}
    if branch:
        params["branch"] = branch
    url = f"{BASE}/stock?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {
            "success": False,
            "error_type": "unavailable",
            "message": "Stock information is currently unavailable.",
        }
