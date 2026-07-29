"""
Agent (orchestrateur de la Couche 3)
=====================================
Relie IntentRouter, ToolCaller et ResponseBuilder.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .http_data_client import HttpDataClient
from .intent_router import Intent, IntentRouter
from .mcp_client import MCPClient, MockMCPClient
from .response_builder import ResponseBuilder
from .tool_caller import ToolCaller, ToolCallResult

logger = logging.getLogger("agent_ia.agent")


@dataclass
class AgentAnswer:
    question: str
    intent: Intent
    reponse: str
    tool_result: Optional[ToolCallResult] = None


class Agent:
    """Orchestrateur de la Couche 3 — Agent IA."""

    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self._data_client = mcp_client or HttpDataClient()
        self.intent_router = IntentRouter()
        self.tool_caller = ToolCaller(self._data_client)
        self.response_builder = ResponseBuilder()

    def repondre(self, question: str) -> AgentAnswer:
        intent_result = self.intent_router.classify(question)
        logger.info(
            "Intention détectée : %s (confiance=%.2f, mots-clés=%s)",
            intent_result.intent,
            intent_result.confidence,
            intent_result.matched_keywords,
        )

        if intent_result.intent == Intent.HORS_SCOPE:
            reponse = (
                "Cette question sort du périmètre que je peux traiter "
                "(produits, stock, agences). Pouvez-vous reformuler votre "
                "demande en lien avec l'un de ces sujets ?"
            )
            return AgentAnswer(
                question=question, intent=intent_result.intent, reponse=reponse
            )

        entites = self._extraire_entites(question)
        tool_result = self.tool_caller.call_for_intent(intent_result.intent, entites)
        reponse = self.response_builder.build(
            intent_result.intent, entites, tool_result
        )

        return AgentAnswer(
            question=question,
            intent=intent_result.intent,
            reponse=reponse,
            tool_result=tool_result,
        )

    def _extraire_entites(self, question: str) -> dict:
        q = question.lower()
        entites: dict = {}

        produit = self._match_produit(q, question)
        if produit:
            entites["produit"] = produit

        branche = self._match_branche(q)
        if branche:
            entites["branche"] = branche

        return entites

    def _match_branche(self, question_lower: str) -> Optional[str]:
        branches: list[str] = []
        client = self._data_client
        if isinstance(client, HttpDataClient):
            try:
                branches = [
                    str(b.get("name"))
                    for b in client.list_branches()
                    if b.get("name")
                ]
            except Exception:  # noqa: BLE001
                branches = []
        if not branches:
            branches = ["Lyon", "Paris"]

        for name in sorted(branches, key=len, reverse=True):
            if re.search(rf"\b{re.escape(name.lower())}\b", question_lower):
                return name
        return None

    def _match_produit(self, question_lower: str, question_raw: str) -> Optional[str]:
        products: list[dict] = []
        client = self._data_client
        if isinstance(client, HttpDataClient):
            try:
                products = client.list_products()
            except Exception:  # noqa: BLE001
                products = []
        elif isinstance(client, MockMCPClient):
            products = [
                {"name": name, "id": data.get("reference"), "sku": data.get("reference")}
                for name, data in MockMCPClient._PRODUITS.items()
            ]

        # 1) Longest catalog name contained in the question
        best_name: Optional[str] = None
        best_len = 0
        for product in products:
            name = str(product.get("name") or "").strip()
            if not name:
                continue
            name_l = name.lower()
            if name_l in question_lower and len(name_l) > best_len:
                best_name = name
                best_len = len(name_l)
        if best_name:
            return best_name

        # 2) Explicit SKU (e.g. HB-LAP-1001)
        for product in products:
            sku = str(product.get("sku") or "").strip()
            if sku and re.search(rf"\b{re.escape(sku)}\b", question_raw, flags=re.I):
                return sku

        # 3) "produit 1" / "id 1" / bare known numeric id
        id_match = re.search(
            r"\b(?:produit|product|id|référence|reference)\s*[#:]?\s*(\d+)\b",
            question_lower,
        )
        if id_match:
            return id_match.group(1)

        known_ids = {str(p.get("id")) for p in products if p.get("id") is not None}
        for token in re.findall(r"\b\d+\b", question_raw):
            if token in known_ids:
                return token

        for legacy in ("chaise ergonomique", "bureau assis-debout"):
            if legacy in question_lower:
                return legacy
        return None
