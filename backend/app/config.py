from pathlib import Path
from typing import Optional
import os
import sys

from platformdirs import user_data_path

APP_ID = "br.com.local.financas"
APP_VERSION = "0.1.0"
DEFAULT_CURRENCY = "BRL"
SAFE_INTEGER_MAX = 9_007_199_254_740_991


def data_directory(override: Optional[str] = None) -> Path:
    configured = override or os.environ.get("FINANCAS_DATA_DIR")
    if configured:
        result = Path(configured).expanduser().resolve()
    else:
        result = Path(user_data_path(APP_ID, appauthor=False, roaming=False))
    result.mkdir(parents=True, exist_ok=True)
    return result


def resource_directory() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "app" / "static"
    return Path(__file__).resolve().parent / "static"

