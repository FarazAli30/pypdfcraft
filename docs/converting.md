# Converting

```python
pdf.convert("a.pdf", "docx")      # Word        (also: xlsx, pptx, html, md, txt)
pdf.convert("a.pdf", "png")       # one picture per page in a_png/   (jpg, tiff; dpi=150, pages=[1,2])
pdf.convert("a.pdf", "pdfa")      # archival PDF/A
pdf.convert("letter.docx")        # docx, xlsx, pptx, rtf -> PDF
pdf.convert("photo.jpg")          # picture -> PDF        (tif, png, gif, bmp)
pdf.convert("notes.txt")          # text -> PDF
```
Individual functions: `to_word, to_excel, to_powerpoint, to_html, to_markdown, to_text, to_images, to_pdfa,
extract_images, images_to_pdf, text_to_pdf, office_to_pdf`. For many images or mixed files in one PDF use
`merge([...])` - it converts images, text and Office files on the way.

Conversion runs entirely on the device by the Rust engine; layout fidelity of PDF -> Office follows the engine's
export (tables become real tables where it can detect them).
