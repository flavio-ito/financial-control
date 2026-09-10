from datetime import date
from decimal import Decimal

import pytest

from app.domain.calculations import (
    CashProjectionItem,
    DomainValidationError,
    account_balance,
    budget_result,
    cash_projection,
    installment_schedule,
    invoice_dates,
    split_installments,
    suggest_invoice_month,
)
from app.domain.recurrence import occurrence_date


def test_ac04_installment_remainder_is_exact_and_consecutive():
    schedule = installment_schedule(10000, 3, "2026-09", 10, 20)
    assert [item.amount_minor for item in schedule] == [3334, 3333, 3333]
    assert [item.reference_month for item in schedule] == ["2026-09", "2026-10", "2026-11"]
    assert sum(item.amount_minor for item in schedule) == 10000


def test_ac05_six_installments_cross_year_without_bank_entry():
    schedule = installment_schedule(120000, 6, "2026-10", 10, 20)
    assert [item.amount_minor for item in schedule] == [20000] * 6
    assert [item.reference_month for item in schedule] == ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"]


def test_installments_reject_zero_and_unsafe_values_ac41():
    with pytest.raises(DomainValidationError):
        split_installments(2, 3)
    with pytest.raises(DomainValidationError):
        split_installments(9007199254740992, 1)


def test_invoice_calendar_closing_before_after_and_equal_due_day():
    before = invoice_dates("2026-10", 10, 20)
    after = invoice_dates("2026-10", 25, 10)
    equal = invoice_dates("2026-10", 10, 10)
    assert (before.closing_date, before.due_date) == (date(2026, 10, 10), date(2026, 10, 20))
    assert (after.closing_date, after.due_date) == (date(2026, 9, 25), date(2026, 10, 10))
    assert (equal.closing_date, equal.due_date) == (date(2026, 9, 10), date(2026, 10, 10))


def test_ac28_purchase_on_closing_and_next_day():
    assert suggest_invoice_month(date(2026, 9, 10), 10, 20) == "2026-09"
    assert suggest_invoice_month(date(2026, 9, 11), 10, 20) == "2026-10"


def test_days_28_29_30_31_and_ac10_recurrence():
    assert occurrence_date("2024-02", 31) == date(2024, 2, 29)
    assert occurrence_date("2025-02", 31) == date(2025, 2, 28)
    assert occurrence_date("2025-03", 31) == date(2025, 3, 31)
    assert invoice_dates("2025-03", 31, 30).closing_date == date(2025, 2, 28)


def test_ac01_ac02_ac31_reference_balance_includes_effective_entries_on_reference_date():
    entries = [
        {"effective_date": date(2026, 8, 15), "status": "effective", "signed_amount_minor": -10000},
        {"effective_date": date(2026, 8, 31), "status": "effective", "signed_amount_minor": -5000},
        {"effective_date": date(2026, 9, 1), "status": "effective", "signed_amount_minor": 50000},
        {"effective_date": date(2026, 9, 2), "status": "effective", "signed_amount_minor": -20000},
        {"effective_date": date(2026, 9, 3), "status": "planned", "signed_amount_minor": -99999},
    ]
    assert account_balance(100000, date(2026, 8, 31), date(2026, 9, 30), entries) == 125000


def test_ac12_budget_exceeded():
    result = budget_result(60000, 65000, 0)
    assert result.excess_minor == 5000
    assert result.percentage == Decimal("108.33")
    assert result.status == "exceeded"


def test_ac13_absent_and_zero_budget_are_distinct():
    assert budget_result(None, 0, 0).status == "not_configured"
    zero = budget_result(0, 100, 0)
    assert zero.status == "exceeded"
    assert zero.percentage is None


def test_ac14_projected_budget_risk():
    result = budget_result(60000, 40000, 25000)
    assert result.registered_minor == 40000
    assert result.projected_minor == 65000
    assert result.excess_minor == 5000
    assert result.status == "risk"


def test_ac18_projection_deduplicates_invoice_obligation():
    items = [
        CashProjectionItem("invoice:1", "account-a", date(2026, 10, 20), -20000, "invoice"),
        CashProjectionItem("invoice:1", "account-a", date(2026, 10, 19), -20000, "invoice_payment_plan"),
    ]
    total, normalized = cash_projection(100000, items, date(2026, 9, 1))
    assert total == 80000
    assert len(normalized) == 1
