"""
Client HTTP réel : product-mcp + API stock/backoffice interne.
=================================================================
Implémente l'interface MCPClient (get_produit / get_stock / get_branche)
contre de vrais services HTTP :

    - product-mcp        : GET {PRODUCT_MCP_URL}/tools/list_products
                            GET {PRODUCT_MCP_URL}/tools/products/{ref}
    - API stock interne   : GET {STOCK_API_URL}/internal/stock?...
                            GET {STOCK_API_URL}/internal/branches...
                            (authentifiée via header X-Internal-Api-Key)

Variables d'environnement :
    PRODUCT_MCP_URL   (défaut : http://localhost:8002)
    STOCK_API_URL     (défaut : http://localhost:8000)
    INTERNAL_API_KEY  (clé pour l'API interne)

Ce module ne dépend que de la stdlib (urllib), pas de requests.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class HttpDataClient:
    """Implements MCPClient-style access against real HTTP backends."""

    def __init__(
        self,
        product_mcp_url: str | None = None,
        stock_api_url: str | None = None,
        internal_api_key: str | None = None,
        timeout: float = 5.0,
        cache_ttl_seconds: float = 60.0,
    ):
        self.product_mcp_url = (
            product_mcp_url
            or os.getenv("PRODUCT_MCP_URL", "http://localhost:8002")
        ).rstrip("/")
        self.stock_api_url = (
            stock_api_url or os.getenv("STOCK_API_URL", "http://localhost:8000")
        ).rstrip("/")
        self.internal_api_key = internal_api_key or os.getenv("INTERNAL_API_KEY", "")
        self.timeout = timeout
        self.cache_ttl_seconds = cache_ttl_seconds
        self._products_cache: tuple[float, list[dict]] | None = None
        self._branches_cache: tuple[float, list[dict]] | None = None

    def _request(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8") if e.fp else ""
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise ConnectionError(f"HTTP request failed for {url}: {e}") from e

        data: Any = None
        if body:
            try:
                data = json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON from {url}") from e
        return status, data

    def _internal_headers(self) -> dict[str, str]:
        return {"X-Internal-Api-Key": self.internal_api_key}

    @staticmethod
    def _raise_for_service_status(status: int, service: str) -> None:
        if status in {401, 403}:
            raise PermissionError(f"{service} refused the service credentials")
        if status >= 500:
            raise ConnectionError(f"{service} is temporarily unavailable")

    @staticmethod
    def _to_agent_product(product: dict) -> dict:
        reference = product.get("sku") or product.get("id") or product.get("reference")
        return {
            "id": str(product.get("id")) if product.get("id") is not None else None,
            "reference": str(reference) if reference is not None else "inconnue",
            "nom": product.get("name") or product.get("nom"),
            "prix": product.get("price", product.get("prix")),
            "description": product.get("description"),
            "currency": product.get("currency"),
        }

    def list_products(self) -> list[dict]:
        now = time.monotonic()
        if self._products_cache and now - self._products_cache[0] < self.cache_ttl_seconds:
            return self._products_cache[1]

        status, data = self._request(f"{self.product_mcp_url}/tools/list_products")
        self._raise_for_service_status(status, "product-mcp")
        if status != 200 or not isinstance(data, dict) or not data.get("success"):
            raise ValueError("Invalid product-mcp catalogue response")
        products = data.get("products") or []
        if not isinstance(products, list):
            return []
        self._products_cache = (now, products)
        return products

    def list_branches(self) -> list[dict]:
        now = time.monotonic()
        if self._branches_cache and now - self._branches_cache[0] < self.cache_ttl_seconds:
            return self._branches_cache[1]

        status, data = self._request(
            f"{self.stock_api_url}/internal/branches",
            headers=self._internal_headers(),
        )
        self._raise_for_service_status(status, "backoffice")
        if status != 200 or not isinstance(data, list):
            raise ValueError("Invalid backoffice branches response")
        self._branches_cache = (now, data)
        return data

    def resolve_product(self, nom_ou_ref: str) -> Optional[dict]:
        key = (nom_ou_ref or "").strip()
        if not key:
            return None

        status, data = self._request(
            f"{self.product_mcp_url}/tools/products/{urllib.parse.quote(key, safe='')}"
        )
        self._raise_for_service_status(status, "product-mcp")
        if status == 200 and isinstance(data, dict) and data.get("success") and data.get("product"):
            return data["product"]

        key_l = key.lower()
        best: dict | None = None
        best_len = -1
        for product in self.list_products():
            name = str(product.get("name") or "").lower()
            sku = str(product.get("sku") or "").lower()
            pid = str(product.get("id") or "").lower()
            if key_l == pid or key_l == sku:
                return product
            if key_l and key_l in name and len(key_l) > best_len:
                best = product
                best_len = len(key_l)
            elif name and name in key_l and len(name) > best_len:
                best = product
                best_len = len(name)
        return best

    def get_produit(self, nom_ou_ref: str) -> Optional[dict]:
        product = self.resolve_product(nom_ou_ref)
        if not product:
            return None
        return self._to_agent_product(product)

    def get_stock(self, nom_ou_ref: str, branche: Optional[str] = None) -> Optional[dict]:
        if not branche:
            return None
        product = self.resolve_product(nom_ou_ref)
        if not product or product.get("id") is None:
            return None

        return self.get_stock_by_product_id(str(product["id"]), branche)

    def get_stock_by_product_id(
        self,
        product_id: str,
        branche: Optional[str],
    ) -> Optional[dict]:
        """Lit le stock sans résoudre une seconde fois le produit déjà identifié."""
        if not product_id or not branche:
            return None
        query = urllib.parse.urlencode(
            {"product_id": product_id, "branch": branche.strip()}
        )
        status, data = self._request(
            f"{self.stock_api_url}/internal/stock?{query}",
            headers=self._internal_headers(),
        )

        if status == 404:
            return None
        self._raise_for_service_status(status, "backoffice")
        if status != 200 or not isinstance(data, dict):
            raise ValueError("Invalid backoffice stock response")
        qty = data.get("quantity")
        if qty is None:
            return None
        return {"quantite": int(qty), "external_product_id": product_id}

    def _enrich_stock_rows(self, rows: list[dict]) -> list[dict]:
        products_by_id = {
            str(product.get("id")): product
            for product in self.list_products()
            if product.get("id") is not None
        }
        enriched: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("external_product_id") or "")
            product = products_by_id.get(pid) or {}
            name = product.get("name")
            sku = product.get("sku")
            if name and sku:
                label = f"{name} (réf. {sku})"
            elif name or sku:
                label = str(name or sku)
            else:
                label = f"produit {pid}"
            enriched.append(
                {
                    "external_product_id": pid,
                    "product_name": label,
                    "quantite": int(row.get("quantity", 0)),
                    "branch_id": row.get("branch_id"),
                    "branch_name": row.get("branch_name"),
                }
            )
        return enriched

    def _fetch_stock_list(self, path: str) -> list[dict]:
        status, data = self._request(
            f"{self.stock_api_url}{path}",
            headers=self._internal_headers(),
        )
        if status == 404:
            return []
        self._raise_for_service_status(status, "backoffice")
        if status != 200 or not isinstance(data, list):
            raise ValueError("Invalid backoffice stock list response")
        return self._enrich_stock_rows(data)

    def list_stock_by_branch(self, branche: str) -> list[dict]:
        name = (branche or "").strip()
        if not name:
            return []
        encoded = urllib.parse.quote(name, safe="")
        return self._fetch_stock_list(f"/internal/stock/by-branch/{encoded}")

    def list_stock_by_product(self, nom_ou_ref: str) -> list[dict]:
        product = self.resolve_product(nom_ou_ref)
        if not product or product.get("id") is None:
            return []
        return self.list_stock_by_product_id(str(product["id"]))

    def list_stock_by_product_id(self, product_id: str) -> list[dict]:
        if not product_id:
            return []
        pid = urllib.parse.quote(str(product_id), safe="")
        return self._fetch_stock_list(f"/internal/stock/by-product/{pid}")

    def list_all_stock(self) -> list[dict]:
        return self._fetch_stock_list("/internal/stock/all")

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]:
        key = (nom_ou_ref or "").strip()
        if not key:
            return None
        status, data = self._request(
            f"{self.stock_api_url}/internal/branches/{urllib.parse.quote(key, safe='')}",
            headers=self._internal_headers(),
        )
        self._raise_for_service_status(status, "backoffice")
        if status != 200 or not isinstance(data, dict):
            return None
        return {
            "nom": data.get("name") or key,
            "adresse": data.get("adresse"),
            "horaires": data.get("horaires"),
        }
