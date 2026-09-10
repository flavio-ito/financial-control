from datetime import date
from pathlib import Path
import json
import sqlite3

from fastapi.testclient import TestClient

from app.api.security import SessionSecurity
from app.main import create_app
from app.storage.database import Database
from app.storage.migrations import migrate
from app.storage.models import Account, Payment


def run_packaged_self_test(data_dir: Path) -> int:
    """Exercise the packaged stack without exposing bootstrap credentials."""
    result_path = data_dir / "self-test-result.json"
    database = None
    try:
        database_path = data_dir / "database.sqlite3"
        migrate(database_path, data_dir / "backups" / "pre-migration")
        database = Database(database_path)
        security = SessionSecurity()
        token = security.issue_bootstrap()
        app = create_app(database=database, security=security)
        origin = "http://127.0.0.1"
        with TestClient(app, base_url=origin) as client:
            bootstrap = client.post("/api/v1/session/bootstrap", json={"token": token}, headers={"Origin": origin})
            _ok(bootstrap, "bootstrap")
            headers = {"Origin": origin, "X-CSRF-Token": bootstrap.json()["csrf_token"]}
            account = client.post("/api/v1/accounts", json={"name": "Autoteste empacotado", "reference_date": date.today().isoformat(), "reference_balance_minor": 100000}, headers=headers)
            _ok(account, "conta")
            category = client.post("/api/v1/categories", json={"name": "Autoteste", "kind": "expense"}, headers=headers)
            _ok(category, "categoria")
            card = client.post("/api/v1/cards", json={"name": "Cartão autoteste", "limit_minor": 500000, "closing_day": 10, "due_day": 20, "default_account_id": account.json()["id"]}, headers=headers)
            _ok(card, "cartão")
            purchase_input = {"card_id": card.json()["id"], "description": "Compra autoteste", "purchase_date": date.today().isoformat(), "total_minor": 10000, "installment_count": 3, "category_id": category.json()["id"], "first_invoice_month": date.today().strftime("%Y-%m")}
            preview = client.post("/api/v1/purchases/preview", json=purchase_input)
            _ok(preview, "prévia da compra")
            purchase_headers = dict(headers, **{"Idempotency-Key": "packaged-purchase"})
            purchase = client.post("/api/v1/purchases", json=dict(purchase_input, preview_token=preview.json()["preview_token"]), headers=purchase_headers)
            _ok(purchase, "compra")
            invoices = client.get("/api/v1/invoices")
            _ok(invoices, "faturas")
            invoice = next(item for item in invoices.json()["items"] if item["reference_month"] == date.today().strftime("%Y-%m"))
            _ok(client.post("/api/v1/invoices/{}/close".format(invoice["id"]), json={"expected_revision": invoice["revision"]}, headers=headers), "fechamento")
            payment_preview = client.get("/api/v1/invoices/{}/payment-preview".format(invoice["id"]), params={"account_id": account.json()["id"], "paid_date": date.today().isoformat()})
            _ok(payment_preview, "prévia do pagamento")
            payment_headers = dict(headers, **{"Idempotency-Key": "packaged-payment"})
            payment = client.post("/api/v1/invoices/{}/payments".format(invoice["id"]), json={"account_id": account.json()["id"], "paid_date": date.today().isoformat(), "amount_minor": payment_preview.json()["amount_minor"], "preview_token": payment_preview.json()["preview_token"]}, headers=payment_headers)
            _ok(payment, "pagamento")
            exported = client.post("/api/v1/backups/export", headers=headers)
            _ok(exported, "backup")
            extra_headers = dict(headers, **{"Idempotency-Key": "packaged-extra"})
            _ok(client.post("/api/v1/cash-entries", json={"account_id": account.json()["id"], "kind": "expense", "description": "Será removida pelo restore", "amount_minor": 1, "planned_date": date.today().isoformat(), "effective_date": date.today().isoformat(), "status": "effective"}, headers=extra_headers), "mudança pós-backup")
            restore_preview = client.post("/api/v1/backups/restore/preview", files={"backup": ("self-test.finbackup", exported.content, "application/zip")}, headers=headers)
            _ok(restore_preview, "prévia do restore")
            _ok(client.post("/api/v1/backups/restore/confirm", json={"restore_token": restore_preview.json()["restore_token"]}, headers=headers), "restore")
            spa = client.get("/planejamento")
            if spa.status_code != 200 or '<div id="root">' not in spa.text:
                raise RuntimeError("fallback SPA")
            if client.get("/api/v1/inexistente").status_code != 404:
                raise RuntimeError("fallback da API")
        database.dispose()
        database = Database(database_path)
        with database.session() as session:
            account_count = session.query(Account).count()
            payment_count = session.query(Payment).count()
        with sqlite3.connect(str(database_path)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if account_count != 1 or payment_count != 1 or foreign_keys != 1 or integrity != "ok" or foreign_errors:
            raise RuntimeError("persistência/integridade após reabertura")
        result_path.write_text(json.dumps({"status": "ok", "account_count": account_count, "payment_count": payment_count, "backup_bytes": len(exported.content), "foreign_keys": foreign_keys}), encoding="utf-8")
        return 0
    except Exception as error:
        result_path.write_text(json.dumps({"status": "error", "message": "{}: {}".format(type(error).__name__, error)}, ensure_ascii=False), encoding="utf-8")
        return 1
    finally:
        if database is not None:
            database.dispose()


def _ok(response, label: str) -> None:
    if not 200 <= response.status_code < 300:
        raise RuntimeError("{} retornou {}: {}".format(label, response.status_code, response.text[:300]))
