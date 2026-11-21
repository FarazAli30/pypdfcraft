"""Locate and load the native PdfCraft engine (a UniFFI ``cdylib``) on any platform.

Search order (first hit wins):

1. ``$PDFCRAFT_LIB`` - a full path to the library file
2. ``pypdfcraft/_lib/``  - where the platform wheels put it
3. ``pypdfcraft/``       - next to this file (hand-copied libraries)
4. the folder above the package, and the current directory

Accepted file names: ``libpdfcraft_engine.so | .dylib``, ``pdfcraft_engine.dll`` and the names the
upstream Android app uses (``libpdfcraft_android.so``).

If a library cannot be mapped from where it lies (Android's shared storage is mounted ``noexec``)
it is copied to private storage (``$PYPDFCRAFT_CACHE``, ``~/.pypdfcraft``, temp dir) and loaded
from there.
"""
import ctypes
import os
import shutil
import sys
import tempfile

LIB_NAMES = (
    "libpdfcraft_engine.so",
    "libpdfcraft_engine.dylib",
    "pdfcraft_engine.dll",
    "libpdfcraft_android.so",      # name used by the upstream Android app / cargo's default
    "libpdfcraft_android.dylib",
    "pdfcraft_android.dll",
)


def _candidates():
    here = os.path.dirname(os.path.abspath(__file__))
    env = os.environ.get("PDFCRAFT_LIB")
    if env:
        yield env
    for folder in (os.path.join(here, "_lib"), here, os.path.dirname(here), os.getcwd()):
        for name in LIB_NAMES:
            yield os.path.join(folder, name)


def _private_dirs():
    return [d for d in (os.environ.get("PYPDFCRAFT_CACHE"),
                        os.path.join(os.path.expanduser("~"), ".pypdfcraft"),
                        os.path.join(tempfile.gettempdir(), "pypdfcraft")) if d]


def find_library():
    """Return the first existing library path, or ``None``."""
    seen = set()
    for c in _candidates():
        c = os.path.abspath(c)
        if c not in seen and os.path.isfile(c):
            return c
        seen.add(c)
    return None


def _load(path):
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        with os.add_dll_directory(os.path.dirname(path)):
            return ctypes.CDLL(path)
    return ctypes.cdll.LoadLibrary(path)


def load_native():
    """Load the engine and return the ``ctypes`` library object (raises ``OSError`` with details)."""
    errors = []
    path = find_library()
    if path:
        try:
            return _load(path)
        except OSError as e:
            errors.append(f"{path}: {e}")
        for d in _private_dirs():
            try:
                os.makedirs(d, exist_ok=True)
                dst = os.path.join(d, os.path.basename(path))
                if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(path):
                    shutil.copyfile(path, dst)
                os.chmod(dst, 0o755)
                return _load(dst)
            except OSError as e:
                errors.append(f"{d}: {e}")
    else:
        errors.append("no libpdfcraft_engine / pdfcraft_engine library found in: " +
                      ", ".join(sorted({os.path.dirname(os.path.abspath(c)) for c in _candidates()})))
    raise OSError("; ".join(errors))
