# Cookbook

## Batch-compress a folder
```python
import pathlib, pypdfcraft as pdf
for f in pathlib.Path("inbox").glob("*.pdf"):
    r = pdf.compress(f, pathlib.Path("outbox") / f.name)
    print(f.name, r.bytes_before, "->", r.bytes_after)
```
`compress` writes nothing when the file cannot get smaller; `r.copied_original` is then `True` and `out` is a copy.

## Update a date everywhere, then stamp it
```python
pdf.replace_text("report.pdf", "Q3 2025", "Q4 2025", out="report_q4.pdf")
pdf.watermark("report_q4.pdf", "CONFIDENTIAL", opacity=0.2, inplace=True)
```

## Replace a logo
```python
pdf.show_images("brochure.pdf")                    # find the page / image number
pdf.replace_image("brochure.pdf", page=1, image=1, file="new_logo.png")
```

## Scanned document -> searchable -> Word
```python
pdf.install_models()                               # once (or: pip install "pypdfcraft[ocr]")
pdf.ocr("scan.pdf", out="scan_ocr.pdf")
pdf.convert("scan_ocr.pdf", "docx")
```

## Sign a PDF
```python
pdf.create_digital_id("me.p12", name="Ada Lovelace", password="s3cret-pass", email="ada@example.com")
pdf.sign("contract.pdf", "me.p12", id_password="s3cret-pass", reason="I approve",
         page=1, rect=[72, 700, 272, 760])         # visible signature -> contract_signed.pdf
print(pdf.signatures("contract_signed.pdf"))
```

## Redact
```python
pdf.redact("a.pdf", find="123-45-6789")            # black boxes + the text is really removed
print(pdf.audit_redactions("other.pdf"))           # finds fake redactions (text still underneath)
```

## Fill a form
```python
print(pdf.form_fields("form.pdf"))
pdf.fill_form("form.pdf", {"name": "Ada", "agree": True})
pdf.flatten("form_filled.pdf", fields=True)
```

## Bates numbering across files
```python
pdf.bates(["a.pdf", "b.pdf"], prefix="ACME-", start_number=1, digits=6)
```

## Comments and links
```python
pdf.add_comment("a.pdf", page=1, type="highlight", find="important phrase", color="#ffee00")
pdf.add_comment("a.pdf", page=1, type="note", at=[100, 100], contents="Check this", author="Ada")
print(pdf.comments("a_commented.pdf"))
pdf.add_link("a.pdf", page=1, rect=[72, 72, 200, 90], url="https://example.com")
```

## Sanitize before sharing
```python
print(pdf.hidden_info("a.pdf"))
pdf.sanitize("a.pdf")                              # metadata, comments, attachments, scripts ...
```

## Pull text with positions (for your own layout code)
```python
with pdf.open("a.pdf") as doc:
    for line in doc.lines(1):
        print(line.line, line.rect, line.size, line.text)
    hits = doc.search("invoice")                   # [(page, SearchHit)]
```

## Encrypted input
Every function accepts `password="..."` for opening the source file.
