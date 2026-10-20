from sqlalchemy import func
from sqlalchemy.orm import Session

from app.storage.models import Installment, Invoice, InvoiceAdjustment


def card_commitment(session: Session, card_id: str) -> int:
    installments = (
        session.query(func.coalesce(func.sum(Installment.amount_minor), 0))
        .join(Invoice, Invoice.id == Installment.invoice_id)
        .filter(Invoice.card_id == card_id, Invoice.state != "settled", Installment.status == "confirmed")
        .scalar()
    )
    adjustments = (
        session.query(InvoiceAdjustment.signed_amount_minor)
        .join(Invoice, Invoice.id == InvoiceAdjustment.invoice_id)
        .filter(Invoice.card_id == card_id, Invoice.state != "settled", InvoiceAdjustment.status == "active")
        .all()
    )
    return max(0, installments + sum(value for (value,) in adjustments))
