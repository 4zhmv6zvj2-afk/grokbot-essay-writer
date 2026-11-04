"""Read words from a photo inside the essay flow.

Cursor and Grok Build both call prepare_photo. The running model sees the
image and returns the words. This module does not shell out to a separate
reader, and it does not invent words for an empty or damaged photo.
"""

from __future__ import annotations

from pathlib import Path

from essay_writer.canon import file_sha256

SOURCE = "essay_writer.vision.prepare_photo"
MAX_PHOTO_BYTES = 2_000_000
MAX_READING_CHARS = 200_000

PHOTO_PROMPT = (
    "Read every word visible in this photo, including headings and handwriting. "
    "Return only those words. Do not add anything that is not visible."
)

_EMPTY = "This photo is empty, so there is no text to file."
_DAMAGED = "This photo is damaged, so I can't read any words from it."
_NOT_PHOTO = "This file isn't a photo I can read. Use a PNG, JPEG, GIF, or WEBP picture."
_TOO_BIG = "This photo is too large to read."
_NO_WORDS = "I couldn't read any words in this photo, so I didn't file it."
_NOT_TEXT = "The words from the photo have to be text."
_TOO_LONG = "Those words are too long to file with the module."
_NO_SAVED = "this photo has no saved words yet"

_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_UNSUPPORTED = frozenset({".heic", ".heif", ".bmp", ".tif", ".tiff"})
_REASON = {"empty": _EMPTY, "damaged": _DAMAGED, "not": _NOT_PHOTO}


def is_image_suffix(suffix: str) -> bool:
    return suffix.lower() in _MEDIA


def is_photo_name(name: str) -> bool:
    suffix = Path(name).suffix.lower()
    return suffix in _MEDIA or suffix in _UNSUPPORTED


def photo_words_path(image: Path) -> Path:
    """Text filed beside the photo. The essay flow reads this."""
    return Path(str(image) + ".txt")


def saved_photo_words(path: Path) -> str:
    sidecar = photo_words_path(path)
    if not sidecar.is_file():
        raise ValueError(_NO_SAVED)
    text = sidecar.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(_NO_SAVED)
    return text


def clean_reading(reading: object) -> tuple[str | None, str | None]:
    """Return (words, error). Missing words are (None, None), not an error."""
    if reading is None:
        return None, None
    if not isinstance(reading, str):
        return None, _NOT_TEXT
    text = reading.strip()
    if not text:
        return None, _NO_WORDS
    if len(text) > MAX_READING_CHARS:
        return None, _TOO_LONG
    return text, None


def photo_problem(path: Path) -> str | None:
    """Plain-English reason to refuse, or None when the photo can be shown."""
    suffix = path.suffix.lower()
    if suffix in _UNSUPPORTED:
        return _NOT_PHOTO
    if suffix not in _MEDIA:
        return _NOT_PHOTO
    size = path.stat().st_size
    if size == 0:
        return _EMPTY
    if size > MAX_PHOTO_BYTES:
        return _TOO_BIG
    status = _status(suffix, path.read_bytes())
    if status == "ok":
        return None
    return _REASON[status]


def prepare_photo(path: Path) -> dict[str, object]:
    """Payload the model sees. Intake and Grok Build both call this."""
    if not path.is_file():
        return {"ok": False, "reason": "That photo isn't there.", "source": SOURCE, "name": path.name}
    reason = photo_problem(path)
    if reason:
        return {"ok": False, "reason": reason, "source": SOURCE, "name": path.name}
    return {
        "ok": True,
        "source": SOURCE,
        "name": path.name,
        "media_type": _MEDIA[path.suffix.lower()],
        "sha256": file_sha256(path),
        "bytes": path.stat().st_size,
        "prompt": PHOTO_PROMPT,
        "show_image": str(path.resolve()),
    }


def _status(suffix: str, data: bytes) -> str:
    if suffix == ".png":
        return _png_status(data)
    if suffix in {".jpg", ".jpeg"}:
        return _jpeg_status(data)
    if suffix == ".gif":
        return _gif_status(data)
    if suffix == ".webp":
        return _webp_status(data)
    return "not"


def _png_status(data: bytes) -> str:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "not"
    if len(data) < 24 or data[12:16] != b"IHDR":
        return "damaged"
    if int.from_bytes(data[8:12], "big") != 13:
        return "damaged"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width == 0 or height == 0:
        return "empty"
    if b"IEND" not in data:
        return "damaged"
    return "ok"


def _gif_status(data: bytes) -> str:
    if data[:6] not in {b"GIF87a", b"GIF89a"}:
        return "not"
    if len(data) < 13:
        return "damaged"
    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    if width == 0 or height == 0:
        return "empty"
    return "ok"


def _webp_status(data: bytes) -> str:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return "not"
    if len(data) <= 12:
        return "empty"
    return "ok"


def _jpeg_status(data: bytes) -> str:
    if not data.startswith(b"\xff\xd8"):
        return "not"
    if len(data) < 4 or not data.endswith(b"\xff\xd9"):
        return "damaged"
    index = 2
    while index + 3 < len(data):
        if data[index] != 0xFF:
            return "damaged"
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            return "damaged"
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            return "damaged"
        segment = int.from_bytes(data[index : index + 2], "big")
        if segment < 2 or index + segment > len(data):
            return "damaged"
        if marker in {0xC0, 0xC1, 0xC2}:
            if segment < 7:
                return "damaged"
            height = int.from_bytes(data[index + 3 : index + 5], "big")
            width = int.from_bytes(data[index + 5 : index + 7], "big")
            if width == 0 or height == 0:
                return "empty"
            return "ok"
        index += segment
    return "damaged"
