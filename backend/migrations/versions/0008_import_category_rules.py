"""Add optional, review-only category suggestion rules."""
from alembic import op
import sqlalchemy as sa

revision = "0008_import_category_rules"
down_revision = "0007_bank_integrations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("import_category_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phrase", sa.String(120), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="RESTRICT")),
        sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id", ondelete="RESTRICT")),
        sa.Column("active", sa.Integer, nullable=False),
        sa.CheckConstraint("length(trim(phrase)) > 0", name="ck_import_category_rule_phrase"),
        sa.CheckConstraint("NOT (account_id IS NOT NULL AND card_id IS NOT NULL)", name="ck_import_category_rule_target"))


def downgrade():
    op.drop_table("import_category_rules")
