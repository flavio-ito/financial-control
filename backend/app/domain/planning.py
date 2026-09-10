from datetime import date
from typing import Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.analytics import monthly_summary
from app.domain.calculations import CashProjectionItem, add_months, budget_result, cash_projection, limited_date
from app.domain.services import balance_for_account, calculate_invoice
from app.storage.models import Account, Budget, BudgetDefault, Card, CashEntry, Installment, Invoice, InvoiceAdjustment, InvoicePaymentPlan, PlannedCardPurchase


def card_commitment(session: Session, card_id: str) -> int:
    installments = (
        session.query(func.coalesce(func.sum(Installment.amount_minor), 0))
        .join(Invoice, Invoice.id == Installment.invoice_id)
        .filter(Invoice.card_id == card_id, Invoice.state != "settled", Installment.status == "confirmed")
        .scalar()
    )
    adjustments = (
        session.query(InvoiceAdjustment.signed_amount_minor)
        .join(Invoice, Invoice.id == InvoiceAdjustment.invoice_id)
        .filter(Invoice.card_id == card_id, Invoice.state != "settled", InvoiceAdjustment.status == "active")
        .all()
    )
    return max(0, installments + sum(value for (value,) in adjustments))


def budget_for_category(session: Session, category_id: str, month: str):
    override = session.query(Budget).filter(Budget.category_id == category_id, Budget.month == month).one_or_none()
    if override:
        limit = override.amount_minor
    else:
        default = (
            session.query(BudgetDefault)
            .filter(BudgetDefault.category_id == category_id, BudgetDefault.effective_from_month <= month)
            .order_by(BudgetDefault.effective_from_month.desc())
            .first()
        )
        limit = default.amount_minor if default else None
    registered = monthly_summary(session, month).categories.get(category_id, 0)
    start = limited_date(month, 1)
    end = limited_date(add_months(month, 1), 1)
    planned_cash = (
        session.query(func.coalesce(func.sum(-CashEntry.signed_amount_minor), 0))
        .filter(CashEntry.category_id == category_id, CashEntry.kind == "expense", CashEntry.status == "planned", CashEntry.planned_date >= start, CashEntry.planned_date < end)
        .scalar()
    )
    planned_card = (
        session.query(func.coalesce(func.sum(PlannedCardPurchase.expected_amount_minor), 0))
        .filter(PlannedCardPurchase.category_id == category_id, PlannedCardPurchase.status == "planned", PlannedCardPurchase.estimated_invoice_month == month)
        .scalar()
    )
    return budget_result(limit, registered, planned_cash + planned_card)


def projected_cash(session: Session, today: date, through_month: str) -> Dict[str, object]:
    accounts = session.query(Account).filter(Account.archived_at.is_(None)).all()
    current_by_account = {account.id: balance_for_account(session, account.id, today) for account in accounts}
    items: List[CashProjectionItem] = []
    horizon_end = limited_date(add_months(through_month, 1), 1)
    for entry in session.query(CashEntry).filter(CashEntry.status == "planned", CashEntry.planned_date < horizon_end).all():
        items.append(CashProjectionItem("cash:{}".format(entry.id), entry.account_id, entry.planned_date, entry.signed_amount_minor, "cash_entry"))
    for invoice in session.query(Invoice).filter(Invoice.state != "settled", Invoice.due_date < horizon_end).all():
        total = calculate_invoice(session, invoice.id)
        planned_extra = session.query(func.coalesce(func.sum(PlannedCardPurchase.expected_amount_minor), 0)).filter(
            PlannedCardPurchase.card_id == invoice.card_id,
            PlannedCardPurchase.estimated_invoice_month == invoice.reference_month,
            PlannedCardPurchase.status == "planned",
        ).scalar()
        payable = max(total.net_minor + planned_extra, 0)
        plan = session.query(InvoicePaymentPlan).filter(InvoicePaymentPlan.invoice_id == invoice.id, InvoicePaymentPlan.status == "active").one_or_none()
        card = session.query(Card).filter(Card.id == invoice.card_id).one()
        account_id = plan.account_id if plan else card.default_account_id
        projected_date = plan.planned_date if plan else invoice.due_date
        items.append(CashProjectionItem("invoice:{}".format(invoice.id), account_id, projected_date, -payable, "invoice_payment_plan" if plan else "invoice"))
    current_total = sum(current_by_account.values())
    consolidated, normalized = cash_projection(current_total, items, today)
    by_account = dict(current_by_account)
    incomplete = False
    for item in normalized:
        if item.account_id:
            by_account[item.account_id] = by_account.get(item.account_id, 0) + item.signed_amount_minor
        elif item.signed_amount_minor:
            incomplete = True
    return {"current_minor": current_total, "projected_minor": consolidated, "by_account": by_account, "items": normalized, "incomplete_by_account": incomplete}

