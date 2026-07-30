"""Interpréteur Ollama optionnel, utilisé uniquement pour les questions ambiguës."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intents": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "product_detail",
                    "product_search",
                    "stock_lookup",
                    "stock_by_product",
                    "stock_by_branch",
                    "branch_info",
                    "branch_list",
                    "access_info",
                    "access_management",
                    "out_of_scope",
                ],
            },
            "minItems": 1,
            "maxItems": 3,
        },
        "product_query": {"type": ["string", "null"]},
        "branch": {"type": ["string", "null"]},
        "used_history": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "intents",
        "product_query",
        "branch",
        "used_history",
        "confidence",
    ],
    "additionalProperties": False,
}


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
            "Réponds uniquement avec l'objet JSON imposé, sans explication. "
            "Toute entité doit provenir mot pour mot de la question ou de "
            "l'historique fourni."
        )
        user_prompt = f"""
Choisis les intentions avec ces règles :
- prix, fiche ou description d'un produit : product_detail ;
- recherche par catégorie, caractéristique ou prix : product_search ;
- quantité d'un produit dans une agence : stock_lookup ;
- agences où trouver un produit : stock_by_product ;
- stock complet d'une agence : stock_by_branch ;
- adresse ou horaires d'une agence : branch_info ;
- liste des agences HBntory : branch_list ;
- lecture ou modification des accès : access_info ou access_management ;
- aucune de ces demandes : out_of_scope.

Copie uniquement le produit et l'agence réellement demandés.
Utilise null si une entité ou un filtre est absent.
Pour un suivi, utilise le produit de la dernière question pertinente et mets
used_history à true. Une agence citée dans la question actuelle remplace
toujours celle de l'historique.
« autres boutiques/agences » signifie stock_by_product.
« combien de PC portables dans une agence » signifie stock_lookup.

Historique utilisateur :
{json.dumps(history[-4:], ensure_ascii=False)}

Question à analyser :
{json.dumps(question, ensure_ascii=False)}
""".strip()
        payload = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "format": _PLAN_SCHEMA,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "options": {
                    "temperature": 0,
                    "num_ctx": 1024,
                    "num_predict": 80,
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
