# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "Dexfloat.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "assets"), "assets")],
    hiddenimports=["pydexcom", "cryptography.fernet", "app.ui.settings_dialog"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Dexfloat", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
    icon=str(root / "assets" / "icon.ico"),
)
