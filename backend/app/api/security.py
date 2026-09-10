from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hmac
import secrets
from threading import RLock
from typing import Dict, Optional

from fastapi import Cookie, Header, Request

from app.api.errors import api_error

SESSION_COOKIE = "financas_session"


@dataclass(frozen=True)
class SessionRecord:
    csrf_token: str
    expires_at: datetime


class SessionSecurity:
    def __init__(self, session_hours: int = 12):
        self._bootstrap_token: Optional[str] = None
        self._sessions: Dict[str, SessionRecord] = {}
        self._session_lifetime = timedelta(hours=session_hours)
        self._lock = RLock()

    def issue_bootstrap(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._bootstrap_token = token
        return token

    def exchange_bootstrap(self, candidate: str):
        with self._lock:
            expected = self._bootstrap_token
            if expected is None or not hmac.compare_digest(expected, candidate):
                raise api_error(401, "INVALID_BOOTSTRAP", "Token de inicialização inválido ou já utilizado.")
            self._bootstrap_token = None
            session_id = secrets.token_urlsafe(32)
            csrf_token = secrets.token_urlsafe(32)
            self._sessions[session_id] = SessionRecord(
                csrf_token=csrf_token,
                expires_at=datetime.now(timezone.utc) + self._session_lifetime,
            )
            return session_id, csrf_token

    def session(self, session_id: Optional[str]) -> SessionRecord:
        if not session_id:
            raise api_error(401, "SESSION_REQUIRED", "Sessão local ausente ou expirada.")
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None or record.expires_at <= datetime.now(timezone.utc):
                self._sessions.pop(session_id, None)
                raise api_error(401, "SESSION_REQUIRED", "Sessão local ausente ou expirada.")
            return record

    def revoke_all(self) -> None:
        with self._lock:
            self._bootstrap_token = None
            self._sessions.clear()


def expected_origin(request: Request) -> str:
    return "{}://{}".format(request.url.scheme, request.headers.get("host", ""))


def require_session(request: Request, session_id: Optional[str] = Cookie(None, alias=SESSION_COOKIE)):
    return request.app.state.security.session(session_id)


def require_mutation(
    request: Request,
    session_id: Optional[str] = Cookie(None, alias=SESSION_COOKIE),
    csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    origin: Optional[str] = Header(None, alias="Origin"),
):
    record = request.app.state.security.session(session_id)
    if origin is None or not hmac.compare_digest(origin, expected_origin(request)):
        raise api_error(403, "INVALID_ORIGIN", "Origem da requisição não permitida.")
    if csrf_token is None or not hmac.compare_digest(csrf_token, record.csrf_token):
        raise api_error(403, "CSRF_REQUIRED", "Token CSRF ausente ou inválido.")
    return record

