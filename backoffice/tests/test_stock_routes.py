"""Tests des routes de stock réservées aux utilisateurs common."""

import os
from types import SimpleNamespace
from typing import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Les tests de routes utilisent une base SQLite isolée.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.dependencies import get_current_common
from app.models import Base, Branch, Stock, UserRole
from app.product_api import ProductAPIUnavailable, ProductNotFound
from app.routers import stock as stock_router


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Branch(id=1, name="Paris"), Branch(id=2, name="Lyon")])
        session.commit()
        yield session


def common_user(branch_id: int = 1):
    return SimpleNamespace(role=UserRole.COMMON, branch_id=branch_id)


def test_common_user_only_sees_own_branch(db: Session) -> None:
    db.add_all(
        [
            Stock(branch_id=1, external_product_id="1", quantity=4),
            Stock(branch_id=2, external_product_id="2", quantity=9),
        ]
    )
    db.commit()

    result = stock_router.list_stock(user=common_user(1), db=db)

    assert [(item.external_product_id, item.quantity) for item in result] == [
        ("1", 4)
    ]


def test_add_stock_validates_and_canonicalizes_product(
    db: Session, monkeypatch
) -> None:
    monkeypatch.setattr(
        stock_router,
        "get_product",
        lambda identifier: {
            "id": 6,
            "sku": "HB-KBD-4101",
            "name": "Mechanical Keyboard EN",
        },
    )

    result = stock_router.add_stock(
        action=stock_router.StockAction(
            external_product_id="HB-KBD-4101",
            quantity=3,
        ),
        user=common_user(1),
        db=db,
    )

    assert result.external_product_id == "6"
    assert result.quantity == 3


def test_unknown_product_does_not_modify_stock(
    db: Session, monkeypatch
) -> None:
    def unknown_product(identifier):
        raise ProductNotFound("Produit inconnu")

    monkeypatch.setattr(stock_router, "get_product", unknown_product)

    with pytest.raises(HTTPException) as error:
        stock_router.add_stock(
            action=stock_router.StockAction(
                external_product_id="UNKNOWN",
                quantity=3,
            ),
            user=common_user(1),
            db=db,
        )

    assert error.value.status_code == 404
    assert db.query(Stock).count() == 0


def test_unavailable_product_api_does_not_modify_stock(
    db: Session, monkeypatch
) -> None:
    def unavailable_api(identifier):
        raise ProductAPIUnavailable("API indisponible")

    monkeypatch.setattr(stock_router, "get_product", unavailable_api)

    with pytest.raises(HTTPException) as error:
        stock_router.add_stock(
            action=stock_router.StockAction(
                external_product_id="1",
                quantity=3,
            ),
            user=common_user(1),
            db=db,
        )

    assert error.value.status_code == 503
    assert db.query(Stock).count() == 0


def test_remove_stock_remains_local(db: Session) -> None:
    db.add(Stock(branch_id=1, external_product_id="123", quantity=5))
    db.commit()

    result = stock_router.remove_stock(
        action=stock_router.StockAction(
            external_product_id="123",
            quantity=2,
        ),
        user=common_user(1),
        db=db,
    )

    assert result.quantity == 3


def test_update_stock_sets_exact_quantity(db: Session) -> None:
    db.add(Stock(branch_id=1, external_product_id="123", quantity=5))
    db.commit()

    result = stock_router.update_stock(
        action=stock_router.StockUpdate(
            external_product_id="123",
            quantity=8,
        ),
        user=common_user(1),
        db=db,
    )

    assert result.quantity == 8
    assert db.query(Stock).filter_by(branch_id=1, external_product_id="123").one().quantity == 8


def test_update_stock_to_zero_keeps_product_in_stock_sheet(db: Session) -> None:
    db.add(Stock(branch_id=1, external_product_id="123", quantity=5))
    db.commit()

    result = stock_router.update_stock(
        action=stock_router.StockUpdate(
            external_product_id="123",
            quantity=0,
        ),
        user=common_user(1),
        db=db,
    )

    assert result.quantity == 0
    assert db.query(Stock).filter_by(branch_id=1, external_product_id="123").one().quantity == 0


def test_list_stock_keeps_empty_rows(db: Session) -> None:
    db.add_all(
        [
            Stock(branch_id=1, external_product_id="empty", quantity=0),
            Stock(branch_id=1, external_product_id="available", quantity=2),
        ]
    )
    db.commit()

    result = stock_router.list_stock(user=common_user(1), db=db)

    assert [item.external_product_id for item in result] == ["available", "empty"]


def test_delete_empty_stock_removes_row(db: Session) -> None:
    db.add(Stock(branch_id=1, external_product_id="empty", quantity=0))
    db.commit()

    response = stock_router.delete_empty_stock(
        external_product_id="empty",
        user=common_user(1),
        db=db,
    )

    assert response.status_code == 204
    assert db.query(Stock).filter_by(branch_id=1, external_product_id="empty").count() == 0


def test_delete_stock_with_quantity_is_refused(db: Session) -> None:
    db.add(Stock(branch_id=1, external_product_id="available", quantity=2))
    db.commit()

    with pytest.raises(HTTPException) as error:
        stock_router.delete_empty_stock(
            external_product_id="available",
            user=common_user(1),
            db=db,
        )

    assert error.value.status_code == 409


def test_admin_cannot_use_common_dependency() -> None:
    with pytest.raises(HTTPException) as error:
        get_current_common(
            SimpleNamespace(role=UserRole.ADMIN, branch_id=None)
        )

    assert error.value.status_code == 403


def test_common_without_branch_is_refused() -> None:
    with pytest.raises(HTTPException) as error:
        get_current_common(
            SimpleNamespace(role=UserRole.COMMON, branch_id=None)
        )

    assert error.value.status_code == 403
