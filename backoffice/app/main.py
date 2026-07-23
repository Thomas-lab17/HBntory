"""Point d'entrée du Backoffice."""

import os
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.auth import create_auth_router, hash_password
from app.database import Base, SessionLocal, engine
from app.models import Branch, Stock, User, UserRole
from app.routers import products, stock, users


def find_by_username(username: str) -> Optional[User]:
    with SessionLocal() as db:
        return db.scalar(select(User).where(User.username == username))


def find_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as db:
        return db.get(User, user_id)


def seed_demo_data() -> None:
    """Ajoute les données du README une seule fois en développement."""
    if os.getenv("APP_ENV", "development") == "production":
        return

    with SessionLocal() as db:
        paris = db.scalar(select(Branch).where(Branch.name == "Paris"))
        lyon = db.scalar(select(Branch).where(Branch.name == "Lyon"))
        if paris is None:
            paris = Branch(name="Paris")
            db.add(paris)
        if lyon is None:
            lyon = Branch(name="Lyon")
            db.add(lyon)
        db.flush()

        if db.scalar(select(User).where(User.username == "admin")) is None:
            db.add(
                User(
                    username="admin",
                    password_hash=hash_password(
                        os.getenv("DEMO_ADMIN_PASSWORD", "admin")
                    ),
                    role=UserRole.ADMIN,
                )
            )

        if db.scalar(select(User).where(User.username == "personne1")) is None:
            db.add(
                User(
                    username="personne1",
                    password_hash=hash_password(
                        os.getenv("DEMO_COMMON_PASSWORD", "common")
                    ),
                    role=UserRole.COMMON,
                    branch=paris,
                )
            )

        stock_exists = db.scalar(
            select(Stock).where(
                Stock.branch_id == paris.id,
                Stock.external_product_id == "123",
            )
        )
        if stock_exists is None:
            db.add(
                Stock(
                    branch=paris,
                    external_product_id="123",
                    quantity=10,
                )
            )
        db.commit()


app = FastAPI(title="HBntory Backoffice API", version="0.1.0")
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


@app.on_event("startup")
def create_tables() -> None:
    """Crée les tables au démarrage."""
    Base.metadata.create_all(bind=engine)
    seed_demo_data()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "backoffice"}

# modifier selon arborescence locale
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="backoffice")
