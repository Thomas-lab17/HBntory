"""
test_manual.py
---------------
Manual test evidence for the Product MCP server, run against:
  1. product_client.py directly (raw HTTP layer)
  2. product_tools.py (the exact logic wired into the MCP tools)

Covers all four required scenarios:
  - Successful product listing
  - Product detail retrieval
  - Product not found
  - Product API connection error

Usage:
  Terminal 1:  python mock_api.py
  Terminal 2:  python test_manual.py
"""

import json
import os

from product_client import ProductAPIClient, ProductNotFoundError, ProductAPIConnectionError
import product_tools


def header(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    live_base_url = os.environ.get("PRODUCT_API_BASE_URL", "http://localhost:8000")

    # ---------------------------------------------------------------
    header("PART 1 - product_client.py (raw API communication layer)")
    # ---------------------------------------------------------------
    client = ProductAPIClient(base_url=live_base_url)

    print("\n[Test 1] list_products() against a running API")
    try:
        products = client.list_products()
        print(f"OK - received {len(products)} products:")
        for p in products:
            print(f"   - {p['id']}: {p['name']} (${p['price']})")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print("\n[Test 2] get_product('p1') - existing product")
    try:
        product = client.get_product("p1")
        print(f"OK - {json.dumps(product)}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print("\n[Test 3] get_product('does-not-exist') - should raise ProductNotFoundError")
    try:
        product = client.get_product("does-not-exist")
        print(f"UNEXPECTED SUCCESS: {product}")
    except ProductNotFoundError as e:
        print(f"OK (expected) - {type(e).__name__}: {e} [status_code={e.status_code}]")
    except Exception as e:
        print(f"FAILED (wrong exception type): {type(e).__name__}: {e}")

    print("\n[Test 4] list_products() against an unreachable API port (9999)")
    print("          -> should raise ProductAPIConnectionError, not crash")
    unreachable_client = ProductAPIClient(base_url="http://localhost:9999")
    try:
        products = unreachable_client.list_products()
        print(f"UNEXPECTED SUCCESS: {products}")
    except ProductAPIConnectionError as e:
        print(f"OK (expected) - {type(e).__name__}: {e}")
    except Exception as e:
        print(f"FAILED (wrong exception type): {type(e).__name__}: {e}")

    # ---------------------------------------------------------------
    header("PART 2 - product_tools.py (exact logic behind the MCP tools)")
    # ---------------------------------------------------------------
    # product_tools uses PRODUCT_API_BASE_URL / PRODUCT_API_KEY env vars
    # internally via its module-level _client instance.

    print("\n[Tool test 1] list_products_impl() -> AI-agent-facing tool output")
    result = product_tools.list_products_impl()
    print(json.dumps(result, indent=2))
    assert result["success"] is True
    assert result["count"] == 3

    print("\n[Tool test 2] get_product_impl('p2') -> existing product")
    result = product_tools.get_product_impl("p2")
    print(json.dumps(result, indent=2))
    assert result["success"] is True
    assert result["product"]["name"] == "Mechanical Keyboard"

    print("\n[Tool test 3] get_product_impl('does-not-exist') -> not found")
    result = product_tools.get_product_impl("does-not-exist")
    print(json.dumps(result, indent=2))
    assert result["success"] is False
    assert result["error_type"] == "not_found"

    print("\n[Tool test 4] get_product_impl('') -> invalid input, handled before any API call")
    result = product_tools.get_product_impl("")
    print(json.dumps(result, indent=2))
    assert result["success"] is False
    assert result["error_type"] == "invalid_input"

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
