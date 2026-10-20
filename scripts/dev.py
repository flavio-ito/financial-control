"""Run the authenticated local app with Vite hot updates."""
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from app.launcher.runtime import available_port, main


def run() -> int:
    repo = Path(__file__).resolve().parent.parent
    api_port = available_port()
    frontend_port = available_port()
    while frontend_port == api_port:
        frontend_port = available_port()
    origin = "http://127.0.0.1:{}".format(frontend_port)
    env = dict(os.environ, FINANCAS_DEV_API="http://127.0.0.1:{}".format(api_port))
    # Start Node directly so termination never leaves an npm child server running.
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js não encontrado.")
    process = subprocess.Popen(
        [node, str(repo / "frontend/node_modules/vite/bin/vite.js"), "--port", str(frontend_port)],
        cwd=str(repo / "frontend"), env=env,
    )
    try:
        opener = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + 30
        while True:
            if process.poll() is not None:
                raise RuntimeError("Vite encerrou antes de iniciar.")
            try:
                with opener.open(origin, timeout=1):
                    break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Vite não iniciou em 30 segundos.")
                time.sleep(0.2)
        data_dir = os.environ.get("FINANCAS_DATA_DIR", str(repo / "build/dev-data"))
        print("Desenvolvimento: {} | Dados: {}".format(origin, data_dir), flush=True)
        return main(data_dir_override=data_dir, frontend_url=origin, server_port=api_port)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        pass
