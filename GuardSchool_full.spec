# -*- mode: python ; coding: utf-8 -*-
# Сборка каталога со всеми DLL (портативно, без установленного Python).

from pathlib import Path

_datas = [('static', 'static'), ('widgets', 'widgets')]
_ico = Path(SPECPATH) / 'ico.png'
if _ico.is_file():
    _datas.append((str(_ico), '.'))

a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GuardSchool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GuardSchool',
)
