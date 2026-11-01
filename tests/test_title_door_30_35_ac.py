"""Bugs #30 and #35. One title page, one door card for the sequence that opened.

AC1: the stage 10 Word title page includes the registration number when the brief asks.
AC2: that title page omits the student name.
AC3: a fresh kick shows only the door Confirm for that sequence.
AC5: page numbers stay lower right when the brief asks.
Build covered: Cursor and Grok Build share the stage door, the kick door, and write_docx.
"""

import inspect
import json
import zipfile
from pathlib import Path

from helpers import mac_handoff_sequence_dir, with_word_references

from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import stage_launch
from essay_writer.confirm import save_draft
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.diary import title_page_spec
from essay_writer.doors import DOORS
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.server import INSTRUCTIONS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists.grok_bot import STAGE_CONFIRM_EACH, front_office_call
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import TOOL, _save_confirm, load_pointer
from essay_writer.state import load_state, save_state
from essay_writer.word import write_docx

REPO = Path(__file__).resolve().parents[1]
NUMBER = "445566"
NAME = "Ada Example"
MODULE = "RPT5001AA"
OPEN_SEQUENCE = (
    "When a sequence opens, post only the Confirm card in that door result. "
    "That card's sequence id is the sequence that opened. "
    "Do not post a Confirm from another sequence."
)
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
HEADING = """
Title page
- module title
- module code
- assignment title
- student ID
- word count
"""


def _brief(module: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _kick(module: str, parent: str | None = None) -> dict:
    args = {"module": module, "confirmPhase": "draft"}
    if parent is not None:
        args["parent"] = parent
    draft = front_office_call("essay.sequence.new", args)
    assert draft["ok"] is True, draft
    assert "card" not in draft
    args["confirmPhase"] = "confirm"
    return front_office_call("essay.sequence.new", args)


def _park(seq: str, *, stage: str, closed: bool) -> str:
    parked = save_draft(
        seq,
        TOOL,
        {"essay_id": seq, "stage": stage, "look": f"Parked {seq} stage {stage}."},
        {"stage": stage},
    )
    pointer = load_pointer(seq)
    pointer["current"] = stage
    pointer["saved"] = ["1"] if stage == "2" else []
    pointer["closed"] = closed
    pointer["waiting_stage"] = stage
    pointer["waiting_digest"] = parked
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    return parked


def _title_and_document(path: Path) -> tuple[str, str]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return xml.split('w:type="page"', 1)[0], xml


def _footer(path: Path) -> str:
    return zipfile.ZipFile(path).read("word/footer1.xml").decode("utf-8")


def test_ac1_ac2_ac5_registration_on_the_title_page_without_the_name(workspace, monkeypatch, tmp_path):
    """AC1, AC2, AC5. Student ID is a registration ask. The name stays off. The page number stays right."""
    asked = title_page_spec(BRIEF)
    assert asked["registration"] is True
    assert "registration" in asked["fields"]
    assert asked["name"] == "forbidden"
    headed = title_page_spec(HEADING)
    assert headed["registration"] is True
    assert "registration" in headed["fields"]
    refused = title_page_spec("Title page: module title.\nDo not include your student ID.")
    assert refused["registration"] is False

    documents = tmp_path / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    _brief(MODULE)
    opened = _kick(MODULE)
    seq = opened["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    pack = {
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
    report = {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }
    stage6 = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, pack, report, stage6)
    state = load_state(seq)
    bare = dict(pack)
    assert "registration_number" not in bare
    state["saved_pack"] = with_word_references(bare)
    save_state(seq, state)
    final = write_stage10(seq)
    assert final["copied"] is True, final
    final_path = mac_handoff_sequence_dir(documents, seq) / f"{MODULE}-final.docx"
    assert final_path.is_file()
    for path in (stage6, final_path):
        title, document = _title_and_document(path)
        assert "Practice module" in title
        assert MODULE in title
        assert "Individual reflective diary" in title
        assert f"Registration number: {NUMBER}" in title
        assert "Counted words:" in title
        assert "Teaching partner" not in title
        assert NAME not in title
        assert NAME not in document
        footer = _footer(path)
        assert "PAGE" in footer
        assert "instrText" in footer
        assert 'w:val="right"' in footer


def test_ac3_fresh_kick_shows_only_this_sequence_door_card(workspace):
    """AC3. A closed parent's parked stage 2 card is not the card the new sequence opens."""
    module = "RPT5001AA"
    _brief(module)
    first = _kick(module)
    parent = first["sequence_id"]
    assert first["card"]["essay_id"] == parent
    assert first["card"]["stage"] == "1"
    parked = _park(parent, stage="2", closed=True)
    before = (work_dir(parent) / "tracking" / "stage.json").read_bytes()
    opened = _kick(module)
    child = opened["sequence_id"]
    assert child != parent
    card = opened["card"]
    assert card["kind"] == "confirm"
    assert card["essay_id"] == child
    assert card["stage"] == "1"
    assert opened["cardAction"] == "confirm"
    assert opened["cardDigest"] == card["digest"]
    assert opened["cardDigest"] != parked
    assert opened["cardDigest"] != first["cardDigest"]
    assert (work_dir(parent) / "tracking" / "stage.json").read_bytes() == before
    folder = work_dir(child) / ".drafts" / TOOL
    stages = []
    for path in folder.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["payload"]
        assert payload["essay_id"] == child
        stages.append(payload["stage"])
    assert "2" not in stages
    assert load_pointer(child)["current"] == "1"
    assert load_pointer(child)["saved"] == []
    assert load_pointer(parent)["current"] == "2"
    assert load_pointer(parent)["closed"] is True


def test_ac3_open_roll_forward_returns_the_child_card(workspace):
    """An open parent resets the child to stage 1. The kick card names the child."""
    module = "MOD1011AA"
    _brief(module)
    first = _kick(module)
    parent = first["sequence_id"]
    parked = _park(parent, stage="2", closed=False)
    before = (work_dir(parent) / "tracking" / "stage.json").read_bytes()
    opened = _kick(module, parent=parent)
    child = opened["sequence_id"]
    card = opened["card"]
    assert card["essay_id"] == child
    assert card["stage"] == "1"
    assert opened["cardDigest"] == card["digest"]
    assert opened["cardDigest"] != parked
    assert card["essay_id"] != parent
    assert (work_dir(parent) / "tracking" / "stage.json").read_bytes() == before
    kept = load_pointer(child)
    assert kept["current"] == "1"
    assert kept["saved"] == []
    assert kept["closed"] is False
    assert load_pointer(parent)["waiting_digest"] == parked


def test_build_covered_cursor_and_grok_build_share_the_kick_and_the_cover(monkeypatch):
    """Cursor and Grok Build read one stage door, one kick door, and one write_docx."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert cursor_shell()["handlers"]["essay.sequence.new"] is front_office()["handlers"]["essay.sequence.new"]
    assert "write_docx(" in inspect.getsource(write_stage10)
    assert "return _commit_with_next_card(" in inspect.getsource(_save_confirm)
    assert "_commit_with_next_card" not in inspect.getsource(stage_launch)
    assert "_commit_with_next_card" not in inspect.getsource(cursor_stage_launch)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("10")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("10")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"] == stage_settings("10")["rules"]
    door = next(item for item in DOORS if item["tool"] == "essay.sequence.new")
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    for text in (STAGE_CONFIRM_EACH, INSTRUCTIONS, bot, workflow, door["description"]):
        assert OPEN_SEQUENCE in text
