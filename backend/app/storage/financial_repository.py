from datetime import date
from typing import Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from app.config import SAFE_INTEGER_MAX
from app.storage.models import CashEntry, Installment, PlannedCardPurchase, Purchase, Transfer


class PersistenceRuleError(ValueError):
    pass


def validate_positive_money(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > SAFE_INTEGER_MAX:
        raise PersistenceRuleError("Valor monetário deve ser inteiro positivo dentro do intervalo seguro.")


def save_transfer(
    session: Session,
    from_account_id: str,
    to_account_id: str,
    amount_minor: int,
    planned_date: date,
    status: str,
    effective_date: Optional[date] = None,
) -> Transfer:
    validate_positive_money(amount_minor)
    if from_account_id == to_account_id:
        raise PersistenceRuleError("As contas da transferência devem ser diferentes.")
    if status not in ("planned", "effective"):
        raise PersistenceRuleError("Estado inicial de transferência inválido.")
    if status == "effective" and effective_date is None:
        raise PersistenceRuleError("Transferência efetivada exige data efetiva.")
    transfer = Transfer(
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount_minor=amount_minor,
        planned_date=planned_date,
        effective_date=effective_date,
        status=status,
    )
    session.add(transfer)
    session.flush()
    entry_status = "effective" if status == "effective" else "planned"
    common = {"planned_date": planned_date, "effective_date": effective_date, "status": entry_status, "transfer_id": transfer.id, "source": "manual"}
    session.add_all(
        [
            CashEntry(account_id=from_account_id, kind="transfer_out", description="Transferência entre contas", signed_amount_minor=-amount_minor, **common),
            CashEntry(account_id=to_account_id, kind="transfer_in", description="Transferência entre contas", signed_amount_minor=amount_minor, **common),
        ]
    )
    session.flush()
    return transfer


def save_purchase_with_installments(
    session: Session,
    card_id: str,
    description: str,
    purchase_date: date,
    total_minor: int,
    category_id: Optional[str],
    source: str,
    installment_rows: Iterable[Mapping[str, object]],
    planned_card_purchase_id: Optional[str] = None,
    recurrence_occurrence_id: Optional[str] = None,
) -> Purchase:
    validate_positive_money(total_minor)
    rows = list(installment_rows)
    if not rows or len(rows) > total_minor:
        raise PersistenceRuleError("Cronograma de parcelas inválido.")
    amounts = [row.get("amount_minor") for row in rows]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in amounts):
        raise PersistenceRuleError("Parcela deve ter valor inteiro positivo.")
    if sum(amounts) != total_minor:
        raise PersistenceRuleError("A soma das parcelas deve ser igual ao valor total.")
    if [row.get("installment_number") for row in rows] != list(range(1, len(rows) + 1)):
        raise PersistenceRuleError("A numeração das parcelas deve ser consecutiva.")
    purchase = Purchase(
        card_id=card_id,
        description=description,
        purchase_date=purchase_date,
        total_minor=total_minor,
        installment_count=len(rows),
        category_id=category_id,
        source=source,
        recurrence_occurrence_id=recurrence_occurrence_id,
        planned_card_purchase_id=planned_card_purchase_id,
        status="confirmed",
    )
    session.add(purchase)
    session.flush()
    for row in rows:
        session.add(
            Installment(
                purchase_id=purchase.id,
                installment_number=row["installment_number"],
                amount_minor=row["amount_minor"],
                invoice_id=row["invoice_id"],
                category_id_snapshot=category_id,
                status=row.get("status", "confirmed"),
            )
        )
    session.flush()
    return purchase


def confirm_planned_purchase(session: Session, planned_id: str, **purchase_values) -> Purchase:
    planned = session.query(PlannedCardPurchase).filter(PlannedCardPurchase.id == planned_id).one_or_none()
    if planned is None:
        raise PersistenceRuleError("Previsão de compra não encontrada.")
    if planned.status != "planned" or planned.confirmed_purchase_id is not None:
        raise PersistenceRuleError("Previsão de compra já confirmada ou cancelada.")
    purchase = save_purchase_with_installments(
        session,
        planned_card_purchase_id=planned.id,
        **purchase_values
    )
    planned.status = "confirmed"
    planned.confirmed_purchase_id = purchase.id
    planned.revision += 1
    session.flush()
    return purchase

