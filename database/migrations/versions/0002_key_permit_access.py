from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0002_key_permit_access"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "ssh_key_permit_rules",
        sa.Column("ssh_key_id", sa.Integer(), sa.ForeignKey("ssh_keys.id", ondelete="CASCADE"), primary_key=True),
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
            INSERT INTO ssh_key_permit_rules (ssh_key_id, permit_open_rule_id)
            SELECT k.id, r.id
            FROM ssh_keys k
            INNER JOIN permit_open_rules r ON k.tunnel_user_id = r.tunnel_user_id
            """
        )
    )

    op.create_table(
        "permit_open_rules_new",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alias", sa.String(length=100), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("host", "port", name="uq_host_port"),
    )

    old_rules = conn.execute(
        text("SELECT id, alias, host, port, comment, created_at, enabled FROM permit_open_rules ORDER BY id")
    ).fetchall()

    old_to_new: dict[int, int] = {}
    canonical_by_host_port: dict[tuple[str, int], int] = {}

    for rule in old_rules:
        host_port = (rule.host, rule.port)
        if host_port not in canonical_by_host_port:
            conn.execute(
                text(
                    """
                    INSERT INTO permit_open_rules_new (id, alias, host, port, comment, created_at, enabled)
                    VALUES (:id, :alias, :host, :port, :comment, :created_at, :enabled)
                    """
                ),
                {
                    "id": rule.id,
                    "alias": rule.alias,
                    "host": rule.host,
                    "port": rule.port,
                    "comment": rule.comment,
                    "created_at": rule.created_at,
                    "enabled": int(rule.enabled),
                },
            )
            canonical_by_host_port[host_port] = rule.id
        old_to_new[rule.id] = canonical_by_host_port[host_port]

    for old_id, new_id in old_to_new.items():
        if old_id != new_id:
            conn.execute(
                text(
                    """
                    UPDATE ssh_key_permit_rules
                    SET permit_open_rule_id = :new_id
                    WHERE permit_open_rule_id = :old_id
                    """
                ),
                {"old_id": old_id, "new_id": new_id},
            )

    conn.execute(
        text(
            """
            DELETE FROM ssh_key_permit_rules
            WHERE rowid NOT IN (
                SELECT MIN(rowid) FROM ssh_key_permit_rules GROUP BY ssh_key_id, permit_open_rule_id
            )
            """
        )
    )

    op.drop_table("permit_open_rules")
    op.rename_table("permit_open_rules_new", "permit_open_rules")
    op.create_index("ix_permit_open_rules_id", "permit_open_rules", ["id"])

    with op.batch_alter_table("ssh_keys") as batch_op:
        batch_op.drop_constraint("uq_user_public_key", type_="unique")
        batch_op.create_unique_constraint("uq_public_key", ["public_key"])


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for 0002_key_permit_access")
