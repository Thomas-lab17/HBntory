# SQLAlchemy models for the HBntory Backoffice database.
# Stores local data only: users, branches, stock by external product id.
# Product details (names, prices, ...) are never stored here; they come
# from the external Product API (via Tom's MCP server).
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base

ROLE_ADMIN = "admin"
ROLE_COMMON = "common"  # common user


class TimestampMixin:
    """Adds created_at / updated_at columns to a model."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class Branch(TimestampMixin, Base):
    """A physical retail branch; owns its own stock."""

    __tablename__ = "branches"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    address = Column(String(200), nullable=True)

    users = relationship("User", back_populates="branch")
    stock_items = relationship("Stock", back_populates="branch")


class User(TimestampMixin, Base):
    """A Backoffice user. role is 'admin' or 'common' (common user).
    Common users must belong to exactly one branch; the admin has none.
    Soft-deleted users keep their row (is_deleted=True) and cannot log in."""

    __tablename__ = "users"
    __table_args__ = (
        # A common user must be assigned to a branch; the admin is exempt.
        CheckConstraint(
            "(role != 'common') OR (branch_id IS NOT NULL)",
            name="ck_user_branch_required_for_common",
        ),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # werkzeug hash, never plain text
    role = Column(String(20), nullable=False, default=ROLE_COMMON)
    branch_id = Column(ForeignKey("branches.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)

    branch = relationship("Branch", back_populates="users")

    @property
    def is_admin(self) -> bool:
        """True for the single administrator account."""
        return self.role == ROLE_ADMIN


class Stock(TimestampMixin, Base):
    """Quantity of an external product held by one branch."""

    __tablename__ = "stocks"
    __table_args__ = (
        # One row per (branch, product).
        UniqueConstraint("branch_id", "product_id", name="uq_stock_branch_product"),
        # Stock quantity must never be negative — enforced by the DB.
        CheckConstraint("quantity >= 0", name="ck_stock_quantity_non_negative"),
    )

    id = Column(Integer, primary_key=True)
    branch_id = Column(ForeignKey("branches.id"), nullable=False)
    product_id = Column(String(80), nullable=False, index=True)
    quantity = Column(Integer, default=0, nullable=False)

    branch = relationship("Branch", back_populates="stock_items")
