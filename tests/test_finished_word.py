"""The finished Word file is one build on the stage 10 save.

Page-number and reference checks run on that build, then those bytes are saved
and copied. A failed check leaves the previous files. Earlier Word steps do not
write the final-named file. The references confirm stays the submit file, and
the specialist look-up stays there. A successful build is remembered and reused.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest
from helpers import (
    ESSAY,
    TOPIC,
    card_digest_for,
    open_sequence,
    pack,
    picked,
    source,
    with_word_references,
    write_upload,
)

from essay_writer import late_chain
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.late_chain import (
    _deliver_stage10,
    _write_stage10_sequence,
    build_finished_word,
    write_stage10,
)
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.research import essay_research_summary
from essay_writer.review import essay_review
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists.eqr import read_submit_word, submit_word_path
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_hold import (
    _commit_pointer,
    _commit_with_next_card,
    _render_stage10_before_close,
)
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word, word_manifest, write_docx

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"
QUESTION = "How do chokepoints constrain the corridor?"
SAVED_SENTENCE = "The saved draft names the corridor."
WORKING_SENTENCE = "The working file names the strait."
HOST_TOKENS = ("SHELL_CURSOR", "SHELL_GROK", "spawn_agent", "spawn_grok")


def _brief(text: str | None = None) -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        text or f"Genre: report\nQuestion: {QUESTION}\n",
        encoding="utf-8",
    )


def _working(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def _sequence_final(seq: str) -> Path:
    project = module_code(seq)
    return work_dir(seq) / "output" / f"{project}-10" / f"{project}-final.docx"


def _student_final(folder: Path, seq: str) -> Path:
    project = module_code(seq)
    return folder / project / seq / f"{project}-final.docx"


def _park(seq: str) -> None:
    pointer = load_pointer(seq)
    pointer["current"] = "10"
    pointer["saved"] = ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9"]
    pointer["closed"] = False
    pointer["chain_armed"] = False
    pointer["waiting_stage"] = None
    pointer["waiting_digest"] = None
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")


def _calls(node: ast.AST, name: str) -> int:
    found = 0
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and func.id == name:
            found += 1
        elif isinstance(func, ast.Attribute) and func.attr == name:
            found += 1
    return found


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def _spy_build(monkeypatch):
    seen: list[dict] = []
    real = build_finished_word

    def spy(essay_id, draft, report, path):
        seen.append(draft)
        return real(essay_id, draft, report, path)

    monkeypatch.setattr(late_chain, "build_finished_word", spy)
    return seen


def _store(seq: str, sentence: str) -> dict:
    body = with_word_references(
        {
            "essay_id": seq,
            "title": "Chokepoints on the corridor",
            "referencing": "harvard",
            "assessment": "Individual report",
            "conclusion": "noted",
            "sections": [{"heading": "Notes", "body": sentence}],
        }
    )
    state = load_state(seq)
    state["saved_pack"] = body
    save_state(seq, state)
    return body


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-word-1", id="AC-ew-word-1")],
)
def test_one_build_is_checked_then_copied(case_id: str, workspace, monkeypatch, tmp_path) -> None:
    """AC-ew-word-1: one build only at stage 10 save, before saved, checks then byte-for-byte copy."""
    assert case_id == "AC-ew-word-1"
    chain = PACKAGE / "late_chain.py"
    builder = _function(chain, "build_finished_word")
    sequence = _function(chain, "_write_stage10_sequence")
    deliver = _function(chain, "_deliver_stage10")
    assert _calls(builder, "write_docx") == 1
    assert _calls(sequence, "build_finished_word") == 1
    assert _calls(sequence, "write_docx") == 0
    assert _calls(deliver, "write_docx") == 0
    assert _calls(deliver, "build_finished_word") == 0
    commit_source = inspect.getsource(_commit_with_next_card)
    assert commit_source.index("_render_stage10_before_close") < commit_source.index(
        "_commit_pointer"
    )
    assert inspect.getsource(_write_stage10_sequence).index("build_finished_word(") < (
        inspect.getsource(_write_stage10_sequence).index("empty_footer_refusal(")
    )
    assert inspect.getsource(_write_stage10_sequence).index("writer_reference_block(") < (
        inspect.getsource(_write_stage10_sequence).index("os.replace(")
    )

    _brief()
    saved_seq = open_sequence()
    _store(saved_seq, SAVED_SENTENCE)
    other = _working(saved_seq)
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"working-file-not-the-input")
    saved_seen = _spy_build(monkeypatch)
    saved_result = write_stage10(saved_seq)
    assert saved_result["ok"] is True, saved_result
    assert len(saved_seen) == 1
    assert SAVED_SENTENCE in json.dumps(saved_seen[0])
    assert b"working-file-not-the-input" not in _working(saved_seq).read_bytes()
    monkeypatch.setattr(late_chain, "build_finished_word", build_finished_word)

    _brief()
    working_seq = open_sequence()
    drafted = with_word_references(
        {
            "essay_id": working_seq,
            "title": "Chokepoints on the corridor",
            "referencing": "harvard",
            "assessment": "Individual report",
            "conclusion": "noted",
            "sections": [{"heading": "Notes", "body": WORKING_SENTENCE}],
        }
    )
    prepared, report = word_manifest(working_seq, drafted, product_log=False)
    write_docx(working_seq, prepared, report, _working(working_seq))
    state = load_state(working_seq)
    state["saved_pack"] = None
    save_state(working_seq, state)
    working_seen = _spy_build(monkeypatch)
    working_result = write_stage10(working_seq)
    assert working_result["ok"] is True, working_result
    assert working_result.get("pack_path") == "pack_from_docx"
    assert len(working_seen) == 1
    assert WORKING_SENTENCE in json.dumps(working_seen[0])
    monkeypatch.setattr(late_chain, "build_finished_word", build_finished_word)

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _store(seq, "The finished file names one corridor.")
    _park(seq)
    seen = _spy_build(monkeypatch)
    before_save = {"built": 0, "saved": True}

    def watching(essay_id, base, proposed, *, note=None, note_text=None):
        if proposed.get("closed") is True:
            before_save["built"] = len(seen)
            before_save["saved"] = "10" in (base.get("saved") or [])
            assert _sequence_final(essay_id).is_file()
            assert _student_final(documents, essay_id).is_file()
            assert _working(essay_id).read_bytes() == _sequence_final(essay_id).read_bytes()
            assert (
                _working(essay_id).read_bytes() == _student_final(documents, essay_id).read_bytes()
            )
        return _commit_pointer(essay_id, base, proposed, note=note, note_text=note_text)

    monkeypatch.setattr("essay_writer.stage_hold._commit_pointer", watching)
    look = "\n".join(basics_pass_lines(seq)) + "\nThe final file is ready."
    draft = essay_stage(seq, "10", "draft", look)
    assert draft["ok"] is True, draft
    assert seen == []
    saved = essay_stage(seq, "10", "confirm", **picked(draft))
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert "10" in load_pointer(seq)["saved"]
    assert before_save == {"built": 1, "saved": False}
    assert len(seen) == 1
    chat = saved["final_word"]["chat_docx"]
    assert chat["name"] == f"{ESSAY}-final.docx"
    assert chat["docx_base64"]
    project = module_code(seq)
    assert saved["final_word"]["final_name"] == f"{project}-final.docx"


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-word-2", id="AC-ew-word-2")],
)
def test_a_failed_check_leaves_files_and_the_step_unsaved(
    case_id: str, workspace, monkeypatch, tmp_path
) -> None:
    """AC-ew-word-2: failed check leaves previous files and stage 10 unsaved."""
    assert case_id == "AC-ew-word-2"
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    seq = open_sequence()
    _store(seq, "A previous draft stays on the sequence.")
    _park(seq)
    working = _working(seq)
    working.parent.mkdir(parents=True, exist_ok=True)
    working.write_bytes(b"previous-working")
    sequence_final = _sequence_final(seq)
    sequence_final.parent.mkdir(parents=True, exist_ok=True)
    sequence_final.write_bytes(b"previous-sequence-final")
    student = _student_final(documents, seq)
    student.parent.mkdir(parents=True, exist_ok=True)
    student.write_bytes(b"previous-student-final")
    seen = _spy_build(monkeypatch)

    def refuse_page(_path):
        return {
            "ok": False,
            "refused": "footer",
            "reason": "The page number is missing. An empty footer is refused.",
            "wrote": False,
        }

    monkeypatch.setattr("essay_writer.word.empty_footer_refusal", refuse_page)
    look = "\n".join(basics_pass_lines(seq)) + "\nThe final file is ready."
    draft = essay_stage(seq, "10", "draft", look)
    assert draft["ok"] is True, draft
    refused = essay_stage(seq, "10", "confirm", **picked(draft))
    assert refused["ok"] is False, refused
    assert refused.get("stored") is not True
    assert refused.get("closed") is not True
    assert "10" not in load_pointer(seq)["saved"]
    assert load_pointer(seq)["closed"] is False
    assert len(seen) == 1
    assert working.read_bytes() == b"previous-working"
    assert sequence_final.read_bytes() == b"previous-sequence-final"
    assert student.read_bytes() == b"previous-student-final"
    assert not working.with_name(f".{working.name}.writing").exists()


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-word-3", id="AC-ew-word-3")],
)
def test_earlier_steps_do_not_write_the_final_name(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-word-3: earlier Word steps do not write the final-named file; references confirm remains the review submit file and is not called the final Word file; specialist look-up does not run again at finish."""
    assert case_id == "AC-ew-word-3"
    render_source = inspect.getsource(essay_pack_render_word)
    assert "final Word file" not in render_source
    assert "references confirm" in render_source
    assert "final_specialist_lookup(" in render_source
    finish_source = (
        inspect.getsource(build_finished_word)
        + inspect.getsource(write_stage10)
        + inspect.getsource(_deliver_stage10)
        + inspect.getsource(_write_stage10_sequence)
    )
    assert "final_specialist_lookup" not in finish_source
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    assert "At the references confirm (stage 9" in workflow
    assert "At the final Word (stage 9" not in workflow
    assert "Finish does not run that look-up again." in workflow

    write_upload(workspace)
    _brief(
        f"Genre: report\nQuestion: {QUESTION}\n"
        "Use at least one specialist industry source (Statista).\n"
    )
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(
        seq,
        TOPIC,
        "confirm",
        [source()],
        cardDigest=card_digest_for(seq, "essay.research.summary"),
    )
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    for stage in ("6", "7", "9"):
        held = essay_pack_render_word(seq, pack(), "confirm", stage=stage)
        assert held.get("wrote") is not True
        assert "final Word file" not in json.dumps(held)
        assert not _sequence_final(seq).exists()
    preview = essay_pack_render_word(seq, pack(), "draft")
    written = essay_pack_render_word(seq, pack(), "confirm")
    assert preview["wrote"] is False
    assert written["wrote"] is True, written
    assert _working(seq).is_file()
    assert not _sequence_final(seq).exists()

    from docx import Document

    submit = submit_word_path(seq)
    submit.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(f"This is a report. {QUESTION} (Smith, 2020).")
    document.save(str(submit))
    drafted = essay_review(
        seq,
        "9",
        "PASS",
        "draft",
        constitution=f"This is a report. {QUESTION}",
    )
    assert drafted["ok"] is True, drafted
    stored = essay_review(
        seq,
        "9",
        "PASS",
        "confirm",
        constitution=f"This is a report. {QUESTION}",
    )
    assert stored["stored"] is True, stored
    assert read_submit_word(seq)["opened"] is True
    assert submit_word_path(seq) == _working(seq)
    assert submit_word_path(seq).name != f"{ESSAY}-final.docx"

    lookups: list[str] = []

    def search(query: str) -> dict:
        lookups.append(query)
        return {"called": False, "hits": [], "skipped": "test"}

    monkeypatch.setattr("essay_writer.mark_fit._default_specialist_search", search)
    preview = essay_pack_render_word(seq, pack(), "draft", stage="9")
    assert preview["ok"] is True, preview
    assert "final Word file" not in json.dumps(preview)
    before = _working(seq).read_bytes()
    confirmed = essay_pack_render_word(seq, pack(), "confirm", stage="9")
    assert confirmed["wrote"] is True, confirmed
    assert "final Word file" not in json.dumps(confirmed)
    assert _working(seq).read_bytes() != before
    assert not _sequence_final(seq).exists()
    assert lookups
    held_at = len(lookups)
    finished = write_stage10(seq)
    assert finished["ok"] is True, finished
    assert len(lookups) == held_at
    assert _sequence_final(seq).is_file()


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-word-4", id="AC-ew-word-4")],
)
def test_a_remembered_file_is_reused_by_both_hosts(
    case_id: str, workspace, monkeypatch, tmp_path
) -> None:
    """AC-ew-word-4: remember-and-reuse, missing-remembered-file stop, and separate comments/review files hold; Build covered."""
    assert case_id == "AC-ew-word-4"
    assert (
        cursor_shell()["handlers"]["essay.stage"]
        is front_office()["handlers"]["essay.stage"]
        is HANDLERS["essay.stage"]
    )
    for name in ("cursor_office.py", "build_office.py"):
        text = (PACKAGE / name).read_text(encoding="utf-8")
        assert "build_finished_word" not in text
        assert "write_stage10" not in text
    shared = inspect.getsource(build_finished_word) + inspect.getsource(write_stage10)
    for token in HOST_TOKENS:
        assert token not in shared
    assert cursor_stage_launch("10")["settings"]["rules"] == stage_launch("10")["settings"]["rules"]
    assert inspect.getsource(_commit_with_next_card).count("write_stage10(") == 0
    assert "write_stage10(" in inspect.getsource(_render_stage10_before_close)

    _brief()
    seq = open_sequence()
    _store(seq, "The remembered file stays in this chat.")
    first = write_stage10(seq)
    assert first["ok"] is True, first
    assert first["copied"] is False
    assert first["chat_docx"]["name"] == f"{ESSAY}-final.docx"
    mark = _working(seq).with_name(".stage10-copied.json")
    assert mark.is_file()
    record = json.loads(mark.read_text(encoding="utf-8"))
    assert record["copied"] is False
    assert record["sequence_written"] is True
    remembered = _sequence_final(seq).read_bytes()
    seen = _spy_build(monkeypatch)
    again = write_stage10(seq)
    assert again["ok"] is True, again
    assert again.get("reused") is True
    assert again["chat_docx"]["name"] == f"{ESSAY}-final.docx"
    assert seen == []
    assert _sequence_final(seq).read_bytes() == remembered
    monkeypatch.setattr(late_chain, "build_finished_word", build_finished_word)

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    mounted = open_sequence()
    _store(mounted, "The folder copy stays beside the notes.")
    copied = write_stage10(mounted)
    assert copied["copied"] is True, copied
    student = _student_final(documents, mounted)
    comments = student.with_name(f"{ESSAY}-comments.docx")
    assert student.is_file()
    assert comments.is_file()
    assert comments.read_bytes() != student.read_bytes()
    assert student.read_bytes() == _sequence_final(mounted).read_bytes()
    findings = copied.get("findings_file")
    assert isinstance(findings, dict)
    assert findings.get("place") != str(student)
    project = module_code(mounted)
    findings_name = f"{project}-findings.docx"
    assert findings_name != student.name
    assert comments.name != student.name
    sequence_bytes = _working(mounted).read_bytes()
    final_bytes = _sequence_final(mounted).read_bytes()
    student.unlink()
    stopped = _spy_build(monkeypatch)
    missing = write_stage10(mounted)
    assert missing["ok"] is False, missing
    assert missing["reason"] == "The final Word file is missing."
    assert stopped == []
    assert not student.exists()
    assert comments.is_file()
    assert _working(mounted).read_bytes() == sequence_bytes
    assert _sequence_final(mounted).read_bytes() == final_bytes
