# Quickstart

```python
import pypdfcraft as pdf

pdf.help()                 # cheat sheet of every function
pdf.search("watermark")    # find anything
```

## Output paths are optional

Leave `out` away and a new file appears next to the source (`report.pdf` -> `report_compressed.pdf`).
Nothing is overwritten (`_2`, `_3` are appended). Pass `out="x.pdf"` to choose, or `inplace=True` to overwrite the source.
Every function returns a `Result`; `r.out` is the file or folder written.

```python
r = pdf.compress("big.pdf")
print(r.out, r.bytes_before, r.bytes_after)
```

## Common tasks

```python
pdf.merge(["a.pdf", "b.pdf", "scan.png"])          # a_merged.pdf (images and Office files work too)
pdf.split("book.pdf", every=10)                    # book_parts/book-part1.pdf ...
pdf.extract_pages("a.pdf", [1, 4, 5])
pdf.rotate("a.pdf", 90, pages=[2])
pdf.protect("a.pdf", open_password="secret");  pdf.unprotect("a_protected.pdf", "secret")
pdf.watermark("a.pdf", "DRAFT", opacity=0.3)
pdf.convert("a.pdf", "docx");  pdf.convert("letter.docx");  pdf.convert("a.pdf", "png", dpi=150)
```

## Edit the real text and pictures

```python
pdf.show_lines("a.pdf", page=1)                    # p1 #3 [Helvetica 12pt] Invoice 2023 total
pdf.edit_line("a.pdf", page=1, line=3, text="Invoice 2024 total")
pdf.replace_text("a.pdf", "2023", "2024")
pdf.show_images("a.pdf", page=1)
pdf.replace_image("a.pdf", page=1, image=2, file="logo.png")
```

## Work on an open document

```python
with pdf.open("a.pdf") as doc:                     # password="..." for encrypted files
    print(doc.page_count, doc.metadata)
    print(doc.text(1))
    doc.page.rotate(degrees=90, pages=[1])         # any engine tool: doc.<tool>(...) / doc.<group>.<tool>(...)
    doc.save("out.pdf")                            # unsaved edits are discarded (with a warning) otherwise
```
or let `edit()` save for you:
```python
with pdf.edit("a.pdf") as doc:                     # saves to a_edited.pdf when the block ends
    doc.replace_text("2023", "2024")
    doc.replace_image(1, 2, "logo.png")
print(doc.out_path)
```

## Any of the 186 engine tools

```python
pdf.apply("a.pdf", "text_word_count")              # read-only: nothing written, returns the result
pdf.apply("a.pdf", "doc_flatten", fields=True)     # modifying: saved to a_edited.pdf
pdf.doc_background("a.pdf", color="#fff8dc")       # generated typed one-shot function per tool
help(pdf.tool("doc_watermark"))                    # arguments of a tool
```
See the [tool reference](tools.md).

## Errors

All derive from `pypdfcraft.PdfCraftError`: `OpenError`, `PasswordRequired`, `WrongPassword`, `ToolError`,
`RenderError`, `NoDocumentError`, `TextNotFound`, `OcrModelsMissing`, `NativeLibraryError`.
