"""Remove online bank connections while preserving local file imports."""
from alembic import op
import sqlalchemy as sa


revision = "0011_remove_online_bank_connections"
down_revision = "0010_yields_do_not_affect_cash"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bank_sync_runs") as batch_op:
        batch_op.drop_column("connection_id")
    with op.batch_alter_table("external_accounts") as batch_op:
        batch_op.drop_column("connection_id")
    op.drop_table("bank_connections")


def downgrade():
    op.create_table(
        "bank_connections",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False),
        sa.Column("consent_expires_at", sa.String(40)),
        sa.Column("provider_updated_at", sa.String(40)),
        sa.Column("last_sync_at", sa.String(40)),
        sa.Column("error", sa.String(240)),
    )
    with op.batch_alter_table("external_accounts") as batch_op:
        batch_op.add_column(sa.Column("connection_id", sa.String(160)))
        batch_op.create_foreign_key("fk_external_accounts_connection", "bank_connections", ["connection_id"], ["id"], ondelete="RESTRICT")
    with op.batch_alter_table("bank_sync_runs") as batch_op:
        batch_op.add_column(sa.Column("connection_id", sa.String(160)))
        batch_op.create_foreign_key("fk_bank_sync_runs_connection", "bank_connections", ["connection_id"], ["id"], ondelete="RESTRICT")
