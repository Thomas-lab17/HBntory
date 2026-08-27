# HBntory — Client Web

Public web interface of the HBntory project: a page where **anonymous**
visitors ask natural-language questions about products and stock. No login,
no history: each question is independent.

## Current state

The page is **connected to the AI Query Service** (`ai_service`, port
8100). Submitting a question sends `POST /query` and displays the answer in
the conversation, with loading feedback (`…`) while waiting and a clear
error message if the service fails.

No dependencies, no build: vanilla HTML + CSS + JavaScript.

## Files

| File | Role |
|---|---|
| `index.html` | Page structure: header, conversation (`#messages`), question form (`#question-form`) |
| `style.css` | Minimal styling (user / assistant bubbles, error banner) |
| `app.js` | Submits the question to `http://localhost:8100/query`, renders the answer or an error |

## Run

Via Docker Compose (from the project root):

```bash
docker compose up --build
# then open http://localhost:8080
```

The `client_web` service serves the static files with nginx
(`./client_web` mounted read-only).

## How it works

1. The visitor types a question and submits it.
2. `app.js` adds the question as a user bubble and disables the form.
3. It sends `POST http://localhost:8100/query` with `{"question": "..."}`.
4. The answer is displayed as an assistant bubble; on failure the error is
   shown in place.

Each question is handled independently; nothing is stored (neither on the
page nor on the server). Reloading the page resets the conversation.

## Example questions

- "Give me details about product HB-LAP-1001"
- "Which branch has stock of HB-LAP-1001?"
- "What products can I find in Lyon?"
- "Can I buy 2 of HB-LAP-1001 and 3 of HB-MON-2101 in one branch?"

The AI service answers using real product data (external Product API via
the MCP server) and real stock data (Backoffice API), and never invents
information.

## Relations

```text
Anonymous visitor
    │  (browser)
    ▼
client_web/  (static page, no own server)
    │  POST /query
    ▼
ai_service  (independent of the Backoffice)
    ├─ products: external Product API via product_mcp_server
    └─ stock: Backoffice API (internal endpoint)
```

The client web shares no code with the Backoffice and does not contact it
directly.
