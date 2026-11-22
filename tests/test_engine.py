"""Integration tests against the REAL native engine (skipped automatically if it cannot be loaded)."""
import json
import os
import zipfile

import pytest
from conftest import pixel, solid_png

import pypdfcraft as pdf

pytestmark = pytest.mark.engine


def names(folder):
    return sorted(os.listdir(folder))


# ------------------------------------------------------------------------------------------ basics
def test_engine_and_tool_table():
    assert pdf.engine_version().count(".") == 2
    assert len(pdf.tools()) >= 180
    assert "doc_reduce" in pdf.tools() and callable(pdf.comment_add)


def test_open_relative_path_info_and_context(sample):
    with pdf.open("in.pdf") as doc:                       # relative path
        assert doc.page_count == 3 and len(doc) == 3
        assert "Invoice 2023 total" in doc.text(1)
        assert doc.metadata["pdf_version"]
    assert pdf.info("in.pdf")["pages"]


def test_errors(sample):
    with pytest.raises(pdf.OpenError):
        pdf.open("missing.pdf")
    with pytest.raises(pdf.TextNotFound):
        pdf.replace_text(sample, "no such phrase", "x")
    assert pdf.replace_text(sample, "no such phrase", "x", missing_ok=True).replaced == 0
    with pytest.raises(TypeError):
        pdf.page_rotate(sample)                          # missing required `degrees`
    with pytest.raises(pdf.PdfCraftError):
        pdf.rotate(sample, 45)                           # engine refuses non-multiples of 90


def test_never_overwrites(sample, tmp_path):
    a = pdf.compress(sample).out
    b = pdf.compress(sample).out
    assert a != b and os.path.exists(a) and os.path.exists(b)
    assert a.endswith("in_compressed.pdf") and b.endswith("in_compressed_2.pdf")


# ------------------------------------------------------------------------------------------ text
def test_lines_replace_edit(sample):
    assert [(l.line, l.text) for l in pdf.lines(sample, 1)] == [(1, "Invoice 2023 total"), (2, "Thank you for 2023")]
    r = pdf.replace_text(sample, "2023", "2024")
    assert r.replaced == 2 and r.out.endswith("in_edited.pdf")
    assert [l.text for l in pdf.lines(r.out, 1)] == ["Invoice 2024 total", "Thank you for 2024"]
    r2 = pdf.edit_line(sample, 2, 1, "Replaced line")
    assert pdf.lines(r2.out, 2)[0].text == "Replaced line"
    with pytest.raises(IndexError):
        pdf.edit_line(sample, 2, 9, "x")


def test_replace_text_paragraph_mode_and_inplace(sample):
    r = pdf.replace_text(sample, "Hello world", "Hi planet", pages=[3], mode="paragraph")
    assert "Hi planet" in pdf.extract_text(r.out, [3])
    pdf.replace_text(sample, "Page two", "Seite zwei", inplace=True)
    assert "Seite zwei" in pdf.extract_text(sample, [2])


def test_add_and_find_text(sample):
    r = pdf.add_text(sample, 2, "NEW TEXT", at=[72, 300], size=12)
    assert "NEW TEXT" in pdf.extract_text(r.out, [2])
    assert pdf.find(sample, "Thank")


# ------------------------------------------------------------------------------------------ images
def test_images_replace_delete_extract(sample, tmp_path):
    assert pixel(sample, 1, 120, 250) == (255, 0, 0, 255)
    im = pdf.images(sample, 1)
    assert [i.image for i in im] == [1] and im[0].pixels == [40, 40]
    blue = solid_png(tmp_path / "blue.png", 60, 30, (0, 0, 255))
    r = pdf.replace_image(sample, 1, None, blue)           # image=None: the page has exactly one
    assert pixel(r.out, 1, 120, 250) == (0, 0, 255, 255)
    d = pdf.delete_image(sample, 1, 1)
    assert pdf.images(d.out, 1) == []
    ex = pdf.extract_images(sample)
    assert ex.count == 1 and names(ex.out)
    s = pdf.save_image(sample, 1, 1)
    assert os.path.getsize(s.out) > 0


# ------------------------------------------------------------------------------------------ pages
def test_merge_split_extract_delete_rotate(sample):
    m = pdf.merge([sample, sample])
    assert len(pdf.info(m.out)["pages"]) == 6
    s = pdf.split(sample, every=1)
    assert names(s.out) == ["in-part1.pdf", "in-part2.pdf", "in-part3.pdf"]
    e = pdf.extract_pages(sample, [1, 3])
    assert len(pdf.info(e.out)["pages"]) == 2
    d = pdf.delete_pages(sample, [2])
    assert len(pdf.info(d.out)["pages"]) == 2
    r = pdf.rotate(sample, 90, pages=[1])
    assert pdf.info(r.out)["pages"][0]["rotation"] == 90
    with pytest.raises(ValueError):
        pdf.split(sample)                                # needs exactly one criterion
    assert len(pdf.info(pdf.move_pages(sample, [3], 1).out)["pages"]) == 3
    assert len(pdf.info(pdf.insert_blank_page(sample, 2).out)["pages"]) == 4
    assert pdf.number_pages(sample, style="lower-roman").out.endswith("numbered.pdf")


def test_compress_reports_sizes(sample):
    r = pdf.compress(sample)
    assert os.path.exists(r.out) and r.bytes_after is not None
    r2 = pdf.compress(sample, preset="mobile")
    assert os.path.exists(r2.out)


# ------------------------------------------------------------------------------------------ security
def test_protect_unprotect(sample):
    p = pdf.protect(sample, "secret1234")
    with pytest.raises(pdf.PasswordRequired):
        pdf.open(p.out)
    with pytest.raises(pdf.WrongPassword):
        pdf.open(p.out, "nope-nope-1")
    with pdf.open(p.out, "secret1234") as doc:
        assert doc.page_count == 3
    u = pdf.unprotect(p.out, "secret1234")
    with pdf.open(u.out) as doc:
        assert doc.page_count == 3


def test_redact_really_removes_text(sample):
    r = pdf.redact(sample, find="Invoice")
    assert "Invoice" not in pdf.extract_text(r.out)


def test_watermark_and_sanitize(sample):
    w = pdf.watermark(sample, "DRAFT", opacity=0.3)
    assert "DRAFT" in pdf.extract_text(w.out)
    assert pdf.sanitize(sample).out.endswith("sanitized.pdf")
    assert "total" in pdf.hidden_info(sample)


def test_sign_and_list(sample, tmp_path):
    idp = tmp_path / "me.p12"
    pdf.create_digital_id(idp, name="Test Signer", password="s3cret-pass-1", email="t@example.com")
    s = pdf.sign(sample, idp, id_password="s3cret-pass-1", reason="approve", page=1, rect=[72, 600, 272, 660])
    assert s.out.endswith("in_signed.pdf") and os.path.getsize(s.out) > os.path.getsize(sample)
    assert pdf.signatures(s.out)["count"] == 1


# ------------------------------------------------------------------------------------------ convert
def test_convert_both_directions(sample, tmp_path):
    docx = pdf.convert(sample, "docx")
    assert docx.out.endswith("in.docx") and zipfile.is_zipfile(docx.out)
    assert zipfile.is_zipfile(pdf.convert(sample, "xlsx").out)
    assert zipfile.is_zipfile(pdf.convert(sample, "pptx").out)
    assert "Invoice 2023 total" in open(pdf.convert(sample, "md").out, encoding="utf-8").read()
    assert "Invoice" in open(pdf.convert(sample, "txt").out, encoding="utf-8").read()
    assert pdf.convert(sample, "html").out.endswith("in.html")
    png = pdf.convert(sample, "png")
    assert png.out.endswith("in_png") and names(png.out) == ["in_page_1.png", "in_page_2.png", "in_page_3.png"]
    jpg = pdf.convert(sample, "jpg", dpi=72)
    assert jpg.out.endswith("in_jpg") and all(n.endswith((".jpg", ".jpeg")) for n in names(jpg.out))
    back = pdf.convert(docx.out)                           # Word -> PDF
    assert "Invoice" in pdf.extract_text(back.out)
    pic = pdf.convert(os.path.join(png.out, "in_page_1.png"))   # picture -> PDF
    assert len(pdf.info(pic.out)["pages"]) == 1
    assert pdf.to_pdfa(sample).out.endswith("pdfa.pdf")


# ------------------------------------------------------------------------------------------ rendering
def test_render_and_image_helpers(sample, tmp_path):
    im = pdf.render(sample, 1, 144)
    assert (im.width, im.height) == (1224, 1584)
    out = im.save(tmp_path / "p.png")
    assert open(out, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
    with pdf.open(sample) as doc:
        tile = doc.render(1, 1.0, region=(0, 0, 100, 50))
        assert (tile.width, tile.height) == (100, 50)
    assert pdf.thumbnail(sample, 128).width <= 128


# ------------------------------------------------------------------------------------------ forms / comments / links
def test_forms_roundtrip(sample):
    f = pdf.add_form_field(sample, 1, "text", [72, 400, 272, 424], name="fullname")
    assert pdf.form_fields(f.out)["fields"][0]["name"] == "fullname"
    g = pdf.fill_form(f.out, {"fullname": "Ada Lovelace"})
    assert pdf.form_fields(g.out)["fields"][0]["value"] == "Ada Lovelace"


def test_comments_links_bookmarks(sample):
    c = pdf.add_comment(sample, 1, "note", at=[100, 100], contents="hi", author="me")
    assert pdf.comments(c.out)["count"] == 1
    assert pdf.add_link(sample, 1, [72, 72, 200, 90], url="https://example.com").out.endswith(".pdf")
    b = pdf.add_bookmark(sample, "Chapter 1", 1)
    assert pdf.bookmarks(b.out)


def test_bates(sample):
    r = pdf.bates([sample], prefix="AC-", start_number=7, digits=4)
    assert r.completed == 1 and "AC-0009" in pdf.extract_text(sample.replace("in.pdf", "in_bates.pdf"))


# ------------------------------------------------------------------------------------------ generic tool access
@pytest.mark.filterwarnings("ignore:.*unsaved changes")
def test_apply_and_oneshot(sample):
    q = pdf.apply(sample, "text_word_count")               # read-only: nothing written
    assert q.out is None
    f = pdf.apply(sample, "doc_flatten", fields=True)
    assert f.out.endswith("in_edited.pdf")
    assert pdf.doc_background(sample, color="#fff8dc").out.endswith(".pdf")
    assert pdf.run_tool("ocr_status")["languages"] is not None
    with pdf.open(sample) as doc:
        assert doc.page.rotate(degrees=90, pages=[1])["rotated"] == 1
        assert doc.tool("text_word_count")


def test_edit_context_manager(sample):
    with pdf.edit(sample) as doc:
        doc.replace_text("2023", "2024")
        doc.rotate(degrees=90, pages=[1])
    assert doc.out_path.endswith("in_edited.pdf")
    assert "2024" in pdf.extract_text(doc.out_path, [1])


# ------------------------------------------------------------------------------------------ native text-geometry methods
def test_native_text_methods(sample):
    with pdf.open(sample) as doc:
        n = doc.glyph_count(1)
        assert n > 20
        g = doc.nearest_glyph(1, 80, 108)
        assert g is not None and len(doc.glyph_rect(1, g)) == 4
        assert [b.text for b in doc.blocks(1)] == ["Invoice 2023 total", "Thank you for 2023"]
        hits = doc.search("thank")
        assert hits and hits[0][0] == 1
        assert doc.outline() == []


# ------------------------------------------------------------------------------------------ OCR (needs the model files)
def test_ocr_roundtrip(sample, tmp_path):
    from pypdfcraft import models
    if not models.find_dir():
        pytest.skip("OCR models not installed (pip install pypdfcraft[ocr])")
    models.ensure_env()
    scan = pdf.render(sample, 1, 200).save(tmp_path / "scan.png")
    pic = pdf.images_to_pdf([scan], tmp_path / "scan.pdf")
    assert pdf.extract_text(pic.out).strip() == ""
    r = pdf.ocr(pic.out)
    assert "Invoice" in pdf.extract_text(r.out)


def test_bundled_catalogue_matches_engine():
    """data/tools_catalog.json must be a snapshot of the loaded library's own tool table."""
    from pypdfcraft import core
    bundled = {i.name: json.loads(i.input_schema) for i in core._bundled_catalog()}
    live = {t.name: json.loads(t.input_schema) for t in pdf._native().MobileSession().tools()}
    assert bundled == live


# ------------------------------------------------------------------------------------------ Read Aloud
def test_reading_text_and_read_aloud_order(sample):
    from pypdfcraft import speech
    paras = pdf.reading_text(sample)
    assert [p.text for p in paras] == ["Invoice 2023 total", "Thank you for 2023", "Page two text", "Hello world across lines"]
    assert [p.page for p in paras] == [1, 1, 2, 3]

    class Rec(speech.Backend):
        name = "rec"

        def __init__(self):
            self.spoken = []

        def available(self):
            return True

        def speak(self, text, **kw):
            self.spoken.append(text)

    rec, words = Rec(), []
    pdf.read_aloud(sample, pages=[1, 2], backend=rec, rate=1.2, on_word=words.append)
    assert rec.spoken == ["Invoice 2023 total", "Thank you for 2023", "Page two text"]
    with pdf.open(sample) as doc:
        assert [p["text"] for p in doc.reading_text(2)] == ["Page two text"]
        r = speech.ReadAloud(doc, pages=[1], backend=Rec())
        ws = r.words(0)
        assert [w.text for w in ws] == ["Invoice", "2023", "total"]
        for w in ws:                                    # rectangles really are where the words are on the page
            x0, y0, x1, y1 = w.rect
            assert 60 < x0 < x1 < 400 and 95 < y0 < y1 < 125
    with pytest.raises(pdf.PdfCraftError, match="nothing to read"):
        pdf.read_aloud(sample, pages=[], backend=Rec())


def test_to_audio_with_a_real_speech_engine(sample):
    import wave

    from pypdfcraft import speech
    try:
        backend = speech.get_backend()
    except speech.NoSpeechEngine:
        pytest.skip("no text-to-speech engine installed (e.g. apt install espeak-ng)")
    if not backend.can_save:
        pytest.skip(f"speech engine {backend.name} cannot write files")
    r = pdf.to_audio(sample, pages=[1, 2])
    assert r.out.endswith("in.wav") and r.words == 10 and r.engine == backend.name
    with wave.open(r.out) as w:
        assert w.getnframes() / w.getframerate() > 1.0
    faster = pdf.to_audio(sample, r.out.replace("in.wav", "fast.wav"), pages=[1, 2], rate=2.0)
    assert faster.seconds < r.seconds
