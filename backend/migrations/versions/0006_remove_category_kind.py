"""remove category kind

Revision ID: 0006_remove_category_kind
Revises: 0005_investment_withdrawals
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_remove_category_kind"
down_revision = "0005_investment_withdrawals"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite batch migrations are not transactional. If the process is
    # interrupted after Alembic creates its working table, the table remains
    # behind and every subsequent startup fails before it can retry.
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_categories")
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_index("ix_categories_kind_archived")
        batch_op.drop_constraint("ck_categories_kind", type_="check")
        batch_op.drop_column("kind")
        batch_op.create_index("ix_categories_archived_at", ["archived_at"], unique=False)


def downgrade():
    with op.batch_alter_table("categories", schema=None) as batch_op:
        batch_op.drop_index("ix_categories_archived_at")
        batch_op.add_column(sa.Column("kind", sa.String(length=16), nullable=False, server_default="expense"))
        batch_op.create_check_constraint("ck_categories_kind", "kind IN ('income','expense')")
        batch_op.create_index("ix_categories_kind_archived", ["kind", "archived_at"], unique=False)

