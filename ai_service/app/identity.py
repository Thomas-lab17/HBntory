"""Résolution de l'identité via le cookie HttpOnly du backoffice."""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request

from app.domain import UserContext, UserRole

logger = logging.getLogger("hbntory.ai.identity")


class IdentityServiceError(ConnectionError):
    """Le backoffice ne peut pas valider un cookie pourtant présent."""


class IdentityResolver:
    """Le navigateur ne peut jamais déclarer lui-même son rôle ou son agence."""

    def __init__(self, auth_api_url: str | None = None, timeout: float = 2.0):
        self.auth_api_url = (
            auth_api_url
            or os.getenv("AUTH_API_URL")
            or os.getenv("STOCK_API_URL")
            or "http://localhost:8000"
        ).rstrip("/")
        self.timeout = timeout

    def resolve(self, access_token: str | None) -> UserContext:
        if not access_token:
            return UserContext.anonymous()

        request = urllib.request.Request(
            f"{self.auth_api_url}/auth/me",
            headers={
                "Accept": "application/json",
                "Cookie": f"access_token={access_token}",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                return UserContext.anonymous()
            logger.warning("Échec de l'introspection utilisateur: HTTP %s", error.code)
            raise IdentityServiceError("Identity service unavailable") from error
        except (
            urllib.error.URLError,
            socket.timeout,
            OSError,
        ) as error:
            logger.warning("Backoffice indisponible pour l'identité: %s", error)
            raise IdentityServiceError("Identity service unavailable") from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise IdentityServiceError("Invalid identity response") from error

        if not isinstance(payload, dict):
            raise IdentityServiceError("Invalid identity response")
        try:
            role = UserRole(str(payload.get("role")))
            user_id = int(payload["id"])
        except (KeyError, TypeError, ValueError):
            raise IdentityServiceError("Invalid identity response")
        if role not in {UserRole.COMMON, UserRole.ADMIN}:
            raise IdentityServiceError("Invalid identity role")
        branch_id = payload.get("branch_id")
        return UserContext(
            role=role,
            user_id=user_id,
            username=str(payload.get("username") or "") or None,
            branch_id=int(branch_id) if branch_id is not None else None,
            branch_name=str(payload.get("branch_name") or "") or None,
        )
