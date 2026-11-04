"""Stage 10 recovery when saved_pack is null, plus operator debug lines for the MOD2004AA-3 FAIL.

AC1: Stage 10 cover keeps sequence id, assignment title, and counted words after pack_from_docx.
AC2: References stay non-empty when the on-disk Word already listed cites and uploads match.
AC3: Module-seq copy with saved_pack null still recovers cover and refs like a CLEAR final.
AC4: Operator debug.log names pack path, saved_pack null, cover audit, and ref count without Word.
Build covered: Cursor and Grok Build share write_stage10, word_manifest, write_docx,
log_word_manifest, log_word_docx_written, and log_word_step.
"""

import hashlib
import inspect
import json
from pathlib import Path

import pytest
from docx import Document
from helpers import ESSAY, open_sequence, pack, report_sections, write_upload

from essay_writer.debug_log import debug_log_path, log_word_step
from essay_writer.late_chain import (
    log_word_docx_written,
    log_word_manifest,
    write_stage10,
)
from essay_writer.ml_events import ml_events_path
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.research import essay_research_summary
from essay_writer.validate import essay_pack_validate, inspect_pack
from essay_writer.word import word_manifest, write_docx

MODULE = ESSAY
SEQ3 = f"{MODULE}-3"
TOPIC = "How should the firm manage corridor risk?"
ASSIGNMENT = "Individual supply chain report"
REPORT_BRIEF = (
    f"Question: {TOPIC}\n"
    f"Assignment title: {ASSIGNMENT}\n"
)
SCHEME = "High Distinction (80-100): the question is answered with evidence.\n"

FAIL_SAMPLE = Path(__file__).parent / "fixtures" / "stage10_fail_log_sample.txt"
FAIL_MARKERS = [
    line.strip()
    for line in FAIL_SAMPLE.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]

FAIL_GREP = [
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 pack_path=pack_from_docx",
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 saved_pack=null",
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 cover_sequence_id=0",
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 cover_title_line=0",
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 cover_counted_words=0",
    "event=essay.product.write_stage10 essay_id=MOD2004AA-3 refs_n=0",
]


def _no_consecutive_duplicate_lines(text: str) -> None:
    lines = [line for line in text.splitlines() if line.strip()]
    for left, right in zip(lines, lines[1:], strict=False):
        assert left != right


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(REPORT_BRIEF, encoding="utf-8")
    (folder / "mark-scheme.md").write_text(SCHEME, encoding="utf-8")


def _cover(path: Path) -> list[str]:
    document = Document(str(path))
    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style is not None and paragraph.style.name.startswith("Heading"):
            break
        lines.append(text)
    return lines


def _references_body(path: Path) -> list[str]:
    texts = [paragraph.text.strip() for paragraph in Document(str(path)).paragraphs if paragraph.text.strip()]
    if "References" not in texts:
        return []
    return texts[texts.index("References") + 1 :]


def _report_pack(seq: str) -> dict:
    cite_hasan = "(Hasan and Sarker, 2023)"
    cite_imma = "(Immadisetty, 2022)"
    body = pack(seq)
    body["assessment"] = ASSIGNMENT
    body["sections"] = report_sections(
        f"High Distinction. Corridor risk {cite_hasan}.",
        f"One named chain {cite_imma}.",
        f"Evidence {cite_hasan}.",
        f"Conclusion {cite_imma}.",
    )
    body["sources"] = [
        {
            "id": "src-hasan",
            "origin": "upload",
            "locator": f"uploads/{MODULE}/hasan.md",
            "author": "Hasan and Sarker",
            "year": "2023",
            "title": "Corridor risk is material for the chain",
            "quote": "Corridor risk is material for the chain.",
        },
        {
            "id": "src-imma",
            "origin": "upload",
            "locator": f"uploads/{MODULE}/immadisetty.md",
            "author": "Immadisetty",
            "year": "2022",
            "title": "One named chain is in scope for the report",
            "quote": "One named chain is in scope for the report.",
        },
    ]
    return body


def _write_good_word(seq: str, body: dict) -> Path:
    report = inspect_pack(seq, body)
    stage = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, stage)
    return stage


def _null_saved_pack(seq: str) -> None:
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    state["saved_pack"] = None
    state["research"] = {"summary": None, "full": None}
    save_state(seq, state)


@pytest.fixture
def operator_debug(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")

    def _path(seq: str) -> Path:
        return debug_log_path(seq)

    return _path


def test_ac4_fail_sample_fixture_lists_debug_markers():
    """AC4. PR sample lines are greppable key=value facts for the MOD2004AA-3 FAIL."""
    joined = "\n".join(FAIL_MARKERS)
    for needle in FAIL_GREP:
        assert needle in joined
    assert "event=essay.product.word_manifest" not in joined


def test_ac4_operator_log_names_pack_from_docx_path_and_cover_audit(
    workspace, monkeypatch, tmp_path, operator_debug
):
    """AC4. Debug log records pack path and cover/refs counts for null saved_pack recovery."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    write_upload(
        workspace,
        MODULE,
        "hasan.md",
        (
            "Hasan and Sarker (2023) How should the firm manage corridor risk? "
            "Corridor risk is material for the chain.\n"
        ),
    )
    write_upload(
        workspace,
        MODULE,
        "immadisetty.md",
        (
            "Immadisetty (2022) How should the firm manage corridor risk? "
            "One named chain is in scope for the report.\n"
        ),
    )
    seq = open_sequence(MODULE)
    body = _report_pack(seq)
    essay_research_summary(seq, TOPIC, "draft", body["sources"])
    essay_research_summary(seq, TOPIC, "confirm", body["sources"])
    essay_pack_validate(seq, body, "confirm")
    _write_good_word(seq, body)
    _null_saved_pack(seq)
    log_path = operator_debug(seq)
    log_path.unlink(missing_ok=True)

    final = write_stage10(seq)
    assert final["sequence_written"] is True, final
    assert final.get("pack_path") == "pack_from_docx"
    assert final.get("saved_pack_state") == "null"

    log_text = log_path.read_text(encoding="utf-8")
    _no_consecutive_duplicate_lines(log_text)
    assert "event=essay.product.word_manifest" not in log_text
    assert "event=essay.product.write_docx" not in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} stage=10" in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} saved_pack=null" in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} cover_sequence_id=1" in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} cover_title_line=1" in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} cover_counted_words=1" in log_text
    assert f"event=essay.product.write_stage10 essay_id={seq} refs_n=2" in log_text or (
        f"event=essay.product.write_stage10 essay_id={seq} refs_n=1" in log_text
    )
    assert f"event=essay.product.write_stage10 essay_id={seq} sha=" in log_text
    assert "title=Draft" not in log_text
    assert f'title="{ASSIGNMENT}"' in log_text or f"title={ASSIGNMENT}" in log_text
    assert f'assessment="{ASSIGNMENT}"' in log_text or f"assessment={ASSIGNMENT}" in log_text


def test_ac6_write_stage10_recovery_refreshes_ml_paths_sha(
    workspace, monkeypatch, tmp_path, operator_debug
):
    """AC6. pack_from_docx rewrite updates ml-events.jsonl sequence docx sha to match debug.log."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    write_upload(
        workspace,
        MODULE,
        "hasan.md",
        (
            "Hasan and Sarker (2023) How should the firm manage corridor risk? "
            "Corridor risk is material for the chain.\n"
        ),
    )
    write_upload(
        workspace,
        MODULE,
        "immadisetty.md",
        (
            "Immadisetty (2022) How should the firm manage corridor risk? "
            "One named chain is in scope for the report.\n"
        ),
    )
    seq = open_sequence(MODULE)
    body = _report_pack(seq)
    essay_research_summary(seq, TOPIC, "draft", body["sources"])
    essay_research_summary(seq, TOPIC, "confirm", body["sources"])
    essay_pack_validate(seq, body, "confirm")
    stage_path = _write_good_word(seq, body)
    stale_sha = "a0763b9f" + ("0" * 56)
    ml_path = ml_events_path(seq)
    stale = {
        "kind": "paths",
        "t": "2026-01-01T00:00:00+00:00",
        "tool": "essay.stage",
        "essay_id": seq,
        "files": [
            {
                "display": f"Essay-writer/{MODULE}/sequences/1/output/{seq}.docx",
                "exists": True,
                "sha256": stale_sha,
            }
        ],
    }
    ml_path.write_text(json.dumps(stale, sort_keys=True) + "\n", encoding="utf-8")
    _null_saved_pack(seq)
    log_path = operator_debug(seq)
    log_path.unlink(missing_ok=True)

    final = write_stage10(seq)
    assert final["sequence_written"] is True, final

    current_sha = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    assert current_sha != stale_sha
    log_text = log_path.read_text(encoding="utf-8")
    assert f"sha={current_sha}" in log_text

    rows = [json.loads(line) for line in ml_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    paths = [row for row in rows if row.get("kind") == "paths" and row.get("essay_id") == seq]
    assert paths
    latest = paths[-1]["files"]
    sequence_file = next(item for item in latest if item["display"].endswith(f"{seq}.docx"))
    assert sequence_file["sha256"] == current_sha


def test_ac1_null_saved_pack_keeps_house_cover(workspace, monkeypatch, tmp_path):
    """AC1. pack_from_docx recovery still prints sequence id, title, and counted words."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    write_upload(workspace, MODULE, "hasan.md", "Hasan and Sarker (2023) Corridor risk is material for the chain.\n")
    write_upload(workspace, MODULE, "immadisetty.md", "Immadisetty (2022) One named chain is in scope for the report.\n")
    seq = open_sequence(MODULE)
    body = _report_pack(seq)
    essay_research_summary(seq, TOPIC, "draft", body["sources"])
    essay_research_summary(seq, TOPIC, "confirm", body["sources"])
    essay_pack_validate(seq, body, "confirm")
    stage = _write_good_word(seq, body)
    _null_saved_pack(seq)
    final = write_stage10(seq)
    assert final["sequence_written"] is True, final
    lines = _cover(stage)
    assert seq in lines
    assert ASSIGNMENT in lines
    assert any(item.startswith("Counted words:") for item in lines)


def test_ac2_null_saved_pack_keeps_references_from_word_and_uploads(
    workspace, monkeypatch, tmp_path, operator_debug
):
    """AC2. Harvard entries return when research state was cleared but the Word file still cites."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    write_upload(
        workspace,
        MODULE,
        "hasan.md",
        (
            "Hasan and Sarker (2023) How should the firm manage corridor risk? "
            "Corridor risk is material for the chain.\n"
        ),
    )
    write_upload(
        workspace,
        MODULE,
        "immadisetty.md",
        (
            "Immadisetty (2022) How should the firm manage corridor risk? "
            "One named chain is in scope for the report.\n"
        ),
    )
    seq = open_sequence(MODULE)
    body = _report_pack(seq)
    essay_research_summary(seq, TOPIC, "draft", body["sources"])
    essay_research_summary(seq, TOPIC, "confirm", body["sources"])
    essay_pack_validate(seq, body, "confirm")
    stage = _write_good_word(seq, body)
    _null_saved_pack(seq)
    final = write_stage10(seq)
    assert final["sequence_written"] is True, final
    refs = _references_body(stage)
    joined = "\n".join(refs)
    assert "Hasan" in joined
    assert "Immadisetty" in joined
    assert refs


def test_ac3_module_seq_null_saved_pack_matches_clear_cover_and_refs(
    workspace, monkeypatch, tmp_path
):
    """AC3. Third sequence after copy keeps cover and refs when saved_pack is null."""
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    write_upload(workspace, MODULE, "hasan.md", "Hasan and Sarker (2023) Corridor risk is material for the chain.\n")
    write_upload(workspace, MODULE, "immadisetty.md", "Immadisetty (2022) One named chain is in scope for the report.\n")
    open_sequence(MODULE)
    parent = f"{MODULE}-1"
    essay_sequence_new(MODULE, "draft", parent=parent)
    essay_sequence_new(MODULE, "confirm", parent=parent)
    essay_sequence_new(MODULE, "draft", parent=f"{MODULE}-2")
    seq3 = essay_sequence_new(MODULE, "confirm", parent=f"{MODULE}-2")["sequence_id"]
    assert seq3.endswith("-3")
    body = _report_pack(seq3)
    essay_research_summary(seq3, TOPIC, "draft", body["sources"])
    essay_research_summary(seq3, TOPIC, "confirm", body["sources"])
    essay_pack_validate(seq3, body, "confirm")
    stage = _write_good_word(seq3, body)
    _null_saved_pack(seq3)
    final = write_stage10(seq3)
    assert final["sequence_written"] is True, final
    lines = _cover(stage)
    assert seq3 in lines
    assert ASSIGNMENT in lines
    assert any(item.startswith("Counted words:") for item in lines)
    assert _references_body(stage)


def test_build_covered_shared_word_product_log_doors():
    """Build covered. Launch assemblers do not redefine the shared Word product log doors."""
    from essay_writer.build_office import stage_launch
    from essay_writer.cursor_office import cursor_stage_launch

    assert "log_word_manifest(" in inspect.getsource(word_manifest)
    assert "log_word_docx_written(" in inspect.getsource(write_docx)
    assert "log_word_step(" in inspect.getsource(write_stage10)
    assert "note_stage10_rewrite_paths(" in inspect.getsource(write_stage10)
    assert log_word_manifest.__module__ == "essay_writer.late_chain"
    assert log_word_docx_written.__module__ == "essay_writer.late_chain"
    assert log_word_step.__module__ == "essay_writer.debug_log"
    launch = inspect.getsource(stage_launch)
    cursor = inspect.getsource(cursor_stage_launch)
    for name in ("log_word_manifest", "log_word_docx_written", "log_word_step"):
        assert f"def {name}" not in launch
        assert f"def {name}" not in cursor
