#!/usr/bin/env python3
"""Assemble a platform wheel: the pure-Python package + the native engine library for ONE platform.

    python scripts/build_wheel.py --lib target/release/libpdfcraft_android.so --tag manylinux_2_28_x86_64

The library is loaded with ``ctypes`` (UniFFI), so nothing links against a Python version: wheels are
tagged ``py3-none-<platform>`` and work on every Python >= 3.9 of that platform.  The library is stored
as ``pypdfcraft/_lib/{libpdfcraft_engine.so | libpdfcraft_engine.dylib | pdfcraft_engine.dll}``.

Platform tags used by the release workflow:
    manylinux_2_28_x86_64  manylinux_2_28_aarch64  musllinux_1_2_x86_64  musllinux_1_2_aarch64
    macosx_10_13_x86_64    macosx_11_0_arm64       win_amd64             win_arm64
    android_24_arm64_v8a   android_24_armeabi_v7a  android_24_x86_64     android_24_x86
    linux_aarch64          (Termux / Pydroid: the Android library with a plain linux tag; GitHub Releases only)
"""
import argparse
import base64
import csv
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:                                    # Python < 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "pypdfcraft"


def lib_name(tag):
    if tag.startswith("win"):
        return "pdfcraft_engine.dll"
    if tag.startswith("macosx"):
        return "libpdfcraft_engine.dylib"
    return "libpdfcraft_engine.so"


def norm(s):
    return re.sub(r"[-.]+", "_", s)


def b64(data):
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def metadata(proj, version, readme):
    lines = ["Metadata-Version: 2.4", f"Name: {proj['name']}", f"Version: {version}", f"Summary: {proj['description']}"]
    if proj.get("keywords"):
        lines.append("Keywords: " + ",".join(proj["keywords"]))
    for a in proj.get("authors", []):
        lines.append(f"Author-email: {a['name']} <{a['email']}>")
    for m in proj.get("maintainers", []):
        lines.append(f"Maintainer-email: {m['name']} <{m['email']}>")
    lines.append(f"License-Expression: {proj['license']}")
    for f in proj.get("license-files", []):
        lines.append(f"License-File: {Path(f).name}")
    lines += [f"Classifier: {c}" for c in proj.get("classifiers", [])]
    for k, v in proj.get("urls", {}).items():
        lines.append(f"Project-URL: {k}, {v}")
    lines.append(f"Requires-Python: {proj['requires-python']}")
    for extra, reqs in proj.get("optional-dependencies", {}).items():
        lines.append(f"Provides-Extra: {extra}")
        lines += [f'Requires-Dist: {r}; extra == "{extra}"' for r in reqs]
    lines += ["Description-Content-Type: text/markdown", "", readme]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lib", required=True, help="built engine library for the target platform")
    ap.add_argument("--tag", required=True, help="platform tag, e.g. manylinux_2_28_x86_64")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()

    lib = Path(a.lib)
    if not lib.is_file():
        sys.exit(f"library not found: {lib}")
    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    proj = py["project"]
    ns = {}
    exec((SRC / "_version.py").read_text(encoding="utf-8"), ns)
    version = ns["__version__"]
    plat = norm(a.tag)
    dist = norm(proj["name"])
    di = f"{dist}-{version}.dist-info"
    wheel_name = f"{dist}-{version}-py3-none-{plat}.whl"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    files = {}                                                   # archive name -> bytes
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc" and "_lib" not in p.relative_to(SRC).parts:
            files[f"pypdfcraft/{p.relative_to(SRC).as_posix()}"] = p.read_bytes()
    files[f"pypdfcraft/_lib/{lib_name(a.tag)}"] = lib.read_bytes()
    readme = (ROOT / proj["readme"]).read_text(encoding="utf-8")
    files[f"{di}/METADATA"] = metadata(proj, version, readme).encode("utf-8")
    files[f"{di}/WHEEL"] = (f"Wheel-Version: 1.0\nGenerator: pypdfcraft scripts/build_wheel.py\n"
                            f"Root-Is-Purelib: false\nTag: py3-none-{plat}\n").encode()
    files[f"{di}/entry_points.txt"] = b"[console_scripts]\npypdfcraft = pypdfcraft.__main__:main\n"
    for f in proj.get("license-files", []):
        files[f"{di}/licenses/{Path(f).name}"] = (ROOT / f).read_bytes()

    rec = io.StringIO()
    w = csv.writer(rec, lineterminator="\n")
    for name, data in files.items():
        w.writerow([name, f"sha256={b64(data)}", len(data)])
    w.writerow([f"{di}/RECORD", "", ""])
    files[f"{di}/RECORD"] = rec.getvalue().encode()

    target = out / wheel_name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in files.items():
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o755 if name.endswith((".so", ".dylib", ".dll")) else 0o644) << 16
            z.writestr(zi, data)
    print(f"{target}  ({target.stat().st_size // 1024} KiB)")


if __name__ == "__main__":
    main()
