"""Rendered pixels with convenient conversions (no dependencies required)."""
import struct
import zlib


def _png_bytes(width, height, rgba_straight):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: none
        raw += rgba_straight[y * stride:(y + 1) * stride]
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


class Image:
    """A rendered page (or tile): ``width`` x ``height`` pixels, ``rgba`` bytes.

    The engine delivers *premultiplied* RGBA8; ``straight_rgba()`` un-premultiplies it.
    """

    def __init__(self, width, height, rgba):
        self.width, self.height, self.rgba = int(width), int(height), bytes(rgba)

    @classmethod
    def _from_native(cls, r):
        return cls(r.width, r.height, r.rgba)

    # -- conversions ---------------------------------------------------------
    def straight_rgba(self):
        data = self.rgba
        if data[3::4].count(255) == self.width * self.height:   # fully opaque: nothing to do
            return data
        try:
            import numpy as np
            a = np.frombuffer(data, np.uint8).reshape(-1, 4).astype(np.uint32)
            alpha = a[:, 3:4]
            rgb = np.where(alpha > 0, np.minimum(255, (a[:, :3] * 255 + alpha // 2) // np.maximum(alpha, 1)), 0)
            return np.concatenate([rgb, alpha], axis=1).astype(np.uint8).tobytes()
        except ImportError:
            out = bytearray(data)
            for i in range(0, len(out), 4):
                al = out[i + 3]
                if 0 < al < 255:
                    for k in range(3):
                        out[i + k] = min(255, (out[i + k] * 255 + al // 2) // al)
                elif al == 0:
                    out[i] = out[i + 1] = out[i + 2] = 0
            return bytes(out)

    def to_numpy(self):
        """``(height, width, 4)`` uint8 array (straight alpha). Needs numpy."""
        import numpy as np
        return np.frombuffer(self.straight_rgba(), np.uint8).reshape(self.height, self.width, 4)

    def to_pil(self):
        """A ``PIL.Image`` (RGBA). Needs Pillow."""
        from PIL import Image as PILImage
        return PILImage.frombytes("RGBA", (self.width, self.height), self.straight_rgba())

    def to_png_bytes(self):
        return _png_bytes(self.width, self.height, self.straight_rgba())

    def save(self, path):
        """Save as PNG (built in) or any format Pillow supports (by extension)."""
        path = str(path)
        if path.lower().endswith(".png"):
            with open(path, "wb") as f:
                f.write(self.to_png_bytes())
        else:
            im = self.to_pil()
            if path.lower().endswith((".jpg", ".jpeg")):
                im = im.convert("RGB")
            im.save(path)
        return path

    def _repr_png_(self):            # shows inline in Jupyter
        return self.to_png_bytes()

    def __repr__(self):
        return f"<pypdfcraft.Image {self.width}x{self.height}>"
