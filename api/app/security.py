# Password hashing (werkzeug scrypt) and JWT (HS256, 12h expiry).
import datetime as dt
import os

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
ALGO = "HS256"
TOKEN_HOURS = 12


def hash_password(plain: str) -> str:
    """Hash a plain-text password with werkzeug's scrypt."""
    return generate_password_hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain password against its stored hash."""
    return check_password_hash(hashed, plain)


def create_token(user) -> str:
    """Issue a signed JWT for a user (id + role), valid TOKEN_HOURS."""
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + dt.timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGO)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT; return its payload or None."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
    except jwt.PyJWTError:
        return None
