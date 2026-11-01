"""A photo dropped into intake becomes words the essay flow can use."""

import base64
import json
import struct
import zlib

import pytest
from helpers import ESSAY, TOPIC, open_sequence, source
from mcp.server.mcpserver.utilities.types import Image

from essay_writer.build_office import photo_vision
from essay_writer.intake import essay_intake
from essay_writer.invent import read_gathered_text
from essay_writer.originals import essay_originals
from essay_writer.paths import uploads_dir
from essay_writer.research import essay_research_summary
from essay_writer.server import intake_with_image
from essay_writer.server import main as server_main
from essay_writer.vision import PHOTO_PROMPT, SOURCE, prepare_photo

WORDS = (
    "Assignment brief.\n"
    "Smith, J. (2020) Chokepoints and crude.\n"
    "The Strait handles a large share of flows.\n"
    "The door of the warehouse is on the brief.\n"
)
BANNED = ("OCR", "ocr", "mid office", "mid-office", "EQR", "vision", "Grok", "Cursor")


def _chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def _png(width: int = 1, height: int = 1) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    rows = b"".join(b"\x00" + (b"\xff\x00\x00" * width) for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")


def _jpeg(width: int = 1, height: int = 1) -> bytes:
    body = struct.pack(">BHHB", 8, height, width, 1) + bytes([1, 0x11, 0])
    sof = b"\xff\xc0" + struct.pack(">H", len(body) + 2) + body
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _gif(width: int = 1, height: int = 1) -> bytes:
    return b"GIF89a" + struct.pack("<HHBBB", width, height, 0, 0, 0)


def _webp() -> bytes:
    return b"RIFF" + struct.pack("<I", 8) + b"WEBP" + b"VP8 "


def _drop(workspace, name: str, data: bytes):
    folder = workspace / "unassigned"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return path


def _quiet(body: dict) -> None:
    for key in ("next", "reason"):
        text = body.get(key)
        if not isinstance(text, str):
            continue
        for banned in BANNED:
            assert banned not in text


def test_photo_words_are_filed_and_the_essay_can_use_them(workspace):
    png = _png()
    _drop(workspace, "brief.png", png)
    seen = essay_intake("brief.png", "draft", ESSAY)
    assert seen["ok"] is True
    assert seen["needs_reading"] is True
    assert seen["wrote"] is False
    assert seen["source"] == SOURCE
    assert seen["prompt"] == PHOTO_PROMPT
    assert seen["media_type"] == "image/png"
    assert "digest" not in seen
    _quiet(seen)
    shown = intake_with_image("brief.png", "draft", ESSAY)
    assert isinstance(shown, list)
    body, image = shown
    assert body["needs_reading"] is True
    assert isinstance(image, Image)
    content = image.to_image_content()
    assert content.mime_type == "image/png"
    assert base64.b64decode(content.data) == png

    preview = essay_intake("brief.png", "draft", ESSAY, reading=WORDS)
    assert preview["wrote"] is False
    assert preview["needs_reading"] is False
    assert preview["reading"] == WORDS.strip()
    assert "door" in preview["reading"]
    _quiet(preview)
    assert (workspace / "unassigned" / "brief.png").is_file()

    filed = essay_intake("brief.png", "confirm", ESSAY, reading=WORDS)
    assert filed["ok"] is True
    assert filed["stored"] is True
    assert filed["wrote"] is True
    assert "door" in filed["reading"]
    _quiet(filed)
    image_path = uploads_dir(ESSAY) / "brief.png"
    text_path = uploads_dir(ESSAY) / "brief.png.txt"
    assert image_path.read_bytes() == png
    assert "The door of the warehouse is on the brief." in text_path.read_text(encoding="utf-8")
    assert not (workspace / "unassigned" / "brief.png").exists()

    read_image = essay_originals(ESSAY, "read", "brief.png")
    read_text = essay_originals(ESSAY, "read", "brief.png.txt")
    assert "Chokepoints and crude" in read_image["text"]
    assert read_text["text"] == read_image["text"]
    assert read_gathered_text(image_path) == text_path.read_text(encoding="utf-8")

    seq = open_sequence()
    item = source()
    item["locator"] = f"uploads/{ESSAY}/brief.png"
    draft = essay_research_summary(seq, TOPIC, "draft", [item])
    assert draft["ok"] is True
    assert draft["sources"][0]["quote"] == "The Strait handles a large share of flows."


def test_empty_and_bad_photos_are_refused(workspace):
    _drop(workspace, "blank.png", b"")
    empty = essay_intake("blank.png", "draft", ESSAY, reading=WORDS)
    assert empty["ok"] is False
    assert empty["wrote"] is False
    assert "empty" in empty["reason"]
    _quiet(empty)
    assert (workspace / "unassigned" / "blank.png").is_file()
    assert not uploads_dir(ESSAY).exists() or not any(uploads_dir(ESSAY).glob("*"))

    _drop(workspace, "zero.png", _png(width=0, height=1))
    zero = essay_intake("zero.png", "confirm", ESSAY, reading="invented words")
    assert zero["ok"] is False
    assert "empty" in zero["reason"]
    assert (workspace / "unassigned" / "zero.png").is_file()

    _drop(workspace, "notes.png", b"this is not a photo")
    bad = essay_intake("notes.png", "draft", ESSAY)
    assert bad["ok"] is False
    assert "isn't a photo" in bad["reason"]
    _quiet(bad)
    assert (workspace / "unassigned" / "notes.png").is_file()

    _drop(workspace, "torn.png", b"\x89PNG\r\n\x1a\n")
    torn = essay_intake("torn.png", "draft", ESSAY)
    assert torn["ok"] is False
    assert "damaged" in torn["reason"]

    _drop(workspace, "scan.heic", b"not-really-heic")
    heic = essay_intake("scan.heic", "draft", ESSAY, reading=WORDS)
    assert heic["ok"] is False
    assert heic["stored"] is False

    _drop(workspace, "real.png", _png())
    blank_words = essay_intake("real.png", "draft", ESSAY, reading="  \n\t ")
    assert blank_words["ok"] is False
    assert "couldn't read any words" in blank_words["reason"]
    assert (workspace / "unassigned" / "real.png").is_file()
    skipped = essay_intake("real.png", "confirm", ESSAY)
    assert skipped["ok"] is False
    assert "Nothing was filed" in skipped["reason"]


def test_a_changed_reading_cannot_reuse_the_draft(workspace):
    _drop(workspace, "brief.png", _png())
    essay_intake("brief.png", "draft", ESSAY, reading="First reading of the brief.")
    refused = essay_intake("brief.png", "confirm", ESSAY, reading="A different reading.")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert (workspace / "unassigned" / "brief.png").is_file()


def test_build_photo_vision_is_the_shared_helper(tmp_path, capsys):
    assert photo_vision is prepare_photo
    photo = tmp_path / "brief.jpg"
    photo.write_bytes(_jpeg())
    payload = photo_vision(photo)
    assert payload == prepare_photo(photo)
    assert payload["ok"] is True
    assert payload["source"] == SOURCE
    assert payload["media_type"] == "image/jpeg"
    assert payload["prompt"] == PHOTO_PROMPT

    gif = tmp_path / "notes.gif"
    gif.write_bytes(_gif())
    assert prepare_photo(gif)["media_type"] == "image/gif"
    webp = tmp_path / "shot.webp"
    webp.write_bytes(_webp())
    assert prepare_photo(webp)["ok"] is True
    assert prepare_photo(tmp_path / "empty.gif")["ok"] is False
    (tmp_path / "empty.gif").write_bytes(_gif(0, 0))
    assert "empty" in prepare_photo(tmp_path / "empty.gif")["reason"]
    assert "isn't there" in prepare_photo(tmp_path / "missing.png")["reason"]

    server_main(["--read-photo", str(photo)])
    printed = json.loads(capsys.readouterr().out)
    assert printed == payload

    with pytest.raises(SystemExit) as caught:
        server_main(["--read-photo", str(tmp_path / "missing.png")])
    assert caught.value.code == 1
    refused = json.loads(capsys.readouterr().out)
    assert refused["ok"] is False
    assert refused["source"] == SOURCE

