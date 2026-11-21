"""pypdfcraft - Python library for the PdfCraft PDF engine (read, edit, convert, sign, OCR ...).

    import pypdfcraft as pdf

    pdf.help()                                      # cheat sheet of everything
    pdf.compress("big.pdf")                         # -> big_compressed.pdf (output path is optional)
    pdf.replace_text("a.pdf", "2023", "2024")       # edit real page text -> a_edited.pdf
    pdf.replace_image("a.pdf", 1, 2, "logo.png")    # swap picture 2 on page 1
    pdf.convert("a.pdf", "docx")                    # PDF -> Word (also xlsx/pptx/html/md/txt/png/jpg)

    with pdf.open("in.pdf") as doc:                 # or work on an open document
        print(doc.text(1)); doc.render(1).save("p1.png")
        doc.page.rotate(degrees=90)                 # every engine tool: doc.<tool>(...) / doc.<group>.<tool>(...)
        doc.save("out.pdf")

    pdf.tools()                                     # all engine tools; pdf.apply("a.pdf", "<tool>", ...) runs any

The engine is the open-source PdfCraft Rust library (MIT OR Apache-2.0) by the ArtCraft Team and the
PdfCraft contributors; this package is its Python binding.  See the project README for credits.
"""
from . import api as _api
from . import errors
from . import features as _features
from ._version import ENGINE_VERSION, __version__
from .api import *  # noqa: F401,F403  (compress, merge, split, ocr, apply ...)
from .core import (  # noqa: A004
    Document,
    diagnose,
    digital_id_info,
    document,
    documents,
    engine_version,
    init_logging,
    open,
    release_memory,
    session,
    thumbnail,
    use_session,
)
from .core import native as _native
from .core import registry as _registry
from .errors import *  # noqa: F401,F403
from .features import *  # noqa: F401,F403  (comments, links, signing, forms, bates ...)
from .helpers import help, search  # noqa: A004
from .image import Image
from .models import install_models
from .models import set_dir as set_models_dir
from .results import AttrDict, Result
from .tools import ALIASES, Tool, ToolGroup


def tools(group=None):
    """Dict ``name -> Tool`` (optionally only tools whose name starts with ``group_``)."""
    t = _registry().tools
    return {k: v for k, v in sorted(t.items()) if group is None or k.startswith(group + "_")}


def tool(name):
    """Get one raw (document-bound) tool by name or friendly alias."""
    return _registry().lookup(name)


def call(name, /, **kwargs):
    """Run a raw tool by name with explicit arguments: ``pdf.call("doc_split", doc=1, every=2)``."""
    return tool(name)(**kwargs)


def describe(name):
    """Print the documentation of a tool / group."""
    t = tool(name)
    print(t.__doc__ if isinstance(t, Tool) else repr(t))


def __getattr__(name):
    """``pdf.<tool_name>("file.pdf", ...)`` - the generated one-call form of every engine tool."""
    if name.startswith("_"):
        raise AttributeError(name)
    import importlib
    oneshot = importlib.import_module(f"{__name__}.oneshot")      # (not `from . import`: that re-enters here)
    if name == "oneshot":
        return oneshot
    fn = getattr(oneshot, name, None)
    if callable(fn):
        return fn
    return _registry().lookup(name)


def __dir__():
    base = [k for k in globals() if not k.startswith("_")]
    try:
        import importlib
        oneshot = importlib.import_module(f"{__name__}.oneshot")
        return sorted(set(base) | set(oneshot.__all__))
    except Exception:                                  # noqa: BLE001
        return sorted(base)
