"""add investment withdrawals

Revision ID: 0005_investment_withdrawals
Revises: 0004_daily_investment_yields
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_investment_withdrawals"
down_revision = "0004_daily_investment_yields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investment_withdrawals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("investment_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("withdrawal_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("balance_before_minor", sa.Integer(), nullable=False),
        sa.Column("balance_after_minor", sa.Integer(), nullable=False),
        sa.Column("cash_entry_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("amount_minor BETWEEN 1 AND 9007199254740991", name="ck_investment_withdrawals_safe_amount"),
        sa.ForeignKeyConstraint(["investment_id"], ["investments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cash_entry_id"], ["cash_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cash_entry_id"),
    )
    op.create_index("ix_investment_withdrawals_date", "investment_withdrawals", ["withdrawal_date"])


def downgrade():
    op.drop_index("ix_investment_withdrawals_date", table_name="investment_withdrawals")
    op.drop_table("investment_withdrawals")
