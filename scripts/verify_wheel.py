#!/usr/bin/env python3
"""Verify built wheels: integrity, metadata and that the bundled engine library is the right kind for the platform tag.

    python scripts/verify_wheel.py dist/*.whl

Checks, per wheel: zip CRCs; every file against the sizes/SHA-256 in RECORD; the ``Tag`` in WHEEL equals the file name;
Name/Version in METADATA equal the file name; exactly one engine library with the right name for the platform; its
format (ELF / Mach-O / PE) and CPU (x86_64, aarch64, arm, x86) match the tag; it exports the engine's UniFFI symbols.
Run in CI after building AND again after the artifacts were downloaded, so a damaged wheel is never published.
"""
import base64
import csv
import hashlib
import io
import re
import struct
import sys
import zipfile
from pathlib import Path

MARK = b"ffi_pdfcraft_android_uniffi_contract_version"
ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64", "arm64_v8a": "aarch64",
        "armv7l": "arm", "armeabi_v7a": "arm", "x86": "x86", "win32": "x86"}
ELF_MACHINE = {"x86_64": 62, "aarch64": 183, "arm": 40, "x86": 3}
MACHO_CPU = {"x86_64": 0x01000007, "aarch64": 0x0100000C}
PE_MACHINE = {"x86_64": 0x8664, "aarch64": 0xAA64, "x86": 0x14C}


def b64(data):
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def tag_info(plat):
    """-> (format, arch) from a platform tag like manylinux_2_28_x86_64 / macosx_11_0_arm64 / win_amd64 / android_24_arm64_v8a"""
    if plat.startswith("win"):
        fmt = "pe"
    elif plat.startswith("macosx"):
        fmt = "macho"
    elif plat.startswith(("manylinux", "musllinux", "linux", "android")):
        fmt = "elf"
    else:
        raise ValueError(f"unknown platform tag {plat!r}")
    for key in sorted(ARCH, key=len, reverse=True):
        if plat.endswith(key):
            return fmt, ARCH[key]
    raise ValueError(f"cannot tell the CPU from platform tag {plat!r}")


def lib_kind(data):
    """-> (format, arch) read from the library's own header."""
    if data[:4] == b"\x7fELF":
        return "elf", {v: k for k, v in ELF_MACHINE.items()}.get(struct.unpack_from("<H", data, 18)[0], "?")
    if data[:4] == b"\xcf\xfa\xed\xfe":
        return "macho", {v: k for k, v in MACHO_CPU.items()}.get(struct.unpack_from("<I", data, 4)[0], "?")
    if data[:2] == b"MZ":
        off = struct.unpack_from("<I", data, 0x3C)[0]
        if data[off:off + 4] == b"PE\0\0":
            return "pe", {v: k for k, v in PE_MACHINE.items()}.get(struct.unpack_from("<H", data, off + 4)[0], "?")
    return "unknown", "?"


def verify(path):
    """Return a list of problems (empty = wheel is good)."""
    path = Path(path)
    problems = []
    m = re.match(r"^(?P<name>[^-]+)-(?P<ver>[^-]+)-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>.+)\.whl$", path.name)
    if not m:
        return [f"{path.name}: not a wheel file name"]
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        return [f"{path.name}: not a readable zip ({e})"]
    with z:
        bad = z.testzip()
        if bad:
            problems.append(f"zip CRC error in {bad}")
        di = f"{m['name']}-{m['ver']}.dist-info"
        try:
            rows = {r[0]: r for r in csv.reader(io.StringIO(z.read(f"{di}/RECORD").decode())) if r}
        except KeyError:
            return problems + [f"{di}/RECORD is missing"]
        for n in z.namelist():
            if n.endswith("/RECORD"):
                continue
            if n not in rows:
                problems.append(f"{n} is not listed in RECORD")
                continue
            try:
                data = z.read(n)
            except Exception as e:                                      # noqa: BLE001  (bad CRC, bad deflate ...)
                problems.append(f"cannot read {n}: {e}")
                continue
            if rows[n][1] != f"sha256={b64(data)}" or int(rows[n][2]) != len(data):
                problems.append(f"{n}: content does not match RECORD (size {len(data)}, expected {rows[n][2]})")
        for n in rows:
            if n not in z.namelist() and not n.endswith("/RECORD"):
                problems.append(f"{n} is listed in RECORD but missing from the wheel")
        wheel = z.read(f"{di}/WHEEL").decode()
        if f"Tag: {m['py']}-{m['abi']}-{m['plat']}" not in wheel:
            problems.append("Tag in WHEEL does not match the file name")
        meta = z.read(f"{di}/METADATA").decode()
        norm = lambda x: re.sub(r"[-_.]+", "-", x).lower()                  # noqa: E731
        name = re.search(r"^Name: (.+)$", meta, re.M)
        version = re.search(r"^Version: (.+)$", meta, re.M)
        if not (name and version and norm(name.group(1)) == norm(m["name"]) and version.group(1) == m["ver"]):
            problems.append("Name/Version in METADATA do not match the file name")
        libs = [n for n in z.namelist() if n.startswith(f"{m['name']}/_lib/") and not n.endswith(".gitkeep")]
        if m["name"] == "pypdfcraft":
            if len(libs) != 1:
                problems.append(f"expected exactly one engine library in _lib/, found {libs}")
            else:
                try:
                    fmt, arch = tag_info(m["plat"])
                    try:
                        data = z.read(libs[0])
                    except Exception as e:                                  # noqa: BLE001
                        problems.append(f"cannot read the engine library: {e}")
                        return problems

                    want_name = {"pe": "pdfcraft_engine.dll", "macho": "libpdfcraft_engine.dylib"}.get(fmt, "libpdfcraft_engine.so")
                    if Path(libs[0]).name != want_name:
                        problems.append(f"library is named {Path(libs[0]).name}, expected {want_name}")
                    got = lib_kind(data)
                    if got != (fmt, arch):
                        problems.append(f"library is {got[0]}/{got[1]} but the platform tag says {fmt}/{arch}")
                    if MARK not in data:
                        problems.append("library does not export the engine's UniFFI symbols")
                except (ValueError, KeyError) as e:
                    problems.append(str(e))
    return problems


def main(argv):
    wheels = [Path(a) for a in argv[1:]]
    if not wheels:
        sys.exit(__doc__)
    failed = 0
    for w in wheels:
        probs = verify(w)
        print(("OK    " if not probs else "FAIL  ") + w.name)
        for p in probs:
            print("      - " + p)
        failed += bool(probs)
    if failed:
        sys.exit(f"{failed} wheel(s) failed verification")


if __name__ == "__main__":
    main(sys.argv)
