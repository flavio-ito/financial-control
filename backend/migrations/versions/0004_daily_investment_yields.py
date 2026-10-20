"""add daily investment yields and configurable CDI

Revision ID: 0004_daily_investment_yields
Revises: 0003_investments
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_daily_investment_yields"
down_revision = "0003_investments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("settings", sa.Column("cdi_annual_rate_bps", sa.Integer(), nullable=False, server_default="1447"))
    op.create_table(
        "investment_yields",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("investment_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("yield_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("balance_before_minor", sa.Integer(), nullable=False),
        sa.Column("balance_after_minor", sa.Integer(), nullable=False),
        sa.Column("cdi_annual_rate_bps", sa.Integer(), nullable=False),
        sa.Column("investment_cdi_percentage", sa.Integer(), nullable=False),
        sa.Column("cash_entry_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint("amount_minor BETWEEN 0 AND 9007199254740991", name="ck_investment_yields_safe_amount"),
        sa.ForeignKeyConstraint(["investment_id"], ["investments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cash_entry_id"], ["cash_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investment_id", "yield_date", name="uq_investment_yields_investment_date"),
        sa.UniqueConstraint("cash_entry_id"),
    )
    op.create_index("ix_investment_yields_date", "investment_yields", ["yield_date"])
    op.create_index("ix_investment_yields_cash_entry", "investment_yields", ["cash_entry_id"])


def downgrade():
    op.drop_index("ix_investment_yields_cash_entry", table_name="investment_yields")
    op.drop_index("ix_investment_yields_date", table_name="investment_yields")
    op.drop_table("investment_yields")
    op.drop_column("settings", "cdi_annual_rate_bps")
