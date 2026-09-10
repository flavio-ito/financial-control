from pathlib import Path
from threading import Timer
from typing import Optional
import json
import os
import socket
import sys
import traceback
import webbrowser

from filelock import FileLock, Timeout
import uvicorn

from app.api.security import SessionSecurity
from app.config import APP_ID, data_directory
from app.domain.recurrence import generate_pending_occurrences
from app.main import create_app
from app.maintenance.backup import MaintenanceGate, ensure_daily_backup
from app.storage.database import Database
from app.storage.migrations import migrate


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def notify_already_running(runtime_path: Path) -> None:
    message = "O Controle Financeiro Local já está em execução. Use a janela existente do navegador."
    try:
        if sys.platform == "win32" and os.environ.get("FINANCAS_NO_DIALOG") != "1":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Controle Financeiro Local", 0x40)
        else:
            print(message)
    except Exception:
        print(message)


def main(data_dir_override: Optional[str] = None, open_browser: bool = True) -> int:
    data_dir = data_directory(data_dir_override)
    lock = FileLock(str(data_dir / "{}.lock".format(APP_ID)))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        notify_already_running(data_dir / "runtime.json")
        return 2

    database_path = data_dir / "database.sqlite3"
    runtime_path = data_dir / "runtime.json"
    startup_error_path = data_dir / "startup-error.log"
    if startup_error_path.exists():
        try:
            startup_error_path.unlink()
        except OSError:
            pass
    db = None
    security = SessionSecurity()
    try:
        migrate(database_path, data_dir / "backups" / "pre-migration")
        db = Database(database_path)
        generate_pending_occurrences(db)
        ensure_daily_backup(database_path, data_dir / "backups" / "daily")

        port = available_port()
        token = security.issue_bootstrap()
        server_box = {}

        def request_shutdown():
            server_box["server"].should_exit = True

        app = create_app(database=db, security=security, shutdown_callback=request_shutdown, maintenance_gate=MaintenanceGate())
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False, log_config=None)
        server = uvicorn.Server(config)
        server_box["server"] = server
        runtime_path.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")
        url = "http://127.0.0.1:{}/#bootstrap={}".format(port, token)
        if open_browser and os.environ.get("FINANCAS_NO_BROWSER") != "1":
            Timer(0.35, lambda: webbrowser.open(url)).start()
        server.run()
        return 0
    except Exception:
        try:
            startup_error_path.write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        return 1
    finally:
        security.revoke_all()
        if db is not None:
            db.dispose()
        if runtime_path.exists():
            try:
                runtime_path.unlink()
            except OSError:
                pass
        lock.release()
