"""Unit tests for the loader, the wheel builder and the generated modules (no native library needed)."""
import base64
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"

needs_repo = pytest.mark.skipif(not (SCRIPTS / "build_wheel.py").exists(),
                                reason="repository scripts not available (tests run from an installed wheel)")


# --------------------------------------------------------------------------------------------- loader
def test_loader_candidates_and_env(tmp_path, monkeypatch):
    from pypdfcraft import _loader
    fake = tmp_path / "libpdfcraft_engine.so"
    fake.write_bytes(b"not a real library")
    monkeypatch.setenv("PDFCRAFT_LIB", str(fake))
    assert os.path.samefile(_loader.find_library(), fake)
    monkeypatch.setenv("PDFCRAFT_LIB", str(tmp_path / "nope.so"))
    found = _loader.find_library()
    assert found is None or found != str(tmp_path / "nope.so")


def test_loader_reports_a_helpful_error(tmp_path, monkeypatch):
    from pypdfcraft import _loader
    bad = tmp_path / "libpdfcraft_engine.so"
    bad.write_bytes(b"\x7fELF but garbage")
    monkeypatch.setenv("PDFCRAFT_LIB", str(bad))
    monkeypatch.setenv("PYPDFCRAFT_CACHE", str(tmp_path / "cache"))
    with pytest.raises(OSError) as e:
        _loader.load_native()
    assert str(bad) in str(e.value)


# --------------------------------------------------------------------------------------------- wheel builder
@needs_repo
@pytest.mark.parametrize("tag, lib", [
    ("manylinux_2_28_x86_64", "libpdfcraft_engine.so"),
    ("musllinux_1_2_aarch64", "libpdfcraft_engine.so"),
    ("macosx_11_0_arm64", "libpdfcraft_engine.dylib"),
    ("macosx_10_13_x86_64", "libpdfcraft_engine.dylib"),
    ("win_amd64", "pdfcraft_engine.dll"),
    ("win_arm64", "pdfcraft_engine.dll"),
    ("android_24_arm64_v8a", "libpdfcraft_engine.so"),
    ("linux_aarch64", "libpdfcraft_engine.so"),
])
def test_build_wheel(tmp_path, tag, lib):
    fake = tmp_path / "engine.bin"
    fake.write_bytes(b"\x00engine\x00" * 100)
    subprocess.run([sys.executable, str(SCRIPTS / "build_wheel.py"), "--lib", str(fake), "--tag", tag,
                    "--out", str(tmp_path / "dist")], check=True, capture_output=True)
    (whl,) = (tmp_path / "dist").glob("*.whl")
    assert whl.name == f"pypdfcraft-{_version()}-py3-none-{tag}.whl"
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
        assert f"pypdfcraft/_lib/{lib}" in names
        assert "pypdfcraft/__init__.py" in names and "pypdfcraft/oneshot.py" in names
        assert "pypdfcraft/data/tools_catalog.json" in names
        di = f"pypdfcraft-{_version()}.dist-info"
        wheel = z.read(f"{di}/WHEEL").decode()
        assert "Root-Is-Purelib: false" in wheel and f"Tag: py3-none-{tag}" in wheel
        meta = z.read(f"{di}/METADATA").decode()
        assert "License-Expression: MIT OR Apache-2.0" in meta and "Provides-Extra: ocr" in meta
        assert f"{di}/licenses/NOTICE" in names and f"{di}/licenses/LICENSE-MIT" in names
        # RECORD must list every file with the right hash and size
        rows = list(csv.reader(io.StringIO(z.read(f"{di}/RECORD").decode())))
        listed = {r[0]: r for r in rows if r}
        for n in names:
            assert n in listed
            if n.endswith("RECORD"):
                continue
            data = z.read(n)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            assert listed[n][1] == f"sha256={digest}" and int(listed[n][2]) == len(data)


def _version():
    ns = {}
    exec((SRC / "pypdfcraft" / "_version.py").read_text(), ns)
    return ns["__version__"]


@needs_repo
def test_owner_is_consistent_everywhere():
    """The name in pyproject.toml must also be the licence holder / README owner, and upstream credit must remain."""
    import re
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    owner = re.search(r'authors\s*=\s*\[\{\s*name\s*=\s*"([^"]+)"', py).group(1)
    for f in ("LICENSE-MIT", "README.md", "AUTHORS.md"):
        assert owner in (ROOT / f).read_text(encoding="utf-8"), f
    assert "ArtCraft Team and the PdfCraft contributors" in (ROOT / "LICENSE-MIT").read_text(encoding="utf-8")
    assert "ArtCraft Team" in (ROOT / "NOTICE").read_text(encoding="utf-8") or "PdfCraft" in (ROOT / "NOTICE").read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------------- generated modules
@needs_repo
def test_oneshot_is_up_to_date():
    r = subprocess.run([sys.executable, str(SCRIPTS / "gen_oneshot.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_every_tool_has_a_oneshot_function():
    import pypdfcraft
    from pypdfcraft import oneshot
    cat = json.loads((SRC / "pypdfcraft" / "data" / "tools_catalog.json").read_text())["tools"] if (SRC / "pypdfcraft").exists() \
        else json.loads(Path(pypdfcraft.__file__).with_name("data").joinpath("tools_catalog.json").read_text())["tools"]
    session_level = {"doc_open", "doc_close", "doc_list", "doc_save"}
    missing = [t["name"] for t in cat if t["name"] not in session_level and not callable(getattr(oneshot, t["name"], None))]
    assert not missing
    assert len(oneshot.__all__) == len(cat) - len(session_level)


def test_tool_table_offline_matches_catalogue():
    import pypdfcraft
    from pypdfcraft import core
    infos = core._bundled_catalog()
    assert len(infos) >= 180 and all(i.name and i.input_schema for i in infos)
    assert pypdfcraft.help is not None and pypdfcraft.search("watermark")


# --------------------------------------------------------------------------------------------- metadata must be installable / uploadable
def _toml(path):
    try:
        import tomllib
    except ModuleNotFoundError:                       # Python < 3.11
        import tomli as tomllib
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


@needs_repo
def test_pyproject_is_valid_for_current_setuptools():
    """A PEP 639 licence expression and `License ::` classifiers must not be mixed (setuptools refuses to build)."""
    proj = _toml(ROOT / "pyproject.toml")["project"]
    assert isinstance(proj["license"], str)
    assert not [c for c in proj["classifiers"] if c.startswith("License ::")]
    for f in proj["license-files"]:
        assert (ROOT / f).is_file(), f
    assert (ROOT / proj["readme"]).is_file()


@needs_repo
def test_wheel_metadata_requirements_parse(tmp_path):
    """Every Requires-Dist line must be a valid PEP 508 requirement (PyPI rejects the upload otherwise)."""
    from packaging.requirements import Requirement
    fake = tmp_path / "engine.bin"
    fake.write_bytes(b"x")
    subprocess.run([sys.executable, str(SCRIPTS / "build_wheel.py"), "--lib", str(fake), "--tag", "win_amd64",
                    "--out", str(tmp_path)], check=True, capture_output=True)
    (whl,) = tmp_path.glob("*.whl")
    with zipfile.ZipFile(whl) as z:
        meta = z.read(f"pypdfcraft-{_version()}.dist-info/METADATA").decode()
    reqs = [l.split(": ", 1)[1] for l in meta.splitlines() if l.startswith("Requires-Dist: ")]
    assert reqs and all(Requirement(r) for r in reqs)
    assert not any(l.startswith("Classifier: License ::") for l in meta.splitlines())


# --------------------------------------------------------------------------------------------- OCR model download (no network in tests)
def test_packaged_licence_text_matches_the_expected_checksum():
    from pypdfcraft import models
    assert models._sha256_text(models.licence_path()) == models.LICENCE_SHA256


def test_fetch_needs_no_network_for_the_licence(tmp_path, monkeypatch):
    """The licence comes from the package (the CC website answered 403 to CI runners); only the models are downloaded."""
    from pypdfcraft import models
    wanted = []

    def fake_download(urls, target, sha, progress):
        wanted.append(Path(target).name)
        Path(target).write_bytes(b"model")

    monkeypatch.setattr(models, "_download", fake_download)
    out = models.fetch(str(tmp_path / "m"), progress=lambda *a: None)
    assert wanted == list(models.SHA256)                                    # nothing else was fetched
    for name in models.SHA256:
        assert models._sha256_text(str(Path(out) / f"{name}.LICENCE.txt")) == models.LICENCE_SHA256
    assert "CC-BY-SA-4.0" in (Path(out) / "ATTRIBUTION.txt").read_text()


def test_downloads_send_a_user_agent(monkeypatch):
    from pypdfcraft import models
    seen = {}

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return b""

    def fake_urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        return R()

    monkeypatch.setattr(models.urllib.request, "urlopen", fake_urlopen)
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        models._http_get("https://example.org/x", os.path.join(d, "x"))
    assert seen["ua"].startswith("pypdfcraft")


def test_licence_with_windows_line_endings_is_accepted(tmp_path, monkeypatch):
    """A Windows git checkout turns the licence into CRLF; that must not look like a damaged file (it did in CI)."""
    from pypdfcraft import models
    crlf = tmp_path / "CC-BY-SA-4.0.txt"
    crlf.write_bytes(Path(models.licence_path()).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert models._sha256(str(crlf)) != models.LICENCE_SHA256                 # a plain checksum would reject it ...
    assert models._sha256_text(str(crlf)) == models.LICENCE_SHA256            # ... the line-ending-proof one does
    monkeypatch.setattr(models, "licence_path", lambda: str(crlf))
    wanted = []
    monkeypatch.setattr(models, "_download", lambda urls, target, sha, progress: (wanted.append(Path(target).name),
                                                                                 Path(target).write_bytes(b"m")))
    out = models.fetch(str(tmp_path / "m"), progress=lambda *a: None)
    assert wanted == list(models.SHA256)                                     # still nothing downloaded for the licence
    written = (Path(out) / "text-detection.rten.LICENCE.txt").read_bytes()
    assert b"\r\n" not in written                                            # and it is written with LF endings


# --------------------------------------------------------------------------------------------- verify_wheel.py
def _fake_lib(kind, cpu, size=200_000):
    """A byte string with the header of a real ELF / Mach-O / PE file for ``cpu`` plus the engine's exported symbol name."""
    import os
    import struct
    b = bytearray(os.urandom(size))                           # incompressible: damage to it cannot go unnoticed
    if kind == "elf":
        b[:4] = b"\x7fELF"
        struct.pack_into("<H", b, 18, {"x86_64": 62, "aarch64": 183, "arm": 40, "x86": 3}[cpu])
    elif kind == "macho":
        b[:4] = b"\xcf\xfa\xed\xfe"
        struct.pack_into("<I", b, 4, {"x86_64": 0x01000007, "aarch64": 0x0100000C}[cpu])
    else:
        b[:2] = b"MZ"
        struct.pack_into("<I", b, 0x3C, 0x80)
        b[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<H", b, 0x84, {"x86_64": 0x8664, "aarch64": 0xAA64, "x86": 0x14C}[cpu])
    b[200:243] = b"ffi_pdfcraft_android_uniffi_contract_version"
    return bytes(b)


def _wheel(tmp_path, tag, lib):
    tmp_path.mkdir(parents=True, exist_ok=True)
    f = tmp_path / "engine.bin"
    f.write_bytes(lib)
    subprocess.run([sys.executable, str(SCRIPTS / "build_wheel.py"), "--lib", str(f), "--tag", tag,
                    "--out", str(tmp_path / "dist")], check=True, capture_output=True)
    return next((tmp_path / "dist").glob(f"*{tag}.whl"))


def _verify():
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_wheel", SCRIPTS / "verify_wheel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.verify


@needs_repo
@pytest.mark.parametrize("tag, kind, cpu", [
    ("manylinux_2_28_x86_64", "elf", "x86_64"), ("manylinux_2_28_aarch64", "elf", "aarch64"),
    ("musllinux_1_2_aarch64", "elf", "aarch64"), ("linux_aarch64", "elf", "aarch64"), ("linux_armv7l", "elf", "arm"),
    ("android_24_arm64_v8a", "elf", "aarch64"), ("android_24_armeabi_v7a", "elf", "arm"),
    ("android_24_x86_64", "elf", "x86_64"), ("android_24_x86", "elf", "x86"),
    ("macosx_11_0_arm64", "macho", "aarch64"), ("macosx_10_13_x86_64", "macho", "x86_64"),
    ("win_amd64", "pe", "x86_64"), ("win_arm64", "pe", "aarch64"),
])
def test_verify_accepts_a_matching_library(tmp_path, tag, kind, cpu):
    assert _verify()(_wheel(tmp_path, tag, _fake_lib(kind, cpu))) == []


@needs_repo
def test_verify_rejects_wrong_cpu_wrong_format_and_foreign_library(tmp_path):
    verify = _verify()
    assert any("aarch64" in p for p in verify(_wheel(tmp_path / "a", "android_24_arm64_v8a", _fake_lib("elf", "x86_64"))))
    assert any("macho" in p or "elf" in p for p in verify(_wheel(tmp_path / "b", "win_amd64", _fake_lib("elf", "x86_64"))))
    lib = bytearray(_fake_lib("elf", "x86_64"))
    lib[200:243] = b"x" * 43                                                   # not an engine library
    assert any("UniFFI" in p for p in verify(_wheel(tmp_path / "c", "manylinux_2_28_x86_64", bytes(lib))))


@needs_repo
def test_verify_detects_a_damaged_wheel(tmp_path):
    """The failure seen in the wild: the library inside a wheel no longer matches its checksum."""
    whl = _wheel(tmp_path, "android_24_arm64_v8a", _fake_lib("elf", "aarch64"))
    assert _verify()(whl) == []
    raw = bytearray(whl.read_bytes())
    with zipfile.ZipFile(whl) as z:
        zi = z.getinfo("pypdfcraft/_lib/libpdfcraft_engine.so")
    raw[zi.header_offset + 30 + len(zi.filename) + zi.compress_size // 2] ^= 0xFF     # one flipped byte in the middle
    whl.write_bytes(bytes(raw))
    problems = _verify()(whl)
    assert problems and any("libpdfcraft_engine.so" in p for p in problems)


@needs_repo
def test_verify_checks_the_tag_matches_the_file_name(tmp_path):
    whl = _wheel(tmp_path, "win_amd64", _fake_lib("pe", "x86_64"))
    renamed = whl.with_name(whl.name.replace("win_amd64", "macosx_11_0_arm64"))
    whl.rename(renamed)
    assert _verify()(renamed)
