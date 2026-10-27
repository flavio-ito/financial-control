"""Add isolated bank integration records; preserve all financial tables."""
from alembic import op
import sqlalchemy as sa

revision = "0007_bank_integrations"
down_revision = "0006_remove_category_kind"
branch_labels = None
depends_on = None


def upgrade():
    # Copy the frozen definitions so future model edits cannot change this migration.
    op.create_table("bank_connections",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False),
        sa.Column("consent_expires_at", sa.String(40)),
        sa.Column("provider_updated_at", sa.String(40)),
        sa.Column("last_sync_at", sa.String(40)), sa.Column("error", sa.String(240)))
    op.create_table("external_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("external_id", sa.String(160), nullable=False),
        sa.Column("connection_id", sa.String(160), sa.ForeignKey("bank_connections.id", ondelete="RESTRICT")),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("currency", sa.String(8)),
        sa.Column("balance_minor", sa.Integer), sa.Column("limit_minor", sa.Integer),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id", ondelete="RESTRICT")),
        sa.Column("enabled", sa.Integer, nullable=False), sa.Column("last_sync_at", sa.String(40)),
        sa.UniqueConstraint("provider", "external_id", name="uq_external_account_identity"),
        sa.CheckConstraint("NOT (account_id IS NOT NULL AND card_id IS NOT NULL)", name="ck_external_single_target"))
    op.create_table("imported_transactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_account_id", sa.String(36), sa.ForeignKey("external_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False), sa.Column("import_id", sa.String(64)),
        sa.Column("transaction_date", sa.Date, nullable=False), sa.Column("description", sa.String(240), nullable=False),
        sa.Column("amount_minor", sa.Integer, nullable=False), sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("provider_status", sa.String(32), nullable=False), sa.Column("category", sa.String(160)),
        sa.Column("installment_number", sa.Integer), sa.Column("installment_count", sa.Integer),
        sa.Column("state", sa.String(16), nullable=False), sa.Column("review_reason", sa.String(240)),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("cash_entry_id", sa.String(36), sa.ForeignKey("cash_entries.id", ondelete="RESTRICT")),
        sa.Column("installment_id", sa.String(36), sa.ForeignKey("installments.id", ondelete="RESTRICT")),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id", ondelete="RESTRICT")),
        sa.Column("invoice_adjustment_id", sa.String(36), sa.ForeignKey("invoice_adjustments.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("external_account_id", "external_id", name="uq_imported_transaction_identity"),
        sa.CheckConstraint("state IN ('review','linked','ignored')", name="ck_imported_state"),
        sa.CheckConstraint("amount_minor BETWEEN -9007199254740991 AND 9007199254740991 AND amount_minor <> 0", name="ck_imported_amount"))
    op.create_table("bank_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("connection_id", sa.String(160), sa.ForeignKey("bank_connections.id", ondelete="RESTRICT")),
        sa.Column("finished_at", sa.String(40), nullable=False),
        *[sa.Column(name, sa.Integer, nullable=False) for name in ("new", "updated", "ignored", "review")],
        sa.Column("error", sa.String(240)))


def downgrade():
    # Explicit migration command only; the application never invokes downgrade.
    for table in ("bank_sync_runs", "imported_transactions", "external_accounts", "bank_connections"):
        op.drop_table(table)
