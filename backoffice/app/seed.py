"""Jeu de données de démonstration pour l'environnement de développement."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from sqlalchemy import select

from app.auth import hash_password, verify_password
from app.database import SessionLocal
from app.models import Branch, Stock, User, UserRole


# Les identifiants correspondent au catalogue livré avec Product API.
# Le produit 32 est volontairement absent : il est marqué comme discontinued.
DEMO_PRODUCT_IDS = tuple(str(product_id) for product_id in range(1, 41) if product_id != 32)

# Des identités réalistes rendent les écrans de démonstration plus naturels.
DEMO_BRANCH_USERS = (
    ("Paris", "camille.martin"),
    ("Lyon", "thomas.bernard"),
    ("Bordeaux", "lea.dubois"),
    ("Lille", "hugo.robert"),
    ("Nantes", "chloe.richard"),
    ("Toulouse", "nathan.petit"),
    ("Marseille", "ines.durand"),
    ("Nice", "louis.moreau"),
    ("Rennes", "emma.simon"),
    ("Strasbourg", "gabriel.laurent"),
    ("Annecy", "manon.rousseau"),
)

LIMITED_STOCK_BRANCH = "Annecy"
LIMITED_STOCK_PRODUCT_IDS = DEMO_PRODUCT_IDS[:7]


def demo_product_ids_for_branch(branch_name: str) -> tuple[str, ...]:
    """Retourne un assortiment réduit pour l'agence de démonstration Annecy."""
    if branch_name == LIMITED_STOCK_BRANCH:
        return LIMITED_STOCK_PRODUCT_IDS
    return DEMO_PRODUCT_IDS


def demo_quantity(branch_index: int, product_id: str) -> int:
    """Retourne une quantité déterministe incluant ruptures et stocks faibles."""
    marker = (int(product_id) + branch_index * 3) % 12
    if marker == 0:
        return 0
    if marker <= 4:
        return marker
    return 8 + ((int(product_id) * 7 + branch_index * 11) % 64)


def _seed_user(
    db: Any,
    *,
    username: str,
    password: str,
    role: UserRole,
    password_hasher: Callable[[str], str],
    branch: Branch | None = None,
) -> None:
    """Crée un compte manquant sans écraser un compte existant."""
    if db.scalar(select(User).where(User.username == username)) is not None:
        return
    db.add(
        User(
            username=username,
            password_hash=password_hasher(password),
            role=role,
            branch=branch,
        )
    )


def seed_demo_data(
    *,
    session_factory: Callable[[], Any] = SessionLocal,
    password_hasher: Callable[[str], str] = hash_password,
    password_verifier: Callable[[str, str], bool] = verify_password,
) -> None:
    """Crée un catalogue de démo complet sans réinitialiser les données existantes.

    L'opération est additive et idempotente : les agences, comptes et lignes de
    stock déjà présents restent inchangés. Cela permet de relancer le service
    sans perdre les ajustements de stock réalisés dans l'interface.
    """
    if os.getenv("APP_ENV", "development") == "production":
        return
    if os.getenv("SEED_DEMO_DATA", "true").lower() in {"0", "false", "no"}:
        return

    admin_password = os.getenv("DEMO_ADMIN_PASSWORD", "Admin123!")
    common_password = os.getenv("DEMO_COMMON_PASSWORD", "Common123!")

    with session_factory() as db:
        branches_by_name = {
            branch.name: branch
            for branch in db.scalars(
                select(Branch).where(
                    Branch.name.in_([name for name, _ in DEMO_BRANCH_USERS])
                )
            )
        }

        for branch_name, _ in DEMO_BRANCH_USERS:
            if branch_name not in branches_by_name:
                branch = Branch(name=branch_name)
                db.add(branch)
                branches_by_name[branch_name] = branch
        db.flush()

        _seed_user(
            db,
            username="admin",
            password=admin_password,
            role=UserRole.ADMIN,
            password_hasher=password_hasher,
        )

        # Migre les anciens comptes personne1…personne10 vers les nouveaux noms
        # sans créer de doublons dans une base de démonstration existante.
        for legacy_index, (_, username) in enumerate(DEMO_BRANCH_USERS, start=1):
            existing_user = db.scalar(
                select(User).where(User.username == username)
            )
            if existing_user is not None:
                continue
            legacy_user = db.scalar(
                select(User).where(User.username == f"personne{legacy_index}")
            )
            if legacy_user is not None:
                legacy_user.username = username
                legacy_user.password_hash = password_hasher(common_password)

        # SessionLocal désactive l'autoflush : synchroniser les renommages avant
        # que _seed_user vérifie si les nouveaux identifiants existent.
        db.flush()

        # Migre uniquement l'ancien mot de passe de démonstration par défaut.
        # Un mot de passe personnalisé par l'utilisateur reste inchangé.
        if common_password != "common":
            for _, username in DEMO_BRANCH_USERS:
                existing_user = db.scalar(
                    select(User).where(User.username == username)
                )
                if (
                    existing_user is not None
                    and password_verifier("common", existing_user.password_hash)
                ):
                    existing_user.password_hash = password_hasher(common_password)

        for branch_name, username in DEMO_BRANCH_USERS:
            _seed_user(
                db,
                username=username,
                password=common_password,
                role=UserRole.COMMON,
                branch=branches_by_name[branch_name],
                password_hasher=password_hasher,
            )

        existing_stock_keys = {
            (branch_id, external_product_id)
            for branch_id, external_product_id in db.execute(
                select(Stock.branch_id, Stock.external_product_id).where(
                    Stock.branch_id.in_(
                        [branch.id for branch in branches_by_name.values()]
                    )
                )
            )
        }
        for branch_index, (branch_name, _) in enumerate(DEMO_BRANCH_USERS):
            branch = branches_by_name[branch_name]
            for product_id in demo_product_ids_for_branch(branch_name):
                stock_key = (branch.id, product_id)
                if stock_key in existing_stock_keys:
                    continue
                db.add(
                    Stock(
                        branch=branch,
                        external_product_id=product_id,
                        quantity=demo_quantity(branch_index, product_id),
                    )
                )

        db.commit()
