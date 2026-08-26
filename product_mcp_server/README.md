# Product MCP Server

Isolates access to the external product catalog and exposes stable tools
for the AI agent (and the Backoffice). It is the **single integration
point** for the external Product API: both `ai_service` and `api/` call
this service instead of the external API directly.

## HTTP (Docker container)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/tools/list_products` | List the product catalog |
| `GET` | `/tools/products/{id}` | Product detail by id or SKU |

Env: `PRODUCT_API_URL` (e.g. `http://external-products-api:5000` in the
Compose network, or `http://localhost:5001` for local runs).

Errors are never silent: every tool returns a structured JSON payload with
a `success` flag, an `error_type` (`connection_error`, `not_found`,
`api_error`, `invalid_input`) and a `message`, so the AI agent can decide
how to react.

## MCP stdio (optional)

`app/server.py` exposes the same tools (`list_products`, `get_product`)
over the standard MCP protocol for tooling such as the MCP Inspector.

