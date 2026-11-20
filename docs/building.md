# Building from source

## Requirements
* Rust (the version pinned in `rust/rust-toolchain.toml`; `rustup` picks it up automatically) and `git`
  (two small dependencies are fetched from GitHub: `craft-docpath`, `craft-print`).
* Python >= 3.9.
* No C/C++ toolchain is needed for the engine itself on Linux/macOS/Windows; Android needs the NDK.

## 1. Build the engine library for your machine

```bash
cd rust
cargo build --release --locked -p pdfcraft-android
# -> rust/target/release/libpdfcraft_android.so | .dylib | pdfcraft_android.dll
```
(`pdfcraft-android` is the UniFFI crate; the name is historical - it builds on every OS.)

For a quick, slow-at-runtime build while developing, lower the optimisation:
`CARGO_PROFILE_RELEASE_OPT_LEVEL=0 CARGO_PROFILE_RELEASE_LTO=false CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 cargo build --release -p pdfcraft-android`.

## 2. Use it from a checkout

```bash
pip install -e ".[dev]"
export PDFCRAFT_LIB=$PWD/rust/target/release/libpdfcraft_android.so    # Windows: set PDFCRAFT_LIB=...\pdfcraft_android.dll
python -m pypdfcraft diagnose
pytest                      # unit tests + real-engine tests
```

## 3. Regenerate generated files after changing `rust/`

```bash
python scripts/gen_bindings.py rust/target/release/libpdfcraft_android.so   # src/pypdfcraft/_bindings.py
python -m pypdfcraft catalog --json src/pypdfcraft/data/tools_catalog.json  # snapshot of the tool table
python scripts/gen_oneshot.py                                                # src/pypdfcraft/oneshot.py
python scripts/gen_docs.py                                                   # docs/api.md, tools.md, coverage.md
```
`gen_bindings.py` uses the workspace's own `pdfcraft-android-bindgen` crate (same UniFFI version as the library);
set `UNIFFI_BINDGEN=/path/to/uniffi-bindgen` to use a prebuilt one. CI fails if these files are stale.

## 4. Build a wheel

```bash
python scripts/build_wheel.py --lib rust/target/release/libpdfcraft_android.so --tag manylinux_2_28_x86_64 --out dist
pip install dist/pypdfcraft-*.whl
```
`--tag` is the platform tag (see [Installation](installation.md)). Use the tag that matches how you built the
library - a library built on a new glibc is **not** `manylinux_2_28`; the CI builds portable libraries with zig.

## 5. Other platforms (what CI does)

| target | how |
|---|---|
| Linux glibc / musl, x86_64 + aarch64 | `pip install cargo-zigbuild`, `cargo zigbuild --release -p pdfcraft-android --target x86_64-unknown-linux-gnu.2.28` (musl: `RUSTFLAGS="-C target-feature=-crt-static"`) |
| macOS arm64 / x86_64 | `MACOSX_DEPLOYMENT_TARGET=11.0 cargo build --release --target aarch64-apple-darwin` / `10.13` + `x86_64-apple-darwin` |
| Windows x64 / ARM64 | `RUSTFLAGS="-C target-feature=+crt-static" cargo build --release --target x86_64-pc-windows-msvc` / `aarch64-pc-windows-msvc` |
| Android | `cargo install cargo-ndk`; `cargo ndk -t arm64-v8a -P 24 build --release -p pdfcraft-android` (also `armeabi-v7a`, `x86_64`, `x86`) |

## 6. Upgrading the engine

```bash
git clone https://github.com/artcraft-android/pdfcraft-android /tmp/upstream
python scripts/sync_upstream.py /tmp/upstream        # copies crates/, vendor/, the FFI crate; trims UI-only parts
cd rust && cargo build --release -p pdfcraft-android # refreshes Cargo.lock
# then step 3, update CHANGELOG.md and ENGINE_VERSION in src/pypdfcraft/_version.py
```
