from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target", sa.String(length=120), nullable=False),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])

    op.create_table(
        "tunnel_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("linux_home", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_tunnel_users_id", "tunnel_users", ["id"])
    op.create_index("ix_tunnel_users_username", "tunnel_users", ["username"], unique=True)

    op.create_table(
        "ssh_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tunnel_user_id", sa.Integer(), sa.ForeignKey("tunnel_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("tunnel_user_id", "public_key", name="uq_user_public_key"),
    )
    op.create_index("ix_ssh_keys_id", "ssh_keys", ["id"])
    op.create_index("ix_ssh_keys_tunnel_user_id", "ssh_keys", ["tunnel_user_id"])

    op.create_table(
        "permit_open_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tunnel_user_id", sa.Integer(), sa.ForeignKey("tunnel_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("tunnel_user_id", "host", "port", name="uq_user_host_port"),
    )
    op.create_index("ix_permit_open_rules_id", "permit_open_rules", ["id"])
    op.create_index("ix_permit_open_rules_tunnel_user_id", "permit_open_rules", ["tunnel_user_id"])


def downgrade() -> None:
    op.drop_index("ix_permit_open_rules_tunnel_user_id", table_name="permit_open_rules")
    op.drop_index("ix_permit_open_rules_id", table_name="permit_open_rules")
    op.drop_table("permit_open_rules")

    op.drop_index("ix_ssh_keys_tunnel_user_id", table_name="ssh_keys")
    op.drop_index("ix_ssh_keys_id", table_name="ssh_keys")
    op.drop_table("ssh_keys")

    op.drop_index("ix_tunnel_users_username", table_name="tunnel_users")
    op.drop_index("ix_tunnel_users_id", table_name="tunnel_users")
    op.drop_table("tunnel_users")

    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
