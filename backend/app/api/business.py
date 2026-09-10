from datetime import date
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_mutation_session, get_session
from app.api.idempotency import canonical_hash, idempotent
from app.api.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountReferenceUpdate,
    BudgetSet,
    BudgetDefaultSet,
    CardTermsUpdate,
    CardCreate,
    CardUpdate,
    CashEntryCreate,
    CashEntryUpdate,
    CategoryCreate,
    CategoryUpdate,
    InvoicePaymentRequest,
    InvoiceAdjustmentCreate,
    InvoicePlanCreate,
    InvoiceDatesUpdate,
    InstallmentCancel,
    OccurrenceConfirm,
    OccurrenceUpdate,
    PaymentReverse,
    PlannedPurchaseConfirm,
    PlannedPurchaseCreate,
    PurchaseConfirm,
    PurchaseInput,
    PurchaseCategoryUpdate,
    RecurrenceCreate,
    RecurrenceVersion,
    RefundCreate,
    TransferCreate,
    TransferConfirm,
    TransferReverse,
    TransitionRequest,
    CoverageCreate,
    InitialPurchaseCreate,
    OpeningReplacement,
    SetupUpdate,
)
from app.api.security import require_mutation, require_session
from app.domain.analytics import compare_months, coverage_status, monthly_summary
from app.domain.calculations import DomainValidationError
from app.domain.planning import budget_for_category, card_commitment, projected_cash
from app.domain.services import (
    archive_entity,
    balance_for_account,
    calculate_invoice,
    close_invoice,
    confirm_planned_card_purchase,
    create_cash_entry,
    create_planned_card_purchase,
    create_purchase,
    create_transfer,
    preview_purchase,
    register_refund,
    reopen_invoice,
    reverse_invoice_payment,
    reverse_transfer,
    settle_invoice,
    transition_cash_entry,
    edit_purchase_category,
    update_card_terms,
    confirm_recurrence_occurrence,
    correct_cash_entry,
    create_initial_purchase,
    replace_opening_contribution,
    require_active,
    update_named_entity,
    audit,
    ensure_revision,
)
from app.domain.recurrence import generate_rule_occurrences, version_from_month
from app.domain.calculations import add_months, month_of
from app.storage.models import Account, Budget, BudgetDefault, Card, CashEntry, Category, CoverageInterval, Installment, Invoice, InvoiceAdjustment, InvoicePaymentPlan, Payment, PlannedCardPurchase, Purchase, RecurrenceOccurrence, RecurrenceRule, Refund, Transfer


class StalePreview(Exception):
    def __init__(self, preview):
        super().__init__("STALE_PREVIEW")
        self.preview = preview


def entity_dict(entity):
    return {column.name: getattr(entity, column.name) for column in entity.__table__.columns}


def paginated(query, page: int, page_size: int):
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [entity_dict(item) for item in rows], "page": page, "page_size": page_size, "total": total}


def purchase_preview_data(session: Session, payload: PurchaseInput):
    card, schedule = preview_purchase(session, payload.card_id, payload.purchase_date, payload.total_minor, payload.installment_count, payload.first_invoice_month, date.today())
    items = []
    for item in schedule:
        invoice = session.query(Invoice).filter(Invoice.card_id == card.id, Invoice.reference_month == item.reference_month).one_or_none()
        items.append(
            {
                "installment_number": item.installment_number,
                "amount_minor": item.amount_minor,
                "reference_month": item.reference_month,
                "closing_date": item.closing_date.isoformat(),
                "due_date": item.due_date.isoformat(),
                "invoice_revision": invoice.revision if invoice else None,
                "invoice_state": invoice.state if invoice else None,
            }
        )
    effect = {
        "card_id": card.id,
        "card_revision": card.revision,
        "total_minor": payload.total_minor,
        "installment_count": payload.installment_count,
        "schedule": items,
        "estimated_commitment_after_minor": card_commitment(session, card.id) + payload.total_minor,
    }
    return dict(effect, preview_token=canonical_hash(effect))


def payment_preview_data(session: Session, invoice_id: str, account_id: str, paid_date: date):
    invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    account = session.query(Account).filter(Account.id == account_id).one_or_none()
    if invoice is None or account is None:
        raise DomainValidationError("Fatura ou conta não encontrada.")
    total = calculate_invoice(session, invoice.id)
    effect = {
        "invoice_id": invoice.id,
        "invoice_revision": invoice.revision,
        "account_id": account.id,
        "account_revision": account.revision,
        "paid_date": paid_date.isoformat(),
        "amount_minor": total.payable_minor,
        "resulting_balance_minor": balance_for_account(session, account.id, date.today()) - total.payable_minor,
        "insufficient_balance": balance_for_account(session, account.id, date.today()) < total.payable_minor,
    }
    return dict(effect, preview_token=canonical_hash(effect))


def business_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(require_session)])

    @router.get("/setup")
    def setup_status(session: Session = Depends(get_session)):
        from app.storage.models import Setting

        settings = session.query(Setting).first()
        return {"setup_step": settings.setup_step if settings else 0, "has_account": session.query(Account).count() > 0, "locale": "pt-BR", "currency": "BRL"}

    @router.put("/setup", dependencies=[Depends(require_mutation)])
    def update_setup(payload: SetupUpdate, session: Session = Depends(get_mutation_session)):
        from app.storage.models import Setting
        settings = session.query(Setting).first()
        if settings is None:
            settings = Setting(id=1, setup_step=payload.setup_step)
            session.add(settings)
        elif payload.setup_step > settings.setup_step:
            settings.setup_step = payload.setup_step
            settings.revision += 1
        session.flush()
        return {"setup_step": settings.setup_step}

    @router.get("/accounts")
    def accounts(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), include_archived: bool = False, session: Session = Depends(get_session)):
        query = session.query(Account).order_by(Account.name)
        if not include_archived:
            query = query.filter(Account.archived_at.is_(None))
        result = paginated(query, page, page_size)
        for item in result["items"]:
            item["current_balance_minor"] = balance_for_account(session, item["id"], date.today())
        return result

    @router.post("/accounts", dependencies=[Depends(require_mutation)])
    def add_account(payload: AccountCreate, session: Session = Depends(get_mutation_session)):
        account = Account(**payload.dict())
        session.add(account)
        session.flush()
        return entity_dict(account)

    @router.post("/accounts/{entity_id}/archive", dependencies=[Depends(require_mutation)])
    def archive_account(entity_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(archive_entity(session, Account, entity_id, payload.expected_revision))

    @router.put("/accounts/{entity_id}", dependencies=[Depends(require_mutation)])
    def edit_account(entity_id: str, payload: AccountUpdate, session: Session = Depends(get_mutation_session)):
        return entity_dict(update_named_entity(session, Account, entity_id, payload.expected_revision, name=payload.name, institution=payload.institution))

    def account_reference_preview_data(session: Session, entity_id: str, payload: AccountReferenceUpdate):
        account = session.query(Account).filter(Account.id == entity_id).one_or_none()
        if account is None:
            raise DomainValidationError("Conta não encontrada.")
        ensure_revision(account, payload.expected_revision)
        if payload.reference_date > date.today():
            raise DomainValidationError("Data de referência não pode estar no futuro.")
        current = balance_for_account(session, account.id, date.today())
        entries = session.query(CashEntry).filter(CashEntry.account_id == account.id, CashEntry.status == "effective", CashEntry.effective_date >= payload.reference_date, CashEntry.effective_date <= date.today()).all()
        resulting = payload.reference_balance_minor + sum(item.signed_amount_minor for item in entries)
        effect = {"account_id": account.id, "account_revision": account.revision, "old_reference_date": account.reference_date.isoformat(), "old_reference_balance_minor": account.reference_balance_minor, "reference_date": payload.reference_date.isoformat(), "reference_balance_minor": payload.reference_balance_minor, "current_balance_before_minor": current, "current_balance_after_minor": resulting, "difference_minor": resulting - current, "covered_movement_count": len(entries)}
        return dict(effect, preview_token=canonical_hash(effect))

    @router.post("/accounts/{entity_id}/reference/preview")
    def preview_account_reference(entity_id: str, payload: AccountReferenceUpdate, session: Session = Depends(get_session)):
        return account_reference_preview_data(session, entity_id, payload)

    @router.post("/accounts/{entity_id}/reference", dependencies=[Depends(require_mutation)])
    def update_account_reference(entity_id: str, payload: AccountReferenceUpdate, session: Session = Depends(get_mutation_session)):
        current = account_reference_preview_data(session, entity_id, payload)
        if not payload.preview_token or current["preview_token"] != payload.preview_token:
            raise StalePreview(current)
        account = session.query(Account).filter(Account.id == entity_id).one()
        before = {"reference_date": account.reference_date, "reference_balance_minor": account.reference_balance_minor}
        account.reference_date = payload.reference_date
        account.reference_balance_minor = payload.reference_balance_minor
        account.revision += 1
        audit(session, "account", account.id, "reference_corrected", before=before, after={"reference_date": payload.reference_date, "reference_balance_minor": payload.reference_balance_minor}, reason=payload.reason)
        return entity_dict(account)

    @router.get("/categories")
    def categories(include_archived: bool = False, session: Session = Depends(get_session)):
        query = session.query(Category).order_by(Category.kind, Category.name)
        if not include_archived:
            query = query.filter(Category.archived_at.is_(None))
        return {"items": [entity_dict(item) for item in query.all()]}

    @router.post("/categories", dependencies=[Depends(require_mutation)])
    def add_category(payload: CategoryCreate, session: Session = Depends(get_mutation_session)):
        category = Category(**payload.dict())
        session.add(category)
        session.flush()
        return entity_dict(category)

    @router.post("/categories/{entity_id}/archive", dependencies=[Depends(require_mutation)])
    def archive_category(entity_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(archive_entity(session, Category, entity_id, payload.expected_revision))

    @router.put("/categories/{entity_id}", dependencies=[Depends(require_mutation)])
    def edit_category(entity_id: str, payload: CategoryUpdate, session: Session = Depends(get_mutation_session)):
        return entity_dict(update_named_entity(session, Category, entity_id, payload.expected_revision, name=payload.name))

    @router.get("/cards")
    def cards(include_archived: bool = False, session: Session = Depends(get_session)):
        query = session.query(Card).order_by(Card.name)
        if not include_archived:
            query = query.filter(Card.archived_at.is_(None))
        items = []
        for card in query.all():
            row = entity_dict(card)
            row["commitment_minor"] = card_commitment(session, card.id)
            row["available_estimated_minor"] = card.limit_minor - row["commitment_minor"]
            items.append(row)
        return {"items": items}

    @router.post("/cards", dependencies=[Depends(require_mutation)])
    def add_card(payload: CardCreate, session: Session = Depends(get_mutation_session)):
        if payload.default_account_id and session.query(Account).filter(Account.id == payload.default_account_id, Account.archived_at.is_(None)).count() != 1:
            raise DomainValidationError("Conta habitual inválida ou arquivada.")
        card = Card(**payload.dict())
        session.add(card)
        session.flush()
        return entity_dict(card)

    @router.post("/cards/{entity_id}/archive", dependencies=[Depends(require_mutation)])
    def archive_card(entity_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(archive_entity(session, Card, entity_id, payload.expected_revision))

    @router.put("/cards/{entity_id}", dependencies=[Depends(require_mutation)])
    def edit_card(entity_id: str, payload: CardUpdate, session: Session = Depends(get_mutation_session)):
        if payload.default_account_id:
            require_active(session, Account, payload.default_account_id, "Conta habitual")
        return entity_dict(update_named_entity(session, Card, entity_id, payload.expected_revision, name=payload.name, limit_minor=payload.limit_minor, default_account_id=payload.default_account_id))

    @router.post("/cards/{entity_id}/terms", dependencies=[Depends(require_mutation)])
    def card_terms(entity_id: str, payload: CardTermsUpdate, session: Session = Depends(get_mutation_session)):
        return entity_dict(update_card_terms(session, entity_id, payload.closing_day, payload.due_day, payload.expected_revision))

    @router.get("/cash-entries")
    def cash_entries(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), account_id: Optional[str] = None, category_id: Optional[str] = None, status: Optional[str] = None, source: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None, search: Optional[str] = None, session: Session = Depends(get_session)):
        query = session.query(CashEntry).order_by(CashEntry.planned_date.desc(), CashEntry.created_at.desc())
        if account_id:
            query = query.filter(CashEntry.account_id == account_id)
        if status:
            query = query.filter(CashEntry.status == status)
        if category_id:
            query = query.filter(CashEntry.category_id == category_id)
        if source:
            query = query.filter(CashEntry.source == source)
        if date_from:
            query = query.filter(CashEntry.planned_date >= date_from)
        if date_to:
            query = query.filter(CashEntry.planned_date <= date_to)
        if search:
            query = query.filter(CashEntry.description.ilike("%{}%".format(search)))
        return paginated(query, page, page_size)

    @router.post("/cash-entries", dependencies=[Depends(require_mutation)])
    def add_cash_entry(payload: CashEntryCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            entry = create_cash_entry(session, today=date.today(), **payload.dict())
            return entity_dict(entry)

        return idempotent(session, idempotency_key, "cash-entry:create", payload.dict(), action)

    @router.put("/cash-entries/{entry_id}", dependencies=[Depends(require_mutation)])
    def correct_entry(entry_id: str, payload: CashEntryUpdate, session: Session = Depends(get_mutation_session)):
        values = payload.dict(exclude={"expected_revision", "reason"})
        return entity_dict(correct_cash_entry(session, entry_id, payload.expected_revision, payload.reason, date.today(), **values))

    @router.post("/cash-entries/{entry_id}/{transition}", dependencies=[Depends(require_mutation)])
    def mutate_cash_entry(entry_id: str, transition: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(transition_cash_entry(session, entry_id, transition, payload.expected_revision, date.today(), payload.effective_date, payload.reason))

    @router.post("/transfers", dependencies=[Depends(require_mutation)])
    def add_transfer(payload: TransferCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            transfer = create_transfer(session, today=date.today(), **payload.dict())
            return entity_dict(transfer)

        return idempotent(session, idempotency_key, "transfer:create", payload.dict(), action)

    def transfer_preview_data(session: Session, payload: TransferCreate):
        source = require_active(session, Account, payload.from_account_id, "Conta de origem")
        target = require_active(session, Account, payload.to_account_id, "Conta de destino")
        if source.id == target.id:
            raise DomainValidationError("Contas de origem e destino devem ser diferentes.")
        if source.currency != target.currency:
            raise DomainValidationError("Transferência exige contas na mesma moeda.")
        source_balance = balance_for_account(session, source.id, date.today())
        target_balance = balance_for_account(session, target.id, date.today())
        effect = {"from_account_id": source.id, "from_revision": source.revision, "to_account_id": target.id, "to_revision": target.revision, "amount_minor": payload.amount_minor, "source_balance_after_minor": source_balance - payload.amount_minor, "target_balance_after_minor": target_balance + payload.amount_minor, "consolidated_change_minor": 0}
        return dict(effect, preview_token=canonical_hash(effect))

    @router.post("/transfers/preview")
    def preview_transfer(payload: TransferCreate, session: Session = Depends(get_session)):
        return transfer_preview_data(session, payload)

    @router.post("/transfers/confirm", dependencies=[Depends(require_mutation)])
    def confirm_transfer(payload: TransferConfirm, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        input_payload = TransferCreate(**payload.dict(exclude={"preview_token"}))
        def action():
            current = transfer_preview_data(session, input_payload)
            if current["preview_token"] != payload.preview_token:
                raise StalePreview(current)
            return entity_dict(create_transfer(session, today=date.today(), **input_payload.dict()))
        return idempotent(session, idempotency_key, "transfer:confirm", payload.dict(), action)

    @router.post("/transfers/{transfer_id}/reverse", dependencies=[Depends(require_mutation)])
    def reverse_transfer_route(transfer_id: str, payload: TransferReverse, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            transfer = reverse_transfer(session, transfer_id, payload.expected_revision, payload.reversal_date, date.today(), payload.reason)
            return entity_dict(transfer)

        return idempotent(session, idempotency_key, "transfer:reverse:{}".format(transfer_id), payload.dict(), action)

    @router.get("/transfers")
    def transfers(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), status: Optional[str] = None, session: Session = Depends(get_session)):
        query = session.query(Transfer).order_by(Transfer.planned_date.desc())
        if status:
            query = query.filter(Transfer.status == status)
        return paginated(query, page, page_size)

    @router.post("/purchases/preview")
    def purchase_preview(payload: PurchaseInput, session: Session = Depends(get_session)):
        return purchase_preview_data(session, payload)

    @router.post("/purchases", dependencies=[Depends(require_mutation)])
    def add_purchase(payload: PurchaseConfirm, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        input_payload = PurchaseInput(**payload.dict(exclude={"preview_token"}))
        def action():
            current = purchase_preview_data(session, input_payload)
            if current["preview_token"] != payload.preview_token:
                raise StalePreview(current)
            purchase = create_purchase(session, today=date.today(), **input_payload.dict())
            return entity_dict(purchase)

        return idempotent(session, idempotency_key, "purchase:create", payload.dict(), action)

    @router.get("/purchases")
    def purchases(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), card_id: Optional[str] = None, category_id: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None, session: Session = Depends(get_session)):
        query = session.query(Purchase).order_by(Purchase.purchase_date.desc())
        if card_id:
            query = query.filter(Purchase.card_id == card_id)
        if category_id:
            query = query.filter(Purchase.category_id == category_id)
        if date_from:
            query = query.filter(Purchase.purchase_date >= date_from)
        if date_to:
            query = query.filter(Purchase.purchase_date <= date_to)
        return paginated(query, page, page_size)

    @router.get("/purchases/{purchase_id}")
    def purchase_detail(purchase_id: str, session: Session = Depends(get_session)):
        purchase = session.query(Purchase).filter(Purchase.id == purchase_id).one_or_none()
        if purchase is None:
            raise DomainValidationError("Compra não encontrada.")
        return {"purchase": entity_dict(purchase), "installments": [entity_dict(item) for item in session.query(Installment).filter(Installment.purchase_id == purchase.id).order_by(Installment.installment_number).all()], "refunds": [entity_dict(item) for item in session.query(Refund).filter(Refund.purchase_id == purchase.id).all()]}

    @router.post("/cards/{card_id}/opening-purchases", dependencies=[Depends(require_mutation)])
    def add_opening_purchase(card_id: str, payload: InitialPurchaseCreate, session: Session = Depends(get_mutation_session)):
        return entity_dict(create_initial_purchase(session, card_id=card_id, **payload.dict()))

    @router.post("/purchases/{purchase_id}/category", dependencies=[Depends(require_mutation)])
    def purchase_category(purchase_id: str, payload: PurchaseCategoryUpdate, session: Session = Depends(get_mutation_session)):
        return entity_dict(edit_purchase_category(session, purchase_id, payload.category_id, payload.expected_revision))

    @router.post("/planned-purchases", dependencies=[Depends(require_mutation)])
    def add_planned(payload: PlannedPurchaseCreate, session: Session = Depends(get_mutation_session)):
        return entity_dict(create_planned_card_purchase(session, **payload.dict()))

    @router.get("/planned-purchases")
    def planned_purchases(status: Optional[str] = None, session: Session = Depends(get_session)):
        query = session.query(PlannedCardPurchase).order_by(PlannedCardPurchase.expected_date)
        if status:
            query = query.filter(PlannedCardPurchase.status == status)
        items = []
        for item in query.all():
            row = entity_dict(item)
            card = session.query(Card).filter(Card.id == item.card_id).one()
            row["dependency_warning"] = "Cartão arquivado; corrija ou cancele esta previsão." if card.archived_at else None
            items.append(row)
        return {"items": items}

    @router.post("/planned-purchases/{planned_id}/preview-confirmation")
    def preview_planned_confirmation(planned_id: str, payload: PurchaseInput, session: Session = Depends(get_session)):
        planned = session.query(PlannedCardPurchase).filter(PlannedCardPurchase.id == planned_id, PlannedCardPurchase.status == "planned").one_or_none()
        if planned is None or planned.card_id != payload.card_id:
            raise DomainValidationError("Previsão de compra inválida.")
        return purchase_preview_data(session, payload)

    @router.post("/planned-purchases/{planned_id}/confirm", dependencies=[Depends(require_mutation)])
    def confirm_planned(planned_id: str, payload: PlannedPurchaseConfirm, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            planned = session.query(PlannedCardPurchase).filter(PlannedCardPurchase.id == planned_id).one_or_none()
            if planned is None:
                raise DomainValidationError("Previsão de compra não encontrada.")
            preview_input = PurchaseInput(card_id=planned.card_id, description=planned.description, purchase_date=payload.purchase_date, total_minor=payload.total_minor, installment_count=payload.installment_count, category_id=planned.category_id, first_invoice_month=payload.first_invoice_month)
            current = purchase_preview_data(session, preview_input)
            if current["preview_token"] != payload.preview_token:
                raise StalePreview(current)
            purchase = confirm_planned_card_purchase(session, planned_id, payload.purchase_date, payload.total_minor, payload.installment_count, payload.first_invoice_month, date.today())
            return entity_dict(purchase)

        return idempotent(session, idempotency_key, "planned-purchase:confirm:{}".format(planned_id), payload.dict(), action)

    @router.post("/planned-purchases/{planned_id}/cancel", dependencies=[Depends(require_mutation)])
    def cancel_planned(planned_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        planned = session.query(PlannedCardPurchase).filter(PlannedCardPurchase.id == planned_id).one_or_none()
        if planned is None:
            raise DomainValidationError("Previsão não encontrada.")
        ensure_revision(planned, payload.expected_revision)
        if planned.status != "planned":
            raise DomainValidationError("Previsão não pode ser cancelada neste estado.")
        planned.status = "cancelled"
        planned.revision += 1
        audit(session, "planned_card_purchase", planned.id, "cancelled", reason=payload.reason)
        return entity_dict(planned)

    @router.get("/invoices")
    def invoices(card_id: Optional[str] = None, state: Optional[str] = None, session: Session = Depends(get_session)):
        query = session.query(Invoice).order_by(Invoice.due_date.desc())
        if card_id:
            query = query.filter(Invoice.card_id == card_id)
        if state:
            query = query.filter(Invoice.state == state)
        items = []
        for invoice in query.all():
            item = entity_dict(invoice)
            total = calculate_invoice(session, invoice.id)
            item.update({"net_minor": total.net_minor, "payable_minor": total.payable_minor})
            card = session.query(Card).filter(Card.id == invoice.card_id).one()
            item["dependency_warning"] = "Cartão arquivado; obrigação preservada no histórico." if card.archived_at else None
            items.append(item)
        return {"items": items}

    @router.get("/invoices/{invoice_id}")
    def invoice_detail(invoice_id: str, session: Session = Depends(get_session)):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None:
            raise DomainValidationError("Fatura não encontrada.")
        return {"invoice": entity_dict(invoice), "total": calculate_invoice(session, invoice.id).__dict__, "installments": [entity_dict(item) for item in session.query(Installment).filter(Installment.invoice_id == invoice.id).all()], "adjustments": [entity_dict(item) for item in session.query(InvoiceAdjustment).filter(InvoiceAdjustment.invoice_id == invoice.id).all()]}

    def invoice_dates_preview_data(session: Session, invoice_id: str, payload: InvoiceDatesUpdate):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None:
            raise DomainValidationError("Fatura não encontrada.")
        ensure_revision(invoice, payload.expected_revision)
        if invoice.state == "settled" or payload.closing_date >= payload.due_date:
            raise DomainValidationError("Fatura liquidada é imutável ou datas são inconsistentes.")
        effect = {"invoice_id": invoice.id, "invoice_revision": invoice.revision, "old_closing_date": invoice.closing_date.isoformat(), "old_due_date": invoice.due_date.isoformat(), "closing_date": payload.closing_date.isoformat(), "due_date": payload.due_date.isoformat(), "installment_count": session.query(Installment).filter(Installment.invoice_id == invoice.id).count()}
        return dict(effect, preview_token=canonical_hash(effect))

    @router.post("/invoices/{invoice_id}/dates/preview")
    def preview_invoice_dates(invoice_id: str, payload: InvoiceDatesUpdate, session: Session = Depends(get_session)):
        return invoice_dates_preview_data(session, invoice_id, payload)

    @router.post("/invoices/{invoice_id}/dates", dependencies=[Depends(require_mutation)])
    def update_invoice_dates(invoice_id: str, payload: InvoiceDatesUpdate, session: Session = Depends(get_mutation_session)):
        current = invoice_dates_preview_data(session, invoice_id, payload)
        if not payload.preview_token or current["preview_token"] != payload.preview_token:
            raise StalePreview(current)
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one()
        before = {"closing_date": invoice.closing_date, "due_date": invoice.due_date}
        invoice.closing_date = payload.closing_date
        invoice.due_date = payload.due_date
        invoice.revision += 1
        audit(session, "invoice", invoice.id, "dates_corrected", before=before, after={"closing_date": payload.closing_date, "due_date": payload.due_date})
        return entity_dict(invoice)

    @router.post("/invoices/{invoice_id}/close", dependencies=[Depends(require_mutation)])
    def close(invoice_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(close_invoice(session, invoice_id, payload.expected_revision))

    @router.post("/invoices/{invoice_id}/reopen", dependencies=[Depends(require_mutation)])
    def reopen(invoice_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(reopen_invoice(session, invoice_id, payload.expected_revision, payload.reason or ""))

    @router.get("/invoices/{invoice_id}/payment-preview")
    def payment_preview(invoice_id: str, account_id: str, paid_date: date, session: Session = Depends(get_session)):
        return payment_preview_data(session, invoice_id, account_id, paid_date)

    @router.post("/invoices/{invoice_id}/payments", dependencies=[Depends(require_mutation)])
    def pay(invoice_id: str, payload: InvoicePaymentRequest, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            current = payment_preview_data(session, invoice_id, payload.account_id, payload.paid_date)
            if current["preview_token"] != payload.preview_token:
                raise StalePreview(current)
            payment = settle_invoice(session, invoice_id, payload.account_id, payload.paid_date, payload.amount_minor, date.today())
            return entity_dict(payment)

        return idempotent(session, idempotency_key, "invoice:pay:{}".format(invoice_id), payload.dict(), action)

    @router.post("/invoices/{invoice_id}/payment-plan", dependencies=[Depends(require_mutation)])
    def plan_payment(invoice_id: str, payload: InvoicePlanCreate, session: Session = Depends(get_mutation_session)):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None or invoice.state == "settled":
            raise DomainValidationError("Fatura não aceita planejamento de pagamento.")
        require_active(session, Account, payload.account_id, "Conta pagadora")
        if session.query(InvoicePaymentPlan).filter(InvoicePaymentPlan.invoice_id == invoice_id, InvoicePaymentPlan.status == "active").count():
            raise DomainValidationError("A fatura já tem um plano de pagamento ativo.")
        plan = InvoicePaymentPlan(invoice_id=invoice_id, account_id=payload.account_id, planned_date=payload.planned_date, status="active")
        session.add(plan)
        session.flush()
        return entity_dict(plan)

    @router.get("/invoice-payment-plans")
    def payment_plans(session: Session = Depends(get_session)):
        return {"items": [entity_dict(item) for item in session.query(InvoicePaymentPlan).order_by(InvoicePaymentPlan.planned_date).all()]}

    @router.post("/invoice-payment-plans/{plan_id}/cancel", dependencies=[Depends(require_mutation)])
    def cancel_plan(plan_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        plan = session.query(InvoicePaymentPlan).filter(InvoicePaymentPlan.id == plan_id).one_or_none()
        if plan is None:
            raise DomainValidationError("Plano não encontrado.")
        ensure_revision(plan, payload.expected_revision)
        if plan.status != "active":
            raise DomainValidationError("Plano já está cancelado.")
        plan.status = "cancelled"
        plan.revision += 1
        return entity_dict(plan)

    @router.post("/invoices/{invoice_id}/adjustments", dependencies=[Depends(require_mutation)])
    def add_adjustment(invoice_id: str, payload: InvoiceAdjustmentCreate, session: Session = Depends(get_mutation_session)):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None or invoice.state == "settled":
            raise DomainValidationError("Fatura não aceita ajuste.")
        adjustment = InvoiceAdjustment(invoice_id=invoice.id, status="active", **payload.dict())
        session.add(adjustment)
        session.flush()
        audit(session, "invoice_adjustment", adjustment.id, "created")
        return entity_dict(adjustment)

    @router.post("/invoice-adjustments/{adjustment_id}/replace-opening", dependencies=[Depends(require_mutation)])
    def replace_opening(adjustment_id: str, payload: OpeningReplacement, session: Session = Depends(get_mutation_session)):
        return entity_dict(replace_opening_contribution(session, adjustment_id, payload.installment_ids, payload.amount_minor))

    @router.post("/installments/{installment_id}/cancel", dependencies=[Depends(require_mutation)])
    def cancel_installment(installment_id: str, payload: InstallmentCancel, session: Session = Depends(get_mutation_session)):
        installment = session.query(Installment).filter(Installment.id == installment_id).one_or_none()
        if installment is None:
            raise DomainValidationError("Parcela não encontrada.")
        ensure_revision(installment, payload.expected_revision)
        invoice = session.query(Invoice).filter(Invoice.id == installment.invoice_id).one()
        if installment.status != "confirmed" or invoice.state == "settled":
            raise DomainValidationError("Parcela não pode ser cancelada.")
        purchase = session.query(Purchase).filter(Purchase.id == installment.purchase_id).one()
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        other_cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        if refunded + other_cancelled + installment.amount_minor > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegível da compra.")
        installment.status = "cancelled"
        installment.cancellation_date = payload.cancellation_date
        installment.cancellation_reason = payload.reason
        installment.revision += 1
        audit(session, "installment", installment.id, "cancelled", reason=payload.reason)
        return entity_dict(installment)

    def installment_cancel_preview_data(session: Session, installment_id: str, payload: InstallmentCancel):
        installment = session.query(Installment).filter(Installment.id == installment_id).one_or_none()
        if installment is None:
            raise DomainValidationError("Parcela não encontrada.")
        ensure_revision(installment, payload.expected_revision)
        invoice = session.query(Invoice).filter(Invoice.id == installment.invoice_id).one()
        purchase = session.query(Purchase).filter(Purchase.id == installment.purchase_id).one()
        if installment.status != "confirmed" or invoice.state == "settled":
            raise DomainValidationError("Parcela não pode ser cancelada.")
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        if refunded + cancelled + installment.amount_minor > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegível da compra.")
        effect = {"installment_id": installment.id, "installment_revision": installment.revision, "amount_minor": installment.amount_minor, "invoice_id": invoice.id, "invoice_month": invoice.reference_month, "remaining_eligible_minor": purchase.total_minor - refunded - cancelled - installment.amount_minor, "reason": payload.reason, "cancellation_date": payload.cancellation_date.isoformat()}
        return dict(effect, preview_token=canonical_hash(effect))

    @router.post("/installments/{installment_id}/cancel-preview")
    def preview_installment_cancel(installment_id: str, payload: InstallmentCancel, session: Session = Depends(get_session)):
        return installment_cancel_preview_data(session, installment_id, payload)

    @router.post("/installments/{installment_id}/cancel-confirm", dependencies=[Depends(require_mutation)])
    def confirm_installment_cancel(installment_id: str, payload: InstallmentCancel, session: Session = Depends(get_mutation_session)):
        current = installment_cancel_preview_data(session, installment_id, payload)
        if not payload.preview_token or current["preview_token"] != payload.preview_token:
            raise StalePreview(current)
        installment = session.query(Installment).filter(Installment.id == installment_id).one()
        installment.status = "cancelled"
        installment.cancellation_date = payload.cancellation_date
        installment.cancellation_reason = payload.reason
        installment.revision += 1
        audit(session, "installment", installment.id, "cancelled", reason=payload.reason)
        return entity_dict(installment)

    @router.post("/payments/{payment_id}/reverse", dependencies=[Depends(require_mutation)])
    def reverse_payment(payment_id: str, payload: PaymentReverse, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            payment = reverse_invoice_payment(session, payment_id, payload.reversal_date, date.today(), payload.reason)
            return entity_dict(payment)

        return idempotent(session, idempotency_key, "payment:reverse:{}".format(payment_id), payload.dict(), action)

    @router.post("/refunds", dependencies=[Depends(require_mutation)])
    def refund(payload: RefundCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            value = register_refund(session, today=date.today(), **payload.dict())
            return entity_dict(value)

        return idempotent(session, idempotency_key, "refund:create", payload.dict(), action)

    def refund_preview_data(session: Session, payload: RefundCreate):
        purchase = session.query(Purchase).filter(Purchase.id == payload.purchase_id).one_or_none()
        if purchase is None:
            raise DomainValidationError("Compra não encontrada.")
        cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        if payload.amount_minor + cancelled + refunded > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegível da compra.")
        if payload.status == "confirmed" and (payload.recognition_date is None or payload.recognition_date > date.today()):
            raise DomainValidationError("Estorno confirmado exige data efetiva válida.")
        if payload.target_kind == "invoice":
            target = session.query(Invoice).filter(Invoice.id == payload.target_id).one_or_none()
            if target is None or target.state == "settled" or target.card_id != purchase.card_id:
                raise DomainValidationError("Estorno exige fatura não liquidada do mesmo cartão.")
        else:
            target = require_active(session, Account, payload.target_id, "Conta de reembolso")
        effect = {"purchase_id": purchase.id, "purchase_revision": purchase.revision, "amount_minor": payload.amount_minor, "status": payload.status, "target_kind": payload.target_kind, "target_id": target.id, "target_revision": target.revision, "remaining_eligible_minor": purchase.total_minor - cancelled - refunded - payload.amount_minor, "analytical_effect": "reduz despesa; não cria receita"}
        return dict(effect, preview_token=canonical_hash(effect))

    @router.post("/refunds/preview")
    def preview_refund(payload: RefundCreate, session: Session = Depends(get_session)):
        return refund_preview_data(session, payload)

    @router.post("/refunds/confirm", dependencies=[Depends(require_mutation)])
    def confirm_refund(payload: RefundCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            current = refund_preview_data(session, payload)
            if not payload.preview_token or current["preview_token"] != payload.preview_token:
                raise StalePreview(current)
            values = payload.dict(exclude={"preview_token"})
            return entity_dict(register_refund(session, today=date.today(), **values))
        return idempotent(session, idempotency_key, "refund:confirm", payload.dict(), action)

    @router.post("/budgets", dependencies=[Depends(require_mutation)])
    def set_budget(payload: BudgetSet, session: Session = Depends(get_mutation_session)):
        budget = session.query(Budget).filter(Budget.category_id == payload.category_id, Budget.month == payload.month).one_or_none()
        if budget:
            budget.amount_minor = payload.amount_minor
            budget.revision += 1
        else:
            budget = Budget(**payload.dict())
            session.add(budget)
        session.flush()
        return entity_dict(budget)

    @router.post("/budget-defaults", dependencies=[Depends(require_mutation)])
    def set_budget_default(payload: BudgetDefaultSet, session: Session = Depends(get_mutation_session)):
        category = require_active(session, Category, payload.category_id, "Categoria")
        if category.kind != "expense":
            raise DomainValidationError("Orçamento exige categoria de despesa.")
        current = session.query(BudgetDefault).filter(BudgetDefault.category_id == payload.category_id, BudgetDefault.effective_from_month == payload.effective_from_month).one_or_none()
        if current:
            current.amount_minor = payload.amount_minor
            current.revision += 1
        else:
            current = BudgetDefault(**payload.dict())
            session.add(current)
        session.flush()
        return entity_dict(current)

    @router.get("/budget-defaults")
    def budget_defaults(session: Session = Depends(get_session)):
        return {"items": [entity_dict(item) for item in session.query(BudgetDefault).order_by(BudgetDefault.effective_from_month.desc()).all()]}

    @router.get("/recurrences")
    def recurrences(session: Session = Depends(get_session)):
        rules = session.query(RecurrenceRule).order_by(RecurrenceRule.series_id, RecurrenceRule.version).all()
        occurrences = session.query(RecurrenceOccurrence).order_by(RecurrenceOccurrence.expected_date).all()
        rule_items = []
        for item in rules:
            row = entity_dict(item)
            model, entity_id = (Account, item.account_id) if item.account_id else (Card, item.card_id)
            dependency = session.query(model).filter(model.id == entity_id).one_or_none()
            row["dependency_warning"] = "Entidade vinculada arquivada; a recorrência permanece visível e exige correção." if dependency is not None and dependency.archived_at else None
            rule_items.append(row)
        return {"rules": rule_items, "occurrences": [entity_dict(item) for item in occurrences]}

    @router.post("/recurrences", dependencies=[Depends(require_mutation)])
    def add_recurrence(payload: RecurrenceCreate, session: Session = Depends(get_mutation_session)):
        if payload.kind in ("income", "expense") and not payload.account_id:
            raise DomainValidationError("Recorrência em conta exige conta.")
        if payload.kind == "card_purchase" and not payload.card_id:
            raise DomainValidationError("Recorrência no cartão exige cartão.")
        rule = RecurrenceRule(series_id=None, version=1, active=1, **payload.dict())
        from app.storage.models import uuid4_string
        rule.series_id = uuid4_string()
        session.add(rule)
        session.flush()
        generate_rule_occurrences(session, rule, add_months(month_of(date.today()), 12))
        return entity_dict(rule)

    @router.post("/recurrences/{rule_id}/version", dependencies=[Depends(require_mutation)])
    def version_recurrence(rule_id: str, payload: RecurrenceVersion, session: Session = Depends(get_mutation_session)):
        rule = session.query(RecurrenceRule).filter(RecurrenceRule.id == rule_id).one_or_none()
        if rule is None:
            raise DomainValidationError("Recorrência não encontrada.")
        ensure_revision(rule, payload.expected_revision)
        changes = payload.dict(exclude={"expected_revision", "cut_month"}, exclude_none=True)
        replacement = version_from_month(session, rule, payload.cut_month, **changes)
        generate_rule_occurrences(session, replacement, add_months(month_of(date.today()), 12))
        return entity_dict(replacement)

    @router.post("/recurrence-occurrences/{occurrence_id}/confirm", dependencies=[Depends(require_mutation)])
    def confirm_occurrence(occurrence_id: str, payload: OccurrenceConfirm, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            occurrence = confirm_recurrence_occurrence(session, occurrence_id, payload.actual_date, payload.actual_amount_minor, date.today())
            return entity_dict(occurrence)

        return idempotent(session, idempotency_key, "recurrence:confirm:{}".format(occurrence_id), payload.dict(), action)

    @router.put("/recurrence-occurrences/{occurrence_id}", dependencies=[Depends(require_mutation)])
    def edit_occurrence(occurrence_id: str, payload: OccurrenceUpdate, session: Session = Depends(get_mutation_session)):
        occurrence = session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.id == occurrence_id).one_or_none()
        if occurrence is None or occurrence.status != "planned":
            raise DomainValidationError("Somente ocorrência prevista pode receber exceção.")
        ensure_revision(occurrence, payload.expected_revision)
        before = {"expected_date": occurrence.expected_date, "expected_amount_minor": occurrence.expected_amount_minor}
        occurrence.expected_date = payload.expected_date
        occurrence.expected_amount_minor = payload.expected_amount_minor
        occurrence.exception = 1
        occurrence.revision += 1
        audit(session, "recurrence_occurrence", occurrence.id, "exception_created", before=before, after={"expected_date": payload.expected_date, "expected_amount_minor": payload.expected_amount_minor}, reason=payload.reason)
        return entity_dict(occurrence)

    @router.post("/recurrence-occurrences/{occurrence_id}/cancel", dependencies=[Depends(require_mutation)])
    def cancel_occurrence(occurrence_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        occurrence = session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.id == occurrence_id).one_or_none()
        if occurrence is None:
            raise DomainValidationError("Ocorrência não encontrada.")
        ensure_revision(occurrence, payload.expected_revision)
        from app.domain.states import ensure_transition
        ensure_transition("recurrence_occurrences", occurrence.status, "cancelled")
        occurrence.status = "cancelled"
        occurrence.revision += 1
        audit(session, "recurrence_occurrence", occurrence.id, "cancelled", reason=payload.reason)
        return entity_dict(occurrence)

    @router.get("/coverage")
    def coverage(session: Session = Depends(get_session)):
        return {"items": [entity_dict(item) for item in session.query(CoverageInterval).order_by(CoverageInterval.date_from.desc()).all()]}

    @router.post("/coverage", dependencies=[Depends(require_mutation)])
    def add_coverage(payload: CoverageCreate, session: Session = Depends(get_mutation_session)):
        if (payload.account_id is None) == (payload.card_id is None):
            raise DomainValidationError("Cobertura exige exatamente uma conta ou cartão.")
        interval = CoverageInterval(**payload.dict())
        if interval.date_from > interval.date_to:
            raise DomainValidationError("O início da cobertura deve ser anterior ou igual ao fim.")
        session.add(interval)
        session.flush()
        return entity_dict(interval)

    @router.get("/budgets/{month}")
    def budgets(month: str, session: Session = Depends(get_session)):
        return {"items": [dict(entity_dict(category), result=budget_for_category(session, category.id, month).__dict__) for category in session.query(Category).filter(Category.kind == "expense").all()]}

    @router.get("/reports/monthly/{month}")
    def monthly(month: str, previous_month: Optional[str] = None, session: Session = Depends(get_session)):
        summary = monthly_summary(session, month)
        return {"summary": summary.__dict__, "coverage": coverage_status(session, month), "comparison": compare_months(session, month, previous_month) if previous_month else None}

    @router.get("/reports/projection")
    def projection(through_month: str, session: Session = Depends(get_session)):
        return projected_cash(session, date.today(), through_month)

    @router.get("/audit/{entity_type}/{entity_id}")
    def audit_trail(entity_type: str, entity_id: str, session: Session = Depends(get_session)):
        from app.storage.models import AuditEvent
        return {"items": [entity_dict(item) for item in session.query(AuditEvent).filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id).order_by(AuditEvent.created_at).all()]}

    return router
