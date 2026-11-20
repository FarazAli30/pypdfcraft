# Contributing

Thanks for helping! The short version:

```bash
git clone https://github.com/FarazAli30/pypdfcraft && cd pypdfcraft
pip install -e ".[dev]"
pytest -m "not engine"            # unit tests, no native library needed
```

## Running the real-engine tests
Build the engine (`cd rust && cargo build --release -p pdfcraft-android`, see [docs/building.md](docs/building.md)), then
`export PDFCRAFT_LIB=$PWD/rust/target/release/libpdfcraft_android.so && pytest`.
`tests/test_engine.py` creates its own PDFs with the engine, so no fixtures are needed. OCR tests run when the models are
installed (`pip install pypdfcraft-ocr-models` or `PDFCRAFT_MODELS=...`).

## Where things live
* `src/pypdfcraft/api.py`, `features.py`, `editing.py` - hand-written API. Conventions: path in, optional `out`,
  `inplace`, `password`, 1-based pages, return a `Result`, add a docstring (first line = summary used by `pdf.help()`).
* `_bindings.py`, `oneshot.py`, `data/tools_catalog.json`, `docs/api.md|tools.md|coverage.md` - **generated**; never edit
  by hand, run the scripts in `scripts/` (CI checks they are current).
* `rust/` - upstream PdfCraft. Changes to the engine belong upstream
  (<https://github.com/artcraft-android/pdfcraft-android>); here we only sync (`scripts/sync_upstream.py`).

## Style
`ruff check .` must pass (CI). Keep the package dependency-free (optional extras only).

## Pull requests
Describe the change, add/adjust tests, update `CHANGELOG.md`. By contributing you agree that your contribution is
licensed under MIT OR Apache-2.0 like the rest of the project.
