from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.exc import IntegrityError

from app.api.routes import api_router
from app.api.business import StalePreview
from app.domain.calculations import DomainValidationError
from app.domain.states import InvalidTransition
from app.api.security import SessionSecurity
from app.config import data_directory, resource_directory
from app.storage.database import Database
from app.maintenance.backup import BackupError, MaintenanceGate


def create_app(
    database: Optional[Database] = None,
    security: Optional[SessionSecurity] = None,
    static_directory: Optional[Path] = None,
    shutdown_callback: Optional[Callable[[], None]] = None,
    maintenance_gate: Optional[MaintenanceGate] = None,
) -> FastAPI:
    data_dir = database.path.parent if database else data_directory()
    db = database or Database(data_dir / "database.sqlite3")
    static_dir = static_directory or resource_directory()

    app = FastAPI(title="Controle Financeiro Local API", version="0.1.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.state.database = db
    app.state.security = security or SessionSecurity()
    app.state.data_directory = data_dir
    app.state.maintenance_gate = maintenance_gate or MaintenanceGate()
    app.state.pending_restores = {}
    app.include_router(api_router(shutdown_callback))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError):
        first = error.errors()[0] if error.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", [])[1:]) or None
        return JSONResponse(status_code=422, content={"detail": {"code": "VALIDATION_ERROR", "message": "Dados inválidos.", "field": field}})

    @app.exception_handler(DomainValidationError)
    async def domain_error(_request: Request, error: DomainValidationError):
        message = str(error)
        code = "DOMAIN_VALIDATION_ERROR"
        status = 422
        if message == "REVISION_CONFLICT":
            code, status, message = "REVISION_CONFLICT", 409, "O registro foi alterado em outra aba."
        elif message == "IDEMPOTENCY_CONFLICT":
            code, status, message = "IDEMPOTENCY_CONFLICT", 409, "A chave de idempotência já foi usada com conteúdo diferente."
        elif message == "IDEMPOTENCY_KEY_REQUIRED":
            code, status, message = "IDEMPOTENCY_KEY_REQUIRED", 400, "Chave de idempotência obrigatória."
        return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})

    @app.exception_handler(InvalidTransition)
    async def transition_error(_request: Request, error: InvalidTransition):
        return JSONResponse(status_code=422, content={"detail": {"code": "INVALID_TRANSITION", "message": str(error)}})

    @app.exception_handler(IntegrityError)
    async def integrity_error(_request: Request, _error: IntegrityError):
        return JSONResponse(status_code=409, content={"detail": {"code": "INTEGRITY_CONFLICT", "message": "A operação conflita com um vínculo ou registro existente."}})

    @app.exception_handler(StalePreview)
    async def stale_preview(_request: Request, error: StalePreview):
        return JSONResponse(status_code=409, content={"detail": {"code": "STALE_PREVIEW", "message": "A prévia mudou; revise antes de confirmar.", "preview": error.preview}})

    @app.exception_handler(BackupError)
    async def backup_error(_request: Request, error: BackupError):
        return JSONResponse(status_code=422, content={"detail": {"code": "BACKUP_ERROR", "message": str(error)}})

    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, _error: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INTERNAL_ERROR", "message": "Erro interno inesperado."}},
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": {"code": "NOT_FOUND", "message": "Endpoint não encontrado."}},
            )
        index = static_dir / "index.html"
        if not index.is_file():
            return JSONResponse(
                status_code=503,
                content={"detail": {"code": "FRONTEND_NOT_BUILT", "message": "Frontend ainda não compilado."}},
            )
        return FileResponse(str(index))

    return app
