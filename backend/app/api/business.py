from datetime import date
import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_mutation_session, get_session
from app.api.idempotency import canonical_hash, idempotent
from app.api.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountReferenceUpdate,
    CardTermsUpdate,
    CardCreate,
    CardUpdate,
    InvestmentCreate,
    InvestmentSettingsUpdate,
    InvestmentWithdrawalCreate,
    InvestmentUpdate,
    CashEntryCreate,
    CashEntryInstallmentCreate,
    CashEntryUpdate,
    CategoryCreate,
    CategoryUpdate,
    InvoicePaymentRequest,
    InvoiceAdjustmentCreate,
    InvoiceDatesUpdate,
    InstallmentCancel,
    OccurrenceConfirm,
    OccurrenceUpdate,
    PaymentReverse,
    PurchaseConfirm,
    PurchaseInput,
    PurchaseCategoryUpdate,
    PurchaseUpdate,
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
from app.domain.card_commitment import card_commitment
from app.domain.services import (
    archive_entity,
    balance_for_account,
    calculate_invoice,
    close_invoice,
    create_cash_entry,
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
    correct_purchase,
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
from app.domain.investments import materialize_daily_yields
from app.domain.recurrence import generate_rule_occurrences, version_from_month
from app.domain.calculations import add_months, limited_date, month_of, split_installments
from app.storage.models import Account, Card, CashEntry, Category, CoverageInterval, Installment, Investment, InvestmentWithdrawal, InvestmentYield, Invoice, InvoiceAdjustment, Payment, Purchase, RecurrenceOccurrence, RecurrenceRule, Refund, Setting, Transfer


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
        raise DomainValidationError("Fatura ou conta nÃ£o encontrada.")
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

    @router.get("/settings/investments")
    def investment_settings(session: Session = Depends(get_session)):
        settings = session.query(Setting).first()
        return {"cdi_annual_rate_bps": settings.cdi_annual_rate_bps if settings else 1447, "revision": settings.revision if settings else 1}

    @router.put("/settings/investments", dependencies=[Depends(require_mutation)])
    def update_investment_settings(payload: InvestmentSettingsUpdate, session: Session = Depends(get_mutation_session)):
        settings = session.query(Setting).first()
        if settings is None:
            settings = Setting(id=1, cdi_annual_rate_bps=payload.cdi_annual_rate_bps)
            session.add(settings)
        else:
            ensure_revision(settings, payload.expected_revision)
            settings.cdi_annual_rate_bps = payload.cdi_annual_rate_bps
            settings.revision += 1
        session.flush()
        return {"cdi_annual_rate_bps": settings.cdi_annual_rate_bps, "revision": settings.revision}

    @router.get("/accounts")
    def accounts(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), include_archived: bool = False, session: Session = Depends(get_mutation_session)):
        materialize_daily_yields(session, date.today())
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
            raise DomainValidationError("Conta nÃ£o encontrada.")
        ensure_revision(account, payload.expected_revision)
        if payload.reference_date > date.today():
            raise DomainValidationError("Data de referÃªncia nÃ£o pode estar no futuro.")
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
        query = session.query(Category).order_by(Category.name)
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
            raise DomainValidationError("Conta habitual invÃ¡lida ou arquivada.")
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

    @router.get("/investments")
    def investments(include_archived: bool = False, session: Session = Depends(get_mutation_session)):
        materialize_daily_yields(session, date.today())
        query = session.query(Investment).order_by(Investment.created_at.desc())
        if not include_archived:
            query = query.filter(Investment.archived_at.is_(None))
        return {"items": [entity_dict(item) for item in query.all()]}

    @router.get("/investment-yields")
    def investment_yields(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), date_from: Optional[date] = None, date_to: Optional[date] = None, session: Session = Depends(get_mutation_session)):
        materialize_daily_yields(session, date.today())
        yields_query = session.query(InvestmentYield)
        withdrawals_query = session.query(InvestmentWithdrawal)
        if date_from:
            yields_query = yields_query.filter(InvestmentYield.yield_date >= date_from)
            withdrawals_query = withdrawals_query.filter(InvestmentWithdrawal.withdrawal_date >= date_from)
        if date_to:
            yields_query = yields_query.filter(InvestmentYield.yield_date <= date_to)
            withdrawals_query = withdrawals_query.filter(InvestmentWithdrawal.withdrawal_date <= date_to)
        yields = yields_query.all()
        withdrawals = withdrawals_query.all()
        items = [{
            "id": item.id,
            "investment_id": item.investment_id,
            "account_id": item.account_id,
            "description": "Rendimento diÃ¡rio de CDI",
            "kind": "income",
            "signed_amount_minor": item.amount_minor,
            "planned_date": item.yield_date,
            "effective_date": item.yield_date,
            "status": "effective",
            "category_id": None,
            "source": "investment_yield",
            "revision": item.revision,
            "cdi_annual_rate_bps": item.cdi_annual_rate_bps,
            "investment_cdi_percentage": item.investment_cdi_percentage,
            "balance_before_minor": item.balance_before_minor,
            "balance_after_minor": item.balance_after_minor,
        } for item in yields]
        items.extend({
            "id": item.id,
            "investment_id": item.investment_id,
            "account_id": item.account_id,
            "description": "Saque de investimento",
            "kind": "expense",
            "signed_amount_minor": -item.amount_minor,
            "planned_date": item.withdrawal_date,
            "effective_date": item.withdrawal_date,
            "status": "effective",
            "category_id": None,
            "source": "investment_withdrawal",
            "revision": item.revision,
            "balance_before_minor": item.balance_before_minor,
            "balance_after_minor": item.balance_after_minor,
        } for item in withdrawals)
        items.sort(key=lambda item: (item["planned_date"], item["id"]), reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return {"items": items[start:start + page_size], "page": page, "page_size": page_size, "total": total}

    @router.post("/investment-withdrawals", dependencies=[Depends(require_mutation)])
    def add_investment_withdrawal(payload: InvestmentWithdrawalCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            if payload.withdrawal_date != date.today():
                raise DomainValidationError("O saque deve ser registrado na data atual.")
            materialize_daily_yields(session, payload.withdrawal_date)
            investment = require_active(session, Investment, payload.investment_id, "Investimento")
            if payload.amount_minor > investment.amount_minor:
                raise DomainValidationError("O valor do saque excede o saldo do investimento.")
            before = investment.amount_minor
            entry = CashEntry(
                account_id=investment.account_id,
                kind="expense",
                description="Saque de investimento",
                signed_amount_minor=-payload.amount_minor,
                planned_date=payload.withdrawal_date,
                effective_date=payload.withdrawal_date,
                status="effective",
                source="bank_api",
                note="Saque automÃ¡tico do investimento {}".format(investment.id),
            )
            session.add(entry)
            session.flush()
            investment.amount_minor -= payload.amount_minor
            investment.revision += 1
            withdrawal = InvestmentWithdrawal(
                investment_id=investment.id,
                account_id=investment.account_id,
                withdrawal_date=payload.withdrawal_date,
                amount_minor=payload.amount_minor,
                balance_before_minor=before,
                balance_after_minor=investment.amount_minor,
                cash_entry_id=entry.id,
            )
            session.add(withdrawal)
            session.flush()
            return entity_dict(withdrawal)

        return idempotent(session, idempotency_key, "investment-withdrawal:create", payload.dict(), action)

    @router.post("/investments", dependencies=[Depends(require_mutation)])
    def add_investment(payload: InvestmentCreate, session: Session = Depends(get_mutation_session)):
        require_active(session, Account, payload.account_id, "Banco associado")
        investment = Investment(**payload.dict())
        session.add(investment)
        session.flush()
        return entity_dict(investment)

    @router.put("/investments/{entity_id}", dependencies=[Depends(require_mutation)])
    def edit_investment(entity_id: str, payload: InvestmentUpdate, session: Session = Depends(get_mutation_session)):
        investment = require_active(session, Investment, entity_id, "Investimento")
        ensure_revision(investment, payload.expected_revision)
        require_active(session, Account, payload.account_id, "Banco associado")
        before = entity_dict(investment)
        investment.account_id = payload.account_id
        investment.amount_minor = payload.amount_minor
        investment.cdi_percentage = payload.cdi_percentage
        investment.revision += 1
        audit(session, "investment", investment.id, "updated", before=before, after=entity_dict(investment))
        return entity_dict(investment)

    @router.post("/investments/{entity_id}/archive", dependencies=[Depends(require_mutation)])
    def archive_investment(entity_id: str, payload: TransitionRequest, session: Session = Depends(get_mutation_session)):
        return entity_dict(archive_entity(session, Investment, entity_id, payload.expected_revision))

    @router.get("/cash-entries")
    def cash_entries(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), account_id: Optional[str] = None, card_id: Optional[str] = None, category_id: Optional[str] = None, status: Optional[str] = None, source: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None, search: Optional[str] = None, investment_only: bool = False, active_only: bool = False, session: Session = Depends(get_session)):
        query = session.query(CashEntry).order_by(CashEntry.planned_date.desc(), CashEntry.created_at.desc())
        if active_only:
            query = query.filter(CashEntry.status.in_(("planned", "effective")))
        if investment_only:
            investment_account_ids = select(Investment.account_id).where(Investment.archived_at.is_(None))
            query = query.filter(CashEntry.account_id.in_(investment_account_ids))
        if account_id:
            query = query.filter(CashEntry.account_id == account_id)
        if card_id:
            payment_ids = select(Payment.id).join(Invoice, Payment.invoice_id == Invoice.id).where(Invoice.card_id == card_id)
            refund_ids = select(Refund.id).outerjoin(Purchase, Refund.purchase_id == Purchase.id).outerjoin(Invoice, Refund.target_invoice_id == Invoice.id).where(or_(Purchase.card_id == card_id, Invoice.card_id == card_id))
            query = query.filter(or_(CashEntry.payment_id.in_(payment_ids), CashEntry.refund_id.in_(refund_ids)))
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
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        payment_ids = {row.payment_id for row in rows if row.payment_id}
        refund_ids = {row.refund_id for row in rows if row.refund_id}
        card_by_payment = dict(
            session.query(Payment.id, Invoice.card_id)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(Payment.id.in_(payment_ids))
            .all()
        ) if payment_ids else {}
        card_by_refund = {}
        if refund_ids:
            refund_cards = (
                session.query(Refund.id, Purchase.card_id, Invoice.card_id)
                .outerjoin(Purchase, Refund.purchase_id == Purchase.id)
                .outerjoin(Invoice, Refund.target_invoice_id == Invoice.id)
                .filter(Refund.id.in_(refund_ids))
                .all()
            )
            card_by_refund = {refund_id: purchase_card_id or invoice_card_id for refund_id, purchase_card_id, invoice_card_id in refund_cards}
        items = []
        for row in rows:
            item = entity_dict(row)
            item["card_id"] = card_by_payment.get(row.payment_id) or card_by_refund.get(row.refund_id)
            items.append(item)
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    @router.post("/cash-entries", dependencies=[Depends(require_mutation)])
    def add_cash_entry(payload: CashEntryCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            entry = create_cash_entry(session, today=date.today(), **payload.dict())
            return entity_dict(entry)

        return idempotent(session, idempotency_key, "cash-entry:create", payload.dict(), action)

    @router.post("/cash-entries/installments", dependencies=[Depends(require_mutation)])
    def add_cash_entry_installments(payload: CashEntryInstallmentCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), session: Session = Depends(get_mutation_session)):
        def action():
            amounts = split_installments(payload.amount_minor, payload.installment_count)
            entries = []
            first_month = month_of(payload.planned_date)
            for index, amount in enumerate(amounts):
                planned_date = limited_date(add_months(first_month, index), payload.planned_date.day)
                is_first = index == 0
                status = payload.status if is_first else "planned"
                effective_date = payload.effective_date if is_first and status == "effective" else None
                description = payload.description if payload.installment_count == 1 else "{} ({}/{})".format(payload.description, index + 1, payload.installment_count)
                entry = create_cash_entry(
                    session,
                    account_id=payload.account_id,
                    kind=payload.kind,
                    description=description,
                    amount_minor=amount,
                    planned_date=planned_date,
                    status=status,
                    today=date.today(),
                    category_id=payload.category_id,
                    effective_date=effective_date,
                    note=payload.note,
                )
                entries.append(entity_dict(entry))
            return {"items": entries}

        return idempotent(session, idempotency_key, "cash-entry:create-installments", payload.dict(), action)

    @router.put("/cash-entries/{entry_id}", dependencies=[Depends(require_mutation)])
    def correct_entry(entry_id: str, payload: CashEntryUpdate, session: Session = Depends(get_mutation_session)):
        values = payload.dict(exclude={"expected_revision"})
        return entity_dict(correct_cash_entry(session, entry_id, payload.expected_revision, date.today(), **values))

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
            raise DomainValidationError("TransferÃªncia exige contas na mesma moeda.")
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

    @router.get("/purchase-installments")
    def purchase_installments(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), account_id: Optional[str] = None, card_id: Optional[str] = None, category_id: Optional[str] = None, date_from: Optional[date] = None, date_to: Optional[date] = None, session: Session = Depends(get_session)):
        query = (
            session.query(Installment, Purchase, Invoice, Card)
            .join(Purchase, Purchase.id == Installment.purchase_id)
            .join(Invoice, Invoice.id == Installment.invoice_id)
            .join(Card, Card.id == Purchase.card_id)
            .filter(Purchase.status == "confirmed", Installment.status.in_(("confirmed", "historical_settled")))
            .order_by(Invoice.reference_month.desc(), Purchase.purchase_date.desc(), Installment.installment_number.desc())
        )
        if account_id:
            query = query.filter(Card.default_account_id == account_id)
        if card_id:
            query = query.filter(Purchase.card_id == card_id)
        if category_id:
            query = query.filter(Installment.category_id_snapshot == category_id)
        if date_from:
            query = query.filter(Invoice.reference_month >= date_from.strftime("%Y-%m"))
        if date_to:
            query = query.filter(Invoice.reference_month <= date_to.strftime("%Y-%m"))
        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()
        items = [{
            "id": installment.id,
            "purchase_id": purchase.id,
            "description": purchase.description,
            "card_id": purchase.card_id,
            "category_id": installment.category_id_snapshot,
            "purchase_date": purchase.purchase_date,
            "reference_month": invoice.reference_month,
            "due_date": invoice.due_date,
            "installment_number": installment.installment_number,
            "installment_count": purchase.installment_count,
            "amount_minor": installment.amount_minor,
            "total_minor": purchase.total_minor,
            "purchase_revision": purchase.revision,
            "purchase_source": purchase.source,
        } for installment, purchase, invoice, _card in rows]
        return {"items": items, "page": page, "page_size": page_size, "total": total}

    @router.get("/purchases/{purchase_id}")
    def purchase_detail(purchase_id: str, session: Session = Depends(get_session)):
        purchase = session.query(Purchase).filter(Purchase.id == purchase_id).one_or_none()
        if purchase is None:
            raise DomainValidationError("Compra nÃ£o encontrada.")
        return {"purchase": entity_dict(purchase), "installments": [entity_dict(item) for item in session.query(Installment).filter(Installment.purchase_id == purchase.id).order_by(Installment.installment_number).all()], "refunds": [entity_dict(item) for item in session.query(Refund).filter(Refund.purchase_id == purchase.id).all()]}

    @router.post("/cards/{card_id}/opening-purchases", dependencies=[Depends(require_mutation)])
    def add_opening_purchase(card_id: str, payload: InitialPurchaseCreate, session: Session = Depends(get_mutation_session)):
        return entity_dict(create_initial_purchase(session, card_id=card_id, **payload.dict()))

    @router.post("/purchases/{purchase_id}/category", dependencies=[Depends(require_mutation)])
    def purchase_category(purchase_id: str, payload: PurchaseCategoryUpdate, session: Session = Depends(get_mutation_session)):
        return entity_dict(edit_purchase_category(session, purchase_id, payload.category_id, payload.expected_revision))

    @router.put("/purchases/{purchase_id}", dependencies=[Depends(require_mutation)])
    def update_purchase(purchase_id: str, payload: PurchaseUpdate, session: Session = Depends(get_mutation_session)):
        values = payload.dict(exclude={"expected_revision"})
        return entity_dict(correct_purchase(session, purchase_id, payload.expected_revision, date.today(), **values))

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
            item["dependency_warning"] = "CartÃ£o arquivado; obrigaÃ§Ã£o preservada no histÃ³rico." if card.archived_at else None
            items.append(item)
        return {"items": items}

    @router.get("/invoices/{invoice_id}")
    def invoice_detail(invoice_id: str, session: Session = Depends(get_session)):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None:
            raise DomainValidationError("Fatura nÃ£o encontrada.")
        return {"invoice": entity_dict(invoice), "total": calculate_invoice(session, invoice.id).__dict__, "installments": [entity_dict(item) for item in session.query(Installment).filter(Installment.invoice_id == invoice.id).all()], "adjustments": [entity_dict(item) for item in session.query(InvoiceAdjustment).filter(InvoiceAdjustment.invoice_id == invoice.id).all()]}

    def invoice_dates_preview_data(session: Session, invoice_id: str, payload: InvoiceDatesUpdate):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None:
            raise DomainValidationError("Fatura nÃ£o encontrada.")
        ensure_revision(invoice, payload.expected_revision)
        if invoice.state == "settled" or payload.closing_date >= payload.due_date:
            raise DomainValidationError("Fatura liquidada Ã© imutÃ¡vel ou datas sÃ£o inconsistentes.")
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

    @router.post("/invoices/{invoice_id}/adjustments", dependencies=[Depends(require_mutation)])
    def add_adjustment(invoice_id: str, payload: InvoiceAdjustmentCreate, session: Session = Depends(get_mutation_session)):
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
        if invoice is None or invoice.state == "settled":
            raise DomainValidationError("Fatura nÃ£o aceita ajuste.")
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
            raise DomainValidationError("Parcela nÃ£o encontrada.")
        ensure_revision(installment, payload.expected_revision)
        invoice = session.query(Invoice).filter(Invoice.id == installment.invoice_id).one()
        if installment.status != "confirmed" or invoice.state == "settled":
            raise DomainValidationError("Parcela nÃ£o pode ser cancelada.")
        purchase = session.query(Purchase).filter(Purchase.id == installment.purchase_id).one()
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        other_cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        if refunded + other_cancelled + installment.amount_minor > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegÃ­vel da compra.")
        installment.status = "cancelled"
        installment.cancellation_date = payload.cancellation_date
        installment.cancellation_reason = payload.reason
        installment.revision += 1
        audit(session, "installment", installment.id, "cancelled", reason=payload.reason)
        return entity_dict(installment)

    def installment_cancel_preview_data(session: Session, installment_id: str, payload: InstallmentCancel):
        installment = session.query(Installment).filter(Installment.id == installment_id).one_or_none()
        if installment is None:
            raise DomainValidationError("Parcela nÃ£o encontrada.")
        ensure_revision(installment, payload.expected_revision)
        invoice = session.query(Invoice).filter(Invoice.id == installment.invoice_id).one()
        purchase = session.query(Purchase).filter(Purchase.id == installment.purchase_id).one()
        if installment.status != "confirmed" or invoice.state == "settled":
            raise DomainValidationError("Parcela nÃ£o pode ser cancelada.")
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        if refunded + cancelled + installment.amount_minor > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegÃ­vel da compra.")
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
            raise DomainValidationError("Compra nÃ£o encontrada.")
        cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
        refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
        if payload.amount_minor + cancelled + refunded > purchase.total_minor:
            raise DomainValidationError("Estorno/cancelamento excede o valor elegÃ­vel da compra.")
        if payload.status == "confirmed" and (payload.recognition_date is None or payload.recognition_date > date.today()):
            raise DomainValidationError("Estorno confirmado exige data efetiva vÃ¡lida.")
        if payload.target_kind == "invoice":
            target = session.query(Invoice).filter(Invoice.id == payload.target_id).one_or_none()
            if target is None or target.state == "settled" or target.card_id != purchase.card_id:
                raise DomainValidationError("Estorno exige fatura nÃ£o liquidada do mesmo cartÃ£o.")
        else:
            target = require_active(session, Account, payload.target_id, "Conta de reembolso")
        effect = {"purchase_id": purchase.id, "purchase_revision": purchase.revision, "amount_minor": payload.amount_minor, "status": payload.status, "target_kind": payload.target_kind, "target_id": target.id, "target_revision": target.revision, "remaining_eligible_minor": purchase.total_minor - cancelled - refunded - payload.amount_minor, "analytical_effect": "reduz despesa; nÃ£o cria receita"}
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

    @router.get("/recurrences")
    def recurrences(session: Session = Depends(get_session)):
        rules = session.query(RecurrenceRule).order_by(RecurrenceRule.series_id, RecurrenceRule.version).all()
        occurrences = session.query(RecurrenceOccurrence).order_by(RecurrenceOccurrence.expected_date).all()
        rule_items = []
        for item in rules:
            row = entity_dict(item)
            model, entity_id = (Account, item.account_id) if item.account_id else (Card, item.card_id)
            dependency = session.query(model).filter(model.id == entity_id).one_or_none()
            row["dependency_warning"] = "Entidade vinculada arquivada; a recorrÃªncia permanece visÃ­vel e exige correÃ§Ã£o." if dependency is not None and dependency.archived_at else None
            rule_items.append(row)
        return {"rules": rule_items, "occurrences": [entity_dict(item) for item in occurrences]}

    @router.post("/recurrences", dependencies=[Depends(require_mutation)])
    def add_recurrence(payload: RecurrenceCreate, session: Session = Depends(get_mutation_session)):
        if payload.kind in ("income", "expense") and not payload.account_id:
            raise DomainValidationError("RecorrÃªncia em conta exige conta.")
        if payload.kind == "card_purchase" and not payload.card_id:
            raise DomainValidationError("RecorrÃªncia no cartÃ£o exige cartÃ£o.")
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
            raise DomainValidationError("RecorrÃªncia nÃ£o encontrada.")
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
            raise DomainValidationError("Somente ocorrÃªncia prevista pode receber exceÃ§Ã£o.")
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
            raise DomainValidationError("OcorrÃªncia nÃ£o encontrada.")
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
            raise DomainValidationError("Cobertura exige exatamente uma conta ou cartÃ£o.")
        interval = CoverageInterval(**payload.dict())
        if interval.date_from > interval.date_to:
            raise DomainValidationError("O inÃ­cio da cobertura deve ser anterior ou igual ao fim.")
        session.add(interval)
        session.flush()
        return entity_dict(interval)

    @router.get("/reports/overview")
    def overview_report(date_from: str, date_to: str, account_id: Optional[str] = None, card_id: Optional[str] = None, category_id: Optional[str] = None, session: Session = Depends(get_session)):
        if date_from > date_to:
            raise DomainValidationError("O inicio do periodo deve ser anterior ou igual ao fim.")
        accounts_query = session.query(Account).filter(Account.archived_at.is_(None))
        if account_id:
            accounts_query = accounts_query.filter(Account.id == account_id)
        balance_accounts = accounts_query.all()
        months = []
        month = date_from
        while month <= date_to and len(months) < 36:
            summary = monthly_summary(session, month, account_id, card_id, category_id)
            balance_date = limited_date(month, 31)
            balance_minor = None if any(account.reference_date > balance_date for account in balance_accounts) else sum(
                balance_for_account(session, account.id, balance_date) for account in balance_accounts
            )
            months.append(dict(month=month, balance_minor=balance_minor, **summary.__dict__))
            month = add_months(month, 1)
        if month <= date_to:
            raise DomainValidationError("O periodo maximo para a visao geral e de 36 meses.")
        return {"months": months}

    @router.get("/reports/future-balance")
    def future_balance(account_id: Optional[str] = None, session: Session = Depends(get_session)):
        today = date.today()
        accounts_query = session.query(Account).filter(Account.archived_at.is_(None))
        if account_id:
            accounts_query = accounts_query.filter(Account.id == account_id)
        accounts = accounts_query.all()
        account_ids = [account.id for account in accounts]
        if not account_ids:
            return {"current_minor": 0, "planned_expenses_minor": 0, "installments_minor": 0, "future_balance_minor": 0}
        current_minor = sum(balance_for_account(session, account.id, today) for account in accounts)

        planned_expenses_query = session.query(func.coalesce(func.sum(CashEntry.signed_amount_minor), 0)).filter(
            CashEntry.status == "planned",
            CashEntry.kind == "expense",
            CashEntry.planned_date >= today,
        )
        installments_query = (
            session.query(func.coalesce(func.sum(Installment.amount_minor), 0))
            .join(Invoice, Invoice.id == Installment.invoice_id)
            .join(Card, Card.id == Invoice.card_id)
            .filter(
                Installment.status == "confirmed",
                Invoice.state != "settled",
                Invoice.due_date >= today,
            )
        )
        if account_id:
            planned_expenses_query = planned_expenses_query.filter(CashEntry.account_id == account_id)
            installments_query = installments_query.filter(Card.default_account_id == account_id)
        elif account_ids:
            planned_expenses_query = planned_expenses_query.filter(CashEntry.account_id.in_(account_ids))
            installments_query = installments_query.filter(Card.default_account_id.in_(account_ids))

        planned_expenses_minor = abs(planned_expenses_query.scalar() or 0)
        installments_minor = installments_query.scalar() or 0
        return {
            "current_minor": current_minor,
            "planned_expenses_minor": planned_expenses_minor,
            "installments_minor": installments_minor,
            "future_balance_minor": current_minor - planned_expenses_minor - installments_minor,
        }

    @router.get("/reports/monthly/{month}")
    def monthly(month: str, previous_month: Optional[str] = None, session: Session = Depends(get_session)):
        summary = monthly_summary(session, month)
        return {"summary": summary.__dict__, "coverage": coverage_status(session, month), "comparison": compare_months(session, month, previous_month) if previous_month else None}

    @router.get("/audit/{entity_type}/{entity_id}")
    def audit_trail(entity_type: str, entity_id: str, session: Session = Depends(get_session)):
        from app.storage.models import AuditEvent
        return {"items": [entity_dict(item) for item in session.query(AuditEvent).filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id).order_by(AuditEvent.created_at).all()]}

    return router


