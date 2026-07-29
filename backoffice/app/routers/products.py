"""Routes sécurisées donnant accès au catalogue produit externe."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

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
    category: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    discontinued: Optional[bool] = None
    weight_kg: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    updated_at: Optional[str] = None


def _response(product: dict[str, Any]) -> ProductResponse:
    return ProductResponse(
        id=str(product["id"]),
        sku=str(product.get("sku", product["id"])),
        name=product["name"],
        category=product.get("category"),
        description=product.get("description"),
        brand=product.get("brand"),
        supplier_id=product.get("supplier_id"),
        supplier_name=product.get("supplier_name"),
        unit_price=product.get("unit_price"),
        currency=product.get("currency"),
        discontinued=product.get("discontinued"),
        weight_kg=product.get("weight_kg"),
        tags=product.get("tags") if isinstance(product.get("tags"), list) else [],
        updated_at=product.get("updated_at"),
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
