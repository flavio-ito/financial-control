from datetime import datetime, timezone
import uuid

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import declarative_base

from app.config import SAFE_INTEGER_MAX

Base = declarative_base()
SAFE = str(SAFE_INTEGER_MAX)


def uuid4_string():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class MutableMixin:
    id = Column(String(36), primary_key=True, default=uuid4_string)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    revision = Column(Integer, nullable=False, default=1)


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (CheckConstraint("currency = 'BRL'", name="ck_settings_currency_brl"),)
    id = Column(Integer, primary_key=True)
    locale = Column(String(10), nullable=False, default="pt-BR")
    currency = Column(String(3), nullable=False, default="BRL")
    timezone = Column(String(64), nullable=False, default="America/Sao_Paulo")
    setup_step = Column(Integer, nullable=False, default=0)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Account(MutableMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("currency = 'BRL'", name="ck_accounts_currency_brl"),
        CheckConstraint("reference_balance_minor BETWEEN -{} AND {}".format(SAFE, SAFE), name="ck_accounts_safe_balance"),
        Index("ix_accounts_archived_at", "archived_at"),
    )
    name = Column(String(120), nullable=False)
    institution = Column(String(120))
    currency = Column(String(3), nullable=False, default="BRL")
    reference_date = Column(Date, nullable=False)
    reference_balance_minor = Column(Integer, nullable=False)
    archived_at = Column(DateTime(timezone=True))


class Card(MutableMixin, Base):
    __tablename__ = "cards"
    __table_args__ = (
        CheckConstraint("currency = 'BRL'", name="ck_cards_currency_brl"),
        CheckConstraint("limit_minor BETWEEN 0 AND {}".format(SAFE), name="ck_cards_safe_limit"),
        CheckConstraint("closing_day BETWEEN 1 AND 31", name="ck_cards_closing_day"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="ck_cards_due_day"),
        Index("ix_cards_default_account", "default_account_id"),
        Index("ix_cards_archived_at", "archived_at"),
    )
    name = Column(String(120), nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    limit_minor = Column(Integer, nullable=False)
    closing_day = Column(Integer, nullable=False)
    due_day = Column(Integer, nullable=False)
    default_account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"))
    archived_at = Column(DateTime(timezone=True))


class Category(MutableMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("kind IN ('income','expense')", name="ck_categories_kind"),
        Index("ix_categories_kind_archived", "kind", "archived_at"),
    )
    name = Column(String(120), nullable=False)
    kind = Column(String(16), nullable=False)
    archived_at = Column(DateTime(timezone=True))


class Transfer(MutableMixin, Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("from_account_id <> to_account_id", name="ck_transfers_distinct_accounts"),
        CheckConstraint("amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_transfers_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_transfers_currency_brl"),
        CheckConstraint("status IN ('planned','effective','cancelled','reversed')", name="ck_transfers_status"),
        Index("ix_transfers_from_date", "from_account_id", "effective_date"),
        Index("ix_transfers_to_date", "to_account_id", "effective_date"),
        Index("ix_transfers_status", "status"),
    )
    from_account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    to_account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    planned_date = Column(Date, nullable=False)
    effective_date = Column(Date)
    status = Column(String(16), nullable=False)
    reversal_of = Column(String(36), ForeignKey("transfers.id", ondelete="RESTRICT"))
    reason = Column(Text)


class CashEntry(MutableMixin, Base):
    __tablename__ = "cash_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('income','expense','transfer_in','transfer_out','invoice_payment','refund','balance_adjustment')", name="ck_cash_entries_kind"),
        CheckConstraint("status IN ('planned','effective','cancelled','voided')", name="ck_cash_entries_status"),
        CheckConstraint("source IN ('manual','opening','recurrence','file_import','bank_api')", name="ck_cash_entries_source"),
        CheckConstraint("currency = 'BRL'", name="ck_cash_entries_currency_brl"),
        CheckConstraint("signed_amount_minor BETWEEN -{} AND {} AND signed_amount_minor <> 0".format(SAFE, SAFE), name="ck_cash_entries_safe_amount"),
        Index("ix_cash_entries_account_date", "account_id", "effective_date"),
        Index("ix_cash_entries_planned_date", "planned_date"),
        Index("ix_cash_entries_category", "category_id"),
        Index("ix_cash_entries_status_source", "status", "source"),
        Index("ix_cash_entries_transfer", "transfer_id"),
        Index("ix_cash_entries_payment", "payment_id"),
        Index("ix_cash_entries_recurrence", "recurrence_occurrence_id"),
    )
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    kind = Column(String(32), nullable=False)
    description = Column(String(240), nullable=False)
    note = Column(Text)
    signed_amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    planned_date = Column(Date, nullable=False)
    effective_date = Column(Date)
    status = Column(String(16), nullable=False)
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    transfer_id = Column(String(36), ForeignKey("transfers.id", ondelete="RESTRICT"))
    payment_id = Column(String(36), ForeignKey("payments.id", ondelete="RESTRICT"))
    recurrence_occurrence_id = Column(String(36), ForeignKey("recurrence_occurrences.id", ondelete="RESTRICT"))
    refund_id = Column(String(36), ForeignKey("refunds.id", ondelete="RESTRICT"))
    reversal_of_id = Column(String(36), ForeignKey("cash_entries.id", ondelete="RESTRICT"))
    source = Column(String(24), nullable=False, default="manual")
    external_id = Column(String(160))
    source_connection_id = Column(String(160))


class PlannedCardPurchase(MutableMixin, Base):
    __tablename__ = "planned_card_purchases"
    __table_args__ = (
        CheckConstraint("expected_amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_planned_purchases_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_planned_purchases_currency_brl"),
        CheckConstraint("status IN ('planned','confirmed','cancelled')", name="ck_planned_purchases_status"),
        CheckConstraint("(status = 'confirmed' AND confirmed_purchase_id IS NOT NULL) OR (status <> 'confirmed' AND confirmed_purchase_id IS NULL)", name="ck_planned_purchases_confirmation_link"),
        Index("ix_planned_purchases_card_month", "card_id", "estimated_invoice_month"),
        Index("ix_planned_purchases_category", "category_id"),
        Index("ix_planned_purchases_status_date", "status", "expected_date"),
    )
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False)
    description = Column(String(240), nullable=False)
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    expected_date = Column(Date, nullable=False)
    expected_amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    estimated_invoice_month = Column(String(7), nullable=False)
    status = Column(String(16), nullable=False, default="planned")
    confirmed_purchase_id = Column(String(36), ForeignKey("purchases.id", ondelete="RESTRICT"), unique=True)


class Purchase(MutableMixin, Base):
    __tablename__ = "purchases"
    __table_args__ = (
        CheckConstraint("total_minor BETWEEN 1 AND {}".format(SAFE), name="ck_purchases_safe_total"),
        CheckConstraint("installment_count >= 1 AND installment_count <= total_minor", name="ck_purchases_installments"),
        CheckConstraint("currency = 'BRL'", name="ck_purchases_currency_brl"),
        CheckConstraint("source IN ('manual','opening','recurrence','file_import','bank_api')", name="ck_purchases_source"),
        CheckConstraint("status IN ('confirmed','voided')", name="ck_purchases_status"),
        Index("ix_purchases_card_date", "card_id", "purchase_date"),
        Index("ix_purchases_category", "category_id"),
        Index("ix_purchases_status_source", "status", "source"),
        Index("ix_purchases_recurrence", "recurrence_occurrence_id"),
    )
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False)
    description = Column(String(240), nullable=False)
    purchase_date = Column(Date, nullable=False)
    total_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    installment_count = Column(Integer, nullable=False)
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    source = Column(String(24), nullable=False, default="manual")
    recurrence_occurrence_id = Column(String(36), ForeignKey("recurrence_occurrences.id", ondelete="RESTRICT"))
    planned_card_purchase_id = Column(String(36), ForeignKey("planned_card_purchases.id", ondelete="RESTRICT"), unique=True)
    status = Column(String(16), nullable=False, default="confirmed")
    external_id = Column(String(160))
    source_connection_id = Column(String(160))


class Invoice(MutableMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("card_id", "reference_month", name="uq_invoices_card_month"),
        CheckConstraint("state IN ('open','closed','settled')", name="ck_invoices_state"),
        CheckConstraint("closing_date < due_date", name="ck_invoices_dates"),
        Index("ix_invoices_card_due", "card_id", "due_date"),
        Index("ix_invoices_state_due", "state", "due_date"),
    )
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="RESTRICT"), nullable=False)
    reference_month = Column(String(7), nullable=False)
    closing_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    state = Column(String(16), nullable=False, default="open")


class Installment(MutableMixin, Base):
    __tablename__ = "installments"
    __table_args__ = (
        UniqueConstraint("purchase_id", "installment_number", name="uq_installments_purchase_number"),
        CheckConstraint("amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_installments_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_installments_currency_brl"),
        CheckConstraint("status IN ('confirmed','cancelled','historical_settled')", name="ck_installments_status"),
        Index("ix_installments_invoice_status", "invoice_id", "status"),
        Index("ix_installments_category", "category_id_snapshot"),
    )
    purchase_id = Column(String(36), ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=False)
    installment_number = Column(Integer, nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    category_id_snapshot = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    status = Column(String(24), nullable=False, default="confirmed")
    cancellation_date = Column(Date)
    cancellation_reason = Column(Text)


class InvoiceAdjustment(MutableMixin, Base):
    __tablename__ = "invoice_adjustments"
    __table_args__ = (
        CheckConstraint("signed_amount_minor BETWEEN -{} AND {} AND signed_amount_minor <> 0".format(SAFE, SAFE), name="ck_invoice_adjustments_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_invoice_adjustments_currency_brl"),
        CheckConstraint("kind IN ('opening','debit','refund','credit_carry')", name="ck_invoice_adjustments_kind"),
        CheckConstraint("status IN ('active','cancelled','consumed')", name="ck_invoice_adjustments_status"),
        Index("ix_invoice_adjustments_invoice_status", "invoice_id", "status"),
        Index("ix_invoice_adjustments_category", "category_id"),
        Index("uq_active_carry_origin", "origin_invoice_id", unique=True, sqlite_where=text("kind = 'credit_carry' AND status = 'active'")),
    )
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    signed_amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    kind = Column(String(24), nullable=False)
    description = Column(String(240), nullable=False)
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    refund_id = Column(String(36), ForeignKey("refunds.id", ondelete="RESTRICT"))
    origin_invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"))
    status = Column(String(16), nullable=False, default="active")


class InvoicePaymentPlan(MutableMixin, Base):
    __tablename__ = "invoice_payment_plans"
    __table_args__ = (
        CheckConstraint("status IN ('active','cancelled')", name="ck_invoice_payment_plans_status"),
        Index("ix_invoice_payment_plans_date", "planned_date"),
        Index("uq_active_invoice_payment_plan", "invoice_id", unique=True, sqlite_where=text("status = 'active'")),
    )
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    planned_date = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="active")


class Payment(MutableMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor BETWEEN 0 AND {}".format(SAFE), name="ck_payments_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_payments_currency_brl"),
        CheckConstraint("status IN ('active','reversed')", name="ck_payments_status"),
        Index("ix_payments_account_date", "account_id", "paid_date"),
        Index("uq_active_payment_invoice", "invoice_id", unique=True, sqlite_where=text("status = 'active'")),
    )
    invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    paid_date = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, default="active")
    reversal_of = Column(String(36), ForeignKey("payments.id", ondelete="RESTRICT"))
    cash_entry_id = Column(String(36), ForeignKey("cash_entries.id", ondelete="RESTRICT"), unique=True)


class Refund(MutableMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_refunds_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_refunds_currency_brl"),
        CheckConstraint("status IN ('planned','confirmed','cancelled')", name="ck_refunds_status"),
        CheckConstraint("target_kind IN ('invoice','account')", name="ck_refunds_target_kind"),
        CheckConstraint("(purchase_id IS NOT NULL AND original_cash_entry_id IS NULL) OR (purchase_id IS NULL AND original_cash_entry_id IS NOT NULL)", name="ck_refunds_single_origin"),
        CheckConstraint("(target_kind = 'invoice' AND target_invoice_id IS NOT NULL AND target_account_id IS NULL) OR (target_kind = 'account' AND target_account_id IS NOT NULL AND target_invoice_id IS NULL)", name="ck_refunds_single_target"),
        Index("ix_refunds_purchase", "purchase_id"),
        Index("ix_refunds_cash_entry", "original_cash_entry_id"),
        Index("ix_refunds_status_date", "status", "recognition_date"),
    )
    purchase_id = Column(String(36), ForeignKey("purchases.id", ondelete="RESTRICT"))
    original_cash_entry_id = Column(String(36), ForeignKey("cash_entries.id", ondelete="RESTRICT"))
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    status = Column(String(16), nullable=False)
    planned_date = Column(Date, nullable=False)
    recognition_date = Column(Date)
    target_kind = Column(String(16), nullable=False)
    target_invoice_id = Column(String(36), ForeignKey("invoices.id", ondelete="RESTRICT"))
    target_account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"))
    reason = Column(Text, nullable=False)


class RecurrenceRule(MutableMixin, Base):
    __tablename__ = "recurrence_rules"
    __table_args__ = (
        UniqueConstraint("series_id", "version", name="uq_recurrence_rules_series_version"),
        CheckConstraint("kind IN ('income','expense','card_purchase')", name="ck_recurrence_rules_kind"),
        CheckConstraint("day BETWEEN 1 AND 31", name="ck_recurrence_rules_day"),
        CheckConstraint("amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_recurrence_rules_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_recurrence_rules_currency_brl"),
        CheckConstraint("(kind IN ('income','expense') AND account_id IS NOT NULL AND card_id IS NULL) OR (kind = 'card_purchase' AND card_id IS NOT NULL AND account_id IS NULL)", name="ck_recurrence_rules_target"),
        Index("ix_recurrence_rules_series_active", "series_id", "active"),
        Index("ix_recurrence_rules_account", "account_id"),
        Index("ix_recurrence_rules_card", "card_id"),
    )
    series_id = Column(String(36), nullable=False, default=uuid4_string)
    version = Column(Integer, nullable=False, default=1)
    kind = Column(String(24), nullable=False)
    description = Column(String(240), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"))
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="RESTRICT"))
    day = Column(Integer, nullable=False)
    start_month = Column(String(7), nullable=False)
    end_month = Column(String(7))
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"))
    active = Column(Integer, nullable=False, default=1)


class RecurrenceOccurrence(MutableMixin, Base):
    __tablename__ = "recurrence_occurrences"
    __table_args__ = (
        CheckConstraint("status IN ('planned','confirmed','cancelled','superseded')", name="ck_recurrence_occurrences_status"),
        CheckConstraint("expected_amount_minor BETWEEN 1 AND {}".format(SAFE), name="ck_recurrence_occurrences_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_recurrence_occurrences_currency_brl"),
        Index("ix_recurrence_occurrences_rule", "rule_id"),
        Index("ix_recurrence_occurrences_series_month", "series_id", "occurrence_month"),
        Index("ix_recurrence_occurrences_status_date", "status", "expected_date"),
        Index("uq_active_recurrence_series_month", "series_id", "occurrence_month", unique=True, sqlite_where=text("status <> 'superseded'")),
    )
    series_id = Column(String(36), nullable=False)
    rule_id = Column(String(36), ForeignKey("recurrence_rules.id", ondelete="RESTRICT"), nullable=False)
    occurrence_month = Column(String(7), nullable=False)
    expected_date = Column(Date, nullable=False)
    expected_amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")
    status = Column(String(16), nullable=False, default="planned")
    exception = Column(Integer, nullable=False, default=0)
    linked_cash_entry_id = Column(String(36), ForeignKey("cash_entries.id", ondelete="RESTRICT"), unique=True)
    linked_purchase_id = Column(String(36), ForeignKey("purchases.id", ondelete="RESTRICT"), unique=True)
    superseded_by_rule_id = Column(String(36), ForeignKey("recurrence_rules.id", ondelete="RESTRICT"))


class BudgetDefault(MutableMixin, Base):
    __tablename__ = "budget_defaults"
    __table_args__ = (
        UniqueConstraint("category_id", "effective_from_month", name="uq_budget_defaults_category_month"),
        CheckConstraint("amount_minor BETWEEN 0 AND {}".format(SAFE), name="ck_budget_defaults_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_budget_defaults_currency_brl"),
        Index("ix_budget_defaults_effective", "effective_from_month"),
    )
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    effective_from_month = Column(String(7), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")


class Budget(MutableMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("category_id", "month", name="uq_budgets_category_month"),
        CheckConstraint("amount_minor BETWEEN 0 AND {}".format(SAFE), name="ck_budgets_safe_amount"),
        CheckConstraint("currency = 'BRL'", name="ck_budgets_currency_brl"),
        Index("ix_budgets_month", "month"),
    )
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False)
    month = Column(String(7), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False, default="BRL")


class CoverageInterval(MutableMixin, Base):
    __tablename__ = "coverage_intervals"
    __table_args__ = (
        CheckConstraint("status IN ('complete','partial','unknown')", name="ck_coverage_intervals_status"),
        CheckConstraint("date_from <= date_to", name="ck_coverage_intervals_dates"),
        CheckConstraint("(account_id IS NOT NULL AND card_id IS NULL) OR (account_id IS NULL AND card_id IS NOT NULL)", name="ck_coverage_intervals_owner"),
        Index("ix_coverage_intervals_account_dates", "account_id", "date_from", "date_to"),
        Index("ix_coverage_intervals_card_dates", "card_id", "date_from", "date_to"),
    )
    account_id = Column(String(36), ForeignKey("accounts.id", ondelete="RESTRICT"))
    card_id = Column(String(36), ForeignKey("cards.id", ondelete="RESTRICT"))
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=False)
    status = Column(String(16), nullable=False)
    note = Column(Text)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("key", "operation_scope", name="uq_idempotency_key_scope"), Index("ix_idempotency_created_at", "created_at"))
    id = Column(String(36), primary_key=True, default=uuid4_string)
    key = Column(String(160), nullable=False)
    operation_scope = Column(String(160), nullable=False)
    request_hash = Column(String(64), nullable=False)
    result_status = Column(String(24), nullable=False)
    response_code = Column(Integer, nullable=False)
    response_body = Column(Text)
    result_reference = Column(String(160))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_entity", "entity_type", "entity_id"), Index("ix_audit_events_occurred_at", "occurred_at"))
    id = Column(String(36), primary_key=True, default=uuid4_string)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(36), nullable=False)
    action = Column(String(80), nullable=False)
    before_json = Column(Text)
    after_json = Column(Text)
    reason = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class BackupRun(Base):
    __tablename__ = "backup_runs"
    __table_args__ = (CheckConstraint("status IN ('started','succeeded','failed')", name="ck_backup_runs_status"), Index("ix_backup_runs_created_status", "created_at", "status"))
    id = Column(String(36), primary_key=True, default=uuid4_string)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    destination = Column(Text, nullable=False)
    status = Column(String(16), nullable=False)
    checksum = Column(String(64))
    app_version = Column(String(32), nullable=False)
    alembic_revision = Column(String(64), nullable=False)
    backup_format_version = Column(Integer, nullable=False)
    error_message = Column(Text)

