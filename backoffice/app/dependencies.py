"""Authorization dependencies for role-based access control."""

from typing import Any, Optional
from fastapi import Cookie, Depends, HTTPException, status
import jwt
import os
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import User

COOKIE_NAME = "access_token"
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "development-secret")


def get_current_user(token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)) -> User:
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    with SessionLocal() as db:
        user = db.scalar(
            select(User)
            .options(joinedload(User.branch))
            .where(User.id == user_id)
        )
        if user is None or user.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def get_current_common(user: User = Depends(get_current_user)) -> User:
    if user.role != "common":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Common user access required")
    if not user.branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Common user must be assigned to a branch")
    return user
