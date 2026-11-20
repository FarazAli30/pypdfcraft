# Authors and credits

## pypdfcraft (this repository)
* **Faraz Ali** - owner and maintainer: Python package, build scripts, CI/CD, documentation.

## PdfCraft engine (`rust/`)
The PDF engine, the tool table and the UniFFI interface this package wraps are
**PdfCraft** by the **ArtCraft Team and the PdfCraft contributors**
(<https://github.com/artcraft-android/pdfcraft-android>, a part of <https://github.com/storytold/pdfcraft>),
MIT OR Apache-2.0. All credit for the engine's capabilities belongs to them.
Vendored third-party crates keep their own licences (see `rust/vendor/README.md`, `rust/NOTICE`,
`rust/ATTRIBUTION.md`).

## OCR models
[ocrs-models](https://github.com/robertknight/ocrs-models) by Robert Knight (CC-BY-SA-4.0), shipped unmodified in the
optional `pypdfcraft-ocr-models` wheel.

## Tooling
[UniFFI](https://github.com/mozilla/uniffi-rs) (Mozilla, MPL-2.0) generates the FFI layer;
[cargo-zigbuild](https://github.com/rust-cross/cargo-zigbuild), [cargo-ndk](https://github.com/bbqsrc/cargo-ndk)
and [Zig](https://ziglang.org) are used for cross-compilation in CI.
