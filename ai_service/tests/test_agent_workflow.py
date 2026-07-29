"""Tests fonctionnels du workflow multi-agents, sans appel réseau."""

from __future__ import annotations

import unittest
from collections import Counter
from typing import Any

from app.agent import Agent
from app.domain import (
    ConversationMessage,
    Intent,
    UserContext,
    UserRole,
    WorkflowStatus,
)


class FakeDataClient:
    """Jeu de données réaliste avec traçage de chaque accès métier."""

    PRODUCTS = [
        {
            "id": "101",
            "sku": "MON-27-IPS",
            "name": "27 inch Lab Monitor",
            "description": "Professional 27 inch IPS monitor.",
            "category": "Monitors",
            "price": 299.90,
            "currency": "EUR",
        },
        {
            "id": "102",
            "sku": "MON-24-OFF",
            "name": "24 inch Office Monitor",
            "description": "Compact 24 inch monitor for office use.",
            "category": "Monitors",
            "price": 179.00,
            "currency": "EUR",
        },
        {
            "id": "201",
            "sku": "KEY-WL-001",
            "name": "Wireless Keyboard",
            "description": "Compact wireless keyboard.",
            "category": "Keyboards",
            "price": 69.00,
            "currency": "EUR",
        },
    ]
    BRANCHES = [
        {"id": 1, "name": "Lyon"},
        {"id": 2, "name": "Paris"},
    ]
    STOCKS = {
        ("101", "Lyon"): 40,
        ("101", "Paris"): 3,
        ("102", "Lyon"): 12,
        ("102", "Paris"): 0,
        ("201", "Lyon"): 5,
    }

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    @property
    def call_counts(self) -> Counter[str]:
        return Counter(name for name, _ in self.calls)

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def list_products(self) -> list[dict]:
        self._record("list_products")
        return [dict(product) for product in self.PRODUCTS]

    def list_branches(self) -> list[dict]:
        self._record("list_branches")
        return [dict(branch) for branch in self.BRANCHES]

    def get_stock_by_product_id(
        self,
        product_id: str,
        branch: str | None,
    ) -> dict | None:
        self._record("get_stock_by_product_id", product_id, branch)
        quantity = self.STOCKS.get((str(product_id), branch or ""))
        if quantity is None:
            return None
        return {
            "external_product_id": str(product_id),
            "quantite": quantity,
        }

    def get_stock(
        self,
        product_reference: str,
        branch: str | None = None,
    ) -> dict | None:
        self._record("get_stock", product_reference, branch)
        product = self._find_product(product_reference)
        if product is None:
            return None
        return self.get_stock_by_product_id(str(product["id"]), branch)

    def list_stock_by_branch(self, branch: str) -> list[dict]:
        self._record("list_stock_by_branch", branch)
        rows: list[dict] = []
        for (product_id, stock_branch), quantity in self.STOCKS.items():
            if stock_branch.casefold() != branch.casefold():
                continue
            product = self._find_product(product_id) or {}
            rows.append(
                {
                    "external_product_id": product_id,
                    "product_name": product.get("name", product_id),
                    "branch_name": stock_branch,
                    "quantite": quantity,
                }
            )
        return rows

    def list_stock_by_product_id(self, product_id: str) -> list[dict]:
        self._record("list_stock_by_product_id", product_id)
        product = self._find_product(product_id) or {}
        return [
            {
                "external_product_id": stock_product_id,
                "product_name": product.get("name", stock_product_id),
                "branch_name": branch,
                "quantite": quantity,
            }
            for (stock_product_id, branch), quantity in self.STOCKS.items()
            if stock_product_id == str(product_id)
        ]

    def list_stock_by_product(self, product_reference: str) -> list[dict]:
        self._record("list_stock_by_product", product_reference)
        product = self._find_product(product_reference)
        if product is None:
            return []
        return self.list_stock_by_product_id(str(product["id"]))

    def get_produit(self, product_reference: str) -> dict | None:
        self._record("get_produit", product_reference)
        product = self._find_product(product_reference)
        return dict(product) if product else None

    def get_branche(self, branch_reference: str) -> dict | None:
        self._record("get_branche", branch_reference)
        return next(
            (
                dict(branch)
                for branch in self.BRANCHES
                if branch["name"].casefold() == branch_reference.casefold()
            ),
            None,
        )

    def _find_product(self, reference: str) -> dict | None:
        key = str(reference).casefold()
        return next(
            (
                product
                for product in self.PRODUCTS
                if key
                in {
                    str(product["id"]).casefold(),
                    str(product["sku"]).casefold(),
                    str(product["name"]).casefold(),
                }
            ),
            None,
        )


class AgentWorkflowTests(unittest.TestCase):
    def make_agent(self) -> tuple[Agent, FakeDataClient]:
        data_client = FakeDataClient()
        agent = Agent(data_client)
        # Les tests couvrent le workflow déterministe sans dépendre d'Ollama.
        agent.workflow.query_agent.llm.enabled = False
        return agent, data_client

    def test_ecran_27_pouces_disponible_a_lyon(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre(
            "Y a-t-il un écran 27 pouces dans l'agence de Lyon ?"
        )

        self.assertEqual(result.intent, Intent.STOCK_LOOKUP)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertIn("27 inch Lab Monitor", result.reponse)
        self.assertIn("Lyon", result.reponse)
        self.assertIn("40 unité(s)", result.reponse)
        self.assertEqual(result.planner_status, "fallback")
        self.assertEqual(result.planner_failure, "llm_disabled")
        self.assertEqual(
            data_client.calls[-1],
            ("get_stock_by_product_id", ("101", "Lyon")),
        )

    def test_ecran_sans_taille_demande_une_clarification(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre(
            "Y a-t-il un écran dans l'agence de Lyon ?"
        )

        self.assertEqual(result.intent, Intent.STOCK_LOOKUP)
        self.assertEqual(result.status, WorkflowStatus.NEEDS_CLARIFICATION)
        self.assertIn("Plusieurs produits correspondent", result.reponse)
        self.assertIn("24 inch Office Monitor", result.reponse)
        self.assertIn("27 inch Lab Monitor", result.reponse)
        self.assertEqual(
            data_client.call_counts["get_stock_by_product_id"],
            0,
        )

    def test_prix_et_stock_declenchent_les_deux_agents(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre(
            "Quel est le prix et le stock de l'écran 27 pouces "
            "dans l'agence de Lyon ?"
        )

        self.assertEqual(result.intent, Intent.STOCK_LOOKUP)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertEqual(result.agent, "product_agent+stock_agent")
        self.assertIn("Prix : 299.9 EUR", result.reponse)
        self.assertIn("40 unité(s)", result.reponse)
        self.assertEqual(
            data_client.call_counts["get_stock_by_product_id"],
            1,
        )

    def test_catalogue_global_reste_public_et_ne_lit_pas_le_stock(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre("Quels produits avez-vous ?")

        self.assertEqual(result.intent, Intent.PRODUCT_SEARCH)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertIn("contient 3 produit(s)", result.reponse)
        self.assertIn("27 inch Lab Monitor", result.reponse)
        self.assertEqual(data_client.call_counts["list_stock_by_branch"], 0)

    def test_suivi_et_le_prix_reutilise_le_produit_precedent(self) -> None:
        agent, _ = self.make_agent()
        history = (
            ConversationMessage(
                role="user",
                content="Y a-t-il un écran 27 pouces à Lyon ?",
            ),
            ConversationMessage(
                role="assistant",
                content="Le produit est disponible à Lyon.",
            ),
        )

        result = agent.repondre("Et le prix ?", history=history)

        self.assertEqual(result.intent, Intent.PRODUCT_DETAIL)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertTrue(result.used_history)
        self.assertIn("27 inch Lab Monitor", result.reponse)
        self.assertIn("299.9 EUR", result.reponse)

    def test_suivi_et_a_paris_reutilise_le_produit_precedent(self) -> None:
        agent, data_client = self.make_agent()
        previous_question = (
            "Y a-t-il un écran 27 pouces dans l'agence de Lyon ?"
        )
        history = (
            ConversationMessage(role="user", content=previous_question),
            ConversationMessage(
                role="assistant",
                content="Le produit est disponible à Lyon.",
            ),
        )

        result = agent.repondre("Et à Paris ?", history=history)

        self.assertEqual(result.intent, Intent.STOCK_LOOKUP)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertTrue(result.used_history)
        self.assertIn("Paris", result.reponse)
        self.assertIn("3 unité(s)", result.reponse)
        self.assertEqual(
            data_client.calls[-1],
            ("get_stock_by_product_id", ("101", "Paris")),
        )

    def test_hors_scope_ne_declenche_aucun_appel_metier(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre(
            "Raconte-moi une blague sur les développeurs."
        )

        self.assertEqual(result.intent, Intent.OUT_OF_SCOPE)
        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertEqual(data_client.calls, [])

    def test_panne_catalogue_n_est_pas_presentee_comme_produit_inconnu(self) -> None:
        class BrokenCatalogueClient(FakeDataClient):
            def list_products(self) -> list[dict]:
                self._record("list_products")
                raise ConnectionError("supplier unavailable")

        data_client = BrokenCatalogueClient()
        agent = Agent(data_client)
        agent.workflow.query_agent.llm.enabled = False

        result = agent.repondre("Quel est le prix du produit 101 ?")

        self.assertEqual(result.status, WorkflowStatus.ERROR)
        self.assertIn("temporairement indisponible", result.reponse)

    def test_stock_agrege_est_refuse_aux_anonymes(self) -> None:
        agent, data_client = self.make_agent()

        result = agent.repondre(
            "Donne-moi tout le stock de l'agence de Lyon."
        )

        self.assertEqual(result.intent, Intent.STOCK_BY_BRANCH)
        self.assertEqual(result.status, WorkflowStatus.DENIED)
        self.assertFalse(result.access_granted)
        self.assertEqual(result.access_scope, "public_item_only")
        self.assertIn("connexion au backoffice", result.reponse)
        self.assertEqual(data_client.calls, [])

    def test_common_peut_lire_le_stock_de_sa_propre_agence(self) -> None:
        agent, data_client = self.make_agent()
        user = UserContext(
            role=UserRole.COMMON,
            user_id=7,
            username="alice",
            branch_id=1,
            branch_name="Lyon",
        )

        result = agent.repondre(
            "Donne-moi tout le stock de mon agence.",
            user_context=user,
        )

        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertTrue(result.access_granted)
        self.assertEqual(result.access_scope, "stock:read:self")
        self.assertIn("Stock de l'agence Lyon", result.reponse)
        self.assertEqual(
            data_client.calls[-1],
            ("list_stock_by_branch", ("Lyon",)),
        )

    def test_common_ne_peut_pas_lire_le_stock_d_une_autre_agence(self) -> None:
        agent, data_client = self.make_agent()
        user = UserContext(
            role=UserRole.COMMON,
            user_id=7,
            username="alice",
            branch_id=1,
            branch_name="Lyon",
        )

        result = agent.repondre(
            "Donne-moi tout le stock de l'agence de Paris.",
            user_context=user,
        )

        self.assertEqual(result.status, WorkflowStatus.DENIED)
        self.assertFalse(result.access_granted)
        self.assertEqual(result.access_scope, "stock:read:self")
        self.assertIn("uniquement le stock de l'agence Lyon", result.reponse)
        self.assertEqual(
            data_client.call_counts["list_stock_by_branch"],
            0,
        )

    def test_gestion_acces_admin_reste_en_lecture_seule(self) -> None:
        agent, data_client = self.make_agent()
        admin = UserContext(
            role=UserRole.ADMIN,
            user_id=1,
            username="admin",
        )

        result = agent.repondre(
            "Donne accès à Alice à l'agence de Lyon.",
            user_context=admin,
        )

        self.assertEqual(result.intent, Intent.ACCESS_MANAGEMENT)
        self.assertEqual(result.status, WorkflowStatus.DENIED)
        self.assertFalse(result.access_granted)
        self.assertEqual(result.access_scope, "admin_read_only")
        self.assertIn("lecture seule", result.reponse)
        self.assertIn("aucune modification n'a été effectuée", result.reponse)
        self.assertEqual(data_client.calls, [])

    def test_alias_historique_mcp_client_reste_compatible(self) -> None:
        data_client = FakeDataClient()
        agent = Agent(mcp_client=data_client)
        agent.workflow.query_agent.llm.enabled = False

        result = agent.repondre("Quel est le prix du produit 101 ?")

        self.assertEqual(result.status, WorkflowStatus.ANSWERED)
        self.assertIn("299.9 EUR", result.reponse)


if __name__ == "__main__":
    unittest.main()
