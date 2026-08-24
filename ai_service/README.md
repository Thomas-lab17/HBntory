# AI Query Service (HBntory)

Independent backend that answers natural-language questions about products
and stock using an AI agent (Groq, OpenAI-compatible chat completions)
and tool calling.

## How it works

- `POST /query` `{"question": "..."}` -> `{"answer": "...", "tool_calls": [...]}`
- Each question is independent (no conversation history), so the client uses
  **REST** rather than WebSockets: simpler, stateless, and sufficient.
- The agent calls tools exposed by Tom's **Product MCP server** (HTTP bridge):
  `list_products`, `get_product`.
- Stock is read through the Backoffice API's read-only `/stock` endpoint.
  Until that service exists, stock answers clearly state it is unavailable.
- The agent never invents data: tool failures are relayed to the user.

## Run

```bash
# 1. Product MCP server (Tom's service, port 8002) — see product_mcp_server/

# 2. This service
cd ai_service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GROQ_API_KEY=gsk_... .venv/bin/uvicorn app.main:app --port 8100
```

Env vars: `GROQ_API_KEY` (required; Groq console key),
`GROQ_MODEL` (default `qwen/qwen3.6-27b`),
`MCP_SERVER_URL` (default `http://localhost:8002`),
`BACKOFFICE_API_URL` (default `http://localhost:8000`).

## Supported question types

- Product details ("Tell me about product p1")
- Where a product is available ("Which branch has stock of p1?")
- What products a branch has ("What products are in Downtown?")
- Which branch satisfies a shopping list ("Can I buy 2 of p1 and 3 of p2 in one branch?")

Out-of-scope questions get a clear "not supported" answer.
