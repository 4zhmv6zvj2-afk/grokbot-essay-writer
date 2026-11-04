"""Bug #30. Stage 10 Confirm writes the sequence Word file, then closes.

AC1: a cloned diary Word file (page number, no registration) is rewritten on
the child by essay.stage Confirm, with the stored registration number.
AC2: the same run writes Documents/<module>-10/<module>-final.docx.
AC3: the parent sequence output is not rewritten.
AC4: a missing required number does not close and does not record the file final.
Calling write_docx on the child alone is not this proof.
Build covered: Cursor and Grok Build share essay.stage, write_docx, and note_call.
"""

import inspect
import json
import zipfile
from pathlib import Path

from helpers import mac_handoff_sequence_dir, with_word_references

from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.debug_log import LOG_FILENAME, debug_log_path
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import _commit_with_next_card, essay_stage, load_pointer
from essay_writer.state import load_state, save_state
from essay_writer.word import write_docx

MODULE = "RPT5001AA"
NUMBER = "445566"
NAME = "Ada Example"
BRIEF = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Title page: module title, module code, assignment title, and the word count.
Include your student ID.
The name stays off the title page and the file.

Pages: Arial, size 12. 2.5 cm margins on all sides. Page numbers in the lower right.
"""


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _kick(parent: str | None = None) -> dict:
    args = {"module": MODULE, "confirmPhase": "draft"}
    if parent is not None:
        args["parent"] = parent
    draft = essay_sequence_new(MODULE, "draft", parent)
    assert draft["ok"] is True, draft
    opened = front_office_call(
        "essay.sequence.new",
        {"module": MODULE, "confirmPhase": "confirm", "parent": parent} if parent else {
            "module": MODULE,
            "confirmPhase": "confirm",
        },
    )
    assert opened["ok"] is True, opened
    assert isinstance(opened.get("sequence_id"), str) and opened["sequence_id"]
    return opened


def _all_debug_log_text(workspace: Path) -> str:
    chunks: list[str] = []
    root_log = workspace / LOG_FILENAME
    if root_log.is_file():
        chunks.append(root_log.read_text(encoding="utf-8"))
    essay_root = workspace / "Essay-writer"
    if essay_root.is_dir():
        for path in essay_root.rglob(LOG_FILENAME):
            if path.is_file():
                chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _assert_sequence_log(opened: dict, line: str) -> None:
    """The debug line matches the card the door returned on that confirm."""
    card = opened.get("card")
    digest = opened.get("cardDigest")
    if isinstance(card, dict) and isinstance(digest, str) and digest.strip() and digest != "none":
        assert card.get("digest") == digest
        assert f"Card digest {digest}." in line
        assert "Card present." in line
        assert f"Posted {digest}." in line
        assert "Card digest none." not in line
        assert "Card absent." not in line
        return
    assert "Card digest none." in line
    assert "Card absent." in line
    assert "Card present." not in line


def _pack(seq: str) -> dict:
    return with_word_references(
        {
            "essay_id": seq,
            "title": "Individual reflective diary",
            "referencing": "harvard",
            "assessment": "Individual reflective diary",
            "module_title": "Practice module",
            "conclusion": "noted",
            "student_name": NAME,
            "sections": [
                {
                    "heading": "One decision",
                    "body": "A decision, with theory, on the practice the brief names.",
                }
            ],
        }
    )


def _report(pack: dict) -> dict:
    return {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }


def _output(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def _park(seq: str) -> None:
    pointer = load_pointer(seq)
    pointer["current"] = "10"
    pointer["saved"] = ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9"]
    pointer["closed"] = False
    pointer["chain_armed"] = False
    pointer["waiting_stage"] = None
    pointer["waiting_digest"] = None
    pointer["room_grant"] = None
    pointer["room_lock"] = False
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")


def _title(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return xml.split('w:type="page"', 1)[0]


def _footer(path: Path) -> str:
    return zipfile.ZipFile(path).read("word/footer1.xml").decode("utf-8")


def _assert_cover(path: Path) -> None:
    title = _title(path)
    document = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    assert "Practice module" in title
    assert MODULE in title
    assert "Individual reflective diary" in title
    assert f"Registration number: {NUMBER}" in title
    assert "Counted words:" in title
    assert NAME not in title
    assert NAME not in document
    footer = _footer(path)
    assert "PAGE" in footer
    assert "instrText" in footer
    assert 'w:val="right"' in footer


def test_ac1_ac2_ac3_clone_then_stage10_confirm_writes_the_child_and_documents(
    workspace, monkeypatch, tmp_path
):
    """Clone, store the number, then Confirm through essay.stage. The parent file stays."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    parent_open = _kick()
    parent = parent_open["sequence_id"]
    pack = _pack(parent)
    parent_path = _output(parent)
    write_docx(parent, pack, _report(pack), parent_path)
    assert f"Registration number: {NUMBER}" not in _title(parent_path)
    assert "PAGE" in _footer(parent_path)
    state = load_state(parent)
    state["saved_pack"] = pack
    save_state(parent, state)

    child_open = _kick(parent)
    child = child_open["sequence_id"]
    assert child != parent
    child_path = _output(child)
    assert child_path.is_file()
    assert f"Registration number: {NUMBER}" not in _title(child_path)
    assert remember_registration(child, NUMBER) == NUMBER
    _park(child)
    look = "\n".join(basics_pass_lines(child))
    draft = essay_stage(child, "10", "draft", look)
    assert draft["ok"] is True, draft
    parent_before = parent_path.read_bytes()
    child_before = child_path.read_bytes()

    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": child,
            "stage": "10",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": draft["cardDigest"],
        },
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["closed"] is True
    assert saved.get("card") is None
    assert load_pointer(child)["closed"] is True
    assert "10" in load_pointer(child)["saved"]
    assert child_path.read_bytes() != parent_before
    assert child_path.read_bytes() != child_before
    assert parent_path.read_bytes() == parent_before
    _assert_cover(child_path)
    final_path = mac_handoff_sequence_dir(documents, child) / f"{MODULE}-final.docx"
    assert final_path.is_file()
    _assert_cover(final_path)

    log = _all_debug_log_text(workspace)
    kicks = (parent_open, child_open)
    for opened in kicks:
        digest = opened.get("cardDigest")
        card = opened.get("card")
        if not isinstance(digest, str) and isinstance(card, dict):
            digest = card.get("digest")
        candidates = [line for line in log.splitlines() if "essay.sequence.new confirm" in line]
        matches = (
            [line for line in candidates if isinstance(digest, str) and digest in line]
            if isinstance(digest, str) and digest
            else []
        )
        if not matches:
            sid = opened["sequence_id"]
            matches = [line for line in candidates if sid in line]
        assert matches, f"missing sequence.new confirm log for {opened.get('sequence_id')}"
        _assert_sequence_log(opened, matches[-1])
    stage_line = next(line for line in log.splitlines() if "essay.stage confirm" in line and child in line)
    assert "Confirm store yes advance no next-card none." in stage_line
    assert "Card absent." in stage_line
    assert f"Essay-writer/{MODULE}/sequences/2/output/{child}.docx mtime " in stage_line
    assert " sha " in stage_line
    assert f"Documents/Essay Bot/{MODULE}/{child}/{MODULE}-final.docx mtime " in stage_line
    assert "debug.log" not in json.dumps(saved)


def test_ac4_missing_registration_does_not_close_or_record_the_sequence_final(
    workspace, monkeypatch, tmp_path
):
    """Confirm without the required number stays open. The cloned file is not the final."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief()
    parent = _kick()["sequence_id"]
    pack = _pack(parent)
    write_docx(parent, pack, _report(pack), _output(parent))
    state = load_state(parent)
    state["saved_pack"] = pack
    save_state(parent, state)
    child = _kick(parent)["sequence_id"]
    child_path = _output(child)
    before = child_path.read_bytes()
    _park(child)
    look = "\n".join(basics_pass_lines(child))
    draft = essay_stage(child, "10", "draft", look)
    assert draft["ok"] is True, draft
    note = work_dir(child) / "tracking" / "10.md"
    draft_note = note.read_bytes()

    refused = front_office_call(
        "essay.stage",
        {
            "essay_id": child,
            "stage": "10",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": draft["cardDigest"],
        },
    )
    assert refused["ok"] is False, refused
    assert refused["closed"] is False
    assert refused.get("stored") is not True
    assert load_pointer(child)["closed"] is False
    assert load_pointer(child)["current"] == "10"
    assert "10" not in load_pointer(child)["saved"]
    assert child_path.read_bytes() == before
    assert f"Registration number: {NUMBER}" not in _title(child_path)
    assert "Status: final" not in note.read_text(encoding="utf-8")
    assert note.read_bytes() == draft_note
    assert not (mac_handoff_sequence_dir(documents, child) / f"{MODULE}-final.docx").exists()
    log = debug_log_path(child).read_text(encoding="utf-8")
    stage_line = next(line for line in log.splitlines() if "essay.stage confirm" in line and child in line)
    assert "Confirm store no advance no next-card" in stage_line
    assert f"Essay-writer/{MODULE}/sequences/2/output/{child}.docx mtime " in stage_line


def test_build_covered_both_shells_share_the_write_and_the_log(monkeypatch):
    """Build covered. Cursor and Grok Build share the stage door, write_docx, and the log."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert cursor_shell()["handlers"]["essay.sequence.new"] is front_office()["handlers"]["essay.sequence.new"]
    assert cursor_shell()["handlers"]["essay.health"] is front_office()["handlers"]["essay.health"]
    assert "write_docx(" in inspect.getsource(write_stage10)
    assert "copy2" not in inspect.getsource(write_stage10)
    commit = inspect.getsource(_commit_with_next_card)
    assert commit.index("_render_stage10_before_close") < commit.index("_commit_pointer")
    assert "note_call" in inspect.getsource(front_office_call)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = cursor_stage_launch("10")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_launch("10")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"] == stage_settings("10")["rules"]
