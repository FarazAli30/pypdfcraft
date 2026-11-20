# Editing text and images

pypdfcraft drives the same engine functions as PdfCraft's Android "Edit PDF" mode.

## Text

Numbers are 1-based and come from the listings, so *look first, then edit*:

```python
pdf.show_lines("a.pdf", page=1)
# p1 #1   [Helvetica 12pt]  Invoice 2023
# p1 #2   [Helvetica 12pt]  Total due: 120.00
pdf.edit_line("a.pdf", page=1, line=2, text="Total due: 150.00")
```

| function | what it does |
|---|---|
| `lines(src, page=None)` | `[{page, line, text, rect, font, size}]` |
| `paragraphs(src, page=None)` | paragraphs with `font, size, bold, italic, color` |
| `find(src, query)` | where a phrase occurs |
| `edit_line(src, page, line, text)` | replace one line; position, size and colour are kept |
| `edit_paragraph(src, page, n, text=None, **format)` | re-wrapped text and/or restyle (`size`, `bold`, `italic`, `color`, `align`, `font`, `line_spacing`, `dx`, `dy`, `width`) |
| `replace_text(src, old, new, pages=None, case_sensitive=False, mode="auto")` | replace a phrase everywhere; raises `TextNotFound` if absent |
| `add_text(src, page, text, at=[x, y], size=...)` | new text |
| `interactive_edit(src)` | console editor (page -> line -> type text) |

Notes

* `mode="line"` edits single lines; a phrase that wraps across lines needs `mode="paragraph"` (`"auto"` tries lines, then paragraphs).
* Characters the document's font lacks are substituted from standard fonts; scripts that cannot be represented are refused with a clear `ToolError`.
* Scanned pages have no text layer: run [`ocr()`](ocr.md) first.
* Coordinates are PDF points measured from the **top-left** of the page.

## Images

```python
pdf.show_images("a.pdf", page=1)        # p1 image 2  image (800, 600) px  rect=[...]
pdf.replace_image("a.pdf", page=1, image=2, file="logo.png")   # placement kept
pdf.delete_image("a.pdf", 1, 2)
pdf.move_image("a.pdf", 1, 2, [50, 50, 250, 200])              # move / resize
pdf.edit_image("a.pdf", 1, 2, "rotate_by", degrees=15)         # crop, flip_horizontal, bring_to_front, ...
pdf.add_image("a.pdf", 1, "stamp.png", [400, 40, 520, 100])
pdf.save_image("a.pdf", 1, 2)           # export one picture;  extract_images("a.pdf") exports all
```
`image=None` is accepted when the page has exactly one picture. A replacement with a different aspect ratio is
stretched to the old frame - adjust with `move_image` afterwards.

## Several edits, one save

```python
with pdf.edit("a.pdf") as doc:          # -> a_edited.pdf
    doc.replace_text("2023", "2024")
    doc.replace_image(1, 2, "logo.png")
    doc.page.rotate(degrees=90, pages=[3])
```
