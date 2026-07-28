"""Build the standalone Windows GUI executable with PyInstaller."""

import os
import sys
from pathlib import Path

import PyInstaller.__main__


PROJECT_DIR = Path(__file__).resolve().parent
PYTHON_DIR = Path(sys.base_prefix)
TCL_DIR = PYTHON_DIR / "tcl"
DLL_DIR = PYTHON_DIR / "DLLs"


def bundle(source, destination):
    """Format a PyInstaller source/destination bundle argument."""
    return f"{source}{os.pathsep}{destination}"


def main():
    required = (
        PYTHON_DIR / "Lib" / "tkinter",
        TCL_DIR / "tcl8.6",
        TCL_DIR / "tk8.6",
        DLL_DIR / "_tkinter.pyd",
        DLL_DIR / "tcl86t.dll",
        DLL_DIR / "tk86t.dll",
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(
            "Cannot build because this Python installation is missing:\n- "
            + "\n- ".join(missing)
        )

    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name=CS2-Radar",
            f"--runtime-hook={PROJECT_DIR / 'packaging' / 'pyi_rth_tkinter.py'}",
            f"--add-data={bundle(PROJECT_DIR / 'config.json', '.')}",
            f"--add-data={bundle(PROJECT_DIR / 'offsets.json', '.')}",
            f"--add-data={bundle(PYTHON_DIR / 'Lib' / 'tkinter', 'tkinter')}",
            f"--add-data={bundle(TCL_DIR / 'tcl8.6', '_tcl_data')}",
            f"--add-data={bundle(TCL_DIR / 'tk8.6', '_tk_data')}",
            f"--add-binary={bundle(DLL_DIR / '_tkinter.pyd', '.')}",
            f"--add-binary={bundle(DLL_DIR / 'tcl86t.dll', '.')}",
            f"--add-binary={bundle(DLL_DIR / 'tk86t.dll', '.')}",
            str(PROJECT_DIR / "main.py"),
        ]
    )


if __name__ == "__main__":
    main()
