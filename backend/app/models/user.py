"""
user.py — User ORM model with RBAC roles.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from app.models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=True)
    role = Column(
        Enum("ADMIN", "WAREHOUSE_MANAGER", name="user_role"),
        nullable=False,
        default="WAREHOUSE_MANAGER",
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User id={self.id} username={self.username} role={self.role}>"
