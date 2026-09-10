from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

repo = Path(SPECPATH).parents[1]
backend = repo / "backend"

datas = [
    (str(backend / "app" / "static"), "app/static"),
    (str(backend / "migrations"), "migrations"),
    (str(backend / "alembic.ini"), "."),
    (str(repo / "README.md"), "."),
    (str(repo / "LICENSE"), "."),
    (str(repo / "docs"), "docs"),
]

hiddenimports = collect_submodules("uvicorn") + [
    "sqlalchemy.dialects.sqlite",
    "multipart",
]

a = Analysis(
    [str(backend / "app" / "launcher" / "__main__.py")],
    pathex=[str(backend)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "setuptools", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ControleFinanceiroLocal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="ControleFinanceiroLocal",
)
