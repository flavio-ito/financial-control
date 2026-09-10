from pathlib import Path
import json
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from app.main import create_app
from app.storage.database import Database

target = root / "build" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=str(target.parent)) as temporary:
    database = Database(Path(temporary) / "schema.sqlite3")
    try:
        schema = create_app(database=database).openapi()
    finally:
        database.dispose()
target.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
