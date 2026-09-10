from datetime import date
from typing import Optional

from app.domain.calculations import add_months, limited_date, month_of
from app.storage.models import RecurrenceOccurrence, RecurrenceRule


def occurrence_date(month: str, original_day: int) -> date:
    return limited_date(month, original_day)


def generate_pending_occurrences(database, today: Optional[date] = None) -> int:
    current = today or date.today()
    horizon = add_months(month_of(current), 12)
    created = 0
    with database.session() as session:
        rules = session.query(RecurrenceRule).filter(RecurrenceRule.active == 1).all()
        for rule in rules:
            created += generate_rule_occurrences(session, rule, horizon)
    return created


def generate_rule_occurrences(session, rule: RecurrenceRule, horizon_month: str) -> int:
    month = rule.start_month
    last = min(horizon_month, rule.end_month) if rule.end_month else horizon_month
    created = 0
    while month <= last:
        exists = (
            session.query(RecurrenceOccurrence.id)
            .filter(
                RecurrenceOccurrence.series_id == rule.series_id,
                RecurrenceOccurrence.occurrence_month == month,
                RecurrenceOccurrence.status != "superseded",
            )
            .first()
        )
        if exists is None:
            session.add(
                RecurrenceOccurrence(
                    series_id=rule.series_id,
                    rule_id=rule.id,
                    occurrence_month=month,
                    expected_date=occurrence_date(month, rule.day),
                    expected_amount_minor=rule.amount_minor,
                    currency=rule.currency,
                    status="planned",
                )
            )
            created += 1
        month = add_months(month, 1)
    session.flush()
    return created


def version_from_month(session, rule: RecurrenceRule, cut_month: str, **changes) -> RecurrenceRule:
    future = (
        session.query(RecurrenceOccurrence)
        .filter(
            RecurrenceOccurrence.series_id == rule.series_id,
            RecurrenceOccurrence.occurrence_month >= cut_month,
            RecurrenceOccurrence.status == "planned",
        )
        .all()
    )
    rule.active = 0
    replacement = RecurrenceRule(
        series_id=rule.series_id,
        version=rule.version + 1,
        kind=changes.get("kind", rule.kind),
        description=changes.get("description", rule.description),
        account_id=changes.get("account_id", rule.account_id),
        card_id=changes.get("card_id", rule.card_id),
        day=changes.get("day", rule.day),
        start_month=cut_month,
        end_month=changes.get("end_month", rule.end_month),
        amount_minor=changes.get("amount_minor", rule.amount_minor),
        currency=rule.currency,
        category_id=changes.get("category_id", rule.category_id),
        active=1,
    )
    session.add(replacement)
    session.flush()
    for occurrence in future:
        occurrence.status = "superseded"
        occurrence.superseded_by_rule_id = replacement.id
        occurrence.revision += 1
    session.flush()
    return replacement
