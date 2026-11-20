# OCR (searchable scans)

OCR needs two model files (~12 MB, CC-BY-SA-4.0, by the *ocrs* project) that are **not** inside the engine library.

```bash
pip install "pypdfcraft[ocr]"       # recommended: ships them as pypdfcraft-ocr-models
```
or, once per machine:
```python
pdf.install_models()                      # downloads + SHA-256-verifies into ~/.pypdfcraft/models
pdf.install_models(apk="PdfCraft.apk")    # offline: take them from the Android app's APK
pdf.set_models_dir("/my/models")          # a folder you provide
```
Models are also found through `$PDFCRAFT_MODELS`.

```python
pdf.ocr("scan.pdf")                       # -> scan_ocr.pdf with an invisible text layer
pdf.ocr.status()                          # {'available': True, 'search_dirs': [...], 'languages': [...]}
```
The engine's recognizer currently covers the Latin alphabet. After OCR you can `extract_text`, `replace_text`,
`convert(..., "docx")`, search, etc. `ocr_recognize_files` (tool) recognizes image files directly:
`pdf.run_tool("ocr_recognize_files", ...)`.
