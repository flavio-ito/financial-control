from datetime import date
import hashlib
import hmac
import json
import time
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, get_mutation_session
from app.api.security import require_session, require_mutation
from app.domain.calculations import DomainValidationError
from app.integrations.files import MAX_FILE_BYTES, analyze_csv, detect_statement_kind, parse_file
from app.integrations.service import (
    candidates, category_suggestions, create_imported_refund, file_account, now, record_dict,
    refund_purchase_candidates, require_record, resolve, resolve_transfer, stage, uid,
)
from app.storage.models import ExternalAccount, ImportedTransaction, BankSyncRun, ImportCategoryRule, Category, Account, Card


class ImportBodyLimitMiddleware:
    """Bound multipart input before Starlette can spool a large upload to disk."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/integrations/files/"):
            return await self.app(scope, receive, send)
        limit = MAX_FILE_BYTES + 65536  # allow bounded multipart/form metadata
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                response = JSONResponse(status_code=413, content={"detail": {"code": "IMPORT_TOO_LARGE", "message": "Arquivo de importação excede o limite de 5 MB."}})
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        delivered = False
        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        await self.app(scope, replay, send)


class ResolutionInput(BaseModel):
    action: Literal["ignore", "keep", "link_cash", "link_installment", "link_payment", "link_adjustment", "create_cash", "create_purchase"]
    target_id: str | None = None
    category_id: str | None = None
    expected_fingerprint: str


class TransferInput(BaseModel):
    first_id: str
    second_id: str
    first_fingerprint: str
    second_fingerprint: str


class CategoryRuleInput(BaseModel):
    phrase: str = Field(min_length=1, max_length=120)
    category_id: str
    account_id: str | None = None
    card_id: str | None = None


def integration_router():
    router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[Depends(require_session)])

    @router.get("/category-rules")
    def list_category_rules(session: Session = Depends(get_session)):
        return {"items": [record_dict(rule) for rule in session.query(ImportCategoryRule).filter_by(active=1).order_by(ImportCategoryRule.id)]}

    @router.post("/category-rules", dependencies=[Depends(require_mutation)])
    def add_category_rule(payload: CategoryRuleInput, session: Session = Depends(get_mutation_session)):
        phrase = payload.phrase.strip()
        if not phrase or (payload.account_id and payload.card_id):
            raise DomainValidationError("Informe uma expressão e selecione no máximo um destino.")
        category = session.get(Category, payload.category_id)
        if category is None or category.archived_at is not None:
            raise DomainValidationError("Selecione uma categoria ativa.")
        if payload.account_id and session.get(Account, payload.account_id) is None:
            raise DomainValidationError("Conta da regra não encontrada.")
        if payload.card_id and session.get(Card, payload.card_id) is None:
            raise DomainValidationError("Cartão da regra não encontrado.")
        rule = ImportCategoryRule(id=uid(), phrase=phrase, category_id=payload.category_id,
                                  account_id=payload.account_id, card_id=payload.card_id, active=1)
        session.add(rule)
        session.flush()
        return record_dict(rule)

    @router.delete("/category-rules/{rule_id}", dependencies=[Depends(require_mutation)])
    def deactivate_category_rule(rule_id: str, session: Session = Depends(get_mutation_session)):
        rule = require_record(session, ImportCategoryRule, rule_id)
        rule.active = 0
        return {"status": "disabled"}

    @router.get("/transactions")
    def transactions(page: int = Query(1, ge=1), state: Literal["review", "linked", "ignored"] = "review", session: Session = Depends(get_session)):
        query = session.query(ImportedTransaction).filter_by(state=state)
        rows = query.order_by(ImportedTransaction.transaction_date.desc(), ImportedTransaction.id).offset((page - 1) * 50).limit(50).all()
        items = []
        for row in rows:
            external = require_record(session, ExternalAccount, row.external_account_id)
            item = record_dict(row)
            item.update(provider=external.provider, account_name=external.name, account_id=external.account_id, card_id=external.card_id,
                        candidates=candidates(session, external, row),
                        category_suggestions=category_suggestions(session, external, row))
            items.append(item)
        return {"items": items, "total": query.count(), "page": page, "page_size": 50}

    @router.post("/transactions/{transaction_id}/resolve", dependencies=[Depends(require_mutation)])
    def resolve_row(transaction_id: str, payload: ResolutionInput, session: Session = Depends(get_mutation_session)):
        return record_dict(resolve(session, require_record(session, ImportedTransaction, transaction_id), **payload.dict()))

    @router.post("/transfers/resolve", dependencies=[Depends(require_mutation)])
    def transfer(payload: TransferInput, session: Session = Depends(get_mutation_session)):
        result = resolve_transfer(session, require_record(session, ImportedTransaction, payload.first_id),
                                  require_record(session, ImportedTransaction, payload.second_id), payload.first_fingerprint, payload.second_fingerprint)
        return {"transfer_id": result.id}

    @router.post("/files/{format}", dependencies=[Depends(require_mutation)])
    async def import_file(format: Literal["csv", "ofx"], request: Request, file: UploadFile = File(...),
                          account_id: str | None = Form(None), card_id: str | None = Form(None),
                          mapping: str = Form("{}"), invert_signs: bool | None = Form(None),
                          decisions: str = Form("{}"),
                          edits: str = Form("{}"),
                          confirmation: str | None = Form(None),
                          session: Session = Depends(get_mutation_session)):
        try:
            columns = json.loads(mapping)
            if (not isinstance(columns, dict) or any(key not in ("date", "description", "amount", "id") for key in columns)
                    or any(not isinstance(v, str) for v in columns.values())):
                raise ValueError()
        except ValueError:
            raise DomainValidationError("Mapeamento CSV inválido.") from None
        try:
            choices = json.loads(decisions)
            if not isinstance(choices, dict) or any(not isinstance(key, str) or not isinstance(value, dict)
                    or value.get("action") not in ("insert", "ignore")
                    or set(value) - {"action", "target_id"}
                    or ("target_id" in value and not isinstance(value["target_id"], str))
                    for key, value in choices.items()):
                raise ValueError()
        except ValueError:
            raise DomainValidationError("Decisões da importação são inválidas.") from None
        try:
            changes = json.loads(edits)
            if not isinstance(changes, dict) or any(
                    not isinstance(key, str) or not isinstance(value, dict)
                    or set(value) - {"description", "category_id"}
                    or not isinstance(value.get("description"), str)
                    or not value["description"].strip() or len(value["description"].strip()) > 240
                    or (value.get("category_id") is not None and not isinstance(value["category_id"], str))
                    for key, value in changes.items()):
                raise ValueError()
        except (KeyError, ValueError):
            raise DomainValidationError("Edições da importação são inválidas.") from None
        raw = await file.read(MAX_FILE_BYTES + 1)
        external = file_account(session, format, account_id, card_id)
        analysis = analyze_csv(raw, "card" if card_id else "account") if format == "csv" else None
        effective_columns = columns or (analysis["mapping"] if analysis else {})
        effective_invert = bool((analysis["invert_signs"] if analysis else False) if invert_signs is None else invert_signs)
        if format == "csv" and any(not effective_columns.get(field) for field in ("date", "description", "amount")):
            return {"confirmed": False, "confirmation": None, "total": analysis["row_count"], "preview": [],
                    "preview_limit": 100, "csv_analysis": analysis,
                    "message": "Ajuste o mapeamento obrigatório e gere a prévia."}
        digest, rows = parse_file(raw, format, effective_columns or None, effective_invert)
        detected_kind = detect_statement_kind(raw, format, analysis, rows)
        selected_kind = "card" if card_id else "account"
        if detected_kind and detected_kind != selected_kind:
            expected = "cartão" if detected_kind == "card" else "conta bancária"
            selected = "cartão" if selected_kind == "card" else "conta bancária"
            raise DomainValidationError(
                f"O arquivo parece ser um extrato de {expected}, mas o destino selecionado é {selected}. "
                "Selecione o destino correspondente antes de continuar."
            )
        payload_hash = hashlib.sha256(json.dumps(
            [digest, format, external.id, effective_columns, effective_invert], sort_keys=True).encode()).hexdigest()
        def signature(stamp):
            return hmac.new(request.app.state.import_signing_key, (str(stamp) + ":" + payload_hash).encode(), hashlib.sha256).hexdigest()
        if confirmation:
            try:
                stamp, provided = confirmation.split(":", 1)
                stamp = int(stamp)
                if not 0 <= time.time() - stamp <= 1800 or not hmac.compare_digest(provided, signature(stamp)):
                    raise ValueError()
            except ValueError:
                raise DomainValidationError("Prévia expirada ou arquivo/destino alterado. Gere outra prévia.") from None
            counts = stage(session, external, rows, digest)
            financial_created = reconciled = 0
            for source_row in rows:
                imported = session.query(ImportedTransaction).filter_by(
                    external_account_id=external.id, external_id=source_row.external_id).one()
                if imported.state != "review":
                    continue
                matches = candidates(session, external, imported)
                refunds = refund_purchase_candidates(session, external, imported)
                requires_choice = bool(matches) or bool(external.card_id and imported.amount_minor > 0)
                choice = choices.get(imported.external_id)
                if requires_choice and choice is None:
                    raise DomainValidationError("Defina se cada item em Atenção deve ser salvo ou ignorado.")
                if choice and choice["action"] == "ignore":
                    resolve(session, imported, "ignore", expected_fingerprint=imported.fingerprint)
                    counts["ignored"] += 1
                    continue
                edit = changes.get(imported.external_id)
                if edit:
                    imported.description = edit["description"].strip()
                suggestions = category_suggestions(session, external, imported)
                category_id = edit.get("category_id") if edit else (suggestions[0]["category_id"] if len(suggestions) == 1 else None)
                if category_id:
                    category = session.get(Category, category_id)
                    if category is None or category.archived_at is not None:
                        raise DomainValidationError("A categoria selecionada não está disponível.")
                if external.account_id:
                    resolve(session, imported, "create_cash", category_id=category_id,
                            expected_fingerprint=imported.fingerprint)
                elif imported.amount_minor < 0:
                    resolve(session, imported, "create_purchase", category_id=category_id,
                            expected_fingerprint=imported.fingerprint)
                else:
                    target_id = choice.get("target_id") if choice else None
                    if not target_id or target_id not in {item["id"] for item in refunds}:
                        raise DomainValidationError("Selecione a compra original para registrar o estorno.")
                    create_imported_refund(session, external, imported, target_id, category_id)
                financial_created += 1
            counts["review"] = session.query(ImportedTransaction).filter(
                ImportedTransaction.external_account_id == external.id,
                ImportedTransaction.import_id == digest,
                ImportedTransaction.state == "review").count()
            external.last_sync_at = now()
            run = BankSyncRun(id=uid(), provider=format, finished_at=now(), **counts)
            session.add(run)
            session.flush()
            return {"confirmed": True, "result": {**record_dict(run), "financial_created": financial_created,
                                                    "reconciled": reconciled}}
        preview = []
        for row in rows[:100]:
            existing = session.query(ImportedTransaction).filter_by(external_account_id=external.id, external_id=row.external_id).one_or_none()
            comparison_row = existing if existing and existing.state == "review" else row
            preview.append({"external_id": row.external_id, "date": row.transaction_date, "description": row.description,
                            "amount_minor": row.amount_minor, "currency": row.currency,
                            "duplicate": bool(existing and existing.state != "review"),
                            "candidates": candidates(session, external, comparison_row),
                            "refund_candidates": refund_purchase_candidates(session, external, comparison_row),
                            "category_suggestions": category_suggestions(session, external, comparison_row)})
        stamp = int(time.time())
        return {"confirmed": False, "confirmation": str(stamp) + ":" + signature(stamp), "total": len(rows),
                "preview": preview, "preview_limit": 100,
                "csv_analysis": ({**analysis, "mapping": effective_columns, "invert_signs": effective_invert}
                                 if analysis else None),
                "message": "Revise as correspondências e confirme para criar os lançamentos financeiros."}

    return router
