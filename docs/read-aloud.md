# Read aloud

PdfCraft's Android app can read a document aloud: the engine splits each page into **paragraphs in reading order** and
tells, for every character, which glyph it came from, so the word being spoken can be marked on the page; the phone's
own text-to-speech voice does the speaking. pypdfcraft gives you the same on every platform - nothing is bundled and
nothing goes online.

```python
import pypdfcraft as pdf

pdf.read_aloud("book.pdf")                         # speak everything, wait until done
pdf.read_aloud("book.pdf", pages=[3, 4], rate=1.3)  # pages 3-4, 30 % faster
pdf.to_audio("book.pdf")                           # -> book.wav
pdf.reading_text("book.pdf", pages=[1])            # [{page, index, text}] - exactly what would be spoken
pdf.voices()                                       # voices of the speech engine
```

## Controlling playback

```python
r = pdf.ReadAloud("book.pdf", pages=range(1, 6), rate=1.1, voice="en-us")
r.play(wait=False)       # reads in the background
r.pause()                # stop; the position stays on the paragraph being read
r.resume()               # continue from the start of that paragraph (like the app)
r.forward(); r.back()    # next / previous paragraph (keeps playing if it was playing)
r.stop(); r.close()
print(r.position, r.seconds())     # paragraph index, estimated total reading time
```
`with pdf.open("a.pdf") as doc: doc.read_aloud(pages=[1])` and `doc.reading_text(1)` work on an open document too.

## Following along: paragraphs and words

```python
def show(word):                       # word.text, word.rect = [x0, y0, x1, y1] in PDF points (top-left origin)
    print(word.page, word.text, word.rect)

pdf.read_aloud("a.pdf", on_paragraph=lambda p: print("paragraph", p.index, p.rects), on_word=show)
```
Multiply `rect` by your render scale to draw a highlight on a page image (see [viewer](viewer.md)).
Word callbacks are **exact** with the `pyttsx3` engine; with command-line engines (espeak-ng, say, SAPI ...) they are
timed estimates (proportional to word length) because those tools do not report progress.
"Words" are counted like in the app: runs of letters and digits; every CJK character is a word of its own.

## Speech engines

| engine (`backend=`) | where | needs | audio file | word events |
|---|---|---|---|---|
| `espeak` | Linux, any OS with it | `espeak-ng` (`sudo apt install espeak-ng`) | wav | estimated |
| `say` | macOS | built in | wav | estimated |
| `sapi` | Windows | built in (PowerShell + System.Speech) | wav | estimated |
| `pyttsx3` | any | `pip install "pypdfcraft[speech]"` | yes | exact |
| `termux` | Android (Termux) | `pkg install termux-api` + the Termux:API app | no | estimated |
| `plyer` | Android / iOS | `pip install plyer` | no | estimated |
| `spd-say` | Linux | speech-dispatcher | no | estimated |

The engine is picked automatically for your platform; choose one with `backend="pyttsx3"` or the environment variable
`PYPDFCRAFT_TTS`. Your own function works too: `read_aloud("a.pdf", backend=lambda text: my_speak(text))`.
`voice=` takes a voice name (`pdf.voices()`), `language="en-us"` a language code (engine-dependent).

Command line: `python -m pypdfcraft read book.pdf --pages 1-3 --rate 1.2` and `... --save` (audio file), `python -m pypdfcraft voices`.

## Notes

* **Scanned pages have no text**: run [`ocr()`](ocr.md) first, then read the OCR'd file.
* Long paragraphs are cut at sentence ends into utterances of at most `max_chars=1500` characters.
* `pause()`/`resume()` restart the current paragraph (the command-line engines cannot pause mid-utterance).
* Use the document only from one thread at a time: `play(wait=False)` reads in a background thread.
* Android engines (`termux`, `plyer`) are provided on a best-effort basis; `espeak`, the audio export and the whole
  reading pipeline are covered by tests.
