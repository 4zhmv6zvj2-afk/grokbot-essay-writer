"""Copy-only Mac handoff and keep-existing 4b reviews. Stable ids: AC1–AC4."""

from __future__ import annotations

import inspect
import io
import json
import zipfile
from pathlib import Path

from docx import Document
from helpers import mac_handoff_sequence_dir, open_sequence, plant_gathered_source

from essay_writer import build_office, cursor_office
from essay_writer.build_office import _stage_files, build_deliverable_handoff
from essay_writer.first_run import main as first_run_main
from essay_writer.harvard_4a import harvard_4a_line
from essay_writer.research_packs import ship_4b
from essay_writer.server import HANDLERS
from essay_writer.server import main as server_main
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists import researcher
from essay_writer.spine import stage_critical_reviews

LONG = (
    "The corridor limit is argued across several pages, not as a citation line alone.\n"
    "UNIQUE-KEEP-4B-REVIEW The firm has to treat the chokepoint as the constraint "
    "on the whole route, including the weeks when traffic bunches at the strait.\n"
    "A later reader can still find this full note after the pack is zipped again.\n"
)
SOURCE = {
    "id": "src-1",
    "author": "Smith, J.",
    "year": "2020",
    "title": "Chokepoints and crude",
}


def _output(workspace: Path) -> Path:
    return workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "output"


def _docx_text(payload: bytes) -> str:
    return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(payload)).paragraphs)


def _zip_body(path: Path, name: str = "src-1.docx") -> str:
    with zipfile.ZipFile(path) as archive:
        return _docx_text(archive.read(name))


def _refuse_writers(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("sequence copy must not write stage files")

    monkeypatch.setattr(build_office, "write_stage_deliverables", boom)
    monkeypatch.setattr(researcher, "deliver_saved_sources", boom)
    monkeypatch.setattr("essay_writer.research_packs.ship_4b", boom)
    monkeypatch.setattr("essay_writer.research_packs.ship_4a", boom)


def test_ac1_copy_to_mac_copies_existing_files_only(workspace, tmp_path, monkeypatch, capsys):
    """AC1. Sequence --copy-to-mac does not write stage files. It copies the four that exist."""
    mac = tmp_path / "mac"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    seq = open_sequence()
    plant_gathered_source(seq)
    out = _output(workspace)
    reviews = out / "reviews"
    reviews.mkdir(parents=True)
    (out / "annotation.docx").write_bytes(b"ann-bytes-keep")
    (out / "critical-reviews.zip").write_bytes(b"zip-bytes-keep")
    (out / "other.docx").write_bytes(b"not-a-stage-file")
    review = reviews / "src-1.md"
    review.write_text(LONG, encoding="utf-8")
    _refuse_writers(monkeypatch)

    code = first_run_main(["--copy-to-mac", str(out)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["handoff"] == "stage-deliverables"
    assert payload["deliverables"] == ["annotation.docx", "critical-reviews.zip"]
    assert review.read_text(encoding="utf-8") == LONG
    assert (out / "annotation.docx").read_bytes() == b"ann-bytes-keep"
    assert (out / "critical-reviews.zip").read_bytes() == b"zip-bytes-keep"
    assert not (out / "download-list.docx").exists()
    assert not (out / "papers.zip").exists()

    copied = mac_handoff_sequence_dir(mac, seq)
    assert (copied / "annotation.docx").read_bytes() == b"ann-bytes-keep"
    assert (copied / "critical-reviews.zip").read_bytes() == b"zip-bytes-keep"
    assert not (copied / "download-list.docx").exists()
    assert not (copied / "papers.zip").exists()
    assert not (copied / "other.docx").exists()
    assert "write_stage_deliverables(" not in inspect.getsource(build_deliverable_handoff)
    assert "write_stage_deliverables(" not in inspect.getsource(_stage_files)


def test_ac2_ship_4b_keeps_existing_long_review(workspace):
    """AC2. ship_4b(supplied=None) leaves a long review markdown and its zip body."""
    seq = open_sequence()
    review = _output(workspace) / "reviews" / "src-1.md"
    review.parent.mkdir(parents=True)
    review.write_text(LONG, encoding="utf-8")
    before = review.read_bytes()

    first = ship_4b(seq, [SOURCE], None)
    assert review.read_bytes() == before
    body = _zip_body(_output(workspace) / "critical-reviews.zip")
    assert "UNIQUE-KEEP-4B-REVIEW" in body
    assert first["reviews"][0]["markdown_path"].endswith("src-1.md")

    again = ship_4b(seq, [SOURCE], None)
    assert review.read_bytes() == before
    assert _zip_body(_output(workspace) / "critical-reviews.zip") == body
    assert again["reviews"][0]["opened"] is True


def test_ac3_ship_4b_stubs_only_when_review_is_absent(workspace):
    """AC3. ship_4b(supplied=None) writes the citation-line stub only when the markdown is missing."""
    seq = open_sequence()
    review = _output(workspace) / "reviews" / "src-1.md"
    assert not review.exists()
    delivered = ship_4b(seq, [SOURCE], None)
    text = review.read_text(encoding="utf-8")
    line = harvard_4a_line(SOURCE)
    assert line in text
    assert "Critical note:" in text
    assert "UNIQUE-KEEP-4B-REVIEW" not in text
    assert len(text) < 400
    assert delivered["reviews_zip"]["name"] == "critical-reviews.zip"
    body = _zip_body(_output(workspace) / "critical-reviews.zip")
    assert line in body
    assert "UNIQUE-KEEP-4B-REVIEW" not in body


def test_ac4_build_covered_copy_only_handoff_and_keep_existing_ship_4b():
    """AC4. Build covered. Cursor and Grok Build / first_run share the copy-only handoff and ship_4b."""
    handoff_src = inspect.getsource(build_deliverable_handoff)
    stage_src = inspect.getsource(_stage_files)
    ship_src = inspect.getsource(ship_4b)
    assert "write_stage_deliverables(" not in handoff_src
    assert "write_stage_deliverables(" not in stage_src
    assert "supplied is None and md_path.is_file()" in ship_src
    assert "build_deliverable_handoff" in inspect.getsource(first_run_main)
    assert "first_run_main" in inspect.getsource(server_main)
    assert researcher.ship_4b is ship_4b
    assert "ship_4b(essay_id, sources, None)" in inspect.getsource(researcher.deliver_critical_reviews)
    assert "deliver_critical_reviews" in inspect.getsource(stage_critical_reviews)

    cursor_src = Path(cursor_office.__file__).read_text(encoding="utf-8")
    build_src = Path(build_office.__file__).read_text(encoding="utf-8")
    assert "def ship_4b" not in cursor_src
    assert "def ship_4b" not in build_src
    assert "def build_deliverable_handoff" not in cursor_src
    assert build_src.count("def build_deliverable_handoff") == 1

    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert cursor_shell()["handlers"]["essay.research.full"] is HANDLERS["essay.research.full"]
    assert front_office()["handlers"]["essay.research.full"] is HANDLERS["essay.research.full"]

