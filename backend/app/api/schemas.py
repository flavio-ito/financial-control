from datetime import date
from typing import Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field, validator

from app.config import SAFE_INTEGER_MAX


class MoneyModel(BaseModel):
    @validator("*", pre=True, allow_reuse=True)
    def reject_bool_for_integer(cls, value, field):
        if field.name.endswith("_minor") and isinstance(value, bool):
            raise ValueError("valor monetário deve ser inteiro")
        return value


Money = Field(..., ge=0, le=SAFE_INTEGER_MAX)
PositiveMoney = Field(..., ge=1, le=SAFE_INTEGER_MAX)


class SetupUpdate(BaseModel):
    setup_step: int = Field(..., ge=0, le=8)


class AccountCreate(MoneyModel):
    name: str = Field(..., min_length=1, max_length=120)
    institution: Optional[str] = Field(None, max_length=120)
    reference_date: date
    reference_balance_minor: int = Field(..., ge=-SAFE_INTEGER_MAX, le=SAFE_INTEGER_MAX)


class AccountUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    institution: Optional[str] = Field(None, max_length=120)
    expected_revision: int = Field(..., ge=1)


class AccountReferenceUpdate(MoneyModel):
    reference_date: date
    reference_balance_minor: int = Field(..., ge=-SAFE_INTEGER_MAX, le=SAFE_INTEGER_MAX)
    expected_revision: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)
    preview_token: Optional[str] = Field(None, min_length=64, max_length=64)


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: Literal["income", "expense"]


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    expected_revision: int = Field(..., ge=1)


class CardCreate(MoneyModel):
    name: str = Field(..., min_length=1, max_length=120)
    limit_minor: int = Money
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)
    default_account_id: Optional[str] = None


class CardUpdate(MoneyModel):
    name: str = Field(..., min_length=1, max_length=120)
    limit_minor: int = Money
    default_account_id: Optional[str] = None
    expected_revision: int = Field(..., ge=1)


class CashEntryCreate(MoneyModel):
    account_id: str
    kind: Literal["income", "expense", "balance_adjustment"]
    description: str = Field(..., min_length=1, max_length=240)
    amount_minor: int = PositiveMoney
    planned_date: date
    status: Literal["planned", "effective"]
    effective_date: Optional[date] = None
    category_id: Optional[str] = None
    note: Optional[str] = None


class CashEntryUpdate(CashEntryCreate):
    expected_revision: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)


class TransitionRequest(BaseModel):
    expected_revision: int = Field(..., ge=1)
    effective_date: Optional[date] = None
    reason: Optional[str] = None


class TransferCreate(MoneyModel):
    from_account_id: str
    to_account_id: str
    amount_minor: int = PositiveMoney
    planned_date: date
    status: Literal["planned", "effective"]
    effective_date: Optional[date] = None


class TransferConfirm(TransferCreate):
    preview_token: str = Field(..., min_length=64, max_length=64)


class TransferReverse(BaseModel):
    expected_revision: int = Field(..., ge=1)
    reversal_date: date
    reason: str = Field(..., min_length=1)


class PurchaseInput(MoneyModel):
    card_id: str
    description: str = Field(..., min_length=1, max_length=240)
    purchase_date: date
    total_minor: int = PositiveMoney
    installment_count: int = Field(..., ge=1)
    category_id: Optional[str] = None
    first_invoice_month: Optional[str] = Field(None, regex=r"^\d{4}-(0[1-9]|1[0-2])$")


class PurchaseConfirm(PurchaseInput):
    preview_token: str = Field(..., min_length=64, max_length=64)


class PlannedPurchaseCreate(MoneyModel):
    card_id: str
    description: str = Field(..., min_length=1, max_length=240)
    category_id: Optional[str] = None
    expected_date: date
    expected_amount_minor: int = PositiveMoney
    estimated_invoice_month: Optional[str] = Field(None, regex=r"^\d{4}-(0[1-9]|1[0-2])$")


class PlannedPurchaseConfirm(MoneyModel):
    purchase_date: date
    total_minor: int = PositiveMoney
    installment_count: int = Field(..., ge=1)
    first_invoice_month: Optional[str] = Field(None, regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    preview_token: str = Field(..., min_length=64, max_length=64)


class InvoicePaymentRequest(MoneyModel):
    account_id: str
    paid_date: date
    amount_minor: int = Money
    preview_token: str = Field(..., min_length=64, max_length=64)


class InvoicePlanCreate(BaseModel):
    account_id: str
    planned_date: date


class InvoiceDatesUpdate(BaseModel):
    closing_date: date
    due_date: date
    expected_revision: int = Field(..., ge=1)
    preview_token: Optional[str] = Field(None, min_length=64, max_length=64)


class RefundCreate(MoneyModel):
    purchase_id: str
    amount_minor: int = PositiveMoney
    status: Literal["planned", "confirmed"]
    planned_date: date
    recognition_date: Optional[date] = None
    target_kind: Literal["invoice", "account"]
    target_id: str
    reason: str = Field(..., min_length=1)
    preview_token: Optional[str] = Field(None, min_length=64, max_length=64)


class BudgetSet(MoneyModel):
    category_id: str
    month: str = Field(..., regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_minor: int = Money


class BudgetDefaultSet(MoneyModel):
    category_id: str
    effective_from_month: str = Field(..., regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_minor: int = Money


class CardTermsUpdate(BaseModel):
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)
    expected_revision: int = Field(..., ge=1)


class PurchaseCategoryUpdate(BaseModel):
    category_id: Optional[str] = None
    expected_revision: int = Field(..., ge=1)


class InvoiceAdjustmentCreate(MoneyModel):
    signed_amount_minor: int = Field(..., ge=-SAFE_INTEGER_MAX, le=SAFE_INTEGER_MAX)
    kind: Literal["opening", "debit"]
    description: str = Field(..., min_length=1, max_length=240)
    category_id: Optional[str] = None

    @validator("signed_amount_minor")
    def adjustment_not_zero(cls, value):
        if value == 0:
            raise ValueError("ajuste não pode ser zero")
        return value


class InstallmentCancel(BaseModel):
    expected_revision: int = Field(..., ge=1)
    cancellation_date: date
    reason: str = Field(..., min_length=1)
    preview_token: Optional[str] = Field(None, min_length=64, max_length=64)


class InitialPurchaseCreate(MoneyModel):
    description: str = Field(..., min_length=1, max_length=240)
    purchase_date: date
    total_minor: int = PositiveMoney
    total_installments: int = Field(..., ge=1)
    next_installment: int = Field(..., ge=1)
    category_id: Optional[str] = None
    first_pending_invoice_month: str = Field(..., regex=r"^\d{4}-(0[1-9]|1[0-2])$")


class OpeningReplacement(MoneyModel):
    installment_ids: list
    amount_minor: int = PositiveMoney


class PaymentReverse(BaseModel):
    reversal_date: date
    reason: str = Field(..., min_length=1)


class RecurrenceCreate(MoneyModel):
    kind: Literal["income", "expense", "card_purchase"]
    description: str = Field(..., min_length=1, max_length=240)
    account_id: Optional[str] = None
    card_id: Optional[str] = None
    day: int = Field(..., ge=1, le=31)
    start_month: str = Field(..., regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    end_month: Optional[str] = Field(None, regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    amount_minor: int = PositiveMoney
    category_id: Optional[str] = None


class RecurrenceVersion(BaseModel):
    expected_revision: int = Field(..., ge=1)
    cut_month: str = Field(..., regex=r"^\d{4}-(0[1-9]|1[0-2])$")
    description: Optional[str] = Field(None, min_length=1, max_length=240)
    day: Optional[int] = Field(None, ge=1, le=31)
    amount_minor: Optional[int] = Field(None, ge=1, le=SAFE_INTEGER_MAX)
    category_id: Optional[str] = None


class OccurrenceConfirm(MoneyModel):
    actual_date: date
    actual_amount_minor: int = PositiveMoney


class OccurrenceUpdate(MoneyModel):
    expected_revision: int = Field(..., ge=1)
    expected_date: date
    expected_amount_minor: int = PositiveMoney
    reason: str = Field(..., min_length=1)


class CoverageCreate(BaseModel):
    account_id: Optional[str] = None
    card_id: Optional[str] = None
    date_from: date
    date_to: date
    status: Literal["complete", "partial", "unknown"]
    note: Optional[str] = None
