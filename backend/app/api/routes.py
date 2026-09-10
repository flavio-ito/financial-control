from typing import Callable, Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, constr

from app import __version__
from app.api.security import SESSION_COOKIE, require_mutation, require_session
from app.api.business import business_router
from app.api.backup_routes import backup_router
from app.config import APP_ID


class BootstrapRequest(BaseModel):
    token: constr(min_length=20, max_length=256)


class CsrfResponse(BaseModel):
    csrf_token: str


def api_router(shutdown_callback: Optional[Callable[[], None]] = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    def health():
        return {"status": "ok", "app_id": APP_ID, "version": __version__}

    @router.post("/session/bootstrap", response_model=CsrfResponse)
    def bootstrap(payload: BootstrapRequest, request: Request, response: Response):
        session_id, csrf_token = request.app.state.security.exchange_bootstrap(payload.token)
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return {"csrf_token": csrf_token}

    @router.get("/session/csrf", response_model=CsrfResponse)
    def csrf(record=Depends(require_session)):
        return {"csrf_token": record.csrf_token}

    @router.get("/status")
    def status(request: Request, _record=Depends(require_session)):
        return {
            "ready": True,
            "app_id": APP_ID,
            "data_directory": str(request.app.state.data_directory),
        }

    @router.post("/application/shutdown", status_code=202)
    def shutdown(_record=Depends(require_mutation)):
        if shutdown_callback is not None:
            shutdown_callback()
        return {"status": "shutting_down"}

    router.include_router(business_router())
    router.include_router(backup_router())
    return router
