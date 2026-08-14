# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build specification for PySimplePMT.

Produces a self-contained one-directory build: the Python interpreter, every
pip dependency and the Tcl/Tk runtime are all bundled, so the end user needs
nothing installed beyond the base system libraries listed in the .deb control
file.

Build with:
    pyinstaller packaging/pysimplepmt.spec --noconfirm --clean

DEVELOPMENT NOTES:
------------------
customtkinter ships its themes and assets as package data rather than as
importable modules, so they have to be collected explicitly or the app starts
with unstyled widgets.

tkinterdnd2 used to be bundled for drag-and-drop. Nothing imports it: it
exchanges drops with other applications, while reordering a row inside one
Treeview needs only the pointer position, so the task list does that in plain
Tk. Bundling it added a native extension for no gain.

plotly draws the interactive chart and tkinterweb embeds it in the window.
PNG, PDF and SVG export is drawn with Pillow by utils/chart_render.py, so no
browser and no rendering service is involved.
"""

import importlib.util
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

# The spec runs with the project root as the working directory
PROJECT_ROOT = Path(SPECPATH).parent

datas = []
binaries = []
hiddenimports = []


def bundle(package_name, optional=False):
    """
    Collect a package's modules, data files and binaries into the build.

    PARAMETERS:
    -----------
    package_name : str
        Import name of the package to bundle.
    optional : bool
        When True, a package that is not installed is reported and skipped
        rather than failing the build.

    DEVELOPMENT NOTES:
    ------------------
    Importability is checked first because collect_all does not raise for a
    package that is not installed - it logs a warning and returns empty lists.
    Relying on an exception would let a required package go missing from the
    build while the log claimed it had been bundled.
    """
    if importlib.util.find_spec(package_name) is None:
        message = f"[spec] package {package_name!r} is not installed"
        if optional:
            print(f"{message} - skipping (feature degrades gracefully)")
            return
        raise SystemExit(f"{message} - cannot build without it")

    package_datas, package_binaries, package_hidden = collect_all(package_name)

    datas.extend(package_datas)
    binaries.extend(package_binaries)
    hiddenimports.extend(package_hidden)
    print(f"[spec] bundled {package_name}: "
          f"{len(package_datas)} data, {len(package_binaries)} binaries, "
          f"{len(package_hidden)} modules")


# Themes, assets and rendering engines these packages load from disk at runtime
bundle('customtkinter')
bundle('plotly')
bundle('tkinterweb')
bundle('tkinterweb_tkhtml')

hiddenimports += [
    'plotly.graph_objects',
    'plotly.io',
    'plotly.offline',
    'tkinterweb',
    'tkinterweb_tkhtml',
    'openpyxl',
    'openpyxl.workbook',
    'PIL._tkinter_finder',
]

# The application's own assets directory, when it holds anything
assets_dir = PROJECT_ROOT / 'gantt_app' / 'assets'
if assets_dir.is_dir() and any(assets_dir.iterdir()):
    datas.append((str(assets_dir), 'gantt_app/assets'))

# Large packages that are never imported at runtime. Excluding them keeps the
# package to a sensible size for a desktop download.
excludes = [
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    'IPython', 'jupyter', 'notebook', 'pytest', 'sphinx',
    'pandas', 'scipy', 'setuptools._distutils',
    'matplotlib', 'numpy',
    # Plotly's matplotlib bridge, which imports numpy at module level. It is
    # never used and only produces a collection warning during the build.
    'plotly.matplotlylib',
    # Kaleido parses sys.argv at import time, so PyInstaller's isolated
    # submodule scan exits with "unrecognized arguments" and fails the build.
    # It is no longer a dependency; excluding it keeps a stray install out.
    'kaleido',
]


a = Analysis(
    [str(PROJECT_ROOT / 'run.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pysimplepmt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    upx=False,
    upx_exclude=[],
    name='pysimplepmt',
)
