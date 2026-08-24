"""Product MCP HTTP shell — exposes tool logic for the AI service."""

from __future__ import annotations

from fastapi import FastAPI

from app.product_tools import get_product_impl, list_products_impl

app = FastAPI(title="HBntory Product MCP", version="0.2.0")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "product-mcp"}


@app.get("/tools/list_products", tags=["tools"])
def list_products() -> dict:
    return list_products_impl()


@app.get("/tools/products/{product_id}", tags=["tools"])
def get_product(product_id: str) -> dict:
    return get_product_impl(product_id)
