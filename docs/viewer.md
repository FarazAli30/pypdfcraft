# Showing pages in a GUI (Tkinter / Qt)

The engine renders pages to pixels; any toolkit can display them.

```python
import base64, tkinter as tk, pypdfcraft as pdf

doc, scale = pdf.open("a.pdf"), 1.5
root = tk.Tk(); cv = tk.Canvas(root, bg="gray"); cv.pack(fill="both", expand=True)

def show(page=1):
    global ph
    png = doc.render(page, scale).to_png_bytes()              # no Pillow needed
    ph = tk.PhotoImage(data=base64.b64encode(png))             # keep a reference
    cv.delete("all"); cv.create_image(0, 0, image=ph, anchor="nw")
    for l in doc.lines(page):                                  # clickable line boxes
        x0, y0, x1, y1 = [v * scale for v in l.rect]
        cv.create_rectangle(x0, y0, x1, y1, outline="", tags=f"line{l.line}")
show(1); root.mainloop()
```

* **Zoom / pan:** `doc.render(page, scale, region=(x, y, w, h))` renders just a tile (device pixels at that scale).
* **Click -> text:** `doc.nearest_glyph(page, x_pt, y_pt)`, `doc.word_at(page, x, y)`, `doc.text_rects(range)` give
  selection geometry; divide canvas pixels by the render scale to get PDF points.
* **Live edits:** after `doc.edit_line(...)` call `doc.render(...)` again - unsaved edits are rendered.
* `Image.to_pil()` / `.to_numpy()` / `.save("p.png")` convert for other toolkits (`pip install "pypdfcraft[pil]"`).
