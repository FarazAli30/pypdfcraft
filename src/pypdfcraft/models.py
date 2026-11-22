"""OCR models.

The engine's OCR needs two model files (``text-detection.rten`` and ``text-recognition.rten``,
CC-BY-SA-4.0, ~12 MB).  They are not inside the .so: the Android app ships them as APK assets and
points the engine at them with the environment variable PDFCRAFT_MODELS.  This module does the same.

    import pypdfcraft as pdf
    pdf.install_models()                         # download from the project's GitHub repo
    # or:  pip install "pypdfcraft[ocr]"         # ships the models as a separate wheel
    pdf.install_models(apk="/sdcard/pdfcraft.apk")   # or take them from the APK you extracted the .so from
"""
import hashlib
import os
import shutil
import urllib.request
import zipfile

NAMES = ("text-detection.rten", "text-recognition.rten")
EXTRA = ("text-detection.rten.LICENCE.txt", "text-recognition.rten.LICENCE.txt", "ATTRIBUTION.txt")
# Same sources and checksums as the upstream project's fetch-models.sh.
MODEL_URL = "https://ocrs-models.s3-accelerate.amazonaws.com/"
FALLBACK_URL = "https://raw.githubusercontent.com/artcraft-android/pdfcraft-android/main/assets/models/"
SHA256 = {
    "text-detection.rten": "f15cfb56bd02c4bf478a20343986504a1f01e1665c2b3a0ad66340f054b1b5ca",
    "text-recognition.rten": "e484866d4cce403175bd8d00b128feb08ab42e208de30e42cd9889d8f1735a6e",
}
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt"
LICENCE_SHA256 = "28a9529c7d0bb4dc51f4bf5c116a3d16ef247a052f7591466768ddf563fd1cf5"
ATTRIBUTION = """PdfCraft's text recognition (Scan & OCR) uses these models, unmodified.

{files}
  by Robert Knight (ocrs-models; trained on HierText, CC-BY-SA-4.0)
  from https://github.com/robertknight/ocrs-models (model card: https://huggingface.co/robertknight/ocrs, cc-by-sa-4.0)
  licence: CC-BY-SA-4.0 ({licence}; full text in <model>.LICENCE.txt)
"""


def _have(d):
    return bool(d) and all(os.path.isfile(os.path.join(d, n)) and os.path.getsize(os.path.join(d, n)) > 0 for n in NAMES)


def default_dir():
    return os.path.join(os.path.expanduser("~"), ".pypdfcraft", "models")


def _package_dir():
    """Folder of the optional ``pypdfcraft-ocr-models`` wheel (``pip install pypdfcraft[ocr]``)."""
    try:
        import pypdfcraft_ocr_models
        return pypdfcraft_ocr_models.models_dir()
    except Exception:                                   # noqa: BLE001
        return None


def _candidates():
    here = os.path.dirname(os.path.abspath(__file__))
    return [os.environ.get("PDFCRAFT_MODELS"), _package_dir(), os.path.join(here, "models"),
            os.path.join(os.path.dirname(here), "models"), os.path.join(os.getcwd(), "models"),
            default_dir(), os.path.join(os.path.expanduser("~"), "pdfcraft_models")]


def find_dir():
    return next((d for d in _candidates() if _have(d)), None)


def set_dir(path):
    """Point the engine at a folder containing the two .rten files."""
    path = os.path.abspath(os.path.expanduser(str(path)))
    if not _have(path):
        raise FileNotFoundError(f"{path} must contain {', '.join(NAMES)}")
    os.environ["PDFCRAFT_MODELS"] = path
    try:                                   # make sure the C environment (read by Rust) sees it too
        import ctypes
        ctypes.CDLL(None).setenv(b"PDFCRAFT_MODELS", path.encode(), 1)
    except Exception:                      # noqa: BLE001
        pass
    return path


def ensure_env():
    """Called before the engine starts: use any models folder we can find."""
    d = find_dir()
    if d:
        set_dir(d)
    return d


def status():
    d = find_dir()
    return f"found in {d}" if d else "not installed (call pypdfcraft.install_models())"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_text(path):
    """SHA-256 of a text file with line endings normalised to LF (a Windows git checkout may have made them CRLF)."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()


def _copy_text(src, dst):
    """Copy a text file, writing LF line endings."""
    with open(src, "rb") as f, open(dst, "wb") as g:
        g.write(f.read().replace(b"\r\n", b"\n"))


USER_AGENT = "pypdfcraft (+https://github.com/FarazAli30/pypdfcraft)"


def _http_get(url, target):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(target, "wb") as f:
        shutil.copyfileobj(r, f)


def _download(urls, target, sha, progress):
    """Download the first working URL to ``target`` (checked by SHA-256; kept if already correct)."""
    if os.path.isfile(target) and _sha256(target) == sha:
        return
    last = None
    for url in urls:
        tmp = target + ".part"
        try:
            progress(f"downloading {os.path.basename(target)} ...")
            _http_get(url, tmp)
            if _sha256(tmp) != sha:
                raise ValueError(f"checksum mismatch for {url}")
            os.replace(tmp, target)
            return
        except Exception as e:                           # noqa: BLE001
            last = e
            if os.path.exists(tmp):
                os.remove(tmp)
    raise OSError(f"could not download {os.path.basename(target)}: {last}")


def licence_path():
    """The CC-BY-SA-4.0 legal text shipped inside this package (no download needed)."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "CC-BY-SA-4.0.txt")


def fetch(dest, progress=print):
    """Download the two models (+ licence and attribution notes) into ``dest``, verified by SHA-256."""
    os.makedirs(dest, exist_ok=True)
    licence = licence_path()
    if not (os.path.isfile(licence) and _sha256_text(licence) == LICENCE_SHA256):          # packaged copy missing/damaged
        licence = os.path.join(dest, "LICENCE.part.txt")
        _download([LICENCE_URL], licence, LICENCE_SHA256, progress)
    for name, sha in SHA256.items():
        _download([MODEL_URL + name, FALLBACK_URL + name], os.path.join(dest, name), sha, progress)
        _copy_text(licence, os.path.join(dest, name + ".LICENCE.txt"))
    if licence.endswith("LICENCE.part.txt"):
        os.remove(licence)
    with open(os.path.join(dest, "ATTRIBUTION.txt"), "w", encoding="utf-8") as f:
        f.write(ATTRIBUTION.format(files="\n".join(SHA256), licence=LICENCE_URL))
    return dest


def install_models(dest=None, apk=None, progress=print):
    """Make OCR available.  ``apk``: path of the PdfCraft APK to take the models from (offline);
    otherwise they are downloaded from GitHub.  Returns the folder and activates it."""
    dest = os.path.abspath(os.path.expanduser(str(dest or default_dir())))
    os.makedirs(dest, exist_ok=True)
    if apk:
        with zipfile.ZipFile(apk) as z:
            for info in z.infolist():
                base = os.path.basename(info.filename)
                if "/models/" in "/" + info.filename and base in NAMES + EXTRA:
                    with z.open(info) as src, open(os.path.join(dest, base), "wb") as out:
                        shutil.copyfileobj(src, out)
                    progress(f"extracted {base}")
    else:
        fetch(dest, progress)
    if not _have(dest):
        raise FileNotFoundError(f"models not found in {'the APK' if apk else 'the download'}")
    return set_dir(dest)
