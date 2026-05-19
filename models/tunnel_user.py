from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class TunnelUser(Base):
    __tablename__ = "tunnel_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    comment: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    linux_home: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ssh_keys = relationship("SSHKey", back_populates="tunnel_user", cascade="all, delete-orphan")
    permit_open_rules = relationship("PermitOpenRule", back_populates="tunnel_user", cascade="all, delete-orphan")
