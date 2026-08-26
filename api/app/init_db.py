# Initialize the Backoffice database: tables + seed data.
# Run with: python -m app.init_db  (from api/)
# Admin password comes from env ADMIN_PASSWORD (default "admin" for dev only).
import os

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .database import Base, SessionLocal, engine
from .models import Branch, ROLE_ADMIN, Stock, User

ADMIN_USERNAME = "admin"
SAMPLE_BRANCHES = [
    {"name": "Paris", "address": "12 Rue de Rivoli"},
    {"name": "Lyon", "address": "4 Place Bellecour"},
]
# Sample stock keyed by branch name -> {product_id: quantity}.
# Product ids are SKUs from the external Product API catalog (e.g. HB-LAP-1001).
SAMPLE_STOCK = {
    "Paris": {"HB-LAP-1001": 10, "HB-KBD-4101": 5},
    "Lyon": {"HB-LAP-1001": 7, "HB-MON-2101": 12},
}


def seed_if_missing(session) -> None:
    """Create admin, branches, and sample stock only when absent (idempotent)."""
    if session.scalar(select(User).where(User.username == ADMIN_USERNAME)) is None:
        admin_pw = os.environ.get("ADMIN_PASSWORD", "admin")
        session.add(
            User(
                username=ADMIN_USERNAME,
                password_hash=generate_password_hash(admin_pw),
                role=ROLE_ADMIN,
            )
        )

    branches = {}
    for spec in SAMPLE_BRANCHES:
        branch = session.scalar(select(Branch).where(Branch.name == spec["name"]))
        if branch is None:
            branch = Branch(name=spec["name"], address=spec["address"])
            session.add(branch)
            session.flush()
        branches[branch.name] = branch

    for name, items in SAMPLE_STOCK.items():
        for product_id, qty in items.items():
            exists = session.scalar(
                select(Stock).where(
                    Stock.branch_id == branches[name].id,
                    Stock.product_id == product_id,
                )
            )
            if exists is None:
                session.add(
                    Stock(branch_id=branches[name].id, product_id=product_id, quantity=qty)
                )

    session.commit()


def main() -> None:
    """Create tables and seed initial data."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_if_missing(session)
    print("Database initialized: admin user, branches, sample stock.")


if __name__ == "__main__":
    main()
