from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, constr

from app.api.security import require_mutation, require_session
from app.maintenance.backup import BackupError, create_finbackup, database_revision, restore_finbackup, validate_finbackup
from app.storage.database import financial_write_lock

MAX_BACKUP_BYTES = 1024 * 1024 * 1024


class RestoreConfirm(BaseModel):
    restore_token: constr(min_length=32, max_length=64)


def _pending(request: Request) -> Dict[str, Path]:
    return request.app.state.pending_restores


def backup_router() -> APIRouter:
    router = APIRouter(prefix="/backups", dependencies=[Depends(require_session)])

    @router.get("")
    def list_backups(request: Request):
        root = request.app.state.data_directory / "backups"
        items = []
        if root.exists():
            for path in sorted(root.rglob("*.finbackup"), key=lambda item: item.stat().st_mtime, reverse=True):
                try:
                    validated = validate_finbackup(path)
                except BackupError:
                    continue
                items.append({"name": path.name, "size_bytes": path.stat().st_size, "manifest": validated.manifest})
        return {"items": items}

    @router.post("/export", dependencies=[Depends(require_mutation)])
    def export_backup(request: Request):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = request.app.state.data_directory / "backups" / "manual" / "financas-{}.finbackup".format(timestamp)
        with financial_write_lock:
            create_finbackup(request.app.state.database.path, destination)
        return FileResponse(str(destination), media_type="application/zip", filename=destination.name)

    @router.post("/restore/preview", dependencies=[Depends(require_mutation)])
    async def preview_restore(request: Request, backup: UploadFile = File(...)):
        if not backup.filename or not backup.filename.lower().endswith(".finbackup"):
            raise BackupError("Selecione um arquivo .finbackup.")
        pending_dir = request.app.state.data_directory / "backups" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        restore_token = uuid.uuid4().hex
        destination = pending_dir / "{}.finbackup".format(restore_token)
        size = 0
        try:
            with destination.open("wb") as stream:
                while True:
                    chunk = await backup.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BACKUP_BYTES:
                        raise BackupError("Arquivo de backup excede o limite de 1 GB.")
                    stream.write(chunk)
            validated = validate_finbackup(destination, expected_revision=database_revision(request.app.state.database.path))
        except Exception:
            if destination.exists():
                destination.unlink()
            raise
        finally:
            await backup.close()
        _pending(request)[restore_token] = destination
        return {"restore_token": restore_token, "filename": Path(backup.filename).name, "size_bytes": size, "manifest": validated.manifest, "warning": "A restauração substituirá todos os dados atuais após criar uma cópia de segurança."}

    @router.post("/restore/confirm", dependencies=[Depends(require_mutation)])
    def confirm_restore(payload: RestoreConfirm, request: Request):
        backup_path = _pending(request).pop(payload.restore_token, None)
        if backup_path is None or not backup_path.is_file():
            raise BackupError("Prévia de restauração expirada ou inválida.")
        gate = request.app.state.maintenance_gate
        try:
            with gate.lock:
                gate.active = True
                with financial_write_lock:
                    result = restore_finbackup(request.app.state.database, backup_path, request.app.state.data_directory)
        finally:
            gate.active = False
            if backup_path.exists():
                backup_path.unlink()
        return {"status": "restored", **result}

    return router
