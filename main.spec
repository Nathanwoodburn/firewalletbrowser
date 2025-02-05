# -*- mode: python ; coding: utf-8 -*-

import compileall
from PyInstaller.utils.hooks import collect_data_files
import os

compileall.compile_dir('.', force=True)



datas = [
    ('templates', 'templates'),
    ('assets', 'assets'),
    ('themes', 'themes'),
    ('plugins', 'plugins')
]
hiddenimports = [
    'plugins.automations',
    'plugins.batching',
    'plugins.customPlugins',
    'plugins.renewal',
    'plugins.varo'
]

# Copy the plugins folder to the dist folder
os.system(f'cp -r plugins dist/')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name='FireWallet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=False,
)
