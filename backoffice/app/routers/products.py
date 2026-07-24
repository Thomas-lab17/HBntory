"""Routes sécurisées donnant accès au catalogue produit externe."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.dependencies import get_current_common
from app.product_api import (
    ProductAPIError,
    ProductAPIUnavailable,
    ProductNotFound,
    get_product,
    list_products as fetch_products,
)

router = APIRouter(prefix="/products", tags=["products"])


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    category: str | None = None
    unit_price: float | None = None
    currency: str | None = None


def _response(product: dict[str, Any]) -> ProductResponse:
    return ProductResponse(
        id=str(product["id"]),
        sku=str(product.get("sku", product["id"])),
        name=product["name"],
        category=product.get("category"),
        unit_price=product.get("unit_price"),
        currency=product.get("currency"),
    )


def _http_error(exc: ProductAPIError) -> HTTPException:
    if isinstance(exc, ProductNotFound):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit inconnu.",
        )
    if isinstance(exc, ProductAPIUnavailable):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'API Product est indisponible.",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Réponse invalide de l'API Product.",
    )


@router.get("/", response_model=list[ProductResponse])
def list_products(user=Depends(get_current_common)):
    """Liste les produits disponibles pour un utilisateur common."""
    try:
        return [_response(product) for product in fetch_products()]
    except ProductAPIError as exc:
        raise _http_error(exc) from exc


@router.get("/{identifier}", response_model=ProductResponse)
def product_details(identifier: str, user=Depends(get_current_common)):
    """Retourne les détails utiles d'un produit du catalogue."""
    try:
        return _response(get_product(identifier))
    except ProductAPIError as exc:
        raise _http_error(exc) from exc
