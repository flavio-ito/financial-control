from datetime import date

from app.domain.calculations import add_months, limited_date
from app.domain.services import balance_for_account, create_cash_entry, create_purchase
from app.storage.models import Account, Card, CashEntry, Category, Investment, RecurrenceOccurrence, RecurrenceRule


def headers(csrf, idempotency=None):
    value = {"Origin": "http://127.0.0.1", "X-CSRF-Token": csrf}
    if idempotency:
        value["Idempotency-Key"] = idempotency
    return value


def test_investment_movements_are_asset_transfers(authenticated):
    client, csrf, _, db = authenticated
    today = date.today()
    with db.session() as session:
        account = Account(name="Conta", reference_date=today, reference_balance_minor=10_000)
        session.add(account); session.flush()
        investment = Investment(account_id=account.id, amount_minor=5_000, cdi_percentage=10_000)
        session.add(investment); session.flush()
        account_id, investment_id = account.id, investment.id

    response = client.post("/api/v1/investment-contributions", json={"investment_id": investment_id, "amount_minor": 1_000, "contribution_date": str(today)}, headers=headers(csrf, "contribution"))
    assert response.status_code == 200, response.text
    response = client.post("/api/v1/investment-withdrawals", json={"investment_id": investment_id, "amount_minor": 600, "withdrawal_date": str(today)}, headers=headers(csrf, "withdrawal"))
    assert response.status_code == 200, response.text
    with db.session() as session:
        entries = session.query(CashEntry).order_by(CashEntry.created_at).all()
        assert [(item.kind, item.signed_amount_minor) for item in entries] == [("balance_adjustment", -1_000), ("balance_adjustment", 600)]
        assert balance_for_account(session, account_id, today) == 9_600
        assert session.get(Investment, investment_id).amount_minor == 5_400


def test_planning_budget_and_projection_share_future_events(authenticated):
    client, csrf, _, db = authenticated
    today = date.today()
    month = today.strftime("%Y-%m")
    with db.session() as session:
        account = Account(name="Conta", reference_date=today, reference_balance_minor=100_000)
        category = Category(name="Casa")
        session.add_all([account, category]); session.flush()
        card = Card(name="Cartão", limit_minor=200_000, closing_day=10, due_day=20, default_account_id=account.id)
        session.add(card); session.flush()
        create_cash_entry(session, account.id, "income", "Receita futura", 20_000, today, "planned", today)
        create_cash_entry(session, account.id, "expense", "Despesa futura", 5_000, today, "planned", today, category_id=category.id)
        rule = RecurrenceRule(kind="expense", description="Recorrente", account_id=account.id, day=today.day, start_month=month, amount_minor=3_000, category_id=category.id)
        session.add(rule); session.flush()
        session.add(RecurrenceOccurrence(series_id=rule.series_id, rule_id=rule.id, occurrence_month=month, expected_date=today, expected_amount_minor=3_000))
        account_id, card_id, category_id = account.id, card.id, category.id

    response = client.post("/api/v1/planned-card-purchases", json={"card_id": card_id, "description": "Compra futura", "category_id": category_id, "expected_date": str(today), "expected_amount_minor": 7_000}, headers=headers(csrf))
    assert response.status_code == 200, response.text
    planned_id = response.json()["id"]
    projection = client.get(f"/api/v1/reports/future-balance?account_id={account_id}&date_to={today}").json()
    assert projection["planned_income_minor"] == 20_000
    assert projection["planned_expenses_minor"] == 8_000
    assert projection["installments_minor"] == 7_000
    assert projection["future_balance_minor"] == 105_000

    response = client.put(f"/api/v1/budgets/{month}/{category_id}", json={"month": month, "category_id": category_id, "amount_minor": 4_000}, headers=headers(csrf))
    assert response.status_code == 200, response.text
    budget = client.get(f"/api/v1/budgets/{month}").json()["items"][0]
    assert budget["planned_minor"] == 8_000
    assert budget["status"] == "risk"

    response = client.post(f"/api/v1/planned-card-purchases/{planned_id}/confirm", headers=headers(csrf))
    assert response.status_code == 200, response.text
    projection = client.get(
        f"/api/v1/reports/future-balance?account_id={account_id}&date_to={limited_date(add_months(month, 2), 28)}"
    )
    assert projection.status_code == 200, projection.text
    assert projection.json()["installments_minor"] == 7_000
    with db.session() as session:
        assert session.query(RecurrenceOccurrence).count() == 1
        assert create_purchase is not None
