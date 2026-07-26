"""Stock management routes for common users."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_current_common
from app.models import Stock

router = APIRouter(prefix="/stock", tags=["stock"])


class StockResponse(BaseModel):
    id: int
    external_product_id: str
    quantity: int

    class Config:
        from_attributes = True


class StockAction(BaseModel):
    external_product_id: str
    quantity: int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[StockResponse])
def list_stock(
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """List stock for the current user's branch."""
    stocks = db.scalars(
        select(Stock).where(Stock.branch_id == user.branch_id)
    ).all()
    return stocks


@router.post("/add", response_model=StockResponse)
def add_stock(
    action: StockAction,
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """Add stock to the current user's branch."""
    if action.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be positive",
        )

    stock = db.scalar(
        select(Stock).where(
            Stock.branch_id == user.branch_id,
            Stock.external_product_id == action.external_product_id,
        )
    )

    if stock is None:
        stock = Stock(
            branch_id=user.branch_id,
            external_product_id=action.external_product_id,
            quantity=0,
        )
        db.add(stock)
        db.flush()

    stock.quantity += action.quantity
    db.commit()
    db.refresh(stock)
    return stock


@router.post("/remove", response_model=StockResponse)
def remove_stock(
    action: StockAction,
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """Remove stock from the current user's branch."""
    if action.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be positive",
        )

    stock = db.scalar(
        select(Stock).where(
            Stock.branch_id == user.branch_id,
            Stock.external_product_id == action.external_product_id,
        )
    )

    if stock is None or stock.quantity < action.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient stock",
        )

    stock.quantity -= action.quantity
    db.commit()
    db.refresh(stock)
    return stock
