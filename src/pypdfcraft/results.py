"""Small result containers: dicts with attribute access."""


class AttrDict(dict):
    """A dict whose keys are also attributes (``line.text``, ``line["text"]``)."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None

    def __repr__(self):
        body = ", ".join(f"{k}={v!r}" for k, v in list(self.items())[:8])
        return f"{type(self).__name__}({body}{', ...' if len(self) > 8 else ''})"


class Result(AttrDict):
    """What the one-call functions return.  ``result.out`` is the file/folder that was written."""

    @property
    def out(self):
        """The file or folder that was written (``None`` for read-only calls)."""
        return self.get("out")

    def __repr__(self):
        shown = {k: v for k, v in self.items() if k != "out" and not isinstance(v, (dict, list))}
        extra = ", ".join(f"{k}={v!r}" for k, v in list(shown.items())[:5])
        return f"<Result out={self.get('out')!r}{', ' + extra if extra else ''}>"
