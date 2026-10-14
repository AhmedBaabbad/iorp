"""Real files for upload tests (PROJECT-FILES-003): uploads are opened and made small, so a fake header is not enough."""
from io import BytesIO
import random

from PIL import Image


def png(size=(8, 8), color="#24556b") -> bytes:
    out = BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


def photo(size=(4000, 3000), exif=True) -> bytes:
    """A camera-like JPEG: large, noisy (so it does not compress to nothing), with EXIF (camera, GPS)."""
    rng = random.Random(7)
    # Like a photo: smooth light and shapes with sensor grain (pure noise compresses like no real picture does).
    base = Image.linear_gradient("L").resize(size).convert("RGB")
    image = Image.blend(base, Image.effect_noise(size, 12).convert("RGB"), 0.2)
    image.paste((rng.randrange(256), 90, 40), (size[0] // 4, size[1] // 4, size[0] // 2, size[1] // 2))
    out = BytesIO()
    if exif:
        data = Image.Exif()
        data[0x010F] = "PhoneMaker"   # Make
        data[0x0110] = "Model X"      # Model
        data[0x0112] = 1              # Orientation
        image.save(out, "JPEG", quality=95, exif=data.tobytes())
    else:
        image.save(out, "JPEG", quality=95)
    return out.getvalue()


def pdf(body: bytes = b"signed note") -> bytes:
    return b"%PDF-1.7\n" + body + b"\n%%EOF\n"
