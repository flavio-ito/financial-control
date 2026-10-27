"""Provider-independent staging, explicit reconciliation, and sync orchestration."""
from dataclasses import asdict
from datetime import date, datetime, timezone
from uuid import uuid4
from difflib import SequenceMatcher
import unicodedata

from sqlalchemy import or_

from app.domain.calculations import DomainValidationError
from app.domain.services import create_cash_entry, create_purchase, create_transfer, register_refund, require_active, audit
from app.integrations.contracts import Transaction
from app.storage.models import (
    Account, Card, CashEntry, Installment, Purchase, Category, ImportCategoryRule,
    ExternalAccount, ImportedTransaction, BankSyncRun, Payment, Invoice, InvoiceAdjustment, Refund,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid4())


def record_dict(record):
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


def require_record(session, model, key):
    record = session.get(model, key)
    if record is None:
        raise DomainValidationError("Registro da integração não encontrado.")
    return record


def bind_account(session, external, account_id=None, card_id=None, enabled=True):
    if bool(account_id) and bool(card_id):
        raise DomainValidationError("Selecione uma conta ou um cartão.")
    if account_id:
        require_active(session, Account, account_id, "Conta")
        if external.kind != "BANK":
            raise DomainValidationError("Esta conta externa deve ser vinculada a um cartão.")
    if card_id:
        require_active(session, Card, card_id, "Cartão")
        if external.kind != "CREDIT":
            raise DomainValidationError("Esta conta externa deve ser vinculada a uma conta bancária.")
    if external.currency != "BRL" and (account_id or card_id):
        raise DomainValidationError("Somente contas BRL podem ser vinculadas nesta versão.")
    if (external.account_id, external.card_id) != (account_id, card_id):
        # Rebinding historical records would move their reconciliation scope.
        has_history = session.query(ImportedTransaction).filter_by(external_account_id=external.id).first()
        if has_history and (external.account_id or external.card_id) and (account_id or card_id):
            raise DomainValidationError("Conta com histórico: desative a sincronização para preservar o vínculo original.")
        if has_history and not account_id and not card_id:
            external.enabled = 0
            return external
    if account_id or card_id:
        overlap = session.query(ExternalAccount).filter(
            ExternalAccount.id != external.id, ExternalAccount.provider == external.provider,
            ExternalAccount.enabled == 1,
            or_(ExternalAccount.account_id == account_id if account_id else False,
                ExternalAccount.card_id == card_id if card_id else False)).first()
        if overlap:
            raise DomainValidationError("Já existe uma conta ativa deste provedor vinculada ao destino. Desative o vínculo anterior.")
    external.account_id, external.card_id = account_id, card_id
    external.enabled = int(enabled and bool(account_id or card_id))
    return external


def file_account(session, provider, account_id=None, card_id=None):
    if bool(account_id) == bool(card_id):
        raise DomainValidationError("Selecione uma conta ou cartão para importar o arquivo.")
    target = require_active(session, Account if account_id else Card, account_id or card_id, "Conta/cartão")
    identity = ("account:" if account_id else "card:") + target.id
    external = session.query(ExternalAccount).filter_by(provider=provider, external_id=identity).one_or_none()
    if external is None:
        external = ExternalAccount(id=uid(), provider=provider, external_id=identity, name=target.name,
                                   kind="BANK" if account_id else "CREDIT", currency="BRL", enabled=1,
                                   account_id=account_id, card_id=card_id)
        session.add(external)
        session.flush()
    return external


def candidates(session, external, row):
    """Suggestions only: even a single amount/date match is never auto-merged."""
    found = []
    if external.account_id:
        entries = session.query(CashEntry).filter(
            CashEntry.account_id == external.account_id,
            CashEntry.signed_amount_minor == row.amount_minor,
            CashEntry.status.in_(("effective", "planned")),
            or_(CashEntry.effective_date == row.transaction_date, CashEntry.planned_date == row.transaction_date)).limit(20).all()
        for entry in entries:
            found.append({"kind": "cash_entry", "id": entry.id, "description": entry.description,
                          "amount_minor": entry.signed_amount_minor,
                          "date": entry.effective_date or entry.planned_date, "status": entry.status})
    elif external.card_id and row.amount_minor < 0:
        # Bank posting dates need not equal purchase dates; amount is only a suggestion.
        installments = session.query(Installment, Purchase).join(Purchase, Purchase.id == Installment.purchase_id).filter(
            Purchase.card_id == external.card_id, Purchase.status == "confirmed",
            Installment.status.in_(("confirmed", "historical_settled")),
            Installment.amount_minor == -row.amount_minor).limit(20).all()
        for installment, purchase in installments:
            found.append({"kind": "installment", "id": installment.id,
                          "description": purchase.description + " · parcela " + str(installment.installment_number),
                          "amount_minor": -installment.amount_minor, "date": purchase.purchase_date,
                          "status": installment.status})
    elif external.card_id and row.amount_minor > 0:
        payments = session.query(Payment).join(Invoice, Invoice.id == Payment.invoice_id).filter(
            Invoice.card_id == external.card_id, Payment.amount_minor == row.amount_minor,
            Payment.status == "active", Payment.paid_date == row.transaction_date).limit(20).all()
        found.extend({"kind": "payment", "id": x.id, "description": "Pagamento de fatura · " + str(x.paid_date),
                      "amount_minor": x.amount_minor, "date": x.paid_date, "status": x.status} for x in payments)
        credits = session.query(InvoiceAdjustment).join(Invoice, Invoice.id == InvoiceAdjustment.invoice_id).filter(
            Invoice.card_id == external.card_id, InvoiceAdjustment.signed_amount_minor == -row.amount_minor,
            InvoiceAdjustment.kind == "refund", InvoiceAdjustment.status == "active").limit(20).all()
        found.extend({"kind": "adjustment", "id": x.id, "description": "Estorno · " + x.description,
                      "amount_minor": -x.signed_amount_minor, "date": None, "status": x.status} for x in credits)
    return found


def refund_purchase_candidates(session, external, row):
    """Purchases that can originate a positive card refund, ordered by description similarity."""
    if not external.card_id or row.amount_minor <= 0:
        return []

    def normalized(value):
        return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                       if not unicodedata.combining(char))

    wanted = normalized(row.description)
    purchases = session.query(Purchase).filter_by(card_id=external.card_id, status="confirmed").all()
    matches = []
    for purchase in purchases:
        refunded = sum(item.amount_minor for item in session.query(Refund).filter(
            Refund.purchase_id == purchase.id, Refund.status.in_(("planned", "confirmed"))).all())
        cancelled = sum(item.amount_minor for item in session.query(Installment).filter_by(
            purchase_id=purchase.id, status="cancelled").all())
        if purchase.total_minor - refunded - cancelled < row.amount_minor:
            continue
        description = normalized(purchase.description)
        score = SequenceMatcher(None, wanted, description).ratio()
        shared = set(wanted.split()) & set(description.split())
        if purchase.total_minor == row.amount_minor and (score >= .45 or shared):
            matches.append({"kind": "purchase_refund", "id": purchase.id, "description": purchase.description,
                            "amount_minor": purchase.total_minor, "status": purchase.status, "score": score})
    return sorted(matches, key=lambda item: (-item["score"], item["description"]))[:20]


def create_imported_refund(session, external, row, purchase_id, category_id=None):
    """Create and link a confirmed card refund selected during file import."""
    eligible(row)
    purchase = require_record(session, Purchase, purchase_id)
    if purchase.card_id != external.card_id:
        raise DomainValidationError("A compra selecionada pertence a outro cartão.")
    allowed = {item["id"] for item in refund_purchase_candidates(session, external, row)}
    if purchase.id not in allowed:
        raise DomainValidationError("A compra selecionada não é compatível com este estorno.")
    invoice = session.query(Invoice).filter(
        Invoice.card_id == external.card_id, Invoice.state != "settled",
        Invoice.closing_date >= row.transaction_date).order_by(Invoice.closing_date).first()
    if invoice is None:
        invoice = session.query(Invoice).filter(
            Invoice.card_id == external.card_id, Invoice.state != "settled").order_by(Invoice.closing_date.desc()).first()
    if invoice is None:
        raise DomainValidationError("Não há fatura não liquidada para receber o estorno.")
    refund = register_refund(session, purchase.id, row.amount_minor, "confirmed", row.transaction_date,
                             "invoice", invoice.id, row.description, row.transaction_date, date.today())
    session.flush()
    adjustment = session.query(InvoiceAdjustment).filter_by(refund_id=refund.id).one()
    adjustment.category_id = category_id
    row.invoice_adjustment_id, row.state = adjustment.id, "linked"
    audit(session, "imported_transaction", row.id, "create_refund", after={"invoice_adjustment_id": adjustment.id})
    session.flush()
    return row


def category_suggestions(session, external, row):
    """Return configured matches for review; never assign a category to financial facts."""
    def normalized(value):
        return "".join(char for char in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(char))

    description = normalized(row.description)
    rules = session.query(ImportCategoryRule, Category).join(Category, Category.id == ImportCategoryRule.category_id).filter(
        ImportCategoryRule.active == 1, Category.archived_at.is_(None)).order_by(ImportCategoryRule.id).all()
    return [{"rule_id": rule.id, "category_id": category.id, "category_name": category.name, "phrase": rule.phrase}
            for rule, category in rules
            if (rule.account_id is None or rule.account_id == external.account_id)
            and (rule.card_id is None or rule.card_id == external.card_id)
            and normalized(rule.phrase.strip()) in description]


def reason(row):
    if row.currency != "BRL":
        return "Moeda não suportada; nenhuma conversão automática."
    if row.provider_status != "POSTED":
        return "Transação pendente ou estado desconhecido; aguarde confirmação do banco."
    if row.transaction_date > date.today():
        return "Data futura; nenhuma realização automática."
    if row.installment_count or row.installment_number:
        return "Parcela bancária: concilie com uma parcela existente; não criar plano futuro."
    return "Revise possíveis transferências, pagamentos de fatura, estornos e lançamentos já cadastrados."


def stage(session, external, rows: list[Transaction], import_id=None):
    result = {"new": 0, "updated": 0, "ignored": 0, "review": 0}
    for row in rows:
        existing = session.query(ImportedTransaction).filter_by(external_account_id=external.id, external_id=row.external_id).one_or_none()
        fingerprint = row.fingerprint()
        if existing and existing.fingerprint == fingerprint:
            result["ignored"] += 1
            continue
        values = asdict(row)
        if existing:
            before = {"fingerprint": existing.fingerprint, "amount_minor": existing.amount_minor,
                      "transaction_date": str(existing.transaction_date), "provider_status": existing.provider_status}
            for key, value in values.items():
                setattr(existing, key, value)
            existing.fingerprint = fingerprint
            existing.state = "review"
            existing.review_reason = "Provedor corrigiu o registro. O lançamento local foi preservado; revise a conciliação."
            audit(session, "imported_transaction", existing.id, "provider_updated", before=before,
                  after={"fingerprint": fingerprint, "amount_minor": row.amount_minor})
            result["updated"] += 1
        else:
            existing = ImportedTransaction(id=uid(), external_account_id=external.id, import_id=import_id,
                                           fingerprint=fingerprint, state="review", review_reason=reason(row), **values)
            session.add(existing)
            result["new"] += 1
        result["review"] += 1
        session.flush()  # identity protection also within a single batch
    return result


def eligible(row):
    if row.currency != "BRL" or row.provider_status != "POSTED" or row.transaction_date > date.today():
        raise DomainValidationError("Aguarde confirmação, data válida e moeda BRL antes de conciliar.")


def resolve(session, row, action, target_id=None, category_id=None, expected_fingerprint=None):
    if row.state != "review" or row.fingerprint != expected_fingerprint:
        raise DomainValidationError("A revisão mudou ou já foi concluída. Atualize a lista.")
    external = require_record(session, ExternalAccount, row.external_account_id)
    if action == "ignore":
        row.state = "ignored"
        audit(session, "imported_transaction", row.id, "ignored")
        return row
    eligible(row)
    has_link = bool(row.cash_entry_id or row.installment_id or row.payment_id or row.invoice_adjustment_id)
    if action == "keep":
        if not has_link:
            raise DomainValidationError("Não há lançamento conciliado para preservar.")
        row.state = "linked"
    elif action == "link_cash":
        if has_link:
            raise DomainValidationError("Registro já conciliado; preserve o vínculo existente.")
        target = require_record(session, CashEntry, target_id)
        if target.account_id != external.account_id or target.signed_amount_minor != row.amount_minor or target.status != "effective":
            raise DomainValidationError("Conciliação exige conta, valor e realização compatíveis. Efetive a previsão primeiro.")
        row.cash_entry_id, row.state = target.id, "linked"
    elif action == "link_installment":
        if has_link:
            raise DomainValidationError("Registro já conciliado; preserve o vínculo existente.")
        target = require_record(session, Installment, target_id)
        purchase = require_record(session, Purchase, target.purchase_id)
        if purchase.card_id != external.card_id or target.amount_minor != -row.amount_minor or target.status not in ("confirmed", "historical_settled") or purchase.status != "confirmed":
            raise DomainValidationError("Parcela incompatível com cartão, valor ou estado.")
        row.installment_id, row.state = target.id, "linked"
    elif action in ("link_payment", "link_adjustment"):
        if has_link:
            raise DomainValidationError("Registro já conciliado; preserve o vínculo existente.")
        target = require_record(session, Payment if action == "link_payment" else InvoiceAdjustment, target_id)
        invoice = require_record(session, Invoice, target.invoice_id)
        amount = target.amount_minor if action == "link_payment" else -target.signed_amount_minor
        if (invoice.card_id != external.card_id or row.amount_minor <= 0 or amount != row.amount_minor
                or target.status != "active" or (action == "link_adjustment" and target.kind != "refund")):
            raise DomainValidationError("Crédito incompatível com o pagamento ou estorno selecionado.")
        if action == "link_payment":
            row.payment_id = target.id
        else:
            row.invoice_adjustment_id = target.id
        row.state = "linked"
    elif action in ("create_cash", "create_purchase"):
        if has_link:
            raise DomainValidationError("Registro já conciliado; preserve o vínculo existente.")
        source = "file_import"
        if action == "create_cash":
            if not external.account_id:
                raise DomainValidationError("Vincule uma conta bancária primeiro.")
            entry = create_cash_entry(session, external.account_id, "income" if row.amount_minor > 0 else "expense",
                                      row.description, abs(row.amount_minor), row.transaction_date, "effective", date.today(),
                                      category_id=category_id, effective_date=row.transaction_date, source=source)
            entry.external_id, entry.source_connection_id = row.external_id[:160], external.id
            row.cash_entry_id = entry.id
        else:
            if not external.card_id or row.amount_minor >= 0 or (row.installment_number or 0) > 1 or (row.installment_count or 0) > 1:
                raise DomainValidationError("Crie apenas compra avulsa de débito no cartão. Parcelas e créditos exigem conciliação.")
            purchase = create_purchase(session, external.card_id, row.description, row.transaction_date,
                                       -row.amount_minor, 1, category_id, None, date.today(), source=source)
            purchase.external_id, purchase.source_connection_id = row.external_id[:160], external.id
            row.installment_id = session.query(Installment).filter_by(purchase_id=purchase.id).one().id
        row.state = "linked"
    else:
        raise DomainValidationError("Ação de conciliação inválida.")
    audit(session, "imported_transaction", row.id, action, after={"cash_entry_id": row.cash_entry_id, "installment_id": row.installment_id, "payment_id": row.payment_id, "invoice_adjustment_id": row.invoice_adjustment_id})
    session.flush()
    return row


def resolve_transfer(session, first, second, first_fingerprint, second_fingerprint):
    for row, fingerprint in ((first, first_fingerprint), (second, second_fingerprint)):
        eligible(row)
        if row.state != "review" or row.cash_entry_id or row.installment_id or row.fingerprint != fingerprint:
            raise DomainValidationError("Transferência exige dois registros novos em revisão.")
    a = require_record(session, ExternalAccount, first.external_account_id)
    b = require_record(session, ExternalAccount, second.external_account_id)
    if (not a.account_id or not b.account_id or a.account_id == b.account_id
            or first.amount_minor != -second.amount_minor or first.transaction_date != second.transaction_date):
        raise DomainValidationError("Transferência exige contas distintas, valores opostos e mesma data.")
    outgoing, incoming = (first, second) if first.amount_minor < 0 else (second, first)
    source, target = (a, b) if first.amount_minor < 0 else (b, a)
    transfer = create_transfer(session, source.account_id, target.account_id, incoming.amount_minor,
                               first.transaction_date, "effective", date.today(), first.transaction_date)
    for row, kind in ((outgoing, "transfer_out"), (incoming, "transfer_in")):
        entry = session.query(CashEntry).filter_by(transfer_id=transfer.id, kind=kind).one()
        external = a if row.id == first.id else b
        entry.source = "file_import"
        row.cash_entry_id, row.state = entry.id, "linked"
        audit(session, "imported_transaction", row.id, "transfer_linked", after={"transfer_id": transfer.id})
    return transfer
