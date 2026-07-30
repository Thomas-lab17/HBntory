"""Résolution des produits et agences à partir des données réelles."""

from __future__ import annotations

import re
from typing import Any

from app.agents.query_agent import normalize_text
from app.domain import Intent, ResolvedEntities, WorkflowState


_ALIASES = {
    "ecran": "monitor",
    "ecrans": "monitor",
    "moniteur": "monitor",
    "moniteurs": "monitor",
    "pouce": "inch",
    "pouces": "inch",
    "ordinateur": "computer",
    "ordinateurs": "computer",
    "portable": "laptop",
    "portables": "laptop",
    "clavier": "keyboard",
    "claviers": "keyboard",
    "souris": "mouse",
    "casque": "headset",
    "casques": "headset",
}

_STOP_WORDS = {
    "a", "agence", "article", "au", "aux", "avec", "avez", "dans", "de",
    "des", "disponible", "du", "en", "est", "il", "la", "le", "les",
    "magasin", "modele", "ou", "par", "pour", "prix", "produit", "produits",
    "quel", "quelle", "quels", "quelles", "reference", "stock", "sur", "un",
    "une", "vous", "y",
}


def _aliases(text: str) -> str:
    normalized = normalize_text(text)
    for source, target in _ALIASES.items():
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return normalized


class EntityResolverAgent:
    def __init__(self, data_client: Any, max_candidates: int = 5):
        self.data_client = data_client
        self.max_candidates = max_candidates

    def run(self, state: WorkflowState) -> ResolvedEntities:
        needs_product = state.plan.has(
            Intent.PRODUCT_DETAIL,
            Intent.PRODUCT_SEARCH,
            Intent.STOCK_LOOKUP,
            Intent.STOCK_BY_PRODUCT,
        )
        needs_branch = state.plan.has(
            Intent.STOCK_LOOKUP,
            Intent.STOCK_BY_BRANCH,
            Intent.BRANCH_INFO,
            Intent.BRANCH_LIST,
        )

        products = self.data_client.list_products() if needs_product else []
        products = self._filter_products(products, state.plan)
        branches = self.data_client.list_branches() if needs_branch else []
        branch = self._resolve_branch(
            state.plan.branch or state.question,
            branches,
        )

        product = None
        candidates: list[dict[str, Any]] = []
        if needs_product:
            if state.plan.list_all_products:
                candidates = products[: self.max_candidates]
            else:
                product, candidates = self._resolve_product(
                    state.plan.product_query or state.question,
                    products,
                    search_mode=(
                        state.plan.has(Intent.PRODUCT_SEARCH)
                        or state.plan.aggregate_matching_products
                    ),
                    branch_names=[
                        str(item.get("name") or "")
                        for item in branches
                    ],
                    candidate_limit=(
                        None
                        if state.plan.aggregate_matching_products
                        else self.max_candidates
                    ),
                )

        return ResolvedEntities(
            product=product,
            product_candidates=candidates,
            branch=branch,
            branches=branches,
            product_total=len(products),
        )

    def _resolve_branch(
        self,
        text: str,
        branches: list[dict[str, Any]],
    ) -> str | None:
        normalized = normalize_text(text)
        for branch in sorted(
            branches,
            key=lambda item: len(str(item.get("name") or "")),
            reverse=True,
        ):
            name = str(branch.get("name") or "").strip()
            if name and re.search(rf"\b{re.escape(normalize_text(name))}\b", normalized):
                return name
        return None

    def _resolve_product(
        self,
        text: str,
        products: list[dict[str, Any]],
        *,
        search_mode: bool,
        branch_names: list[str],
        candidate_limit: int | None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        raw = text.strip()
        normalized = _aliases(raw)

        explicit_id = re.search(
            r"\b(?:produit|product|id|reference)\s*[#:]?\s*(\d+)\b",
            normalize_text(raw),
        )
        if explicit_id:
            identifier = explicit_id.group(1)
            product = next(
                (
                    item
                    for item in products
                    if str(item.get("id")) == identifier
                ),
                None,
            )
            return product, [product] if product else []

        for product in products:
            sku = str(product.get("sku") or "").strip()
            name = str(product.get("name") or "").strip()
            if sku and re.search(rf"\b{re.escape(sku)}\b", raw, flags=re.I):
                return product, [product]
            if name and _aliases(name) in normalized:
                return product, [product]

        ignored_branch_tokens = {
            token
            for name in branch_names
            for token in normalize_text(name).split()
        }
        query_tokens = {
            token
            for token in normalized.split()
            if token not in _STOP_WORDS
            and token not in ignored_branch_tokens
            and len(token) > 1
        }
        if not query_tokens:
            return None, []

        scored: list[tuple[int, dict[str, Any]]] = []
        for product in products:
            searchable = _aliases(
                " ".join(
                    str(product.get(field) or "")
                    for field in (
                        "name",
                        "description",
                        "category",
                        "sku",
                        "tags",
                    )
                )
            )
            product_tokens = set(searchable.split())
            matching = query_tokens & product_tokens
            if not matching:
                continue
            score = sum(4 if token.isdigit() else 1 for token in matching)
            scored.append((score, product))

        scored.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("name") or "").casefold(),
            )
        )
        if not scored:
            return None, []

        best_score = scored[0][0]
        minimum_search_score = max(1, best_score - 1)
        candidates = [
            product
            for score, product in scored
            if (
                score >= minimum_search_score
                if search_mode
                else score == best_score
            )
        ]
        if candidate_limit is not None:
            candidates = candidates[:candidate_limit]

        if search_mode:
            return None, candidates
        if len(candidates) == 1:
            return candidates[0], candidates
        return None, candidates

    @staticmethod
    def _filter_products(
        products: list[dict[str, Any]],
        plan: Any,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for product in products:
            if plan.product_kind and not EntityResolverAgent._matches_kind(
                product,
                plan.product_kind,
            ):
                continue
            value = product.get("price", product.get("prix"))
            try:
                price = float(value) if value is not None else None
            except (TypeError, ValueError):
                price = None
            if plan.price_min is not None and (
                price is None or price < plan.price_min
            ):
                continue
            if plan.price_max is not None and (
                price is None or price > plan.price_max
            ):
                continue
            if plan.currency and str(
                product.get("currency") or ""
            ).upper() != plan.currency:
                continue
            filtered.append(product)
        return filtered

    @staticmethod
    def _matches_kind(product: dict[str, Any], kind: str) -> bool:
        name = _aliases(str(product.get("name") or product.get("nom") or ""))
        category = normalize_text(str(product.get("category") or ""))
        if kind == "laptop":
            return (
                "laptop" in name.split()
                and any(token in category for token in ("laptop", "computer"))
            )
        tokens = {
            "monitor": {"monitor"},
            "keyboard": {"keyboard"},
            "mouse": {"mouse"},
            "headset": {"headset"},
        }.get(kind, {kind})
        return bool(tokens & set(name.split()))
