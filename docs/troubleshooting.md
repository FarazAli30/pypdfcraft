# Troubleshooting

Start with `python -m pypdfcraft diagnose` - it shows the Python/CPU, which `pypdfcraft` was imported, where the
engine library was found and whether it loads.

| Symptom | Cause / fix |
|---|---|
| `NativeLibraryError: Could not load the PdfCraft engine` | No wheel for your platform, or the library was moved. `pip install pypdfcraft` on a supported OS/CPU, or set `PDFCRAFT_LIB`. 32-bit Python on a 64-bit OS needs a 32-bit library. |
| `module 'pypdfcraft' has no attribute 'open'` / `help()` lists only your own files | Python imported a **folder** called `pypdfcraft` that is not the package (e.g. the unzipped outer folder). Rename the outer folder or run from a different directory; `import pypdfcraft; print(pypdfcraft.__file__)` must end in `pypdfcraft/__init__.py`. |
| `OSError: ... failed to map segment` / `cannot open shared object file` on Android | Shared storage (`/sdcard`, `/storage/emulated/0`) is mounted `noexec`. pypdfcraft copies the library to private storage automatically; make sure `$HOME` (or `$PYPDFCRAFT_CACHE`) is writable. |
| `contract version mismatch` / `checksum mismatch` at import | The library does not belong to the installed bindings. Use the library from the same wheel, or regenerate `_bindings.py` (`scripts/gen_bindings.py`). |
| `OpenError: file not found` | Paths are made absolute from the *current directory*; check `os.getcwd()`. |
| `PasswordRequired` / `WrongPassword` | Pass `password="..."` (every function accepts it for the source file). |
| `compress()` result is the same size | The engine writes nothing when it cannot shrink a file; `r.written` is False and `out` is a copy of the input. Try `preset="mobile"` or other optimizer options. |
| `OcrModelsMissing` | `pip install "pypdfcraft[ocr]"` or `pypdfcraft.install_models()`. |
| `TextNotFound` | The text is not in the page's text layer (scanned page: run `ocr()`), or the phrase wraps across lines (`mode="paragraph"`). |
| Text edit refused for a character | The font cannot represent it and no standard font covers that script; use a different text or font. |
| `UserWarning: closed with unsaved changes` | You edited inside `with pdf.open(...)` without `doc.save(path)`; use `pdf.edit(...)` which saves for you. |
| Windows: `ImportError`/DLL load failed | Install the 64-bit Python wheel matching your Python's CPU (`win_amd64` vs `win_arm64`). |
