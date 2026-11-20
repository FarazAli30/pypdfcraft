#!/usr/bin/env python3
"""Copy the engine sources from an upstream PdfCraft checkout into ``rust/`` (and trim what we do not build).

    git clone https://github.com/artcraft-android/pdfcraft-android /tmp/upstream
    python scripts/sync_upstream.py /tmp/upstream

Kept: ``crates/``, the patched crates in ``vendor/`` that the workspace manifest points at, the UniFFI crate
``apps/pdfcraft-android`` (Rust only - no Android UI), fonts, licences, notices, lockfile.
Trimmed: the desktop-UI-only ``[patch]`` git entries and workspace dependencies (egui, winit, craft-ui ...) and the
``targets`` list of ``rust-toolchain.toml`` (CI installs targets itself).  After syncing, build once so cargo prunes
``Cargo.lock``, then regenerate the generated files (see docs/building.md).
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "rust"
UI_ONLY = ("craft-ui =", "craft-quit =", "craft-menu =", "craft-keymap =", "craft-i18n =", "craft-update =",
           "pdfcraft-ui-egui =")
ROOT_FILES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "clippy.toml", "rustfmt.toml", "LICENSE-MIT",
              "LICENSE-APACHE", "NOTICE", "ATTRIBUTION.md", "ATTRIBUTION.toml"]
FFI = ["src", "bindgen", "Cargo.toml", "README.md", "uniffi.toml", "fetch-models.sh"]


def copy(src, dst):
    if dst.exists():
        shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("target", ".git")) if src.is_dir() else shutil.copy2(src, dst)


def trim_manifest(text):
    i = text.find("# The egui and winit crates below")
    if i != -1:
        text = text[:i].rstrip() + "\n"
    out = []
    for line in text.split("\n"):
        if line.startswith(UI_ONLY):
            while out and out[-1].startswith("#"):
                out.pop()
            continue
        out.append(line)
    return "\n".join(out)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    up = Path(sys.argv[1]).resolve()
    if not (up / "Cargo.toml").exists() or not (up / "crates").is_dir():
        sys.exit(f"{up} does not look like a PdfCraft checkout")
    DEST.mkdir(exist_ok=True)
    copy(up / "crates", DEST / "crates")
    for f in ROOT_FILES:
        if (up / f).exists():
            copy(up / f, DEST / f)
    manifest = (up / "Cargo.toml").read_text(encoding="utf-8")
    vendored = sorted(set(re.findall(r'path\s*=\s*"vendor/([^"]+)"', manifest)))
    (DEST / "vendor").mkdir(exist_ok=True)
    for name in vendored:
        copy(up / "vendor" / name, DEST / "vendor" / name)
    if (up / "vendor" / "README.md").exists():
        copy(up / "vendor" / "README.md", DEST / "vendor" / "README.md")
    (DEST / "apps" / "pdfcraft-android").mkdir(parents=True, exist_ok=True)
    for f in FFI:
        copy(up / "apps" / "pdfcraft-android" / f, DEST / "apps" / "pdfcraft-android" / f)
    copy(up / "assets" / "fonts", DEST / "assets" / "fonts")
    (DEST / "Cargo.toml").write_text(trim_manifest(manifest), encoding="utf-8")
    tc = DEST / "rust-toolchain.toml"
    tc.write_text("\n".join(l for l in tc.read_text().splitlines() if not l.startswith("targets")) + "\n")
    version = re.search(r'^version\s*=\s*"([^"]+)"', manifest, re.M)
    print(f"synced PdfCraft {version.group(1) if version else '?'} into {DEST} ({len(vendored)} vendored crates)")
    print("next: cd rust && cargo build --release -p pdfcraft-android   # prunes Cargo.lock")


if __name__ == "__main__":
    main()
