from datetime import date

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.domain.states import InvalidTransition, TRANSITIONS, ensure_transition
from app.storage.database import Database
from app.storage.migrations import alembic_config, current_revision, head_revision, migrate
from app.storage.models import (
    Account,
    Card,
    Category,
    Invoice,
    InvoicePaymentPlan,
    RecurrenceOccurrence,
    RecurrenceRule,
)

EXPECTED_TABLES = {
    "settings",
    "accounts",
    "cards",
    "categories",
    "cash_entries",
    "transfers",
    "planned_card_purchases",
    "purchases",
    "installments",
    "invoices",
    "invoice_adjustments",
    "invoice_payment_plans",
    "payments",
    "refunds",
    "recurrence_rules",
    "recurrence_occurrences",
    "budget_defaults",
    "budgets",
    "coverage_intervals",
    "idempotency_records",
    "audit_events",
    "backup_runs",
}


@pytest.fixture
def domain_db(tmp_path):
    path = tmp_path / "database.sqlite3"
    migrate(path, tmp_path / "backups")
    database = Database(path)
    yield database
    database.dispose()


def seed_account_card_category(session):
    account = Account(name="Conta sintética", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
    category = Category(name="Categoria sintética", kind="expense")
    session.add_all([account, category])
    session.flush()
    card = Card(name="Cartão sintético", limit_minor=500000, closing_day=10, due_day=20, default_account_id=account.id)
    session.add(card)
    session.flush()
    return account, card, category


def test_migration_contains_all_contract_tables_and_indexes(domain_db):
    inspector = inspect(domain_db.engine)
    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))
    assert current_revision(domain_db.path) == head_revision(domain_db.path) == "0002_domain_schema"
    assert any(index["name"] == "ix_cash_entries_account_date" for index in inspector.get_indexes("cash_entries"))
    assert any(index["name"] == "uq_active_recurrence_series_month" for index in inspector.get_indexes("recurrence_occurrences"))


def test_upgrade_preserves_existing_settings(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    config = alembic_config(path)
    command.upgrade(config, "0001_foundation")
    database = Database(path)
    with database.session() as session:
        session.execute(text("INSERT INTO settings(locale,currency,timezone,setup_step,revision) VALUES ('pt-BR','BRL','America/Sao_Paulo',7,3)"))
    database.dispose()
    assert migrate(path, tmp_path / "backups") is True
    reopened = Database(path)
    with reopened.session() as session:
        assert session.execute(text("SELECT setup_step,revision FROM settings")).one() == (7, 3)
    reopened.dispose()
    backups = list((tmp_path / "backups").glob("database-before-*.finbackup"))
    assert backups
    from app.maintenance.backup import validate_finbackup
    assert validate_finbackup(backups[0]).manifest["alembic_revision"] == "0001_foundation"


def test_foreign_keys_and_safe_money_are_database_constraints(domain_db):
    with pytest.raises(IntegrityError), domain_db.session() as session:
        session.execute(
            text("INSERT INTO cash_entries(id,created_at,updated_at,revision,account_id,kind,description,signed_amount_minor,currency,planned_date,status,source) VALUES ('e1',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1,'missing','expense','Inválido',100,'BRL','2026-09-01','effective','manual')")
        )
    with pytest.raises(IntegrityError), domain_db.session() as session:
        session.add(Account(name="Fora do limite", reference_date=date(2026, 8, 31), reference_balance_minor=9007199254740992))


def test_unique_invoice_and_active_payment_plan(domain_db):
    with domain_db.session() as session:
        account, card, _category = seed_account_card_category(session)
        invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20))
        session.add(invoice)
        session.flush()
        session.add(InvoicePaymentPlan(invoice_id=invoice.id, account_id=account.id, planned_date=date(2026, 9, 20)))
    with pytest.raises(IntegrityError), domain_db.session() as session:
        invoice = session.query(Invoice).one()
        account = session.query(Account).one()
        session.add(InvoicePaymentPlan(invoice_id=invoice.id, account_id=account.id, planned_date=date(2026, 9, 19)))
    with domain_db.session() as session:
        current = session.query(InvoicePaymentPlan).one()
        current.status = "cancelled"
    with domain_db.session() as session:
        invoice = session.query(Invoice).one()
        account = session.query(Account).one()
        session.add(InvoicePaymentPlan(invoice_id=invoice.id, account_id=account.id, planned_date=date(2026, 9, 19)))
    with pytest.raises(IntegrityError), domain_db.session() as session:
        card = session.query(Card).one()
        session.add(Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20)))


def test_one_active_occurrence_per_series_month(domain_db):
    with domain_db.session() as session:
        account, _card, category = seed_account_card_category(session)
        rule = RecurrenceRule(
            series_id="series-1", version=1, kind="expense", description="Regra sintética", account_id=account.id,
            day=31, start_month="2026-01", amount_minor=1000, category_id=category.id,
        )
        session.add(rule)
        session.flush()
        session.add(RecurrenceOccurrence(series_id="series-1", rule_id=rule.id, occurrence_month="2026-02", expected_date=date(2026, 2, 28), expected_amount_minor=1000))
    with pytest.raises(IntegrityError), domain_db.session() as session:
        rule = session.query(RecurrenceRule).one()
        session.add(RecurrenceOccurrence(series_id="series-1", rule_id=rule.id, occurrence_month="2026-02", expected_date=date(2026, 2, 28), expected_amount_minor=1000))
    with domain_db.session() as session:
        old = session.query(RecurrenceOccurrence).one()
        old.status = "superseded"
    with domain_db.session() as session:
        rule = session.query(RecurrenceRule).one()
        session.add(RecurrenceOccurrence(series_id="series-1", rule_id=rule.id, occurrence_month="2026-02", expected_date=date(2026, 2, 28), expected_amount_minor=1000))


def test_authoritative_state_machines_accept_only_declared_transitions():
    assert set(TRANSITIONS) == {
        "cash_entries", "transfers", "planned_card_purchases", "purchases", "invoices",
        "payments", "refunds", "recurrence_occurrences", "invoice_payment_plans",
    }
    ensure_transition("cash_entries", "planned", "effective")
    ensure_transition("transfers", "effective", "reversed")
    ensure_transition("invoices", "settled", "closed")
    with pytest.raises(InvalidTransition):
        ensure_transition("cash_entries", "cancelled", "effective")
    with pytest.raises(InvalidTransition):
        ensure_transition("payments", "reversed", "active")
