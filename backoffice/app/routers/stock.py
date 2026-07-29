"""Stock management routes for common users."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_common
from app.models import Stock
from app.product_api import (
    ProductAPIError,
    ProductAPIUnavailable,
    ProductNotFound,
    get_product,
)

router = APIRouter(prefix="/stock", tags=["stock"])


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_product_id: str
    quantity: int


class StockAction(BaseModel):
    external_product_id: str
    quantity: int = Field(gt=0, le=1_000_000)


class StockUpdate(BaseModel):
    external_product_id: str
    quantity: int = Field(ge=0, le=1_000_000)


@router.get("/", response_model=list[StockResponse])
def list_stock(
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """List stock for the current user's branch."""
    stocks = db.scalars(
        select(Stock)
        .where(Stock.branch_id == user.branch_id)
        .order_by(Stock.external_product_id)
    ).all()
    return stocks


@router.post("/add", response_model=StockResponse)
def add_stock(
    action: StockAction,
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """Add stock to the current user's branch."""
    try:
        product = get_product(action.external_product_id)
    except ProductNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit inconnu.",
        ) from exc
    except ProductAPIUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="L'API Product est indisponible. Aucun stock n'a été modifié.",
        ) from exc
    except ProductAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse invalide de l'API Product. Aucun stock n'a été modifié.",
        ) from exc

    canonical_product_id = str(product["id"])
    stock_statement = (
        select(Stock)
        .where(
            Stock.branch_id == user.branch_id,
            Stock.external_product_id == canonical_product_id,
        )
        .with_for_update()
    )
    stock = db.scalar(stock_statement)

    if stock is None:
        stock = Stock(
            branch_id=user.branch_id,
            external_product_id=canonical_product_id,
            quantity=0,
        )
        db.add(stock)
        try:
            db.flush()
        except IntegrityError:
            # Une requête concurrente a créé la même ligne : on la réutilise
            # afin de garantir un stock unique par agence et par produit.
            db.rollback()
            stock = db.scalar(stock_statement)
            if stock is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Le stock a été modifié simultanément. Réessayez.",
                )

    stock.quantity += action.quantity
    db.commit()
    db.refresh(stock)
    return stock


@router.post("/update", response_model=StockResponse)
def update_stock(
    action: StockUpdate,
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """Set the exact stock quantity for a product in the current branch."""
    stock = db.scalar(
        select(Stock).where(
            Stock.branch_id == user.branch_id,
            Stock.external_product_id == action.external_product_id,
        )
    )
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit absent du stock.",
        )

    stock.quantity = action.quantity
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


@router.delete("/{external_product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_empty_stock(
    external_product_id: str,
    user=Depends(get_current_common),
    db: Session = Depends(get_db),
):
    """Delete a stock row only when its quantity is zero."""
    stock = db.scalar(
        select(Stock).where(
            Stock.branch_id == user.branch_id,
            Stock.external_product_id == external_product_id,
        )
    )
    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produit absent de la liste des stocks.",
        )
    if stock.quantity > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mettez la quantité à 0 avant de supprimer ce produit.",
        )

    db.delete(stock)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
