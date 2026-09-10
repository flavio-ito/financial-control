from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple

from app.config import SAFE_INTEGER_MAX


class DomainValidationError(ValueError):
    pass


def validate_minor(value: int, allow_zero: bool = False) -> int:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > SAFE_INTEGER_MAX:
        raise DomainValidationError("Valor monetário inválido ou fora do intervalo seguro.")
    return value


def parse_month(month: str) -> Tuple[int, int]:
    try:
        year_text, month_text = month.split("-")
        year, number = int(year_text), int(month_text)
        if len(year_text) != 4 or len(month_text) != 2 or number < 1 or number > 12:
            raise ValueError
        return year, number
    except (AttributeError, TypeError, ValueError):
        raise DomainValidationError("Competência deve usar o formato AAAA-MM.")


def month_of(value: date) -> str:
    return "{:04d}-{:02d}".format(value.year, value.month)


def add_months(month: str, count: int) -> str:
    year, number = parse_month(month)
    absolute = year * 12 + number - 1 + count
    if absolute < 12:
        raise DomainValidationError("Competência fora do intervalo suportado.")
    return "{:04d}-{:02d}".format(absolute // 12, absolute % 12 + 1)


def limited_date(month: str, day: int) -> date:
    year, number = parse_month(month)
    if day < 1 or day > 31:
        raise DomainValidationError("Dia deve estar entre 1 e 31.")
    return date(year, number, min(day, monthrange(year, number)[1]))


class InvoiceDates(NamedTuple):
    reference_month: str
    closing_date: date
    due_date: date


def invoice_dates(reference_month: str, closing_day: int, due_day: int) -> InvoiceDates:
    due = limited_date(reference_month, due_day)
    closing_month = reference_month
    closing = limited_date(closing_month, closing_day)
    if closing >= due:
        closing_month = add_months(reference_month, -1)
        closing = limited_date(closing_month, closing_day)
    return InvoiceDates(reference_month, closing, due)


def suggest_invoice_month(purchase_date: date, closing_day: int, due_day: int) -> str:
    candidate = month_of(purchase_date)
    for offset in range(0, 25):
        reference = add_months(candidate, offset)
        dates = invoice_dates(reference, closing_day, due_day)
        if dates.closing_date >= purchase_date:
            return reference
    raise DomainValidationError("Não foi possível sugerir a primeira fatura.")


def split_installments(total_minor: int, installment_count: int) -> List[int]:
    validate_minor(total_minor)
    if isinstance(installment_count, bool) or not isinstance(installment_count, int) or installment_count < 1:
        raise DomainValidationError("Quantidade de parcelas deve ser um inteiro positivo.")
    if installment_count > total_minor:
        raise DomainValidationError("Quantidade de parcelas produziria valor zero.")
    base, remainder = divmod(total_minor, installment_count)
    return [base + (1 if index < remainder else 0) for index in range(installment_count)]


@dataclass(frozen=True)
class InstallmentPreview:
    installment_number: int
    amount_minor: int
    reference_month: str
    closing_date: date
    due_date: date


def installment_schedule(total_minor: int, installment_count: int, first_invoice_month: str, closing_day: int, due_day: int) -> List[InstallmentPreview]:
    amounts = split_installments(total_minor, installment_count)
    result = []
    for index, amount in enumerate(amounts):
        reference = add_months(first_invoice_month, index)
        dates = invoice_dates(reference, closing_day, due_day)
        result.append(InstallmentPreview(index + 1, amount, reference, dates.closing_date, dates.due_date))
    return result


def account_balance(reference_balance_minor: int, reference_date: date, target_date: date, entries: Iterable[Mapping[str, object]]) -> int:
    if abs(reference_balance_minor) > SAFE_INTEGER_MAX:
        raise DomainValidationError("Saldo de referência fora do intervalo seguro.")
    if target_date < reference_date:
        raise DomainValidationError("Saldo anterior à referência não é confirmado.")
    total = reference_balance_minor
    for entry in entries:
        effective = entry.get("effective_date")
        if entry.get("status") == "effective" and isinstance(effective, date) and reference_date <= effective <= target_date:
            amount = entry.get("signed_amount_minor")
            if isinstance(amount, bool) or not isinstance(amount, int):
                raise DomainValidationError("Movimento monetário inválido.")
            total += amount
    if abs(total) > SAFE_INTEGER_MAX:
        raise DomainValidationError("Saldo calculado fora do intervalo seguro.")
    return total


@dataclass(frozen=True)
class InvoiceTotal:
    net_minor: int
    payable_minor: int
    carry_minor: int


def invoice_total(confirmed_debits: Iterable[int], active_adjustments: Iterable[int]) -> InvoiceTotal:
    net = sum(confirmed_debits) + sum(active_adjustments)
    if abs(net) > SAFE_INTEGER_MAX:
        raise DomainValidationError("Total da fatura fora do intervalo seguro.")
    return InvoiceTotal(net_minor=net, payable_minor=max(net, 0), carry_minor=max(-net, 0))


def estimated_card_commitment(installments: Iterable[int], debit_adjustments: Iterable[int], unused_credits: Iterable[int]) -> int:
    result = sum(installments) + sum(debit_adjustments) - sum(unused_credits)
    return max(0, result)


@dataclass(frozen=True)
class BudgetResult:
    limit_minor: Optional[int]
    registered_minor: int
    additional_planned_minor: int
    projected_minor: int
    remaining_minor: Optional[int]
    excess_minor: int
    percentage: Optional[Decimal]
    status: str


def budget_result(limit_minor: Optional[int], registered_minor: int, additional_planned_minor: int) -> BudgetResult:
    projected = registered_minor + additional_planned_minor
    if limit_minor is None:
        return BudgetResult(None, registered_minor, additional_planned_minor, projected, None, 0, None, "not_configured")
    validate_minor(limit_minor, allow_zero=True)
    remaining = limit_minor - registered_minor
    excess = max(registered_minor - limit_minor, 0)
    percentage = None if limit_minor == 0 else (Decimal(registered_minor) * Decimal(100) / Decimal(limit_minor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if registered_minor > limit_minor:
        status = "exceeded"
    elif registered_minor == limit_minor:
        status = "reached"
    elif projected > limit_minor:
        status = "risk"
        excess = projected - limit_minor
    else:
        status = "within"
    return BudgetResult(limit_minor, registered_minor, additional_planned_minor, projected, remaining, excess, percentage, status)


@dataclass(frozen=True)
class CashProjectionItem:
    key: str
    account_id: Optional[str]
    date: date
    signed_amount_minor: int
    source: str


def cash_projection(current_balance_minor: int, items: Sequence[CashProjectionItem], today: date) -> Tuple[int, List[CashProjectionItem]]:
    seen = set()
    normalized = []
    total = current_balance_minor
    for item in sorted(items, key=lambda candidate: (max(candidate.date, today), candidate.key)):
        if item.key in seen:
            continue
        seen.add(item.key)
        effective_item = item if item.date >= today else CashProjectionItem(item.key, item.account_id, today, item.signed_amount_minor, item.source)
        normalized.append(effective_item)
        total += item.signed_amount_minor
    return total, normalized
