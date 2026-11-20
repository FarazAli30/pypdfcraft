"""Unit tests for the loader, the wheel builder and the generated modules (no native library needed)."""
import base64
import csv
import hashlib
import io
import json
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
    assert _loader.find_library() == str(fake.resolve())
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
