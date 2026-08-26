# Backoffice API (HBntory)

SQLAlchemy-backed Backoffice API. It provides authentication, stock
management (common users) and user management (admin) over a **real
relational database**. The route contract mirrors Thomas's Flask backoffice
(`/api/*`), so the backoffice frontend works against this service unchanged.

Product data is **never stored locally** — it comes from the external
Product API through Tom's MCP server.

## Architecture

```
Browser (Thomas's frontend)
   │  /api/* JSON + Bearer token
   ▼
┌───────────────────────┐   SQLAlchemy   ┌──────────────┐
│  Backoffice API       │ ─────────────► │  SQLite DB   │
│  (app/main.py)        │                │ users/branch │
│  JWT auth + role      │                │ es/stocks    │
│  guards               │                └──────────────┘
└──────────┬────────────┘
           │ product info (list/detail)
           ▼
   Tom's MCP server ──► external Product API
```

Two kinds of client talk to this service:

- **The backoffice frontend** (Thomas's) — authenticated users.
- **The AI Query Service** (your `ai` branch) — internal read-only stock
  queries with a shared service key.

## How it works

### Authentication and authorization (`app/security.py`, `app/deps.py`)

- `POST /api/login` verifies the password against its stored hash and
  returns a signed **JWT** (HS256, 12h expiry).
- Every protected request re-reads the user from the DB: a soft-deleted
  user's token stops working immediately, and the user's **branch always
  comes from the token**, never from client input.
- Role guards enforce the rules in the backend, not just in the UI:
  - `require_admin` — user management routes only.
  - `require_common` — stock routes only, scoped to the user's branch.

**Password hashing:** werkzeug's scrypt (salted, slow by design). A general
hash like plain SHA256 is unsuitable because it is fast to brute-force;
scrypt is deliberately expensive, making offline password cracking
impractical.

### Stock management

- Common users add/remove/list stock **only for their assigned branch**;
  the branch id is read from the token.
- Rules enforced by both the API and the DB:
  - quantity must be a positive integer,
  - stock can never go below zero (`CHECK (quantity >= 0)` in the schema),
  - one row per (branch, product) — adding to an existing product merges.

### Product data

`GET /api/products` and `GET /api/products/{id}` proxy to **Tom's MCP
server**, which bridges the external Product API. The local database only
stores `product_id` strings — never names, prices, or descriptions.

### Internal endpoint for the AI service

`GET /api/stock/product/{id}` returns stock of a product **across all
branches** (read-only). It is guarded by the `X-API-Key` header
(`SERVICE_API_KEY`), so only the AI service can call it. If a product is
unknown to the external API it returns `not_found`, so the AI can
distinguish "no stock anywhere" from "no such product".

## Database schema (`app/models.py`)

| Table | Columns | Rules |
|---|---|---|
| `users` | id, username (unique), password_hash, role, branch_id, is_deleted, timestamps | common users must have a branch (CHECK); admin has none |
| `branches` | id, name (unique), address, timestamps | — |
| `stocks` | id, branch_id (FK), product_id, quantity, timestamps | quantity ≥ 0 (CHECK); unique (branch, product) |

Soft delete: users keep their row with `is_deleted = True`; they can no
longer log in, and existing stock is untouched.

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
Default credentials after init: `admin` / `admin` (override with
`ADMIN_PASSWORD` when running `init_db`).

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
| POST | `/api/users` | admin — creates common users (role forced) |
| PATCH | `/api/users/{id}` | admin |
| DELETE | `/api/users/{id}` | admin — soft delete |
| GET | `/api/products` | any authenticated user — via MCP bridge |
| GET | `/api/products/{id}` | any authenticated user — via MCP bridge |
| GET | `/api/stock/product/{id}` | `X-API-Key: SERVICE_API_KEY` — internal, for the AI service |

## Design decisions

- **FastAPI + SQLAlchemy**: the project mandates SQLAlchemy; SQLite for
  development, easy switch to Postgres (only `DATABASE_URL` changes).
- **JWT over server sessions**: stateless, fits the JSON API, expiry
  enforced client-side; revocation handled by re-checking the user in the
  DB on every request.
- **Product info via the MCP bridge** instead of a second direct client:
  one integration point for the external Product API (Tom's), reused by
  both the backoffice and the AI service.
