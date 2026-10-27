from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json

from app.config import SAFE_INTEGER_MAX
from app.domain.calculations import DomainValidationError


def minor(value) -> int:
    try:
        amount = Decimal(str(value)) * 100
        if not amount.is_finite() or amount != amount.to_integral_value() or abs(amount) > SAFE_INTEGER_MAX:
            raise ValueError()
        return int(amount)
    except (InvalidOperation, ValueError, TypeError):
        raise DomainValidationError("Valor monetário inválido; use até duas casas decimais.") from None


@dataclass(frozen=True)
class Transaction:
    external_id: str
    transaction_date: date
    description: str
    amount_minor: int
    currency: str = "BRL"
    provider_status: str = "POSTED"
    category: str | None = None
    installment_number: int | None = None
    installment_count: int | None = None

    def __post_init__(self):
        if (not isinstance(self.external_id, str) or not isinstance(self.description, str)
                or not isinstance(self.currency, str) or not isinstance(self.provider_status, str)
                or not isinstance(self.transaction_date, date) or isinstance(self.amount_minor, bool)
                or not isinstance(self.amount_minor, int)
                or (self.category is not None and not isinstance(self.category, str))):
            raise DomainValidationError("Campos de transação inválidos.")
        for value in (self.installment_number, self.installment_count):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10000):
                raise DomainValidationError("Metadados de parcelas inválidos.")
        if (not self.external_id or len(self.external_id) > 200 or not self.description.strip()
                or len(self.description) > 240 or not self.amount_minor
                or abs(self.amount_minor) > SAFE_INTEGER_MAX or len(self.currency) > 8
                or len(self.provider_status) > 32 or (self.category and len(self.category) > 160)):
            raise DomainValidationError("Transação incompleta ou fora dos limites suportados.")

    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, default=str).encode()).hexdigest()


