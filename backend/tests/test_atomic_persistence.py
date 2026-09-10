from datetime import date

import pytest
from sqlalchemy import event

from app.storage.financial_repository import confirm_planned_purchase, save_purchase_with_installments, save_transfer
from app.storage.models import Account, Card, CashEntry, Category, Installment, Invoice, PlannedCardPurchase, Purchase, Transfer


def seed(session):
    first = Account(name="Conta A", reference_date=date(2026, 8, 31), reference_balance_minor=300000)
    second = Account(name="Conta B", reference_date=date(2026, 8, 31), reference_balance_minor=50000)
    category = Category(name="Categoria teste", kind="expense")
    session.add_all([first, second, category])
    session.flush()
    card = Card(name="Cartão teste", limit_minor=100000, closing_day=10, due_day=20, default_account_id=first.id)
    session.add(card)
    session.flush()
    invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20))
    session.add(invoice)
    session.flush()
    return first, second, card, category, invoice


def test_transfer_rolls_back_if_second_leg_fails(domain_db):
    with domain_db.session() as session:
        first, second, _card, _category, _invoice = seed(session)
        ids = first.id, second.id

    def fail_second_leg(_mapper, _connection, target):
        if target.kind == "transfer_in":
            raise RuntimeError("falha sintética na segunda perna")

    event.listen(CashEntry, "before_insert", fail_second_leg)
    try:
        with pytest.raises(RuntimeError), domain_db.session() as session:
            save_transfer(session, ids[0], ids[1], 30000, date(2026, 9, 1), "effective", date(2026, 9, 1))
    finally:
        event.remove(CashEntry, "before_insert", fail_second_leg)
    with domain_db.session() as session:
        assert session.query(Transfer).count() == 0
        assert session.query(CashEntry).count() == 0


def test_purchase_rolls_back_if_any_installment_fails(domain_db):
    with domain_db.session() as session:
        _first, _second, card, category, invoice = seed(session)
        ids = card.id, category.id, invoice.id

    def fail_installment(_mapper, _connection, target):
        if target.installment_number == 2:
            raise RuntimeError("falha sintética na parcela")

    event.listen(Installment, "before_insert", fail_installment)
    try:
        with pytest.raises(RuntimeError), domain_db.session() as session:
            save_purchase_with_installments(
                session, ids[0], "Compra sintética", date(2026, 9, 1), 10000, ids[1], "manual",
                [{"installment_number": 1, "amount_minor": 5000, "invoice_id": ids[2]}, {"installment_number": 2, "amount_minor": 5000, "invoice_id": ids[2]}],
            )
    finally:
        event.remove(Installment, "before_insert", fail_installment)
    with domain_db.session() as session:
        assert session.query(Purchase).count() == 0
        assert session.query(Installment).count() == 0


def test_confirm_planned_purchase_links_exactly_one_purchase_atomically(domain_db):
    with domain_db.session() as session:
        _first, _second, card, category, invoice = seed(session)
        planned = PlannedCardPurchase(
            card_id=card.id, description="Planejada", category_id=category.id, expected_date=date(2026, 9, 1),
            expected_amount_minor=9000, estimated_invoice_month="2026-09", status="planned",
        )
        session.add(planned)
        session.flush()
        values = planned.id, card.id, category.id, invoice.id
    with domain_db.session() as session:
        purchase = confirm_planned_purchase(
            session, values[0], card_id=values[1], description="Real", purchase_date=date(2026, 9, 2),
            total_minor=9900, category_id=values[2], source="manual",
            installment_rows=[{"installment_number": 1, "amount_minor": 9900, "invoice_id": values[3]}],
        )
        purchase_id = purchase.id
    with domain_db.session() as session:
        planned = session.query(PlannedCardPurchase).one()
        assert planned.status == "confirmed"
        assert planned.confirmed_purchase_id == purchase_id
        assert session.query(Purchase).filter(Purchase.planned_card_purchase_id == planned.id).count() == 1
    with pytest.raises(Exception), domain_db.session() as session:
        confirm_planned_purchase(
            session, values[0], card_id=values[1], description="Duplicada", purchase_date=date(2026, 9, 2),
            total_minor=9900, category_id=values[2], source="manual",
            installment_rows=[{"installment_number": 1, "amount_minor": 9900, "invoice_id": values[3]}],
        )
    with domain_db.session() as session:
        assert session.query(Purchase).count() == 1

