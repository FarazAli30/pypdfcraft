"""Session management and the Document class."""
import sys
import warnings

from . import errors as E
from .image import Image
from .tools import Registry, ToolGroup

_state = {"native": None, "session": None, "registry": None}


# --------------------------------------------------------------------------- native / session
def native():
    """The generated UniFFI bindings module (loaded lazily)."""
    if _state["native"] is None:
        try:
            from . import _bindings
        except Exception as e:                          # OSError (not found / wrong CPU) or UniFFI checksum mismatch
            import platform
            raise E.NativeLibraryError(
                f"Could not load the PdfCraft engine: {e}\n"
                f"This Python is {platform.machine()} / {sys.platform}. Install the wheel for your platform "
                "(pip install pypdfcraft), or - when using a hand-built/extracted library - put it in "
                "pypdfcraft/_lib/ or set PDFCRAFT_LIB=/full/path/to/library. "
                "If it says 'checksum' / 'contract version', the library is from a different engine build than the "
                "installed bindings. Run `python -m pypdfcraft diagnose` for details.") from e
        _state["native"] = _bindings
    return _state["native"]


def session():
    """The default :class:`MobileSession` (created on first use)."""
    if _state["session"] is None:
        n = native()
        from .models import ensure_env
        ensure_env()
        _state["session"] = n.MobileSession()
    return _state["session"]


def use_session(s):
    """Use a specific session object (e.g. a second isolated session, or a test double)."""
    _state["session"], _state["registry"] = s, None


def _bundled_catalog():
    import builtins
    import json
    import os
    import types
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tools_catalog.json")
    with builtins.open(p, encoding="utf-8") as f:
        data = json.load(f)["tools"]
    return [types.SimpleNamespace(name=t["name"], title=t["title"], description=t["description"],
                                  input_schema=json.dumps(t["input_schema"]), read_only=t["read_only"])
            for t in data]


def registry():
    """The tool registry.  Uses the live engine's table; if the native library cannot be loaded
    it falls back to the bundled catalogue (docs/help/signatures work, calls raise
    NativeLibraryError)."""
    if _state["registry"] is None:
        try:
            _state["registry"] = Registry(session)
        except E.NativeLibraryError:
            _state["registry"] = Registry(session, _bundled_catalog(), offline=True)
    return _state["registry"]


def translate_error(e):
    """Map the engine's MobileError variants to pdfcraft.errors classes."""
    if any(c.__name__ == "MobileError" for c in type(e).__mro__):
        kind = type(e).__name__
        cls = {"Command": E.ToolError, "Open": E.OpenError, "NeedsPassword": E.PasswordRequired,
               "WrongPassword": E.WrongPassword, "Render": E.RenderError,
               "NoDocument": E.NoDocumentError}.get(kind, E.PdfCraftError)
        return cls(str(e))
    return e


def diagnose():
    """Print what is needed to load the engine (CPU, Python, library path, load result)."""
    import os
    import platform
    print("python      :", sys.version.split()[0], platform.machine(), sys.platform)
    print("package     :", os.path.dirname(os.path.abspath(__file__)))
    from . import _loader
    print("library     :", _loader.find_library() or "not found")
    try:
        native()
        print("engine      : loaded, version", native().engine_version())
    except E.NativeLibraryError as e:
        print("engine      : NOT loaded\n", e)
        return False
    from .models import status as _ms
    print("ocr models  :", _ms())
    return True


def _guard(fn):
    def wrapper(*a, **k):
        try:
            return fn(*a, **k)
        except Exception as e:                      # noqa: BLE001
            t = translate_error(e)
            if t is e:
                raise
            raise t from None
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


# --------------------------------------------------------------------------- module-level helpers
def engine_version():
    return native().engine_version()


def init_logging():
    native().init_logging()


@_guard
def thumbnail(path, max_side=256):
    """Page 1 of the PDF at ``path`` as an :class:`Image` fitting ``max_side`` pixels."""
    return Image._from_native(native().file_thumbnail(str(path), int(max_side)))


@_guard
def digital_id_info(path, password):
    """Certificate details of a .p12/.pfx digital ID."""
    return native().digital_id_info(str(path), password)


def release_memory():
    session().release_memory()


# --------------------------------------------------------------------------- Document
class Document:
    """An open PDF.  **All page numbers in this class are 1-based.**

    Everything the engine can do is reachable from here:

    * explicit methods: ``text, blocks, search, render, outline, links, comments, ...``
    * friendly verbs:   ``doc.compress(...), doc.split(...), doc.ocr(...), doc.rotate(...)``
    * grouped tools:    ``doc.page.rotate(...), doc.text_.find(...)``  (see ``dir(doc.page)``)
    * any raw tool:     ``doc.tool("form_fill", ...)``

    The document id is filled in for you.  Tool arguments are keyword-only; see
    ``help(doc.compress)`` for exact names.
    """

    def __init__(self, info, sess=None):
        self._s = sess or session()
        self.id = info.id
        self._info = info

    # -- state -------------------------------------------------------------------
    @property
    def info(self):
        """Fresh :class:`DocumentInfo` (permissions, dirty flag, page list, ...)."""
        self._info = self._s.document(self.id)
        return self._info

    @property
    def page_count(self):
        return len(self.info.pages)

    @property
    def pages(self):
        return self.info.pages

    @property
    def dirty(self):
        return self.info.dirty

    @property
    def metadata(self):
        i = self.info
        return {k: getattr(i, k) for k in ("title", "author", "subject", "keywords",
                                           "creator", "producer", "pdf_version")}

    def __repr__(self):
        i = self._info
        return f"<pypdfcraft.Document #{self.id} {i.name!r} {len(i.pages)} pages>"

    def __len__(self):
        return self.page_count

    def _p(self, page):
        n = self.page_count
        if not isinstance(page, int) or not 1 <= page <= n:
            raise IndexError(f"page {page!r} out of range (1..{n}; pages are 1-based)")
        return page - 1

    # -- reading -------------------------------------------------------------------
    @_guard
    def text(self, page=None, sep="\n\n"):
        """Plain text of one page, a list of pages, or the whole document."""
        if isinstance(page, int):
            return self._s.page_plain_text(self.id, self._p(page))
        pages = range(1, self.page_count + 1) if page is None else page
        return sep.join(self._s.page_plain_text(self.id, self._p(p)) for p in pages)

    @_guard
    def blocks(self, page):
        """Paragraphs of a page in reading order (:class:`ReadingBlock`)."""
        return self._s.reading_blocks(self.id, self._p(page))

    @_guard
    def search(self, query, *, pages=None, case_sensitive=False, whole_words=False):
        """All hits as ``[(page_1_based, SearchHit), ...]``."""
        out = []
        for p in (range(1, self.page_count + 1) if pages is None else pages):
            for h in self._s.find_in_page(self.id, self._p(p), query, case_sensitive, whole_words):
                out.append((p, h))
        return out

    @_guard
    def render(self, page=1, scale=2.0, region=None):
        """Draw a page -> :class:`Image`.  ``scale`` = device pixels per PDF point (2.0 ≈ 144 dpi).

        ``region=(x, y, width, height)`` in device pixels at that scale renders just that tile.
        """
        tile = None
        if region is not None:
            tile = native().TileRect(x=int(region[0]), y=int(region[1]),
                                     width=int(region[2]), height=int(region[3]))
        return Image._from_native(self._s.render_page(self.id, self._p(page), float(scale), tile))

    def render_all(self, directory, scale=2.0, pattern="page_{n:04d}.png"):
        """Render every page to PNG files; returns the paths."""
        import os
        os.makedirs(directory, exist_ok=True)
        return [self.render(n, scale).save(os.path.join(directory, pattern.format(n=n)))
                for n in range(1, self.page_count + 1)]

    @_guard
    def outline(self):
        return self._s.outline(self.id)

    @_guard
    def links(self, page):
        return self._s.links(self.id, self._p(page))

    @_guard
    def comments(self):
        return self._s.comments(self.id)

    @_guard
    def attachments(self):
        return self._s.attachments(self.id)

    @_guard
    def save_attachment(self, index, path):
        return self._s.save_attachment(self.id, index, str(path))

    @_guard
    def widgets(self):
        """Visible form-field widgets (see also ``doc.form.fields()``)."""
        return self._s.widgets(self.id)

    @_guard
    def signer_certificate(self, field):
        return self._s.signer_certificate(self.id, field)

    @_guard
    def save_sound(self, page, index, path):
        return self._s.save_sound(self.id, self._p(page), index, str(path))

    @_guard
    def word_at(self, page, x, y, slop=8.0):
        return self._s.word_at(self.id, self._p(page), x, y, slop)

    @_guard
    def text_of(self, text_range):
        return self._s.text_of(self.id, text_range)

    @_guard
    def glyph_count(self, page):
        """Number of selectable glyphs on a page (the index space of the glyph methods)."""
        return self._s.glyph_count(self.id, self._p(page))

    @_guard
    def nearest_glyph(self, page, x, y):
        """Index of the glyph nearest to (x, y) in PDF points, or None for an empty page."""
        return self._s.nearest_glyph(self.id, self._p(page), x, y)

    @_guard
    def glyph_rect(self, page, index):
        """``[x0, y0, x1, y1]`` of one glyph (PDF points, top-left origin)."""
        return self._s.glyph_rect(self.id, self._p(page), index)

    @_guard
    def text_rects(self, text_range):
        """Flat ``[x0, y0, x1, y1, ...]`` highlight rectangles of a TextRange."""
        return self._s.text_rects(self.id, text_range)

    # -- editing (real page text and embedded images; see pypdfcraft.editing) --------------------
    def lines(self, page=None):
        """Text lines with their numbers: ``[{page, line, text, rect, font, size}]``."""
        from . import editing
        return editing.lines(self, page)

    def paragraphs(self, page=None):
        from . import editing
        return editing.paragraphs(self, page)

    def find_text(self, query, limit=None):
        from . import editing
        return editing.find(self, query, limit)

    def edit_line(self, page, line, text, **style):
        """``doc.edit_line(1, 3, "New text")`` - replace line 3 of page 1."""
        from . import editing
        return editing.edit_line(self, page, line, text, **style)

    def edit_paragraph(self, page, paragraph, text=None, **format):
        from . import editing
        return editing.edit_paragraph(self, page, paragraph, text, **format)

    def replace_text(self, old, new, **kw):
        """Replace a phrase in the real text: ``doc.replace_text("2023", "2024")``."""
        from . import editing
        return editing.replace_text(self, old, new, **kw)

    def images(self, page=None):
        """Embedded pictures with their numbers: ``[{page, image, rect, pixels, name, kind}]``."""
        from . import editing
        return editing.images(self, page)

    def edit_image(self, page, image, action, **kw):
        from . import editing
        return editing.edit_image(self, page, image, action, **kw)

    def replace_image(self, page, image, file):
        """``doc.replace_image(1, 2, "new.png")`` - swap picture number 2 on page 1."""
        from . import editing
        return editing.replace_image(self, page, image, file)

    def delete_image(self, page, image=None):
        from . import editing
        return editing.delete_image(self, page, image)

    def save_image(self, page, image, path):
        from . import editing
        return editing.save_image(self, page, image, path)

    # -- tools ---------------------------------------------------------------------
    def tool(self, tool_name, /, **kwargs):
        """Run any engine tool on this document: ``doc.tool("page_rotate", pages=[1], degrees=90)``."""
        return registry().lookup(tool_name, self.id)(**kwargs)

    def __getattr__(self, name):
        if name.startswith("_") or name in ("id",):
            raise AttributeError(name)
        reg = registry()
        if name.endswith("_") and name[:-1] in reg.groups():            # doc.text_ -> group 'text'
            return ToolGroup(reg, name[:-1], self.id)
        return reg.lookup(name, self.id)

    def save(self, path=None, **kwargs):
        """Save (tool ``doc_save``).  Extra keyword arguments are passed to the tool."""
        if path is not None:
            kwargs.setdefault("path", str(path))
        return self.tool("doc_save", **kwargs)

    @_guard
    def close(self, discard_changes=False):
        self._s.close(self.id, discard_changes)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._s.document(self.id).dirty:
                warnings.warn(f"{self!r} closed with unsaved changes (they were discarded); "
                              "call doc.save(path) first", stacklevel=2)
            self._s.close(self.id, True)
        except Exception:                          # noqa: BLE001
            pass
        return False


@_guard
def open(path, password=None):                      # noqa: A001  (mirrors builtins.open on purpose)
    """Open a PDF -> :class:`Document`.  Use as a context manager to close automatically."""
    import os
    s = session()
    path = os.path.abspath(os.path.expanduser(os.fspath(path)))     # the engine requires absolute paths
    if not os.path.isfile(path):
        raise E.OpenError(f"file not found: {path}")
    return Document(s.open(path, password), s)


def document(doc_id):
    """Wrap a document that is already open in the session (e.g. one a tool just created)."""
    s = session()
    return Document(s.document(doc_id), s)


def documents():
    """All documents currently open in the session."""
    return [document(i) for i in session().documents()]
