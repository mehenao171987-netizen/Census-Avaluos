"""Procesamiento de imágenes: validación de firma binaria, eliminación de metadatos y edición."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

MAX_PIXELS = 40_000_000
MAX_SIDE = 4096


class ImageError(ValueError):
    pass


def detect_format(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def validate_upload(data: bytes, max_mb: int) -> str:
    if len(data) > max_mb * 1024 * 1024:
        raise ImageError(f"El archivo supera {max_mb} MB.")
    fmt = detect_format(data)
    if fmt is None:
        raise ImageError("Formato no permitido. Use JPG, PNG o WEBP.")
    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
        with Image.open(BytesIO(data)) as im:
            if im.width * im.height > MAX_PIXELS:
                raise ImageError("La resolución es demasiado alta.")
    except ImageError:
        raise
    except Exception as exc:
        raise ImageError("El archivo no es una imagen válida.") from exc
    return fmt


def load_clean(data: bytes) -> Image.Image:
    """Abre la imagen, corrige orientación y reconstruye los píxeles para eliminar EXIF/GPS/XMP."""
    with Image.open(BytesIO(data)) as im:
        im = ImageOps.exif_transpose(im)
        mode = "RGBA" if "A" in im.getbands() else "RGB"
        converted = im.convert(mode)
        return Image.frombytes(mode, converted.size, converted.tobytes())


def open_bytes(data: bytes) -> Image.Image:
    im = Image.open(BytesIO(data))
    im.load()
    return im


def apply_edits(img: Image.Image, *, rotate: int = 0, flip_h: bool = False,
                crop: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
                brightness: float = 1.0, contrast: float = 1.0, sharpness: float = 1.0,
                grayscale: bool = False, blur: float = 0.0, max_side: int = MAX_SIDE) -> Image.Image:
    out = img
    if rotate:
        out = out.rotate(-rotate, expand=True)  # rotación horaria
    if flip_h:
        out = ImageOps.mirror(out)
    left, top, right, bottom = crop
    w, h = out.size
    box = (int(left * w), int(top * h), int(right * w), int(bottom * h))
    if box[2] - box[0] < 10 or box[3] - box[1] < 10:
        raise ImageError("El recorte es demasiado pequeño.")
    out = out.crop(box)
    if grayscale:
        out = ImageOps.grayscale(out).convert("RGB")
    if brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(brightness)
    if contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(contrast)
    if sharpness != 1.0:
        out = ImageEnhance.Sharpness(out).enhance(sharpness)
    if blur:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    if max(out.size) > max_side:
        out.thumbnail((max_side, max_side))
    return out


def to_png(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
