# Changelog

All notable changes. Format: [Keep a Changelog](https://keepachangelog.com/); versions follow [SemVer](https://semver.org/).
The `Engine` line is the PdfCraft Rust engine version the wheels are built from.

## [0.4.0] - 2026-11-19
Engine: PdfCraft 0.18.1

### Added
* Full repository: Rust workspace (`rust/`), Python package (`src/pypdfcraft`), build scripts, tests, docs.
* GitHub Actions: CI, cross-platform wheel build (Linux glibc/musl x86_64+aarch64, macOS x86_64+arm64,
  Windows x64+ARM64, Android arm64-v8a/armeabi-v7a/x86_64/x86), release to PyPI + GitHub Releases, docs site.
* Optional output paths with automatic, never-overwriting names; `inplace=True`.
* `apply()` / `run_tool()` and the generated `pypdfcraft.<tool>()` one-shot functions: all 186 engine tools in one-call form.
* Curated functions for comments, links, bookmarks, attachments, signing, digital IDs, stamps, Fill & Sign, form fields,
  page boxes / insertion / replacement / numbering, Bates numbering, sanitising, backgrounds, initial view,
  accessibility, PDF/A verification, measuring, JavaScript, camera clean-up.
* Native text-geometry methods on `Document`: `glyph_count`, `nearest_glyph`, `glyph_rect`, `text_rects`.
* **Read Aloud**: `read_aloud()`, `to_audio()`, `reading_text()`, `voices()` and the `ReadAloud` controller (play / stop / pause / resume /
  forward / back, paragraph and word callbacks with page rectangles), using the engine's reading-order paragraphs and the
  system speech engine (espeak-ng, macOS `say`, Windows SAPI, pyttsx3, Termux, plyer); `python -m pypdfcraft read|voices`.
* `pypdfcraft-ocr-models` wheel (`pip install pypdfcraft[ocr]`); checksum-verified model download.
* `python -m pypdfcraft diagnose | tools | describe | run | catalog | stubs | install-models`.


### Changed
* Package renamed `pypdfcraft`; `src/` layout; the native library is found by `_loader` on all platforms
  (`_lib/` in the wheel, `PDFCRAFT_LIB`, private-storage copy on Android).
* Image conversion folders are named by format (`name_png/`, `name_jpg/`).

### Fixed
* OCR-models wheel build: the CC-BY-SA licence text now ships inside the package (the creativecommons.org site answered
  `403 Forbidden` to CI runners) and downloads send a User-Agent.
* Packaging: removed the `License ::` classifiers that clash with the PEP 639 `license` expression (setuptools refused to build,
  so `pip install -e .` failed in CI); wheel `Requires-Dist` markers are now valid PEP 508 (`twine check` passes).
* CI: Linux jobs pinned to `ubuntu-24.04` (`ubuntu-latest` has no Python 3.9), `macos-latest`, `cargo ndk --platform 24`,
  portable smoke-test venv, grouped Dependabot updates; unit tests no longer assume `/` path separators.
* Engine `open` requires absolute paths: every path is made absolute and output folders are created.
* `Document.tool(name=...)` no longer clashes with a tool argument called `name`.
