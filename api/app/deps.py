# FastAPI dependencies: DB session, current user, role guards.
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User
from .security import decode_token


def get_db():
    """Yield a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the user from the Bearer token; reject missing/deleted users."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentification requise")
    payload = decode_token(authorization.removeprefix("Bearer "))
    if payload is None:
        raise HTTPException(status_code=401, detail="Token invalide")
    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None or user.is_deleted:
        raise HTTPException(status_code=401, detail="Authentification requise")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Reserve the route to the admin role."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès administrateur requis")
    return user


def require_common(user: User = Depends(get_current_user)) -> User:
    """Reserve the route to common users with an assigned branch."""
    if user.role != "common":
        raise HTTPException(
            status_code=403, detail="Seuls les utilisateurs communs gèrent le stock"
        )
    if user.branch_id is None:
        raise HTTPException(status_code=400, detail="L'utilisateur n'a pas de branche assignée")
    return user
