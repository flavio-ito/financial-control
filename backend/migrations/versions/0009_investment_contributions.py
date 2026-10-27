"""add investment contributions

Revision ID: 0009_investment_contributions
Revises: 0008_import_category_rules
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_investment_contributions"
down_revision = "0008_import_category_rules"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investment_contributions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("investment_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("contribution_date", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("balance_before_minor", sa.Integer(), nullable=False),
        sa.Column("balance_after_minor", sa.Integer(), nullable=False),
        sa.Column("cash_entry_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("amount_minor BETWEEN 1 AND 9007199254740991", name="ck_investment_contributions_safe_amount"),
        sa.ForeignKeyConstraint(["investment_id"], ["investments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cash_entry_id"], ["cash_entries.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cash_entry_id"),
    )
    op.create_index("ix_investment_contributions_date", "investment_contributions", ["contribution_date"])


def downgrade():
    op.drop_index("ix_investment_contributions_date", table_name="investment_contributions")
    op.drop_table("investment_contributions")
