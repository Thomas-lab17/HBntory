"""Gestion des agences réservée aux administrateurs."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Branch, Stock, User


router = APIRouter(prefix="/branches", tags=["branches"])


class BranchPayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Le nom de l’agence doit contenir au moins 2 caractères.")
        return normalized


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    user_count: int
    stock_count: int


def _branch_response(db: Session, branch: Branch) -> BranchResponse:
    user_count = db.scalar(
        select(func.count(User.id)).where(
            User.branch_id == branch.id,
            User.deleted_at.is_(None),
        )
    )
    stock_count = db.scalar(
        select(func.count(Stock.id)).where(Stock.branch_id == branch.id)
    )
    return BranchResponse(
        id=branch.id,
        name=branch.name,
        user_count=user_count or 0,
        stock_count=stock_count or 0,
    )


def _find_by_name(db: Session, name: str) -> Optional[Branch]:
    return db.scalar(
        select(Branch).where(func.lower(Branch.name) == name.casefold())
    )


@router.get("/", response_model=list[BranchResponse])
def list_branches(
    search: Annotated[Optional[str], Query(max_length=120)] = None,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Liste les agences par ordre alphabétique."""
    statement = select(Branch)
    if search:
        statement = statement.where(Branch.name.ilike(f"%{search.strip()}%"))
    branches = db.scalars(statement.order_by(Branch.name)).all()
    return [_branch_response(db, branch) for branch in branches]


@router.post(
    "/",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_branch(
    payload: BranchPayload,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Crée une agence au nom unique sans tenir compte de la casse."""
    if _find_by_name(db, payload.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une agence porte déjà ce nom.",
        )

    branch = Branch(name=payload.name)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return _branch_response(db, branch)


@router.patch("/{branch_id}", response_model=BranchResponse)
def rename_branch(
    branch_id: int,
    payload: BranchPayload,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Renomme une agence."""
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Agence introuvable.")

    existing = _find_by_name(db, payload.name)
    if existing is not None and existing.id != branch.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une agence porte déjà ce nom.",
        )

    branch.name = payload.name
    db.commit()
    db.refresh(branch)
    return _branch_response(db, branch)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch(
    branch_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Supprime uniquement une agence vide."""
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Agence introuvable.")

    usage = _branch_response(db, branch)
    if usage.user_count or usage.stock_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cette agence contient encore des utilisateurs ou du stock. "
                "Réaffectez-les avant de la supprimer."
            ),
        )

    db.delete(branch)
    db.commit()
