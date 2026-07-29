"""Planifie la question utilisateur en une ou plusieurs intentions HBntory."""

from __future__ import annotations

import re
import unicodedata

from app.domain import ConversationMessage, Intent, QueryPlan
from app.ollama_client import OllamaQueryInterpreter


_LLM_INTENTS = {
    "product_detail": Intent.PRODUCT_DETAIL,
    "product_search": Intent.PRODUCT_SEARCH,
    "stock_lookup": Intent.STOCK_LOOKUP,
    "stock_by_product": Intent.STOCK_BY_PRODUCT,
    "stock_by_branch": Intent.STOCK_BY_BRANCH,
    "branch_info": Intent.BRANCH_INFO,
    "branch_list": Intent.BRANCH_LIST,
    "access_info": Intent.ACCESS_INFO,
    "access_management": Intent.ACCESS_MANAGEMENT,
    "out_of_scope": Intent.OUT_OF_SCOPE,
}


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", without_accents)).strip()


class QueryAgent:
    """Route rapidement les cas évidents et sollicite Ollama en dernier recours."""

    def __init__(self, llm: OllamaQueryInterpreter | None = None):
        self.llm = llm or OllamaQueryInterpreter()

    def run(
        self,
        question: str,
        history: tuple[ConversationMessage, ...] = (),
    ) -> QueryPlan:
        plan = self._deterministic(question)
        previous_questions = [
            message.content
            for message in history
            if message.role == "user" and message.content.strip() != question.strip()
        ]

        if previous_questions and self._looks_like_follow_up(question):
            previous_plan = self._deterministic(previous_questions[-1])
            if (
                plan.primary_intent is Intent.OUT_OF_SCOPE
                and previous_plan.primary_intent is not Intent.OUT_OF_SCOPE
            ):
                plan = QueryPlan(
                    intents=previous_plan.intents,
                    confidence=0.75,
                    product_query=f"{previous_questions[-1]} {question}",
                    used_history=True,
                )
            elif (
                plan.has(
                    Intent.PRODUCT_DETAIL,
                    Intent.STOCK_LOOKUP,
                    Intent.STOCK_BY_PRODUCT,
                )
                and previous_plan.has(
                    Intent.PRODUCT_DETAIL,
                    Intent.PRODUCT_SEARCH,
                    Intent.STOCK_LOOKUP,
                    Intent.STOCK_BY_PRODUCT,
                )
                and not self._has_product_clue(question)
            ):
                plan.product_query = f"{previous_questions[-1]} {question}"
                plan.used_history = True

        if plan.confidence < 0.7:
            llm_plan = self._from_llm(
                self.llm.interpret(question, previous_questions),
                question,
            )
            if llm_plan is not None and llm_plan.confidence > plan.confidence:
                plan = llm_plan
        return plan

    def _deterministic(self, question: str) -> QueryPlan:
        text = normalize_text(question)

        if self._contains_any(
            text,
            (
                "donne acces", "donner acces", "accorde acces", "grant access",
                "affecte ", "reaffecte ", "change l agence", "change son agence",
                "supprime l acces", "retire l acces",
            ),
        ):
            return QueryPlan(
                (Intent.ACCESS_MANAGEMENT,),
                0.98,
                product_query=None,
            )

        stock_signal = self._contains_any(
            text,
            (
                "stock", "disponible", "disponibilite", "quantite",
                "combien reste", "reste t il", "rupture", "en reserve",
                "y a t il", "dispo",
            ),
        )

        if not stock_signal and self._contains_any(
            text,
            (
                "mes acces", "mon acces", "mon role", "mon agence",
                "qui suis je", "mes permissions",
            ),
        ):
            return QueryPlan((Intent.ACCESS_INFO,), 0.98)

        product_signal = self._contains_any(
            text,
            (
                "produit", "article", "prix", "tarif", "reference",
                "description", "caracteristique", "modele", "fiche technique",
                "catalogue", "ecran", "moniteur", "ordinateur", "portable",
                "clavier", "souris", "casque",
            ),
        )
        branch_signal = self._contains_any(
            text,
            (
                "agence", "magasin", "branche", "succursale", "point de vente",
                "adresse", "horaires",
            ),
        )

        if stock_signal:
            if self._contains_any(
                text,
                (
                    "ou est disponible", "ou trouver", "quelles agences",
                    "quels magasins", "dans quelle agence", "dans quels magasins",
                ),
            ):
                intents = [Intent.STOCK_BY_PRODUCT]
            elif self._contains_any(
                text,
                (
                    "liste du stock", "liste le stock", "tout le stock",
                    "tous les produits", "quels produits", "produits en rupture",
                    "stock faible",
                ),
            ):
                intents = [Intent.STOCK_BY_BRANCH]
            else:
                intents = [Intent.STOCK_LOOKUP]
            if product_signal and self._contains_any(
                text,
                ("prix", "tarif", "description", "reference", "fiche technique"),
            ):
                intents.append(Intent.PRODUCT_DETAIL)
            stock_filter = None
            if "rupture" in text:
                stock_filter = "out_of_stock"
            elif "faible" in text:
                stock_filter = "low_stock"
            return QueryPlan(
                tuple(intents),
                0.9,
                product_query=question,
                stock_filter=stock_filter,
            )

        if product_signal:
            if self._contains_any(
                text,
                (
                    "quels produits", "quels articles", "liste les",
                    "montre les", "cherche", "recherche", "avez vous des",
                ),
            ):
                list_all_products = self._contains_any(
                    text,
                    (
                        "quels produits avez vous",
                        "liste les produits",
                        "liste des produits",
                        "tous les produits du catalogue",
                        "montre le catalogue",
                        "montre moi le catalogue",
                    ),
                )
                return QueryPlan(
                    (Intent.PRODUCT_SEARCH,),
                    0.85,
                    product_query=question,
                    list_all_products=list_all_products,
                )
            return QueryPlan(
                (Intent.PRODUCT_DETAIL,),
                0.85,
                product_query=question,
            )

        if branch_signal:
            if self._contains_any(
                text,
                ("quelles agences", "liste des agences", "toutes les agences"),
            ):
                return QueryPlan((Intent.BRANCH_LIST,), 0.9)
            return QueryPlan((Intent.BRANCH_INFO,), 0.8)

        return QueryPlan((Intent.OUT_OF_SCOPE,), 0.55)

    def _from_llm(
        self,
        payload: dict | None,
        question: str,
    ) -> QueryPlan | None:
        if not payload:
            return None
        raw_intents = payload.get("intents")
        if not isinstance(raw_intents, list):
            return None
        intents = tuple(
            _LLM_INTENTS[value]
            for value in raw_intents
            if isinstance(value, str) and value in _LLM_INTENTS
        )
        if not intents:
            return None
        try:
            confidence = min(max(float(payload.get("confidence", 0.0)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.0
        product_query = payload.get("product_query")
        branch = payload.get("branch")
        return QueryPlan(
            intents=intents,
            confidence=confidence,
            product_query=product_query if isinstance(product_query, str) else question,
            branch=branch if isinstance(branch, str) else None,
        )

    @staticmethod
    def _contains_any(text: str, expressions: tuple[str, ...]) -> bool:
        return any(expression in text for expression in expressions)

    @staticmethod
    def _looks_like_follow_up(question: str) -> bool:
        text = normalize_text(question)
        return (
            text.startswith(("et ", "sinon ", "alors "))
            or len(text.split()) <= 5
        )

    @staticmethod
    def _has_product_clue(question: str) -> bool:
        text = normalize_text(question)
        return bool(
            re.search(r"\b(?:produit|id|reference)\s*\d+\b", text)
            or re.search(r"\b\d+\s*(?:pouce|pouces|inch)\b", text)
            or any(
                token in text.split()
                for token in (
                    "ecran",
                    "moniteur",
                    "ordinateur",
                    "portable",
                    "clavier",
                    "souris",
                    "casque",
                )
            )
        )
