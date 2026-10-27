from datetime import date, datetime, timezone

from app.domain.investments import daily_yield_minor, materialize_daily_yields
from app.domain.services import balance_for_account
from app.storage.models import Account, CashEntry, Investment, InvestmentYield, Setting


def test_daily_yield_uses_annual_cdi_and_investment_percentage():
    full_cdi = daily_yield_minor(1_000_000, 1447, 10_000)
    half_cdi = daily_yield_minor(1_000_000, 1447, 5_000)

    assert full_cdi > 0
    assert 0 < half_cdi < full_cdi


def test_materialization_is_daily_compound_and_idempotent(domain_db):
    with domain_db.session() as session:
        session.add(Setting(id=1, cdi_annual_rate_bps=1447))
        account = Account(name="Investimentos", reference_date=date(2026, 10, 14), reference_balance_minor=0)
        session.add(account)
        session.flush()
        investment = Investment(
            account_id=account.id,
            amount_minor=1_000_000,
            cdi_percentage=10_000,
            created_at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
        )
        session.add(investment)

    with domain_db.session() as session:
        assert materialize_daily_yields(session, date(2026, 10, 18)) == 3
        assert session.query(InvestmentYield).count() == 3
        assert session.query(CashEntry).count() == 0
        investment = session.query(Investment).one()
        assert investment.amount_minor > 1_000_000
        assert balance_for_account(session, investment.account_id, date(2026, 10, 18)) == 0

    with domain_db.session() as session:
        assert materialize_daily_yields(session, date(2026, 10, 18)) == 0
        assert session.query(InvestmentYield).count() == 3
        assert session.query(CashEntry).count() == 0
