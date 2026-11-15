"""Helpful friend voice, and one sentence on the step after the first read.

The persona is the helpful friend. Stage 6 still leaves the edit with the
student, then says the next step asks questions and edits from the answers.
Earlier cases stay as they are.

Ids are seated once. The id is the docstring and the pytest id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document
from helpers import open_sequence, pack, picked, plant_gathered_source

from essay_writer.assignment_gate import read_assignment
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.diary import title_page_spec
from essay_writer.encourage import DEPTH_PROMPT
from essay_writer.paths import essay_dir, work_dir
from essay_writer.prompt_loader import text
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import STAGE5_SAVE_LINE, saved_next
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage7 import _QUESTIONS, ASK_FIRST, answers_mean_no_change, note_edits
from essay_writer.stage_llm import stage_settings, stage_title
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.student_turns import (
    REDIRECT_ORDER,
    REDIRECT_WHOLE,
    STAGE6_LEAD_IN,
    STAGE7_LINE,
    redirect_for,
)
from essay_writer.word import cover_lines
from essay_writer.writing_basics import CHECKLISTS, STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
FRIEND = (
    "Sound like a helpful friend guiding one step at a time, "
    "not a help desk or a system log."
)
WARM = (
    "- **Warm and concise.** Use short, complete sentences. "
    "Sound like a helpful friend guiding one step at a time, not a help desk or a system log."
)
HELPFUL_BULLET = (
    "- **Helpful friend.** Not sales. Not one generic script. Propose the next step or a "
    "clear choice. The first three steps may be drafted in this chat. Deeper research, "
    "writing, and the separate review stay off the student's side of the conversation. "
    "The first time the writer path needs independent review before Word, say that review "
    "runs in a separate specialist review and is not a writer-stage save in this chat."
)
BANKING = (
    "Speak as a private banking Relationship Manager: bespoke to this client's brief and "
    "mark scheme, professional, and responsible for their satisfaction."
)
NEXT_STEP = "The next step asks questions and edits from the answers."
STAGE6_CLOSE = (
    "At the start of the first read, show the short read list once, then stop. "
    "The student edits. Do not rewrite the draft for them. Do not add a gate, a score, "
    f"or a blocker. {NEXT_STEP}"
)
STAGE6_STORY = (
    "The tool drafts. The student directs and confirms. "
    "Stage 6 is the student's read-through and feedback, not a tool rewrite."
)
STAGE7_STORY = (
    "The tool drafts. The student directs and confirms. "
    "Stage 7 asks questions and edits from the student's answers."
)
READ_PHRASE = "show the short read list once, then stop"
READ_LIST = (
    "Read the draft and edit it yourself. Look for a fact made smoother or more important "
    "than the source, a line that says experts say or research shows with no source you "
    "opened, and a quotation, page, or finding you cannot find in the opened file. Also "
    "look for empty praise, an empty contrast, a decorative list of three, and use *is* "
    "instead of *serves as*. A real contrast stays. This is not a score, and the draft is "
    "not rewritten for you."
)
LEAD_IN = (
    "This is your turn to read the draft. I will show you what to look for once, "
    "then you can edit it yourself."
)
OLD_STAGE9 = (
    "Do not approve a save if references are unchanged from the last saved draft bundle."
)
NEW_STAGE9 = (
    "If the list is wrong, fix it before approving. If it is right and unchanged, say so and approve."
)
SOURCE_NEXT = "Add a gathered source, then press Confirm."
BIBLIOGRAPHY_NEXT = "Add a bibliography, then press Confirm."
SOURCE_REASON = "Stage 4a stays here until a gathered source is on the list."
BIBLIOGRAPHY_REASON = "Stage 4b stays here until stage 4a has a bibliography."
WHOLE = (
    "We work on the essay in stages: what the assignment asks, the plan, the sources, "
    "then the draft. If you already have the assignment, send it over and we will start "
    "with the first stage."
)
ORDER = (
    "We work through the stages in order. Tell me where you are up to and we will carry "
    "on from the next one. If nothing is done yet, we start at the beginning."
)
ALL_FINE = "If the draft is fine as it is, say all fine."
SENTENCE = "The corridor depends on one narrow strait."
TITLE = "Named chains through the corridor"
QUESTION = "How do chokepoints constrain the corridor?"
NAME = "Ada Example"
NUMBER = "445566"
PROGRAMME_LINES = (
    "Teaching partner",
    "Awarding university",
    "Undergraduate programme",
    "PROG01",
)
COVER_NOTED = "Conclusion: noted"
COVER_OPEN = "Conclusion: open — not a settled finding"
HEADED_PLAN = (
    "Central theme: The corridor stays open.\n"
    "1. Supply chain context\n"
    "2. Conclusion\n"
)
EMPTY_PLAN = (
    "Central theme: The corridor stays open.\n"
    "The draft follows that claim in one pass with no numbered parts.\n"
)
TRAPS_IDS = (
    "essay-traps-a1",
    "essay-traps-a2",
    "essay-traps-a3",
    "essay-traps-b1",
    "essay-traps-b2",
    "essay-traps-c1",
    "essay-traps-c2",
    "essay-traps-d1",
    "essay-traps-e1",
    "essay-traps-f1",
)
COVER_IDS = (
    "essay-cover-a1",
    "essay-cover-a2",
    "essay-cover-b1",
    "essay-cover-b2",
    "essay-cover-c1",
    "essay-cover-c2",
    "essay-cover-c3",
    "essay-cover-d1",
    "essay-cover-e1",
)
PROMISE_IDS = (
    "essay-promise-a1",
    "essay-promise-a2",
    "essay-promise-a3",
    "essay-promise-a4",
    "essay-promise-b1",
    "essay-promise-b2",
    "essay-promise-b3",
    "essay-promise-c1",
    "essay-promise-c2",
    "essay-promise-d1",
)
ASK_IDS = (
    "essay-ask-a1",
    "essay-ask-a2",
    "essay-ask-a3",
    "essay-ask-a4",
    "essay-ask-a5",
    "essay-ask-a6",
    "essay-ask-a7",
    "essay-ask-a8",
    "essay-ask-b1",
    "essay-ask-b2",
    "essay-ask-b3",
    "essay-ask-b4",
    "essay-ask-c1",
    "essay-ask-c2",
    "essay-ask-d1",
)
VOICE_IDS = (
    "essay-voice-a1",
    "essay-voice-b1",
    "essay-voice-c1",
    "essay-voice-d1",
)
FIRST_RUN_OPENING = (
    "ESSAY BOT OPERATOR SETUP — not the developer guide. "
    "Developers: see README.md and ARCHITECTURE.md.\n\n"
    "Set up essay writer from this copy. You talk to the user. "
    "File work does not own this chat.\n\n"
    "This file is operator setup. Do not read these install steps into student chat. "
    "The Basics checklist stays internal. A new student starts a new essay. "
    "Do not continue a leftover module on this computer unless they name that sequence. "
    "Do not delete a leftover module.\n"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _snapshot() -> dict:
    return json.loads(_read(REPO / "tests" / "snapshots" / "prompts.json"))


def _persona_sources() -> dict[str, str]:
    return {
        "template": _read(REPO / "tools" / "doc_templates" / "bot.md"),
        "sheet": _read(REPO / "docs" / "templates" / "bot.md"),
        "briefing": _read(REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md"),
        "snapshot": _read(REPO / "tests" / "snapshots" / "prompts.json"),
    }


def _without_dashboard_clients(value: str) -> str:
    return value.replace("Keys and Clients", "").replace("Keys and clients", "")


def _assert_persona_gone(value: str) -> None:
    cleaned = _without_dashboard_clients(value)
    folded = cleaned.casefold()
    assert "private banking" not in folded
    assert "relationship manager" not in folded
    assert "satisfaction" not in folded
    assert "client" not in folded
    assert BANKING not in value


def _assert_friend_sources() -> None:
    sources = _persona_sources()
    for value in sources.values():
        _assert_persona_gone(value)
    for name in ("template", "sheet"):
        assert WARM in sources[name]
        assert HELPFUL_BULLET in sources[name]
        assert sources[name].count(FRIEND) == 1
    assert FRIEND in sources["briefing"]
    assert "Not sales. Not a thin script." in sources["briefing"]
    assert FRIEND in INSTRUCTIONS
    assert _snapshot()["instructions"] == INSTRUCTIONS
    briefing = sources["briefing"]
    operator = _read(REPO / "src" / "essay_writer" / "prompts" / "install" / "operator.md")
    first_run = _read(REPO / "FIRST-RUN.txt")
    packaged = _read(REPO / "src" / "essay_writer" / "FIRST-RUN.txt")
    for value in (briefing, operator, first_run, packaged, sources["snapshot"], INSTRUCTIONS):
        assert "Keys and Clients" in value
        assert "Keys and clients" in value
    server = _read(REPO / "src" / "essay_writer" / "server.py")
    assert "open client" in server
    module = _read(REPO / "src" / "essay_writer" / "specialists" / "grok_bot.py")
    doc = module.split('"""', 2)[1]
    assert doc.startswith("Grok Bot. Helpful friend.")
    assert "private banking" not in doc.casefold()
    assert "relationship manager" not in doc.casefold()
    assert "client" not in doc.casefold()
    role = _read(REPO / "tests" / "test_fo_rm.py")
    assert FRIEND in role
    assert '"private banking Relationship Manager" in' not in role
    assert '"satisfaction" in' not in role
    assert BANKING not in role


def _assert_stage6_sentence() -> None:
    stage = _read(REPO / "src" / "essay_writer" / "prompts" / "stages" / "06.md")
    helpers = _read(REPO / "docs" / "academic-writing-helpers.md")
    line = f"- {STAGE6_CLOSE}"
    assert stage.count(line) == 1
    assert helpers.count(line) == 1
    assert stage.rstrip().endswith(line)
    assert CHECKLISTS["6"][-1] == STAGE6_CLOSE
    assert CHECKLISTS["6"][0] == STAGE6_STORY
    assert CHECKLISTS["7"][0] == STAGE7_STORY
    assert NEXT_STEP not in "\n".join(CHECKLISTS["7"])
    assert text("front_office/chat.md", "stage6_read_list") == READ_LIST
    assert text("front_office/chat.md", "stage6_lead_in") == LEAD_IN
    assert STAGE6_LEAD_IN == LEAD_IN
    assert READ_PHRASE in STAGE6_CLOSE
    assert NEXT_STEP not in READ_LIST
    assert NEXT_STEP not in LEAD_IN
    snapshot = _snapshot()
    for genre in (None, "essay", "report", "diary"):
        key = f"6:{genre or 'none'}"
        rules = stage_settings("6", genre)["rules"]
        assert rules == snapshot["stage_rules"][key]
        assert rules.count(NEXT_STEP) == 1
        assert f"Do not add a gate, a score, or a blocker. {NEXT_STEP}" in rules
        assert "The student edits." in rules
        assert "Do not rewrite the draft for them." in rules
        assert STAGE6_STORY in rules
        assert READ_PHRASE in rules
        later = stage_settings("7", genre)["rules"]
        assert later == snapshot["stage_rules"][f"7:{genre or 'none'}"]
        assert STAGE7_STORY in later
        assert NEXT_STEP not in later
    assert stage_launch("6")["settings"]["rules"] == cursor_stage_launch("6")["settings"]["rules"]
    assert NEXT_STEP in stage_launch("6")["settings"]["rules"]
    assert stage_launch("7")["settings"]["rules"] == cursor_stage_launch("7")["settings"]["rules"]
    assert STAGE7_STORY in stage_launch("7")["settings"]["rules"]
    assert ASK_FIRST == "Ask the questions in this chat before editing from the answers."
    assert "Edits from the answers" in (note_edits.__doc__ or "")


def _look(stage: str) -> str:
    return f"{SENTENCE} This sentence belongs to stage {stage}."


def _through(seq: str, stop: str) -> None:
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        draft = essay_stage(seq, stage, "draft", _look(stage))
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            assert draft.get("card") is None
            continue
        saved = essay_stage(seq, stage, "confirm", _look(stage), **picked(draft))
        assert saved["stored"] is True, saved


def _clear_sources(seq: str) -> None:
    state = load_state(seq)
    research = state.get("research")
    if not isinstance(research, dict):
        research = {}
    research["summary"] = {"sources": []}
    research["full"] = None
    state["research"] = research
    state["papers"] = []
    save_state(seq, state)


def _plant(module: str, brief: str) -> str:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


def _report(title: str, sections: list[dict[str, str]]) -> dict:
    return {
        "title": title,
        "word_count": {"counted": 12, "stated": 800},
        "sections": sections,
        "figures": [],
        "tables": [],
        "sources": [],
    }


def _module(tag: str, number: int) -> str:
    return f"VOI{tag}{number:02d}AA"


def _refuse_saved_stage(seq: str, ask: str) -> dict:
    refused = essay_stage(seq, "1", "draft", ask)
    assert refused["ok"] is False, refused
    assert refused["refused"] == "turn"
    assert refused["stored"] is False
    assert refused["wrote"] is False
    assert refused["next"] == redirect_for(ask)
    assert load_pointer(seq)["saved"] == []
    return refused


def _stage5_autosave(module: str) -> None:
    seq = open_sequence(module)
    planted = {
        "current": "5",
        "saved": ["1", "2", "3", "4a", "4b"],
        "files": {},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": False,
        "waiting_stage": None,
        "waiting_digest": None,
        "revision": 4,
    }
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(planted), encoding="utf-8")
    assert stage_uses_confirm_card("5") is False
    assert advances_without_confirm("5") == "6"
    stored = essay_stage(seq, "5", "draft", "The first full draft names the corridor.")
    assert stored["ok"] is True, stored
    assert stored["stored"] is True
    assert stored.get("card") is None
    assert load_pointer(seq)["current"] == "6"
    assert "5" in load_pointer(seq)["saved"]
    assert "6" not in load_pointer(seq)["saved"]
    assert STAGE5_SAVE_LINE in saved_next("5", stage_title("5"))


def _silent_cover(module: str) -> list[str]:
    seq = _plant(module, f"Module code: {module}\nStudents meet on Tuesdays.\n")
    body = pack(seq)
    body["title"] = TITLE
    body["conclusion"] = "open"
    body["student_name"] = NAME
    body["student_number"] = NUMBER
    body["registration_number"] = NUMBER
    return cover_lines(seq, body, _report(TITLE, body["sections"]))


def _seat_once(path: Path, name: str) -> None:
    source = _read(path)
    assert source.count(f'id="{name}"') == 1
    assert source.count(f'"""{name}:') == 1


def _assert_refusals(tag: str) -> None:
    source = open_sequence(_module(tag, 1))
    _through(source, "4a")
    draft = essay_stage(source, "4a", "draft", _look("4a"))
    assert draft["ok"] is True, draft
    assert draft["card"]["kind"] == "confirm"
    refused = essay_stage(source, "4a", "confirm", _look("4a"), **picked(draft))
    assert refused["next"] == SOURCE_NEXT
    assert not refused["next"].startswith("Open the Confirm card")
    assert SOURCE_REASON in refused["reason"]
    assert refused["card"]["kind"] == "confirm"
    assert refused["card"]["stage"] == "4a"
    assert refused["stored"] is False
    assert "4a" not in load_pointer(source)["saved"]

    bibliography = open_sequence(_module(tag, 2))
    _through(bibliography, "4b")
    drafted = essay_stage(bibliography, "4b", "draft", _look("4b"))
    assert drafted["card"]["stage"] == "4b"
    _clear_sources(bibliography)
    blocked = essay_stage(bibliography, "4b", "confirm", _look("4b"), **picked(drafted))
    assert blocked["next"] == BIBLIOGRAPHY_NEXT
    assert not blocked["next"].startswith("Open the Confirm card")
    assert BIBLIOGRAPHY_REASON in blocked["reason"]
    assert blocked["card"]["kind"] == "confirm"
    assert blocked["card"]["stage"] == "4b"
    assert blocked["stored"] is False
    assert "4b" not in load_pointer(bibliography)["saved"]


def _assert_asks(tag: str) -> None:
    assert REDIRECT_WHOLE == WHOLE
    assert REDIRECT_ORDER == ORDER
    seq = open_sequence(_module(tag, 3))
    for ask, expected in (
        ("write my essay", REDIRECT_WHOLE),
        ("just write it", REDIRECT_WHOLE),
        ("finish the essay for me", REDIRECT_WHOLE),
        ("can we skip ahead", REDIRECT_ORDER),
        ("write the whole essay now", REDIRECT_WHOLE),
        ("skip the stages", REDIRECT_ORDER),
        ("make it sound less like AI", text("front_office/chat.md", "redirect_voice")),
        ("beat the detector", text("front_office/chat.md", "redirect_close")),
    ):
        assert redirect_for(ask) == expected
        assert _refuse_saved_stage(seq, ask)["next"] == expected
    for near in (
        "write my essay plan",
        "I wrote the essay introduction",
        "skip the questions",
    ):
        assert redirect_for(near) is None
        drafted = essay_stage(seq, "1", "draft", near)
        assert drafted.get("refused") != "turn"
        assert drafted["stored"] is False
    assert load_pointer(seq)["saved"] == []


def _assert_all_fine(tag: str) -> None:
    assert ALL_FINE in STAGE7_LINE
    assert "all fine saves" not in STAGE7_LINE.casefold()
    assert answers_mean_no_change("all fine") is True
    seq = open_sequence(_module(tag, 4))
    _through(seq, "7")
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("The firm cut emissions in 2024.")
    document.save(str(path))
    asked = essay_stage(seq, "7", "draft", SENTENCE)
    assert asked["ok"] is True, asked
    assert ALL_FINE in asked["next"]
    assert asked["questions"] == list(_QUESTIONS)
    opened = essay_stage(seq, "7", "confirm", "all fine")
    assert opened["ok"] is True, opened
    assert opened["stored"] is False
    assert opened["card"]["kind"] == "confirm"
    assert "7" not in load_pointer(seq)["saved"]


def _assert_empty_plan(tag: str) -> None:
    empty = _plant(
        _module(tag, 5),
        "Genre: essay\nQuestion: How does the corridor hold?\n",
    )
    for stage in ("1", "2"):
        draft = essay_stage(empty, stage, "draft", _look(stage))
        saved = essay_stage(empty, stage, "confirm", _look(stage), **picked(draft))
        assert saved["stored"] is True, saved
    empty_draft = essay_stage(empty, "3", "draft", EMPTY_PLAN)
    assert empty_draft["ok"] is True, empty_draft
    empty_saved = front_office_call(
        "essay.stage",
        {
            "essay_id": empty,
            "stage": "3",
            "confirmPhase": "confirm",
            "look": EMPTY_PLAN,
            **picked(empty_draft),
        },
    )
    assert empty_saved["stored"] is True, empty_saved
    assert DEPTH_PROMPT not in empty_saved["next"]
    ask = (empty_saved.get("encourage") or {}).get("ask") or {}
    assert ask.get("prompt") != DEPTH_PROMPT
    assert "which part" not in empty_saved["next"].casefold()


def _assert_stage9() -> None:
    template = _read(REPO / "src" / "essay_writer" / "prompts" / "stages" / "09.md")
    helpers = _read(REPO / "docs" / "academic-writing-helpers.md")
    snapshot = _snapshot()
    assert NEW_STAGE9 in template
    assert OLD_STAGE9 not in template
    assert f"- {NEW_STAGE9}" in helpers
    assert OLD_STAGE9 not in helpers
    assert NEW_STAGE9 in CHECKLISTS["9"]
    assert OLD_STAGE9 not in "\n".join(CHECKLISTS["9"])
    for key in ("9:none", "9:essay", "9:report", "9:diary"):
        assert NEW_STAGE9 in snapshot["stage_rules"][key]
        assert OLD_STAGE9 not in snapshot["stage_rules"][key]
    for launch in (stage_launch("9"), cursor_stage_launch("9")):
        assert NEW_STAGE9 in launch["settings"]["rules"]
        assert OLD_STAGE9 not in launch["settings"]["rules"]


def _assert_brief_stage5_and_cover(tag: str) -> None:
    assert stage_title("2", None) == "Establish the focus"
    assert stage_title("3", None) == "Write the plan"
    assert stage_title("10") == "Finish the Word file"
    module = _module(tag, 6)
    seq = _plant(module, f"Module code: {module}\nStudents meet on Tuesdays.\n")
    folder = essay_dir(module)
    brief = folder / "brief.md"
    before = brief.read_bytes()
    meta = folder / "brief-meta.json"
    assert not meta.exists()
    quiet = essay_stage(seq, "1", "draft", "A sentence of my own for this stage.")
    assert quiet["ok"] is True, quiet
    assert brief.read_bytes() == before
    assert not meta.exists()
    reply = essay_stage(
        seq,
        "1",
        "draft",
        formatAnswer="essay",
        questionAnswer=QUESTION,
    )
    assert reply["ok"] is True, reply
    assert reply.get("refused") != "guidance-only"
    assert brief.read_bytes() == before
    stored = json.loads(meta.read_text(encoding="utf-8"))
    assert stored["format"] == "essay"
    assert stored["question"] == QUESTION
    seen = read_assignment(seq)
    assert seen["format"] == "essay"
    assert seen["question"] == QUESTION
    assert stage_title("2", None) == "Establish the focus"

    _stage5_autosave(_module(tag, 7))
    lines = _silent_cover(_module(tag, 8))
    assert lines[0] == TITLE
    for line in PROGRAMME_LINES:
        assert line not in lines
    assert COVER_NOTED not in lines
    assert COVER_OPEN not in lines
    assert NAME not in lines
    assert NUMBER not in lines
    assert title_page_spec(f"Module code: {module}\nStudents meet on Tuesdays.\n")["programme"] is False

    asked_module = _module(tag, 9)
    asked = _plant(
        asked_module,
        "Genre: essay\nQuestion: How does the corridor hold?\n"
        "Title page: programme name and partner institution.\n",
    )
    asked_body = pack(asked)
    asked_body["title"] = TITLE
    asked_lines = cover_lines(asked, asked_body, _report(TITLE, asked_body["sections"]))
    for line in PROGRAMME_LINES:
        assert line in asked_lines
    assert asked_lines[0] == TITLE


def _assert_parent_cases(tag: str) -> None:
    _assert_refusals(tag)
    _assert_asks(tag)
    _assert_all_fine(tag)
    _assert_empty_plan(tag)
    _assert_stage9()
    _assert_brief_stage5_and_cover(tag)


def _seat_parents() -> None:
    seats = (
        (REPO / "tests" / "test_essay_traps.py", TRAPS_IDS),
        (REPO / "tests" / "test_essay_cover.py", COVER_IDS),
        (REPO / "tests" / "test_essay_promise.py", PROMISE_IDS),
        (REPO / "tests" / "test_stored_brief_answer.py", ASK_IDS),
    )
    for path, names in seats:
        for name in names:
            _seat_once(path, name)


@pytest.mark.parametrize("case_id", [pytest.param("essay-voice-a1", id="essay-voice-a1")])
def test_the_chat_sounds_like_a_helpful_friend(case_id):
    """essay-voice-a1: The persona is the helpful friend. The banking sentence is gone."""
    assert case_id == "essay-voice-a1"
    _assert_friend_sources()
    assert 'version = "0.9.2"' in _read(REPO / "pyproject.toml")


@pytest.mark.parametrize("case_id", [pytest.param("essay-voice-b1", id="essay-voice-b1")])
def test_stage_six_says_the_next_step_asks_and_edits(case_id):
    """essay-voice-b1: Stage 6 keeps the student's edit, then names the next step."""
    assert case_id == "essay-voice-b1"
    _assert_stage6_sentence()


@pytest.mark.parametrize("case_id", [pytest.param("essay-voice-c1", id="essay-voice-c1")])
def test_earlier_cases_still_hold(case_id, workspace):
    """essay-voice-c1: The smaller traps, the cover, the promise, and the stored answers still hold."""
    assert case_id == "essay-voice-c1"
    _seat_parents()
    _assert_parent_cases("11")
    assert 'version = "0.9.2"' in _read(REPO / "pyproject.toml")


@pytest.mark.parametrize("case_id", [pytest.param("essay-voice-d1", id="essay-voice-d1")])
def test_a_partial_update_keeps_the_voice_and_the_saves(case_id, workspace):
    """essay-voice-d1: A partial update must not leave the old persona or the earlier saves wrong."""
    assert case_id == "essay-voice-d1"
    _assert_friend_sources()
    _assert_stage6_sentence()
    _assert_parent_cases("21")
    for name in VOICE_IDS:
        _seat_once(Path(__file__), name)
    briefing = _read(REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md")
    assert "Do not invent a Documents path." in briefing
    first_run = _read(REPO / "FIRST-RUN.txt")
    packaged = _read(REPO / "src" / "essay_writer" / "FIRST-RUN.txt")
    assert first_run == packaged
    assert first_run.startswith(FIRST_RUN_OPENING)
    assert FRIEND not in first_run
    assert NEXT_STEP not in first_run
    assert "Do not fall back to Documents and call it this computer." in first_run
    assert 'version = "0.9.2"' in _read(REPO / "pyproject.toml")
