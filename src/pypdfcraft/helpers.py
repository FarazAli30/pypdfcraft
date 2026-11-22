"""pypdfcraft.help() / pypdfcraft.search(): a built-in cheat sheet."""
import inspect

from . import api, features, speech


def _lookup(name):
    return getattr(api, name, None) or getattr(features, name, None) or getattr(speech, name, None)


def _all_names():
    return (set(api.__all__) | set(features.__all__) | set(speech.CATALOG["Read aloud"])) - {"CATALOG"}


def _first(fn):
    doc = inspect.getdoc(fn) or ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def _registry_or_none():
    try:
        from .core import registry
        return registry()
    except Exception:                                    # noqa: BLE001
        return None


def search(text):
    """Find functions and engine tools by keyword -> ``[(kind, name, summary)]``."""
    q = text.lower()
    hits = []
    for name in sorted(_all_names()):
        fn = _lookup(name)
        if callable(fn) and not isinstance(fn, type) and (q in name or q in (inspect.getdoc(fn) or "").lower()):
            hits.append(("function", name, _first(fn)))
    reg = _registry_or_none()
    if reg:
        for n, t in sorted(reg.tools.items()):
            if q in n or q in (t.title or "").lower() or q in (t.info.description or "").lower():
                hits.append(("tool", n, t.title))
    return hits


def help(topic=None):                                   # noqa: A001
    """``help()`` = cheat sheet of everything; ``help("compress")`` = details; ``help("watermark")`` = search."""
    if topic is None:
        print("pypdfcraft - everything takes a PDF path; output paths are optional (a new *_<what>.pdf is made"
              "\nnext to the source, never overwriting; add inplace=True to overwrite). Pages/lines are 1-based.\n")
        for cat, names in {**api.CATALOG, **{f"{k} (more)": v for k, v in features.CATALOG.items()}, **speech.CATALOG}.items():
            print(f"{cat}")
            for n in names:
                fn = _lookup(n)
                if n == "install_models":
                    print(f"  {n:18s} download the OCR models once")
                elif fn:
                    print(f"  {n:18s} {_first(fn)}")
            print()
        print('More: help("name") for details | search("word") to find anything | tools() lists all engine tools; apply("a.pdf", "<tool>", ...) runs any of them\n'
              '      with pypdfcraft.open("a.pdf") as doc: doc.<tool>(...) for full control.')
        return
    fn = _lookup(topic)
    if callable(fn):
        try:
            print(f"{topic}{inspect.signature(fn)}\n")
        except (TypeError, ValueError):
            pass
        print(inspect.getdoc(fn))
        return
    reg = _registry_or_none()
    if reg and reg.resolve(topic):
        print(reg.resolve(topic).__doc__)
        return
    hits = search(topic)
    if not hits:
        print(f"nothing found for {topic!r}")
    for kind, name, summary in hits[:25]:
        print(f"  {kind:8s} {name:28s} {summary}")
