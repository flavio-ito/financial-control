from dataclasses import dataclass
from datetime import date
from typing import Dict

from sqlalchemy.orm import Session

from app.domain.calculations import add_months, limited_date
from app.storage.models import Account, Card, CashEntry, CoverageInterval, Installment, Invoice, InvoiceAdjustment


@dataclass(frozen=True)
class MonthlySummary:
    income_minor: int
    expense_minor: int
    registered_result_minor: int
    cash_flow_minor: int
    categories: Dict[str, int]
    uncategorized_minor: int


def monthly_summary(session: Session, month: str) -> MonthlySummary:
    start = limited_date(month, 1)
    end = limited_date(add_months(month, 1), 1)
    entries = (
        session.query(CashEntry)
        .filter(CashEntry.status == "effective", CashEntry.effective_date >= start, CashEntry.effective_date < end)
        .all()
    )
    income = sum(item.signed_amount_minor for item in entries if item.kind == "income")
    expense = sum(-item.signed_amount_minor for item in entries if item.kind == "expense")
    cash_refunds = sum(item.signed_amount_minor for item in entries if item.kind == "refund")
    cash_flow = sum(item.signed_amount_minor for item in entries if item.kind != "balance_adjustment")
    categories = {}
    uncategorized = 0
    for item in entries:
        value = -item.signed_amount_minor if item.kind == "expense" else (-item.signed_amount_minor if item.kind == "refund" else 0)
        if value:
            if item.category_id:
                categories[item.category_id] = categories.get(item.category_id, 0) + value
            else:
                uncategorized += value

    installments = (
        session.query(Installment)
        .join(Invoice, Invoice.id == Installment.invoice_id)
        .filter(Invoice.reference_month == month, Installment.status.in_(("confirmed", "historical_settled")))
        .all()
    )
    card_expense = sum(item.amount_minor for item in installments)
    for item in installments:
        if item.category_id_snapshot:
            categories[item.category_id_snapshot] = categories.get(item.category_id_snapshot, 0) + item.amount_minor
        else:
            uncategorized += item.amount_minor

    adjustments = (
        session.query(InvoiceAdjustment)
        .join(Invoice, Invoice.id == InvoiceAdjustment.invoice_id)
        .filter(
            Invoice.reference_month == month,
            InvoiceAdjustment.status.in_(("active", "consumed")),
            InvoiceAdjustment.kind.in_(("opening", "debit", "refund")),
        )
        .all()
    )
    analytical_adjustment = sum(item.signed_amount_minor for item in adjustments)
    for item in adjustments:
        if item.category_id:
            categories[item.category_id] = categories.get(item.category_id, 0) + item.signed_amount_minor
        else:
            uncategorized += item.signed_amount_minor

    expense = expense - cash_refunds + card_expense + analytical_adjustment
    return MonthlySummary(income, expense, income - expense, cash_flow, categories, uncategorized)


def coverage_status(session: Session, month: str) -> str:
    start = limited_date(month, 1)
    end = limited_date(add_months(month, 1), 1)
    owners = [("account_id", item.id) for item in session.query(Account).filter(Account.archived_at.is_(None)).all()]
    owners += [("card_id", item.id) for item in session.query(Card).filter(Card.archived_at.is_(None)).all()]
    if not owners:
        return "unknown"
    statuses = []
    for field, owner_id in owners:
        column = getattr(CoverageInterval, field)
        interval = session.query(CoverageInterval).filter(column == owner_id, CoverageInterval.date_from <= start, CoverageInterval.date_to >= end).first()
        statuses.append(interval.status if interval else "unknown")
    if all(status == "complete" for status in statuses):
        return "complete"
    if any(status == "partial" for status in statuses):
        return "partial"
    return "unknown"


def compare_months(session: Session, current_month: str, previous_month: str):
    current = monthly_summary(session, current_month)
    previous = monthly_summary(session, previous_month)
    reliable = coverage_status(session, current_month) == "complete" and coverage_status(session, previous_month) == "complete"
    difference = current.expense_minor - previous.expense_minor
    percentage = None
    if reliable and previous.expense_minor > 0:
        from decimal import Decimal, ROUND_HALF_UP

        percentage = (Decimal(difference) * Decimal(100) / Decimal(previous.expense_minor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"difference_minor": difference, "percentage": percentage, "reliable": reliable}
