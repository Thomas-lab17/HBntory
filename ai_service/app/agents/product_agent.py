"""Agent spécialisé dans le catalogue fournisseur."""

from __future__ import annotations

from typing import Any

from app.domain import AgentOutput, Intent, WorkflowState, WorkflowStatus


def product_label(product: dict[str, Any]) -> str:
    name = product.get("name") or product.get("nom") or "Produit"
    sku = product.get("sku") or product.get("reference")
    return f"{name} (réf. {sku})" if sku else str(name)


def product_price(product: dict[str, Any]) -> str | None:
    value = product.get("price", product.get("prix"))
    if value is None:
        return None
    currency = product.get("currency") or "EUR"
    return f"{value:g} {currency}" if isinstance(value, (int, float)) else f"{value} {currency}"


class ProductAgent:
    name = "product_agent"

    def run(self, state: WorkflowState) -> AgentOutput:
        if state.plan.has(Intent.PRODUCT_SEARCH):
            return self._search(state)

        product = state.entities.product
        candidates = state.entities.product_candidates
        if product is None and len(candidates) > 1:
            labels = ", ".join(product_label(item) for item in candidates)
            return AgentOutput(
                answer=(
                    f"Plusieurs produits correspondent à votre demande : {labels}. "
                    "Lequel souhaitez-vous consulter ?"
                ),
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": [item.get("id") for item in candidates]},
            )
        if product is None:
            return AgentOutput(
                answer=(
                    "Je n'ai trouvé aucun produit correspondant dans le catalogue "
                    "du fournisseur. Précisez le nom, la référence ou une caractéristique."
                ),
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": []},
            )

        parts = [product_label(product) + "."]
        price = product_price(product)
        parts.append(
            f"Prix : {price}."
            if price
            else "Le prix n'est pas renseigné par le fournisseur."
        )
        description = product.get("description")
        if description:
            parts.append(str(description))
        category = product.get("category")
        if category:
            parts.append(f"Catégorie : {category}.")
        return AgentOutput(
            answer=" ".join(parts),
            sources=["product-mcp:product"],
            evidence={"product": product},
        )

    def _search(self, state: WorkflowState) -> AgentOutput:
        candidates = state.entities.product_candidates
        if not candidates:
            return AgentOutput(
                answer=(
                    "Aucun produit du catalogue fournisseur ne correspond à ces critères. "
                    "Essayez une catégorie, une référence ou une caractéristique différente."
                ),
                status=WorkflowStatus.NEEDS_CLARIFICATION,
                sources=["product-mcp:catalogue"],
                evidence={"candidate_ids": []},
            )

        lines = []
        for product in candidates:
            price = product_price(product)
            suffix = f" — {price}" if price else ""
            lines.append(f"{product_label(product)}{suffix}")
        if state.plan.list_all_products:
            total = state.entities.product_total
            prefix = f"Le catalogue fournisseur contient {total} produit(s)."
            if total > len(candidates):
                prefix += f" Voici les {len(candidates)} premiers :"
            else:
                prefix += " Produits :"
            answer = prefix + " " + " ; ".join(lines) + "."
        else:
            answer = "Produits correspondants : " + " ; ".join(lines) + "."
        return AgentOutput(
            answer=answer,
            sources=["product-mcp:catalogue"],
            evidence={"products": candidates},
        )
