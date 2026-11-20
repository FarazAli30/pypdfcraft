"""Unit tests: wrapper logic against a fake engine that serves the REAL bundled tool schemas (no library needed)."""
import builtins
import contextlib
import io
import json
import os
import sys
import tempfile
import types
import warnings

import pytest

import pypdfcraft as pdf
from pypdfcraft import core
from pypdfcraft.errors import NativeLibraryError, ToolError, UnknownToolError

NS = types.SimpleNamespace
class MobileError(Exception): pass
class Command(MobileError): pass
class NeedsPassword(MobileError): pass

class Fake:
    def __init__(self):
        self.docs, self.calls, self.n = {}, [], 0
        self.reduce_written, self.ocr_ok = True, True
        self.lines = {1: ["Invoice 2023 total", "Thank you for 2023"], 2: ["Page two text"], 3: ["Hello world", "across lines"]}
    def tools(self): return core._bundled_catalog()
    def documents(self): return list(self.docs)
    def _info(self, name="x.pdf", dirty=False):
        self.n += 1
        self.docs[self.n] = NS(id=self.n, name=name, pages=[NS(w=1)] * 3, dirty=dirty, title=None, author=None,
                               subject=None, keywords=None, creator=None, producer=None, pdf_version="1.7")
        return self.docs[self.n]
    def open(self, path, pw):
        assert os.path.isabs(path), "native open() needs absolute paths"
        if pw == "needed": raise NeedsPassword("pw")
        return self._info(os.path.basename(path))
    def document(self, i): return self.docs[i]
    def close(self, d, discard): self.docs.pop(d)
    def page_plain_text(self, d, p): return f"page{p}"
    def render_page(self, d, p, scale, tile):
        self.scale = scale; return NS(width=2, height=2, rgba=bytes([255] * 16))
    def execute(self, name, args):
        a = json.loads(args) if args else {}
        self.calls.append((name, a))
        for k in ("path", "out", "out_dir", "folder"):
            if k in a: assert os.path.isabs(a[k]), (name, k, a[k])
        if name == "doc_reduce":
            if self.reduce_written: open(a["path"], "wb").write(b"x")
            return json.dumps({"path": a["path"], "written": self.reduce_written, "bytes_before": 100, "bytes_after": 50})
        if name == "doc_create": return json.dumps({"doc": self._info("new", True).id})
        if name == "doc_save":
            if a.get("path"): open(a["path"], "wb").write(b"saved")
            return json.dumps({"saved": a.get("path")})
        if name == "ocr_status": return json.dumps({"available": self.ocr_ok, "search_dirs": ["/x"], "languages": []})
        if name == "text_lines":
            return json.dumps({"page": a["page"], "lines": [{"line": i + 1, "text": t, "rect": [0, 0, 1, 1], "font": "Helvetica", "size": 12}
                                                           for i, t in enumerate(self.lines[a["page"]])]})
        if name == "text_paragraphs":
            joined = " ".join(self.lines[a["page"]])
            return json.dumps({"page": a["page"], "paragraphs": [{"paragraph": 1, "text": joined, "rect": [0, 0, 1, 1], "font": "Helvetica", "size": 12}]})
        if name == "text_edit":
            if "line" in a: self.lines[a["page"]][a["line"] - 1] = a["text"]
            else: self.lines[a["page"]] = [a["text"]]
            return json.dumps({"ok": True})
        if name == "page_images":
            n = 2 if a["page"] == 1 else 1
            return json.dumps({"page": a["page"], "images": [{"image": i + 1, "rect": [0, 0, 5, 5], "visible_rect": None, "pixels": [10, 10], "name": f"Im{i}", "kind": "image"} for i in range(n)]})
        return json.dumps({"ok": True, "tool": name, "args": a})



@pytest.fixture
def fake(tmp_path, monkeypatch):
    f = Fake()
    monkeypatch.chdir(tmp_path)
    core._state.update(session=None, registry=None)
    pdf.use_session(f)
    yield f
    core._state.update(session=None, registry=None)


def test_wrapper_logic(fake):
    open("in.pdf", "wb").write(b"%PDF-1.4 fake" * 20); open("b.pdf", "wb").write(b"%PDF-1.4 b")
    for n in ("logo.png", "n.docx", "n.txt", "p.jpg"): open(n, "wb").write(b"x")
    D = os.getcwd()
    def calls(name): return [c[1] for c in fake.calls if c[0] == name]

    # ---- optional output paths: automatic, absolute, never overwrite
    r = pdf.compress("in.pdf"); assert r.out == f"{D}/in_compressed.pdf" and r.written and r.bytes_after == 1
    fake.reduce_written = False
    r = pdf.compress("in.pdf"); assert r.out == f"{D}/in_compressed_2.pdf" and r.copied_original and os.path.exists(r.out)
    fake.reduce_written = True
    r = pdf.compress("in.pdf", "sub/small.pdf"); assert r.out == f"{D}/sub/small.pdf"
    r = pdf.compress("in.pdf", preset="mobile"); assert any(c[0] == "doc_optimize" for c in fake.calls)
    r = pdf.merge(["in.pdf", "b.pdf"]); assert r.out == f"{D}/in_merged.pdf"
    assert calls("doc_combine")[-1]["paths"] == [f"{D}/in.pdf", f"{D}/b.pdf"]
    r = pdf.split("in.pdf", every=2); assert r.out == f"{D}/in_parts" and os.path.isdir(r.out)
    for bad in (dict(), dict(every=1, max_mb=2)):
        try: pdf.split("in.pdf", **bad); pytest.fail("criterion")
        except ValueError: pass
    r = pdf.rotate("in.pdf", 90, pages=[1]); assert r.out == f"{D}/in_rotated.pdf" and calls("doc_save")[-1]["path"] == r.out
    r = pdf.delete_pages("in.pdf", [2]); r = pdf.extract_pages("in.pdf", [1, 2]); assert r.out == f"{D}/in_pages.pdf"
    r = pdf.protect("in.pdf", "secret"); assert calls("doc_protect")[-1]["open_password"] == "secret"
    r = pdf.rotate("in.pdf", 180, inplace=True); assert r.out == f"{D}/in.pdf" and "path" not in calls("doc_save")[-1]
    assert not fake.docs, "documents must be closed after each helper"

    # ---- text: lines / replace / edit
    l = pdf.lines("in.pdf", 1); assert l[0].line == 1 and l[0].text == "Invoice 2023 total" and l[0]["page"] == 1
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): pdf.show_lines("in.pdf", 1)
    assert "#1" in buf.getvalue() and "Invoice 2023 total" in buf.getvalue()
    r = pdf.replace_text("in.pdf", "2023", "2024")
    assert r.replaced == 2 and r.out.startswith(f"{D}/in_edited") and calls("text_edit")[0]["text"] == "Invoice 2024 total"
    assert fake.lines[1] == ["Invoice 2024 total", "Thank you for 2024"]
    r = pdf.replace_text("in.pdf", "WORLD across", "planet over", pages=[3])           # spans two lines -> paragraph mode
    assert r.replaced == 1 and "paragraph" in r.edits[0]["where"] and fake.lines[3] == ["Hello planet over lines"]
    try: pdf.replace_text("in.pdf", "zzz", "y"); pytest.fail("not found")
    except pdf.TextNotFound: pass
    assert pdf.replace_text("in.pdf", "zzz", "y", missing_ok=True).replaced == 0
    r = pdf.edit_line("in.pdf", 2, 1, "Replaced"); assert fake.lines[2] == ["Replaced"] and "in_edited_" in r.out and os.path.exists(r.out)
    try: pdf.edit_line("in.pdf", 2, 9, "x"); pytest.fail("range")
    except IndexError: pass
    pdf.edit_paragraph("in.pdf", 3, 1, "Hi", size=14, bold=True)
    assert calls("text_edit")[-1] == {"doc": calls("text_edit")[-1]["doc"], "page": 3, "paragraph": 1, "text": "Hi", "size": 14, "bold": True}
    pdf.add_text("in.pdf", 1, "NEW", at=[10, 20], size=14); assert calls("page_add_text")[-1]["at"] == [10, 20]

    # ---- interactive editor
    answers = iter(["2", "1", "Typed in console", "q"])
    builtins_input = builtins.input; builtins.input = lambda prompt="": next(answers)
    try:
        with contextlib.redirect_stdout(io.StringIO()): r = pdf.interactive_edit("in.pdf")
    finally: builtins.input = builtins_input
    assert fake.lines[2] == ["Typed in console"] and r.out.endswith(".pdf")
    answers = iter(["x"]); builtins.input = lambda prompt="": next(answers)
    try:
        with contextlib.redirect_stdout(io.StringIO()): assert pdf.interactive_edit("in.pdf") is None
    finally: builtins.input = builtins_input

    # ---- images
    im = pdf.images("in.pdf", 1); assert [i.image for i in im] == [1, 2] and im[0].pixels == [10, 10]
    r = pdf.replace_image("in.pdf", 1, 2, "logo.png")
    c = calls("image_edit")[-1]; assert c["action"] == "replace" and c["image"] == 2 and c["path"] == f"{D}/logo.png"
    pdf.replace_image("in.pdf", 2, None, "logo.png"); assert calls("image_edit")[-1]["image"] == 1     # single image -> auto
    try: pdf.replace_image("in.pdf", 1, None, "logo.png"); pytest.fail("ambiguous")
    except ValueError: pass
    pdf.delete_image("in.pdf", 2); assert calls("image_edit")[-1]["action"] == "delete"
    pdf.move_image("in.pdf", 1, 1, [0, 0, 50, 50]); assert calls("image_edit")[-1]["rect"] == [0, 0, 50, 50]
    r = pdf.save_image("in.pdf", 1, 1); assert r.out == f"{D}/in_p1_img1.png" and calls("image_save")[-1]["path"] == r.out
    r = pdf.extract_images("in.pdf"); assert r.out == f"{D}/in_images"
    pdf.add_image("in.pdf", 1, "logo.png", [0, 0, 10, 10]); assert calls("page_add_image")[-1]["path"] == f"{D}/logo.png"

    # ---- convert (both directions) + individual converters
    r = pdf.convert("in.pdf", "docx"); assert r.out == f"{D}/in.docx" and calls("doc_export_office")[-1]["path"] == r.out
    assert pdf.convert("in.pdf", "xlsx").out.endswith("in.xlsx") and pdf.to_powerpoint("in.pdf").out.endswith("in.pptx")
    r = pdf.convert("in.pdf", "jpg"); assert calls("doc_export_images")[-1]["format"] == "jpeg" and r.out == f"{D}/in_jpg"
    assert pdf.convert("in.pdf", "txt").out.endswith("in.txt") and pdf.convert("in.pdf", "md").out.endswith("in.md")
    r = pdf.convert("n.docx"); assert r.out == f"{D}/n.pdf" and calls("doc_create")[-1] == {"from": "office", "path": f"{D}/n.docx"}
    r = pdf.convert("p.jpg"); assert calls("doc_create")[-1]["from"] == "images" and r.out == f"{D}/p.pdf"
    r = pdf.convert("n.txt"); assert calls("doc_create")[-1]["from"] == "text"
    for bad in (("in.pdf", None), ("in.pdf", "zip"), ("a.zip", "pdf")):
        try: pdf.convert(*bad); pytest.fail("bad convert")
        except ValueError: pass

    # ---- OCR gate, text, render
    fake.ocr_ok = False
    try: pdf.ocr("in.pdf"); pytest.fail("models")
    except pdf.OcrModelsMissing: pass
    fake.ocr_ok = True; assert pdf.ocr("in.pdf", pages=[1]).out.endswith("_ocr.pdf") and pdf.ocr.status()["available"]
    assert pdf.extract_text("in.pdf", [1, 2]) == "page0\n\npage1"
    assert pdf.render("in.pdf", 1, dpi=144).to_png_bytes()[:4] == b"\x89PNG" and fake.scale == 2.0

    # ---- Document object: real-schema validation, groups, context manager
    d = pdf.open("in.pdf")
    try: d.rotate(); pytest.fail("missing degrees")
    except TypeError as e: assert "degrees" in str(e)
    try: d.rotate(degree=90); pytest.fail("typo")
    except TypeError as e: assert "degrees" in str(e)
    assert d.page.rotate(degrees=90)["args"]["doc"] == d.id and d.text_.find(query="a")["tool"] == "text_find"
    assert d.lines(1)[0].text.startswith("Invoice") and d.images(1)[0].image == 1
    try: d.nope; pytest.fail("unknown")
    except UnknownToolError: pass
    try: pdf.open("b.pdf", "needed"); pytest.fail("pw")
    except pdf.PasswordRequired: pass
    try: pdf.open("missing.pdf"); pytest.fail("missing")
    except pdf.OpenError: pass
    d.close(discard_changes=True)
    with pdf.edit("in.pdf") as doc: doc.replace_text("Page two", "Seite zwei", missing_ok=True) if False else doc.edit_line(2, 1, "x")
    d2 = pdf.open("in.pdf"); fake.docs[d2.id].dirty = True
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with d2: pass
    assert any("unsaved" in str(x.message) for x in w)

    # ---- help / search
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): pdf.help(); pdf.help("replace_text"); pdf.help("doc_reduce"); pdf.help("watermark")
    t = buf.getvalue(); assert "replace_text" in t and "Edit images" in t and "doc_reduce" in t
    assert any(n == "doc_watermark" for _, n, _ in pdf.search("watermark"))

    # ---- offline mode (no engine): signatures/docs still work from the bundled catalogue
    core._state.update(session=None, registry=None)
    orig = core.native
    def broken(): raise NativeLibraryError("no lib here")
    core.native = broken
    try:
        import inspect
        t = pdf.tool("doc_reduce"); assert list(inspect.signature(t).parameters) == ["doc", "path"] and len(pdf.tools()) >= 180
        try: t(doc=1, path="a"); pytest.fail("offline call must fail")
        except NativeLibraryError: pass
    finally:
        core.native = orig

    # ---- stubs from the catalogue
    from pypdfcraft.__main__ import main
    core._state.update(session=None, registry=None); pdf.use_session(fake)
    with contextlib.redirect_stdout(io.StringIO()):
        main(["stubs", "--out", "gen.py"]); main(["catalog", "--md", "t.md"])
    import importlib.util
    sp = importlib.util.spec_from_file_location("gen", "gen.py"); g = importlib.util.module_from_spec(sp); sp.loader.exec_module(g)
    assert g.doc_flatten(doc=1, fields=True)["args"] == {"doc": 1, "fields": True}

