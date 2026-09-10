from contextlib import contextmanager

from fastapi import Request

from app.storage.database import financial_write_lock
from app.domain.calculations import DomainValidationError


def get_session(request: Request):
    with request.app.state.database.session() as session:
        yield session


def get_mutation_session(request: Request):
    if request.app.state.maintenance_gate.active:
        raise DomainValidationError("Aplicativo em manutenção; novas alterações estão temporariamente bloqueadas.")
    with financial_write_lock:
        with request.app.state.database.session() as session:
            yield session
