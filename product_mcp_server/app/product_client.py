"""
product_client.py
------------------
Thin HTTP client responsible for ALL communication with the external
Product API. This is the only module that knows about HTTP status codes,
timeouts, sockets, etc. Everything above this layer (the MCP tools) only
ever sees clean Python exceptions or clean data.

Uses only the Python standard library (urllib) so it has zero external
dependencies and can run in any environment.
"""

import json
import socket
import urllib.request
import urllib.error
import os


class ProductAPIError(Exception):
    """Base class for all Product API related errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ProductNotFoundError(ProductAPIError):
    """Raised when the Product API returns a 404 for a specific product id."""


class ProductAPIConnectionError(ProductAPIError):
    """Raised when the Product API cannot be reached at all (DNS, refused
    connection, timeout, etc.) -- i.e. we never got an HTTP response."""


class ProductAPIClient:
    """
    Client for the external Product API.

    Expected external API contract (adjust base_url / paths to match the
    real Product API you are given):

        GET {base_url}/products            -> 200 {"products": [ {...}, ... ]}
        GET {base_url}/products/{id}        -> 200 {...single product...}
                                             -> 404 if the id does not exist
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: float = 5.0):
        self.base_url = (base_url or os.environ.get(
            "PRODUCT_API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.api_key = api_key or os.environ.get("PRODUCT_API_KEY")
        self.timeout = timeout

    # ---- internal helpers -------------------------------------------------

    def _build_request(self, path: str) -> urllib.request.Request:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(url, headers=headers, method="GET")

    def _do_get(self, path: str):
        """
        Performs a GET request and returns (status_code, parsed_json).
        Raises ProductAPIConnectionError for anything that means "we could
        not talk to the API at all".
        """
        req = self._build_request(path)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # We DID get a response from the server, just a non-2xx one.
            status = e.code
            body = e.read().decode("utf-8") if e.fp else ""
        except urllib.error.URLError as e:
            # DNS failure, connection refused, etc. -- no response at all.
            raise ProductAPIConnectionError(
                f"Could not connect to Product API at {self.base_url}{path}: {e.reason}"
            ) from e
        except socket.timeout as e:
            raise ProductAPIConnectionError(
                f"Product API request to {self.base_url}{path} timed out "
                f"after {self.timeout}s"
            ) from e
        except OSError as e:
            # Catch-all for low level connection issues (e.g. refused).
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

    # ---- public API ---------------------------------------------------

    def list_products(self) -> list:
        """Returns a list of raw product dicts as provided by the API."""
        status, data = self._do_get("/products")
        if status == 200:
            if isinstance(data, dict) and "products" in data:
                return data["products"]
            if isinstance(data, list):
                return data
            raise ProductAPIError(
                f"Product API returned an unexpected shape for /products: {data!r}",
                status_code=status,
            )
        raise ProductAPIError(
            f"Product API returned unexpected status {status} for /products",
            status_code=status,
        )

    def get_product(self, product_id: str) -> dict:
        """Returns the raw product dict for a single product id."""
        status, data = self._do_get(f"/products/{product_id}")
        if status == 200:
            if isinstance(data, dict):
                return data
            raise ProductAPIError(
                f"Product API returned an unexpected shape for /products/{product_id}: {data!r}",
                status_code=status,
            )
        if status == 404:
            raise ProductNotFoundError(
                f"Product '{product_id}' was not found.", status_code=404
            )
        raise ProductAPIError(
            f"Product API returned unexpected status {status} for /products/{product_id}",
            status_code=status,
        )
