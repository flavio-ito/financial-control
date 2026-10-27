from datetime import date
from dataclasses import replace
import json

import pytest
from alembic import command
from sqlalchemy import text

from app.domain.calculations import DomainValidationError
from app.domain.analytics import monthly_summary
from app.domain.services import create_cash_entry, create_purchase, balance_for_account, correct_cash_entry, correct_purchase, close_invoice, settle_invoice, register_refund
from app.integrations.contracts import Transaction, minor
from app.integrations.files import analyze_csv, parse_file
from app.integrations.service import file_account, stage, resolve, resolve_transfer, candidates, category_suggestions
from app.storage.database import Database
from app.storage.migrations import alembic_config, migrate
from app.storage.models import Account, Card, CashEntry, ImportedTransaction, Installment, ExternalAccount, Invoice, InvoiceAdjustment, Payment, Category, ImportCategoryRule

D = date(2020, 1, 10)


def test_category_rules_suggest_only_and_respect_destination(domain_db):
    with domain_db.session() as session:
        account(session)
        account(session, "b")
        category = Category(id="cat", name="Alimentação")
        session.add(category)
        session.flush()
        rule = ImportCategoryRule(id="rule", phrase="cafe", category_id="cat", account_id="a", active=1)
        session.add(rule)
        first = file_account(session, "csv", "a")
        second = file_account(session, "csv", "b")
        stage(session, first, [Transaction("one", D, "Café fictício", -1234)])
        stage(session, second, [Transaction("two", D, "Café fictício", -1234)])
        rows = session.query(ImportedTransaction).order_by(ImportedTransaction.external_id).all()
        assert [item["category_id"] for item in category_suggestions(session, first, rows[0])] == ["cat"]
        assert category_suggestions(session, second, rows[1]) == []
        assert session.query(CashEntry).count() == 0
        rule.active = 0
        session.flush()
        assert category_suggestions(session, first, rows[0]) == []


def account(session, key="a"):
    obj = Account(id=key, name="Conta teste", reference_date=date(2020, 1, 1), reference_balance_minor=10000)
    session.add(obj); session.flush()
    return obj


def transaction(key="t", amount=-1234, **kwargs):
    return Transaction(key, D, "Compra fictícia", amount, **kwargs)


def test_idempotence_reconciliation_and_user_edits(domain_db):
    with domain_db.session() as session:
        account(session)
        external = file_account(session, "csv", "a")
        counts = stage(session, external, [transaction(), transaction("different")])
        assert counts["new"] == 2  # same date/description/amount are distinct IDs
        assert session.query(CashEntry).count() == 0
        row = session.query(ImportedTransaction).filter_by(external_id="t").one()
        resolve(session, row, "create_cash", expected_fingerprint=row.fingerprint)
        entry = session.get(CashEntry, row.cash_entry_id)
        entry.description, entry.note = "Minha descrição", "Minha nota"
        assert stage(session, external, [transaction()])["ignored"] == 1
        assert entry.description == "Minha descrição"
        assert stage(session, external, [transaction(amount=-1400)])["updated"] == 1
        assert row.state == "review"
        assert entry.signed_amount_minor == -1234
        assert entry.note == "Minha nota"
        resolve(session, row, "keep", expected_fingerprint=row.fingerprint)
        assert session.query(CashEntry).count() == 1


def test_link_manual_payment_or_refund_without_counting_twice(domain_db):
    with domain_db.session() as session:
        account(session)
        entry = create_cash_entry(session, "a", "expense", "Manual", 1234, D, "effective", D, effective_date=D)
        external = file_account(session, "ofx", "a")
        stage(session, external, [transaction()])
        row = session.query(ImportedTransaction).one()
        resolve(session, row, "link_cash", entry.id, expected_fingerprint=row.fingerprint)
        assert balance_for_account(session, "a", D) == 8766
        assert session.query(CashEntry).count() == 1


@pytest.mark.parametrize("changes", [{"provider_status": "PENDING"}, {"currency": "USD"}, {"transaction_date": date(2099, 1, 1)}])
def test_pending_foreign_future_never_realized(domain_db, changes):
    with domain_db.session() as session:
        account(session)
        external = file_account(session, "csv", "a")
        stage(session, external, [replace(transaction(), **changes)])
        row = session.query(ImportedTransaction).one()
        with pytest.raises(DomainValidationError):
            resolve(session, row, "create_cash", expected_fingerprint=row.fingerprint)
        assert session.query(CashEntry).count() == 0


def test_transfer_pair_uses_existing_domain(domain_db):
    with domain_db.session() as session:
        account(session); account(session, "b")
        a, b = file_account(session, "csv", "a"), file_account(session, "csv", "b")
        stage(session, a, [transaction()]); stage(session, b, [transaction("other", 1234)])
        first = session.query(ImportedTransaction).filter_by(external_account_id=a.id).one()
        second = session.query(ImportedTransaction).filter_by(external_account_id=b.id).one()
        resolve_transfer(session, first, second, first.fingerprint, second.fingerprint)
        assert {x.kind for x in session.query(CashEntry)} == {"transfer_in", "transfer_out"}
        assert sum(x.signed_amount_minor for x in session.query(CashEntry)) == 0
        summary = monthly_summary(session, "2020-01")
        assert summary.income_minor == summary.expense_minor == 0


def test_card_installment_links_existing_without_new_plan(domain_db):
    with domain_db.session() as session:
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20)); session.flush()
        purchase = create_purchase(session, "c", "Compra", D, 2468, 2, None, None, D)
        external = file_account(session, "csv", card_id="c")
        stage(session, external, [transaction(installment_number=1, installment_count=2)])
        row = session.query(ImportedTransaction).one()
        with pytest.raises(DomainValidationError):
            resolve(session, row, "create_purchase", expected_fingerprint=row.fingerprint)
        installment = session.query(Installment).filter_by(purchase_id=purchase.id, installment_number=1).one()
        resolve(session, row, "link_installment", installment.id, expected_fingerprint=row.fingerprint)
        assert session.query(Installment).count() == 2


def test_brl_csv_ofx_and_duplicate_files():
    csv = "data;descricao;valor\n10/01/2020;Mercado;-1.234,56\n11/01/2020;Salário;2.000,00\n".encode()
    digest, rows = parse_file(csv, "csv")
    assert [x.amount_minor for x in rows] == [-123456, 200000]
    assert parse_file(csv, "csv") == (digest, rows)
    ofx = b"OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>1<ACCTID>fake</BANKACCTFROM><BANKTRANLIST><STMTTRN><DTPOSTED>20200110120000[-3:BRT]<TRNAMT>-12.34<FITID>fake-id<MEMO>Teste</STMTTRN></BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"
    _, rows = parse_file(ofx, "ofx")
    assert rows[0].amount_minor == -1234
    assert rows[0].external_id.endswith(":fake-id")


def test_csv_analysis_detects_columns_and_nubank_card_signs():
    account_csv = "Data,Valor,Identificador,Descrição\n10/01/2020,-12.34,abc,Mercado\n".encode()
    analysis = analyze_csv(account_csv, "account")
    assert analysis["mapping"] == {"date": "Data", "description": "Descrição", "amount": "Valor", "id": "Identificador"}
    assert analysis["invert_signs"] is False
    assert analysis["encoding"] == "UTF-8"
    card_csv = b"date,title,amount\n2020-01-10,Mercado,12.34\n2020-01-11,Pagamento,-12.34\n"
    analysis = analyze_csv(card_csv, "card")
    assert analysis["mapping"] == {"date": "date", "description": "title", "amount": "amount", "id": ""}
    assert analysis["preset"] == "nubank_card"
    assert analysis["invert_signs"] is True
    _, rows = parse_file(card_csv, "csv", analysis["mapping"], analysis["invert_signs"])
    assert [row.amount_minor for row in rows] == [-1234, 1234]
    with pytest.raises(DomainValidationError):
        parse_file(card_csv, "csv", {"date": "date", "description": "date", "amount": "amount", "id": ""})


@pytest.mark.parametrize("raw,fmt", [(b"", "csv"), (b"x;y\n1;2", "csv"), (b"<OFX><!ENTITY x 'y'>", "ofx"), (b"<OFX></OFX>", "ofx"), (b"x" * (5 * 1024 * 1024 + 1), "csv")], ids=["empty", "columns", "entity", "empty-ofx", "oversize"])
def test_invalid_files(raw, fmt):
    with pytest.raises(DomainValidationError): parse_file(raw, fmt)


def test_exact_money():
    assert minor("-0.29") == -29
    for value in ("NaN", "Infinity", "1.234", "9007199254740992"):
        with pytest.raises(DomainValidationError): minor(value)


def test_populated_0006_migration_keeps_data_and_backup(tmp_path):
    path = tmp_path / "old.sqlite3"
    command.upgrade(alembic_config(path), "0006_remove_category_kind")
    db = Database(path)
    with db.session() as session:
        account(session)
        create_cash_entry(session, "a", "expense", "Anterior", 1234, D, "effective", D, effective_date=D)
    db.dispose()
    assert migrate(path, tmp_path / "backups")
    db = Database(path)
    with db.session() as session:
        assert session.query(CashEntry).one().description == "Anterior"
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
    assert list((tmp_path / "backups").glob("*.finbackup"))
    db.dispose()


def test_0008_migration_preserves_populated_0007_financial_data(tmp_path):
    path = tmp_path / "old.sqlite3"
    command.upgrade(alembic_config(path), "0007_bank_integrations")
    db = Database(path)
    with db.session() as session:
        account(session)
        create_cash_entry(session, "a", "expense", "Anterior", 1234, D, "effective", D, effective_date=D)
    db.dispose()
    assert migrate(path, tmp_path / "backups")
    db = Database(path)
    with db.session() as session:
        assert session.query(CashEntry).one().description == "Anterior"
        assert session.query(ImportCategoryRule).count() == 0
        assert session.execute(text("PRAGMA foreign_key_check")).all() == []
    assert list((tmp_path / "backups").glob("*.finbackup"))
    db.dispose()


def test_file_preview_confirm_and_csrf(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session: account(session)
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    raw = b"data;descricao;valor\n10/01/2020;Teste;-12,34\n"
    assert client.post("/api/v1/integrations/files/csv").status_code == 403
    url = "/api/v1/integrations/files/csv"
    response = client.post(url, data={"account_id": "a"}, files={"file": ("test.csv", raw)}, headers=headers)
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["csv_analysis"]["mapping"] == {"date": "data", "description": "descricao", "amount": "valor", "id": ""}
    with db.session() as session: assert session.query(ImportedTransaction).count() == 0
    response = client.post(url, data={"account_id": "a", "confirmation": preview["confirmation"]}, files={"file": ("test.csv", raw)}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["new"] == 1
    assert response.json()["result"]["financial_created"] == 1
    response = client.post(url, data={"account_id": "a", "confirmation": preview["confirmation"]}, files={"file": ("test.csv", raw)}, headers=headers)
    assert response.json()["result"]["ignored"] == 1
    with db.session() as session: assert session.query(CashEntry).count() == 1


def test_csv_confirmation_binds_mapping_and_sign_conversion(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20))
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    raw = b"date,title,amount\n2020-01-10,Mercado,12.34\n"
    url = "/api/v1/integrations/files/csv"
    preview = client.post(url, data={"card_id": "c"}, files={"file": ("fatura.csv", raw)}, headers=headers).json()
    assert preview["csv_analysis"]["invert_signs"] is True
    assert preview["preview"][0]["amount_minor"] == -1234
    changed = client.post(url, data={"card_id": "c", "mapping": json.dumps(preview["csv_analysis"]["mapping"]),
                                     "invert_signs": "false", "confirmation": preview["confirmation"]},
                          files={"file": ("fatura.csv", raw)}, headers=headers)
    assert changed.status_code == 422
    with db.session() as session:
        assert session.query(ImportedTransaction).count() == 0


def test_file_preview_rejects_destination_incompatible_with_statement(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        account(session)
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20))
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    pix = "data;descricao;valor\n10/01/2020;Transferência Pix enviada;-10,00\n".encode()
    response = client.post("/api/v1/integrations/files/csv", data={"card_id": "c"},
                           files={"file": ("conta.csv", pix)}, headers=headers)
    assert response.status_code == 422
    assert "extrato de conta bancária" in response.json()["detail"]["message"]
    card = b"date,title,amount\n2020-01-10,Mercado,10.00\n"
    response = client.post("/api/v1/integrations/files/csv", data={"account_id": "a"},
                           files={"file": ("cartao.csv", card)}, headers=headers)
    assert response.status_code == 422
    assert "extrato de cartão" in response.json()["detail"]["message"]


def test_file_confirmation_ignores_selected_matching_row(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        account(session)
        existing = create_cash_entry(session, "a", "expense", "Compra existente", 1000, D, "effective", D, effective_date=D)
        existing_id = existing.id
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    raw = b"data;descricao;valor\n10/01/2020;Compra CSV;-10,00\n"
    url = "/api/v1/integrations/files/csv"
    preview = client.post(url, data={"account_id": "a"}, files={"file": ("test.csv", raw)}, headers=headers).json()
    row = preview["preview"][0]
    assert row["candidates"][0]["id"] == existing_id
    decisions = {row["external_id"]: {"action": "ignore"}}
    confirmed = client.post(url, data={"account_id": "a", "confirmation": preview["confirmation"],
                                       "decisions": json.dumps(decisions)},
                            files={"file": ("test.csv", raw)}, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["result"]["ignored"] == 1
    with db.session() as session:
        assert session.query(CashEntry).count() == 1
        imported = session.query(ImportedTransaction).one()
        assert imported.state == "ignored"
        assert imported.cash_entry_id is None


def test_file_reimport_finishes_rows_left_in_review_by_previous_flow(authenticated):
    client, csrf, _, db = authenticated
    raw = b"data;descricao;valor\n10/01/2020;Compra antiga;-10,00\n"
    with db.session() as session:
        account(session)
        _, parsed = parse_file(raw, "csv")
        stage(session, file_account(session, "csv", "a"), parsed)
        assert session.query(ImportedTransaction).one().state == "review"
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    url = "/api/v1/integrations/files/csv"
    preview = client.post(url, data={"account_id": "a"}, files={"file": ("old.csv", raw)}, headers=headers).json()
    assert preview["preview"][0]["duplicate"] is False
    confirmed = client.post(url, data={"account_id": "a", "confirmation": preview["confirmation"]},
                            files={"file": ("old.csv", raw)}, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["result"]["financial_created"] == 1
    with db.session() as session:
        assert session.query(ImportedTransaction).one().state == "linked"
        assert session.query(CashEntry).count() == 1


def test_file_confirmation_applies_reviewed_description_and_category(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        account(session)
        session.add(Category(id="cat", name="Mercado"))
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    raw = b"data;descricao;valor\n10/01/2020;Nome original;-10,00\n"
    url = "/api/v1/integrations/files/csv"
    preview = client.post(url, data={"account_id": "a"}, files={"file": ("test.csv", raw)}, headers=headers).json()
    row_id = preview["preview"][0]["external_id"]
    edits = {row_id: {"description": "Nome revisado", "category_id": "cat"}}

    confirmed = client.post(url, data={"account_id": "a", "confirmation": preview["confirmation"],
                                       "edits": json.dumps(edits)},
                            files={"file": ("test.csv", raw)}, headers=headers)

    assert confirmed.status_code == 200, confirmed.text
    with db.session() as session:
        entry = session.query(CashEntry).one()
        assert entry.description == "Nome revisado"
        assert entry.category_id == "cat"


def test_positive_card_import_creates_refund_for_selected_purchase(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20))
        session.flush()
        purchase = create_purchase(session, "c", "Loja exemplo", D, 1000, 1, None, None, D)
        purchase_id = purchase.id
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    raw = b"data;descricao;valor\n10/01/2020;Estorno Loja exemplo;10,00\n"
    url = "/api/v1/integrations/files/csv"
    preview = client.post(url, data={"card_id": "c"}, files={"file": ("refund.csv", raw)}, headers=headers).json()
    row = preview["preview"][0]
    assert row["refund_candidates"][0]["id"] == purchase_id
    decisions = {row["external_id"]: {"action": "insert", "target_id": purchase_id}}
    confirmed = client.post(url, data={"card_id": "c", "confirmation": preview["confirmation"],
                                       "decisions": json.dumps(decisions)},
                            files={"file": ("refund.csv", raw)}, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["result"]["financial_created"] == 1
    with db.session() as session:
        imported = session.query(ImportedTransaction).one()
        assert imported.state == "linked" and imported.invoice_adjustment_id
        assert session.query(InvoiceAdjustment).filter_by(kind="refund").count() == 1


def test_category_rule_api_only_suggests_until_explicit_resolution(authenticated):
    client, csrf, _, db = authenticated
    with db.session() as session:
        account(session)
        session.add(Category(id="cat", name="Mercado"))
    headers = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    path = "/api/v1/integrations/category-rules"
    payload = {"phrase": "mercado", "category_id": "cat", "account_id": "a"}
    assert client.post(path, json=payload).status_code == 403
    response = client.post(path, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    rule_id = response.json()["id"]
    raw = b"data;descricao;valor\n10/01/2020;Mercado ficticio;-12,34\n"
    preview = client.post("/api/v1/integrations/files/csv", data={"account_id": "a"}, files={"file": ("test.csv", raw)}, headers=headers).json()
    assert preview["preview"][0]["category_suggestions"][0]["category_id"] == "cat"
    with db.session() as session:
        assert session.query(CashEntry).count() == 0
    assert client.delete(f"{path}/{rule_id}", headers=headers).status_code == 200
    preview = client.post("/api/v1/integrations/files/csv", data={"account_id": "a"}, files={"file": ("test.csv", raw)}, headers=headers).json()
    assert preview["preview"][0]["category_suggestions"] == []


def test_csv_and_bank_can_reconcile_same_manual_entry(domain_db):
    with domain_db.session() as session:
        account(session)
        entry = create_cash_entry(session, "a", "income", "Salário", 1234, D, "effective", D, effective_date=D)
        for source in ("csv", "ofx"):
            external = file_account(session, source, "a")
            stage(session, external, [transaction(amount=1234)])
            row = session.query(ImportedTransaction).filter_by(external_account_id=external.id).one()
            resolve(session, row, "link_cash", entry.id, expected_fingerprint=row.fingerprint)
        assert session.query(CashEntry).count() == 1


def test_imported_cash_can_be_edited_using_existing_editor(domain_db):
    with domain_db.session() as session:
        account(session)
        external = file_account(session, "csv", "a")
        stage(session, external, [transaction()])
        row = session.query(ImportedTransaction).one()
        resolve(session, row, "create_cash", expected_fingerprint=row.fingerprint)
        entry = session.get(CashEntry, row.cash_entry_id)
        correct_cash_entry(session, entry.id, entry.revision, D, account_id="a", kind="expense", description="Meu nome",
                           amount_minor=1234, planned_date=D, effective_date=D, status="effective", category_id=None, note="Minha nota")
        assert row.state == "linked"
        stage(session, external, [transaction()])
        assert entry.description == "Meu nome" and entry.note == "Minha nota"


def test_edit_linked_manual_purchase_reopens_review(domain_db):
    with domain_db.session() as session:
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20)); session.flush()
        purchase = create_purchase(session, "c", "Compra", D, 1234, 1, None, None, D)
        installment = session.query(Installment).one()
        external = file_account(session, "csv", card_id="c")
        stage(session, external, [transaction()])
        row = session.query(ImportedTransaction).one()
        resolve(session, row, "link_installment", installment.id, expected_fingerprint=row.fingerprint)
        correct_purchase(session, purchase.id, purchase.revision, D, card_id="c", description="Nome editado", purchase_date=D,
                         total_minor=1234, installment_count=1, category_id=None, first_invoice_month=None)
        session.flush()
        assert row.state == "review" and row.installment_id is None
        assert session.query(Installment).count() == 1


def test_card_payment_and_refund_reconcile_without_consumption_duplicate(domain_db):
    with domain_db.session() as session:
        account(session)
        session.add(Card(id="c", name="Cartão", limit_minor=50000, closing_day=10, due_day=20)); session.flush()
        purchase = create_purchase(session, "c", "Compra", D, 1234, 1, None, None, D)
        invoice = session.query(Invoice).one()
        register_refund(session, purchase.id, 234, "confirmed", D, "invoice", invoice.id, "Teste", D, D)
        session.flush()
        credit = session.query(InvoiceAdjustment).filter_by(kind="refund").one()
        external = file_account(session, "ofx", card_id="c")
        stage(session, external, [transaction("refund", 234)])
        row = session.query(ImportedTransaction).filter_by(external_id="refund").one()
        assert any(x["kind"] == "adjustment" for x in candidates(session, external, row))
        resolve(session, row, "link_adjustment", credit.id, expected_fingerprint=row.fingerprint)
        close_invoice(session, invoice.id, invoice.revision)
        payment = settle_invoice(session, invoice.id, "a", D, 1000, D)
        stage(session, external, [transaction("payment", 1000)])
        row = session.query(ImportedTransaction).filter_by(external_id="payment").one()
        assert any(x["kind"] == "payment" for x in candidates(session, external, row))
        resolve(session, row, "link_payment", payment.id, expected_fingerprint=row.fingerprint)
        assert session.query(Payment).count() == 1
        assert session.query(CashEntry).count() == 1
        assert session.query(CashEntry).one().kind == "invoice_payment"
        summary = monthly_summary(session, invoice.reference_month)
        assert summary.income_minor == 0
        assert summary.expense_minor == 1000


def test_upload_body_rejected_before_multipart_spooling(authenticated):
    client, csrf, _, _ = authenticated
    response = client.post("/api/v1/integrations/files/csv", content=b"x" * (5 * 1024 * 1024 + 65537),
                           headers={"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf})
    assert response.status_code == 413
