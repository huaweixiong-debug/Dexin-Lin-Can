# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=[],
    datas=[('config.json', '.'), ('win11_logo.ico', '.'), ('libs/windows/x86_64/libusb-1.0.dll', 'libs/windows/x86_64'), ('libs/windows/x86_64/USB2XXX.dll', 'libs/windows/x86_64')],
    hiddenimports=['snap7', 'snap7.client', 'snap7.util', 'tkinter', 'tkinter.ttk', 'sqlite3', 'queue', 'logging.handlers', 'platform', 'ctypes', 'os', 'time', 'threading', 'json', 'socket'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PyQt5', 'PySide2', 'wx', 'test', 'unittest', 'pytest', 'distutils', 'setuptools', 'pip', 'wheel', 'email', 'http', 'xml', 'html', 'urllib', 'asyncio', 'bz2', 'csv', 'tarfile', 'sqlite3.dump', 'tkinter.colorchooser', 'tkinter.commondialog', 'tkinter.filedialog', 'tkinter.font', 'tkinter.messagebox', 'tkinter.scrolledtext', 'tkinter.simpledialog', 'tkinter.tix', 'tkinter.dnd', 'tkinter.tkfiledialog', 'tkinter.tksimpledialog', 'tkinter.test'],
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
    name='LGV2_Test_System_Fixed',
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
)
