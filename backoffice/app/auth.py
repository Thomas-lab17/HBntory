"""Gestion de l'authentification JWT."""

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Optional

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
    """Hash un mot de passe avec Argon2."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe avec son hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def create_auth_router(
    find_by_username,
    find_by_id,
    secret: Optional[str] = None,
    expire_minutes: int = 30,
    cookie_secure: Optional[bool] = None,
) -> APIRouter:
    """Crée les routes d'authentification JWT."""
    jwt_secret = secret or os.getenv("JWT_SECRET_KEY", "development-secret")
    secure = (
        cookie_secure
        if cookie_secure is not None
        else os.getenv("APP_ENV", "development") == "production"
    )
    router = APIRouter(prefix="/auth", tags=["authentication"])

    def error(detail: str = "Authentication required") -> HTTPException:
        """Crée une erreur d'authentification."""
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    def make_token(user: Any) -> str:
        """Crée un token JWT pour un utilisateur."""
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
        """Décode et valide un token JWT."""
        return jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "role", "iat", "exp"]},
        )

    def is_deleted(user: Any) -> bool:
        """Indique si un utilisateur est supprimé."""
        return bool(
            getattr(user, "deleted", False)
            or getattr(user, "deleted_at", None) is not None
        )

    def public_user(user: Any) -> Dict[str, Any]:
        """Retourne les informations publiques d'un utilisateur."""
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "branch_id": getattr(user, "branch_id", None),
        }

    def current_user(
        token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
    ) -> Any:
        """Récupère l'utilisateur associé au cookie JWT."""
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
        """Authentifie un utilisateur et crée son cookie JWT."""
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
        """Supprime le cookie JWT."""
        response.delete_cookie(
            key=COOKIE_NAME,
            httponly=True,
            secure=secure,
            samesite="lax",
        )

    @router.get("/me")
    def me(user: Any = Depends(current_user)) -> Dict[str, Any]:
        """Retourne l'utilisateur connecté."""
        return public_user(user)

    return router
