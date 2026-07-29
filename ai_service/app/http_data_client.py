"""HTTP data client: product-mcp + backoffice internal stock API."""

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
        if status != 200 or not isinstance(data, dict) or not data.get("success"):
            return []
        products = data.get("products") or []
        if not isinstance(products, list):
            return []
        self._products_cache = (now, products)
        return products

    def list_branches(self) -> list[dict]:
        now = time.monotonic()
        if self._branches_cache and now - self._branches_cache[0] < self.cache_ttl_seconds:
            return self._branches_cache[1]

        try:
            status, data = self._request(
                f"{self.stock_api_url}/internal/branches",
                headers=self._internal_headers(),
            )
        except ConnectionError:
            return []
        if status != 200 or not isinstance(data, list):
            return []
        self._branches_cache = (now, data)
        return data

    def resolve_product(self, nom_ou_ref: str) -> Optional[dict]:
        key = (nom_ou_ref or "").strip()
        if not key:
            return None

        status, data = self._request(
            f"{self.product_mcp_url}/tools/products/{urllib.parse.quote(key, safe='')}"
        )
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
        try:
            product = self.resolve_product(nom_ou_ref)
        except (ConnectionError, ValueError):
            return None
        if not product:
            return None
        return self._to_agent_product(product)

    def get_stock(self, nom_ou_ref: str, branche: Optional[str] = None) -> Optional[dict]:
        if not branche:
            return None
        try:
            product = self.resolve_product(nom_ou_ref)
        except (ConnectionError, ValueError):
            return None
        if not product or product.get("id") is None:
            return None

        product_id = str(product["id"])
        query = urllib.parse.urlencode(
            {"product_id": product_id, "branch": branche.strip()}
        )
        try:
            status, data = self._request(
                f"{self.stock_api_url}/internal/stock?{query}",
                headers=self._internal_headers(),
            )
        except ConnectionError:
            return None

        if status == 404:
            return None
        if status != 200 or not isinstance(data, dict):
            return None
        qty = data.get("quantity")
        if qty is None:
            return None
        return {"quantite": int(qty), "external_product_id": product_id}

    def _product_label(self, product_id: str) -> str:
        pid = str(product_id)
        for product in self.list_products():
            if str(product.get("id")) == pid:
                name = product.get("name")
                sku = product.get("sku")
                if name and sku:
                    return f"{name} (réf. {sku})"
                if name:
                    return str(name)
                if sku:
                    return str(sku)
        return f"produit {pid}"

    def _enrich_stock_rows(self, rows: list[dict]) -> list[dict]:
        enriched: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("external_product_id") or "")
            enriched.append(
                {
                    "external_product_id": pid,
                    "product_name": self._product_label(pid),
                    "quantite": int(row.get("quantity", 0)),
                    "branch_id": row.get("branch_id"),
                    "branch_name": row.get("branch_name"),
                }
            )
        return enriched

    def _fetch_stock_list(self, path: str) -> list[dict]:
        try:
            status, data = self._request(
                f"{self.stock_api_url}{path}",
                headers=self._internal_headers(),
            )
        except ConnectionError:
            return []
        if status == 404:
            return []
        if status != 200 or not isinstance(data, list):
            return []
        return self._enrich_stock_rows(data)

    def list_stock_by_branch(self, branche: str) -> list[dict]:
        name = (branche or "").strip()
        if not name:
            return []
        encoded = urllib.parse.quote(name, safe="")
        return self._fetch_stock_list(f"/internal/stock/by-branch/{encoded}")

    def list_stock_by_product(self, nom_ou_ref: str) -> list[dict]:
        try:
            product = self.resolve_product(nom_ou_ref)
        except (ConnectionError, ValueError):
            return []
        if not product or product.get("id") is None:
            return []
        pid = urllib.parse.quote(str(product["id"]), safe="")
        return self._fetch_stock_list(f"/internal/stock/by-product/{pid}")

    def list_all_stock(self) -> list[dict]:
        return self._fetch_stock_list("/internal/stock/all")

    def get_branche(self, nom_ou_ref: str) -> Optional[dict]:
        key = (nom_ou_ref or "").strip()
        if not key:
            return None
        try:
            status, data = self._request(
                f"{self.stock_api_url}/internal/branches/{urllib.parse.quote(key, safe='')}",
                headers=self._internal_headers(),
            )
        except ConnectionError:
            return None
        if status != 200 or not isinstance(data, dict):
            return None
        return {
            "nom": data.get("name") or key,
            "adresse": data.get("adresse"),
            "horaires": data.get("horaires"),
        }
