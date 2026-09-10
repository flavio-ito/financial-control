from pathlib import Path
import sys

from app.config import data_directory
from app.launcher.runtime import main

if "--self-test" in sys.argv:
    from app.maintenance.self_test import run_packaged_self_test
    raise SystemExit(run_packaged_self_test(data_directory()))

raise SystemExit(main())
