"""
Response Builder
=================
Synthétise les données réellement récupérées par le ToolCaller en une
réponse en langage naturel. Règle absolue : AUCUNE INVENTION.
"""

from __future__ import annotations

from collections import defaultdict

from .intent_router import Intent
from .tool_caller import ToolCallResult


class ResponseBuilder:
    """Construit la réponse finale à partir des données des outils."""

    def build(self, intent: Intent, entites: dict, tool_result: ToolCallResult) -> str:
        if intent == Intent.PRODUIT:
            return self._reponse_produit(entites, tool_result)
        if intent == Intent.STOCK:
            return self._reponse_stock(entites, tool_result)
        if intent == Intent.BRANCHE:
            return self._reponse_branche(entites, tool_result)

        return (
            "Je ne peux pas traiter cette demande avec les informations "
            "dont je dispose actuellement."
        )

    def _reponse_produit(self, entites: dict, tool_result: ToolCallResult) -> str:
        produit = tool_result.donnees.get("produit")
        nom_demande = entites.get("produit", "ce produit")

        if not produit:
            return (
                f"Je n'ai pas trouvé d'information sur « {nom_demande} » dans "
                f"le catalogue produit. Je ne peux donc pas répondre avec certitude — "
                f"pouvez-vous vérifier le nom exact ou la référence du produit ?"
            )

        parties = [
            f"{produit.get('nom', nom_demande)} (réf. {produit.get('reference', 'inconnue')})."
        ]

        if produit.get("prix") is not None:
            currency = produit.get("currency") or "EUR"
            parties.append(f"Prix : {produit['prix']} {currency}.")
        else:
            parties.append("Le prix n'est pas renseigné dans les données disponibles.")

        if produit.get("description"):
            parties.append(produit["description"])
        else:
            parties.append("Aucune description n'est disponible pour ce produit.")

        return " ".join(parties)

    def _reponse_stock(self, entites: dict, tool_result: ToolCallResult) -> str:
        mode = tool_result.donnees.get("stock_mode") or "single"

        if mode == "by_branch":
            return self._reponse_stocks_agence(entites, tool_result)
        if mode == "by_product":
            return self._reponse_stocks_produit(entites, tool_result)
        if mode == "all":
            return self._reponse_stocks_global(tool_result)
        return self._reponse_stock_single(entites, tool_result)

    def _reponse_stock_single(self, entites: dict, tool_result: ToolCallResult) -> str:
        produit = tool_result.donnees.get("produit")
        stock = tool_result.donnees.get("stock")
        nom_produit = entites.get("produit", "ce produit")
        branche = entites.get("branche")

        if not produit:
            return (
                f"Je n'ai pas trouvé le produit « {nom_produit} » dans le catalogue, "
                f"je ne peux donc pas vérifier son stock."
            )

        nom_affiche = produit.get("nom", nom_produit)

        if stock is None:
            lieu = f" à {branche}" if branche else ""
            return (
                f"Je n'ai pas de donnée de stock disponible pour « {nom_affiche} »{lieu}. "
                f"Je ne peux pas confirmer la disponibilité — cette information manque "
                f"dans les systèmes interrogés."
            )

        quantite = stock.get("quantite")
        if quantite is None:
            return (
                f"La fiche stock de « {nom_affiche} » a été trouvée, mais la quantité "
                f"n'est pas renseignée. Je ne peux donc pas indiquer la disponibilité exacte."
            )

        lieu = f" à {branche}" if branche else ""
        if quantite > 0:
            return f"« {nom_affiche} » est disponible{lieu} : {quantite} unité(s) en stock."
        return f"« {nom_affiche} » est actuellement en rupture de stock{lieu} (0 unité)."

    def _format_stock_line(self, row: dict) -> str:
        name = row.get("product_name") or f"produit {row.get('external_product_id')}"
        qty = row.get("quantite")
        if qty is None:
            return f"- {name} : quantité non renseignée"
        return f"- {name} : {qty} unité(s)"

    def _reponse_stocks_agence(self, entites: dict, tool_result: ToolCallResult) -> str:
        branche = entites.get("branche", "cette agence")
        stocks = tool_result.donnees.get("stocks")
        if stocks is None:
            return (
                f"Je n'ai pas pu récupérer les stocks de l'agence « {branche} ». "
                f"Le service de stock est peut-être indisponible."
            )
        if not stocks:
            return f"Aucun stock n'est enregistré pour l'agence « {branche} »."

        lines = [f"Stocks de l'agence {branche} :"]
        lines.extend(self._format_stock_line(row) for row in stocks)
        return "\n".join(lines)

    def _reponse_stocks_produit(self, entites: dict, tool_result: ToolCallResult) -> str:
        produit = tool_result.donnees.get("produit")
        stocks = tool_result.donnees.get("stocks")
        nom = (
            (produit or {}).get("nom")
            or entites.get("produit")
            or "ce produit"
        )

        if not produit:
            return (
                f"Je n'ai pas trouvé le produit « {entites.get('produit', 'ce produit')} » "
                f"dans le catalogue, je ne peux donc pas lister son stock par agence."
            )
        if stocks is None:
            return (
                f"Je n'ai pas pu récupérer le stock de « {nom} » par agence. "
                f"Le service de stock est peut-être indisponible."
            )
        if not stocks:
            return f"Aucune ligne de stock n'est enregistrée pour « {nom} » dans les agences."

        parts = [f"Stock de « {nom} » par agence :"]
        for row in stocks:
            branch = row.get("branch_name") or "agence inconnue"
            qty = row.get("quantite")
            if qty is None:
                parts.append(f"- {branch} : quantité non renseignée")
            else:
                parts.append(f"- {branch} : {qty} unité(s)")
        return "\n".join(parts)

    def _reponse_stocks_global(self, tool_result: ToolCallResult) -> str:
        stocks = tool_result.donnees.get("stocks")
        if stocks is None:
            return (
                "Je n'ai pas pu récupérer l'ensemble des stocks. "
                "Le service de stock est peut-être indisponible."
            )
        if not stocks:
            return "Aucun stock n'est enregistré dans le système pour le moment."

        by_branch: dict[str, list[dict]] = defaultdict(list)
        for row in stocks:
            by_branch[str(row.get("branch_name") or "Agence inconnue")].append(row)

        parts = ["Stocks par agence :"]
        for branch_name in sorted(by_branch.keys()):
            parts.append(f"{branch_name} :")
            parts.extend(self._format_stock_line(row) for row in by_branch[branch_name])
        return "\n".join(parts)

    def _reponse_branche(self, entites: dict, tool_result: ToolCallResult) -> str:
        branche_data = tool_result.donnees.get("branche")
        nom_demande = entites.get("branche", "cette agence")

        if not branche_data:
            return (
                f"Je n'ai pas trouvé d'agence correspondant à « {nom_demande} » "
                f"dans les données disponibles."
            )

        parties = [f"{branche_data.get('nom', nom_demande)} :"]

        if branche_data.get("adresse"):
            parties.append(f"adresse : {branche_data['adresse']}.")
        else:
            parties.append("adresse non renseignée.")

        if branche_data.get("horaires"):
            parties.append(f"Horaires : {branche_data['horaires']}.")
        else:
            parties.append("Horaires non renseignés.")

        return " ".join(parties)
