# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Block cipher for encryption (optional)
# block_cipher = None

a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include config.json if it exists
        ('config.json', '.') if os.path.exists('config.json') else None,
        # Include icon file
        ('win11_logo.ico', '.') if os.path.exists('win11_logo.ico') else None,
        # Include database file
        ('test_results.db', '.') if os.path.exists('test_results.db') else None,
    ],
    hiddenimports=[
        # Explicitly include snap7 modules
        'snap7',
        'snap7.client',
        'snap7.util',
        'snap7.types',
        # Include tkinter modules
        'tkinter',
        'tkinter.ttk',
        # Include other modules that might be dynamically imported
        'sqlite3',
        'queue',
        'threading',
        'logging',
        'logging.handlers',
        'datetime',
        'json',
        'socket',
        'time',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PyQt5',
        'PySide2',
        'wx',
        'test',
        'unittest',
        'pytest',
        'distutils',
        'setuptools',
        'pip',
        'wheel',
        'email',
        'http',
        'xml',
        'html',
        'urllib',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add all Python files in the project directory
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py') and not file.startswith('test_'):
            module_path = os.path.join(root, file)
            # Convert to module name
            module_name = module_path[2:-3].replace('\\', '.')
            if module_name not in a.hiddenimports:
                a.hiddenimports.append(module_name)

# Remove None entries from datas
a.datas = [d for d in a.datas if d is not None]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LGV2_Test_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Use UPX compression to reduce size
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Change to True if you want to see console output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='win11_logo.ico' if os.path.exists('win11_logo.ico') else None,
)

# Create a single executable (no console window)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LGV2_Test_System',
)