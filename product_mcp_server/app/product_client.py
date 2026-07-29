"""
product_client.py
------------------
Thin HTTP client for the external Product API (stdlib only).
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request


class ProductAPIError(Exception):
    """Base class for all Product API related errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProductNotFoundError(ProductAPIError):
    """Raised when the Product API returns a 404 for a specific product id."""


class ProductAPIConnectionError(ProductAPIError):
    """Raised when the Product API cannot be reached at all."""


class ProductAPIClient:
    """
    Client for the external HBntory Product API.

    Contract:
        GET {base}/api/v1/products            -> 200 {"results": [...]}
        GET {base}/api/v1/products/{id_or_sku} -> 200 {...} | 404
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 5.0,
    ):
        raw = (
            base_url
            or os.environ.get("PRODUCT_API_URL")
            or os.environ.get("PRODUCT_API_BASE_URL")
            or "http://localhost:5001"
        )
        self.base_url = raw.rstrip("/")
        self.api_key = api_key or os.environ.get("PRODUCT_API_KEY")
        self.timeout = timeout

    def _build_request(self, path: str) -> urllib.request.Request:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(url, headers=headers, method="GET")

    def _do_get(self, path: str):
        req = self._build_request(path)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8") if e.fp else ""
        except urllib.error.URLError as e:
            raise ProductAPIConnectionError(
                f"Could not connect to Product API at {self.base_url}{path}: {e.reason}"
            ) from e
        except socket.timeout as e:
            raise ProductAPIConnectionError(
                f"Product API request to {self.base_url}{path} timed out "
                f"after {self.timeout}s"
            ) from e
        except OSError as e:
            raise ProductAPIConnectionError(
                f"Network error contacting Product API at {self.base_url}{path}: {e}"
            ) from e

        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as e:
                raise ProductAPIError(
                    f"Product API returned invalid JSON (status {status}): {e}",
                    status_code=status,
                )
        return status, parsed

    def list_products(self) -> list:
        status, data = self._do_get("/api/v1/products?limit=100&sort=name")
        if status == 200:
            if isinstance(data, dict):
                if isinstance(data.get("results"), list):
                    return data["results"]
                if isinstance(data.get("products"), list):
                    return data["products"]
            if isinstance(data, list):
                return data
            raise ProductAPIError(
                f"Product API returned an unexpected shape for list: {data!r}",
                status_code=status,
            )
        raise ProductAPIError(
            f"Product API returned unexpected status {status} for list products",
            status_code=status,
        )

    def get_product(self, product_id: str) -> dict:
        encoded = urllib.parse.quote(str(product_id).strip(), safe="")
        status, data = self._do_get(f"/api/v1/products/{encoded}")
        if status == 200:
            if isinstance(data, dict):
                return data
            raise ProductAPIError(
                f"Product API returned an unexpected shape for product {product_id}: {data!r}",
                status_code=status,
            )
        if status == 404:
            raise ProductNotFoundError(
                f"Product '{product_id}' was not found.", status_code=404
            )
        raise ProductAPIError(
            f"Product API returned unexpected status {status} for product {product_id}",
            status_code=status,
        )
