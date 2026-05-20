from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class SSHKeyUserAssignment(Base):
    __tablename__ = "ssh_key_user_assignments"

    ssh_key_id: Mapped[int] = mapped_column(
        ForeignKey("ssh_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tunnel_user_id: Mapped[int] = mapped_column(
        ForeignKey("tunnel_users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    ssh_key = relationship("SSHKey", back_populates="user_assignments")
    tunnel_user = relationship("TunnelUser", back_populates="key_assignments")
