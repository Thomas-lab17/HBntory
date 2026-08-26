# Backoffice API (HBntory)

SQLAlchemy-backed Backoffice API for HBntory. Route contract mirrors Thomas's
Flask backoffice (`/api/*`), so the frontend works against this service
unchanged. Product data is never stored locally — it comes from the external
Product API through Tom's MCP server.

## Run

```bash
cd api
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.init_db          # seed admin + branches + stock
.venv/bin/uvicorn app.main:app --port 5000
```

Env vars: `SECRET_KEY` (JWT signing, default `dev-secret-key`),
`SERVICE_API_KEY` (internal endpoints, default `dev-service-key`),
`MCP_SERVER_URL` (default `http://localhost:8002`).

Default credentials after init: `admin` / `admin` (override via
`ADMIN_PASSWORD` env when running `init_db`).

## Endpoints

| Method | Path | Access |
|---|---|---|
| POST | `/api/login` | public — returns Bearer token |
| GET | `/api/me` | any authenticated user |
| GET | `/api/branches` | any authenticated user |
| GET | `/api/stock` | common user — their branch only |
| POST | `/api/stock/add` | common user — their branch |
| POST | `/api/stock/remove` | common user — their branch |
| GET | `/api/users` | admin |
| POST | `/api/users` | admin — creates common users |
| PATCH | `/api/users/{id}` | admin |
| DELETE | `/api/users/{id}` | admin — soft delete |
| GET | `/api/products` | any authenticated user — via MCP bridge |
| GET | `/api/products/{id}` | any authenticated user — via MCP bridge |
| GET | `/api/stock/product/{id}` | `X-API-Key: SERVICE_API_KEY` — internal, used by the AI service |

## Design notes

- Password hashing: werkzeug scrypt (never plain text; plain SHA256 would be
  fast to brute-force — scrypt is slow and salted).
- Auth: JWT HS256, 12h expiry; the user's branch always comes from the token,
  never from the client. Soft-deleted users are rejected on every request.
- Authorization is enforced in the backend (role guards), not in the UI.
- Stock quantity can never go negative (DB CHECK constraint + service checks).
