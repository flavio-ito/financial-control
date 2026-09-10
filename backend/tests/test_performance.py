from datetime import date
from time import perf_counter

from sqlalchemy import text

from app.storage.models import Account


def test_50k_movements_use_indexed_pagination_under_measured_target(domain_db):
    with domain_db.session() as session:
        account = Account(name="Massa 50 mil", reference_date=date(2025, 12, 31), reference_balance_minor=0)
        session.add(account)
        session.flush()
        account_id = account.id
    rows = []
    for index in range(50000):
        day = index % 28 + 1
        month = index % 8 + 1
        effective = "2026-{:02d}-{:02d}".format(month, day)
        rows.append({"id": "perf-{:05d}".format(index), "account": account_id, "description": "Movimento sintético {:05d}".format(index), "amount": 100 if index % 2 == 0 else -100, "effective": effective})
    statement = text("INSERT INTO cash_entries(id,created_at,updated_at,revision,account_id,kind,description,signed_amount_minor,currency,planned_date,effective_date,status,source) VALUES (:id,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,1,:account,'expense',:description,:amount,'BRL',:effective,:effective,'effective','manual')")
    with domain_db.engine.begin() as connection:
        connection.execute(statement, rows)
    started = perf_counter()
    with domain_db.engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM cash_entries WHERE account_id=:account"), {"account": account_id}).scalar_one()
        page = connection.execute(text("SELECT id,description,signed_amount_minor FROM cash_entries WHERE account_id=:account AND effective_date >= '2026-01-01' AND effective_date < '2027-01-01' ORDER BY effective_date DESC LIMIT 50 OFFSET 25000"), {"account": account_id}).all()
        plan = connection.execute(text("EXPLAIN QUERY PLAN SELECT id FROM cash_entries WHERE account_id=:account AND effective_date >= '2026-01-01' ORDER BY effective_date DESC LIMIT 50"), {"account": account_id}).all()
    elapsed = perf_counter() - started
    print("PERF_QUERY_SECONDS={:.6f}".format(elapsed))
    assert count == 50000 and len(page) == 50
    assert any("ix_cash_entries_account_date" in str(row) for row in plan)
    assert elapsed < 2.0, "consulta paginada levou {:.3f}s no ambiente de validação".format(elapsed)
