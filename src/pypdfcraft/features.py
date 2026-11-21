"""Curated one-call functions for the rest of the engine: comments, links, bookmarks, signatures,
forms, accessibility, sanitising, Bates numbering, page boxes ...

Same conventions as :mod:`pypdfcraft.api`: file paths in, optional ``out``, ``inplace=True`` to overwrite,
1-based pages, a :class:`~pypdfcraft.results.Result` back.  Anything not listed here is still available
through ``pypdfcraft.apply(src, "<tool>", ...)`` and the generated ``pypdfcraft.oneshot`` module.
"""
from . import api
from .api import _clean, _edit_call, apply, run_tool
from .results import Result

CATALOG = {
    "Pages": ["number_pages", "crop_pages", "insert_blank_page", "insert_pages", "replace_pages",
              "duplicate_pages", "bates"],
    "Comments & links": ["add_comment", "comments", "reply_comment", "delete_comment", "export_data",
                         "import_data", "add_link", "links", "links_from_urls", "remove_links",
                         "add_bookmark", "attach_file", "remove_attachment"],
    "Sign & stamp": ["sign", "signatures", "create_digital_id", "trust_certificates", "add_stamp",
                     "fill_sign"],
    "Forms": ["add_form_field", "delete_form_field", "set_field_properties", "merge_form_data"],
    "Clean-up & checks": ["sanitize", "hidden_info", "remove_marks", "add_background", "set_initial_view",
                          "accessibility_check", "set_alt_text", "verify_pdfa", "print_readiness",
                          "audit_redactions"],
    "Measure & misc": ["word_count", "fonts", "measure", "run_javascript", "enhance_camera_image",
                       "find_document_in_photo"],
}
__all__ = [n for v in CATALOG.values() for n in v]


# ------------------------------------------------------------------------------ pages
def number_pages(src, first=1, last=None, *, prefix=None, start=None, style=None, out=None, inplace=False, password=None):
    """Label pages ``first..last`` (page labels, e.g. i, ii, iii or A-1): style decimal|upper-roman|lower-roman|upper-alpha|lower-alpha."""
    return _edit_call(src, out, "numbered", inplace, password, lambda d: d.tool(
        "page_number", **{"from": first, "to": last or d.page_count}, **_clean(prefix=prefix, start=start, style=style)))


def crop_pages(src, margins=None, rect=None, *, pages=None, box="crop", out=None, inplace=False, password=None):
    """Set a page box (crop/trim/bleed/art/media) by ``margins=[l,t,r,b]`` or ``rect=[x0,y0,x1,y1]`` in points."""
    return _edit_call(src, out, "cropped", inplace, password,
                      lambda d: d.tool("page_set_box", box=box, **_clean(margins=margins, rect=rect, pages=pages)))


def insert_blank_page(src, at, *, width=None, height=None, out=None, inplace=False, password=None):
    """Insert a blank page at position ``at`` (1-based)."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_insert_blank", at=at, **_clean(width=width, height=height)))


def insert_pages(src, file, at, *, pages=None, out=None, inplace=False, password=None):
    """Insert (some) pages of another PDF/image at position ``at``."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_insert_file", at=at, path=api._p(file), **_clean(pages=pages)))


def replace_pages(src, file, pages, *, from_pages=None, out=None, inplace=False, password=None):
    """Replace ``pages`` of ``src`` with pages of ``file``."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_replace", pages=list(pages), path=api._p(file), **_clean(from_pages=from_pages)))


def duplicate_pages(src, pages, *, at=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("page_duplicate", pages=list(pages), **_clean(at=at)))


def bates(files, *, prefix=None, suffix=None, start_number=None, digits=None, dry_run=None, password=None):
    """Bates-number PDFs in one consecutive sequence across all files.

    ``files``: paths (output ``<name>_bates.pdf`` next to each), ``(input, output)`` pairs, or dicts
    ``{"input":..., "output":..., "password":...}``.  Existing outputs are never replaced.
    ``dry_run=True`` only reports the numbers each file would get."""
    items = []
    for f in files:
        if isinstance(f, dict):
            inp, out, pw = f["input"], f.get("output"), f.get("password", password)
        elif isinstance(f, (tuple, list)):
            (inp, out), pw = f, password
        else:
            inp, out, pw = f, None, password
        out = out or api._auto_out(inp, "bates")
        items.append(_clean(input=api._p(inp), output=api._p(out), password=pw))
    return run_tool("doc_bates_multi", files=items,
                    **_clean(prefix=prefix, suffix=suffix, start_number=start_number, digits=digits, dry_run=dry_run))


# ------------------------------------------------------------------------------ comments / links / bookmarks
def add_comment(src, page, type, *, out=None, inplace=False, password=None, **kw):
    """Add an annotation.  ``type`` e.g. 'highlight', 'note', 'text', 'underline', 'strikeout', 'square', 'stamp' ...
    plus ``contents, author, color, rect, find="phrase to mark", at=[x, y] ...`` (see ``help(pypdfcraft.tool('comment_add'))``)."""
    return _edit_call(src, out, "commented", inplace, password, lambda d: d.tool("comment_add", page=page, type=type, **kw))


def comments(src, page=None, *, password=None):
    """List the comments (all pages, or one)."""
    return apply(src, "comment_list", password=password, **_clean(page=page))


def reply_comment(src, text, *, id=None, index=None, page=None, author=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "commented", inplace, password,
                      lambda d: d.tool("comment_reply", text=text, **_clean(id=id, index=index, page=page, author=author)))


def delete_comment(src, *, id=None, index=None, page=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("comment_delete", **_clean(id=id, index=index, page=page)))


def export_data(src, path=None, what="all", *, password=None):
    """Export comments / form data (``what``: all | comments | fields) to an XFDF/FDF file."""
    path = path or api._auto_out(src, what, ".xfdf")
    r = apply(src, "doc_export_data", password=password, path=api._o(path), what=what)
    r["out"] = api._p(path)
    return r


def import_data(src, path, *, out=None, inplace=False, password=None):
    """Import comments / form data from an XFDF/FDF file."""
    return _edit_call(src, out, "imported", inplace, password, lambda d: d.tool("doc_import_data", path=api._p(path)))


def add_link(src, page, rect, *, url=None, to_page=None, out=None, inplace=False, password=None, **style):
    """Link a rectangle ``[x0,y0,x1,y1]`` to a web address (``url=``) or another page (``to_page=``)."""
    if (url is None) == (to_page is None):
        raise ValueError("add_link(): give exactly one of url= or to_page=")
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("link_add", page=page, rect=list(rect), **_clean(url=url, to_page=to_page), **style))


def links(src, *, password=None):
    return apply(src, "link_list", password=password)


def links_from_urls(src, *, out=None, inplace=False, password=None):
    """Turn plain-text URLs in the document into clickable links."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("links_from_urls"))


def remove_links(src, pages=None, *, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("links_remove", **_clean(pages=pages)))


def add_bookmark(src, title, page, *, parent=None, position=None, top=None, left=None, out=None, inplace=False, password=None):
    """Add a bookmark; ``parent`` is the index path of the parent bookmark (e.g. ``[0, 2]``)."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool(
        "bookmark_add", title=title, page=page, **_clean(parent=parent, position=position, top=top, left=left)))


def attach_file(src, path, *, name=None, description=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("attachment_add", path=api._p(path), **_clean(name=name, description=description)))


def remove_attachment(src, name, *, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("attachment_delete", name=name))


# ------------------------------------------------------------------------------ sign / stamp
def sign(src, id, out=None, *, id_password=None, reason=None, location=None, contact=None, field=None,
         page=None, rect=None, certify=None, password=None, **options):
    """Digitally sign with a .p12/.pfx ``id`` -> ``<name>_signed.pdf`` (``rect`` + ``page`` make it visible).

    ``id_password`` is the digital ID's password; ``password`` opens the PDF itself."""
    out = out or api._auto_out(src, "signed")
    args = _clean(reason=reason, location=location, contact=contact, field=field, page=page, rect=rect, certify=certify)
    args.update(options)
    if id_password:
        args["password"] = id_password          # the tool's own `password` argument belongs to the ID
    with api._open(src, password) as d:
        r = d.tool("sign_document", id=api._p(id), out=api._o(out), **args)
    return Result({**(r if isinstance(r, dict) else {"result": r}), "out": api._p(out)})


def signatures(src, *, password=None):
    """List and validate the signatures."""
    return apply(src, "sign_list", password=password)


def create_digital_id(path, name, password, *, email=None, organization=None, unit=None, country=None, years=None, key=None):
    """Create a self-signed digital ID file (.p12) ``path`` (key: rsa2048|rsa3072|rsa4096|p256)."""
    return run_tool("sign_id_create", path=api._o(path), name=name, password=password,
                    **_clean(email=email, organization=organization, unit=unit, country=country, years=years, key=key))


def trust_certificates(paths=None, *, clear=None, password=None):
    return run_tool("sign_trust", **_clean(paths=[api._p(p) for p in paths] if paths else None, clear=clear, password=password))


def add_stamp(src, page, stamp_pdf, *, rect=None, at=None, name=None, author=None, out=None, inplace=False, password=None):
    """Place a custom stamp (first page of ``stamp_pdf``)."""
    return _edit_call(src, out, "stamped", inplace, password, lambda d: d.tool(
        "stamp_custom", page=page, path=api._p(stamp_pdf), **_clean(rect=rect, at=at, name=name, author=author)))


def fill_sign(src, page, type, at, *, text=None, path=None, out=None, inplace=False, password=None, **style):
    """Fill & Sign: ``type`` text|check|cross|dot|line|date|signature ... at ``[x, y]``; ``path`` = signature image."""
    return _edit_call(src, out, "filled", inplace, password, lambda d: d.tool(
        "fill_sign_add", page=page, type=type, at=list(at), **_clean(text=text, path=api._p(path) if path else None), **style))


# ------------------------------------------------------------------------------ forms
def add_form_field(src, page, type, rect, *, name=None, out=None, inplace=False, password=None, **props):
    """Prepare a form: ``type`` text|date|checkbox|radio|combo|list|button|signature ... ``rect=[x0,y0,x1,y1]``."""
    return _edit_call(src, out, "form", inplace, password,
                      lambda d: d.tool("form_add_field", page=page, type=type, rect=list(rect), **_clean(name=name), **props))


def delete_form_field(src, field, *, widget=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("form_delete_field", field=field, **_clean(widget=widget)))


def set_field_properties(src, field=None, *, fields=None, out=None, inplace=False, password=None, **props):
    """Change field properties (align, font_size, max_length, locked, default, caption ...)."""
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("form_set_props", **_clean(field=field, fields=fields), **props))


def merge_form_data(paths, out):
    """Merge several filled-in form data files into one spreadsheet (CSV)."""
    return run_tool("form_merge_data", paths=[api._p(p) for p in paths], path=api._o(out))


# ------------------------------------------------------------------------------ clean-up, checks, view
def sanitize(src, categories=None, *, out=None, inplace=False, password=None):
    """Remove hidden information (metadata, comments, attachments, scripts ...) -> ``<name>_edited.pdf``."""
    return _edit_call(src, out, "sanitized", inplace, password, lambda d: d.tool("doc_remove_hidden", **_clean(categories=categories)))


def hidden_info(src, *, password=None):
    """What :func:`sanitize` would remove."""
    return apply(src, "doc_hidden_info", password=password)


def remove_marks(src, kind, *, out=None, inplace=False, password=None):
    """Remove 'header_footer', 'watermark' or 'background' added earlier."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("doc_remove_marks", kind=kind))


def add_background(src, *, color=None, file=None, opacity=None, pages=None, scale=None, out=None, inplace=False, password=None, **kw):
    """Page background colour (``color='#ffeecc'``) or picture/PDF page (``file=``)."""
    return _edit_call(src, out, "background", inplace, password, lambda d: d.tool(
        "doc_background", **_clean(color=color, file=api._p(file) if file else None, opacity=opacity, pages=pages, scale=scale), **kw))


def set_initial_view(src, *, out=None, inplace=False, password=None, **options):
    """Open-in view: layout, magnification, full_screen, display_title, hide_toolbar, language ..."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("doc_initial_view", **options))


def accessibility_check(src, *, pages=None, rules=None, categories=None, password=None):
    return apply(src, "accessibility_check", password=password, **_clean(pages=pages, rules=rules, categories=categories))


def set_alt_text(src, figure, alt=None, *, decorative=None, out=None, inplace=False, password=None):
    return _edit_call(src, out, "edited", inplace, password,
                      lambda d: d.tool("accessibility_set_alt", figure=figure, **_clean(alt=alt, decorative=decorative)))


def verify_pdfa(src, level=None, *, password=None):
    """Check PDF/A conformance (level '2b' or '3b')."""
    return apply(src, "pdfa_verify", password=password, **_clean(level=level))


def print_readiness(src, *, password=None):
    return apply(src, "print_readiness", password=password)


def audit_redactions(src, *, password=None):
    """Find 'faux' redactions (black boxes with the text still underneath)."""
    return apply(src, "doc_audit_redactions", password=password)


# ------------------------------------------------------------------------------ measure & misc
def word_count(src, *, pages=None, exclude_code=None, exclude_images=None, exclude_tables=None, password=None):
    return apply(src, "text_word_count", password=password,
                 **_clean(pages=pages, exclude_code=exclude_code, exclude_images=exclude_images, exclude_tables=exclude_tables))


def fonts(src, page, *, password=None):
    """Fonts used on a page."""
    return apply(src, "text_fonts", password=password, page=page)


def measure(src, page, points, type="distance", *, password=None):
    """Distance / perimeter / area between ``points=[[x,y], ...]`` using the page's measurement scale."""
    return apply(src, "measure_info", password=password, page=page, points=[list(p) for p in points], type=type)


def run_javascript(src, script, *, field=None, out=None, inplace=False, password=None):
    """Run a script in the document's JavaScript engine (form calculations, ...)."""
    return _edit_call(src, out, "edited", inplace, password, lambda d: d.tool("js_run", script=script, **_clean(field=field)))


def enhance_camera_image(src, page, mode="colour", *, corners=None, level=None, out=None, inplace=False, password=None):
    """Clean up a photographed page (mode: original|colour|greyscale|bw)."""
    return _edit_call(src, out, "enhanced", inplace, password,
                      lambda d: d.tool("page_enhance_camera", page=page, mode=mode, **_clean(corners=corners, level=level)))


def find_document_in_photo(path):
    """Detect the page corners of a document in a photo."""
    return run_tool("photo_find_document", path=api._p(path))
