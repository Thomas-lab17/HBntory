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

_PRODUCT_KINDS = {
    "laptop",
    "monitor",
    "keyboard",
    "mouse",
    "headset",
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
        deterministic_plan = self._apply_question_constraints(
            self._deterministic(question),
            question,
        )
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
                if llm_plan is not None:
                    llm_plan = self._sanitize_llm_plan(llm_plan, question)
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
                elif self._has_semantic_conflict(
                    deterministic_plan,
                    llm_plan,
                    question,
                ):
                    plan = self._fallback(
                        deterministic_plan,
                        "llm_semantic_override",
                    )
                else:
                    plan = llm_plan
                    plan.planner_source = "ollama"
                    plan.planner_status = "success"
                    plan.planner_failure = None

        plan = self._apply_history(plan, question, previous_questions)
        return self._apply_question_constraints(plan, question)

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
            if not previous_questions or not self._asks_other_locations(question):
                return plan

        previous_plan = self._deterministic(previous_questions[-1])
        if (
            self._is_location_follow_up(question)
            and previous_plan.has(
                Intent.PRODUCT_DETAIL,
                Intent.PRODUCT_SEARCH,
                Intent.STOCK_LOOKUP,
                Intent.STOCK_BY_PRODUCT,
            )
        ):
            plan.intents = (Intent.STOCK_LOOKUP,)
            plan.product_query = f"{previous_questions[-1]} {question}"
            plan.used_history = True
            return plan

        if self._asks_other_locations(question):
            plan.intents = (Intent.STOCK_BY_PRODUCT,)
            plan.product_query = f"{previous_questions[-1]} {question}"
            plan.branch = None
            plan.used_history = True
            return plan

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
            plan.product_query = f"{previous_questions[-1]} {question}"
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
                "y a t il", "dispo", "trouver", "boutique", "boutiques",
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
                "adresse", "horaires", "boutique", "boutiques",
            ),
        )

        if stock_signal:
            if self._contains_any(
                text,
                (
                    "ou est disponible", "ou trouver", "quelles agences",
                    "quels magasins", "dans quelle agence", "dans quels magasins",
                    "autres boutiques", "autre boutique", "quelles boutiques",
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
                (
                    "quelles agences",
                    "quelles sont les agences",
                    "liste des agences",
                    "toutes les agences",
                ),
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
        product_kind = payload.get("product_kind")
        price_min = payload.get("price_min")
        price_max = payload.get("price_max")
        currency = payload.get("currency")
        aggregate_matching_products = payload.get(
            "aggregate_matching_products",
            False,
        )
        used_history = payload.get("used_history", False)

        if product_query is not None and not isinstance(product_query, str):
            return None, "llm_invalid_entities"
        if branch is not None and not isinstance(branch, str):
            return None, "llm_invalid_entities"
        if stock_filter not in {None, "out_of_stock", "low_stock"}:
            return None, "llm_invalid_filter"
        if product_kind not in {None, *_PRODUCT_KINDS}:
            return None, "llm_invalid_filter"
        if currency not in {None, "USD", "EUR"}:
            return None, "llm_invalid_filter"
        parsed_prices: list[float | None] = []
        for raw_price in (price_min, price_max):
            if raw_price is None:
                parsed_prices.append(None)
                continue
            try:
                parsed_price = float(raw_price)
            except (TypeError, ValueError):
                return None, "llm_invalid_filter"
            if not 0 <= parsed_price <= 1_000_000:
                return None, "llm_invalid_filter"
            parsed_prices.append(parsed_price)
        if not isinstance(list_all_products, bool) or not isinstance(
            used_history,
            bool,
        ) or not isinstance(aggregate_matching_products, bool):
            return None, "llm_invalid_flags"

        clean_branch = branch.strip() if isinstance(branch, str) else None
        if clean_branch:
            normalized_branch = normalize_text(clean_branch)
            normalized_question = normalize_text(question)
            previous_context = normalize_text(" ".join(previous_questions))
            if (
                normalized_branch not in normalized_question
                and normalized_branch not in previous_context
            ):
                return None, "llm_ungrounded_branch"
            if (
                normalized_branch not in normalized_question
                and self._has_current_location_clue(question)
            ):
                return None, "llm_history_branch_conflict"

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

        detected_kind = self._extract_product_kind(question)
        if detected_kind is None and used_history and previous_questions:
            detected_kind = self._extract_product_kind(previous_questions[-1])
        if product_kind is not None and product_kind != detected_kind:
            return None, "llm_ungrounded_filter"
        detected_min, detected_max, detected_currency = self._extract_price_filters(
            question
        )
        if (
            parsed_prices[0] is not None
            and parsed_prices[0] != detected_min
        ) or (
            parsed_prices[1] is not None
            and parsed_prices[1] != detected_max
        ) or (
            currency is not None
            and currency != detected_currency
        ):
            return None, "llm_ungrounded_filter"

        return QueryPlan(
            intents=intents,
            confidence=confidence,
            product_query=clean_product_query,
            branch=clean_branch,
            stock_filter=stock_filter,
            used_history=used_history and bool(previous_questions),
            list_all_products=list_all_products,
            product_kind=detected_kind,
            price_min=detected_min,
            price_max=detected_max,
            currency=detected_currency,
            aggregate_matching_products=aggregate_matching_products,
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
    def _asks_other_locations(question: str) -> bool:
        text = normalize_text(question)
        return (
            any(word in text for word in ("boutique", "magasin", "agence"))
            and any(
                expression in text
                for expression in (
                    "autre",
                    "ou trouver",
                    "ou est",
                    "dans quel",
                    "dans quelle",
                )
            )
        )

    @staticmethod
    def _has_current_location_clue(question: str) -> bool:
        text = normalize_text(question)
        return bool(
            re.search(r"^(?:et\s+)?(?:a|dans|pour)\s+\w+", text)
            or re.search(
                r"\b(?:agence|magasin|boutique|branche)\s+(?:de\s+)?\w+",
                text,
            )
        )

    @staticmethod
    def _is_location_follow_up(question: str) -> bool:
        text = normalize_text(question)
        return bool(
            re.search(r"^(?:et|sinon|alors)\s+(?:a|dans|pour)\s+\w+", text)
        )

    @staticmethod
    def _extract_product_kind(question: str) -> str | None:
        text = normalize_text(question)
        mappings = (
            (
                "laptop",
                (
                    "pc portable",
                    "pcs portables",
                    "ordinateur portable",
                    "ordinateurs portables",
                    "laptops",
                ),
            ),
            ("monitor", ("ecran", "ecrans", "moniteur", "moniteurs", "monitor")),
            ("keyboard", ("clavier", "claviers", "keyboard")),
            ("mouse", ("souris", "mouse")),
            ("headset", ("casque", "casques", "headset")),
        )
        for kind, expressions in mappings:
            if any(expression in text for expression in expressions):
                return kind
        return None

    @staticmethod
    def _extract_price_filters(
        question: str,
    ) -> tuple[float | None, float | None, str | None]:
        normalized = normalize_text(question)
        raw = question.lower().replace(",", ".")
        number = r"(\d+(?:\.\d+)?)"
        maximum_patterns = (
            rf"(?:moins\s+de|sous|max(?:imum)?(?:\s+de)?)\s*{number}",
            rf"(?:a|à)?\s*-\s*de\s*{number}",
            rf"<\s*=?\s*{number}",
        )
        minimum_patterns = (
            rf"(?:plus\s+de|au\s+dessus\s+de|min(?:imum)?(?:\s+de)?)\s*{number}",
            rf">\s*=?\s*{number}",
        )

        def extract(patterns: tuple[str, ...]) -> float | None:
            for pattern in patterns:
                match = re.search(pattern, raw)
                if match:
                    return float(match.group(1))
            return None

        price_min = extract(minimum_patterns)
        price_max = extract(maximum_patterns)
        currency = None
        if "$" in question or any(
            token in normalized for token in ("usd", "dollar", "dollars")
        ):
            currency = "USD"
        elif "€" in question or any(
            token in normalized for token in ("eur", "euro", "euros")
        ):
            currency = "EUR"
        return price_min, price_max, currency

    def _apply_question_constraints(
        self,
        plan: QueryPlan,
        question: str,
    ) -> QueryPlan:
        price_min, price_max, currency = self._extract_price_filters(question)
        product_kind = self._extract_product_kind(question)
        plan.price_min = price_min
        plan.price_max = price_max
        plan.currency = currency
        if product_kind is not None or not plan.used_history:
            plan.product_kind = product_kind
        plan.aggregate_matching_products = bool(
            product_kind
            and plan.has(Intent.STOCK_LOOKUP)
            and "combien" in normalize_text(question)
        )
        return plan

    def _has_semantic_conflict(
        self,
        deterministic_plan: QueryPlan,
        llm_plan: QueryPlan,
        question: str,
    ) -> bool:
        text = normalize_text(question)
        if (
            deterministic_plan.has(Intent.BRANCH_LIST)
            and not llm_plan.has(Intent.BRANCH_LIST)
        ):
            return True
        if (
            deterministic_plan.has(Intent.BRANCH_INFO)
            and self._contains_any(text, ("horaires", "adresse", "ou se trouve"))
            and not llm_plan.has(Intent.BRANCH_INFO)
        ):
            return True
        if (
            deterministic_plan.aggregate_matching_products
            and not llm_plan.has(Intent.STOCK_LOOKUP)
        ):
            return True
        if (
            deterministic_plan.has(Intent.PRODUCT_SEARCH)
            and deterministic_plan.price_max is not None
            and not llm_plan.has(Intent.PRODUCT_SEARCH)
        ):
            return True
        if (
            deterministic_plan.has(Intent.STOCK_BY_PRODUCT)
            and self._asks_other_locations(question)
            and not llm_plan.has(Intent.STOCK_BY_PRODUCT)
        ):
            return True
        return False

    def _sanitize_llm_plan(
        self,
        plan: QueryPlan,
        question: str,
    ) -> QueryPlan:
        """Retire les intentions secondaires non demandées explicitement."""
        text = normalize_text(question)
        asks_branch_list = self._contains_any(
            text,
            (
                "quelles agences",
                "quelles sont les agences",
                "liste des agences",
                "toutes les agences",
            ),
        )
        asks_branch_info = self._contains_any(
            text,
            ("horaires", "adresse", "ou se trouve"),
        )
        intents = tuple(
            intent
            for intent in plan.intents
            if not (
                intent is Intent.BRANCH_LIST
                and not asks_branch_list
                and not asks_branch_info
            )
            and not (
                intent is Intent.BRANCH_INFO
                and not asks_branch_info
                and not asks_branch_list
            )
        )
        plan.intents = intents or (Intent.OUT_OF_SCOPE,)
        return plan

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
