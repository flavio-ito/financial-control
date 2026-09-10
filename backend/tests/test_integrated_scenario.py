from datetime import date

from app.domain.analytics import monthly_summary
from app.domain.planning import card_commitment
from app.domain.services import balance_for_account, close_invoice, create_cash_entry, create_purchase, create_transfer, settle_invoice
from app.storage.models import Account, Card, Category, Invoice


def test_integrated_reference_scenario_has_exact_balances_and_no_double_counting(domain_db):
    today = date(2026, 9, 30)
    with domain_db.session() as session:
        account_a = Account(name="A", reference_date=date(2026, 8, 31), reference_balance_minor=300000)
        account_b = Account(name="B", reference_date=date(2026, 8, 31), reference_balance_minor=50000)
        income_category = Category(name="Renda", kind="income")
        expense_category = Category(name="Consumo", kind="expense")
        session.add_all([account_a, account_b, income_category, expense_category])
        session.flush()
        card = Card(name="Cartão", limit_minor=500000, closing_day=10, due_day=20, default_account_id=account_a.id)
        session.add(card)
        session.flush()
        create_cash_entry(session, account_a.id, "income", "Receita", 200000, date(2026, 9, 1), "effective", today, income_category.id, date(2026, 9, 1))
        create_cash_entry(session, account_a.id, "expense", "Despesa", 30000, date(2026, 9, 2), "effective", today, expense_category.id, date(2026, 9, 2))
        create_transfer(session, account_a.id, account_b.id, 40000, date(2026, 9, 3), "effective", today, date(2026, 9, 3))
        create_purchase(session, card.id, "Compra parcelada", date(2026, 9, 4), 60000, 3, expense_category.id, "2026-09", today)
        invoice = session.query(Invoice).filter(Invoice.card_id == card.id, Invoice.reference_month == "2026-09").one()
        close_invoice(session, invoice.id, invoice.revision)
        settle_invoice(session, invoice.id, account_a.id, date(2026, 9, 20), 20000, today)
        ids = account_a.id, account_b.id, card.id
    with domain_db.session() as session:
        assert balance_for_account(session, ids[0], today) == 410000
        assert balance_for_account(session, ids[1], today) == 90000
        assert balance_for_account(session, ids[0], today) + balance_for_account(session, ids[1], today) == 500000
        summary = monthly_summary(session, "2026-09")
        assert summary.income_minor == 200000
        assert summary.expense_minor == 50000
        assert summary.registered_result_minor == 150000
        assert card_commitment(session, ids[2]) == 40000
