"""Client HTTP pour le catalogue produit externe."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import requests


class ProductAPIError(Exception):
    """Réponse invalide reçue depuis l'API Product."""


class ProductAPIUnavailable(ProductAPIError):
    """L'API Product ne peut pas être jointe ou est indisponible."""


class ProductNotFound(ProductAPIError):
    """Le produit demandé n'existe pas dans le catalogue externe."""


def _base_url() -> str:
    return os.getenv("PRODUCT_API_URL", "http://localhost:5001").rstrip("/")


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_base_url()}{path}"
    try:
        response = requests.get(url, params=params, timeout=5)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise ProductAPIUnavailable("L'API Product est indisponible.") from exc
    except requests.RequestException as exc:
        raise ProductAPIError("Impossible de consulter l'API Product.") from exc

    if response.status_code == 404:
        raise ProductNotFound("Produit inconnu.")
    if response.status_code >= 500:
        raise ProductAPIUnavailable("L'API Product est indisponible.")

    try:
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProductAPIError("Réponse invalide de l'API Product.") from exc

    if not isinstance(payload, dict):
        raise ProductAPIError("Réponse invalide de l'API Product.")
    return payload


def list_products() -> list[dict[str, Any]]:
    """Retourne tout le catalogue actif du fournisseur, trié par nom."""
    products: list[dict[str, Any]] = []
    offset = 0

    while True:
        params: dict[str, Any] = {"limit": 100, "sort": "name"}
        if offset:
            params["offset"] = offset

        payload = _get_json("/api/v1/products", params=params)
        results = payload.get("results")
        count = payload.get("count")
        if (
            not isinstance(results, list)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
        ):
            raise ProductAPIError("Réponse invalide de l'API Product.")

        page = [
            product
            for product in results
            if isinstance(product, dict)
            and product.get("id") is not None
            and isinstance(product.get("name"), str)
        ]
        if len(page) != len(results):
            raise ProductAPIError("Un produit reçu est invalide.")

        products.extend(page)
        offset += len(page)
        if offset >= count:
            return products
        if not page:
            raise ProductAPIError("Le catalogue fournisseur est incomplet.")


def get_product(identifier: str) -> dict[str, Any]:
    """Retourne un produit par identifiant ou SKU."""
    normalized_identifier = identifier.strip()
    if not normalized_identifier:
        raise ProductNotFound("Produit inconnu.")

    product = _get_json(
        f"/api/v1/products/{quote(normalized_identifier, safe='')}"
    )
    if product.get("id") is None or not isinstance(product.get("name"), str):
        raise ProductAPIError("Réponse produit invalide.")
    return product
