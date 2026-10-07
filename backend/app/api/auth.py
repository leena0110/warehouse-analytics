"""
auth.py — Authentication API routes: login, token, user info, logout.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.security import (
    verify_password, create_access_token, get_db,
    get_current_user, hash_password, require_admin,
)
from app.core.logger import log_event, log_security
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    full_name: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str | None = None
    role: str = "WAREHOUSE_MANAGER"


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/token", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate user and return JWT access token."""
    user = db.query(User).filter(
        User.username == form_data.username,
        User.is_active == True
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        log_security("login_failed", form_data.username, "Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(data={"sub": user.username, "role": user.role})
    log_event("user_login", user.username, f"role={user.role}")

    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username,
        full_name=user.full_name or "",
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user's profile."""
    return current_user


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Create a new user (admin only)."""
    if payload.role not in ("ADMIN", "WAREHOUSE_MANAGER"):
        raise HTTPException(400, detail="Invalid role. Must be ADMIN or WAREHOUSE_MANAGER.")

    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, detail="Username already exists.")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, detail="Email already registered.")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_event("user_created", _admin.username, f"new_user={user.username} role={user.role}")
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List all users (admin only)."""
    return db.query(User).all()


@router.put("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Deactivate a user account (admin only)."""
    if user_id == current_admin.id:
        raise HTTPException(400, detail="Cannot deactivate your own account.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="User not found.")
    user.is_active = False
    db.commit()
    log_event("user_deactivated", current_admin.username, f"target={user.username}")
    return {"message": f"User {user.username} deactivated."}


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change authenticated user's own password."""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(400, detail="Current password is incorrect.")
    if len(payload.new_password) < 8:
        raise HTTPException(400, detail="New password must be at least 8 characters.")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    log_event("password_changed", current_user.username)
    return {"message": "Password changed successfully."}
