"""The OCR model files used by pypdfcraft (CC-BY-SA-4.0, by Robert Knight / ocrs-models)."""
import os

__version__ = "0.1.0"


def models_dir():
    """Folder containing ``text-detection.rten`` and ``text-recognition.rten``."""
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    if not os.path.isfile(os.path.join(d, "text-recognition.rten")):
        raise FileNotFoundError("model files missing from this installation")
    return d
