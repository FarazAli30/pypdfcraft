## pypdfcraft - fast, fully offline PDF toolkit for Python

Edit the **real text and pictures** of a PDF, compress, merge, split, convert to and from Word / Excel / PowerPoint /
images, OCR scans, sign, redact, fill forms, add comments and **read documents aloud** - from one Python package, with no
Java, no web service and no system libraries. The engine is the open-source [PdfCraft](https://github.com/artcraft-android/pdfcraft-android)
Rust library (MIT OR Apache-2.0); it ships inside the wheel.

```python
import pypdfcraft as pdf

pdf.compress("big.pdf")                           # -> big_compressed.pdf (output path is optional)
pdf.replace_text("contract.pdf", "2023", "2024")  # edits the real page text
pdf.replace_image("a.pdf", page=1, image=2, file="logo.png")
pdf.convert("report.pdf", "docx")                 # also xlsx, pptx, html, md, txt, png, jpg
pdf.ocr("scan.pdf")                               # searchable PDF   (pip install "pypdfcraft[ocr]")
pdf.read_aloud("book.pdf")                        # speak it with the system voice; pdf.to_audio() -> .wav
```

### Install

```
pip install pypdfcraft              # Windows, macOS, Linux (glibc + musl), Android
pip install "pypdfcraft[ocr]"       # + OCR models
pip install "pypdfcraft[speech]"    # + pyttsx3 speech engine (optional)
```
**Termux / Pydroid 3:** download the **`linux_aarch64`** (64-bit phones) or `linux_armv7l` wheel from the assets below and `pip install` the file.
Do not use the `android_24_*` wheels there - those are for CPython builds that report `sys.platform == "android"` (official Android CPython, Chaquopy, BeeWare).
Check your setup any time with `python -m pypdfcraft diagnose`.

### Highlights
* **One-call functions, optional output paths** - a new `name_<what>.pdf` is created next to the source and nothing is ever overwritten.
* **All 186 engine tools** reachable: `pdf.apply("a.pdf", "<tool>", ...)`, typed one-shot functions, or `doc.<tool>()` on an open document.
* **Text and image editing** like the PdfCraft Android app: `show_lines`, `edit_line`, `replace_text`, `replace_image`, `move_image` ...
* **Sign, comment, forms, Bates numbering, sanitize, PDF/A check, accessibility, measuring**, and more ([function reference](https://FarazAli30.github.io/pypdfcraft/api/)).
* **Read aloud** with word rectangles for highlighting; **OCR** with models shipped as a separate wheel.
* Render pages to PNG / NumPy / Pillow - handy for building a viewer (Tkinter, Qt).
* Wheels are `py3-none-<platform>`: **one wheel per OS/CPU that works on every Python >= 3.9**.

### Platforms
| OS | CPU | tested in CI |
|---|---|---|
| Linux (glibc 2.28+) | x86_64 / aarch64 | x86_64 ran the full engine tests |
| Linux (musl / Alpine) | x86_64 / aarch64 | built only |
| macOS 10.13+ / 11+ | Intel / Apple Silicon | Apple Silicon ran the full engine tests |
| Windows | x64 / ARM64 | x64 ran the full engine tests |
| Android | arm64-v8a, armeabi-v7a, x86_64, x86 | built only (also as `linux_*` for Termux/Pydroid) |

### Notes
* This is a **beta**: the API may still change before 1.0. Please report problems at <https://github.com/FarazAli30/pypdfcraft/issues> with the output of `python -m pypdfcraft diagnose`.
* Scanned pages have no text: run `ocr()` before editing, searching or reading aloud.
* Independent community binding - not an official PdfCraft product. Engine (c) ArtCraft Team and the PdfCraft contributors; Python package (c) Faraz Ali; both MIT OR Apache-2.0. OCR models: ocrs-models, CC-BY-SA-4.0.
* Verify downloads with `SHA256SUMS.txt`.
