from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0004_global_keys_multi_user"
down_revision = "0003_permit_rules_per_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "ssh_key_user_assignments",
        sa.Column("ssh_key_id", sa.Integer(), sa.ForeignKey("ssh_keys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "tunnel_user_id",
            sa.Integer(),
            sa.ForeignKey("tunnel_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    conn.execute(
        text(
            """
            INSERT INTO ssh_key_user_assignments (ssh_key_id, tunnel_user_id)
            SELECT id, tunnel_user_id FROM ssh_keys
            """
        )
    )

    op.create_table(
        "ssh_key_permit_rules_new",
        sa.Column("ssh_key_id", sa.Integer(), sa.ForeignKey("ssh_keys.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "tunnel_user_id",
            sa.Integer(),
            sa.ForeignKey("tunnel_users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "permit_open_rule_id",
            sa.Integer(),
            sa.ForeignKey("permit_open_rules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    conn.execute(
        text(
            """
            INSERT INTO ssh_key_permit_rules_new (ssh_key_id, tunnel_user_id, permit_open_rule_id)
            SELECT j.ssh_key_id, k.tunnel_user_id, j.permit_open_rule_id
            FROM ssh_key_permit_rules j
            INNER JOIN ssh_keys k ON k.id = j.ssh_key_id
            """
        )
    )

    op.drop_table("ssh_key_permit_rules")
    op.rename_table("ssh_key_permit_rules_new", "ssh_key_permit_rules")

    with op.batch_alter_table("ssh_keys") as batch_op:
        try:
            batch_op.drop_index("ix_ssh_keys_tunnel_user_id")
        except Exception:
            pass
        batch_op.drop_column("tunnel_user_id")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for 0004_global_keys_multi_user")
