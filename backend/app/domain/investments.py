from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.storage.models import CashEntry, Investment, InvestmentYield, Setting


DEFAULT_CDI_ANNUAL_RATE_BPS = 1447


def daily_yield_minor(balance_minor: int, cdi_annual_rate_bps: int, investment_cdi_percentage: int) -> int:
    annual_rate = (Decimal(cdi_annual_rate_bps) / Decimal(10_000)) * (Decimal(investment_cdi_percentage) / Decimal(10_000))
    daily_rate = Decimal(str((1.0 + float(annual_rate)) ** (1.0 / 365.0) - 1.0))
    return int((Decimal(balance_minor) * daily_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def materialize_daily_yields(session: Session, as_of: date) -> int:
    settings = session.query(Setting).first()
    annual_rate = settings.cdi_annual_rate_bps if settings else DEFAULT_CDI_ANNUAL_RATE_BPS
    created = 0
    investments = session.query(Investment).filter(Investment.archived_at.is_(None)).all()
    for investment in investments:
        latest = session.query(func.max(InvestmentYield.yield_date)).filter(InvestmentYield.investment_id == investment.id).scalar()
        current_date = (latest + timedelta(days=1)) if latest else (investment.created_at.date() + timedelta(days=1))
        while current_date <= as_of:
            before = investment.amount_minor
            amount = daily_yield_minor(before, annual_rate, investment.cdi_percentage)
            entry = None
            if amount > 0:
                entry = CashEntry(
                    account_id=investment.account_id,
                    kind="income",
                    description="Rendimento diário de CDI",
                    signed_amount_minor=amount,
                    planned_date=current_date,
                    effective_date=current_date,
                    status="effective",
                    source="bank_api",
                    note="Rendimento automático do investimento {}".format(investment.id),
                )
                session.add(entry)
                session.flush()
                investment.amount_minor += amount
            session.add(InvestmentYield(
                investment_id=investment.id,
                account_id=investment.account_id,
                yield_date=current_date,
                amount_minor=amount,
                balance_before_minor=before,
                balance_after_minor=investment.amount_minor,
                cdi_annual_rate_bps=annual_rate,
                investment_cdi_percentage=investment.cdi_percentage,
                cash_entry_id=entry.id if entry else None,
            ))
            investment.revision += 1
            created += 1
            current_date += timedelta(days=1)
    session.flush()
    return created
