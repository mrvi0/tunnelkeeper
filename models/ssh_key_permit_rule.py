from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SSHKeyPermitRule(Base):
    __tablename__ = "ssh_key_permit_rules"

    ssh_key_id: Mapped[int] = mapped_column(
        ForeignKey("ssh_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permit_open_rule_id: Mapped[int] = mapped_column(
        ForeignKey("permit_open_rules.id", ondelete="CASCADE"),
        primary_key=True,
    )
