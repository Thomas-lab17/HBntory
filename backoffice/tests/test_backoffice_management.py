"""Tests des améliorations de gestion du Backoffice."""

import os
from types import SimpleNamespace
from typing import Generator

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.models import Base, Branch, Stock, User, UserRole
from app.routers import branches as branch_router
from app.routers import stock as stock_router
from app.routers import users as user_router


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def admin_user():
    return SimpleNamespace(role=UserRole.ADMIN)


def common_user(branch_id: int):
    return SimpleNamespace(role=UserRole.COMMON, branch_id=branch_id)


def test_branch_names_are_normalized_and_unique(db: Session) -> None:
    created = branch_router.create_branch(
        branch_router.BranchPayload(name="  Bordeaux   Centre "),
        admin=admin_user(),
        db=db,
    )
    assert created.name == "Bordeaux Centre"

    with pytest.raises(HTTPException) as error:
        branch_router.create_branch(
            branch_router.BranchPayload(name="bordeaux centre"),
            admin=admin_user(),
            db=db,
        )
    assert error.value.status_code == 409


def test_branch_in_use_cannot_be_deleted(db: Session) -> None:
    branch = Branch(name="Nantes")
    branch.users.append(
        User(
            username="nantes-user",
            password_hash="hash",
            role=UserRole.COMMON,
        )
    )
    db.add(branch)
    db.commit()

    with pytest.raises(HTTPException) as error:
        branch_router.delete_branch(branch.id, admin=admin_user(), db=db)
    assert error.value.status_code == 409


def test_user_response_contains_branch_name(db: Session) -> None:
    branch = Branch(name="Marseille")
    db.add(branch)
    db.commit()

    user = user_router.create_user(
        user_router.CreateUserRequest(
            username="Marseille_User",
            password="Solide123!",
            branch_id=branch.id,
        ),
        admin=admin_user(),
        db=db,
    )
    assert user.username == "marseille_user"
    assert user.branch_name == "Marseille"


def test_weak_password_is_rejected() -> None:
    with pytest.raises(ValidationError):
        user_router.CreateUserRequest(
            username="utilisateur",
            password="trop-simple",
            branch_id=1,
        )


def test_repeated_add_uses_one_stock_row(db: Session, monkeypatch) -> None:
    branch = Branch(name="Lille")
    db.add(branch)
    db.commit()
    monkeypatch.setattr(
        stock_router,
        "get_product",
        lambda identifier: {"id": 42, "name": "Produit unique"},
    )

    for quantity in (2, 3):
        stock_router.add_stock(
            stock_router.StockAction(
                external_product_id="42",
                quantity=quantity,
            ),
            user=common_user(branch.id),
            db=db,
        )

    rows = db.query(Stock).all()
    assert len(rows) == 1
    assert rows[0].quantity == 5
