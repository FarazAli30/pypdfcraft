# pypdfcraft-ocr-models

The two text-detection / text-recognition models used by `pypdfcraft`'s `ocr()` (PdfCraft's "Recognize text"),
packaged as a separate wheel because they are ~12 MB and licensed differently from the code.

* Models: [ocrs-models](https://github.com/robertknight/ocrs-models) by Robert Knight, trained on HierText,
  **CC-BY-SA-4.0** (unmodified; full text next to each model file and in `ATTRIBUTION.txt`).
* Install: `pip install "pypdfcraft[ocr]"` - pypdfcraft finds them automatically.

The wheel is built by `scripts/fetch_models.py` (downloads and SHA-256-verifies the files from the original source).
