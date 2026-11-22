"""Unit tests for Read Aloud (no native library, no speech engine needed)."""
import sys
import threading
import time
import types
import wave

import pytest

import pypdfcraft as pdf
from pypdfcraft import speech
from pypdfcraft.errors import PdfCraftError

NS = types.SimpleNamespace


# ----------------------------------------------------------------------------------------------- text helpers
def test_words_match_the_android_app():
    assert speech.count_words("") == 0
    assert speech.count_words("A PDF reader, judged!") == 4
    assert speech.count_words("page 12 \u2014 done") == 3
    assert speech.count_words("\u7e26\u66f8\u304d") == 3                       # every CJK character is a word
    assert speech.count_words("Hi \u4e16\u754c and \ud55c\uad6d") == 6
    assert [w for _, _, w in speech.words("one, two!")] == ["one", "two"]


@pytest.mark.parametrize("limit", [20, 60, 1500])
def test_split_sentences_keeps_offsets(limit):
    text = "First sentence here. Second one is a bit longer than the first! Third? " + "word " * 30 + "The end."
    chunks = speech.split_sentences(text, limit)
    assert chunks and all(len(c) <= limit for _, c in chunks)
    for off, c in chunks:
        assert text[off:off + len(c)] == c                                      # offsets map back exactly
    assert [w for _, _, w in speech.words(" ".join(c for _, c in chunks))] == [w for _, _, w in speech.words(text)]


def test_split_sentences_edge_cases():
    assert speech.split_sentences("") == [] and speech.split_sentences("   ") == []
    assert speech.split_sentences("No end") == [(0, "No end")]
    assert [c for _, c in speech.split_sentences("A. B. C.", 1500)] == ["A. B. C."]
    long = "x" * 100                                                              # no spaces at all: hard cut
    assert [len(c) for _, c in speech.split_sentences(long, 40)] == [40, 40, 20]


# ----------------------------------------------------------------------------------------------- command line backends
class FakePopen:
    calls = []
    returncode = 0
    stderr_text = b""

    def __init__(self, cmd, stdin=None, stdout=None, stderr=None, **kw):
        FakePopen.calls.append(cmd)
        self.cmd, self.sent, self.terminated = cmd, None, False

    hook = None

    def communicate(self, data=None):
        self.sent = data
        FakePopen.last = self
        if FakePopen.hook:
            FakePopen.hook()
        return b"", FakePopen.stderr_text

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True


@pytest.fixture
def popen(monkeypatch):
    FakePopen.calls, FakePopen.returncode, FakePopen.stderr_text, FakePopen.hook = [], 0, b"", None
    monkeypatch.setattr(speech.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(speech.shutil, "which", lambda n: f"/bin/{n}")
    return FakePopen


def test_espeak_command(popen):
    b = speech.EspeakBackend()
    b.speak("-starts with a dash", rate=1.5, volume=0.5, voice="de")
    cmd = popen.calls[-1]
    assert cmd[0].endswith("espeak-ng") and cmd[cmd.index("-s") + 1] == "262" and cmd[cmd.index("-a") + 1] == "50"
    assert cmd[cmd.index("-v") + 1] == "de" and cmd[-1] == "--stdin"             # text goes via stdin, not argv
    assert popen.last.sent == "-starts with a dash".encode()
    b.save("hello", "/tmp/o.wav", language="en-us")
    assert popen.calls[-1][-3:] == ["-w", "/tmp/o.wav", "--stdin"] and "en-us" in popen.calls[-1]


def test_say_command(popen):
    b = speech.SayBackend()
    b.speak("hi", rate=2.0, voice="Alex")
    assert popen.calls[-1][1:] == ["-r", "350", "-v", "Alex", "-f", "-"]
    b.save("hi", "/tmp/o.wav")
    assert "--data-format=LEI16@22050" in popen.calls[-1] and popen.calls[-1][-2:] == ["-f", "-"]
    b.save("hi", "/tmp/o.aiff")
    assert "--data-format=LEI16@22050" not in popen.calls[-1]


def test_sapi_script(popen):
    b = speech.SapiBackend()
    script = b._script("C:\\t.txt", 2.0, 0.5, "Microsoft Zira's", "C:\\o.wav")
    assert "$s.Rate = 5" in script and "$s.Volume = 50" in script
    assert "SelectVoice('Microsoft Zira''s')" in script and "SetOutputToWaveFile('C:\\o.wav')" in script
    assert script.rstrip().endswith("$s.Dispose()")
    assert "$s.Rate = -5" in b._script("t", 0.5, 1.0, None, None) and "$s.Rate = 10" in b._script("t", 9, 1.0, None, None)


def test_termux_and_spd_commands(popen):
    speech.TermuxBackend().speak("hi", rate=1.2, language="en-US")
    assert popen.calls[-1][1:] == ["-r", "1.2", "-l", "en-US"] and popen.last.sent == b"hi"
    speech.SpdSayBackend().speak("hi", rate=1.5, language="en")
    assert popen.calls[-1][1:4] == ["-w", "-e", "-r"] and popen.calls[-1][4] == "50"


def test_process_failure_and_stop(popen):
    popen.returncode, popen.stderr_text = 3, b"boom: no audio device"
    with pytest.raises(PdfCraftError, match="no audio device"):
        speech.EspeakBackend().speak("x")
    # stop() terminates the process; the non-zero exit that follows is not an error
    b = speech.EspeakBackend()
    popen.returncode, popen.hook = -15, b.stop
    b.speak("long text")
    assert popen.last.terminated and b._stopped


def test_backends_without_save_say_so():
    with pytest.raises(PdfCraftError, match="cannot write audio files"):
        speech.TermuxBackend().save("x", "o.wav")


# ----------------------------------------------------------------------------------------------- backend selection
def _which_only(*names):
    return lambda n: f"/bin/{n}" if n in names else None


def test_backend_selection(monkeypatch):
    monkeypatch.delenv("PYPDFCRAFT_TTS", raising=False)
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(speech.shutil, "which", _which_only("espeak"))
    assert speech.get_backend().name == "espeak"
    monkeypatch.setattr(speech.shutil, "which", _which_only("spd-say"))
    assert speech.get_backend().name == "spd-say"
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(speech.shutil, "which", _which_only("say"))
    assert speech.get_backend().name == "say"
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(speech.shutil, "which", _which_only("powershell"))
    assert speech.get_backend().name == "sapi"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("ANDROID_ROOT", "/system")
    monkeypatch.setattr(speech.shutil, "which", _which_only("termux-tts-speak"))
    assert speech.get_backend().name == "termux"


def test_no_engine_gives_install_hint(monkeypatch):
    monkeypatch.delenv("PYPDFCRAFT_TTS", raising=False)
    monkeypatch.delenv("ANDROID_ROOT", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(speech.shutil, "which", lambda n: None)
    monkeypatch.setattr(speech.Pyttsx3Backend, "available", lambda self: False)
    with pytest.raises(speech.NoSpeechEngine, match="espeak-ng"):
        speech.get_backend()
    monkeypatch.setenv("PYPDFCRAFT_TTS", "say")
    with pytest.raises(speech.NoSpeechEngine, match="'say'"):
        speech.get_backend()
    with pytest.raises(ValueError):
        speech.get_backend("nonsense")


def test_custom_backends():
    got = []
    assert speech.get_backend(lambda text: got.append(text)).name == "custom"
    speech.get_backend(lambda text: got.append(text)).speak("hello", rate=1.0)    # fn that takes no options
    assert got == ["hello"]
    got2 = []
    speech.get_backend(lambda text, **kw: got2.append((text, kw["rate"]))).speak("x", rate=1.3)
    assert got2 == [("x", 1.3)]


# ----------------------------------------------------------------------------------------------- ReadAloud
class FakeDoc:
    def __init__(self, pages):
        self.pages, self.name = pages, "fake.pdf"
        self.info = NS(name="fake.pdf")

    @property
    def page_count(self):
        return len(self.pages)

    def blocks(self, page):
        return [NS(text=t, range=NS(page=page - 1, start=i, end=i + 1), glyph_of_char=list(range(len(t))))
                for i, t in enumerate(self.pages[page - 1])]

    def text_rects(self, r):
        return [0.0, 0.0, 10.0, 10.0]

    def glyph_rect(self, page, g):
        return [g * 5.0, 0.0, g * 5.0 + 5, 10.0]


class Rec(speech.Backend):
    name, can_save = "rec", True

    def __init__(self, delay=0.0):
        self.spoken, self.delay, self.release = [], delay, threading.Event()

    def available(self):
        return True

    def speak(self, text, **kw):
        self.release.clear()
        self.spoken.append((text, kw["rate"], kw["voice"], kw["language"]))
        if self.delay:
            self.release.wait(self.delay)

    def stop(self):
        self.release.set()

    def save(self, text, path, **kw):
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
            w.writeframes(b"\x00\x00" * 16000)             # exactly 2 seconds of silence
        self.saved_text = text


DOC = [["Page one, first paragraph.", "Page one, second."], ["Page two."], ["Page three has this. And that."]]


def test_reads_in_order_with_options():
    b = Rec()
    r = speech.ReadAloud(FakeDoc(DOC), backend=b, rate=1.25, voice="v", language="en")
    seen = []
    r.on_paragraph = lambda p: seen.append((p.page, p.index))
    r.play()
    assert [s[0] for s in b.spoken] == ["Page one, first paragraph.", "Page one, second.", "Page two.",
                                        "Page three has this. And that."]
    assert b.spoken[0][1:] == (1.25, "v", "en") and seen == [(1, 0), (1, 1), (2, 2), (3, 3)]
    assert r.position == 4 and not r.playing


def test_pages_selection_and_start_page():
    b = Rec()
    speech.ReadAloud(FakeDoc(DOC), backend=b, pages=[2, 3]).play()
    assert [s[0] for s in b.spoken][0] == "Page two."
    b2 = Rec()
    speech.ReadAloud(FakeDoc(DOC), backend=b2, start_page=3).play()
    assert len(b2.spoken) == 2 or [s[0] for s in b2.spoken] == ["Page three has this. And that."]


def test_long_paragraph_is_chunked_but_text_is_complete():
    b = Rec()
    text = " ".join(f"Sentence number {i}." for i in range(40))
    speech.ReadAloud(FakeDoc([[text]]), backend=b, max_chars=100).play()
    assert len(b.spoken) > 3 and all(len(s[0]) <= 100 for s in b.spoken)
    assert " ".join(s[0] for s in b.spoken) == text


def test_stop_pause_resume_forward_back():
    b = Rec(delay=5.0)
    r = speech.ReadAloud(FakeDoc(DOC), backend=b)
    r.play(wait=False)
    time.sleep(0.2)
    assert r.playing and len(b.spoken) == 1
    r.pause()
    assert not r.playing and r.position == 0                       # stays on the paragraph that was being read
    r.forward()
    assert r.position == 1
    r.forward(10)
    assert r.position == 3                                          # clamped to the last paragraph
    r.back(99)
    assert r.position == 0
    b.delay = 0
    r.play(from_paragraph=2)
    assert [s[0] for s in b.spoken][-2:] == ["Page two.", "Page three has this. And that."]


def test_forward_while_playing_continues():
    b = Rec(delay=5.0)
    r = speech.ReadAloud(FakeDoc(DOC), backend=b)
    r.play(wait=False)
    time.sleep(0.2)
    r.forward()
    time.sleep(0.3)
    assert r.playing and b.spoken[-1][0] == "Page one, second."
    r.stop()


def test_words_have_page_rectangles():
    r = speech.ReadAloud(FakeDoc(DOC), backend=Rec())
    ws = r.words(0)
    assert [w.text for w in ws] == ["Page", "one", "first", "paragraph"]
    assert ws[0].rect == [0.0, 0.0, 20.0, 10.0] and ws[0].page == 1 and ws[0].paragraph == 0
    assert r.paragraphs[0].rects == [0.0, 0.0, 10.0, 10.0] and r.seconds() > 0


def test_simulated_word_events_are_timed():
    got = []
    b = Rec(delay=0.6)
    r = speech.ReadAloud(FakeDoc([["alpha beta gamma delta"]]), backend=b, rate=3.0, on_word=lambda w: got.append(w.text))
    t = threading.Timer(0.5, b.release.set)                         # speech "ends" after 0.5 s
    t.start()
    r.play()
    assert got[:1] == ["alpha"] and got == ["alpha", "beta", "gamma", "delta"][:len(got)]


def test_exact_word_events_from_pyttsx3(monkeypatch):
    class Eng:
        def __init__(self): self.cb, self.props = None, {}
        def setProperty(self, k, v): self.props[k] = v
        def getProperty(self, k): return []
        def connect(self, ev, cb): self.cb = cb
        def say(self, text): self.text = text
        def runAndWait(self):
            if self.cb:
                for s, e, _ in speech.words(self.text):
                    self.cb("w", s, e - s)
        def stop(self): pass
    fake = types.ModuleType("pyttsx3"); fake.init = lambda: Eng()
    monkeypatch.setitem(sys.modules, "pyttsx3", fake)
    b = speech.Pyttsx3Backend()
    assert b.available() and b.word_events
    got = []
    long = " ".join(["word%d" % i for i in range(30)]) + "."
    r = speech.ReadAloud(FakeDoc([[long]]), backend=b, max_chars=60, on_word=lambda w: got.append(w.text))
    r.play()
    assert got == ["word%d" % i for i in range(30)]                  # every word exactly once, across chunks


def test_errors_inside_the_backend_surface():
    class Boom(Rec):
        def speak(self, text, **kw):
            raise PdfCraftError("device busy")
    with pytest.raises(PdfCraftError, match="device busy"):
        speech.ReadAloud(FakeDoc(DOC), backend=Boom()).play()


def test_save_audio(tmp_path):
    r = speech.ReadAloud(FakeDoc(DOC), backend=Rec())
    res = r.save(tmp_path / "out" / "a.wav")
    assert res.out.endswith("a.wav") and res.seconds == 2.0 and res.paragraphs == 4 and res.engine == "rec"
    assert r.backend.saved_text.startswith("Page one, first paragraph.\n\nPage one, second.")
    with pytest.raises(PdfCraftError, match="nothing to read"):
        speech.ReadAloud(FakeDoc([[]]), backend=Rec()).save(tmp_path / "x.wav")


def test_public_functions_exist():
    for n in ("read_aloud", "to_audio", "reading_text", "voices", "ReadAloud"):
        assert callable(getattr(pdf, n))
    assert pdf.search("speak") and "read_aloud" in pdf.search("aloud")[0][1]
