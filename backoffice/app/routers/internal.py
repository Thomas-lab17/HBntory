"""Internal read-only API for the AI service."""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Branch, Stock

router = APIRouter(prefix="/internal", tags=["internal"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_internal_key(
    x_internal_api_key: Optional[str] = Header(default=None, alias="X-Internal-Api-Key"),
) -> None:
    expected = os.getenv("INTERNAL_API_KEY", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API key is not configured",
        )
    if not x_internal_api_key or x_internal_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StockOut(BaseModel):
    external_product_id: str
    quantity: int
    branch_id: int
    branch_name: str


@router.get("/branches", response_model=List[BranchOut])
def list_branches(
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(Branch).order_by(Branch.name)).all())


@router.get("/branches/{name}", response_model=BranchOut)
def get_branch_by_name(
    name: str,
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    branch = db.scalar(
        select(Branch).where(func.lower(Branch.name) == name.strip().lower())
    )
    if branch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")
    return branch


@router.get("/stock", response_model=StockOut)
def get_stock(
    product_id: str = Query(..., min_length=1),
    branch: str = Query(..., min_length=1),
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(Stock, Branch)
        .join(Branch, Stock.branch_id == Branch.id)
        .where(
            Stock.external_product_id == product_id.strip(),
            func.lower(Branch.name) == branch.strip().lower(),
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock not found")
    stock, branch_row = row
    return StockOut(
        external_product_id=stock.external_product_id,
        quantity=stock.quantity,
        branch_id=branch_row.id,
        branch_name=branch_row.name,
    )


@router.get("/stock/by-branch/{name}", response_model=List[StockOut])
def list_stock_by_branch(
    name: str,
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    branch_row = db.scalar(
        select(Branch).where(func.lower(Branch.name) == name.strip().lower())
    )
    if branch_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Branch not found")

    stocks = db.scalars(select(Stock).where(Stock.branch_id == branch_row.id)).all()
    return [
        StockOut(
            external_product_id=s.external_product_id,
            quantity=s.quantity,
            branch_id=branch_row.id,
            branch_name=branch_row.name,
        )
        for s in stocks
    ]


@router.get("/stock/by-product/{product_id}", response_model=List[StockOut])
def list_stock_by_product(
    product_id: str,
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    pid = product_id.strip()
    if not pid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="product_id required")

    rows = db.execute(
        select(Stock, Branch)
        .join(Branch, Stock.branch_id == Branch.id)
        .where(Stock.external_product_id == pid)
        .order_by(Branch.name)
    ).all()
    return [
        StockOut(
            external_product_id=stock.external_product_id,
            quantity=stock.quantity,
            branch_id=branch_row.id,
            branch_name=branch_row.name,
        )
        for stock, branch_row in rows
    ]


@router.get("/stock/all", response_model=List[StockOut])
def list_all_stock(
    _: None = Depends(require_internal_key),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Stock, Branch)
        .join(Branch, Stock.branch_id == Branch.id)
        .order_by(Branch.name, Stock.external_product_id)
    ).all()
    return [
        StockOut(
            external_product_id=stock.external_product_id,
            quantity=stock.quantity,
            branch_id=branch_row.id,
            branch_name=branch_row.name,
        )
        for stock, branch_row in rows
    ]
