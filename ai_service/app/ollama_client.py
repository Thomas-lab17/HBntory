"""Interpréteur Ollama optionnel, utilisé uniquement pour les questions ambiguës."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any


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
                timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
            except ValueError:
                timeout = 120.0
        self.timeout = max(timeout, 1.0)

    def interpret(self, question: str, history: list[str]) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        system_prompt = (
            "Tu classes les questions HBntory. Tu ne réponds jamais à la "
            "question et tu n'inventes aucune donnée. Réponds uniquement avec "
            "un objet JSON complet, sans explication."
        )
        user_prompt = f"""
Format obligatoire :
{{"intents":["stock_lookup"],"product_query":"écran 27 pouces","branch":"Lyon","confidence":0.9}}

Intentions autorisées :
product_detail, product_search, stock_lookup, stock_by_product,
stock_by_branch, branch_info, branch_list, access_info,
access_management, out_of_scope.

Utilise null lorsque le produit ou l'agence n'est pas précisé.

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
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            socket.timeout,
            OSError,
            ValueError,
        ):
            return None

        content = ((body.get("message") or {}).get("content") or "").strip()
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None
