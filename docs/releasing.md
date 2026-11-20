# Releasing

1. Update `src/pypdfcraft/_version.py` (`__version__`, and `ENGINE_VERSION` if the engine changed) and `CHANGELOG.md`.
2. Make sure `main` is green (CI also checks that the generated files are current).
3. Tag and push:
   ```bash
   git tag v0.4.0 && git push origin v0.4.0
   ```
4. `release.yml` then: verifies tag == package version -> runs `wheels.yml` (12 native builds, smoke tests, models wheel)
   -> publishes every wheel to PyPI -> creates a GitHub Release with all wheels, the Termux/Pydroid wheels and
   `SHA256SUMS.txt`.

## One-time setup

* **PyPI trusted publishing** (no tokens): on <https://pypi.org/manage/account/publishing/> add a *pending publisher*
  for projects `pypdfcraft` and `pypdfcraft-ocr-models`: owner `FarazAli30`, repository `pypdfcraft`,
  workflow `release.yml`, environment `pypi`. Create the GitHub environment `pypi` (Settings -> Environments).
* **GitHub Pages**: Settings -> Pages -> Source: *GitHub Actions* (for `docs.yml`).

## Wheel matrix

`py3-none-<platform>`: manylinux_2_28 (x86_64, aarch64), musllinux_1_2 (x86_64, aarch64), macOS (x86_64 10.13+,
arm64 11+), Windows (x64, ARM64), Android API 24 (arm64-v8a, armeabi-v7a, x86_64, x86), plus `linux_aarch64` /
`linux_armv7l` copies of the Android library for Termux/Pydroid (GitHub Releases only: PyPI rejects `linux_*` tags).
Linux aarch64, musl, macOS x86_64, Windows ARM64 and Android wheels are cross-built and not executed in CI.
