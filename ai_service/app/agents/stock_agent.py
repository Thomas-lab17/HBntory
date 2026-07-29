"""Agent spécialisé dans les quantités de stock HBntory."""

from __future__ import annotations

from typing import Any

from app.domain import AgentOutput, Intent, WorkflowState, WorkflowStatus

from .product_agent import product_label


class StockAgent:
    name = "stock_agent"

    def __init__(self, data_client: Any, low_stock_threshold: int = 5):
        self.data_client = data_client
        self.low_stock_threshold = low_stock_threshold

    def run(self, state: WorkflowState) -> AgentOutput:
        if state.plan.has(Intent.STOCK_BY_BRANCH):
            return self._by_branch(state)
        if state.plan.has(Intent.STOCK_BY_PRODUCT):
            return self._by_product(state)
        return self._lookup(state)

    def _lookup(self, state: WorkflowState) -> AgentOutput:
        product = state.entities.product
        candidates = state.entities.product_candidates
        if product is None and len(candidates) > 1:
            labels = ", ".join(product_label(item) for item in candidates)
            return AgentOutput(
                answer=f"Plusieurs produits correspondent : {labels}. Lequel choisissez-vous ?",
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": [item.get("id") for item in candidates]},
            )
        if product is None:
            return AgentOutput(
                answer=(
                    "Je ne peux pas vérifier le stock sans identifier le produit. "
                    "Indiquez son nom, son SKU ou sa référence."
                ),
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": []},
            )

        branch = (
            state.access.effective_branch
            if state.access and state.access.effective_branch
            else state.entities.branch
        )
        if not branch:
            names = [
                str(item.get("name"))
                for item in state.entities.branches
                if item.get("name")
            ]
            choices = ", ".join(names[:8])
            return AgentOutput(
                answer=(
                    "Dans quelle agence souhaitez-vous vérifier ce produit ?"
                    + (f" Agences disponibles : {choices}." if choices else "")
                ),
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["backoffice:branches"],
                evidence={"branches": names},
            )

        product_id = str(product.get("id") or "")
        get_by_id = getattr(self.data_client, "get_stock_by_product_id", None)
        if get_by_id and product_id:
            stock = get_by_id(product_id, branch)
        else:
            stock = self.data_client.get_stock(
                product_id or str(product.get("name") or ""),
                branch,
            )
        if stock is None:
            return AgentOutput(
                answer=(
                    f"Le produit {product_label(product)} existe dans le catalogue, "
                    f"mais aucune donnée de stock n'est renseignée pour l'agence {branch}."
                ),
                sources=["product-mcp:product", "backoffice:stock"],
                evidence={"product": product, "branch": branch, "stock": None},
            )

        quantity = int(stock.get("quantite", 0))
        availability = (
            f"est disponible à {branch} : {quantity} unité(s) en stock"
            if quantity > 0
            else f"est en rupture de stock à {branch}"
        )
        return AgentOutput(
            answer=f"{product_label(product)} {availability}.",
            sources=["product-mcp:product", "backoffice:stock"],
            evidence={
                "product": product,
                "branch": branch,
                "quantity": quantity,
            },
        )

    def _by_product(self, state: WorkflowState) -> AgentOutput:
        product = state.entities.product
        candidates = state.entities.product_candidates
        if product is None:
            if len(candidates) > 1:
                labels = ", ".join(product_label(item) for item in candidates)
                message = f"Plusieurs produits correspondent : {labels}."
            else:
                message = "Précisez le produit dont vous cherchez la disponibilité."
            return AgentOutput(
                answer=message,
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": [item.get("id") for item in candidates]},
            )

        product_id = str(product.get("id") or "")
        by_id = getattr(self.data_client, "list_stock_by_product_id", None)
        rows = (
            by_id(product_id)
            if by_id and product_id
            else self.data_client.list_stock_by_product(product_id)
        )
        available = [row for row in rows if int(row.get("quantite", 0)) > 0]
        if not available:
            return AgentOutput(
                answer=f"{product_label(product)} n'est disponible dans aucune agence.",
                sources=["product-mcp:product", "backoffice:stock"],
                evidence={"product": product, "stock_rows": rows},
            )
        details = "; ".join(
            f"{row.get('branch_name')} : {int(row.get('quantite', 0))} unité(s)"
            for row in available
        )
        return AgentOutput(
            answer=f"{product_label(product)} est disponible ici : {details}.",
            sources=["product-mcp:product", "backoffice:stock"],
            evidence={"product": product, "stock_rows": available},
        )

    def _by_branch(self, state: WorkflowState) -> AgentOutput:
        branch = (
            state.access.effective_branch
            if state.access and state.access.effective_branch
            else state.entities.branch
        )
        if not branch:
            return AgentOutput(
                answer="Précisez l'agence dont vous souhaitez consulter le stock.",
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["backoffice:branches"],
                evidence={"branch": None},
            )

        rows = self.data_client.list_stock_by_branch(branch)
        if state.plan.stock_filter == "out_of_stock":
            rows = [row for row in rows if int(row.get("quantite", 0)) == 0]
        elif state.plan.stock_filter == "low_stock":
            rows = [
                row
                for row in rows
                if 0 < int(row.get("quantite", 0)) <= self.low_stock_threshold
            ]

        if not rows:
            qualifier = {
                "out_of_stock": "en rupture",
                "low_stock": "en stock faible",
            }.get(state.plan.stock_filter, "en stock")
            return AgentOutput(
                answer=f"Aucun produit {qualifier} n'est renseigné pour l'agence {branch}.",
                sources=["backoffice:stock"],
                evidence={"branch": branch, "stock_rows": []},
            )

        visible = rows[:10]
        details = "; ".join(
            f"{row.get('product_name')} : {int(row.get('quantite', 0))}"
            for row in visible
        )
        remainder = len(rows) - len(visible)
        suffix = f" ; et {remainder} autre(s)" if remainder > 0 else ""
        return AgentOutput(
            answer=f"Stock de l'agence {branch} : {details}{suffix}.",
            sources=["backoffice:stock", "product-mcp:catalogue"],
            evidence={"branch": branch, "stock_rows": rows},
        )
