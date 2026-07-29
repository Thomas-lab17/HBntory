"""Planifie la question utilisateur en une ou plusieurs intentions HBntory."""

from __future__ import annotations

import os
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
    """Utilise Ollama en premier, puis un repli déterministe explicite."""

    def __init__(
        self,
        llm: OllamaQueryInterpreter | None = None,
        min_llm_confidence: float | None = None,
    ):
        self.llm = llm or OllamaQueryInterpreter()
        if min_llm_confidence is None:
            try:
                min_llm_confidence = float(
                    os.getenv("AI_LLM_MIN_CONFIDENCE", "0.65")
                )
            except ValueError:
                min_llm_confidence = 0.65
        self.min_llm_confidence = min(
            max(min_llm_confidence, 0.0),
            1.0,
        )

    def run(
        self,
        question: str,
        history: tuple[ConversationMessage, ...] = (),
    ) -> QueryPlan:
        deterministic_plan = self._deterministic(question)
        previous_questions = [
            message.content
            for message in history
            if message.role == "user" and message.content.strip() != question.strip()
        ]
        if not self.llm.enabled:
            plan = self._fallback(deterministic_plan, "llm_disabled")
        else:
            interpretation = self.llm.interpret_detailed(
                question,
                previous_questions,
            )
            if not interpretation.succeeded:
                plan = self._fallback(
                    deterministic_plan,
                    interpretation.failure_code or "llm_unavailable",
                )
            else:
                llm_plan, failure = self._from_llm(
                    interpretation.payload,
                    question,
                    previous_questions,
                )
                if llm_plan is None:
                    plan = self._fallback(
                        deterministic_plan,
                        failure or "llm_invalid_plan",
                    )
                elif llm_plan.confidence < self.min_llm_confidence:
                    plan = self._fallback(
                        deterministic_plan,
                        "llm_low_confidence",
                    )
                elif any(
                    deterministic_plan.has(sensitive_intent)
                    and not llm_plan.has(sensitive_intent)
                    for sensitive_intent in (
                        Intent.ACCESS_MANAGEMENT,
                        Intent.STOCK_BY_BRANCH,
                    )
                ):
                    plan = self._fallback(
                        deterministic_plan,
                        "llm_security_override",
                    )
                elif (
                    llm_plan.primary_intent is Intent.OUT_OF_SCOPE
                    and deterministic_plan.primary_intent is not Intent.OUT_OF_SCOPE
                ):
                    plan = self._fallback(
                        deterministic_plan,
                        "llm_scope_conflict",
                    )
                else:
                    plan = llm_plan
                    plan.planner_source = "ollama"
                    plan.planner_status = "success"
                    plan.planner_failure = None

        return self._apply_history(plan, question, previous_questions)

    @staticmethod
    def _fallback(plan: QueryPlan, failure_code: str) -> QueryPlan:
        plan.planner_source = "deterministic_fallback"
        plan.planner_status = "fallback"
        plan.planner_failure = failure_code
        return plan

    def _apply_history(
        self,
        plan: QueryPlan,
        question: str,
        previous_questions: list[str],
    ) -> QueryPlan:
        if not previous_questions or not self._looks_like_follow_up(question):
            return plan

        previous_plan = self._deterministic(previous_questions[-1])
        if (
            plan.primary_intent is Intent.OUT_OF_SCOPE
            and previous_plan.primary_intent is not Intent.OUT_OF_SCOPE
        ):
            plan.intents = previous_plan.intents
            plan.confidence = max(plan.confidence, 0.75)
            plan.product_query = f"{previous_questions[-1]} {question}"
            plan.used_history = True
            if plan.planner_source != "ollama":
                plan.planner_failure = (
                    plan.planner_failure or "llm_history_recovery"
                )
            return plan

        if (
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
            current_query = plan.product_query or question
            plan.product_query = f"{previous_questions[-1]} {current_query}"
            plan.used_history = True
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
        previous_questions: list[str],
    ) -> tuple[QueryPlan | None, str | None]:
        if not isinstance(payload, dict) or not payload:
            return None, "llm_invalid_plan"
        raw_intents = payload.get("intents")
        if (
            not isinstance(raw_intents, list)
            or not 1 <= len(raw_intents) <= 3
            or any(
                not isinstance(value, str) or value not in _LLM_INTENTS
                for value in raw_intents
            )
        ):
            return None, "llm_invalid_intents"
        intents = tuple(dict.fromkeys(_LLM_INTENTS[value] for value in raw_intents))
        if (
            Intent.OUT_OF_SCOPE in intents and len(intents) > 1
        ) or (
            Intent.ACCESS_MANAGEMENT in intents and len(intents) > 1
        ):
            return None, "llm_invalid_intents"

        try:
            confidence = min(max(float(payload.get("confidence", 0.0)), 0.0), 1.0)
        except (TypeError, ValueError):
            return None, "llm_invalid_confidence"

        product_query = payload.get("product_query")
        branch = payload.get("branch")
        stock_filter = payload.get("stock_filter")
        list_all_products = payload.get("list_all_products", False)
        used_history = payload.get("used_history", False)

        if product_query is not None and not isinstance(product_query, str):
            return None, "llm_invalid_entities"
        if branch is not None and not isinstance(branch, str):
            return None, "llm_invalid_entities"
        if stock_filter not in {None, "out_of_stock", "low_stock"}:
            return None, "llm_invalid_filter"
        if not isinstance(list_all_products, bool) or not isinstance(
            used_history,
            bool,
        ):
            return None, "llm_invalid_flags"

        clean_branch = branch.strip() if isinstance(branch, str) else None
        if clean_branch:
            user_context = normalize_text(
                " ".join([*previous_questions, question])
            )
            if normalize_text(clean_branch) not in user_context:
                return None, "llm_ungrounded_branch"

        needs_product = any(
            intent
            in {
                Intent.PRODUCT_DETAIL,
                Intent.PRODUCT_SEARCH,
                Intent.STOCK_LOOKUP,
                Intent.STOCK_BY_PRODUCT,
            }
            for intent in intents
        )
        # Le LLM choisit une intention, mais il ne fabrique jamais la requête
        # transmise aux tools. Elle reste fondée sur les mots de l'utilisateur.
        clean_product_query = None
        if needs_product:
            clean_product_query = question
            if used_history and previous_questions:
                clean_product_query = f"{previous_questions[-1]} {question}"
        if stock_filter is not None and Intent.STOCK_BY_BRANCH not in intents:
            return None, "llm_invalid_filter"
        if list_all_products and Intent.PRODUCT_SEARCH not in intents:
            return None, "llm_invalid_flags"

        return QueryPlan(
            intents=intents,
            confidence=confidence,
            product_query=clean_product_query,
            branch=clean_branch,
            stock_filter=stock_filter,
            used_history=used_history and bool(previous_questions),
            list_all_products=list_all_products,
            planner_source="ollama",
            planner_status="success",
        ), None

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
