# pypdfcraft

[![CI](https://github.com/FarazAli30/pypdfcraft/actions/workflows/ci.yml/badge.svg)](https://github.com/FarazAli30/pypdfcraft/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pypdfcraft.svg)](https://pypi.org/project/pypdfcraft/)
[![Python](https://img.shields.io/pypi/pyversions/pypdfcraft.svg)](https://pypi.org/project/pypdfcraft/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](LICENSE-MIT)

**A fast, fully offline Python library for working with PDFs** - edit real text and embedded images,
compress, merge, split, convert to/from Word / Excel / PowerPoint / images, OCR, sign, redact, fill forms,
comment and more. No Java, no external services, no system packages: the engine is the open-source
[PdfCraft](https://github.com/artcraft-android/pdfcraft-android) Rust library, shipped inside the wheel.

> **Independent community binding.** pypdfcraft is maintained by Faraz Ali and is **not** an official product of the
> PdfCraft project. The PDF engine it wraps is [PdfCraft](https://github.com/artcraft-android/pdfcraft-android), an
> open-source Rust library by the ArtCraft Team and the PdfCraft contributors (MIT OR Apache-2.0).

```python
import pypdfcraft as pdf

pdf.compress("big.pdf")                          # -> big_compressed.pdf   (output path is optional)
pdf.replace_text("contract.pdf", "2023", "2024") # edits the real page text
pdf.replace_image("a.pdf", page=1, image=2, file="logo.png")
pdf.convert("report.pdf", "docx")                # PDF -> Word  (xlsx, pptx, html, md, txt, png, jpg ...)
pdf.merge(["a.pdf", "b.pdf"]);  pdf.split("book.pdf", every=10)
pdf.ocr("scan.pdf")                              # searchable PDF (pip install "pypdfcraft[ocr]")
```

Owner / maintainer: **Faraz Ali**.  Engine: **PdfCraft** by the *ArtCraft Team and the PdfCraft contributors*.

## Install

```bash
pip install pypdfcraft              # Windows, macOS, Linux (glibc + musl), Android
pip install "pypdfcraft[ocr]"       # + OCR models (CC-BY-SA, ~12 MB)
pip install "pypdfcraft[speech]"    # + pyttsx3 speech engine (exact word events)
pip install "pypdfcraft[all]"       # + numpy / Pillow helpers
```

Pre-built wheels (`py3-none-<platform>`, any Python >= 3.9):

| OS | CPU | wheel tag |
|---|---|---|
| Linux (glibc >= 2.28) | x86_64, aarch64 | `manylinux_2_28_*` |
| Linux (Alpine / musl) | x86_64, aarch64 | `musllinux_1_2_*` |
| macOS 10.13+ / 11+ | Intel / Apple Silicon | `macosx_10_13_x86_64`, `macosx_11_0_arm64` |
| Windows | x64, ARM64 | `win_amd64`, `win_arm64` |
| Android (CPython 3.13+, Chaquopy, BeeWare) | arm64-v8a, armeabi-v7a, x86_64, x86 | `android_24_*` |
| Termux / Pydroid | aarch64, armv7 | `linux_aarch64`, `linux_armv7l` - download from the GitHub Release |

On Termux / Pydroid, `pip install` cannot see the Android wheel on PyPI, and the `android_24_*` wheels are **not** for
them (their pip says *"not a supported wheel on this platform"*); download the matching
`...-py3-none-linux_aarch64.whl` from the [Releases](https://github.com/FarazAli30/pypdfcraft/releases) page and
`pip install` that file.

## What you get

* **One-call functions** with optional output paths: `compress, merge, split, extract_pages, delete_pages,
  rotate, watermark, header_footer, protect, unprotect, redact, flatten, fill_form, ocr, convert, to_images ...`
* **Real text editing** like the Android app: `show_lines`, `edit_line`, `replace_text`, `edit_paragraph`,
  `interactive_edit`; **image editing**: `replace_image`, `delete_image`, `move_image`, `extract_images`.
* **Sign / comment / forms / accessibility / Bates / sanitize / PDF-A ...** - see the
  [function reference](docs/api.md); **all 186 engine tools** are reachable (`pdf.apply("a.pdf", "<tool>", ...)`,
  typed one-shot functions, or `doc.<tool>(...)` on an open document) - [coverage table](docs/coverage.md).
* **Rendering**: `doc.render(page, scale, region)` -> RGBA / PNG / NumPy / Pillow (handy for a Tkinter or Qt viewer).
* **Read aloud**: `pdf.read_aloud("book.pdf", rate=1.2)` speaks the text in reading order with your system's voice (paragraph and
  word callbacks for highlighting), `pdf.to_audio("book.pdf")` writes a `.wav` - fully offline ([guide](docs/read-aloud.md)).
* `pdf.help()` prints a cheat sheet; `pdf.search("watermark")` finds anything.

```python
with pdf.open("in.pdf") as doc:                  # full control on an open document
    doc.page.rotate(degrees=90, pages=[1])
    doc.replace_text("Draft", "Final")
    doc.render(1, scale=2).save("p1.png")
    doc.save("out.pdf")
```

## Documentation

[Quickstart](docs/quickstart.md) · [Cookbook](docs/cookbook.md) · [Editing text & images](docs/editing.md) · [Read aloud](docs/read-aloud.md) · [Read aloud](docs/read-aloud.md) ·
[Function reference](docs/api.md) · [All 186 tools](docs/tools.md) · [Feature coverage](docs/coverage.md) ·
[Architecture](docs/architecture.md) · [Building from source](docs/building.md) · [Releasing](docs/releasing.md) ·
[Troubleshooting](docs/troubleshooting.md)

## Repository layout

```
src/pypdfcraft/      the Python package (loader, high-level API, generated bindings)
rust/                the PdfCraft Rust workspace (engine crates + the UniFFI library `pdfcraft-android`)
packages/ocr-models/ the optional OCR-models wheel
scripts/             bindings / docs / wheel builders
tests/               unit tests (fake engine) + engine tests (real library)
.github/workflows/   CI, cross-platform wheel build, release, docs
```

## Building from source

```bash
cd rust && cargo build --release -p pdfcraft-android          # the engine library
python scripts/gen_bindings.py rust/target/release/libpdfcraft_android.so
python scripts/build_wheel.py --lib rust/target/release/libpdfcraft_android.so --tag manylinux_2_28_x86_64
```
Details for every platform: [docs/building.md](docs/building.md).

## License and credits

The Python package is **MIT OR Apache-2.0** (c) Faraz Ali. The engine in `rust/` is PdfCraft, (c) ArtCraft Team and
the PdfCraft contributors, also **MIT OR Apache-2.0**; third-party material keeps its own licences
([NOTICE](NOTICE), [rust/ATTRIBUTION.md](rust/ATTRIBUTION.md)). OCR models: ocrs-models, CC-BY-SA-4.0 (separate wheel).
See [AUTHORS.md](AUTHORS.md).
