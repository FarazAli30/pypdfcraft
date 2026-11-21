"""Text and image editing on an open Document (what the Android app's "Edit PDF" does).

All page numbers, line numbers, paragraph numbers and image numbers are 1-based, exactly as the
listings return them.  Coordinates are PDF points from the TOP-LEFT of the page.
"""
import re

from .errors import PdfCraftError, ToolError
from .results import AttrDict


class TextNotFound(PdfCraftError):
    """replace_text() found nothing to replace."""


def _pages(doc, page):
    if page is None:
        return list(range(1, doc.page_count + 1))
    return [page] if isinstance(page, int) else list(page)


# ------------------------------------------------------------------ listings
def lines(doc, page=None):
    """Every text line: ``page, line, text, rect, font, size``."""
    out = []
    for p in _pages(doc, page):
        for l in doc.tool("text_lines", page=p).get("lines", []):
            out.append(AttrDict({**l, "page": p}))
    return out


def paragraphs(doc, page=None):
    """Every paragraph: ``page, paragraph, text, rect, font, size, bold, italic, color``."""
    out = []
    for p in _pages(doc, page):
        for b in doc.tool("text_paragraphs", page=p).get("paragraphs", []):
            out.append(AttrDict({**b, "page": p}))
    return out


def find(doc, query, limit=None):
    """Where a phrase occurs: ``[{page, rect...}]`` (tool ``text_find``)."""
    r = doc.tool("text_find", query=query, **({"limit": limit} if limit else {}))
    return r.get("matches", r) if isinstance(r, dict) else r


# ------------------------------------------------------------------ text edits
def edit_line(doc, page, line, text, **style):
    """Replace the text of line number ``line`` on ``page`` (position, size and colour are kept)."""
    n = len(doc.tool("text_lines", page=page).get("lines", []))
    if not 1 <= line <= n:
        raise IndexError(f"page {page} has {n} lines; line {line} does not exist (see show_lines)")
    return doc.tool("text_edit", page=page, line=line, text=text, **style)


def edit_paragraph(doc, page, paragraph, text=None, **format):
    """Replace a paragraph's text (re-wrapped to its width) and/or restyle or move it.

    ``format``: font ('helvetica'|'times'|'courier'), bold, italic, size, color '#rrggbb',
    align, underline, line_spacing, char_spacing, scale, dx, dy, width."""
    args = dict(format)
    if text is not None:
        args["text"] = text
    return doc.tool("text_edit", page=page, paragraph=paragraph, **args)


def replace_text(doc, old, new, *, pages=None, case_sensitive=False, first_only=False, mode="auto"):
    """Replace ``old`` by ``new`` in the real page text.

    ``mode``: 'line' edits single lines, 'paragraph' re-wraps whole paragraphs (use for phrases that
    break across lines), 'auto' (default) uses lines and falls back to paragraphs per page.
    Returns ``AttrDict(replaced=<n edits>, edits=[{page, where, before, after}])``."""
    if not old:
        raise ValueError("replace_text(): 'old' must not be empty")
    pat = re.compile(re.escape(old), 0 if case_sensitive else re.IGNORECASE)
    edits = []

    def sub(s):
        return pat.sub(lambda m: new, s)

    for p in _pages(doc, pages):
        done = False
        if mode in ("auto", "line"):
            for l in doc.tool("text_lines", page=p).get("lines", []):
                if pat.search(l["text"]):
                    after = sub(l["text"])
                    doc.tool("text_edit", page=p, line=l["line"], text=after)
                    edits.append({"page": p, "where": f"line {l['line']}", "before": l["text"], "after": after})
                    done = True
                    if first_only:
                        return AttrDict(replaced=len(edits), edits=edits)
        if not done and mode in ("auto", "paragraph"):
            listing = doc.tool("text_paragraphs", page=p).get("paragraphs", [])
            todo = [b for b in listing if pat.search(b["text"])]
            for b in sorted(todo, key=lambda b: -b["paragraph"]):        # bottom-up keeps numbers valid
                after = sub(b["text"])
                try:
                    doc.tool("text_edit", page=p, paragraph=b["paragraph"], text=after)
                except ToolError as e:
                    if "list the page again" not in str(e) and "stale" not in str(e).lower():
                        raise
                    fresh = next((x for x in doc.tool("text_paragraphs", page=p).get("paragraphs", [])
                                  if x["text"] == b["text"]), None)
                    if fresh is None:
                        continue
                    doc.tool("text_edit", page=p, paragraph=fresh["paragraph"], text=after)
                edits.append({"page": p, "where": f"paragraph {b['paragraph']}", "before": b["text"], "after": after})
                if first_only:
                    return AttrDict(replaced=len(edits), edits=edits)
    return AttrDict(replaced=len(edits), edits=edits)


# ------------------------------------------------------------------ images
def images(doc, page=None):
    """Raster images / artwork: ``page, image (number), rect, visible_rect, pixels, name, kind``."""
    out = []
    for p in _pages(doc, page):
        for im in doc.tool("page_images", page=p).get("images", []):
            out.append(AttrDict({**im, "page": p}))
    return out


def _pick(doc, page, image):
    if image is not None:
        return image
    found = doc.tool("page_images", page=page).get("images", [])
    if len(found) == 1:
        return found[0]["image"]
    raise ValueError(f"page {page} has {len(found)} images: say which one (see show_images)")


def edit_image(doc, page, image, action, **kw):
    """Any image action: move/crop (rect=[x0,y0,x1,y1]), rotate (quarters), rotate_by (degrees),
    flip_horizontal, flip_vertical, replace (path=), delete, bring_to_front, send_to_back, ..."""
    return doc.tool("image_edit", page=page, image=_pick(doc, page, image), action=action, **kw)


def replace_image(doc, page, image, file):
    """Swap an embedded picture for another image file (PNG, JPEG, ...), keeping its placement."""
    return edit_image(doc, page, image, "replace", path=str(file))


def delete_image(doc, page, image=None):
    return edit_image(doc, page, image, "delete")


def save_image(doc, page, image, path):
    """Write one embedded picture to ``path`` (JPEG unchanged, others PNG)."""
    return doc.tool("image_save", page=page, image=_pick(doc, page, image), path=str(path))
