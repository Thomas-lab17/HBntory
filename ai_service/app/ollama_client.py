"""Interpréteur Ollama optionnel, utilisé uniquement pour les questions ambiguës."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OllamaInterpretation:
    """Résultat explicite d'un appel au planificateur local."""

    payload: dict[str, Any] | None = None
    failure_code: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.payload is not None and self.failure_code is None


class OllamaQueryInterpreter:
    """Retourne un plan JSON structuré sans jamais répondre à l'utilisateur."""

    def __init__(
        self,
        enabled: bool | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        if enabled is None:
            enabled = os.getenv("AI_LLM_ENABLED", "false").lower() in {
                "1",
                "true",
                "yes",
            }
        self.enabled = enabled
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_API_BASE")
            or "http://host.docker.internal:11434"
        ).rstrip("/")
        configured_model = model or os.getenv("MODEL_NAME", "gemma3:1b")
        self.model = configured_model.removeprefix("ollama_chat/")
        if timeout is None:
            try:
                timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "15"))
            except ValueError:
                timeout = 15.0
        self.timeout = max(timeout, 1.0)

    def interpret(self, question: str, history: list[str]) -> dict[str, Any] | None:
        """Façade historique : retourne uniquement le payload éventuel."""
        return self.interpret_detailed(question, history).payload

    def interpret_detailed(
        self,
        question: str,
        history: list[str],
    ) -> OllamaInterpretation:
        if not self.enabled:
            return OllamaInterpretation(failure_code="llm_disabled")

        system_prompt = (
            "Tu es le planificateur sémantique HBntory. Identifie la demande "
            "de l'utilisateur, mais ne réponds jamais à sa question, "
            "n'invente aucune donnée et ne décide jamais des permissions. "
            "Réponds uniquement avec un objet JSON complet, sans explication."
        )
        user_prompt = f"""
Format obligatoire :
{{"intents":["stock_lookup"],"product_query":"écran 27 pouces","branch":"Lyon","stock_filter":null,"list_all_products":false,"used_history":false,"confidence":0.9}}

Intentions autorisées :
product_detail, product_search, stock_lookup, stock_by_product,
stock_by_branch, branch_info, branch_list, access_info,
access_management, out_of_scope.

Filtres de stock autorisés : out_of_stock, low_stock ou null.
Utilise null lorsque le produit ou l'agence n'est pas précisé.
Place plusieurs intentions lorsque la question demande plusieurs informations.
Pour une question de suivi, complète product_query avec le produit de
l'historique et mets used_history à true.

Historique utilisateur :
{json.dumps(history[-4:], ensure_ascii=False)}

Question à analyser :
{json.dumps(question, ensure_ascii=False)}
""".strip()
        payload = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {
                    "temperature": 0,
                    "num_ctx": 512,
                    "num_predict": 64,
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            code = (
                "llm_model_unavailable"
                if error.code == 404
                else "llm_http_error"
            )
            return OllamaInterpretation(failure_code=code)
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
            return OllamaInterpretation(failure_code="llm_unavailable")
        except (TypeError, ValueError):
            return OllamaInterpretation(failure_code="llm_invalid_response")

        content = ((body.get("message") or {}).get("content") or "").strip()
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            return OllamaInterpretation(failure_code="llm_invalid_response")
        if not isinstance(parsed, dict):
            return OllamaInterpretation(failure_code="llm_invalid_response")
        return OllamaInterpretation(payload=parsed)

    def availability(self, timeout: float = 2.0) -> tuple[bool, bool]:
        """Indique si Ollama répond et si le modèle configuré est présent."""
        if not self.enabled:
            return False, False
        request = urllib.request.Request(
            f"{self.base_url}/api/tags",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            socket.timeout,
            TimeoutError,
            OSError,
            TypeError,
            ValueError,
        ):
            return False, False

        models = body.get("models")
        if not isinstance(models, list):
            return True, False
        configured = self.model.casefold()
        model_available = any(
            configured
            in {
                str(item.get("name") or "").casefold(),
                str(item.get("model") or "").casefold(),
            }
            for item in models
            if isinstance(item, dict)
        )
        return True, model_available
