"""Copy-only Mac handoff and keep-existing 4b reviews. Stable ids: AC1–AC4."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from docx import Document
from helpers import mac_handoff_sequence_dir, open_sequence, plant_gathered_source

from essay_writer import build_office, cursor_office
from essay_writer.first_run import main as first_run_main
from essay_writer.harvard_4a import harvard_4a_line
from essay_writer.research_packs import bibliography_sources, ship_4b
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


def test_ac4_build_covered_copy_only_handoff_and_keep_existing_ship_4b(
    workspace, tmp_path, monkeypatch
):
    """AC4. Build covered. Cursor and Grok Build / first_run share the copy-only handoff and ship_4b."""
    assert researcher.ship_4b is ship_4b

    mac = tmp_path / "mac"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    seq = open_sequence()
    out = _output(workspace)
    out.mkdir(parents=True)
    cli_args: list[list[str]] = []

    def spy_first_run(argv=None):
        cli_args.append(list(argv) if argv is not None else [])
        return first_run_main(argv)

    # server.main imports essay_writer.first_run.main when it sees the flag.
    monkeypatch.setattr("essay_writer.first_run.main", spy_first_run)
    with pytest.raises(SystemExit) as caught:
        server_main(["--copy-to-mac", str(out)])
    assert caught.value.code == 0
    assert cli_args == [["--copy-to-mac", str(out)]]

    plant_gathered_source(seq)
    expected_sources = bibliography_sources(seq)
    ship_calls: list[tuple[str, list[dict[str, object]], object]] = []

    def spy_ship_4b(essay_id, sources, supplied):
        ship_calls.append((essay_id, list(sources), supplied))
        return ship_4b(essay_id, sources, supplied)

    monkeypatch.setattr("essay_writer.research_packs.ship_4b", spy_ship_4b)
    researcher.deliver_critical_reviews(seq)
    assert ship_calls == [(seq, expected_sources, None)]
    monkeypatch.setattr("essay_writer.research_packs.ship_4b", ship_4b)

    deliver_calls: list[str] = []
    real_deliver = researcher.deliver_critical_reviews

    def spy_deliver(essay_id):
        deliver_calls.append(essay_id)
        return real_deliver(essay_id)

    monkeypatch.setattr(
        "essay_writer.specialists.researcher.deliver_critical_reviews",
        spy_deliver,
    )
    stage_critical_reviews(seq)
    assert deliver_calls == [seq]

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
