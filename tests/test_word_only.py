"""Easy Word-only student deliverables. Stable ids: AC1–AC5."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from docx import Document
from helpers import (
    CLARIFY_OPEN,
    ESSAY,
    TOPIC,
    open_sequence,
    plant_gathered_source,
    source,
    write_upload,
)

from essay_writer.build_office import (
    build_deliverable_handoff,
    stage_launch,
    write_stage_deliverables,
)
from essay_writer.first_run import DELIVERABLE_SUFFIXES, copy_deliverable_to_mac
from essay_writer.research import essay_research_full
from essay_writer.server import INSTRUCTIONS
from essay_writer.specialists.grok_bot import STAGE_CONFIRM_EACH

REPO = Path(__file__).resolve().parents[1]
ANN = (
    'Smith (2020) argues the corridor is narrow. The authors confirm the limit. '
    'The paper says "The Strait handles a large share of flows."'
)
_STUDENT_MD = re.compile(
    r"(one markdown per paper|zip of those markdowns|\.md\b.*\bcritical|critical-review markdown file)",
    re.IGNORECASE,
)


def _output(workspace: Path, seq: str = "1") -> Path:
    return workspace / "Essay-writer" / ESSAY / "sequences" / seq / "output"


def _docx_text(payload: bytes) -> str:
    return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(payload)).paragraphs)


def _zip_has_only_suffixes(archive: zipfile.ZipFile, *suffixes: str) -> None:
    allowed = tuple(suffix.lower() for suffix in suffixes)
    for name in archive.namelist():
        assert name.lower().endswith(allowed), name


def test_ac1_stage_4b_zip_is_word_only_one_file_per_paper(workspace):
    """AC1. critical-reviews.zip holds one .docx per paper and no .md."""
    write_upload(workspace)
    seq = open_sequence()
    reviews = [{"paper_id": "src-1", "markdown": ANN}]
    essay_research_full(seq, TOPIC, "draft", [source()], clarify_context=CLARIFY_OPEN, reviews=reviews)
    confirmed = essay_research_full(
        seq,
        TOPIC,
        "confirm",
        [source()],
        clarify_context=CLARIFY_OPEN,
        reviews=reviews,
    )
    assert confirmed["stored"] is True
    folder = _output(workspace) / "reviews"
    assert (folder / "src-1.md").is_file()
    archive = zipfile.ZipFile(_output(workspace) / "critical-reviews.zip")
    assert archive.namelist() == ["src-1.docx"]
    _zip_has_only_suffixes(archive, ".docx")
    assert "The Strait handles a large share of flows." in _docx_text(archive.read("src-1.docx"))


def test_ac2_student_zips_and_mac_handoff_never_ship_markdown(workspace, tmp_path, monkeypatch):
    """AC2. Mac Essay Bot copies and student zips stay .docx/.pdf only."""
    assert ".md" not in DELIVERABLE_SUFFIXES
    seq = open_sequence()
    plant_gathered_source(seq)
    write_stage_deliverables(seq)
    out = _output(workspace)
    papers = zipfile.ZipFile(out / "papers.zip")
    _zip_has_only_suffixes(papers, ".pdf")
    reviews = zipfile.ZipFile(out / "critical-reviews.zip")
    _zip_has_only_suffixes(reviews, ".docx")
    assert not any(name.endswith(".md") for name in reviews.namelist())

    mac = tmp_path / "mac" / "Essay Bot"
    mac.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    copied = copy_deliverable_to_mac(out)
    assert copied["copied"] is True
    from helpers import mac_handoff_sequence_dir

    seq_mac = mac_handoff_sequence_dir(mac, seq)
    for path in seq_mac.iterdir():
        assert path.suffix.lower() in {".docx", ".zip"}
    for name in ("annotation.docx", "download-list.docx", "papers.zip", "critical-reviews.zip"):
        assert (seq_mac / name).is_file()


def test_ac3_student_speech_never_points_at_markdown_critical_reviews(workspace):
    """AC3. Confirm next and student-facing briefing avoid markdown critical-review paths."""
    write_upload(workspace)
    seq = open_sequence()
    reviews = [{"paper_id": "src-1", "markdown": ANN}]
    essay_research_full(seq, TOPIC, "draft", [source()], clarify_context=CLARIFY_OPEN, reviews=reviews)
    confirmed = essay_research_full(
        seq,
        TOPIC,
        "confirm",
        [source()],
        clarify_context=CLARIFY_OPEN,
        reviews=reviews,
    )
    next_line = confirmed.get("next") or ""
    assert "word file per paper" in next_line.casefold()
    assert not _STUDENT_MD.search(next_line)

    stage_4b = INSTRUCTIONS.split("Stage 4b confirm", 1)[1].split("essay.gates", 1)[0]
    assert "word file per paper" in stage_4b.casefold()
    assert not _STUDENT_MD.search(stage_4b)
    assert _STUDENT_MD.search(STAGE_CONFIRM_EACH) is None


def test_ac4_build_office_handoff_builds_4b_word_zip(workspace, tmp_path):
    """Confirm writes the Word zip. Handoff copies that file and does not rebuild it."""
    write_upload(workspace)
    seq = open_sequence()
    reviews = [{"paper_id": "src-1", "markdown": ANN}]
    essay_research_full(seq, TOPIC, "draft", [source()], clarify_context=CLARIFY_OPEN, reviews=reviews)
    confirmed = essay_research_full(
        seq,
        TOPIC,
        "confirm",
        [source()],
        clarify_context=CLARIFY_OPEN,
        reviews=reviews,
    )
    assert confirmed["stored"] is True
    mac = tmp_path / "mac"
    folder = _output(workspace)
    before_zip = (folder / "critical-reviews.zip").read_bytes()
    before_md = (folder / "reviews" / "src-1.md").read_text(encoding="utf-8")
    copied = build_deliverable_handoff(folder, mac_dir=mac)
    assert copied["handoff"] == "stage-deliverables"
    assert "critical-reviews.zip" in copied["deliverables"]
    assert (folder / "critical-reviews.zip").read_bytes() == before_zip
    assert (folder / "reviews" / "src-1.md").read_text(encoding="utf-8") == before_md
    archive = zipfile.ZipFile(folder / "critical-reviews.zip")
    _zip_has_only_suffixes(archive, ".docx")
    assert (mac / "critical-reviews.zip").read_bytes() == before_zip
    assert stage_launch("4b")["command"]


def test_ac5_student_wording_names_word_zip_not_markdown():
    """AC5. In-repo student docs describe 4b as a Word zip."""
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    phrase = "one word file per paper in `critical-reviews.zip`"
    assert phrase in workflow.casefold()
    assert phrase in helpers.casefold()
