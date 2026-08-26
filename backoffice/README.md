# Backoffice (HBntory)

The backoffice is the authenticated internal UI for managing stock and
users. It is split into two parts:

- `frontend/` — the static web UI (vanilla HTML/CSS/JS).
- `nginx.conf` — nginx config that serves the UI and proxies `/api/*` to
  the Backoffice API (`api/`).

## How it is served

In Docker Compose, the `backoffice-web` service (nginx:alpine) mounts
`frontend/` read-only and uses `nginx.conf` to forward all `/api/*`
requests to the `api` service (FastAPI, port 5000). Serving the UI and the
API from the same origin means no CORS configuration is needed.

Open http://localhost:8081.

## Login

`admin` / `admin` (seeded on first boot; override with `ADMIN_PASSWORD`).

- **admin** — manage users (list, create, edit, soft-delete). Cannot manage
  stock.
- **common** — manage stock of their assigned branch only. Cannot manage
  users.

## Files

| File | Role |
|---|---|
| `frontend/index.html` | Screens: login, stock, users |
| `frontend/style.css` | Styling |
| `frontend/app.js` | Calls the API with the JWT, renders the view for the role |
| `nginx.conf` | Static serving + `/api` proxy to the `api` service |

The backend itself lives in `api/` (FastAPI + SQLAlchemy + SQLite) — see
`api/README.md`.
