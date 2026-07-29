"""Tests du jeu de données de démonstration."""

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.models import Base, Branch, Stock, User, UserRole
from app.seed import (
    DEMO_BRANCH_USERS,
    DEMO_PRODUCT_IDS,
    LIMITED_STOCK_BRANCH,
    LIMITED_STOCK_PRODUCT_IDS,
    demo_product_ids_for_branch,
    seed_demo_data,
)


def test_seed_is_complete_and_idempotent(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("DEMO_COMMON_PASSWORD", "Common123!")

    seed_demo_data(
        session_factory=session_factory,
        password_hasher=lambda password: f"hash:{password}",
    )

    with Session(engine) as db:
        assert db.query(Branch).count() == len(DEMO_BRANCH_USERS)
        assert db.query(User).count() == len(DEMO_BRANCH_USERS) + 1
        demo_usernames = {
            username for _, username in DEMO_BRANCH_USERS
        }
        assert demo_usernames.issubset(
            set(db.scalars(select(User.username)).all())
        )
        assert db.query(Stock).count() == sum(
            len(demo_product_ids_for_branch(branch_name))
            for branch_name, _ in DEMO_BRANCH_USERS
        )

        paris = db.scalar(select(Branch).where(Branch.name == "Paris"))
        assert paris is not None
        paris_stocks = db.scalars(
            select(Stock).where(Stock.branch_id == paris.id)
        ).all()
        assert {stock.external_product_id for stock in paris_stocks} == set(
            DEMO_PRODUCT_IDS
        )
        assert any(stock.quantity == 0 for stock in paris_stocks)
        assert any(0 < stock.quantity < 5 for stock in paris_stocks)
        assert any(stock.quantity >= 5 for stock in paris_stocks)

        limited_branch = db.scalar(
            select(Branch).where(Branch.name == LIMITED_STOCK_BRANCH)
        )
        assert limited_branch is not None
        limited_stocks = db.scalars(
            select(Stock).where(Stock.branch_id == limited_branch.id)
        ).all()
        assert {stock.external_product_id for stock in limited_stocks} == set(
            LIMITED_STOCK_PRODUCT_IDS
        )

        modified_stock = db.scalar(
            select(Stock).where(
                Stock.branch_id == paris.id,
                Stock.external_product_id == "1",
            )
        )
        assert modified_stock is not None
        modified_stock.quantity = 99
        db.commit()

    seed_demo_data(
        session_factory=session_factory,
        password_hasher=lambda password: f"hash:{password}",
    )

    with Session(engine) as db:
        assert db.query(Branch).count() == len(DEMO_BRANCH_USERS)
        assert db.query(User).count() == len(DEMO_BRANCH_USERS) + 1
        assert db.query(Stock).count() == sum(
            len(demo_product_ids_for_branch(branch_name))
            for branch_name, _ in DEMO_BRANCH_USERS
        )
        paris = db.scalar(select(Branch).where(Branch.name == "Paris"))
        modified_stock = db.scalar(
            select(Stock).where(
                Stock.branch_id == paris.id,
                Stock.external_product_id == "1",
            )
        )
        assert modified_stock.quantity == 99


def test_seed_can_be_disabled(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SEED_DEMO_DATA", "false")

    seed_demo_data(
        session_factory=session_factory,
        password_hasher=lambda password: f"hash:{password}",
    )

    with Session(engine) as db:
        assert db.query(Branch).count() == 0


def test_seed_migrates_legacy_users_with_autoflush_disabled(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("DEMO_COMMON_PASSWORD", "Common123!")

    with session_factory() as db:
        branches = []
        for branch_name, _ in DEMO_BRANCH_USERS:
            branch = Branch(name=branch_name)
            db.add(branch)
            branches.append(branch)
        db.flush()
        for index, branch in enumerate(branches, start=1):
            db.add(
                User(
                    username=f"personne{index}",
                    password_hash="hash:legacy",
                    role=UserRole.COMMON,
                    branch=branch,
                )
            )
        db.commit()

    seed_demo_data(
        session_factory=session_factory,
        password_hasher=lambda password: f"hash:{password}",
    )

    with Session(engine) as db:
        common_users = db.scalars(
            select(User).where(User.role == UserRole.COMMON)
        ).all()
        assert len(common_users) == len(DEMO_BRANCH_USERS)
        assert {user.username for user in common_users} == {
            username for _, username in DEMO_BRANCH_USERS
        }
        assert {user.password_hash for user in common_users} == {"hash:Common123!"}


def test_seed_upgrades_previous_default_password(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SEED_DEMO_DATA", "true")
    monkeypatch.setenv("DEMO_COMMON_PASSWORD", "common")

    fake_hasher = lambda password: f"hash:{password}"
    fake_verifier = lambda password, password_hash: (
        password_hash == f"hash:{password}"
    )
    seed_demo_data(
        session_factory=session_factory,
        password_hasher=fake_hasher,
        password_verifier=fake_verifier,
    )

    monkeypatch.setenv("DEMO_COMMON_PASSWORD", "Common123!")
    seed_demo_data(
        session_factory=session_factory,
        password_hasher=fake_hasher,
        password_verifier=fake_verifier,
    )

    with Session(engine) as db:
        password_hashes = set(
            db.scalars(
                select(User.password_hash).where(User.role == UserRole.COMMON)
            ).all()
        )
        assert password_hashes == {"hash:Common123!"}
