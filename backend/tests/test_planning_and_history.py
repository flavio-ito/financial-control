from datetime import date

import pytest

from app.domain.analytics import compare_months, monthly_summary
from app.domain.calculations import DomainValidationError
from app.domain.planning import budget_for_category, card_commitment, projected_cash
from app.domain.recurrence import generate_pending_occurrences, version_from_month
from app.domain.services import (
    archive_entity,
    close_invoice,
    confirm_recurrence_occurrence,
    create_initial_purchase,
    create_planned_card_purchase,
    create_purchase,
    edit_purchase_category,
    replace_opening_contribution,
    settle_invoice,
    update_card_terms,
)
from app.storage.models import (
    Account,
    BudgetDefault,
    Card,
    Category,
    CoverageInterval,
    Installment,
    Invoice,
    InvoiceAdjustment,
    InvoicePaymentPlan,
    PlannedCardPurchase,
    Purchase,
    RecurrenceOccurrence,
    RecurrenceRule,
)

TODAY = date(2026, 9, 30)


def base(session):
    a = Account(name="A", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
    b = Account(name="B", reference_date=date(2026, 8, 31), reference_balance_minor=50000)
    food = Category(name="Alimentação", kind="expense")
    other = Category(name="Outros", kind="expense")
    session.add_all([a, b, food, other])
    session.flush()
    card = Card(name="Cartão", limit_minor=200000, closing_day=10, due_day=20, default_account_id=a.id)
    session.add(card)
    session.flush()
    return a, b, card, food, other


def test_ac08_only_remaining_old_installments_become_obligations(domain_db):
    with domain_db.session() as session:
        _a, _b, card, food, _other = base(session)
        purchase = create_initial_purchase(session, card.id, "Compra antiga", date(2026, 4, 1), 120000, 6, 4, food.id, "2026-10")
        purchase_id = purchase.id
    with domain_db.session() as session:
        installments = session.query(Installment).filter(Installment.purchase_id == purchase_id).order_by(Installment.installment_number).all()
        assert [item.installment_number for item in installments] == [4, 5, 6]
        assert [item.amount_minor for item in installments] == [20000, 20000, 20000]
        assert [item.invoice.reference_month if hasattr(item, "invoice") else session.query(Invoice).filter(Invoice.id == item.invoice_id).one().reference_month for item in installments] == ["2026-10", "2026-11", "2026-12"]


def test_ac09_opening_replacement_preserves_current_invoice_contribution(domain_db):
    with domain_db.session() as session:
        _a, _b, card, food, _other = base(session)
        invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20))
        session.add(invoice)
        session.flush()
        opening = InvoiceAdjustment(invoice_id=invoice.id, signed_amount_minor=60000, kind="opening", description="Compromisso inicial", status="active")
        session.add(opening)
        session.flush()
        purchase = create_purchase(session, card.id, "Detalhamento", date(2026, 8, 1), 180000, 3, food.id, "2026-09", TODAY)
        contribution = session.query(Installment).filter(Installment.purchase_id == purchase.id, Installment.invoice_id == invoice.id).one()
        values = opening.id, contribution.id, invoice.id, purchase.id
    with domain_db.session() as session:
        assert replace_opening_contribution(session, values[0], [values[1]], 60000).status == "cancelled"
    with domain_db.session() as session:
        assert monthly_summary(session, "2026-09").expense_minor == 60000
        assert session.query(Purchase).filter(Purchase.id == values[3]).one().total_minor == 180000
        assert card_commitment(session, session.query(Card).one().id) == 180000


def test_ac20_settled_installment_category_snapshot_is_immutable(domain_db):
    with domain_db.session() as session:
        account, _b, card, food, other = base(session)
        purchase = create_purchase(session, card.id, "Compra", date(2026, 9, 1), 40000, 2, food.id, "2026-09", TODAY)
        september = session.query(Invoice).filter(Invoice.reference_month == "2026-09").one()
        close_invoice(session, september.id, september.revision)
        settle_invoice(session, september.id, account.id, date(2026, 9, 20), 20000, TODAY)
        values = purchase.id, purchase.revision, food.id, other.id
    with domain_db.session() as session:
        edit_purchase_category(session, values[0], values[3], values[1])
    with domain_db.session() as session:
        rows = session.query(Installment).filter(Installment.purchase_id == values[0]).order_by(Installment.installment_number).all()
        assert rows[0].category_id_snapshot == values[2]
        assert rows[1].category_id_snapshot == values[3]


def test_ac10_ac11_ac32_recurrence_generation_confirmation_and_versioning(domain_db):
    with domain_db.session() as session:
        account, _b, _card, food, _other = base(session)
        rule = RecurrenceRule(series_id="stable-series", version=1, kind="expense", description="Mensal", account_id=account.id, day=31, start_month="2026-09", amount_minor=1000, category_id=food.id, active=1)
        session.add(rule)
        session.flush()
        rule_id = rule.id
    assert generate_pending_occurrences(domain_db, TODAY) == 13
    assert generate_pending_occurrences(domain_db, TODAY) == 0
    with domain_db.session() as session:
        february = session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.occurrence_month == "2027-02").one()
        assert february.expected_date == date(2027, 2, 28)
        september = session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.occurrence_month == "2026-09").one()
        occurrence_id = september.id
    with domain_db.session() as session:
        confirm_recurrence_occurrence(session, occurrence_id, TODAY, 1100, TODAY)
    with pytest.raises(Exception), domain_db.session() as session:
        confirm_recurrence_occurrence(session, occurrence_id, TODAY, 1100, TODAY)
    with domain_db.session() as session:
        rule = session.query(RecurrenceRule).filter(RecurrenceRule.id == rule_id).one()
        version_from_month(session, rule, "2027-01", amount_minor=1200)
    generate_pending_occurrences(domain_db, TODAY)
    with domain_db.session() as session:
        active_counts = {}
        for item in session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.status != "superseded").all():
            active_counts[item.occurrence_month] = active_counts.get(item.occurrence_month, 0) + 1
        assert max(active_counts.values()) == 1
        assert session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.status == "superseded").count() == 9
        assert session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.id == occurrence_id).one().status == "confirmed"


def test_ac14_budget_uses_planned_only_as_additional(domain_db):
    with domain_db.session() as session:
        _a, _b, card, food, _other = base(session)
        session.add(BudgetDefault(category_id=food.id, effective_from_month="2026-01", amount_minor=60000))
        create_purchase(session, card.id, "Confirmada", date(2026, 9, 1), 40000, 1, food.id, "2026-09", TODAY)
        create_planned_card_purchase(session, card.id, "Prevista", food.id, date(2026, 9, 15), 25000, "2026-09")
        category_id = food.id
    with domain_db.session() as session:
        result = budget_for_category(session, category_id, "2026-09")
        assert (result.registered_minor, result.additional_planned_minor, result.projected_minor, result.status) == (40000, 25000, 65000, "risk")


def test_ac35_payment_plan_replaces_account_and_date_without_duplicate(domain_db):
    with domain_db.session() as session:
        a, b, card, food, _other = base(session)
        create_purchase(session, card.id, "Compra", date(2026, 9, 1), 50000, 1, food.id, "2026-10", TODAY)
        invoice = session.query(Invoice).filter(Invoice.reference_month == "2026-10").one()
        ids = a.id, b.id, invoice.id
    with domain_db.session() as session:
        derived = projected_cash(session, TODAY, "2026-10")
        assert derived["projected_minor"] == 100000
        assert len([item for item in derived["items"] if item.key.startswith("invoice:")]) == 1
        session.add(InvoicePaymentPlan(invoice_id=ids[2], account_id=ids[1], planned_date=date(2026, 10, 15), status="active"))
    with domain_db.session() as session:
        explicit = projected_cash(session, TODAY, "2026-10")
        invoice_item = [item for item in explicit["items"] if item.key.startswith("invoice:")][0]
        assert explicit["projected_minor"] == 100000
        assert (invoice_item.account_id, invoice_item.date, invoice_item.source) == (ids[1], date(2026, 10, 15), "invoice_payment_plan")


def test_ac19_partial_coverage_suppresses_reliable_comparison(domain_db):
    with domain_db.session() as session:
        account, _b, _card, _food, _other = base(session)
        session.add(CoverageInterval(account_id=account.id, date_from=date(2026, 8, 1), date_to=date(2026, 8, 31), status="partial"))
    with domain_db.session() as session:
        comparison = compare_months(session, "2026-09", "2026-08")
        assert comparison["reliable"] is False
        assert comparison["percentage"] is None


def test_ac30_and_ac36_archiving_and_card_terms_preserve_existing_obligations(domain_db):
    with domain_db.session() as session:
        _a, _b, card, food, _other = base(session)
        purchase = create_purchase(session, card.id, "Compra", date(2026, 9, 1), 20000, 1, food.id, "2026-09", TODAY)
        invoice = session.query(Invoice).one()
        original_dates = invoice.closing_date, invoice.due_date
        update_card_terms(session, card.id, 5, 15, card.revision)
        archive_entity(session, Card, card.id, card.revision)
        values = card.id, food.id, purchase.id, invoice.id, original_dates
    with domain_db.session() as session:
        invoice = session.query(Invoice).filter(Invoice.id == values[3]).one()
        assert (invoice.closing_date, invoice.due_date) == values[4]
        assert session.query(Purchase).filter(Purchase.id == values[2]).one() is not None
        assert card_commitment(session, values[0]) == 20000
        with pytest.raises(DomainValidationError):
            create_purchase(session, values[0], "Nova", TODAY, 1000, 1, values[1], "2026-10", TODAY)

