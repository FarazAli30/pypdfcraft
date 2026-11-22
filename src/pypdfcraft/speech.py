"""Read Aloud: speak a PDF (or write it to an audio file) using the system's own text-to-speech voice.

The engine prepares the text exactly like PdfCraft's Android "Read Aloud": paragraphs in reading order, plus for every
character the glyph it came from, so the word being spoken can be located on the page.  The speaking itself is done by
whatever speech engine the machine has - nothing is bundled and nothing goes online:

====================  =======================================================  ==========  =============
backend               needs                                                    audio file  word events
====================  =======================================================  ==========  =============
``espeak``            ``espeak-ng`` / ``espeak`` (Linux, also installable)     yes (wav)   approximate
``say``               macOS (built in)                                         yes (wav)   approximate
``sapi``              Windows (built in, PowerShell + System.Speech)           yes (wav)   approximate
``pyttsx3``           ``pip install pypdfcraft[speech]`` (any OS)              yes         exact
``termux``            Termux + the Termux:API app (``termux-tts-speak``)       no          approximate
``plyer``             ``pip install plyer`` (Android / iOS)                    no          approximate
``spd-say``           speech-dispatcher (Linux)                                no          approximate
====================  =======================================================  ==========  =============

    import pypdfcraft as pdf
    pdf.read_aloud("book.pdf", pages=[1, 2], rate=1.2)          # speaks, blocks until done
    pdf.to_audio("book.pdf")                                    # -> book.wav
    r = pdf.ReadAloud("book.pdf", on_word=highlight)            # control: play / stop / pause / back / forward
"""
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

from .errors import PdfCraftError
from .results import AttrDict, Result

CATALOG = {"Read aloud": ["read_aloud", "to_audio", "reading_text", "voices", "ReadAloud"]}
__all__ = ["read_aloud", "to_audio", "reading_text", "voices", "ReadAloud", "NoSpeechEngine", "split_sentences",
           "count_words", "words"]

WORDS_PER_MINUTE = 170                                       # for timing estimates at rate 1.0
# "words" as the Android app counts them: runs of letters and digits; every CJK character is a word of its own
_WORD = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]|[^\W_]+", re.UNICODE)
_SENTENCE_END = re.compile(r"(?<=[.!?\u2026\u3002\uff01\uff1f])\s+|(?<=[\u3002\uff01\uff1f])")


class NoSpeechEngine(PdfCraftError):
    """No text-to-speech engine could be found on this machine."""


# ----------------------------------------------------------------------------------------- text helpers
def words(text):
    """``[(start, end, word)]`` - runs of letters/digits, each CJK character on its own."""
    return [(m.start(), m.end(), m.group()) for m in _WORD.finditer(text)]


def count_words(text):
    return len(_WORD.findall(text))


def estimate_seconds(text, rate=1.0):
    return count_words(text) * 60.0 / (WORDS_PER_MINUTE * max(rate, 0.1))


def split_sentences(text, max_chars=1500):
    """Cut ``text`` into utterances of at most ``max_chars`` at sentence ends (else at spaces).

    Returns ``[(offset, chunk)]`` where ``offset`` is where the chunk starts in ``text`` (so word positions
    reported by a speech engine can be mapped back)."""
    pieces, pos = [], 0
    for m in _SENTENCE_END.finditer(text):
        pieces.append((pos, text[pos:m.end()]))
        pos = m.end()
    if pos < len(text):
        pieces.append((pos, text[pos:]))
    out, cur_off, cur = [], None, ""
    for off, piece in pieces:
        while len(piece) > max_chars:                              # a sentence longer than the limit
            cut = piece.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            head, piece, off = piece[:cut], piece[cut:], off + cut
            if cur:
                out.append((cur_off, cur)); cur_off, cur = None, ""
            out.append((off - len(head), head))
        if cur and len(cur) + len(piece) > max_chars:
            out.append((cur_off, cur)); cur_off, cur = None, ""
        if cur_off is None:
            cur_off = off
        cur += piece
    if cur:
        out.append((cur_off, cur))
    cleaned = []
    for off, chunk in out:
        stripped = chunk.lstrip()
        if stripped.strip():
            cleaned.append((off + len(chunk) - len(stripped), stripped.rstrip()))
    return cleaned


# ----------------------------------------------------------------------------------------- backends
def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _importable(name):
    if name in sys.modules:
        return True
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


class Backend:
    """A speech engine.  ``speak`` blocks until the text has been spoken (or :meth:`stop` is called)."""

    name = "?"
    can_save = False
    word_events = False                                      # reports exact word positions itself

    def available(self):
        return False

    def voices(self):
        return []

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        raise NotImplementedError

    def stop(self):
        pass

    def save(self, text, path, *, rate=1.0, volume=1.0, voice=None, language=None):
        raise PdfCraftError(f"the '{self.name}' speech engine cannot write audio files "
                            "(use espeak-ng, macOS say, Windows SAPI or pyttsx3)")


class _ProcBackend(Backend):
    """Backends that run a command-line speech tool (text goes through stdin: no quoting problems)."""

    exe = None

    def __init__(self):
        self._proc, self._stopped, self._lock = None, False, threading.Lock()

    def _find(self):
        for cand in ([self.exe] if isinstance(self.exe, str) else self.exe):
            p = shutil.which(cand)
            if p:
                return p
        return None

    def available(self):
        return self._find() is not None

    def _run(self, cmd, text=None):
        self._stopped = False
        kw = {}
        if sys.platform == "win32":
            kw["creationflags"] = 0x08000000                    # CREATE_NO_WINDOW
        with self._lock:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if text is not None else subprocess.DEVNULL,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **kw)
            proc = self._proc
        _, err = proc.communicate(text.encode("utf-8") if text is not None else None)
        if proc.returncode != 0 and not self._stopped:
            raise PdfCraftError(f"{os.path.basename(cmd[0])} failed ({proc.returncode}): "
                                f"{err.decode('utf-8', 'replace').strip()[:300]}")

    def stop(self):
        self._stopped = True
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass


class EspeakBackend(_ProcBackend):
    name, exe, can_save = "espeak", ("espeak-ng", "espeak"), True

    def _args(self, rate, volume, voice, language):
        a = [self._find(), "-s", str(_clamp(int(175 * rate), 80, 450)), "-a", str(_clamp(int(100 * volume), 0, 200))]
        v = voice or language
        if v:
            a += ["-v", v]
        return a

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        self._run(self._args(rate, volume, voice, language) + ["--stdin"], text)

    def save(self, text, path, *, rate=1.0, volume=1.0, voice=None, language=None):
        self._run(self._args(rate, volume, voice, language) + ["-w", path, "--stdin"], text)

    def voices(self):
        out = subprocess.run([self._find(), "--voices"], capture_output=True, text=True).stdout.splitlines()[1:]
        return [p[3] for p in (l.split() for l in out) if len(p) >= 4]


class SayBackend(_ProcBackend):
    name, exe, can_save = "say", "say", True

    def _args(self, rate, voice):
        a = [self._find(), "-r", str(_clamp(int(175 * rate), 80, 500))]
        return a + (["-v", voice] if voice else [])

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        self._run(self._args(rate, voice) + ["-f", "-"], text)

    def save(self, text, path, *, rate=1.0, volume=1.0, voice=None, language=None):
        fmt = ["--data-format=LEI16@22050"] if path.lower().endswith(".wav") else []
        self._run(self._args(rate, voice) + ["-o", path] + fmt + ["-f", "-"], text)

    def voices(self):
        out = subprocess.run([self._find(), "-v", "?"], capture_output=True, text=True).stdout.splitlines()
        return [re.split(r"\s{2,}", l.strip())[0] for l in out if l.strip()]


class SapiBackend(_ProcBackend):
    """Windows speech (System.Speech through PowerShell): no extra software needed."""
    name, exe, can_save = "sapi", ("powershell", "pwsh"), True

    def available(self):
        return sys.platform == "win32" and self._find() is not None

    @staticmethod
    def _q(s):
        return "'" + str(s).replace("'", "''") + "'"

    def _script(self, textfile, rate, volume, voice, out):
        lines = ["Add-Type -AssemblyName System.Speech",
                 "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
                 f"$s.Rate = {_clamp(int(round(math.log(max(rate, 0.1), 2) * 5)), -10, 10)}",
                 f"$s.Volume = {_clamp(int(100 * volume), 0, 100)}"]
        if voice:
            lines.append(f"$s.SelectVoice({self._q(voice)})")
        if out:
            lines.append(f"$s.SetOutputToWaveFile({self._q(out)})")
        lines += [f"$t = Get-Content -Raw -Encoding UTF8 {self._q(textfile)}", "$s.Speak($t)", "$s.Dispose()"]
        return "\n".join(lines)

    def _go(self, text, rate, volume, voice, out):
        d = tempfile.mkdtemp(prefix="pypdfcraft-tts-")
        try:
            tf, sf = os.path.join(d, "t.txt"), os.path.join(d, "s.ps1")
            with open(tf, "w", encoding="utf-8-sig") as f:
                f.write(text)
            with open(sf, "w", encoding="utf-8-sig") as f:
                f.write(self._script(tf, rate, volume, voice, out))
            self._run([self._find(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", sf])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        self._go(text, rate, volume, voice, None)

    def save(self, text, path, *, rate=1.0, volume=1.0, voice=None, language=None):
        self._go(text, rate, volume, voice, path)

    def voices(self):
        cmd = [self._find(), "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech;"
               "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | "
               "ForEach-Object { $_.VoiceInfo.Name }"]
        return subprocess.run(cmd, capture_output=True, text=True).stdout.split()


class SpdSayBackend(_ProcBackend):
    name, exe = "spd-say", "spd-say"

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        a = [self._find(), "-w", "-e", "-r", str(_clamp(int((rate - 1) * 100), -100, 100)),
             "-i", str(_clamp(int(volume * 200) - 100, -100, 100))]
        if language:
            a += ["-l", language]
        if voice:
            a += ["-y", voice]
        self._run(a, text)


class TermuxBackend(_ProcBackend):
    """Android with Termux: needs the Termux:API app and ``pkg install termux-api``."""
    name, exe = "termux", "termux-tts-speak"

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        a = [self._find(), "-r", str(_clamp(rate, 0.1, 4.0))]
        if language:
            a += ["-l", language]
        self._run(a, text)


class Pyttsx3Backend(Backend):
    """``pip install pyttsx3`` - SAPI5 (Windows), NSSpeechSynthesizer (macOS), eSpeak (Linux); exact word events."""
    name, can_save, word_events = "pyttsx3", True, True

    def __init__(self):
        self._engine = None

    def available(self):
        return _importable("pyttsx3")

    def _eng(self, rate, volume, voice):
        import pyttsx3
        e = pyttsx3.init()
        e.setProperty("rate", int(200 * rate))
        e.setProperty("volume", _clamp(volume, 0.0, 1.0))
        if voice:
            for v in e.getProperty("voices"):
                if voice.lower() in (v.id or "").lower() or voice.lower() in (v.name or "").lower():
                    e.setProperty("voice", v.id)
                    break
        self._engine = e
        return e

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        e = self._eng(rate, volume, voice)
        if on_word:
            e.connect("started-word", lambda name, location, length: on_word(location, length))
        e.say(text)
        e.runAndWait()

    def save(self, text, path, *, rate=1.0, volume=1.0, voice=None, language=None):
        e = self._eng(rate, volume, voice)
        e.save_to_file(text, path)
        e.runAndWait()

    def stop(self):
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:                                  # noqa: BLE001
                pass

    def voices(self):
        import pyttsx3
        return [v.name for v in pyttsx3.init().getProperty("voices")]


class PlyerBackend(Backend):
    """``pip install plyer``: the platform speech service on Android / iOS (no completion callback: timed)."""
    name = "plyer"

    def available(self):
        return _importable("plyer")

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        from plyer import tts
        tts.speak(text)
        self._stop = threading.Event()
        self._stop.wait(estimate_seconds(text, rate) + 0.5)

    def stop(self):
        if getattr(self, "_stop", None):
            self._stop.set()
        try:
            from plyer import tts
            tts.stop()
        except Exception:                                      # noqa: BLE001
            pass


class CallableBackend(Backend):
    """Wrap your own speech function: ``read_aloud(..., backend=lambda text: my_tts(text))``."""
    name = "custom"

    def __init__(self, target):
        self._target = target.speak if hasattr(target, "speak") else target
        self._obj = target

    def available(self):
        return True

    def speak(self, text, *, rate=1.0, volume=1.0, voice=None, language=None, on_word=None):
        try:
            self._target(text, rate=rate, volume=volume, voice=voice, language=language)
        except TypeError:
            self._target(text)

    def stop(self):
        if hasattr(self._obj, "stop"):
            self._obj.stop()


BACKENDS = {b.name: b for b in (EspeakBackend, SayBackend, SapiBackend, SpdSayBackend, TermuxBackend,
                                Pyttsx3Backend, PlyerBackend)}


def _is_android():
    return sys.platform == "android" or "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel")


def get_backend(spec=None):
    """Pick a speech engine: an instance, a callable, a name (see the table), ``$PYPDFCRAFT_TTS``, or automatic."""
    if isinstance(spec, Backend):
        return spec
    if spec is not None and not isinstance(spec, str):
        return CallableBackend(spec)
    name = spec or os.environ.get("PYPDFCRAFT_TTS")
    if name:
        if name not in BACKENDS:
            raise ValueError(f"unknown speech backend {name!r}; choose from {', '.join(BACKENDS)}")
        b = BACKENDS[name]()
        if not b.available():
            raise NoSpeechEngine(f"the '{name}' speech engine is not available on this machine")
        return b
    if _is_android():
        order = (TermuxBackend, PlyerBackend, Pyttsx3Backend)
    elif sys.platform == "win32":
        order = (SapiBackend, Pyttsx3Backend)
    elif sys.platform == "darwin":
        order = (SayBackend, Pyttsx3Backend)
    else:
        order = (EspeakBackend, SpdSayBackend, Pyttsx3Backend)
    for cls in order:
        b = cls()
        if b.available():
            return b
    hint = {"win32": "Windows should have built-in speech: is PowerShell on PATH? or: pip install pyttsx3",
            "darwin": "macOS should have `say`; or: pip install pyttsx3"}.get(sys.platform, "")
    if _is_android():
        hint = "Termux: `pkg install termux-api` (+ the Termux:API app); Pydroid/others: pip install plyer"
    elif not hint:
        hint = "install espeak-ng (e.g. `sudo apt install espeak-ng`) or `pip install pyttsx3`"
    raise NoSpeechEngine("No text-to-speech engine found. " + hint)


def voices(backend=None):
    """Voices the speech engine offers (names usable as ``voice=``)."""
    return get_backend(backend).voices()


# ----------------------------------------------------------------------------------------- reading
class ReadAloud:
    """Speak a document paragraph by paragraph, like PdfCraft's Android Read Aloud.

    ``source``: a path or an open :class:`~pypdfcraft.Document`.  ``pages``: 1-based list/range (default all).
    ``rate`` 1.0 = normal speed.  ``on_paragraph(p)`` is called when a paragraph starts and ``on_word(w)`` for every
    word (``w.rect`` = ``[x0, y0, x1, y1]`` in PDF points from the top-left, ``w.page``, ``w.text``, ``w.paragraph``);
    word callbacks are exact with the ``pyttsx3`` engine and timed estimates otherwise.

        r = ReadAloud("a.pdf", pages=range(1, 4), rate=1.1)
        r.play()                          # blocks;  r.play(wait=False) returns at once
        r.stop(); r.pause(); r.resume(); r.forward(); r.back()
    """

    def __init__(self, source, *, pages=None, start_page=None, voice=None, language=None, rate=1.0, volume=1.0,
                 backend=None, password=None, max_chars=1500, on_paragraph=None, on_word=None):
        from . import core
        self._owns = isinstance(source, (str, bytes, os.PathLike))
        self.source_path = os.path.abspath(os.fspath(source)) if self._owns else None
        self.doc = core.open(source, password) if self._owns else source
        self.pages = list(pages) if pages is not None else list(range(1, self.doc.page_count + 1))
        if start_page is not None:
            self.pages = [p for p in self.pages if p >= start_page]
        self.voice, self.language, self.rate, self.volume = voice, language, rate, volume
        self.max_chars, self.on_paragraph, self.on_word = max_chars, on_paragraph, on_word
        self._backend_spec, self._backend = backend, None
        self._paragraphs = None
        self.position = 0                                    # index of the paragraph being / to be read
        self._thread, self._stop, self._lock = None, threading.Event(), threading.Lock()
        self.error = None

    # -- backend / lifecycle --------------------------------------------------------------
    @property
    def backend(self):
        if self._backend is None:
            self._backend = get_backend(self._backend_spec)
        return self._backend

    def close(self):
        self.stop()
        if self._owns:
            try:
                self.doc.close(discard_changes=True)
            except Exception:                                 # noqa: BLE001
                pass
            self._owns = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- text ---------------------------------------------------------------------------
    @property
    def paragraphs(self):
        """``[Paragraph(page, index, text, rects, range)]`` in reading order (loaded once)."""
        if self._paragraphs is None:
            out = []
            for page in self.pages:
                for b in self.doc.blocks(page):
                    out.append(AttrDict(page=page, index=len(out), text=b.text, rects=self._rects(b),
                                        range=b.range, glyph_of_char=list(b.glyph_of_char)))
            self._paragraphs = out
        return self._paragraphs

    def _rects(self, block):
        try:
            return list(self.doc.text_rects(block.range))
        except Exception:                                     # noqa: BLE001
            return []

    def words(self, paragraph):
        """Words of a paragraph with their page rectangles: ``[Word(text, start, end, rect, page, paragraph)]``."""
        p = self.paragraphs[paragraph] if isinstance(paragraph, int) else paragraph
        out = []
        for s, e, w in words(p.text):
            glyphs = [g for g in p.glyph_of_char[s:e] if g is not None]
            rect = None
            if glyphs:
                try:
                    rs = [self.doc.glyph_rect(p.page, g) for g in (glyphs[0], glyphs[-1])]
                    rect = [min(r[0] for r in rs), min(r[1] for r in rs), max(r[2] for r in rs), max(r[3] for r in rs)]
                except Exception:                             # noqa: BLE001
                    rect = None
            out.append(AttrDict(text=w, start=s, end=e, rect=rect, page=p.page, paragraph=p.index))
        return out

    def seconds(self):
        """Estimated reading time of everything selected."""
        return sum(estimate_seconds(p.text, self.rate) for p in self.paragraphs)

    # -- playing ------------------------------------------------------------------------
    @property
    def playing(self):
        return self._thread is not None and self._thread.is_alive()

    def play(self, *, from_paragraph=None, wait=True):
        """Start speaking (from ``from_paragraph`` or the current position).  ``wait=False`` returns immediately."""
        self.stop()
        if from_paragraph is not None:
            self.position = max(0, min(from_paragraph, len(self.paragraphs)))
        self.paragraphs                                       # load text in the calling thread
        self.backend
        self._stop.clear()
        self.error = None
        self._thread = threading.Thread(target=self._run, name="pypdfcraft-read-aloud", daemon=True)
        self._thread.start()
        if wait:
            self._thread.join()
            if self.error:
                raise self.error
        return self

    def join(self):
        if self._thread:
            self._thread.join()
        if self.error:
            raise self.error

    def stop(self):
        """Stop speaking; the position stays on the paragraph being read."""
        self._stop.set()
        if self._backend is not None:
            self._backend.stop()
        t = self._thread
        if t is not None and t is not threading.current_thread() and t.is_alive():
            t.join(timeout=5)

    def pause(self):
        self.stop()

    def resume(self, *, wait=False):
        """Continue from the start of the paragraph that was being read (like the app)."""
        return self.play(wait=wait)

    def forward(self, n=1):
        """Skip ``n`` paragraphs ahead (keeps playing if it was playing)."""
        return self._move(n)

    def back(self, n=1):
        return self._move(-n)

    def _move(self, n):
        was = self.playing
        self.stop()
        self.position = max(0, min(self.position + n, max(len(self.paragraphs) - 1, 0)))
        if was:
            self.play(wait=False)
        return self

    def _run(self):
        try:
            paras = self.paragraphs
            while self.position < len(paras) and not self._stop.is_set():
                p = paras[self.position]
                if self.on_paragraph:
                    self.on_paragraph(p)
                self._speak_paragraph(p)
                if self._stop.is_set():
                    break
                self.position += 1
        except Exception as e:                                # noqa: BLE001
            self.error = e

    def _speak_paragraph(self, p):
        word_list = self.words(p) if self.on_word else []
        for off, chunk in split_sentences(p.text, self.max_chars):
            if self._stop.is_set():
                return
            timer = None
            on_word = None
            if self.on_word:
                if self.backend.word_events:
                    def on_word(location, length, _off=off, _words=word_list):
                        pos = _off + location
                        w = next((w for w in _words if w.start <= pos < w.end), None)
                        if w is not None:
                            self.on_word(w)
                else:
                    timer = self._simulate_words(word_list, off, off + len(chunk), chunk)
            try:
                self.backend.speak(chunk, rate=self.rate, volume=self.volume, voice=self.voice,
                                   language=self.language, on_word=on_word)
            finally:
                if timer is not None:
                    timer[0].set()
                    timer[1].join(timeout=1)

    def _simulate_words(self, word_list, start, end, chunk):
        """Approximate word timing for engines that do not report it (proportional to word length)."""
        ws = [w for w in word_list if start <= w.start < end]
        total = estimate_seconds(chunk, self.rate)
        stop = threading.Event()
        chars = sum(w.end - w.start + 1 for w in ws) or 1

        def run():
            t0 = time.monotonic()
            elapsed = 0.0
            for w in ws:
                if stop.is_set() or self._stop.is_set():
                    return
                self.on_word(w)
                elapsed += total * (w.end - w.start + 1) / chars
                delay = t0 + elapsed - time.monotonic()
                if delay > 0 and stop.wait(delay):
                    return
        th = threading.Thread(target=run, daemon=True)
        th.start()
        return stop, th

    # -- audio file -----------------------------------------------------------------------
    def save(self, out=None):
        """Write the selected text to an audio file (default ``<name>.wav`` next to the PDF)."""
        from . import api
        if out is None:
            base = self.source_path or os.path.join(os.getcwd(), self.doc.info.name or "document.pdf")
            out = api._auto_out(base, "", ".wav")
        out = api._o(out)
        text = "\n\n".join(p.text for p in self.paragraphs)
        if not text.strip():
            raise PdfCraftError("nothing to read: the selected pages have no text (scanned? run ocr() first)")
        self.backend.save(text, out, rate=self.rate, volume=self.volume, voice=self.voice, language=self.language)
        seconds = None
        try:
            with wave.open(out) as w:
                seconds = round(w.getnframes() / float(w.getframerate()), 2)
        except Exception:                                     # noqa: BLE001
            pass
        return Result(out=out, seconds=seconds, paragraphs=len(self.paragraphs), words=count_words(text),
                      engine=self.backend.name)


def reading_text(src, pages=None, *, password=None):
    """The paragraphs Read Aloud would speak: ``[{page, index, text}]`` in reading order."""
    with ReadAloud(src, pages=pages, password=password) as r:
        return [AttrDict(page=p.page, index=p.index, text=p.text) for p in r.paragraphs]


def read_aloud(src, pages=None, *, voice=None, language=None, rate=1.0, volume=1.0, backend=None, password=None,
               on_paragraph=None, on_word=None, wait=True):
    """Speak the PDF's text in reading order with the system voice (see the module docs for the engines).

        read_aloud("book.pdf")                       # everything
        read_aloud("book.pdf", pages=[3, 4], rate=1.3, voice="en-us")

    Returns the :class:`ReadAloud` controller (``stop()``, ``pause()``, ``forward()`` ...); with ``wait=False`` it
    keeps reading in the background.  Raises :class:`NoSpeechEngine` if the machine has no speech engine and
    ``PdfCraftError`` if there is no text (scanned pages: run ``ocr()`` first)."""
    r = ReadAloud(src, pages=pages, voice=voice, language=language, rate=rate, volume=volume, backend=backend,
                  password=password, on_paragraph=on_paragraph, on_word=on_word)
    if not r.paragraphs:
        r.close()
        raise PdfCraftError("nothing to read: no text on the selected pages (scanned? run ocr() first)")
    try:
        r.play(wait=wait)
    finally:
        if wait:
            r.close()
    return r


def to_audio(src, out=None, pages=None, *, voice=None, language=None, rate=1.0, volume=1.0, backend=None, password=None):
    """Write the spoken text to an audio file -> ``<name>.wav`` (engines: espeak-ng, macOS say, Windows SAPI, pyttsx3)."""
    with ReadAloud(src, pages=pages, voice=voice, language=language, rate=rate, volume=volume, backend=backend,
                   password=password) as r:
        return r.save(out)
