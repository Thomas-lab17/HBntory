# Backoffice API — FastAPI, SQLAlchemy-backed, JWT auth.
# The backoffice frontend (backoffice/frontend, served by nginx) calls these
# routes: /api/login, /api/me, /api/branches, /api/stock*, /api/users*,
# /api/products*.
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
import os

from fastapi import Header

from . import models
from . import product_client
from .deps import get_current_user, get_db, require_admin, require_common
from .security import create_token, hash_password, verify_password
from .models import ROLE_COMMON

app = FastAPI(title="HBntory Backoffice API", version="0.1.0")


class LoginBody(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    branch_id: int | None
    branch_name: str | None
    is_deleted: bool


def serialize_user(user: models.User) -> UserOut:
    """Format a user for JSON responses."""
    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        branch_id=user.branch_id,
        branch_name=user.branch.name if user.branch else None,
        is_deleted=user.is_deleted,
    )


@app.post("/api/login")
def login(body: LoginBody, db: Session = Depends(get_db)) -> dict:
    """Authenticate and return a Bearer token; reject deleted users."""
    user = db.scalar(select(models.User).where(models.User.username == body.username))
    if user is None or user.is_deleted or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    return {
        "token": create_token(user),
        "token_type": "Bearer",
        "user": serialize_user(user),
    }


@app.get("/api/me")
def me(user: models.User = Depends(get_current_user)) -> dict:
    """Return the current authenticated user."""
    return {"user": serialize_user(user)}


class BranchIn(BaseModel):
    name: str
    address: str | None = None


@app.get("/api/branches")
def list_branches(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """List branches (any authenticated user)."""
    branches = db.scalars(select(models.Branch).order_by(models.Branch.name)).all()
    return {"branches": [{"id": b.id, "name": b.name, "address": b.address} for b in branches]}


@app.post("/api/branches", status_code=201)
def create_branch(body: BranchIn, user: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Create a branch (admin only)."""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Un nom de branche est requis")
    if db.scalar(select(models.Branch).where(models.Branch.name.ilike(name))):
        raise HTTPException(status_code=409, detail="Cette branche existe déjà")
    branch = models.Branch(name=name, address=(body.address or "").strip() or None)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return {"branch": {"id": branch.id, "name": branch.name, "address": branch.address}}

class StockIn(BaseModel):
    product_id: str
    quantity: int


class StockOut(BaseModel):
    id: int
    product_id: str
    quantity: int


def serialize_stock(stock: models.Stock) -> StockOut:
    """Format a stock row for JSON responses."""
    return StockOut(id=stock.id, product_id=stock.product_id, quantity=stock.quantity)


def parse_positive(body: StockIn) -> tuple[str, int]:
    """Validate product_id and quantity; raise 400 on invalid input."""
    product_id = (body.product_id or "").strip()
    if not product_id:
        raise HTTPException(status_code=400, detail="product_id requis")
    if body.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity doit être un entier positif")
    return product_id, body.quantity


@app.get("/api/stock")
def get_stock(user: models.User = Depends(require_common), db: Session = Depends(get_db)) -> dict:
    """List the stock of the current user's branch only."""
    stocks = db.scalars(
        select(models.Stock)
        .where(models.Stock.branch_id == user.branch_id)
        .order_by(models.Stock.product_id)
    ).all()
    return {"branch": user.branch.name, "stock": [serialize_stock(s) for s in stocks]}


@app.post("/api/stock/add", status_code=201)
def add_stock(body: StockIn, user: models.User = Depends(require_common), db: Session = Depends(get_db)) -> dict:
    """Add units of a product to the current user's branch (merges if it exists).

    The product must exist in the external catalog (checked through the MCP
    bridge): stock is only recorded for real products, never invented ones.
    """
    product_id, quantity = parse_positive(body)
    product = product_client.get_product(product_id)
    if not product.get("success"):
        if product.get("error_type") == "not_found":
            raise HTTPException(
                status_code=400,
                detail=f"Produit {product_id} inconnu dans le catalogue",
            )
        raise HTTPException(
            status_code=503,
            detail="Catalogue indisponible : impossible de vérifier le produit",
        )
    stock = db.scalar(
        select(models.Stock).where(
            models.Stock.branch_id == user.branch_id, models.Stock.product_id == product_id
        )
    )
    if stock is None:
        stock = models.Stock(branch_id=user.branch_id, product_id=product_id, quantity=quantity)
        db.add(stock)
    else:
        stock.quantity += quantity
    db.commit()
    db.refresh(stock)
    return {"stock": serialize_stock(stock)}


@app.post("/api/stock/remove")
def remove_stock(body: StockIn, user: models.User = Depends(require_common), db: Session = Depends(get_db)) -> dict:
    """Remove units from the current user's branch; quantity never goes below zero."""
    product_id, quantity = parse_positive(body)
    stock = db.scalar(
        select(models.Stock).where(
            models.Stock.branch_id == user.branch_id, models.Stock.product_id == product_id
        )
    )
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Produit {product_id} introuvable en stock")
    if stock.quantity - quantity < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuffisant : il ne reste que {stock.quantity} unités",
        )
    stock.quantity -= quantity
    db.commit()
    db.refresh(stock)
    return {"stock": serialize_stock(stock)}

class UserCreate(BaseModel):
    username: str
    password: str
    branch_id: int


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    branch_id: int | None = None


@app.get("/api/users")
def list_users(user: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """List all users (admin only)."""
    users = db.scalars(select(models.User).order_by(models.User.id)).all()
    return {"users": [serialize_user(u) for u in users]}


@app.post("/api/users", status_code=201)
def create_user(body: UserCreate, user: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Create a common user; the role is always forced to 'common'."""
    username = (body.username or "").strip()
    if not username or not body.password:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur et mot de passe requis")
    if db.scalar(select(models.User).where(models.User.username == username)):
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà")
    branch = db.get(models.Branch, body.branch_id)
    if branch is None:
        raise HTTPException(status_code=400, detail="Un branch_id valide est requis")
    new_user = models.User(
        username=username,
        password_hash=hash_password(body.password),
        role=ROLE_COMMON,
        branch_id=branch.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"user": serialize_user(new_user)}


@app.patch("/api/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, user: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Update username / password / branch of a common user; admin is protected."""
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Le compte admin ne peut pas être modifié")
    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Le nom d'utilisateur ne peut pas être vide")
        taken = db.scalar(select(models.User).where(models.User.username == username))
        if taken and taken.id != target.id:
            raise HTTPException(status_code=409, detail="Ce nom d'utilisateur existe déjà")
        target.username = username
    if body.password is not None:
        if not body.password:
            raise HTTPException(status_code=400, detail="Le mot de passe ne peut pas être vide")
        target.password_hash = hash_password(body.password)
    if body.branch_id is not None:
        branch = db.get(models.Branch, body.branch_id)
        if branch is None:
            raise HTTPException(status_code=400, detail="branch_id invalide")
        target.branch_id = branch.id
    db.commit()
    db.refresh(target)
    return {"user": serialize_user(target)}


@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, user: models.User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """Soft-delete a common user; the row stays, login is blocked."""
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Le compte admin ne peut pas être supprimé")
    target.is_deleted = True
    db.commit()
    db.refresh(target)
    return {"user": serialize_user(target)}

@app.get("/api/products")
def list_products(user: models.User = Depends(get_current_user)) -> dict:
    """List products from the external Product API (via Tom's MCP bridge)."""
    result = product_client.list_products()
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("message", "Product API unavailable"))
    return {"products": result["products"], "count": result["count"]}


@app.get("/api/products/{product_id}")
def get_product(product_id: str, user: models.User = Depends(get_current_user)) -> dict:
    """Get one product's details from the external Product API."""
    result = product_client.get_product(product_id)
    if not result.get("success"):
        status = 404 if result.get("error_type") == "not_found" else 502
        raise HTTPException(status_code=status, detail=result.get("message", "Product API unavailable"))
    return {"product": result["product"]}

SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY", "dev-service-key")


def require_service_key(x_api_key: str | None = Header(default=None)) -> None:
    """Guard internal endpoints for the AI service with a shared key."""
    if x_api_key != SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="Clé de service invalide")


@app.get("/api/stock/product/{product_id}")
def stock_by_product(
    product_id: str,
    _guard: None = Depends(require_service_key),
    db: Session = Depends(get_db),
) -> dict:
    """Read-only stock of a product across branches (internal AI endpoint)."""
    rows = db.execute(
        select(models.Stock, models.Branch)
        .join(models.Branch, models.Stock.branch_id == models.Branch.id)
        .where(models.Stock.product_id == product_id)
        .order_by(models.Branch.name)
    ).all()
    stock = [{"branch": branch.name, "quantity": row.quantity} for row, branch in rows]
    if stock:
        return {"success": True, "product_id": product_id, "stock": stock}
    # No local stock: distinguish "unknown product" from "known but empty".
    product = product_client.get_product(product_id)
    if not product.get("success"):
        return {
            "success": False,
            "error_type": "not_found",
            "message": product.get("message", "Product not found"),
        }
    return {"success": True, "product_id": product_id, "stock": []}


@app.get("/api/stock/branch/{branch_name}")
def stock_by_branch(
    branch_name: str,
    _guard: None = Depends(require_service_key),
    db: Session = Depends(get_db),
) -> dict:
    """Read-only stock of one branch (internal AI endpoint)."""
    branch = db.scalar(
        select(models.Branch).where(models.Branch.name.ilike(branch_name))
    )
    if branch is None:
        return {
            "success": False,
            "error_type": "not_found",
            "message": f"Branch '{branch_name}' not found",
        }
    rows = db.scalars(
        select(models.Stock)
        .where(models.Stock.branch_id == branch.id)
        .order_by(models.Stock.product_id)
    ).all()
    return {
        "success": True,
        "branch": branch.name,
        "stock": [{"product_id": s.product_id, "quantity": s.quantity} for s in rows],
    }
