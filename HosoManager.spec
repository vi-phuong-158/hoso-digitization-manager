# -*- mode: python ; coding: utf-8 -*-
import json
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
hidden = collect_submodules("app.manager")
version_file = ROOT / "packaging" / "version_info.txt"
identity_file = ROOT / "build" / "build_identity.json"
identity_file.parent.mkdir(parents=True, exist_ok=True)
identity_file.write_text(json.dumps({
    "version": os.environ.get("HOSO_APP_VERSION", "0.2.0"),
    "build_sha": os.environ.get("HOSO_BUILD_SHA", "unknown"),
}) + "\n", encoding="utf-8")
a = Analysis(
    [str(ROOT / "app" / "manager" / "entrypoint.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "document_types.json"), "."),
        (str(ROOT / "app" / "manager" / "templates"), "app/manager/templates"),
        (str(ROOT / "app" / "manager" / "static"), "app/manager/static"),
        (str(identity_file), "app/manager"),
    ],
    hiddenimports=hidden + ["pypdf"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="HosoManager", debug=False,
    bootloader_ignore_signals=False, strip=False, upx=True, console=False,
    version=str(version_file),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="HosoManager")
