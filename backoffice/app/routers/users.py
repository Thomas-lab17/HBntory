"""Gestion des utilisateurs réservée aux administrateurs."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth import hash_password
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import Branch, User, UserRole
from app.password_policy import validate_password_strength


router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    branch_id: Optional[int] = None
    branch_name: Optional[str] = None


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str
    branch_id: int = Field(gt=0)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Le nom d’utilisateur accepte uniquement lettres, chiffres, - et _."
            )
        return normalized

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UpdatePasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UpdateBranchRequest(BaseModel):
    branch_id: int = Field(gt=0)


def _response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        branch_id=user.branch_id,
        branch_name=user.branch.name if user.branch else None,
    )


def _common_user(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .options(joinedload(User.branch))
        .where(
            User.id == user_id,
            User.role == UserRole.COMMON,
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return user


@router.get("/", response_model=list[UserResponse])
def list_users(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Liste les utilisateurs actifs avec le nom de leur agence."""
    users = db.scalars(
        select(User)
        .options(joinedload(User.branch))
        .where(
            User.role == UserRole.COMMON,
            User.deleted_at.is_(None),
        )
        .order_by(User.username)
    ).all()
    return [_response(user) for user in users]


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: CreateUserRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Crée un utilisateur commun et l’affecte à une agence."""
    existing = db.scalar(
        select(User).where(func.lower(User.username) == payload.username)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ce nom d’utilisateur existe déjà.",
        )

    branch = db.get(Branch, payload.branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Agence introuvable.")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=UserRole.COMMON,
        branch=branch,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _response(user)


@router.patch("/{user_id}/password", response_model=UserResponse)
def change_password(
    user_id: int,
    payload: UpdatePasswordRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Change le mot de passe d’un utilisateur commun."""
    user = _common_user(db, user_id)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return _response(user)


@router.patch("/{user_id}/branch", response_model=UserResponse)
def change_branch(
    user_id: int,
    payload: UpdateBranchRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Réaffecte un utilisateur à une agence."""
    user = _common_user(db, user_id)
    branch = db.get(Branch, payload.branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="Agence introuvable.")

    user.branch = branch
    db.commit()
    db.refresh(user)
    return _response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Supprime logiquement un utilisateur commun."""
    user = _common_user(db, user_id)
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
