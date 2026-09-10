from typing import Dict, FrozenSet

TRANSITIONS: Dict[str, Dict[str, FrozenSet[str]]] = {
    "cash_entries": {"planned": frozenset(("effective", "cancelled")), "effective": frozenset(("voided",)), "cancelled": frozenset(), "voided": frozenset()},
    "transfers": {"planned": frozenset(("effective", "cancelled")), "effective": frozenset(("reversed",)), "cancelled": frozenset(), "reversed": frozenset()},
    "planned_card_purchases": {"planned": frozenset(("confirmed", "cancelled")), "confirmed": frozenset(), "cancelled": frozenset()},
    "purchases": {"confirmed": frozenset(("voided",)), "voided": frozenset()},
    "invoices": {"open": frozenset(("closed",)), "closed": frozenset(("open", "settled")), "settled": frozenset(("closed",))},
    "payments": {"active": frozenset(("reversed",)), "reversed": frozenset()},
    "refunds": {"planned": frozenset(("confirmed", "cancelled")), "confirmed": frozenset(), "cancelled": frozenset()},
    "recurrence_occurrences": {"planned": frozenset(("confirmed", "cancelled", "superseded")), "confirmed": frozenset(), "cancelled": frozenset(), "superseded": frozenset()},
    "invoice_payment_plans": {"active": frozenset(("cancelled",)), "cancelled": frozenset()},
}


class InvalidTransition(ValueError):
    pass


def ensure_transition(entity: str, current: str, target: str) -> None:
    states = TRANSITIONS.get(entity)
    if states is None or current not in states or target not in states[current]:
        raise InvalidTransition("Transição inválida para {}: {} -> {}".format(entity, current, target))

