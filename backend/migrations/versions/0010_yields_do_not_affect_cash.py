"""keep investment yields out of bank-account balances

Revision ID: 0010_yields_do_not_affect_cash
Revises: 0009_investment_contributions
"""
from alembic import op


revision = "0010_yields_do_not_affect_cash"
down_revision = "0009_investment_contributions"
branch_labels = None
depends_on = None


def upgrade():
    # Older versions materialized each CDI yield both in the investment and as
    # effective cash income. Preserve those rows and their possible integration
    # links, but void their effect on the associated bank-account balance.
    op.execute(
        """
        UPDATE cash_entries
        SET status = 'voided', updated_at = CURRENT_TIMESTAMP, revision = revision + 1
        WHERE status = 'effective'
          AND id IN (
            SELECT cash_entry_id
            FROM investment_yields
            WHERE cash_entry_id IS NOT NULL
        )
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE cash_entries
        SET status = 'effective', updated_at = CURRENT_TIMESTAMP, revision = revision + 1
        WHERE id IN (
            SELECT cash_entry_id
            FROM investment_yields
            WHERE cash_entry_id IS NOT NULL
        )
        """
    )
