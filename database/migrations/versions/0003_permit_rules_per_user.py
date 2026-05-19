from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0003_permit_rules_per_user"
down_revision = "0002_key_permit_access"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("permit_open_rules") as batch_op:
        batch_op.add_column(sa.Column("tunnel_user_id", sa.Integer(), nullable=True))

    conn.execute(
        text(
            """
            UPDATE permit_open_rules
            SET tunnel_user_id = (
                SELECT k.tunnel_user_id
                FROM ssh_key_permit_rules j
                INNER JOIN ssh_keys k ON k.id = j.ssh_key_id
                WHERE j.permit_open_rule_id = permit_open_rules.id
                LIMIT 1
            )
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE permit_open_rules
            SET tunnel_user_id = (SELECT id FROM tunnel_users ORDER BY id LIMIT 1)
            WHERE tunnel_user_id IS NULL
            """
        )
    )

    with op.batch_alter_table("permit_open_rules") as batch_op:
        batch_op.alter_column("tunnel_user_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_permit_open_rules_tunnel_user_id",
            "tunnel_users",
            ["tunnel_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_permit_open_rules_tunnel_user_id", ["tunnel_user_id"])
        batch_op.drop_constraint("uq_host_port", type_="unique")
        batch_op.create_unique_constraint("uq_user_host_port", ["tunnel_user_id", "host", "port"])


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for 0003_permit_rules_per_user")
