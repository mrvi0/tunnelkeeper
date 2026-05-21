from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0005_sshd_config_architecture"
down_revision = "0004_global_keys_multi_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "tunnel_destinations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("host", "port", name="uq_destination_host_port"),
    )

    conn.execute(
        text(
            """
            INSERT INTO tunnel_destinations (id, alias, host, port, comment, created_at, enabled)
            SELECT MIN(id), MIN(alias), host, port, MIN(comment), MIN(created_at), MAX(enabled)
            FROM permit_open_rules
            GROUP BY host, port
            """
        )
    )

    with op.batch_alter_table("tunnel_users") as batch_op:
        batch_op.add_column(
            sa.Column("linux_shell", sa.String(length=255), server_default="/usr/sbin/nologin", nullable=False)
        )
        batch_op.add_column(sa.Column("supplementary_groups", sa.String(length=500), server_default="", nullable=False))
        batch_op.add_column(
            sa.Column("allow_tcp_forwarding", sa.Boolean(), server_default=sa.true(), nullable=False)
        )
        batch_op.add_column(sa.Column("permit_tty", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("x11_forwarding", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(
            sa.Column("allow_agent_forwarding", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch_op.add_column(sa.Column("force_command", sa.Text(), server_default="", nullable=False))

    conn.execute(
        text(
            """
            UPDATE tunnel_users
            SET force_command = 'echo "Tunnel only";exit'
            WHERE force_command = '' OR force_command IS NULL
            """
        )
    )

    op.create_table(
        "tunnel_user_destinations",
        sa.Column("tunnel_user_id", sa.Integer(), sa.ForeignKey("tunnel_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "tunnel_destination_id",
            sa.Integer(),
            sa.ForeignKey("tunnel_destinations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    conn.execute(
        text(
            """
            INSERT OR IGNORE INTO tunnel_user_destinations (tunnel_user_id, tunnel_destination_id)
            SELECT r.tunnel_user_id, d.id
            FROM permit_open_rules r
            INNER JOIN tunnel_destinations d ON d.host = r.host AND d.port = r.port
            """
        )
    )

    with op.batch_alter_table("ssh_keys") as batch_op:
        batch_op.add_column(sa.Column("tunnel_user_id", sa.Integer(), nullable=True))

    conn.execute(
        text(
            """
            UPDATE ssh_keys SET tunnel_user_id = (
                SELECT MIN(a.tunnel_user_id)
                FROM ssh_key_user_assignments a
                WHERE a.ssh_key_id = ssh_keys.id
            )
            """
        )
    )

    conn.execute(
        text(
            """
            INSERT INTO ssh_keys (tunnel_user_id, name, public_key, fingerprint, created_at, enabled)
            SELECT a.tunnel_user_id, k.name, k.public_key, k.fingerprint, k.created_at, k.enabled
            FROM ssh_key_user_assignments a
            INNER JOIN ssh_keys k ON k.id = a.ssh_key_id
            WHERE a.tunnel_user_id > (
                SELECT MIN(a2.tunnel_user_id)
                FROM ssh_key_user_assignments a2
                WHERE a2.ssh_key_id = k.id
            )
            """
        )
    )

    conn.execute(text("DELETE FROM ssh_keys WHERE tunnel_user_id IS NULL"))

    with op.batch_alter_table("ssh_keys") as batch_op:
        batch_op.alter_column("tunnel_user_id", nullable=False)
        batch_op.create_foreign_key(
            "fk_ssh_keys_tunnel_user_id", "tunnel_users", ["tunnel_user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_ssh_keys_tunnel_user_id", ["tunnel_user_id"])
        try:
            batch_op.drop_constraint("uq_public_key", type_="unique")
        except ValueError:
            pass
        batch_op.create_unique_constraint("uq_user_public_key", ["tunnel_user_id", "public_key"])

    op.drop_table("ssh_key_permit_rules")
    op.drop_table("ssh_key_user_assignments")
    op.drop_table("permit_open_rules")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for 0005_sshd_config_architecture")
