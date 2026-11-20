"""Shared fixtures.  Engine tests are skipped automatically when the native library cannot be loaded."""
import os

import pytest

import pypdfcraft as pdf
from pypdfcraft.errors import NativeLibraryError
from pypdfcraft.image import Image


def pytest_collection_modifyitems(config, items):
    try:
        pdf.engine_version()
        available = True
    except NativeLibraryError:
        available = False
    if available:
        return
    skip = pytest.mark.skip(reason="native engine library not available (set PDFCRAFT_LIB or install a platform wheel)")
    for item in items:
        if "engine" in item.keywords:
            item.add_marker(skip)


def solid_png(path, width, height, rgb):
    Image(width, height, bytes([*rgb, 255]) * (width * height)).save(str(path))
    return str(path)


@pytest.fixture
def sample(tmp_path, monkeypatch):
    """A 3-page PDF made with the engine itself: text on every page and a red picture on page 1."""
    monkeypatch.chdir(tmp_path)
    red = solid_png(tmp_path / "red.png", 40, 40, (255, 0, 0))
    r = pdf.run_tool("doc_create", **{"from": "blank", "pages": 3})
    d = pdf.document(r["doc"])
    d.tool("page_add_text", page=1, text="Invoice 2023 total", at=[72, 100], size=14)
    d.tool("page_add_text", page=1, text="Thank you for 2023", at=[72, 130], size=12)
    d.tool("page_add_text", page=2, text="Page two text", at=[72, 100], size=12)
    d.tool("page_add_text", page=3, text="Hello world across lines", at=[72, 100], size=12)
    d.tool("page_add_image", page=1, path=red, rect=[72, 200, 172, 300])
    d.save(str(tmp_path / "in.pdf"))
    d.close(discard_changes=True)
    return str(tmp_path / "in.pdf")


def pixel(path, page, x_pt, y_pt, dpi=72):
    im = pdf.render(path, page, dpi)
    i = (int(y_pt * dpi / 72) * im.width + int(x_pt * dpi / 72)) * 4
    return tuple(im.rgba[i:i + 4])

