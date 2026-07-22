"""Tests des modèles Branch, User et Stock."""

from datetime import datetime, timezone
import os
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# La production exige DATABASE_URL. Les tests utilisent leur base isolée.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.database import Base
from app.models import Branch, Stock, User, UserRole


@pytest.fixture
def db() -> Generator[Session, None, None]:
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session


def test_relations_between_branch_user_and_stock(db: Session) -> None:
    branch = Branch(name="Paris")
    branch.users.append(
        User(username="alice", password_hash="hash", role=UserRole.COMMON)
    )
    branch.stocks.append(Stock(external_product_id="product-123", quantity=4))
    db.add(branch)
    db.commit()

    assert branch.users[0].branch is branch
    assert branch.stocks[0].branch is branch
    assert branch.stocks[0].external_product_id == "product-123"


def test_branch_product_pair_is_unique(db: Session) -> None:
    branch = Branch(name="Paris")
    branch.stocks.extend(
        [
            Stock(external_product_id="123", quantity=1),
            Stock(external_product_id="123", quantity=2),
        ]
    )
    db.add(branch)

    with pytest.raises(IntegrityError):
        db.commit()


def test_product_can_exist_in_two_branches(db: Session) -> None:
    db.add_all(
        [
            Branch(
                name="Paris",
                stocks=[Stock(external_product_id="123", quantity=1)],
            ),
            Branch(
                name="Lyon",
                stocks=[Stock(external_product_id="123", quantity=2)],
            ),
        ]
    )
    db.commit()


def test_negative_stock_is_refused(db: Session) -> None:
    branch = Branch(
        name="Paris",
        stocks=[Stock(external_product_id="123", quantity=-1)],
    )
    db.add(branch)

    with pytest.raises(IntegrityError):
        db.commit()


def test_user_soft_delete_and_timestamps(db: Session) -> None:
    user = User(username="admin", password_hash="hash", role=UserRole.ADMIN)
    db.add(user)
    db.commit()

    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.deleted_at is None

    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert user.deleted_at is not None


def test_stock_only_keeps_external_product_id() -> None:
    columns = set(Stock.__table__.columns.keys())
    assert "external_product_id" in columns
    assert "product_name" not in columns
    assert "product_description" not in columns
