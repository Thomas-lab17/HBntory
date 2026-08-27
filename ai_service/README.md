# AI Query Service (HBntory)

Independent backend that answers natural-language questions about products
and stock. It uses an AI agent (Groq, OpenAI-compatible chat completions)
with tool calling, so answers are **grounded in real data** — the agent never
invents product names, prices, or stock quantities.

## How it works

```
User question
   │  POST /query {"question": "..."}
   ▼
┌────────────────────────────┐     tools      ┌─────────────────────────────┐
│  agent loop (app/agent.py) │ ─────────────► │  list_products / get_product │
│  system prompt + question  │                │  → product_mcp_server (HTTP) │
│  Groq chat completions     │                └─────────────────────────────┘
│  with tools                │     tools      ┌─────────────────────────────┐
│                            │ ─────────────► │  get_stock                  │
└────────────────────────────┘                │  → Backoffice API (internal)│
   │                                          └─────────────────────────────┘
   ▼
{ "answer": "...", "tool_calls": ["get_stock", ...] }
```

### The agent loop (`app/agent.py`)

1. Send the system prompt + user question to Groq, with the tool schemas.
2. If the model returns **tool calls**, execute them locally and send the
   results back as tool messages; loop.
3. When the model returns plain text, that is the final answer.
4. Loop is bounded (`MAX_STEPS = 6`); if the model never settles, a clear
   fallback message is returned.

Each tool call is logged to stdout as `[tool] <name>(<args>) -> <result>`,
so you can observe exactly what the agent asked for during a question.

### The tools (`app/tools.py`)

| Tool | Backend | Purpose |
|---|---|---|
| `list_products` | MCP server (`MCP_SERVER_URL`) | Full product catalog |
| `get_product` | MCP server | Details of one product |
| `get_stock` | Backoffice API (`BACKOFFICE_API_URL`) | Stock quantity per branch |
| `get_branch_stock` | Backoffice API | Full stock of one branch (single call) |

Product data always comes from the external Product API **through the MCP
server** — the AI service never stores product metadata. Stock comes from the
Backoffice API's internal endpoint `/api/stock/product/{id}` (authenticated
with the shared `SERVICE_API_KEY`).

### Grounded answers

The system prompt forbids inventing data: if a tool fails or has no
information, the model must say the information is unavailable. Verified
behaviour:

- `"Which branch has stock of HB-LAP-1001?"` → real branches and quantities.
- `"Where can I buy zzz9?"` → clear "not found" (the MCP/API returns 404).
- If the Backoffice API is down, stock questions answer "stock information
  is currently unavailable".
- If Groq is unreachable or rate-limited, the endpoint returns a clear
  message instead of crashing (errors are caught, never a 500 stack trace).

## Communication: REST, not WebSockets

Each question is **independent** (no conversation history is stored or
required by the project), so a simple `POST /query` request/response fits.
WebSockets would only add value for streaming or live chat, which the scope
does not need — REST keeps the client and server stateless and simple.

## Supported question types

- Product details: *"Tell me about product HB-LAP-1001"*
- Where a product is available: *"Which branch has stock of HB-LAP-1001?"*
- What a branch carries: *"What products can I find in Lyon?"*
- Shopping-list recommendation: *"Can I buy 2 of HB-LAP-1001 and 3 of HB-MON-2101 in one branch?"*

Out-of-scope questions (weather, etc.) get a clear "I can't help with that"
answer.

## Run

```bash
# 1. MCP server (product_mcp_server, port 8002) — see product_mcp_server/
# 2. Backoffice API (api/, port 5000) — see api/README.md
# 3. This service
cd ai_service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
GROQ_API_KEY=gsk_... .venv/bin/uvicorn app.main:app --port 8100
```

Env vars:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — (required) | Groq console key |
| `GROQ_MODEL` | `qwen/qwen3.6-27b` | LLM model (supports tool calling) |
| `MCP_SERVER_URL` | `http://localhost:8002` | Product MCP bridge |
| `BACKOFFICE_API_URL` | `http://localhost:5000` | Backoffice API |
| `SERVICE_API_KEY` | `dev-service-key` | Must match the Backoffice API |

Note: Groq blocks the default Python `urllib` User-Agent (403), so the
client sends a custom `User-Agent` header.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe |
| POST | `/query` | `{"question": "..."}` → `{"answer": "...", "tool_calls": [...]}` |

CORS is open (`*`) so the public client page can call the service from any
origin.
