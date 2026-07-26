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
import re
from dataclasses import dataclass
from typing import Optional

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


# Liste de branches connues, utilisée par l'extracteur d'entités naïf.
# À remplacer en production par une vraie extraction d'entités (NER / LLM).
_BRANCHES_CONNUES = ["lyon", "paris"]

_PRODUITS_CONNUS = ["chaise ergonomique", "bureau assis-debout"]


class Agent:
    """Orchestrateur de la Couche 3 — Agent IA."""

    def __init__(self, mcp_client: Optional[MCPClient] = None):
        self.intent_router = IntentRouter()
        self.tool_caller = ToolCaller(mcp_client or MockMCPClient())
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

    # -- Extraction d'entités très simple, basée sur des listes connues --
    # NB : en production, remplacer par du NER ou un appel LLM structuré.

    def _extraire_entites(self, question: str) -> dict:
        q = question.lower()
        entites: dict = {}

        for produit in _PRODUITS_CONNUS:
            if produit in q:
                entites["produit"] = produit
                break

        for branche in _BRANCHES_CONNUES:
            if re.search(rf"\b{re.escape(branche)}\b", q):
                entites["branche"] = branche.capitalize()
                break

        return entites
