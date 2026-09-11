"""Load PyMuPDF, including Windows C++ runtime discovery."""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

_PYMUPDF_LOAD_HINT = (
    "PyMuPDF failed to load. On Windows, install the Microsoft Visual C++ "
    "Redistributable (MSVCP140.dll): "
    "https://aka.ms/vs/17/release/vc_redist.x64.exe"
)


def _candidate_runtime_dirs() -> list[Path]:
    dirs: list[Path] = [Path(sys.base_prefix)]
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    dirs.append(system_root / "System32")

    for entry in sys.path:
        pymupdf_dir = Path(entry) / "pymupdf"
        if pymupdf_dir.is_dir():
            dirs.append(pymupdf_dir)

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    search_roots = [
        program_files_x86 / "Microsoft" / "Edge" / "Application",
        program_files / "Mozilla Firefox",
        program_files_x86 / "Microsoft" / "EdgeWebView" / "Application",
    ]
    for root in search_roots:
        if (root / "msvcp140.dll").is_file():
            dirs.append(root)
            continue
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and (child / "msvcp140.dll").is_file():
                dirs.append(child)
                break
    return dirs


@lru_cache(maxsize=1)
def prepare_pymupdf_dlls() -> None:
    """Add Windows directories that may contain MSVCP140.dll to the DLL search path."""
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    seen: set[str] = set()
    for directory in _candidate_runtime_dirs():
        try:
            resolved = str(directory.resolve())
        except OSError:
            continue
        if resolved in seen or not directory.is_dir():
            continue
        try:
            os.add_dll_directory(resolved)
        except OSError:
            continue
        seen.add(resolved)


def import_fitz():
    """Import PyMuPDF after making the Windows C++ runtime discoverable."""
    prepare_pymupdf_dlls()
    try:
        import fitz
    except ImportError as exc:
        raise ImportError(_PYMUPDF_LOAD_HINT) from exc
    return fitz
