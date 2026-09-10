import hashlib
import json
from typing import Callable, Dict

from sqlalchemy.orm import Session

from app.domain.calculations import DomainValidationError
from app.storage.models import IdempotencyRecord


def canonical_hash(payload: Dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def idempotent(session: Session, key: str, scope: str, payload: Dict[str, object], action: Callable[[], Dict[str, object]]):
    if not key or len(key) > 160:
        raise DomainValidationError("IDEMPOTENCY_KEY_REQUIRED")
    request_hash = canonical_hash(payload)
    existing = session.query(IdempotencyRecord).filter(IdempotencyRecord.key == key, IdempotencyRecord.operation_scope == scope).one_or_none()
    if existing:
        if existing.request_hash != request_hash:
            raise DomainValidationError("IDEMPOTENCY_CONFLICT")
        return json.loads(existing.response_body or "{}")
    result = action()
    session.add(
        IdempotencyRecord(
            key=key,
            operation_scope=scope,
            request_hash=request_hash,
            result_status="succeeded",
            response_code=200,
            response_body=json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str),
            result_reference=str(result.get("id", "")) or None,
        )
    )
    session.flush()
    return result

