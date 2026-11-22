# Installation

```bash
pip install pypdfcraft
```

The wheel contains the native engine (`pypdfcraft/_lib/`) for your platform, so nothing else is needed.
It is tagged `py3-none-<platform>`: **one wheel per OS/CPU that works with every Python >= 3.9**.

| Platform | Wheel tag |
|---|---|
| Linux x86_64 / aarch64 (glibc >= 2.28) | `manylinux_2_28_x86_64`, `manylinux_2_28_aarch64` |
| Alpine (musl) x86_64 / aarch64 | `musllinux_1_2_x86_64`, `musllinux_1_2_aarch64` |
| macOS Intel (10.13+) / Apple Silicon (11+) | `macosx_10_13_x86_64`, `macosx_11_0_arm64` |
| Windows x64 / ARM64 | `win_amd64`, `win_arm64` |
| Android (official CPython 3.13+, Chaquopy, BeeWare) | `android_24_arm64_v8a`, `android_24_armeabi_v7a`, `android_24_x86_64`, `android_24_x86` |
| Termux / Pydroid 3 | `linux_aarch64`, `linux_armv7l` (GitHub Releases only) |

## Extras

```bash
pip install "pypdfcraft[ocr]"    # OCR models (pypdfcraft-ocr-models, CC-BY-SA-4.0, ~12 MB)
pip install "pypdfcraft[speech]" # pyttsx3 speech engine for read aloud (optional)
pip install "pypdfcraft[pil]"    # Image.to_pil()
pip install "pypdfcraft[numpy]"  # Image.to_numpy()
pip install "pypdfcraft[all]"
```

## Termux / Pydroid 3 (Android)

PyPI cannot serve a `linux_*` wheel, so download the file that matches `uname -m` from the
[GitHub Release](https://github.com/FarazAli30/pypdfcraft/releases) (`aarch64` = 64-bit phones) and install it:

```bash
pip install pypdfcraft-0.4.0-py3-none-linux_aarch64.whl
```

Pydroid 3: *Pip* menu -> *Install* -> pick the downloaded `.whl`, or copy the `pypdfcraft` folder out of the wheel
(it is a zip) into your project. Then `python -m pypdfcraft diagnose`.

## Check the installation

```bash
python -m pypdfcraft diagnose
```
prints the Python/CPU, where the library was found and whether it loads. Use this output in bug reports.

## Using a hand-built or extracted library

Set `PDFCRAFT_LIB=/full/path/to/libpdfcraft_engine.so` (or `.dylib` / `pdfcraft_engine.dll`; the upstream names
`libpdfcraft_android.so` / `pdfcraft_android.dll` also work), or drop the file into `site-packages/pypdfcraft/_lib/`.
The library must come from the **same engine build** as the installed bindings (they verify checksums when loading).
