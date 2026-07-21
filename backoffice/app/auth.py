"""Authentification JWT réutilisable dans une application FastAPI existante.

Intégration minimale :

    from app.auth import create_auth_router
    app.include_router(create_auth_router(find_by_username, find_by_id))

Les fonctions ``find_by_username`` et ``find_by_id`` doivent retourner un
objet utilisateur qui possède : id, username, password_hash, role et
éventuellement branch_id et deleted (ou deleted_at).
"""

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Callable, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jwt import InvalidTokenError
from pydantic import BaseModel


COOKIE_NAME = "access_token"
_hasher = PasswordHasher()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user: Dict[str, Any]


def hash_password(password: str) -> str:
    """Retourne le hash Argon2 à enregistrer en base."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_auth_router(
    find_by_username: Callable[[str], Any],
    find_by_id: Callable[[int], Any],
    *,
    secret: Optional[str] = None,
    expire_minutes: int = 30,
    cookie_secure: Optional[bool] = None,
) -> APIRouter:
    """Crée les routes JWT en utilisant le stockage de l'application.

    ``find_by_username`` et ``find_by_id`` sont les seuls points à adapter à
    PostgreSQL, SQLAlchemy ou toute autre base.
    """
    jwt_secret = secret or os.getenv("JWT_SECRET_KEY", "development-secret")
    secure = (
        cookie_secure
        if cookie_secure is not None
        else os.getenv("APP_ENV", "development") == "production"
    )
    router = APIRouter(prefix="/auth", tags=["authentication"])

    def error(detail: str = "Authentication required") -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    def make_token(user: Any) -> str:
        now = datetime.now(timezone.utc)
        payload: Dict[str, Any] = {
            "sub": str(user.id),
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(minutes=expire_minutes),
        }
        if user.role == "common":
            payload["branch_id"] = getattr(user, "branch_id", None)
        return jwt.encode(payload, jwt_secret, algorithm="HS256")

    def read_token(token: str) -> Dict[str, Any]:
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "iat", "exp"]},
        )

    def is_deleted(user: Any) -> bool:
        return bool(
            getattr(user, "deleted", False)
            or getattr(user, "deleted_at", None) is not None
        )

    def public_user(user: Any) -> Dict[str, Any]:
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "branch_id": getattr(user, "branch_id", None),
        }

    def current_user(
        token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    ) -> Any:
        if token is None:
            raise error()
        try:
            user = find_by_id(int(read_token(token)["sub"]))
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            raise error()
        if user is None or is_deleted(user):
            raise error()
        return user

    @router.post("/login", response_model=LoginResponse)
    def login(credentials: LoginRequest, response: Response) -> LoginResponse:
        username = credentials.username.strip().casefold()
        user = find_by_username(username)
        if (
            user is None
            or is_deleted(user)
            or not verify_password(credentials.password, user.password_hash)
        ):
            raise error("Invalid username or password")

        response.set_cookie(
            key=COOKIE_NAME,
            value=make_token(user),
            max_age=expire_minutes * 60,
            httponly=True,
            secure=secure,
            samesite="lax",
        )
        return LoginResponse(user=public_user(user))

    @router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(response: Response) -> None:
        response.delete_cookie(
            key=COOKIE_NAME,
            httponly=True,
            secure=secure,
            samesite="lax",
        )

    @router.get("/me")
    def me(user: Any = Depends(current_user)) -> Dict[str, Any]:
        return public_user(user)

    return router
