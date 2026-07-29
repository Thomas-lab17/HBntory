"""Contrat de données du workflow et implémentation de démonstration."""

from __future__ import annotations

from typing import Optional, Protocol


class MCPClient(Protocol):
    def list_products(self) -> list[dict]: ...

    def list_branches(self) -> list[dict]: ...

    def get_produit(self, nom_ou_ref: str) -> Optional[dict]: ...

    def get_stock(
        self,
        nom_ou_ref: str,
        branche: Optional[str] = None,
    ) -> Optional[dict]: ...

    def get_stock_by_product_id(
        self,
        product_id: str,
        branche: Optional[str],
    ) -> Optional[dict]: ...

    def list_stock_by_branch(self, branche: str) -> list[dict]: ...

    def list_stock_by_product(self, nom_ou_ref: str) -> list[dict]: ...

    def list_stock_by_product_id(self, product_id: str) -> list[dict]: ...

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]: ...


class MockMCPClient:
    _PRODUCTS = [
        {
            "id": "1",
            "sku": "CH-ERG-001",
            "name": "Chaise ergonomique",
            "price": 189.90,
            "currency": "EUR",
            "category": "Mobilier",
            "description": "Chaise avec support lombaire réglable.",
        },
        {
            "id": "2",
            "sku": "BUR-AD-002",
            "name": "Bureau assis-debout",
            "price": 349.00,
            "currency": "EUR",
            "category": "Mobilier",
            "description": "Bureau électrique réglable en hauteur.",
        },
    ]
    _BRANCHES = [{"id": 1, "name": "Lyon"}, {"id": 2, "name": "Paris"}]
    _STOCKS = {
        ("1", "Lyon"): 12,
        ("1", "Paris"): 0,
        ("2", "Lyon"): 4,
    }

    def list_products(self) -> list[dict]:
        return list(self._PRODUCTS)

    def list_branches(self) -> list[dict]:
        return list(self._BRANCHES)

    def _resolve(self, value: str) -> dict | None:
        key = value.strip().casefold()
        return next(
            (
                product
                for product in self._PRODUCTS
                if key
                in {
                    str(product["id"]).casefold(),
                    str(product["sku"]).casefold(),
                    str(product["name"]).casefold(),
                }
            ),
            None,
        )

    def get_produit(self, nom_ou_ref: str) -> Optional[dict]:
        product = self._resolve(nom_ou_ref)
        if not product:
            return None
        return {
            "id": product["id"],
            "reference": product["sku"],
            "nom": product["name"],
            "prix": product["price"],
            "currency": product["currency"],
            "description": product["description"],
        }

    def get_stock(
        self,
        nom_ou_ref: str,
        branche: Optional[str] = None,
    ) -> Optional[dict]:
        product = self._resolve(nom_ou_ref)
        if not product:
            return None
        return self.get_stock_by_product_id(str(product["id"]), branche)

    def get_stock_by_product_id(
        self,
        product_id: str,
        branche: Optional[str],
    ) -> Optional[dict]:
        key = (str(product_id), (branche or "").strip())
        if key not in self._STOCKS:
            return None
        return {
            "quantite": self._STOCKS[key],
            "external_product_id": str(product_id),
        }

    def list_stock_by_branch(self, branche: str) -> list[dict]:
        rows = []
        for (product_id, branch), quantity in self._STOCKS.items():
            if branch.casefold() != branche.casefold():
                continue
            product = self._resolve(product_id) or {}
            rows.append(
                {
                    "external_product_id": product_id,
                    "product_name": product.get("name", product_id),
                    "quantite": quantity,
                    "branch_name": branch,
                }
            )
        return rows

    def list_stock_by_product(self, nom_ou_ref: str) -> list[dict]:
        product = self._resolve(nom_ou_ref)
        return (
            self.list_stock_by_product_id(str(product["id"]))
            if product
            else []
        )

    def list_stock_by_product_id(self, product_id: str) -> list[dict]:
        return [
            {
                "external_product_id": pid,
                "product_name": (self._resolve(pid) or {}).get("name", pid),
                "quantite": quantity,
                "branch_name": branch,
            }
            for (pid, branch), quantity in self._STOCKS.items()
            if pid == str(product_id)
        ]

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]:
        key = nom_ou_ref.strip().casefold()
        branch = next(
            (
                item
                for item in self._BRANCHES
                if str(item["name"]).casefold() == key
            ),
            None,
        )
        return {"nom": branch["name"]} if branch else None
