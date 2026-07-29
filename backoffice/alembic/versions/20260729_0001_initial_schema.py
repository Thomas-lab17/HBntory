"""Création du schéma initial du Backoffice.

Revision ID: 20260729_0001
Revises:
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names() -> set[str]:
    """Retourne les tables déjà présentes pour préserver une base existante."""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Crée les tables absentes et adopte sans perte un schéma déjà initialisé."""
    tables = _table_names()

    if "branches" not in tables:
        op.create_table(
            "branches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column(
                "role",
                sa.Enum(
                    "admin",
                    "common",
                    name="user_role",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column("branch_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(
                ["branch_id"],
                ["branches.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_username", "users", ["username"], unique=True)

    if "stocks" not in tables:
        op.create_table(
            "stocks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=False),
            sa.Column("external_product_id", sa.String(length=255), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "quantity >= 0",
                name="ck_stock_quantity_non_negative",
            ),
            sa.ForeignKeyConstraint(
                ["branch_id"],
                ["branches.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "branch_id",
                "external_product_id",
                name="uq_stock_branch_product",
            ),
        )


def downgrade() -> None:
    """Supprime le schéma initial dans l’ordre inverse des dépendances."""
    tables = _table_names()
    if "stocks" in tables:
        op.drop_table("stocks")
    if "users" in tables:
        op.drop_table("users")
    if "branches" in tables:
        op.drop_table("branches")
