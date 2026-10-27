from datetime import date, datetime, timezone
import json
from typing import Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.domain.calculations import (
    DomainValidationError,
    account_balance,
    add_months,
    installment_schedule,
    invoice_dates,
    invoice_total,
    month_of,
    suggest_invoice_month,
    validate_minor,
)
from app.domain.states import ensure_transition
from app.storage.financial_repository import save_purchase_with_installments, save_transfer
from app.storage.models import (
    Account,
    AuditEvent,
    Card,
    CashEntry,
    Category,
    Installment,
    Invoice,
    InvoiceAdjustment,
    Payment,
    Purchase,
    Refund,
    RecurrenceOccurrence,
    RecurrenceRule,
    Transfer,
    ImportedTransaction,
)


def require_active(session: Session, model, entity_id: str, label: str):
    entity = session.query(model).filter(model.id == entity_id).one_or_none()
    if entity is None:
        raise DomainValidationError("{} nÃ£o encontrado(a).".format(label))
    if hasattr(entity, "archived_at") and entity.archived_at is not None:
        raise DomainValidationError("{} estÃ¡ arquivado(a) e nÃ£o aceita novos vÃ­nculos.".format(label))
    return entity


def audit(session: Session, entity_type: str, entity_id: str, action: str, before=None, after=None, reason: Optional[str] = None):
    session.add(
        AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_json=json.dumps(before, ensure_ascii=False, default=str, sort_keys=True) if before is not None else None,
            after_json=json.dumps(after, ensure_ascii=False, default=str, sort_keys=True) if after is not None else None,
            reason=reason,
        )
    )


def ensure_revision(entity, expected_revision: int):
    if entity.revision != expected_revision:
        raise DomainValidationError("REVISION_CONFLICT")


def get_or_create_invoice(session: Session, card: Card, reference_month: str) -> Invoice:
    invoice = session.query(Invoice).filter(Invoice.card_id == card.id, Invoice.reference_month == reference_month).one_or_none()
    if invoice is None:
        dates = invoice_dates(reference_month, card.closing_day, card.due_day)
        invoice = Invoice(card_id=card.id, reference_month=reference_month, closing_date=dates.closing_date, due_date=dates.due_date, state="open")
        session.add(invoice)
        session.flush()
    return invoice


def create_cash_entry(
    session: Session,
    account_id: str,
    kind: str,
    description: str,
    amount_minor: int,
    planned_date: date,
    status: str,
    today: date,
    category_id: Optional[str] = None,
    effective_date: Optional[date] = None,
    note: Optional[str] = None,
    source: str = "manual",
) -> CashEntry:
    validate_minor(amount_minor)
    require_active(session, Account, account_id, "Conta")
    if kind not in ("income", "expense", "balance_adjustment"):
        raise DomainValidationError("Tipo de movimentaÃ§Ã£o manual invÃ¡lido.")
    if category_id:
        require_active(session, Category, category_id, "Categoria")
    if status not in ("planned", "effective"):
        raise DomainValidationError("Estado inicial invÃ¡lido.")
    if status == "effective":
        if effective_date is None:
            raise DomainValidationError("Data efetiva Ã© obrigatÃ³ria.")
        if effective_date > today:
            raise DomainValidationError("MovimentaÃ§Ã£o nÃ£o pode ser efetivada no futuro.")
    signed = amount_minor if kind in ("income", "balance_adjustment") else -amount_minor
    entry = CashEntry(
        account_id=account_id,
        kind=kind,
        description=description.strip(),
        note=note,
        signed_amount_minor=signed,
        planned_date=planned_date,
        effective_date=effective_date,
        status=status,
        category_id=category_id,
        source=source,
    )
    session.add(entry)
    session.flush()
    audit(session, "cash_entry", entry.id, "created", after={"status": status, "amount_minor": signed})
    return entry


def transition_cash_entry(session: Session, entry_id: str, transition: str, expected_revision: int, today: date, effective_date: Optional[date] = None, reason: Optional[str] = None):
    entry = session.query(CashEntry).filter(CashEntry.id == entry_id).one_or_none()
    if entry is None:
        raise DomainValidationError("MovimentaÃ§Ã£o nÃ£o encontrada.")
    ensure_revision(entry, expected_revision)
    ensure_transition("cash_entries", entry.status, transition)
    if transition in ("cancelled", "voided") and not reason:
        raise DomainValidationError("Justificativa Ã© obrigatÃ³ria.")
    if transition == "effective":
        actual = effective_date or today
        if actual > today:
            raise DomainValidationError("MovimentaÃ§Ã£o nÃ£o pode ser efetivada no futuro.")
        entry.effective_date = actual
    before = {"status": entry.status, "revision": entry.revision}
    entry.status = transition
    entry.revision += 1
    audit(session, "cash_entry", entry.id, transition, before=before, after={"status": transition, "revision": entry.revision}, reason=reason)
    return entry


def balance_for_account(session: Session, account_id: str, target_date: date) -> int:
    account = session.query(Account).filter(Account.id == account_id).one()
    entries = session.query(CashEntry).filter(CashEntry.account_id == account_id).all()
    values = [{"effective_date": item.effective_date, "status": item.status, "signed_amount_minor": item.signed_amount_minor} for item in entries]
    return account_balance(account.reference_balance_minor, account.reference_date, target_date, values)


def create_transfer(session: Session, from_account_id: str, to_account_id: str, amount_minor: int, planned_date: date, status: str, today: date, effective_date: Optional[date] = None) -> Transfer:
    source = require_active(session, Account, from_account_id, "Conta de origem")
    target = require_active(session, Account, to_account_id, "Conta de destino")
    if source.currency != target.currency:
        raise DomainValidationError("TransferÃªncia exige contas na mesma moeda.")
    if status == "effective" and (effective_date is None or effective_date > today):
        raise DomainValidationError("Data efetiva invÃ¡lida.")
    transfer = save_transfer(session, from_account_id, to_account_id, amount_minor, planned_date, status, effective_date)
    audit(session, "transfer", transfer.id, "created", after={"status": status, "amount_minor": amount_minor})
    return transfer


def reverse_transfer(session: Session, transfer_id: str, expected_revision: int, reversal_date: date, today: date, reason: str) -> Transfer:
    original = session.query(Transfer).filter(Transfer.id == transfer_id).one_or_none()
    if original is None:
        raise DomainValidationError("TransferÃªncia nÃ£o encontrada.")
    ensure_revision(original, expected_revision)
    ensure_transition("transfers", original.status, "reversed")
    if not reason or reversal_date > today:
        raise DomainValidationError("Data/justificativa de reversÃ£o invÃ¡lida.")
    reverse = save_transfer(session, original.to_account_id, original.from_account_id, original.amount_minor, reversal_date, "effective", reversal_date)
    reverse.reversal_of = original.id
    reverse.reason = reason
    original.status = "reversed"
    original.revision += 1
    audit(session, "transfer", original.id, "reversed", reason=reason, after={"reversal_id": reverse.id})
    return reverse


def preview_purchase(session: Session, card_id: str, purchase_date: date, total_minor: int, installment_count: int, first_invoice_month: Optional[str], today: date):
    card = require_active(session, Card, card_id, "CartÃ£o")
    if purchase_date > today:
        raise DomainValidationError("Compra confirmada nÃ£o pode ter data futura.")
    first = first_invoice_month or suggest_invoice_month(purchase_date, card.closing_day, card.due_day)
    schedule = installment_schedule(total_minor, installment_count, first, card.closing_day, card.due_day)
    return card, schedule


def create_purchase(session: Session, card_id: str, description: str, purchase_date: date, total_minor: int, installment_count: int, category_id: Optional[str], first_invoice_month: Optional[str], today: date, source: str = "manual") -> Purchase:
    card, schedule = preview_purchase(session, card_id, purchase_date, total_minor, installment_count, first_invoice_month, today)
    if category_id:
        require_active(session, Category, category_id, "Categoria")
    rows = []
    for item in schedule:
        invoice = get_or_create_invoice(session, card, item.reference_month)
        if invoice.state == "settled":
            raise DomainValidationError("NÃ£o Ã© possÃ­vel incluir parcela em fatura liquidada.")
        rows.append({"installment_number": item.installment_number, "amount_minor": item.amount_minor, "invoice_id": invoice.id})
    purchase = save_purchase_with_installments(session, card.id, description.strip(), purchase_date, total_minor, category_id, source, rows)
    audit(session, "purchase", purchase.id, "created", after={"total_minor": total_minor, "installment_count": installment_count})
    return purchase


def calculate_invoice(session: Session, invoice_id: str):
    debits = [value for (value,) in session.query(Installment.amount_minor).filter(Installment.invoice_id == invoice_id, Installment.status == "confirmed").all()]
    adjustments = [value for (value,) in session.query(InvoiceAdjustment.signed_amount_minor).filter(InvoiceAdjustment.invoice_id == invoice_id, InvoiceAdjustment.status == "active").all()]
    return invoice_total(debits, adjustments)


def close_invoice(session: Session, invoice_id: str, expected_revision: int) -> Invoice:
    invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise DomainValidationError("Fatura nÃ£o encontrada.")
    ensure_revision(invoice, expected_revision)
    ensure_transition("invoices", invoice.state, "closed")
    invoice.state = "closed"
    invoice.revision += 1
    audit(session, "invoice", invoice.id, "closed")
    return invoice


def reopen_invoice(session: Session, invoice_id: str, expected_revision: int, reason: str) -> Invoice:
    invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise DomainValidationError("Fatura nÃ£o encontrada.")
    ensure_revision(invoice, expected_revision)
    ensure_transition("invoices", invoice.state, "open")
    if not reason:
        raise DomainValidationError("Justificativa Ã© obrigatÃ³ria.")
    invoice.state = "open"
    invoice.revision += 1
    audit(session, "invoice", invoice.id, "reopened", reason=reason)
    return invoice


def settle_invoice(session: Session, invoice_id: str, account_id: str, paid_date: date, requested_amount_minor: int, today: date) -> Payment:
    invoice = session.query(Invoice).filter(Invoice.id == invoice_id).one_or_none()
    if invoice is None:
        raise DomainValidationError("Fatura nÃ£o encontrada.")
    if invoice.state != "closed":
        raise DomainValidationError("Fatura deve estar fechada e nÃ£o liquidada.")
    require_active(session, Account, account_id, "Conta pagadora")
    if paid_date > today:
        raise DomainValidationError("Pagamento nÃ£o pode ocorrer no futuro.")
    planned_count = 0
    if planned_count:
        raise DomainValidationError("Revise as previsÃµes desta fatura antes de liquidar.")
    total = calculate_invoice(session, invoice.id)
    if requested_amount_minor != total.payable_minor:
        raise DomainValidationError("O MVP aceita somente pagamento integral calculado.")
    payment = Payment(invoice_id=invoice.id, account_id=account_id, amount_minor=total.payable_minor, paid_date=paid_date, status="active")
    session.add(payment)
    session.flush()
    if total.payable_minor:
        entry = CashEntry(account_id=account_id, kind="invoice_payment", description="Pagamento de fatura", signed_amount_minor=-total.payable_minor, planned_date=paid_date, effective_date=paid_date, status="effective", payment_id=payment.id, source="manual")
        session.add(entry)
        session.flush()
        payment.cash_entry_id = entry.id
    incoming_carries = session.query(InvoiceAdjustment).filter(InvoiceAdjustment.invoice_id == invoice.id, InvoiceAdjustment.kind == "credit_carry", InvoiceAdjustment.status == "active").all()
    for carry in incoming_carries:
        carry.status = "consumed"
        carry.revision += 1
    if total.carry_minor:
        card = session.query(Card).filter(Card.id == invoice.card_id).one()
        next_invoice = get_or_create_invoice(session, card, add_months(invoice.reference_month, 1))
        session.add(InvoiceAdjustment(invoice_id=next_invoice.id, signed_amount_minor=-total.carry_minor, kind="credit_carry", description="CrÃ©dito transportado", origin_invoice_id=invoice.id, status="active"))
    invoice.state = "settled"
    invoice.revision += 1
    plans = []
    for plan in plans:
        plan.status = "cancelled"
        plan.revision += 1
    session.flush()
    audit(session, "invoice", invoice.id, "settled", after={"payment_id": payment.id, "amount_minor": total.payable_minor})
    return payment


def reverse_invoice_payment(session: Session, payment_id: str, reversal_date: date, today: date, reason: str) -> Payment:
    payment = session.query(Payment).filter(Payment.id == payment_id).one_or_none()
    if payment is None:
        raise DomainValidationError("Pagamento nÃ£o encontrado.")
    ensure_transition("payments", payment.status, "reversed")
    if reversal_date > today or not reason:
        raise DomainValidationError("Data/justificativa de reversÃ£o invÃ¡lida.")
    invoice = session.query(Invoice).filter(Invoice.id == payment.invoice_id).one()
    if payment.amount_minor:
        session.add(CashEntry(account_id=payment.account_id, kind="invoice_payment", description="ReversÃ£o de pagamento de fatura", signed_amount_minor=payment.amount_minor, planned_date=reversal_date, effective_date=reversal_date, status="effective", reversal_of_id=payment.cash_entry_id, source="manual"))
    payment.status = "reversed"
    payment.revision += 1
    invoice.state = "closed"
    invoice.revision += 1
    audit(session, "payment", payment.id, "reversed", reason=reason)
    return payment


def register_refund(session: Session, purchase_id: str, amount_minor: int, status: str, planned_date: date, target_kind: str, target_id: str, reason: str, recognition_date: Optional[date], today: date) -> Refund:
    purchase = session.query(Purchase).filter(Purchase.id == purchase_id).one_or_none()
    if purchase is None:
        raise DomainValidationError("Compra nÃ£o encontrada.")
    validate_minor(amount_minor)
    cancelled = session.query(func.coalesce(func.sum(Installment.amount_minor), 0)).filter(Installment.purchase_id == purchase.id, Installment.status == "cancelled").scalar()
    refunded = session.query(func.coalesce(func.sum(Refund.amount_minor), 0)).filter(Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).scalar()
    if amount_minor + cancelled + refunded > purchase.total_minor:
        raise DomainValidationError("Estorno/cancelamento excede o valor elegÃ­vel da compra.")
    if status == "confirmed" and (recognition_date is None or recognition_date > today):
        raise DomainValidationError("Estorno confirmado exige data efetiva vÃ¡lida.")
    values = {"purchase_id": purchase.id, "amount_minor": amount_minor, "status": status, "planned_date": planned_date, "recognition_date": recognition_date, "target_kind": target_kind, "reason": reason}
    if target_kind == "invoice":
        invoice = session.query(Invoice).filter(Invoice.id == target_id).one_or_none()
        if invoice is None or invoice.state == "settled" or invoice.card_id != purchase.card_id:
            raise DomainValidationError("Estorno deve ser reconhecido em fatura nÃ£o liquidada do mesmo cartÃ£o.")
        values["target_invoice_id"] = invoice.id
    elif target_kind == "account":
        require_active(session, Account, target_id, "Conta de reembolso")
        values["target_account_id"] = target_id
    else:
        raise DomainValidationError("Destino de estorno invÃ¡lido.")
    refund = Refund(**values)
    session.add(refund)
    session.flush()
    if status == "confirmed":
        if target_kind == "invoice":
            session.add(InvoiceAdjustment(invoice_id=target_id, signed_amount_minor=-amount_minor, kind="refund", description="Estorno de compra", category_id=purchase.category_id, refund_id=refund.id, status="active"))
        else:
            session.add(CashEntry(account_id=target_id, kind="refund", description="Reembolso de despesa", signed_amount_minor=amount_minor, planned_date=planned_date, effective_date=recognition_date, status="effective", category_id=purchase.category_id, refund_id=refund.id, source="manual"))
    audit(session, "refund", refund.id, "created", after={"status": status, "amount_minor": amount_minor})
    return refund


def create_initial_purchase(session: Session, card_id: str, description: str, purchase_date: date, total_minor: int, total_installments: int, next_installment: int, category_id: Optional[str], first_pending_invoice_month: str) -> Purchase:
    card = require_active(session, Card, card_id, "CartÃ£o")
    schedule = installment_schedule(total_minor, total_installments, first_pending_invoice_month, card.closing_day, card.due_day)
    if next_installment < 1 or next_installment > total_installments:
        raise DomainValidationError("PrÃ³xima parcela invÃ¡lida.")
    purchase = Purchase(card_id=card.id, description=description, purchase_date=purchase_date, total_minor=total_minor, installment_count=total_installments, category_id=category_id, source="opening", status="confirmed")
    session.add(purchase)
    session.flush()
    for original_number in range(next_installment, total_installments + 1):
        item = schedule[original_number - 1]
        reference = add_months(first_pending_invoice_month, original_number - next_installment)
        invoice = get_or_create_invoice(session, card, reference)
        session.add(Installment(purchase_id=purchase.id, installment_number=original_number, amount_minor=item.amount_minor, invoice_id=invoice.id, category_id_snapshot=category_id, status="confirmed"))
    session.flush()
    audit(session, "purchase", purchase.id, "opening_created", after={"next_installment": next_installment})
    return purchase


def replace_opening_contribution(session: Session, adjustment_id: str, installment_ids: Iterable[str], amount_minor: int):
    adjustment = session.query(InvoiceAdjustment).filter(InvoiceAdjustment.id == adjustment_id).one_or_none()
    if adjustment is None or adjustment.kind != "opening" or adjustment.status != "active" or adjustment.signed_amount_minor <= 0:
        raise DomainValidationError("Compromisso inicial nÃ£o estÃ¡ disponÃ­vel para detalhamento.")
    validate_minor(amount_minor)
    selected = session.query(Installment).filter(Installment.id.in_(list(installment_ids)), Installment.invoice_id == adjustment.invoice_id, Installment.status == "confirmed").all()
    if sum(item.amount_minor for item in selected) != amount_minor:
        raise DomainValidationError("A contribuiÃ§Ã£o das parcelas Ã  fatura deve igualar o valor substituÃ­do.")
    if amount_minor > adjustment.signed_amount_minor:
        raise DomainValidationError("Valor substituÃ­do excede o compromisso inicial.")
    before = adjustment.signed_amount_minor
    if amount_minor == before:
        adjustment.status = "cancelled"
    else:
        adjustment.signed_amount_minor -= amount_minor
    adjustment.revision += 1
    audit(session, "invoice_adjustment", adjustment.id, "opening_replaced", before={"amount_minor": before}, after={"amount_minor": adjustment.signed_amount_minor, "status": adjustment.status})
    return adjustment


def edit_purchase_category(session: Session, purchase_id: str, category_id: Optional[str], expected_revision: int):
    purchase = session.query(Purchase).filter(Purchase.id == purchase_id).one_or_none()
    if purchase is None:
        raise DomainValidationError("Compra nÃ£o encontrada.")
    ensure_revision(purchase, expected_revision)
    if category_id:
        require_active(session, Category, category_id, "Categoria")
    before = purchase.category_id
    purchase.category_id = category_id
    purchase.revision += 1
    for installment in session.query(Installment).filter(Installment.purchase_id == purchase.id).all():
        invoice = session.query(Invoice).filter(Invoice.id == installment.invoice_id).one()
        if invoice.state != "settled":
            installment.category_id_snapshot = category_id
            installment.revision += 1
    audit(session, "purchase", purchase.id, "category_corrected", before={"category_id": before}, after={"category_id": category_id})
    return purchase


def correct_purchase(session: Session, purchase_id: str, expected_revision: int, today: date, **changes):
    purchase = session.query(Purchase).filter(Purchase.id == purchase_id).one_or_none()
    if purchase is None:
        raise DomainValidationError("Compra nÃ£o encontrada.")
    ensure_revision(purchase, expected_revision)
    if purchase.source not in ("manual", "file_import", "bank_api"):
        raise DomainValidationError("Somente compras manuais podem ser alteradas.")
    installments = session.query(Installment).filter(Installment.purchase_id == purchase.id).all()
    if any(session.query(Invoice).filter(Invoice.id == item.invoice_id).one().state == "settled" for item in installments):
        raise DomainValidationError("NÃ£o Ã© possÃ­vel alterar uma compra com parcela em fatura liquidada.")
    card, schedule = preview_purchase(
        session,
        changes["card_id"],
        changes["purchase_date"],
        changes["total_minor"],
        changes["installment_count"],
        changes.get("first_invoice_month"),
        today,
    )
    if changes.get("category_id"):
        require_active(session, Category, changes["category_id"], "Categoria")
    before = {
        "card_id": purchase.card_id, "description": purchase.description,
        "purchase_date": purchase.purchase_date, "total_minor": purchase.total_minor,
        "installment_count": purchase.installment_count, "category_id": purchase.category_id,
    }
    # The existing editor recreates installments. Keep bank evidence and reopen its
    # reconciliation instead of letting the new FK block a previously valid edit.
    installment_ids = [item.id for item in installments]
    for imported in session.query(ImportedTransaction).filter(ImportedTransaction.installment_id.in_(installment_ids)):
        audit(session, "imported_transaction", imported.id, "local_purchase_corrected", before={"installment_id": imported.installment_id})
        imported.installment_id, imported.state = None, "review"
        imported.review_reason = "Compra local alterada; revise novamente a parcela correspondente."
    session.flush()
    session.query(Installment).filter(Installment.purchase_id == purchase.id).delete(synchronize_session=False)
    purchase.card_id = card.id
    purchase.description = changes["description"].strip()
    purchase.purchase_date = changes["purchase_date"]
    purchase.total_minor = changes["total_minor"]
    purchase.installment_count = changes["installment_count"]
    purchase.category_id = changes.get("category_id")
    purchase.revision += 1
    for item in schedule:
        invoice = get_or_create_invoice(session, card, item.reference_month)
        if invoice.state == "settled":
            raise DomainValidationError("NÃ£o Ã© possÃ­vel incluir parcela em fatura liquidada.")
        session.add(Installment(purchase_id=purchase.id, installment_number=item.installment_number, amount_minor=item.amount_minor, invoice_id=invoice.id, category_id_snapshot=purchase.category_id, status="confirmed"))
    audit(session, "purchase", purchase.id, "corrected", before=before, after={key: value for key, value in changes.items() if key != "first_invoice_month"})
    return purchase


def archive_entity(session: Session, model, entity_id: str, expected_revision: int):
    entity = session.query(model).filter(model.id == entity_id).one_or_none()
    if entity is None or not hasattr(entity, "archived_at"):
        raise DomainValidationError("Entidade nÃ£o encontrada ou nÃ£o arquivÃ¡vel.")
    ensure_revision(entity, expected_revision)
    entity.archived_at = datetime.now(timezone.utc)
    entity.revision += 1
    audit(session, model.__tablename__, entity.id, "archived")
    return entity


def update_named_entity(session: Session, model, entity_id: str, expected_revision: int, **changes):
    entity = session.query(model).filter(model.id == entity_id).one_or_none()
    if entity is None:
        raise DomainValidationError("Entidade nÃ£o encontrada.")
    ensure_revision(entity, expected_revision)
    before = {name: getattr(entity, name) for name in changes}
    for name, value in changes.items():
        setattr(entity, name, value.strip() if isinstance(value, str) else value)
    entity.revision += 1
    audit(session, model.__tablename__, entity.id, "corrected", before=before, after=changes)
    return entity


def correct_cash_entry(session: Session, entry_id: str, expected_revision: int, today: date, **values):
    entry = session.query(CashEntry).filter(CashEntry.id == entry_id).one_or_none()
    if entry is None:
        raise DomainValidationError("MovimentaÃ§Ã£o nÃ£o encontrada.")
    ensure_revision(entry, expected_revision)
    if entry.source not in ("manual", "recurrence", "file_import", "bank_api") or entry.kind not in ("income", "expense", "balance_adjustment"):
        raise DomainValidationError("Corrija esta movimentaÃ§Ã£o pelo fluxo de origem.")
    before = {"account_id": entry.account_id, "kind": entry.kind, "description": entry.description, "signed_amount_minor": entry.signed_amount_minor, "planned_date": entry.planned_date, "effective_date": entry.effective_date, "category_id": entry.category_id, "status": entry.status}
    account = require_active(session, Account, values["account_id"], "Conta")
    category_id = values.get("category_id")
    kind = values["kind"]
    if category_id:
        require_active(session, Category, category_id, "Categoria")
    effective_date = values.get("effective_date")
    if values["status"] == "effective" and (effective_date is None or effective_date > today):
        raise DomainValidationError("Data efetiva invÃ¡lida.")
    amount_minor = values["amount_minor"]
    validate_minor(amount_minor)
    entry.account_id = account.id
    entry.kind = kind
    entry.description = values["description"].strip()
    entry.signed_amount_minor = amount_minor if kind in ("income", "balance_adjustment") else -amount_minor
    entry.planned_date = values["planned_date"]
    entry.effective_date = effective_date if values["status"] == "effective" else None
    entry.status = values["status"]
    entry.category_id = category_id
    entry.note = values.get("note")
    entry.revision += 1
    if any(before[key] != getattr(entry, key) for key in ("account_id", "kind", "signed_amount_minor", "planned_date", "effective_date", "status")):
        for imported in session.query(ImportedTransaction).filter_by(cash_entry_id=entry.id):
            imported.state = "review"
            imported.review_reason = "Lançamento local alterado; confira a diferença em relação ao registro externo."
    audit(session, "cash_entry", entry.id, "corrected", before=before, after={"signed_amount_minor": entry.signed_amount_minor, "status": entry.status})
    return entry


def update_card_terms(session: Session, card_id: str, closing_day: int, due_day: int, expected_revision: int):
    card = session.query(Card).filter(Card.id == card_id).one_or_none()
    if card is None:
        raise DomainValidationError("CartÃ£o nÃ£o encontrado.")
    ensure_revision(card, expected_revision)
    if not (1 <= closing_day <= 31 and 1 <= due_day <= 31):
        raise DomainValidationError("Dias de fechamento/vencimento invÃ¡lidos.")
    before = {"closing_day": card.closing_day, "due_day": card.due_day}
    card.closing_day = closing_day
    card.due_day = due_day
    card.revision += 1
    audit(session, "card", card.id, "terms_updated", before=before, after={"closing_day": closing_day, "due_day": due_day})
    return card


def confirm_recurrence_occurrence(session: Session, occurrence_id: str, actual_date: date, actual_amount_minor: int, today: date):
    occurrence = session.query(RecurrenceOccurrence).filter(RecurrenceOccurrence.id == occurrence_id).one_or_none()
    if occurrence is None:
        raise DomainValidationError("OcorrÃªncia nÃ£o encontrada.")
    ensure_transition("recurrence_occurrences", occurrence.status, "confirmed")
    rule = session.query(RecurrenceRule).filter(RecurrenceRule.id == occurrence.rule_id).one()
    if rule.kind in ("income", "expense"):
        entry = create_cash_entry(session, rule.account_id, rule.kind, rule.description, actual_amount_minor, occurrence.expected_date, "effective", today, rule.category_id, actual_date, source="recurrence")
        entry.recurrence_occurrence_id = occurrence.id
        occurrence.linked_cash_entry_id = entry.id
    else:
        purchase = create_purchase(session, rule.card_id, rule.description, actual_date, actual_amount_minor, 1, rule.category_id, None, today, source="recurrence")
        purchase.recurrence_occurrence_id = occurrence.id
        occurrence.linked_purchase_id = purchase.id
    occurrence.status = "confirmed"
    occurrence.revision += 1
    session.flush()
    audit(session, "recurrence_occurrence", occurrence.id, "confirmed")
    return occurrence


