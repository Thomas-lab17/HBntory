# Product MCP Server

An MCP server that bridges an AI agent to an external **Product API**,
exposing exactly two tools: listing products and getting product details.

## Files

| File                | Purpose |
|---------------------|---------|
| `product_client.py` | HTTP layer talking to the external Product API (stdlib `urllib`, zero dependencies). Raises typed exceptions. |
| `product_tools.py`  | The tool logic itself. Calls `product_client`, catches every exception, and returns a clean JSON-serializable dict — never raises, never crashes. |
| `server.py`         | MCP wiring. Registers `list_products` and `get_product` as MCP tools via the official `mcp` Python SDK (`FastMCP`). Thin — just delegates to `product_tools.py`. |
| `mock_api.py`       | A minimal stand-in Product API (stdlib only) used for manual testing. |
| `test_manual.py`    | Manual test script exercising all four required scenarios. |

The logic is split from the MCP wiring on purpose: `product_tools.py` has
no dependency on the `mcp` package, so it can be tested with plain Python
before ever touching the MCP runtime.

## 1. Tool definitions

### `list_products()`
Lists all available products. No input.

**Output (success)**
```json
{
  "success": true,
  "count": 3,
  "products": [
    {"id": "p1", "name": "Wireless Mouse", "price": 19.99,
     "category": "Electronics", "in_stock": true, "description": "..."}
  ]
}
```

**Output (failure)**
```json
{"success": false, "error_type": "connection_error", "message": "...", "status_code": null}
```

### `get_product(product_id: str)`
Gets details for exactly one product.

**Output (success)**
```json
{"success": true, "product": {"id": "p1", "name": "...", "price": 19.99,
 "category": "...", "in_stock": true, "description": "..."}}
```

**Output (not found)**
```json
{"success": false, "error_type": "not_found", "message": "Product 'x' was not found.", "status_code": 404}
```

Both tools return a fixed, normalized product shape (`id`, `name`, `price`,
`category`, `in_stock`, `description`) regardless of the exact shape the
underlying Product API uses internally — this keeps the AI agent
insulated from upstream API changes and avoids exposing any Product API
behavior beyond what's actually needed (pagination internals, raw HTTP
metadata, admin fields, etc. are never passed through).

## 2. Error handling

Every failure mode is turned into a **typed exception** in
`product_client.py`, then converted into a **structured dict** in
`product_tools.py` — the tool never throws and never returns an empty/
ambiguous result:

| Scenario                     | Exception raised            | `error_type` returned to agent |
|-------------------------------|------------------------------|-------------------------------|
| API unreachable (refused, DNS, timeout) | `ProductAPIConnectionError` | `connection_error` |
| Product id doesn't exist (API 404)      | `ProductNotFoundError`      | `not_found` |
| Any other non-2xx / bad response body   | `ProductAPIError`           | `api_error` |
| Empty/blank `product_id` passed by the agent | *(caught before any HTTP call)* | `invalid_input` |

Every error payload includes a human-readable `message` and, where
applicable, the original `status_code`, so the AI agent can decide how to
react (e.g. retry on `connection_error`, tell the user the product
doesn't exist on `not_found`) instead of just seeing a generic failure.

## 3. Running it for real

```bash
pip install mcp
python server.py          # starts the MCP server (stdio transport)
# or, for interactive dev:
mcp dev server.py
```

Point it at your real Product API:
```bash
export PRODUCT_API_BASE_URL="https://products.example.com/api"
export PRODUCT_API_KEY="..."   # optional, sent as Bearer token
python server.py
```

## 4. Manual test evidence

Tested end-to-end against `mock_api.py`, a minimal local stand-in for the
Product API implementing `GET /products`, `GET /products/{id}` (200), and
`GET /products/{id}` (404 for unknown ids).

**Setup**
```bash
python mock_api.py &          # mock Product API on http://localhost:8000
python test_manual.py         # runs all 4 scenarios against product_client.py and product_tools.py
```

**Actual captured output:**

```
======================================================================
PART 1 - product_client.py (raw API communication layer)
======================================================================

[Test 1] list_products() against a running API
OK - received 3 products:
   - p1: Wireless Mouse ($19.99)
   - p2: Mechanical Keyboard ($89.99)
   - p3: Standing Desk ($249.0)

[Test 2] get_product('p1') - existing product
OK - {"id": "p1", "name": "Wireless Mouse", "price": 19.99, "category": "Electronics", "in_stock": true, "description": "A reliable 2.4GHz wireless mouse."}

[Test 3] get_product('does-not-exist') - should raise ProductNotFoundError
OK (expected) - ProductNotFoundError: Product 'does-not-exist' was not found. [status_code=404]

[Test 4] list_products() against an unreachable API port (9999)
          -> should raise ProductAPIConnectionError, not crash
OK (expected) - ProductAPIConnectionError: Could not connect to Product API at http://localhost:9999/products: [Errno 111] Connection refused

======================================================================
PART 2 - product_tools.py (exact logic behind the MCP tools)
======================================================================

[Tool test 1] list_products_impl() -> AI-agent-facing tool output
{
  "success": true,
  "count": 3,
  "products": [ ... 3 normalized products ... ]
}

[Tool test 2] get_product_impl('p2') -> existing product
{
  "success": true,
  "product": {"id": "p2", "name": "Mechanical Keyboard", ...}
}

[Tool test 3] get_product_impl('does-not-exist') -> not found
{
  "success": false,
  "error_type": "not_found",
  "message": "Product 'does-not-exist' was not found.",
  "status_code": 404
}

[Tool test 4] get_product_impl('') -> invalid input, handled before any API call
{
  "success": false,
  "error_type": "invalid_input",
  "message": "product_id must be a non-empty string.",
  "status_code": null
}

All assertions passed.
```

**Additional test: Product API fully down** (mock API process killed, not
just an unreachable port), confirming the tools degrade cleanly with the
real API offline:

```
list_products_impl() with API down:
{
  "success": false,
  "error_type": "connection_error",
  "message": "Could not connect to Product API at http://localhost:8000/products: [Errno 111] Connection refused",
  "status_code": null
}

get_product_impl("p1") with API down:
{
  "success": false,
  "error_type": "connection_error",
  "message": "Could not connect to Product API at http://localhost:8000/products/p1: [Errno 111] Connection refused",
  "status_code": null
}
```

### Checklist mapped to results

- [x] Product listing works — Test 1 / Tool test 1
- [x] Product detail lookup works — Test 2 / Tool test 2
- [x] Invalid product identifiers handled correctly — Test 3 / Tool test 3 (`not_found`) and Tool test 4 (`invalid_input` for empty id)
- [x] Product API failures handled clearly — Test 4 and the "API fully down" run, both return `connection_error` with a clear message instead of raising or hanging
