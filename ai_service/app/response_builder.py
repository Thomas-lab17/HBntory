"""
Response Builder
=================
Synthétise les données réellement récupérées par le ToolCaller en une
réponse en langage naturel. Règle absolue : AUCUNE INVENTION.
Si une donnée attendue est manquante, on le dit explicitement plutôt
que de la deviner ou de l'omettre silencieusement.
"""

from __future__ import annotations

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

        # Filet de sécurité : ne devrait pas arriver (HORS_SCOPE est
        # géré directement par l'Agent, sans passer par ce composant).
        return (
            "Je ne peux pas traiter cette demande avec les informations "
            "dont je dispose actuellement."
        )

    # -- Constructeurs spécifiques par intention ------------------------

    def _reponse_produit(self, entites: dict, tool_result: ToolCallResult) -> str:
        produit = tool_result.donnees.get("produit")
        nom_demande = entites.get("produit", "ce produit")

        if not produit:
            return (
                f"Je n'ai pas trouvé d'information sur « {nom_demande} » dans "
                f"le catalogue produit. Je ne peux donc pas répondre avec certitude — "
                f"pouvez-vous vérifier le nom exact ou la référence du produit ?"
            )

        parties = [f"{produit.get('nom', nom_demande)} (réf. {produit.get('reference', 'inconnue')})."]

        if produit.get("prix") is not None:
            devise = produit.get("currency") or "€"
            parties.append(f"Prix : {produit['prix']} {devise}.")
        else:
            parties.append("Le prix n'est pas renseigné dans les données disponibles.")

        if produit.get("description"):
            parties.append(produit["description"])
        else:
            parties.append("Aucune description n'est disponible pour ce produit.")

        return " ".join(parties)

    def _reponse_stock(self, entites: dict, tool_result: ToolCallResult) -> str:
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
