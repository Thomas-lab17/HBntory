"""Point d'entrée du Backoffice."""

import os
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.auth import create_auth_router
from app.database import SessionLocal
from app.models import User
from app.routers import branches, internal, products, stock, users


def find_by_username(username: str) -> Optional[User]:
    with SessionLocal() as db:
        return db.scalar(
            select(User)
            .options(joinedload(User.branch))
            .where(User.username == username)
        )


def find_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as db:
        return db.scalar(
            select(User)
            .options(joinedload(User.branch))
            .where(User.id == user_id)
        )


app = FastAPI(title="HBntory Backoffice API", version="0.1.0")


@app.middleware("http")
async def disable_frontend_cache_in_development(request: Request, call_next):
    """Évite de conserver d'anciens assets pendant les itérations locales."""
    response = await call_next(request)
    is_frontend_asset = (
        request.url.path == "/"
        or request.url.path.endswith((".html", ".css", ".js"))
    )
    if os.getenv("APP_ENV", "development") != "production" and is_frontend_asset:
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


app.include_router(
    create_auth_router(
        find_by_username,
        find_by_id,
        expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "30")),
    )
)

app.include_router(products.router)
app.include_router(stock.router)
app.include_router(users.router)
app.include_router(branches.router)
app.include_router(internal.router)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "backoffice"}

# modifier selon arborescence locale
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="backoffice")
