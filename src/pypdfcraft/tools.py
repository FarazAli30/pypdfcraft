"""Turns the engine's tool table into documented, introspectable Python callables."""
import difflib
import inspect
import json
import keyword
import typing

from .errors import ToolError, UnknownToolError

DOC_KEYS = ("doc", "doc_id", "document", "document_id")
PATH_KEYS = ("path", "out", "out_dir", "folder", "file", "paths", "dir", "directories")


def _abspath(value):
    """Relative file names -> absolute (the engine requires absolute paths)."""
    import os
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    if isinstance(value, str) and value:
        return os.path.abspath(os.path.expanduser(value))
    if isinstance(value, (list, tuple)):
        return [_abspath(v) for v in value]
    return value


# Friendly names -> candidate engine tool names (first one that exists wins).
ALIASES = {
    "merge": ["doc_combine"], "combine": ["doc_combine"],
    "split": ["doc_split"],
    "compress": ["doc_reduce", "doc_optimize", "doc_optimized"],
    "reduce": ["doc_reduce"], "optimize": ["doc_optimize", "doc_optimized", "doc_reduce"],
    "ocr": ["ocr_recognize"],
    "protect": ["doc_protect"], "unprotect": ["doc_unprotect"],
    "watermark": ["doc_watermark"], "header_footer": ["doc_header_footer"],
    "flatten": ["doc_flatten"], "compare": ["doc_compare"],
    "export_text": ["doc_export_text"], "export_images": ["doc_export_images"],
    "export_office": ["doc_export_office"], "to_pdfa": ["pdfa_convert"],
    "rotate": ["page_rotate"], "rotate_pages": ["page_rotate"],
    "delete_pages": ["page_delete"], "move_pages": ["page_move"],
    "extract_pages": ["page_extract"], "reverse_pages": ["page_reverse"],
    "duplicate_pages": ["page_duplicate"], "insert_pages": ["page_insert_file"],
    "replace_page": ["page_replace"], "add_text": ["page_add_text"], "add_image": ["page_add_image"],
    "redact": ["redact_mark"], "apply_redactions": ["redact_apply"],
    "fill_form": ["form_fill"], "sign": ["sign_document"],
    "undo": ["edit_undo"], "redo": ["edit_redo"],
    "save": ["doc_save"], "run_javascript": ["run_javascript", "js_run"],
}

_JSON_TYPES = {"integer": int, "number": float, "string": str, "boolean": bool,
               "array": list, "object": dict}


def _py_name(name):
    return name + "_" if keyword.iskeyword(name) or name in ("self",) else name


def _annotation(schema):
    if not isinstance(schema, dict):
        return typing.Any
    if "enum" in schema and schema["enum"]:
        try:
            return typing.Literal[tuple(schema["enum"])]
        except Exception:
            pass
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    return _JSON_TYPES.get(t, typing.Any)


class Param:
    def __init__(self, name, schema, required):
        self.name, self.schema, self.required = name, schema or {}, required
        self.py_name = _py_name(name)
        self.annotation = _annotation(self.schema)
        self.default = self.schema.get("default", None)
        self.description = self.schema.get("description", "")


def _is_path_param(p):
    """True for string / list-of-string params (not e.g. bookmark `path` index arrays)."""
    sch = p.schema
    ty = sch.get("type")
    if ty == "string":
        return True
    if ty == "array":
        item = (sch.get("items") or {}).get("type")
        return item == "string"
    return False


class Tool:
    """One engine tool. Call with keyword arguments; positional dict also accepted."""

    def __init__(self, session_getter, info, fixed_doc=None):
        self._session = session_getter
        self.info = info
        self.name = info.name
        self.title = info.title
        self.read_only = info.read_only
        self.params = []
        self.free_form = True          # schema unknown -> pass kwargs through unvalidated
        try:
            schema = json.loads(info.input_schema) if info.input_schema else {}
        except ValueError:
            schema = {}
        self.schema = schema
        props = schema.get("properties") if isinstance(schema, dict) else None
        if isinstance(props, dict):
            self.free_form = False
            req = set(schema.get("required", []))
            self.params = [Param(k, v, k in req) for k, v in props.items()]
            self.params.sort(key=lambda p: not p.required)   # stable: required first
        self.doc_param = next((p for p in self.params if p.name in DOC_KEYS), None)
        self._fixed_doc = fixed_doc
        self._refresh_metadata()

    # -- introspection ----------------------------------------------------------
    def _visible(self):
        return [p for p in self.params if not (self._fixed_doc is not None and p is self.doc_param)]

    def _refresh_metadata(self):
        self.__name__ = self.__qualname__ = self.name
        self.__doc__ = self._build_doc()
        try:
            ps = [inspect.Parameter(p.py_name, inspect.Parameter.KEYWORD_ONLY,
                                    default=inspect.Parameter.empty if p.required else p.default,
                                    annotation=p.annotation) for p in self._visible()]
            if self.free_form:
                ps.append(inspect.Parameter("params", inspect.Parameter.VAR_KEYWORD))
            self.__signature__ = inspect.Signature(ps)
        except Exception:
            pass

    def _build_doc(self):
        lines = [f"{self.title or self.name}  [{self.name}]" + ("  (read-only)" if self.read_only else "")]
        if self.info.description:
            lines += ["", self.info.description.strip()]
        vis = self._visible()
        if vis:
            lines += ["", "Parameters (keyword-only):"]
            for p in vis:
                t = getattr(p.annotation, "__name__", str(p.annotation))
                extra = []
                if not p.required:
                    extra.append(f"optional, default={p.default!r}")
                if p.name != p.py_name:
                    extra.append(f"sent as '{p.name}'")
                lines.append(f"  {p.py_name}: {t}" + (f"  ({'; '.join(extra)})" if extra else ""))
                if p.description:
                    lines.append("      " + p.description.strip().replace("\n", "\n      "))
        elif self.free_form:
            lines += ["", "Parameters: schema not described; keyword arguments are sent as JSON."]
        return "\n".join(lines)

    def bind(self, doc_id):
        """Copy of this tool with the document argument fixed."""
        return Tool(self._session, self.info, fixed_doc=doc_id)

    # -- calling -----------------------------------------------------------------
    def _build_params(self, args, kwargs):
        if args:
            if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                kwargs = dict(args[0])
            else:
                raise TypeError(f"{self.name}() takes keyword arguments only "
                                f"(see help(pypdfcraft.{self.name}) for the names)")
        params = {}
        if self.free_form:
            params = {k.rstrip("_") if keyword.iskeyword(k.rstrip("_")) else k: v
                      for k, v in kwargs.items() if v is not None}
        else:
            by_py = {p.py_name: p for p in self.params}
            by_py.update({p.name: p for p in self.params})
            for k, v in kwargs.items():
                p = by_py.get(k)
                if p is None:
                    close = difflib.get_close_matches(k, list(by_py), n=3)
                    hint = f" Did you mean {', '.join(close)}?" if close else ""
                    valid = ", ".join(p.py_name for p in self._visible()) or "(none)"
                    raise TypeError(f"{self.name}() got an unexpected argument '{k}'.{hint} Valid: {valid}")
                if v is not None:
                    params[p.name] = v
        for k in list(params):
            if k in PATH_KEYS:
                p = next((p for p in self.params if p.name == k), None)
                if p is None or _is_path_param(p):
                    params[k] = _abspath(params[k])
        if self.doc_param is not None and self.doc_param.name not in params:
            doc = self._fixed_doc
            if doc is None:
                docs = list(self._session().documents())
                if len(docs) == 1:
                    doc = docs[0]
            if doc is not None:
                params[self.doc_param.name] = doc
        missing = [p.py_name for p in self.params if p.required and p.name not in params]
        if missing:
            raise TypeError(f"{self.name}() missing required argument(s): {', '.join(missing)}")
        return params

    def __call__(self, *args, **kwargs):
        from .core import translate_error
        params = self._build_params(args, kwargs)
        try:
            out = self._session().execute(self.name, json.dumps(params) if params else "")
        except Exception as e:                       # noqa: BLE001
            raise translate_error(e) from None
        try:
            return json.loads(out)
        except (TypeError, ValueError):
            return out

    def __repr__(self):
        return f"<pypdfcraft tool {self.name}{self.__signature__ if hasattr(self, '__signature__') else '()'}>"


class ToolGroup:
    """``pdf.page`` / ``doc.page``: all tools named ``page_*`` as ``.rotate``, ``.delete``, ..."""

    def __init__(self, registry, prefix, doc_id=None, default=None):
        self._registry, self._prefix, self._doc, self._default = registry, prefix, doc_id, default
        if default is not None:                   # e.g. pdf.ocr(...) AND pdf.ocr.status()
            self.__doc__ = default.__doc__
            if hasattr(default, "__signature__"):
                self.__signature__ = default.__signature__

    def __call__(self, *args, **kwargs):
        if self._default is None:
            raise TypeError(f"'{self._prefix}' is a group of tools, not a function: "
                            f"use one of {', '.join(self._names())}")
        return self._default(*args, **kwargs)

    def _names(self):
        p = self._prefix + "_"
        return [n[len(p):] for n in self._registry.names() if n.startswith(p)]

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        tool = self._registry.tools.get(f"{self._prefix}_{item}")
        if tool is None:
            raise UnknownToolError(f"no tool '{self._prefix}_{item}'. Available: {', '.join(self._names())}")
        return tool.bind(self._doc) if self._doc is not None else tool

    def __dir__(self):
        return self._names()

    def __repr__(self):
        return f"<pypdfcraft group '{self._prefix}': {', '.join(self._names())}>"


class Registry:
    def __init__(self, session_getter, infos=None, offline=False):
        self._session_getter = session_getter
        self.offline = offline
        infos = session_getter().tools() if infos is None else infos
        self.tools = {t.name: Tool(session_getter, t) for t in infos}

    def names(self):
        return sorted(self.tools)

    def groups(self):
        return sorted({n.split("_", 1)[0] for n in self.tools if "_" in n})

    def resolve(self, name):
        """Exact tool name, alias, or None."""
        if name in self.tools:
            return self.tools[name]
        for cand in ALIASES.get(name, []):
            if cand in self.tools:
                return self.tools[cand]
        return None

    def lookup(self, name, doc_id=None):
        tool = self.resolve(name)
        if tool is not None and doc_id is not None:
            tool = tool.bind(doc_id)
        if name in self.groups():                   # group name; also callable if it is an alias too
            return ToolGroup(self, name, doc_id, default=tool)
        if tool is not None:
            return tool
        close = difflib.get_close_matches(name, list(self.tools) + list(ALIASES), n=4)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise UnknownToolError(f"'{name}' is not a pdfcraft function or tool.{hint} "
                               f"See pypdfcraft.tools() for the full list.")
