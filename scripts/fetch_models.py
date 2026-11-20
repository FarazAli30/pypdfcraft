#!/usr/bin/env python3
"""Download + verify the OCR models into ``packages/ocr-models/src/pypdfcraft_ocr_models/models`` (for the models wheel)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pypdfcraft import models  # noqa: E402

dest = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "packages" / "ocr-models" / "src" / "pypdfcraft_ocr_models" / "models"
models.fetch(str(dest))
print("models in", dest)
