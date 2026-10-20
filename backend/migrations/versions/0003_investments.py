"""add investments

Revision ID: 0003_investments
Revises: 0002_domain_schema
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_investments"
down_revision = "0002_domain_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "investments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("cdi_percentage", sa.Integer(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_minor BETWEEN 0 AND 9007199254740991", name="ck_investments_safe_amount"),
        sa.CheckConstraint("cdi_percentage BETWEEN 0 AND 100000", name="ck_investments_cdi_percentage"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_investments_account", "investments", ["account_id"])
    op.create_index("ix_investments_archived_at", "investments", ["archived_at"])


def downgrade():
    op.drop_index("ix_investments_archived_at", table_name="investments")
    op.drop_index("ix_investments_account", table_name="investments")
    op.drop_table("investments")
