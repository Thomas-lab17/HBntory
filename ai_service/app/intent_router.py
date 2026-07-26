"""
Intent Router
=============
Classifie la question de l'utilisateur en une intention parmi :
    - PRODUIT     : question sur un produit (description, prix, caractéristiques...)
    - STOCK       : question sur la disponibilité / quantité en stock
    - BRANCHE     : question sur une agence / succursale / point de vente
    - HORS_SCOPE  : question qui ne relève d'aucune des catégories ci-dessus

Si l'intention est HORS_SCOPE, l'agent doit répondre immédiatement,
SANS appeler le moindre outil MCP (voir agent.py).

Le classifieur par défaut est basé sur des règles/mots-clés (rapide, sans
dépendance externe, facile à tester). Il peut être remplacé par un
classifieur basé sur un LLM en injectant une fonction `classify_fn`
respectant la même signature.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class Intent(str, Enum):
    PRODUIT = "produit"
    STOCK = "stock"
    BRANCHE = "branche"
    HORS_SCOPE = "hors_scope"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    matched_keywords: list[str]


# Mots-clés indicatifs par intention (simples, extensibles).
_KEYWORDS: dict[Intent, list[str]] = {
    Intent.PRODUIT: [
        "produit", "article", "prix", "tarif", "caractéristique",
        "modèle", "référence", "description", "fiche technique",
    ],
    Intent.STOCK: [
        "stock", "disponible", "disponibilité", "quantité",
        "en rupture", "rupture de stock", "combien reste",
        "reste-t-il", "en réserve",
    ],
    Intent.BRANCHE: [
        "agence", "succursale", "magasin", "branche", "point de vente",
        "horaires", "adresse", "où se trouve", "filiale",
    ],
}


class IntentRouter:
    """Route une question vers une intention."""

    def __init__(self, classify_fn: Optional[Callable[[str], IntentResult]] = None):
        """
        Args:
            classify_fn: fonction de classification personnalisée
                (ex : appel à un LLM). Si absente, on utilise le
                classifieur par règles ci-dessous.
        """
        self._classify_fn = classify_fn or self._rule_based_classify

    def classify(self, question: str) -> IntentResult:
        return self._classify_fn(question)

    # -- Implémentation par défaut -----------------------------------

    def _rule_based_classify(self, question: str) -> IntentResult:
        normalized = self._normalize(question)

        scores: dict[Intent, list[str]] = {intent: [] for intent in _KEYWORDS}
        for intent, keywords in _KEYWORDS.items():
            for kw in keywords:
                if kw in normalized:
                    scores[intent].append(kw)

        # On choisit l'intention avec le plus de mots-clés trouvés.
        best_intent, best_matches = max(
            scores.items(), key=lambda item: len(item[1])
        )

        if not best_matches:
            return IntentResult(
                intent=Intent.HORS_SCOPE,
                confidence=1.0,
                matched_keywords=[],
            )

        # Confiance proportionnelle au nombre de mots-clés trouvés
        # (plafonnée à 0.95 pour un classifieur par règles, jamais 100% sûr).
        confidence = min(0.5 + 0.15 * len(best_matches), 0.95)

        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            matched_keywords=best_matches,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r"[^\w\sàâäéèêëïîôöùûüç]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
