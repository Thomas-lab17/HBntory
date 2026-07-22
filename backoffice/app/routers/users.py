"""User management routes for admin users."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_current_admin
from app.models import User, UserRole, Branch
from app.auth import hash_password

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    branch_id: Optional[int] = None

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    username: str
    password: str
    branch_id: int


class UpdatePasswordRequest(BaseModel):
    new_password: str


class UpdateBranchRequest(BaseModel):
    branch_id: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[UserResponse])
def list_users(
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List all common users (excluding soft-deleted)."""
    users = db.scalars(
        select(User).where(
            User.role == UserRole.COMMON,
            User.deleted_at.is_(None)
        )
    ).all()
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a new common user and assign them to a branch."""
    # Check if username exists
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # Check branch exists
    branch = db.get(Branch, payload.branch_id)
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Branch not found",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=UserRole.COMMON,
        branch_id=payload.branch_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/password", response_model=UserResponse)
def change_password(
    user_id: int,
    payload: UpdatePasswordRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Change a common user's password."""
    user = db.get(User, user_id)
    if not user or user.role != UserRole.COMMON:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/branch", response_model=UserResponse)
def change_branch(
    user_id: int,
    payload: UpdateBranchRequest,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Change a common user's assigned branch."""
    user = db.get(User, user_id)
    if not user or user.role != UserRole.COMMON:
        raise HTTPException(status_code=404, detail="User not found")

    branch = db.get(Branch, payload.branch_id)
    if not branch:
        raise HTTPException(status_code=400, detail="Branch not found")

    user.branch_id = payload.branch_id
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin=Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Soft-delete a common user."""
    user = db.get(User, user_id)
    if not user or user.role != UserRole.COMMON:
        raise HTTPException(status_code=404, detail="User not found")

    from datetime import datetime, timezone
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
