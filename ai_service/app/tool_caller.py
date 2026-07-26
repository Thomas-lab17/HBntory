"""
Tool Caller
===========
Appelle les outils MCP nécessaires, dans l'ordre, en fonction de
l'intention détectée. Chaque appel est loggé (logger structuré) pour
faciliter le debug : nom de l'outil, paramètres, succès/échec, durée.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .intent_router import Intent
from .mcp_client import MCPClient

logger = logging.getLogger("agent_ia.tool_caller")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | tool=%(tool)s | '
            'params=%(params)s | status=%(status)s | duree_ms=%(duree_ms)s',
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@dataclass
class ToolCallLog:
    tool: str
    params: dict
    status: str  # "ok" | "vide" | "erreur"
    duree_ms: float
    resultat: Optional[Any] = None
    erreur: Optional[str] = None


@dataclass
class ToolCallResult:
    """Résultat agrégé des appels d'outils pour une question donnée."""
    donnees: dict = field(default_factory=dict)
    logs: list[ToolCallLog] = field(default_factory=list)


class ToolCaller:
    """Appelle les outils MCP nécessaires selon l'intention, avec logs."""

    def __init__(self, mcp_client: MCPClient):
        self._client = mcp_client

    def call_for_intent(
        self,
        intent: Intent,
        entites: dict,
    ) -> ToolCallResult:
        """
        Args:
            intent: intention détectée par l'IntentRouter (jamais HORS_SCOPE ici,
                    l'agent ne doit pas appeler ce composant dans ce cas).
            entites: entités extraites de la question, ex :
                     {"produit": "chaise ergonomique", "branche": "Lyon"}

        Returns:
            ToolCallResult contenant les données récupérées et le journal des appels.
        """
        result = ToolCallResult()

        if intent == Intent.PRODUIT:
            self._appeler(
                result, "get_produit",
                {"nom_ou_ref": entites.get("produit", "")},
                cle_resultat="produit",
            )

        elif intent == Intent.STOCK:
            # Pour une question de stock, on a souvent aussi besoin des
            # infos produit pour construire une réponse complète : on
            # appelle donc les deux outils, dans l'ordre logique.
            self._appeler(
                result, "get_produit",
                {"nom_ou_ref": entites.get("produit", "")},
                cle_resultat="produit",
            )
            self._appeler(
                result, "get_stock",
                {
                    "nom_ou_ref": entites.get("produit", ""),
                    "branche": entites.get("branche"),
                },
                cle_resultat="stock",
            )

        elif intent == Intent.BRANCHE:
            self._appeler(
                result, "get_branche",
                {"nom_ou_ref": entites.get("branche", "")},
                cle_resultat="branche",
            )

        else:
            # Ne devrait jamais arriver : HORS_SCOPE est court-circuité
            # en amont par l'Agent, avant d'atteindre le ToolCaller.
            logger.warning(
                "Appel du ToolCaller avec une intention HORS_SCOPE, "
                "ceci ne devrait pas se produire.",
                extra={"tool": "-", "params": "-", "status": "ignore", "duree_ms": 0},
            )

        return result

    # -- Appel unitaire d'un outil, avec log ---------------------------

    def _appeler(
        self,
        result: ToolCallResult,
        nom_outil: str,
        params: dict,
        cle_resultat: str,
    ) -> None:
        methode = getattr(self._client, nom_outil, None)
        debut = time.perf_counter()

        if methode is None:
            duree_ms = round((time.perf_counter() - debut) * 1000, 2)
            log = ToolCallLog(
                tool=nom_outil, params=params, status="erreur",
                duree_ms=duree_ms, erreur="outil introuvable sur le client MCP",
            )
            result.logs.append(log)
            logger.error(
                "Outil introuvable",
                extra={"tool": nom_outil, "params": params, "status": "erreur", "duree_ms": duree_ms},
            )
            result.donnees[cle_resultat] = None
            return

        try:
            reponse = methode(**params)
            duree_ms = round((time.perf_counter() - debut) * 1000, 2)
            status = "ok" if reponse else "vide"

            log = ToolCallLog(
                tool=nom_outil, params=params, status=status,
                duree_ms=duree_ms, resultat=reponse,
            )
            result.logs.append(log)
            logger.info(
                "Appel outil terminé",
                extra={"tool": nom_outil, "params": params, "status": status, "duree_ms": duree_ms},
            )
            result.donnees[cle_resultat] = reponse

        except Exception as exc:  # noqa: BLE001 - on veut logguer toute erreur d'outil
            duree_ms = round((time.perf_counter() - debut) * 1000, 2)
            log = ToolCallLog(
                tool=nom_outil, params=params, status="erreur",
                duree_ms=duree_ms, erreur=str(exc),
            )
            result.logs.append(log)
            logger.error(
                "Erreur lors de l'appel de l'outil : %s", exc,
                extra={"tool": nom_outil, "params": params, "status": "erreur", "duree_ms": duree_ms},
            )
            result.donnees[cle_resultat] = None
