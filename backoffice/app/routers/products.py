"""Product proxy routes (external API only)."""

from typing import List
from fastapi import APIRouter, Depends
import requests
from pydantic import BaseModel

from app.dependencies import get_current_user

router = APIRouter(prefix="/products", tags=["products"])

EXTERNAL_PRODUCT_API = "http://localhost:5001/api/v1/products"


class ProductResponse(BaseModel):
    id: str
    name: str


@router.get("/", response_model=List[ProductResponse])
def list_products(user=Depends(get_current_user)):
    """Proxy to external Product API. Returns only id and name."""
    try:
        response = requests.get(EXTERNAL_PRODUCT_API, timeout=5)
        response.raise_for_status()
        data = response.json()

        # Ensure we only return id + name, sorted alphabetically
        products = [
            ProductResponse(id=p["id"], name=p["name"])
            for p in data
            if "id" in p and "name" in p
        ]
        products.sort(key=lambda x: x.name.lower())
        return products

    except Exception:
        # Return empty list on any error (external API down, timeout, etc.)
        return []
