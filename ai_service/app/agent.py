"""
Agent (orchestrateur de la Couche 3)
=====================================
Relie les trois sous-composants :
    1. IntentRouter    -> classifie la question
    2. ToolCaller       -> appelle les outils MCP si nécessaire
    3. ResponseBuilder  -> construit la réponse finale

Règle clé : si l'intention est HORS_SCOPE, on répond immédiatement,
SANS appeler le moindre outil (économie de latence et de coût, et on
évite d'exposer des outils à des questions qui ne les concernent pas).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

from .intent_router import Intent, IntentRouter
from .mcp_client import MCPClient, MockMCPClient
from .http_client import HttpDataClient
from .response_builder import ResponseBuilder
from .tool_caller import ToolCaller, ToolCallResult

logger = logging.getLogger("agent_ia.agent")

_PRODUCT_SEARCH_ALIASES = {
    "écran": "monitor",
    "ecran": "monitor",
    "moniteur": "monitor",
    "pouce": "inch",
    "pouces": "inch",
}

_PRODUCT_SEARCH_STOP_WORDS = {
    "agence", "article", "avoir", "dans", "de", "des", "disponible",
    "du", "en", "est", "il", "la", "le", "les", "magasin", "produit",
    "stock", "un", "une", "vous",
}


@dataclass
class AgentAnswer:
    question: str
    intent: Intent
    reponse: str
    tool_result: Optional[ToolCallResult] = None


# Liste de branches connues, utilisée par l'extracteur d'entités naïf.
# À remplacer en production par une vraie extraction d'entités (NER / LLM).
def build_default_mcp_client() -> MCPClient:
    """
    Choisit le client de données par défaut selon l'environnement :

        AGENT_DATA_CLIENT=http  -> HttpDataClient (product-mcp + API stock réelle)
        AGENT_DATA_CLIENT=mock  -> MockMCPClient (données de démo, par défaut)

    Permet de lancer l'agent en mode démo sans rien configurer, et de
    basculer en production en définissant simplement la variable
    d'environnement (+ PRODUCT_MCP_URL / STOCK_API_URL / INTERNAL_API_KEY).
    """
    mode = os.getenv("AGENT_DATA_CLIENT", "mock").strip().lower()
    if mode == "http":
        return HttpDataClient()
    return MockMCPClient()


class Agent:
    """Orchestrateur de la Couche 3 — Agent IA."""

    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self.intent_router = IntentRouter()
        self._data_client = mcp_client or build_default_mcp_client()
        self.tool_caller = ToolCaller(self._data_client)
        self.response_builder = ResponseBuilder()

    def repondre(self, question: str) -> AgentAnswer:
        # 1) Intent router
        intent_result = self.intent_router.classify(question)
        logger.info(
            "Intention détectée : %s (confiance=%.2f, mots-clés=%s)",
            intent_result.intent, intent_result.confidence, intent_result.matched_keywords,
        )

        if intent_result.intent == Intent.HORS_SCOPE:
            # Court-circuit : aucune donnée outil à consulter, on répond directement.
            reponse = (
                "Cette question sort du périmètre que je peux traiter "
                "(produits, stock, agences). Pouvez-vous reformuler votre "
                "demande en lien avec l'un de ces sujets ?"
            )
            return AgentAnswer(question=question, intent=intent_result.intent, reponse=reponse)

        # 2) Extraction d'entités (naïve, à adapter/renforcer selon les besoins réels)
        entites = self._extraire_entites(question)

        # 3) Tool caller
        tool_result = self.tool_caller.call_for_intent(intent_result.intent, entites)

        # 4) Response builder
        reponse = self.response_builder.build(intent_result.intent, entites, tool_result)

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
        list_branches = getattr(client, "list_branches", None)
        if list_branches is not None:
            try:
                branches = [
                    str(branch.get("name"))
                    for branch in list_branches()
                    if branch.get("name")
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
        list_products = getattr(self._data_client, "list_products", None)
        if list_products is not None:
            try:
                products = list_products()
            except Exception:  # noqa: BLE001
                products = []

        best_name: Optional[str] = None
        best_len = 0
        for product in products:
            name = str(product.get("name") or "").strip()
            name_lower = name.lower()
            if name and name_lower in question_lower and len(name_lower) > best_len:
                best_name = name
                best_len = len(name_lower)
        if best_name:
            return best_name

        for product in products:
            sku = str(product.get("sku") or "").strip()
            if sku and re.search(rf"\b{re.escape(sku)}\b", question_raw, flags=re.I):
                return sku

        search_question = self._normalize_product_search(question_lower)
        query_tokens = {
            token
            for token in re.findall(r"\b[\w]+\b", search_question)
            if token not in _PRODUCT_SEARCH_STOP_WORDS and len(token) > 1
        }
        best_product: Optional[dict] = None
        best_score = 0
        for product in products:
            searchable = self._normalize_product_search(
                " ".join(
                    str(product.get(field) or "")
                    for field in ("name", "description", "category", "sku")
                ).lower()
            )
            product_tokens = set(re.findall(r"\b[\w]+\b", searchable))
            matching_tokens = query_tokens & product_tokens
            score = sum(3 if token.isdigit() else 1 for token in matching_tokens)
            if score > best_score:
                best_product = product
                best_score = score

        # Deux indices textuels, ou une dimension numérique accompagnée d'un
        # autre indice, suffisent pour identifier un produit du catalogue.
        if best_product is not None and best_score >= 2:
            return str(best_product.get("name") or best_product.get("sku"))

        identifier = re.search(
            r"\b(?:produit|product|id|référence|reference)\s*[#:]?\s*(\d+)\b",
            question_lower,
        )
        if identifier:
            return identifier.group(1)

        known_ids = {
            str(product.get("id"))
            for product in products
            if product.get("id") is not None
        }
        for token in re.findall(r"\b\d+\b", question_raw):
            if token in known_ids:
                return token
        return None

    @staticmethod
    def _normalize_product_search(text: str) -> str:
        normalized = text
        for source, target in _PRODUCT_SEARCH_ALIASES.items():
            normalized = re.sub(
                rf"\b{re.escape(source)}\b",
                target,
                normalized,
                flags=re.I,
            )
        return normalized
