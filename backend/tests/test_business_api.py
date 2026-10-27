from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.api.security import SessionSecurity
from app.main import create_app
from app.storage.database import Database
from app.storage.migrations import migrate
from app.storage.models import Account, Card, CashEntry, Installment, Investment, InvestmentContribution, InvestmentWithdrawal, InvestmentYield, Invoice, InvoiceAdjustment, Payment, Purchase, Refund


def test_investment_history_summary_uses_full_filtered_period_not_page(authenticated):
    client, _csrf, _path, database = authenticated
    with database.session() as session:
        account = Account(name="Investimentos", reference_date=date(2026, 1, 1), reference_balance_minor=0)
        session.add(account)
        session.flush()
        investment = Investment(account_id=account.id, amount_minor=100_000, cdi_percentage=10_000, archived_at=datetime.now(timezone.utc))
        session.add(investment)
        session.flush()
        for day, amount in ((1, 100), (2, 200), (3, 300)):
            entry = CashEntry(account_id=account.id, kind="income", description="Rendimento", signed_amount_minor=amount, planned_date=date(2026, 10, day), effective_date=date(2026, 10, day), status="effective", source="bank_api")
            session.add(entry)
            session.flush()
            session.add(InvestmentYield(investment_id=investment.id, account_id=account.id, yield_date=date(2026, 10, day), amount_minor=amount, balance_before_minor=100_000, balance_after_minor=100_000 + amount, cdi_annual_rate_bps=1447, investment_cdi_percentage=10_000, cash_entry_id=entry.id))
        withdrawal_entry = CashEntry(account_id=account.id, kind="expense", description="Saque", signed_amount_minor=-250, planned_date=date(2026, 10, 4), effective_date=date(2026, 10, 4), status="effective", source="bank_api")
        session.add(withdrawal_entry)
        session.flush()
        session.add(InvestmentWithdrawal(investment_id=investment.id, account_id=account.id, withdrawal_date=date(2026, 10, 4), amount_minor=250, balance_before_minor=100_600, balance_after_minor=100_350, cash_entry_id=withdrawal_entry.id))

    response = client.get("/api/v1/investment-yields", params={"date_from": "2026-10-01", "date_to": "2026-10-31", "page_size": 2})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["total"] == 4
    assert payload["summary"] == {"income_minor": 600, "withdrawal_minor": 250, "net_minor": 350}
    assert payload["series"] == [
        {"date": "2026-10-01", "portfolio_minor": 100100},
        {"date": "2026-10-02", "portfolio_minor": 100200},
        {"date": "2026-10-03", "portfolio_minor": 100300},
        {"date": "2026-10-04", "portfolio_minor": 100350},
    ]


def test_delete_category_keeps_movements_as_uncategorized(authenticated):
    client, csrf, _path, database = authenticated
    category = client.post("/api/v1/categories", json={"name": "Temporária"}, headers=headers(csrf)).json()
    with database.session() as session:
        account = Account(name="Conta", reference_date=date(2026, 1, 1), reference_balance_minor=0)
        session.add(account)
        session.flush()
        entry = CashEntry(account_id=account.id, kind="expense", description="Compra", signed_amount_minor=-1000, planned_date=date(2026, 10, 1), effective_date=date(2026, 10, 1), status="effective", source="manual", category_id=category["id"])
        session.add(entry)
        session.flush()
        entry_id = entry.id

    response = client.request("DELETE", f"/api/v1/categories/{category['id']}", json={"expected_revision": category["revision"], "reason": "Teste"}, headers=headers(csrf))
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert all(item["id"] != category["id"] for item in client.get("/api/v1/categories").json()["items"])
    with database.session() as session:
        assert session.query(CashEntry).filter(CashEntry.id == entry_id).one().category_id is None


def headers(csrf, key=None):
    result = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    if key:
        result["Idempotency-Key"] = key
    return result


def test_investment_contribution_updates_balance_and_history(authenticated):
    client, csrf, _path, database = authenticated
    with database.session() as session:
        account = Account(name="Conta", reference_date=date.today(), reference_balance_minor=500_000)
        session.add(account)
        session.flush()
        investment = Investment(account_id=account.id, amount_minor=100_000, cdi_percentage=10_000)
        session.add(investment)
        session.flush()
        investment_id = investment.id

    response = client.post("/api/v1/investment-contributions", headers=headers(csrf, "investment-contribution-1"), json={"investment_id": investment_id, "amount_minor": 25_000, "contribution_date": date.today().isoformat()})

    assert response.status_code == 200
    with database.session() as session:
        assert session.get(Investment, investment_id).amount_minor == 125_000
        contribution = session.query(InvestmentContribution).one()
        assert contribution.balance_before_minor == 100_000
        assert contribution.balance_after_minor == 125_000
        entry = session.get(CashEntry, contribution.cash_entry_id)
        assert entry.signed_amount_minor == -25_000

    history = client.get("/api/v1/investment-yields", params={"date_from": date.today().isoformat(), "date_to": date.today().isoformat()}).json()
    assert any(item["source"] == "investment_contribution" and item["signed_amount_minor"] == 25_000 for item in history["items"])
    assert history["series"][-1]["portfolio_minor"] == 125_000


def test_effective_expense_on_reference_date_updates_current_balance(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    today = date.today().isoformat()
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta de hoje", "reference_date": today, "reference_balance_minor": 301},
        headers=mutation,
    ).json()

    response = client.post(
        "/api/v1/cash-entries",
        json={
            "account_id": account["id"], "kind": "expense", "description": "Despesa de hoje",
            "amount_minor": 201, "planned_date": today, "effective_date": today, "status": "effective",
        },
        headers=headers(csrf, "same-day-expense"),
    )

    assert response.status_code == 200
    saved = next(item for item in client.get("/api/v1/accounts").json()["items"] if item["id"] == account["id"])
    assert saved["current_balance_minor"] == 100


def test_cash_entry_installments_split_total_and_schedule_monthly(authenticated):
    client, csrf, _path, _database = authenticated
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta parcelada", "reference_date": "2026-01-01", "reference_balance_minor": 100000},
        headers=headers(csrf),
    ).json()

    response = client.post(
        "/api/v1/cash-entries/installments",
        json={
            "account_id": account["id"], "kind": "expense", "description": "Curso",
            "amount_minor": 1000, "installment_count": 3, "planned_date": "2026-01-31",
            "status": "planned",
        },
        headers=headers(csrf, "installment-expense"),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["signed_amount_minor"] for item in items] == [-334, -333, -333]
    assert [item["planned_date"] for item in items] == ["2026-01-31", "2026-02-28", "2026-03-31"]
    assert [item["description"] for item in items] == ["Curso (1/3)", "Curso (2/3)", "Curso (3/3)"]


def test_purchase_installment_history_uses_each_monthly_amount(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-01-01", "reference_balance_minor": 0}, headers=mutation).json()
    category = client.post("/api/v1/categories", json={"name": "Roupas"}, headers=mutation).json()
    card = client.post("/api/v1/cards", json={"name": "Cartão", "limit_minor": 100000, "closing_day": 10, "due_day": 20, "default_account_id": account["id"]}, headers=mutation).json()
    payload = {"card_id": card["id"], "description": "Tênis", "purchase_date": "2026-07-01", "total_minor": 1000, "installment_count": 3, "category_id": category["id"], "first_invoice_month": "2026-07"}
    preview = client.post("/api/v1/purchases/preview", json=payload).json()
    created = client.post("/api/v1/purchases", json=dict(payload, preview_token=preview["preview_token"]), headers=headers(csrf, "monthly-card-expense"))
    assert created.status_code == 200

    response = client.get("/api/v1/purchase-installments", params={"date_from": "2026-07-01", "date_to": "2026-09-30", "account_id": account["id"]})
    assert response.status_code == 200
    items = sorted(response.json()["items"], key=lambda item: item["installment_number"])
    assert [item["amount_minor"] for item in items] == [334, 333, 333]
    assert [item["reference_month"] for item in items] == ["2026-07", "2026-08", "2026-09"]


def test_investment_crud_and_archive(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta investimento", "institution": "Banco Teste", "reference_date": date.today().isoformat(), "reference_balance_minor": 0},
        headers=mutation,
    ).json()
    created = client.post(
        "/api/v1/investments",
        json={"account_id": account["id"], "amount_minor": 250000, "cdi_percentage": 11050},
        headers=mutation,
    )
    assert created.status_code == 200
    investment = created.json()
    assert investment["cdi_percentage"] == 11050
    assert client.get("/api/v1/investments").json()["items"][0]["amount_minor"] == 250000

    archived = client.post(
        "/api/v1/investments/{}/archive".format(investment["id"]),
        json={"expected_revision": investment["revision"]},
        headers=mutation,
    )
    assert archived.status_code == 200
    assert client.get("/api/v1/investments").json()["items"] == []


def test_api_crud_filters_and_relative_contract(authenticated):
    client, csrf, _path, _database = authenticated
    account = client.post(
        "/api/v1/accounts",
        json={"name": "Conta API", "institution": None, "reference_date": "2026-08-31", "reference_balance_minor": 100000},
        headers=headers(csrf),
    )
    assert account.status_code == 200
    category = client.post("/api/v1/categories", json={"name": "Mercado"}, headers=headers(csrf))
    assert category.status_code == 200
    entry = client.post(
        "/api/v1/cash-entries",
        json={
            "account_id": account.json()["id"], "kind": "expense", "description": "Compra sintética",
            "amount_minor": 2500, "planned_date": "2026-09-01", "status": "effective",
            "effective_date": "2026-09-01", "category_id": category.json()["id"], "note": "Teste",
        },
        headers=headers(csrf, "entry-1"),
    )
    assert entry.status_code == 200
    listing = client.get("/api/v1/cash-entries", params={"account_id": account.json()["id"], "status": "effective"})
    assert listing.status_code == 200 and listing.json()["total"] == 1
    assert client.get("/api/v1/api/v1/accounts").status_code == 404


def test_overview_report_supports_combined_filters(authenticated):
    client, csrf, _path, _database = authenticated
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-10-01", "reference_balance_minor": 100000}, headers=headers(csrf)).json()
    category = client.post("/api/v1/categories", json={"name": "Casa"}, headers=headers(csrf)).json()
    response = client.get("/api/v1/reports/overview", params={"date_from": "2026-10", "date_to": "2026-10", "account_id": account["id"], "category_id": category["id"]})

    assert response.status_code == 200
    assert response.json()["months"] == [{
        "month": "2026-10", "balance_minor": 100000, "income_minor": 0, "expense_minor": 0,
        "registered_result_minor": 0, "cash_flow_minor": 0,
        "categories": {}, "uncategorized_minor": 0,
    }]


def test_api_rejects_unsafe_money_with_stable_error(authenticated):
    client, csrf, _path, _database = authenticated
    response = client.post(
        "/api/v1/accounts",
        json={"name": "Inválida", "reference_date": "2026-08-31", "reference_balance_minor": 9007199254740992},
        headers=headers(csrf),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert response.json()["detail"]["field"] == "reference_balance_minor"


def test_idempotency_survives_app_restart_and_conflicts_on_new_content(tmp_path):
    path = tmp_path / "database.sqlite3"
    migrate(path, tmp_path / "backups")

    def start():
        database = Database(path)
        security = SessionSecurity()
        token = security.issue_bootstrap()
        client = TestClient(create_app(database=database, security=security, static_directory=tmp_path), base_url="http://127.0.0.1")
        client.__enter__()
        bootstrap = client.post("/api/v1/session/bootstrap", json={"token": token}, headers={"Origin": "http://127.0.0.1"})
        return database, client, bootstrap.json()["csrf_token"]

    first_db, first, first_csrf = start()
    account = first.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 0}, headers=headers(first_csrf)).json()
    payload = {"account_id": account["id"], "kind": "expense", "description": "Idempotente", "amount_minor": 1000, "planned_date": "2026-09-01", "status": "effective", "effective_date": "2026-09-01"}
    original = first.post("/api/v1/cash-entries", json=payload, headers=headers(first_csrf, "persistent-key"))
    assert original.status_code == 200
    first.__exit__(None, None, None)
    first_db.dispose()

    second_db, second, second_csrf = start()
    replay = second.post("/api/v1/cash-entries", json=payload, headers=headers(second_csrf, "persistent-key"))
    assert replay.status_code == 200 and replay.json()["id"] == original.json()["id"]
    divergent = dict(payload, amount_minor=1001)
    conflict = second.post("/api/v1/cash-entries", json=divergent, headers=headers(second_csrf, "persistent-key"))
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    with second_db.session() as session:
        assert session.query(CashEntry).count() == 1
    second.__exit__(None, None, None)
    second_db.dispose()


def test_stale_payment_preview_recalculates_and_applies_nothing(authenticated):
    client, csrf, _path, database = authenticated
    with database.session() as session:
        account = Account(name="Conta", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
        session.add(account)
        session.flush()
        card = Card(name="Cartão", limit_minor=100000, closing_day=10, due_day=20, default_account_id=account.id)
        session.add(card)
        session.flush()
        invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20), state="closed")
        session.add(invoice)
        session.flush()
        session.add(InvoiceAdjustment(invoice_id=invoice.id, signed_amount_minor=5000, kind="opening", description="Inicial", status="active"))
        values = invoice.id, account.id
    preview = client.get(
        "/api/v1/invoices/{}/payment-preview".format(values[0]),
        params={"account_id": values[1], "paid_date": "2026-09-09"},
    )
    assert preview.status_code == 200 and preview.json()["amount_minor"] == 5000
    with database.session() as session:
        session.add(InvoiceAdjustment(invoice_id=values[0], signed_amount_minor=1000, kind="debit", description="Alteração concorrente", status="active"))
    confirmation = client.post(
        "/api/v1/invoices/{}/payments".format(values[0]),
        json={"account_id": values[1], "paid_date": "2026-09-09", "amount_minor": 5000, "preview_token": preview.json()["preview_token"]},
        headers=headers(csrf, "stale-payment"),
    )
    assert confirmation.status_code == 409
    assert confirmation.json()["detail"]["code"] == "STALE_PREVIEW"
    assert confirmation.json()["detail"]["preview"]["amount_minor"] == 6000
    with database.session() as session:
        assert session.query(Payment).count() == 0


def test_purchase_preview_and_confirmation_share_domain_service(authenticated):
    client, csrf, _path, _database = authenticated
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 0}, headers=headers(csrf)).json()
    category = client.post("/api/v1/categories", json={"name": "Categoria"}, headers=headers(csrf)).json()
    card = client.post("/api/v1/cards", json={"name": "Cartão", "limit_minor": 20000, "closing_day": 10, "due_day": 20, "default_account_id": account["id"]}, headers=headers(csrf)).json()
    payload = {"card_id": card["id"], "description": "Compra", "purchase_date": "2026-09-01", "total_minor": 10000, "installment_count": 3, "category_id": category["id"], "first_invoice_month": "2026-09"}
    preview = client.post("/api/v1/purchases/preview", json=payload)
    assert preview.status_code == 200
    assert [item["amount_minor"] for item in preview.json()["schedule"]] == [3334, 3333, 3333]
    confirmation = client.post("/api/v1/purchases", json=dict(payload, preview_token=preview.json()["preview_token"]), headers=headers(csrf, "purchase-1"))
    assert confirmation.status_code == 200
    replay = client.post("/api/v1/purchases", json=dict(payload, preview_token=preview.json()["preview_token"]), headers=headers(csrf, "purchase-1"))
    assert replay.status_code == 200 and replay.json()["id"] == confirmation.json()["id"]


def test_manual_purchase_can_be_fully_edited(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 0}, headers=mutation).json()
    category = client.post("/api/v1/categories", json={"name": "Categoria"}, headers=mutation).json()
    card = client.post("/api/v1/cards", json={"name": "CartÃ£o", "limit_minor": 50000, "closing_day": 10, "due_day": 20, "default_account_id": account["id"]}, headers=mutation).json()
    original = {"card_id": card["id"], "description": "Compra", "purchase_date": "2026-09-01", "total_minor": 10000, "installment_count": 2, "category_id": None, "first_invoice_month": "2026-09"}
    preview = client.post("/api/v1/purchases/preview", json=original).json()
    purchase = client.post("/api/v1/purchases", json=dict(original, preview_token=preview["preview_token"]), headers=headers(csrf, "purchase-edit")).json()
    updated = client.put("/api/v1/purchases/{}".format(purchase["id"]), json={"card_id": card["id"], "description": "Compra corrigida", "purchase_date": "2026-09-02", "total_minor": 12000, "installment_count": 3, "category_id": category["id"], "first_invoice_month": None, "expected_revision": purchase["revision"]}, headers=mutation)
    assert updated.status_code == 200
    assert updated.json()["description"] == "Compra corrigida"
    detail = client.get("/api/v1/purchases/{}".format(purchase["id"])).json()
    assert [item["amount_minor"] for item in detail["installments"]] == [4000, 4000, 4000]
    history = client.get("/api/v1/purchase-installments", params={"card_id": card["id"]}).json()["items"]
    assert history[0]["total_minor"] == 12000


def test_setup_progress_entity_edits_filters_and_transfer_preview(authenticated):
    client, csrf, _path, database = authenticated
    mutation = headers(csrf)
    assert client.put("/api/v1/setup", json={"setup_step": 2}, headers=mutation).json()["setup_step"] == 2
    assert client.put("/api/v1/setup", json={"setup_step": 1}, headers=mutation).json()["setup_step"] == 2
    first = client.post("/api/v1/accounts", json={"name": "Origem", "institution": "A", "reference_date": "2026-08-31", "reference_balance_minor": 10000}, headers=mutation).json()
    second = client.post("/api/v1/accounts", json={"name": "Destino", "reference_date": "2026-08-31", "reference_balance_minor": 5000}, headers=mutation).json()
    renamed = client.put("/api/v1/accounts/{}".format(first["id"]), json={"name": "Origem corrigida", "institution": "A", "expected_revision": first["revision"]}, headers=mutation)
    assert renamed.status_code == 200 and renamed.json()["name"] == "Origem corrigida"
    payload = {"from_account_id": first["id"], "to_account_id": second["id"], "amount_minor": 3000, "planned_date": "2026-09-09", "status": "effective", "effective_date": "2026-09-09"}
    preview = client.post("/api/v1/transfers/preview", json=payload)
    assert preview.status_code == 200 and preview.json()["consolidated_change_minor"] == 0
    confirmed = client.post("/api/v1/transfers/confirm", json=dict(payload, preview_token=preview.json()["preview_token"]), headers=headers(csrf, "transfer-preview-1"))
    assert confirmed.status_code == 200
    assert {item["current_balance_minor"] for item in client.get("/api/v1/accounts").json()["items"]} == {7000, 8000}
    with database.session() as session:
        origin = session.query(Account).filter(Account.id == first["id"]).one()
        origin.revision += 1
    stale = client.post("/api/v1/transfers/confirm", json=dict(payload, preview_token=preview.json()["preview_token"]), headers=headers(csrf, "transfer-preview-2"))
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "STALE_PREVIEW"


def test_invoice_date_preview_is_explicit(authenticated):
    client, csrf, _path, database = authenticated
    with database.session() as session:
        account = Account(name="Conta plano", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
        session.add(account)
        session.flush()
        card = Card(name="Cartão plano", limit_minor=100000, closing_day=10, due_day=20, default_account_id=account.id)
        session.add(card)
        session.flush()
        invoice = Invoice(card_id=card.id, reference_month="2026-10", closing_date=date(2026, 9, 10), due_date=date(2026, 10, 20), state="open")
        session.add(invoice)
        session.flush()
        values = invoice.id, invoice.revision
    preview_payload = {"closing_date": "2026-09-11", "due_date": "2026-10-21", "expected_revision": values[1]}
    preview = client.post("/api/v1/invoices/{}/dates/preview".format(values[0]), json=preview_payload)
    assert preview.status_code == 200
    changed = client.post("/api/v1/invoices/{}/dates".format(values[0]), json=dict(preview_payload, preview_token=preview.json()["preview_token"]), headers=headers(csrf))
    assert changed.status_code == 200 and changed.json()["due_date"] == "2026-10-21"


def test_opening_purchase_refund_and_installment_cancel_previews(authenticated):
    client, csrf, _path, database = authenticated
    mutation = headers(csrf)
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 0}, headers=mutation).json()
    category = client.post("/api/v1/categories", json={"name": "Casa"}, headers=mutation).json()
    card = client.post("/api/v1/cards", json={"name": "Cartão", "limit_minor": 100000, "closing_day": 10, "due_day": 20, "default_account_id": account["id"]}, headers=mutation).json()
    opening = client.post("/api/v1/cards/{}/opening-purchases".format(card["id"]), json={"description": "Compra anterior", "purchase_date": "2026-04-01", "total_minor": 60000, "total_installments": 6, "next_installment": 4, "category_id": category["id"], "first_pending_invoice_month": "2026-09"}, headers=mutation)
    assert opening.status_code == 200
    detail = client.get("/api/v1/purchases/{}".format(opening.json()["id"])).json()
    assert [item["installment_number"] for item in detail["installments"]] == [4, 5, 6]
    installment = detail["installments"][0]
    cancel_payload = {"expected_revision": installment["revision"], "cancellation_date": "2026-09-09", "reason": "Cancelada pelo emissor"}
    cancel_preview = client.post("/api/v1/installments/{}/cancel-preview".format(installment["id"]), json=cancel_payload)
    assert cancel_preview.status_code == 200
    cancelled = client.post("/api/v1/installments/{}/cancel-confirm".format(installment["id"]), json=dict(cancel_payload, preview_token=cancel_preview.json()["preview_token"]), headers=mutation)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    invoice_id = detail["installments"][1]["invoice_id"]
    refund_payload = {"purchase_id": opening.json()["id"], "amount_minor": 20000, "status": "confirmed", "planned_date": "2026-09-09", "recognition_date": "2026-09-09", "target_kind": "invoice", "target_id": invoice_id, "reason": "Estorno parcial"}
    refund_preview = client.post("/api/v1/refunds/preview", json=refund_payload)
    assert refund_preview.status_code == 200
    refunded = client.post("/api/v1/refunds/confirm", json=dict(refund_payload, preview_token=refund_preview.json()["preview_token"]), headers=headers(csrf, "refund-preview-1"))
    assert refunded.status_code == 200
    with database.session() as session:
        assert session.query(Purchase).count() == 1
        assert session.query(Installment).filter(Installment.status == "cancelled").count() == 1
        assert session.query(Refund).count() == 1
    too_much = client.post("/api/v1/refunds/preview", json=dict(refund_payload, amount_minor=40001, reason="Excesso"))
    assert too_much.status_code == 422


def test_invoice_payment_is_idempotent_and_divergent_replay_conflicts(authenticated):
    client, csrf, _path, database = authenticated
    with database.session() as session:
        account = Account(name="Conta pagamento", reference_date=date(2026, 8, 31), reference_balance_minor=100000)
        session.add(account)
        session.flush()
        card = Card(name="Cartão pagamento", limit_minor=100000, closing_day=10, due_day=20, default_account_id=account.id)
        session.add(card)
        session.flush()
        invoice = Invoice(card_id=card.id, reference_month="2026-09", closing_date=date(2026, 9, 10), due_date=date(2026, 9, 20), state="closed")
        session.add(invoice)
        session.flush()
        session.add(InvoiceAdjustment(invoice_id=invoice.id, signed_amount_minor=20000, kind="opening", description="Inicial", status="active"))
        values = account.id, invoice.id
    preview = client.get("/api/v1/invoices/{}/payment-preview".format(values[1]), params={"account_id": values[0], "paid_date": "2026-09-09"}).json()
    payload = {"account_id": values[0], "paid_date": "2026-09-09", "amount_minor": 20000, "preview_token": preview["preview_token"]}
    first = client.post("/api/v1/invoices/{}/payments".format(values[1]), json=payload, headers=headers(csrf, "payment-exact-1"))
    replay = client.post("/api/v1/invoices/{}/payments".format(values[1]), json=payload, headers=headers(csrf, "payment-exact-1"))
    assert first.status_code == replay.status_code == 200 and first.json()["id"] == replay.json()["id"]
    conflict = client.post("/api/v1/invoices/{}/payments".format(values[1]), json=dict(payload, amount_minor=19999), headers=headers(csrf, "payment-exact-1"))
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"
    with database.session() as session:
        assert session.query(Payment).count() == 1
        assert session.query(CashEntry).filter(CashEntry.kind == "invoice_payment").count() == 1


def test_purchase_revision_conflict_and_archived_dependency_warning(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 0}, headers=mutation).json()
    category_a = client.post("/api/v1/categories", json={"name": "A"}, headers=mutation).json()
    category_b = client.post("/api/v1/categories", json={"name": "B"}, headers=mutation).json()
    card = client.post("/api/v1/cards", json={"name": "Cartão", "limit_minor": 100000, "closing_day": 10, "due_day": 20, "default_account_id": account["id"]}, headers=mutation).json()
    purchase_payload = {"card_id": card["id"], "description": "Compra", "purchase_date": "2026-09-01", "total_minor": 10000, "installment_count": 1, "category_id": category_a["id"], "first_invoice_month": "2026-09"}
    preview = client.post("/api/v1/purchases/preview", json=purchase_payload).json()
    purchase = client.post("/api/v1/purchases", json=dict(purchase_payload, preview_token=preview["preview_token"]), headers=headers(csrf, "purchase-revision")).json()
    first_edit = client.post("/api/v1/purchases/{}/category".format(purchase["id"]), json={"category_id": category_b["id"], "expected_revision": purchase["revision"]}, headers=mutation)
    assert first_edit.status_code == 200
    stale = client.post("/api/v1/purchases/{}/category".format(purchase["id"]), json={"category_id": category_a["id"], "expected_revision": purchase["revision"]}, headers=mutation)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "REVISION_CONFLICT"
    archived = client.post("/api/v1/cards/{}/archive".format(card["id"]), json={"expected_revision": card["revision"], "reason": "Teste"}, headers=mutation)
    assert archived.status_code == 200
    invoice = client.get("/api/v1/invoices").json()["items"][0]
    assert "preservada" in invoice["dependency_warning"]


def test_reference_correction_and_recurrence_exception(authenticated):
    client, csrf, _path, _database = authenticated
    mutation = headers(csrf)
    account = client.post("/api/v1/accounts", json={"name": "Conta", "reference_date": "2026-08-31", "reference_balance_minor": 100000}, headers=mutation).json()
    category = client.post("/api/v1/categories", json={"name": "Moradia"}, headers=mutation).json()
    client.post("/api/v1/cash-entries", json={"account_id": account["id"], "kind": "expense", "description": "Conta", "amount_minor": 10000, "planned_date": "2026-09-01", "effective_date": "2026-09-01", "status": "effective", "category_id": category["id"]}, headers=headers(csrf, "reference-entry"))
    reference_payload = {"reference_date": "2026-08-31", "reference_balance_minor": 110000, "expected_revision": account["revision"], "reason": "Conciliação explícita"}
    preview = client.post("/api/v1/accounts/{}/reference/preview".format(account["id"]), json=reference_payload)
    assert preview.status_code == 200 and preview.json()["difference_minor"] == 10000
    corrected = client.post("/api/v1/accounts/{}/reference".format(account["id"]), json=dict(reference_payload, preview_token=preview.json()["preview_token"]), headers=mutation)
    assert corrected.status_code == 200
    recurrence = client.post("/api/v1/recurrences", json={"kind": "expense", "description": "Mensal", "account_id": account["id"], "card_id": None, "day": 31, "start_month": "2026-09", "end_month": None, "amount_minor": 1000, "category_id": category["id"]}, headers=mutation)
    assert recurrence.status_code == 200
    occurrence = next(item for item in client.get("/api/v1/recurrences").json()["occurrences"] if item["status"] == "planned")
    edited = client.put("/api/v1/recurrence-occurrences/{}".format(occurrence["id"]), json={"expected_revision": occurrence["revision"], "expected_date": "2026-09-29", "expected_amount_minor": 1100, "reason": "Exceção deste mês"}, headers=mutation)
    assert edited.status_code == 200 and edited.json()["exception"] == 1
