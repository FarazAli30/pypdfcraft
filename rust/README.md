# rust/ - the PdfCraft engine

This directory is the Rust workspace of **PdfCraft**, (c) ArtCraft Team and the PdfCraft contributors,
MIT OR Apache-2.0 - <https://github.com/artcraft-android/pdfcraft-android> (a part of
<https://github.com/storytold/pdfcraft>). It is the engine that pypdfcraft wraps.

| path | what |
|---|---|
| `crates/*` | engine crates: parsing (`cos`), rendering, editing, forms, annotations, export, OCR, signing, redaction ... |
| `crates/automation` | the 186-tool table (`tools.rs`) and its dispatcher - what `pypdfcraft.tools()` exposes |
| `apps/pdfcraft-android` | the UniFFI library crate (`MobileSession`, `file_thumbnail`, ...), built as a `cdylib`; its `bindgen/` is the UniFFI bindgen pinned to the same version |
| `vendor/` | the few third-party crates the workspace patches locally (`[patch.crates-io]`), with their licences |
| `assets/fonts` | fonts embedded at build time (OFL licences included) |

## Differences from upstream
Only the workspace manifest and lockfile are changed, by `scripts/sync_upstream.py`:
the desktop-UI-only `[patch]` git entries (egui, winit) and workspace dependencies (`craft-ui`, ...) are removed
because the library does not use them, and the `targets` line of `rust-toolchain.toml` is dropped (CI installs the
targets it needs). No Rust source file is modified. The Android Kotlin app, docs and CI of upstream are not included.

Build: `cargo build --release --locked -p pdfcraft-android` (see ../docs/building.md).
