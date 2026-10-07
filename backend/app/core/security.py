"""
security.py — Password hashing, JWT token creation and verification,
              role-based access control dependency injection.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logger import log_security

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── OAuth2 scheme ─────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# ── Hashing helpers ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return bcrypt hash of password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── FastAPI dependency injection ──────────────────────────────────────────────

def get_db():
    """Dependency: yields a SQLAlchemy database session."""
    from app.models.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Dependency: decode JWT and return the authenticated user ORM object."""
    from app.models.user import User
    payload = decode_token(token)
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(User).filter(User.username == username, User.is_active == True).first()
    if user is None:
        log_security("auth_failure", username, "User not found or inactive")
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(current_user=Depends(get_current_user)):
    """Dependency: require ADMIN role."""
    if current_user.role != "ADMIN":
        log_security("authz_failure", current_user.username, "Admin role required")
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def require_manager_or_admin(current_user=Depends(get_current_user)):
    """Dependency: require WAREHOUSE_MANAGER or ADMIN role."""
    if current_user.role not in ("ADMIN", "WAREHOUSE_MANAGER"):
        log_security("authz_failure", current_user.username, "Insufficient role")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user
