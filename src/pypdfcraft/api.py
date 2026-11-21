"""One-call functions.  Output paths are optional: if you leave ``out`` away, a sensible new file is
created next to the source (``report.pdf`` -> ``report_compressed.pdf``) and never overwrites anything.
Use ``inplace=True`` to overwrite the source itself.

Every function returns a :class:`Result` (a dict with attribute access): ``r.out`` is what was written.
Page / line / image numbers are 1-based.  Call ``pypdfcraft.help()`` for the cheat sheet.
"""
import os
import shutil
from contextlib import contextmanager

from . import core, editing
from .editing import TextNotFound
from .errors import PdfCraftError
from .results import AttrDict, Result

CATALOG = {
    "Shrink / combine / split": ["compress", "merge", "split", "extract_pages", "delete_pages",
                                 "move_pages", "reverse_pages", "rotate"],
    "Edit text (real PDF text)": ["show_lines", "lines", "paragraphs", "find", "replace_text", "edit_line",
                                  "edit_paragraph", "interactive_edit", "add_text"],
    "Edit images": ["show_images", "images", "replace_image", "delete_image", "move_image", "edit_image",
                    "add_image", "save_image", "extract_images"],
    "Convert": ["convert", "to_images", "to_text", "to_word", "to_excel", "to_powerpoint", "to_html",
                "to_markdown", "to_pdfa", "images_to_pdf", "office_to_pdf", "text_to_pdf"],
    "Scan / OCR": ["ocr", "install_models"],
    "Security / redaction": ["protect", "unprotect", "redact"],
    "Stamp / forms / meta": ["watermark", "header_footer", "flatten", "fill_form", "form_fields",
                             "set_metadata", "compare"],
    "Read": ["info", "extract_text", "render", "bookmarks", "attachments"],
    "Any tool": ["apply", "run_tool"],
}
__all__ = sorted({n for v in CATALOG.values() for n in v} - {"install_models"}) + [
    "edit", "optimize", "apply", "query", "run_tool", "OcrModelsMissing", "TextNotFound", "CATALOG"]


class OcrModelsMissing(PdfCraftError):
    """OCR needs its model files: call pypdfcraft.install_models()."""


# ----------------------------------------------------------------------------- paths
def _p(path):
    return None if path is None else os.path.abspath(os.path.expanduser(os.fspath(path)))


def _o(path):
    """Output path: absolute, with its folder created."""
    p = _p(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    return p


def _free(path):
    """``a.pdf`` -> ``a.pdf`` if free, else ``a_2.pdf``, ``a_3.pdf`` ..."""
    base, ext = os.path.splitext(path)
    cand, n = path, 2
    while os.path.exists(cand):
        cand, n = f"{base}_{n}{ext}", n + 1
    return cand


def _auto_out(src, suffix, ext=".pdf"):
    base = os.path.splitext(_p(src))[0]
    return _free(f"{base}_{suffix}{ext}" if suffix else f"{base}{ext}")


def _auto_dir(src, suffix):
    return f"{os.path.splitext(_p(src))[0]}_{suffix}"


def _target(src, out, suffix, inplace=False, ext=".pdf"):
    if inplace:
        return _p(src)
    return _o(out) if out else _o(_auto_out(src, suffix, ext))


def _tool(name):
    return core.registry().lookup(name)


def _clean(**kw):
    return {k: v for k, v in kw.items() if v is not None}


_DOC_STATE = {"doc", "dirty", "editable", "encrypted", "index", "name", "path", "pages", "read_only_reason", "redo", "undo"}


def _res(r, **extra):
    """Wrap a tool result.  Tools that edit a document answer with the document's bookkeeping
    (``doc``, ``dirty``, ``undo`` ...); that is noise for a one-call function, so it is reduced to ``pages``."""
    base = dict(r) if isinstance(r, dict) else ({"result": r} if r is not None else {})
    if {"doc", "dirty", "editable"} <= base.keys():
        base = {"pages": base["pages"]} if "pages" in base else {}
    base.update(extra)
    return Result(base)


@contextmanager
def _open(src, password=None):
    doc = core.open(_p(src), password)
    try:
        yield doc
    finally:
        try:
            doc.close(discard_changes=True)
        except Exception:                                   # noqa: BLE001
            pass


def _save(doc, target, src):
    if _p(target) == _p(src):
        return doc.tool("doc_save")                          # overwrite the source
    return doc.tool("doc_save", path=_p(target))


@contextmanager
def edit(src, out=None, *, suffix="edited", inplace=False, password=None):
    """``with pypdfcraft.edit("in.pdf") as doc: doc.replace_text("a", "b")`` - opens, yields a Document,
    saves (to ``out`` or an automatic ``in_edited.pdf``) when the block ends without error."""
    target = _target(src, out, suffix, inplace)
    with _open(src, password) as doc:
        doc.out_path = target
        yield doc
        _save(doc, target, src)


def _edit_call(src, out, suffix, inplace, password, fn):
    """Run ``fn(doc)`` on an opened copy, save, and wrap the result."""
    with edit(src, out, suffix=suffix, inplace=inplace, password=password) as doc:
        r = fn(doc)
        target = doc.out_path
    return _res(r, out=target)


# ----------------------------------------------------------------------------- any tool, one call
def apply(src, tool, /, *, out=None, inplace=False, password=None, suffix="edited", **args):
    """Run **any** engine tool on a file in one call (all 186 are reachable this way).

        apply("a.pdf", "doc_flatten", fields=True)           # modifies -> saved to a_edited.pdf
        apply("a.pdf", "text_word_count")                    # read-only -> nothing is written
        apply("a.pdf", "page_rotate", degrees=90, out="r.pdf")

    The file is opened, ``tool`` is run with ``args``, and - only if the tool changed the document -
    the result is saved to ``out`` (default ``<name>_<suffix>.pdf``; ``inplace=True`` overwrites).
    Tools that write their own files (exports, splits ...) leave the document untouched, so nothing
    extra is saved.  Returns a :class:`Result`; ``r.out`` is the saved file (if any).
    See ``pypdfcraft.search("...")`` / ``TOOLS.md`` for tool names and their arguments."""
    with _open(src, password) as d:
        r = d.tool(tool, **args)
        target = None
        if d.info.dirty:
            target = _target(src, out, suffix, inplace)
            _save(d, target, src)
    return _res(r, out=target) if target else _res(r)


query = apply


def run_tool(tool, /, **args):
    """Run an engine tool that does not work on one open document (``doc_combine``, ``sign_id_create``,
    ``doc_bates_multi``, ``printers`` ...).  Returns a :class:`Result`."""
    r = _tool(tool)(**args)
    return Result(r) if isinstance(r, dict) else Result({"result": r})        # raw: keeps e.g. the new document's id


# ----------------------------------------------------------------------------- read
def info(src, password=None):
    """Metadata, pages, bookmarks, fields, fonts, security... (tool ``doc_info``)."""
    with _open(src, password) as d:
        return AttrDict(d.tool("doc_info"))


def extract_text(src, pages=None, password=None):
    """Plain text of the whole file (or the given 1-based pages)."""
    with _open(src, password) as d:
        return d.text(pages)


def render(src, page=1, dpi=144, password=None):
    """Draw one page -> Image (``.save('p.png')``, ``.to_pil()``, ``.to_numpy()``)."""
    with _open(src, password) as d:
        return d.render(page, scale=dpi / 72.0)


def bookmarks(src, password=None):
    """The outline / bookmarks tree."""
    with _open(src, password) as d:
        return d.tool("bookmark_list")


def attachments(src, password=None):
    """Files embedded in the PDF."""
    with _open(src, password) as d:
        return d.attachments()


def form_fields(src, password=None):
    """List the form fields (names, types, values) to use with fill_form()."""
    with _open(src, password) as d:
        return d.tool("form_fields")


# ----------------------------------------------------------------------------- text: look, pick, replace
def lines(src, page=None, password=None):
    """Numbered text lines ``[{page, line, text, rect, font, size}]`` (all pages if ``page`` is None)."""
    with _open(src, password) as d:
        return d.lines(page)


def paragraphs(src, page=None, password=None):
    """Numbered paragraphs ``[{page, paragraph, text, rect, font, size, bold, italic, color}]``."""
    with _open(src, password) as d:
        return d.paragraphs(page)


def find(src, query, password=None):
    """Where ``query`` occurs (page + rectangles)."""
    with _open(src, password) as d:
        return d.find_text(query)


def show_lines(src, page=None, password=None):
    """Print the numbered lines so you can choose one: ``p1 #3  [Helvetica 12pt]  Hello world``."""
    for l in lines(src, page, password):
        print(f"p{l['page']} #{l['line']:<3d} [{l.get('font', '?')} {l.get('size', '?')}pt]  {l['text']}")


def replace_text(src, old, new, *, out=None, pages=None, case_sensitive=False, first_only=False,
                 mode="auto", inplace=False, missing_ok=False, password=None):
    """Replace a phrase in the real text of the PDF (like editing a line in the app).

        replace_text("contract.pdf", "2023", "2024")           # -> contract_edited.pdf
        replace_text("a.pdf", "Mr. Smith", "Ms. Jones", inplace=True)

    ``mode``: 'line' (default behaviour of 'auto') edits single lines; use 'paragraph' for phrases that
    wrap across lines.  Raises TextNotFound when nothing matched (``missing_ok=True`` to ignore)."""
    with _open(src, password) as d:
        r = d.replace_text(old, new, pages=pages, case_sensitive=case_sensitive, first_only=first_only, mode=mode)
        if not r["replaced"]:
            if missing_ok:
                return Result(out=None, replaced=0, edits=[])
            raise TextNotFound(f"{old!r} was not found in the text of {os.path.basename(str(src))} "
                               "(scanned pages have no text: run ocr() first)")
        target = _target(src, out, "edited", inplace)
        _save(d, target, src)
    return Result(out=target, replaced=r["replaced"], edits=r["edits"])


def edit_line(src, page, line, text, *, out=None, inplace=False, password=None, **style):
    """Replace line number ``line`` (see ``show_lines``) on ``page`` with ``text``."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.edit_line(page, line, text, **style))


def edit_paragraph(src, page, paragraph, text=None, *, out=None, inplace=False, password=None, **format):
    """Edit/restyle a paragraph (``paragraphs(src, page)`` shows numbers).
    ``format``: font, bold, italic, size, color, align, line_spacing, dx, dy, width ..."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.edit_paragraph(page, paragraph, text, **format))


def add_text(src, page, text, *, at=None, rect=None, out=None, inplace=False, password=None, **style):
    """Put new text on a page at ``at=[x, y]`` points from the top-left (style: font, size, bold, color ...)."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_add_text", page=page, text=text, **_clean(at=at, rect=rect), **style))


class _Abort(Exception):
    pass


def interactive_edit(src, out=None, *, inplace=False, password=None):
    """Console editor: pick a page, pick a line number, type the new text.  ``q`` saves, ``x`` discards."""
    try:
        with edit(src, out, inplace=inplace, password=password) as doc:
            print(f"{os.path.basename(str(src))}: {doc.page_count} pages.   q = save & quit, x = quit without saving")
            while True:
                a = input("page number> ").strip().lower()
                if a == "q":
                    break
                if a == "x":
                    raise _Abort
                if not a.isdigit() or not 1 <= int(a) <= doc.page_count:
                    print("  not a page"); continue
                page = int(a)
                for l in doc.lines(page):
                    print(f"  #{l['line']:<3d} {l['text']}")
                b = input("line number (blank = back)> ").strip()
                if not b.isdigit():
                    continue
                cur = next((l for l in doc.lines(page) if l["line"] == int(b)), None)
                if cur is None:
                    print("  no such line"); continue
                print("  current:", cur["text"])
                new = input("  new text> ")
                try:
                    doc.edit_line(page, int(b), new)
                    print("  done")
                except PdfCraftError as e:
                    print("  refused:", e)
            target = doc.out_path
    except _Abort:
        print("discarded"); return None
    print("saved", target)
    return Result(out=target)


# ----------------------------------------------------------------------------- images
def images(src, page=None, password=None):
    """Embedded pictures ``[{page, image, rect, pixels, name, kind}]`` (numbers for the functions below)."""
    with _open(src, password) as d:
        return d.images(page)


def show_images(src, page=None, password=None):
    """Print the numbered pictures so you can choose one: ``p1 image 2  image (800, 600) px``."""
    for im in images(src, page, password):
        print(f"p{im['page']} image {im['image']:<3d} {im['kind']:5s} {im['pixels']} px  rect={im['rect']}  {im.get('name', '')}")


def replace_image(src, page, image, file, *, out=None, inplace=False, password=None):
    """Swap embedded picture number ``image`` on ``page`` for ``file`` (PNG/JPEG/...); placement kept.
    ``image`` may be None when the page has exactly one picture."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.replace_image(page, image, file))


def delete_image(src, page, image=None, *, out=None, inplace=False, password=None):
    """Remove a picture (``image`` may be None if the page has exactly one)."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.delete_image(page, image))


def move_image(src, page, image, rect, *, out=None, inplace=False, password=None):
    """Move/resize to ``rect=[x0, y0, x1, y1]`` (points, top-left origin)."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.edit_image(page, image, "move", rect=list(rect)))


def edit_image(src, page, image, action, *, out=None, inplace=False, password=None, **kw):
    """Any action: crop, rotate, rotate_by(degrees=), flip_horizontal, flip_vertical, bring_to_front ..."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.edit_image(page, image, action, **kw))


def add_image(src, page, file, rect=None, *, out=None, inplace=False, password=None):
    """Place a new picture on a page (centred if ``rect`` is not given)."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_add_image", page=page, path=_p(file), **_clean(rect=rect)))


def save_image(src, page, image, path=None, password=None):
    """Write one embedded picture to a file (default: next to the PDF)."""
    path = path or _auto_out(src, f"p{page}_img{image}", ".png")
    with _open(src, password) as d:
        r = d.save_image(page, image, _o(path))
    return _res(r, out=_p(path))


def extract_images(src, folder=None, *, min_size=None, pages=None, password=None):
    """Save every embedded picture into a folder (default ``<name>_images/``)."""
    folder = _p(folder) if folder else _auto_dir(src, "images")
    os.makedirs(folder, exist_ok=True)
    with _open(src, password) as d:
        r = d.tool("doc_export_all_images", folder=folder, **_clean(min_size=min_size, pages=pages))
    return _res(r, out=folder)


# ----------------------------------------------------------------------------- size / structure
def compress(src, out=None, *, preset=None, inplace=False, password=None, keep_original=True, **options):
    """Make the PDF smaller -> ``<name>_compressed.pdf`` (or ``out``).

    No options = Acrobat-style "Reduce File Size".  ``preset="mobile"`` or options such as
    ``discard_thumbnails=True`` use the PDF Optimizer.  If the file can't get smaller the engine
    writes nothing; with ``keep_original=True`` the output is then a copy and ``r.written`` is False."""
    target = _target(src, out, "compressed", inplace)
    tmp = target + ".tmp.pdf" if inplace else target
    with _open(src, password) as d:
        if preset is None and not options:
            r = d.tool("doc_reduce", path=tmp)
        else:
            r = d.tool("doc_optimize", path=tmp, **_clean(preset=preset), **options)
    r = _res(r)
    if os.path.exists(tmp):
        if inplace:
            os.replace(tmp, target)
    elif r.get("written") is False and keep_original:
        if not inplace:
            shutil.copyfile(_p(src), target)
        r["copied_original"] = True
    r.setdefault("bytes_before", os.path.getsize(_p(src)) if os.path.exists(_p(src)) else None)
    r["bytes_after"] = os.path.getsize(target) if os.path.exists(target) else None
    r["out"] = target
    return r


optimize = compress


def merge(paths, out=None, *, pages=None, passwords=None, field_conflicts=None):
    """Combine files in order -> ``<first>_merged.pdf`` (or ``out``).  Images, .txt, .docx/.xlsx/.pptx/.rtf also work.
    ``pages``: per-file ranges like ``["1-3, 6", None]``; ``passwords``: per file."""
    paths = [_p(p) for p in paths]
    if len(paths) < 2:
        raise ValueError("merge() needs at least two files")
    target = _o(out) if out else _o(_auto_out(paths[0], "merged"))
    r = _tool("doc_combine")(**_clean(paths=paths, out=target, pages=pages, passwords=passwords,
                                      field_conflicts=field_conflicts))
    return _res(r, out=target)


def split(src, out_dir=None, *, every=None, before=None, bookmarks=None, max_mb=None, password=None):
    """Split into ``<name>-partK.pdf`` files in ``<name>_parts/`` (or ``out_dir``).
    Give exactly one criterion: every=N pages, before=[pages], bookmarks=True, max_mb=N."""
    if sum(x is not None and x is not False for x in (every, before, bookmarks, max_mb)) != 1:
        raise ValueError("split(): give exactly one of every=, before=, bookmarks=True, max_mb=")
    folder = _p(out_dir) if out_dir else _auto_dir(src, "parts")
    os.makedirs(folder, exist_ok=True)
    with _open(src, password) as d:
        r = d.tool("doc_split", out_dir=folder,
                   **_clean(every=every, before=before, bookmarks=bookmarks or None, max_mb=max_mb))
    return _res(r, out=folder)


def extract_pages(src, pages, out=None, *, password=None):
    """Copy the given 1-based pages into a new PDF -> ``<name>_pages.pdf``."""
    target = _o(out) if out else _o(_auto_out(src, "pages"))
    with _open(src, password) as d:
        r = d.tool("page_extract", pages=list(pages), out=target)
    return _res(r, out=target)


def delete_pages(src, pages, *, out=None, inplace=False, password=None):
    """Remove the given 1-based pages -> ``<name>_edited.pdf``."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("page_delete", pages=list(pages)))


def move_pages(src, pages, to, *, out=None, inplace=False, password=None):
    """Move pages so they start at position ``to``."""
    return _edit_call(src, out, "reordered", inplace, password, lambda d: d.tool("page_move", pages=list(pages), to=to))


def reverse_pages(src, pages=None, *, out=None, inplace=False, password=None):
    """Reverse the page order (or of the given pages) -> ``<name>_reversed.pdf``."""
    return _edit_call(src, out, "reversed", inplace, password, lambda d: d.tool("page_reverse", **_clean(pages=pages)))


def rotate(src, degrees, pages=None, *, out=None, inplace=False, password=None, **options):
    """Rotate by a multiple of 90 (positive = clockwise); ``pages`` default: all."""
    return _edit_call(src, out, "rotated", inplace, password,
                      lambda d: d.tool("page_rotate", degrees=degrees, **_clean(pages=pages), **options))


def watermark(src, text=None, *, file=None, out=None, inplace=False, password=None, **options):
    """Text (or picture ``file=``) watermark; options: opacity, rotation, scale, font_size, color, pages, behind."""
    if text is None and file is None:
        raise ValueError("watermark(): give text or file=")
    return _edit_call(src, out, "watermarked", inplace, password,
                      lambda d: d.tool("doc_watermark", **_clean(text=text, file=_p(file) if file else None), **options))


def header_footer(src, *, out=None, inplace=False, password=None, **options):
    """Headers/footers: header_left/center/right, footer_left/center/right, font_size, color ..."""
    return _edit_call(src, out, "headers", inplace, password, lambda d: d.tool("doc_header_footer", **options))


def flatten(src, out=None, *, comments=None, fields=None, inplace=False, password=None):
    """Burn comments / form fields into the page content -> ``<name>_flattened.pdf``."""
    return _edit_call(src, out, "flattened", inplace, password,
                      lambda d: d.tool("doc_flatten", **_clean(comments=comments, fields=fields)))


def set_metadata(src, *, out=None, inplace=False, password=None, **fields):
    """``set_metadata("a.pdf", title="X", author="Me")``"""
    def run(d):
        for k, v in fields.items():
            d.tool("doc_set_info", key=k, value=str(v))
    return _edit_call(src, out, "meta", inplace, password, run)


def fill_form(src, values, *, out=None, inplace=False, password=None):
    """``values``: field name -> str / bool / list (names from ``form_fields(src)``)."""
    return _edit_call(src, out, "filled", inplace, password, lambda d: d.tool("form_fill", values=dict(values)))


# ----------------------------------------------------------------------------- security
def protect(src, open_password=None, permissions_password=None, *, out=None, inplace=False, password=None, **options):
    """Encrypt -> ``<name>_protected.pdf``.  options: printing, changes, copy, accessibility, compatibility ..."""
    if not (open_password or permissions_password):
        raise ValueError("protect(): give open_password= and/or permissions_password=")
    return _edit_call(src, out, "protected", inplace, password, lambda d: d.tool(
        "doc_protect", **_clean(open_password=open_password, permissions_password=permissions_password), **options))


def unprotect(src, password, out=None, *, inplace=False):
    """Remove the encryption (needs the password) -> ``<name>_unprotected.pdf``."""
    return _edit_call(src, out, "unprotected", inplace, password, lambda d: d.tool("doc_unprotect"))


def redact(src, find=None, *, out=None, inplace=False, apply=True, password=None, **mark):
    """Permanently black out text: ``redact("a.pdf", find="secret")`` (apply=False only marks)."""
    def run(d):
        marked = d.tool("redact_mark", **_clean(find=find), **mark)
        return {"marked": marked, "applied": d.tool("redact_apply") if apply else None}
    return _edit_call(src, out, "redacted", inplace, password, run)


# ----------------------------------------------------------------------------- OCR
def ocr_status():
    """``{"available": bool, "search_dirs": [...], "languages": [...]}``"""
    return _tool("ocr_status")()


def ocr(src, out=None, *, pages=None, language=None, dpi=None, skip_text_pages=None, inplace=False, password=None):
    """Make a scanned PDF searchable -> ``<name>_ocr.pdf``.  Run ``install_models()`` once first."""
    st = ocr_status()
    if isinstance(st, dict) and not st.get("available", True):
        raise OcrModelsMissing("OCR models are not installed. Run pypdfcraft.install_models() "
                               "(downloads ~12 MB) or install_models(apk='/path/to/pdfcraft.apk'). "
                               f"The engine looked in: {st.get('search_dirs')}")
    return _edit_call(src, out, "ocr", inplace, password, lambda d: d.tool(
        "ocr_recognize", **_clean(pages=pages, language=language, dpi=dpi, skip_text_pages=skip_text_pages)))


ocr.status = ocr_status


# ----------------------------------------------------------------------------- create from other formats
def _create_and_save(out, **kw):
    r = _tool("doc_create")(**kw)
    d = core.document(r.get("doc") if isinstance(r, dict) else None)
    try:
        d.save(path=out)
    finally:
        d.close(discard_changes=True)
    return _res(r, out=out)


def images_to_pdf(images, out=None, *, dpi=None):
    """One page per image -> ``<first image>.pdf`` (or ``out``)."""
    images = [_p(i) for i in images]
    target = _o(out) if out else _o(_auto_out(images[0], "", ".pdf"))
    return _create_and_save(target, **{"from": "images"}, paths=images, **_clean(dpi=dpi))


def text_to_pdf(src=None, out=None, *, text=None):
    """From a .txt file or a string (Western-European characters)."""
    if (src is None) == (text is None):
        raise ValueError("text_to_pdf(): give a .txt path or text=")
    target = _o(out) if out else (_o(_auto_out(src, "", ".pdf")) if src else _o("text.pdf"))
    return _create_and_save(target, **{"from": "text"}, **_clean(text=text, path=_p(src) if src else None))


def office_to_pdf(src, out=None):
    """.docx / .xlsx / .pptx / .rtf -> PDF (done on the device)."""
    target = _o(out) if out else _o(_auto_out(src, "", ".pdf"))
    return _create_and_save(target, **{"from": "office"}, path=_p(src))


# ----------------------------------------------------------------------------- convert out of PDF
def to_images(src, folder=None, *, dpi=None, format=None, pages=None, quality=None, password=None):
    """Pages -> picture files in ``<name>_png/`` (or ``_jpg`` / ``_tiff``); format: png, jpeg, tiff."""
    folder = _p(folder) if folder else _auto_dir(src, {"jpeg": "jpg", "jpg": "jpg", "tiff": "tiff"}.get(format or "png", "png"))
    os.makedirs(folder, exist_ok=True)
    with _open(src, password) as d:
        r = d.tool("doc_export_images", folder=folder, **_clean(dpi=dpi, format=format, pages=pages, quality=quality))
    return _res(r, out=folder)


def to_text(src, out=None, *, pages=None, password=None):
    """PDF -> plain .txt file (``<name>.txt``)."""
    target = _o(out) if out else _o(_auto_out(src, "", ".txt"))
    with _open(src, password) as d:
        r = d.tool("doc_export_text", path=target, **_clean(pages=pages))
    return _res(r, out=target)


def _to_office(src, out, ext, password, **kw):
    target = _o(out) if out else _o(_auto_out(src, "", ext))
    with _open(src, password) as d:
        r = d.tool("doc_export_office", path=target, **_clean(**kw))
    return _res(r, out=target)


def to_word(src, out=None, *, password=None):
    """PDF -> .docx"""
    return _to_office(src, out, ".docx", password)


def to_excel(src, out=None, *, password=None):
    """PDF -> .xlsx (tables)"""
    return _to_office(src, out, ".xlsx", password)


def to_powerpoint(src, out=None, *, password=None):
    """PDF -> .pptx"""
    return _to_office(src, out, ".pptx", password)


def to_html(src, out=None, *, html_mode=None, password=None):
    """PDF -> .html (``<name>.html``)."""
    return _to_office(src, out, ".html", password, html_mode=html_mode)


def to_markdown(src, out=None, *, password=None):
    """PDF -> Markdown (``<name>.md``)."""
    return _to_office(src, out, ".md", password)


def to_pdfa(src, out=None, *, level=None, inplace=False, password=None):
    """Archival PDF/A -> ``<name>_pdfa.pdf``"""
    return _edit_call(src, out, "pdfa", inplace, password, lambda d: d.tool("pdfa_convert", **_clean(level=level)))


_IMG_IN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".bmp"}
_OFFICE_IN = {".docx", ".xlsx", ".pptx", ".rtf"}
_OFFICE_OUT = {"docx": to_word, "word": to_word, "xlsx": to_excel, "excel": to_excel,
               "pptx": to_powerpoint, "powerpoint": to_powerpoint, "html": to_html,
               "md": to_markdown, "markdown": to_markdown}


def convert(src, to=None, out=None, **kw):
    """Convert in either direction.  The source type is detected from its extension.

        convert("report.pdf", "docx")      # PDF -> Word      (xlsx, pptx, html, md, txt)
        convert("report.pdf", "png")       # PDF -> pictures  (jpg, tiff) in a folder, one per page
        convert("report.pdf", "pdfa")      # PDF -> PDF/A
        convert("letter.docx")             # Word/Excel/PowerPoint/RTF -> PDF
        convert("photo.jpg")               # picture -> PDF        (use merge()/images_to_pdf for many)
        convert("notes.txt")               # text -> PDF
    """
    ext = os.path.splitext(str(src))[1].lower()
    if ext in _OFFICE_IN:
        return office_to_pdf(src, out)
    if ext in _IMG_IN:
        return images_to_pdf([src], out, **kw)
    if ext == ".txt":
        return text_to_pdf(src, out)
    if ext != ".pdf":
        raise ValueError(f"don't know how to convert {ext or 'this'} files")
    t = (to or "").lower().lstrip(".")
    if not t:
        raise ValueError('convert(): say what to convert to, e.g. convert("a.pdf", "docx")')
    if t in _OFFICE_OUT:
        return _OFFICE_OUT[t](src, out, **kw)
    if t in ("png", "jpg", "jpeg", "tif", "tiff"):
        return to_images(src, out, format={"jpg": "jpeg", "tif": "tiff"}.get(t, t), **kw)
    if t in ("txt", "text"):
        return to_text(src, out, **kw)
    if t in ("pdfa", "pdf/a"):
        return to_pdfa(src, out, **kw)
    raise ValueError(f"unknown target {to!r}: use docx, xlsx, pptx, html, md, txt, png, jpg, tiff, pdfa")


def compare(a, b, *, visual=None, limit=None, password_a=None, password_b=None):
    """Differences between two PDFs (tool ``doc_compare``)."""
    with _open(a, password_a) as da, _open(b, password_b) as db:
        return da.tool("doc_compare", other=db.id, **_clean(visual=visual, limit=limit))
