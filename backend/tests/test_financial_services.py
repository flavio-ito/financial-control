from datetime import date

import pytest

from app.domain.analytics import monthly_summary
from app.domain.calculations import DomainValidationError
from app.domain.services import (
    balance_for_account,
    calculate_invoice,
    close_invoice,
    confirm_planned_card_purchase,
    create_cash_entry,
    create_planned_card_purchase,
    create_purchase,
    create_transfer,
    register_refund,
    reverse_transfer,
    settle_invoice,
)
from app.storage.models import Account, Card, CashEntry, Category, Installment, Invoice, InvoiceAdjustment, Payment, PlannedCardPurchase, Purchase, Refund, Transfer


TODAY = date(2026, 9, 30)


def setup_base(session):
    account_a = Account(name="Conta A", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
    account_b = Account(name="Conta B", reference_date=date(2026, 8, 31), reference_balance_minor=50000)
    income = Category(name="Renda", kind="income")
    expense = Category(name="Alimentação", kind="expense")
    session.add_all([account_a, account_b, income, expense])
    session.flush()
    card = Card(name="Cartão", limit_minor=500000, closing_day=10, due_day=20, default_account_id=account_a.id)
    session.add(card)
    session.flush()
    return account_a, account_b, card, income, expense


def test_ac01_ac02_ac03_ac31_balances_and_transfer_analytics(domain_db):
    with domain_db.session() as session:
        a, b, _card, income, expense = setup_base(session)
        ids = a.id, b.id, income.id, expense.id
        create_cash_entry(session, a.id, "income", "Receita", 50000, date(2026, 9, 5), "effective", TODAY, income.id, date(2026, 9, 5))
        create_cash_entry(session, a.id, "expense", "Despesa", 20000, date(2026, 9, 6), "effective", TODAY, expense.id, date(2026, 9, 6))
        create_cash_entry(session, a.id, "expense", "Histórica", 10000, date(2026, 8, 20), "effective", TODAY, expense.id, date(2026, 8, 20))
        create_cash_entry(session, a.id, "expense", "Boundary", 1000, date(2026, 8, 31), "effective", TODAY, expense.id, date(2026, 8, 31))
        create_transfer(session, a.id, b.id, 30000, date(2026, 9, 7), "effective", TODAY, date(2026, 9, 7))
    with domain_db.session() as session:
        assert balance_for_account(session, ids[0], TODAY) == 99000
        assert balance_for_account(session, ids[1], TODAY) == 80000
        summary = monthly_summary(session, "2026-09")
        assert (summary.income_minor, summary.expense_minor, summary.registered_result_minor) == (50000, 20000, 30000)
        assert monthly_summary(session, "2026-08").expense_minor == 11000


def test_effective_cash_entry_cannot_be_future(domain_db):
    with domain_db.session() as session:
        account, _b, _card, _income, expense = setup_base(session)
        with pytest.raises(DomainValidationError):
            create_cash_entry(session, account.id, "expense", "Futura", 100, date(2026, 10, 1), "effective", TODAY, expense.id, date(2026, 10, 1))


def test_purchase_is_analytical_expense_without_immediate_cash_and_payment_does_not_duplicate(domain_db):
    with domain_db.session() as session:
        account, _b, card, _income, expense = setup_base(session)
        ids = account.id, card.id, expense.id
        purchase = create_purchase(session, card.id, "Compra", date(2026, 9, 1), 60000, 3, expense.id, "2026-09", TODAY)
        assert purchase.total_minor == 60000
    with domain_db.session() as session:
        assert session.query(CashEntry).count() == 0
        september = session.query(Invoice).filter(Invoice.reference_month == "2026-09").one()
        assert calculate_invoice(session, september.id).payable_minor == 20000
        close_invoice(session, september.id, september.revision)
        payment = settle_invoice(session, september.id, ids[0], date(2026, 9, 20), 20000, TODAY)
        assert payment.amount_minor == 20000
    with domain_db.session() as session:
        summary = monthly_summary(session, "2026-09")
        assert summary.expense_minor == 20000
        assert summary.cash_flow_minor == -20000
        assert balance_for_account(session, ids[0], TODAY) == 80000
        assert session.query(Payment).count() == 1


def test_ac17_credit_carry_is_created_and_consumed_once(domain_db):
    with domain_db.session() as session:
        account, _b, card, _income, _expense = setup_base(session)
        invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20), state="closed")
        session.add(invoice)
        session.flush()
        session.add(InvoiceAdjustment(invoice_id=invoice.id, signed_amount_minor=-10000, kind="refund", description="Crédito", status="active"))
        ids = invoice.id, account.id
    with domain_db.session() as session:
        payment = settle_invoice(session, ids[0], ids[1], date(2026, 9, 20), 0, TODAY)
        assert payment.amount_minor == 0
        october = session.query(Invoice).filter(Invoice.reference_month == "2026-10").one()
        assert calculate_invoice(session, october.id).net_minor == -10000
        october_id = october.id
    with domain_db.session() as session:
        october = session.query(Invoice).filter(Invoice.id == october_id).one()
        close_invoice(session, october.id, october.revision)
        settle_invoice(session, october_id, ids[1], date(2026, 9, 30), 0, TODAY)
    with domain_db.session() as session:
        carries = session.query(InvoiceAdjustment).filter(InvoiceAdjustment.kind == "credit_carry").all()
        assert len(carries) == 2
        assert sorted(item.status for item in carries) == ["active", "consumed"]
        november = session.query(Invoice).filter(Invoice.reference_month == "2026-11").one()
        assert calculate_invoice(session, november.id).net_minor == -10000


def test_ac15_refund_after_paid_invoice_preserves_it_and_hits_future_competence(domain_db):
    with domain_db.session() as session:
        account, _b, card, _income, expense = setup_base(session)
        purchase = create_purchase(session, card.id, "Compra", date(2026, 9, 1), 5000, 1, expense.id, "2026-09", TODAY)
        september = session.query(Invoice).filter(Invoice.reference_month == "2026-09").one()
        september.state = "closed"
        settle_invoice(session, september.id, account.id, date(2026, 9, 20), requested_amount_minor=5000, today=TODAY)
        october = Invoice(card_id=card.id, reference_month="2026-10", closing_date=date(2026, 10, 10), due_date=date(2026, 10, 20))
        session.add(october)
        session.flush()
        ids = purchase.id, september.id, october.id
    with domain_db.session() as session:
        register_refund(session, ids[0], 5000, "confirmed", date(2026, 10, 5), "invoice", ids[2], "Estorno real", date(2026, 10, 5), date(2026, 10, 5))
    with domain_db.session() as session:
        assert session.query(Invoice).filter(Invoice.id == ids[1]).one().state == "settled"
        assert monthly_summary(session, "2026-10").expense_minor == -5000


def test_ac16_refund_and_cancellation_cannot_abate_same_value(domain_db):
    with domain_db.session() as session:
        _account, _b, card, _income, expense = setup_base(session)
        purchase = create_purchase(session, card.id, "Compra", date(2026, 9, 1), 10000, 2, expense.id, "2026-10", TODAY)
        first = session.query(Installment).filter(Installment.purchase_id == purchase.id, Installment.installment_number == 1).one()
        first.status = "cancelled"
        october = session.query(Invoice).filter(Invoice.reference_month == "2026-10").one()
        ids = purchase.id, october.id
    with pytest.raises(DomainValidationError), domain_db.session() as session:
        register_refund(session, ids[0], 6000, "confirmed", TODAY, "invoice", ids[1], "Duplo abatimento", TODAY, TODAY)
    with domain_db.session() as session:
        assert session.query(Refund).count() == 0


def test_ac34_planned_purchase_is_replaced_by_exactly_one_real_purchase(domain_db):
    with domain_db.session() as session:
        _account, _b, card, _income, expense = setup_base(session)
        planned = create_planned_card_purchase(session, card.id, "Planejada", expense.id, date(2026, 9, 15), 30000, "2026-10")
        planned_id = planned.id
    with domain_db.session() as session:
        purchase = confirm_planned_card_purchase(session, planned_id, date(2026, 9, 16), 33000, 3, "2026-10", TODAY)
        purchase_id = purchase.id
    with domain_db.session() as session:
        planned = session.query(PlannedCardPurchase).one()
        assert planned.status == "confirmed" and planned.confirmed_purchase_id == purchase_id
        assert session.query(Purchase).count() == 1
        assert [row.amount_minor for row in session.query(Installment).order_by(Installment.installment_number)] == [11000, 11000, 11000]


def test_transfer_reversal_creates_inverse_legs(domain_db):
    with domain_db.session() as session:
        a, b, _card, _income, _expense = setup_base(session)
        transfer = create_transfer(session, a.id, b.id, 10000, date(2026, 9, 2), "effective", TODAY, date(2026, 9, 2))
        values = transfer.id, transfer.revision, a.id, b.id
    with domain_db.session() as session:
        reverse_transfer(session, values[0], values[1], date(2026, 9, 3), TODAY, "Transferência desfeita")
    with domain_db.session() as session:
        assert session.query(Transfer).count() == 2
        assert session.query(CashEntry).count() == 4
        assert balance_for_account(session, values[2], TODAY) == 100000
        assert balance_for_account(session, values[3], TODAY) == 50000
