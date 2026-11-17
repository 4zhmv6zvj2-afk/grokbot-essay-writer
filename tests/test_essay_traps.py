"""Smaller traps: a refused Confirm, short asks, stage 7, and stage 9.

A refused stage 4a or 4b draft names the missing piece, then Confirm, and
keeps the card. Other Confirm refusals still name the card. Short asks use
the approved replies. Stage 7 tells the student to say all fine. An empty
plan does not ask which part to lean on. A correct unchanged reference list
can be approved.

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
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import (
    STAGE5_SAVE_LINE,
    card_next,
    confirm_line,
    missing_confirm_next,
    saved_next,
    stage7_lead,
)
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage7 import _QUESTIONS, answers_mean_no_change
from essay_writer.stage_llm import stage_title
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.student_turns import _LIMIT as REDIRECT_LIMIT
from essay_writer.student_turns import (
    REDIRECT_ORDER,
    REDIRECT_WHOLE,
    STAGE7_LINE,
    redirect_for,
)
from essay_writer.word import cover_lines
from essay_writer.writing_basics import CHECKLISTS, STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
SENTENCE = "The corridor depends on one narrow strait."
SOURCE_NEXT = "Add a gathered source, then press Confirm."
BIBLIOGRAPHY_NEXT = "Add a bibliography, then press Confirm."
SOURCE_REASON = "Stage 4a stays here until a gathered source is on the list."
BIBLIOGRAPHY_REASON = "Stage 4b stays here until stage 4a has a bibliography."
OLD_STAGE9 = "Do not approve a save if references are unchanged from the last saved draft bundle."
NEW_STAGE9 = "If the list is wrong, fix it before approving. If it is right and unchanged, say so and approve."
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
COVER_IDS = (
    "essay-cover-a1",
    "essay-cover-a2",
    "essay-cover-a3",
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
    "essay-ask-a9",
    "essay-ask-b1",
    "essay-ask-b2",
    "essay-ask-b3",
    "essay-ask-b4",
    "essay-ask-c1",
    "essay-ask-c2",
    "essay-ask-d1",
    "essay-ask-d2",
)
HEADED_PLAN = "Central theme: The corridor stays open.\n1. Supply chain context\n2. Conclusion\n"
EMPTY_PLAN = (
    "Central theme: The corridor stays open.\n"
    "The draft follows that claim in one pass with no numbered parts.\n"
)
SILENT_BRIEF = "Module code: TRP1601AA\nStudents meet on Tuesdays.\n"


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


def _silent_cover(module: str) -> list[str]:
    seq = _plant(module, f"Module code: {module}\nStudents meet on Tuesdays.\n")
    body = pack(seq)
    body["title"] = TITLE
    body["conclusion"] = "open"
    body["student_name"] = NAME
    body["student_number"] = NUMBER
    body["registration_number"] = NUMBER
    return cover_lines(seq, body, _report(TITLE, body["sections"]))


def _refuse_saved_stage(seq: str, stage: str, ask: str) -> dict:
    refused = essay_stage(seq, stage, "draft", ask)
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
    assert stored.get("refused") != "guidance-only"
    assert load_pointer(seq)["current"] == "6"
    assert "5" in load_pointer(seq)["saved"]
    assert "6" not in load_pointer(seq)["saved"]
    assert STAGE5_SAVE_LINE in saved_next("5", stage_title("5"))


def _seat_once(path: Path, name: str) -> None:
    source = path.read_text(encoding="utf-8")
    assert source.count(f'id="{name}"') == 1
    assert source.count(f'"""{name}:') == 1


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-a1", id="essay-traps-a1")])
def test_refused_stage_4a_names_the_missing_source(case_id, workspace):
    """essay-traps-a1: A refused stage 4a draft names the missing source, then Confirm."""
    assert case_id == "essay-traps-a1"
    seq = open_sequence("TRP1101AA")
    _through(seq, "4a")
    draft = essay_stage(seq, "4a", "draft", _look("4a"))
    assert draft["ok"] is True, draft
    assert draft["card"]["kind"] == "confirm"
    refused = essay_stage(seq, "4a", "confirm", _look("4a"), **picked(draft))
    assert refused["ok"] is False, refused
    assert refused["stored"] is False
    assert refused["advanced"] is False
    assert refused["next"] == SOURCE_NEXT
    assert not refused["next"].startswith("Open the Confirm card")
    assert SOURCE_REASON in refused["reason"]
    assert refused["card"]["kind"] == "confirm"
    assert refused["card"]["stage"] == "4a"
    assert refused["cardDigest"] == draft["cardDigest"]
    assert load_pointer(seq)["current"] == "4a"
    assert "4a" not in load_pointer(seq)["saved"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-a2", id="essay-traps-a2")])
def test_refused_stage_4b_names_the_missing_bibliography(case_id, workspace):
    """essay-traps-a2: A refused stage 4b draft names the missing bibliography, then Confirm."""
    assert case_id == "essay-traps-a2"
    seq = open_sequence("TRP1201AA")
    _through(seq, "4b")
    draft = essay_stage(seq, "4b", "draft", _look("4b"))
    assert draft["ok"] is True, draft
    assert draft["card"]["stage"] == "4b"
    _clear_sources(seq)
    refused = essay_stage(seq, "4b", "confirm", _look("4b"), **picked(draft))
    assert refused["ok"] is False, refused
    assert refused["stored"] is False
    assert refused["advanced"] is False
    assert refused["next"] == BIBLIOGRAPHY_NEXT
    assert not refused["next"].startswith("Open the Confirm card")
    assert BIBLIOGRAPHY_REASON in refused["reason"]
    assert refused["card"]["kind"] == "confirm"
    assert refused["card"]["stage"] == "4b"
    assert refused["cardDigest"] == draft["cardDigest"]
    assert load_pointer(seq)["current"] == "4b"
    assert "4b" not in load_pointer(seq)["saved"]
    replies = (REPO / "src" / "essay_writer" / "stage_replies.py").read_text(encoding="utf-8")
    assert replies.count("lead=_MISSING_BIBLIOGRAPHY_NEXT") == 2
    assert replies.count(BIBLIOGRAPHY_REASON) == 2


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-a3", id="essay-traps-a3")])
def test_other_confirm_refusals_still_name_the_card(case_id, workspace):
    """essay-traps-a3: A stale card and a wrong stage still name the card. Typed yes stays the fallback."""
    assert case_id == "essay-traps-a3"
    fallback = missing_confirm_next("2", "Establish a thesis")
    assert fallback == (
        "Open the Confirm card for Stage 2 — Establish a thesis in this chat. "
        "If you cannot use the card, type yes to save that step."
    )
    assert card_next("4a", "Annotated bibliography").startswith(
        "Open the Confirm card to save Stage 4a"
    )
    replies = (REPO / "src" / "essay_writer" / "stage_replies.py").read_text(encoding="utf-8")
    assert replies.count("lead=_MISSING_SOURCE_NEXT") == 1

    seq = open_sequence("TRP1301AA")
    first = essay_stage(seq, "1", "draft", "The first note names the corridor.")
    assert first["ok"] is True, first
    second = essay_stage(seq, "1", "draft", "The second note names the corridor again.")
    assert second["ok"] is True, second
    stale = essay_stage(seq, "1", "confirm", "The first note names the corridor.", **picked(first))
    assert stale["ok"] is False, stale
    assert stale["stored"] is False
    assert stale["next"].startswith("Open the Confirm card")
    assert "Confirm card" in stale["next"]
    assert stale["next"] != SOURCE_NEXT
    assert "type yes to save that step" not in stale["next"].casefold()

    saved = essay_stage(seq, "1", "confirm", **picked(second))
    assert saved["stored"] is True, saved
    wrong = essay_stage(seq, "1", "confirm", "yes")
    assert wrong["stored"] is not True
    assert "Confirm card" in wrong["next"]
    assert "type yes to save that step" in wrong["next"].casefold()
    assert wrong["next"] != SOURCE_NEXT
    assert "2" not in load_pointer(seq)["saved"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-b1", id="essay-traps-b1")])
def test_short_asks_use_the_approved_replies(case_id, workspace):
    """essay-traps-b1: Write my essay, just write it, finish the essay for me, and skip ahead use the approved replies."""
    assert case_id == "essay-traps-b1"
    assert REDIRECT_LIMIT == 180
    assert REDIRECT_WHOLE == WHOLE
    assert REDIRECT_ORDER == ORDER
    assert text("front_office/chat.md", "redirect_whole") == WHOLE
    assert text("front_office/chat.md", "redirect_order") == ORDER
    seq = open_sequence("TRP1401AA")
    whole = (
        ("write my essay", REDIRECT_WHOLE),
        ("just write it", REDIRECT_WHOLE),
        ("finish the essay for me", REDIRECT_WHOLE),
        ("writing my essay", REDIRECT_WHOLE),
        ("finishing the essay for me", REDIRECT_WHOLE),
    )
    order = (
        ("can we skip ahead", REDIRECT_ORDER),
        ("skipping ahead", REDIRECT_ORDER),
    )
    for ask, expected in whole + order:
        assert redirect_for(ask) == expected
        assert _refuse_saved_stage(seq, "1", ask)["next"] == expected
    assert redirect_for("please write my essay today") is None
    assert redirect_for("hey write my essay") is None
    long_ask = "please " * 40 + "write my essay"
    assert len(long_ask) > REDIRECT_LIMIT
    assert redirect_for(long_ask) is None
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["current"] == "1"


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-b2", id="essay-traps-b2")])
def test_near_misses_stay_quiet_and_the_old_asks_do_not_save(case_id, workspace):
    """essay-traps-b2: Near misses return nothing. The four existing short asks still do not save."""
    assert case_id == "essay-traps-b2"
    seq = open_sequence("TRP1402AA")
    for ask, expected in (
        ("write the whole essay now", REDIRECT_WHOLE),
        ("skip the stages", REDIRECT_ORDER),
        ("make it sound less like AI", text("front_office/chat.md", "redirect_voice")),
        ("beat the detector", text("front_office/chat.md", "redirect_close")),
    ):
        assert redirect_for(ask) == expected
        assert _refuse_saved_stage(seq, "1", ask)["reason"] == expected
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


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-c1", id="essay-traps-c1")])
def test_stage7_says_all_fine_and_that_answer_does_not_save(case_id, workspace):
    """essay-traps-c1: If the draft is fine, say all fine. That answer does not itself save."""
    assert case_id == "essay-traps-c1"
    assert ALL_FINE in STAGE7_LINE
    assert "all fine saves" not in STAGE7_LINE.casefold()
    assert len(_QUESTIONS) == 5
    lead = stage7_lead(list(_QUESTIONS), "Ask for feedback")
    assert lead.startswith(STAGE7_LINE + " ")
    for question in _QUESTIONS:
        assert question in lead
    assert answers_mean_no_change("all fine") is True
    assert answers_mean_no_change("no changes") is True
    assert answers_mean_no_change("none") is True
    seq = open_sequence("TRP1501AA")
    _through(seq, "7")
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("The firm cut emissions in 2024.")
    document.save(str(path))
    asked = essay_stage(seq, "7", "draft", SENTENCE)
    assert asked["ok"] is True, asked
    assert asked["questions"] == list(_QUESTIONS)
    assert ALL_FINE in asked["next"]
    assert "Please answer these questions" in asked["next"]
    assert "all fine saves" not in asked["next"].casefold()
    skipped = essay_stage(
        seq,
        "7",
        "confirm",
        "skip",
        cardAction=asked["cardAction"],
        cardDigest=asked["cardDigest"],
    )
    assert skipped["ok"] is False, skipped
    assert skipped["stored"] is not True
    assert "Skipping the questions does not save" in skipped["reason"]
    assert "7" not in load_pointer(seq)["saved"]
    opened = essay_stage(seq, "7", "confirm", "all fine")
    assert opened["ok"] is True, opened
    assert opened["stored"] is False
    assert opened["card"]["kind"] == "confirm"
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]
    for launch in (stage_launch("7"), cursor_stage_launch("7")):
        assert ALL_FINE in launch["settings"]["rules"]
    snapshot = json.loads((REPO / "tests" / "snapshots" / "prompts.json").read_text())
    assert ALL_FINE in snapshot["instructions"]
    assert ALL_FINE in snapshot["stage_rules"]["7:none"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-c2", id="essay-traps-c2")])
def test_empty_plan_does_not_ask_which_part_to_lean_on(case_id, workspace):
    """essay-traps-c2: With no section labels, do not ask which part the draft should lean on."""
    assert case_id == "essay-traps-c2"
    headed = _plant("TRP1502AA", "Genre: essay\nQuestion: How does the corridor hold?\n")
    for stage in ("1", "2"):
        draft = essay_stage(headed, stage, "draft", _look(stage))
        saved = essay_stage(headed, stage, "confirm", _look(stage), **picked(draft))
        assert saved["stored"] is True, saved
    headed_draft = essay_stage(headed, "3", "draft", HEADED_PLAN)
    assert headed_draft["ok"] is True, headed_draft
    headed_saved = front_office_call(
        "essay.stage",
        {
            "essay_id": headed,
            "stage": "3",
            "confirmPhase": "confirm",
            "look": HEADED_PLAN,
            **picked(headed_draft),
        },
    )
    assert headed_saved["stored"] is True, headed_saved
    assert DEPTH_PROMPT in headed_saved["next"]
    labels = [item["label"] for item in headed_saved["encourage"]["ask"]["options"]]
    assert labels[-2:] == ["Type your own", "Skip"]
    assert "Supply chain context" in labels

    empty = _plant("TRP1503AA", "Genre: essay\nQuestion: How does the corridor hold?\n")
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
    assert empty_saved["next"].startswith("Start Stage 4a")
    assert load_pointer(empty)["current"] == "4a"
    assert "3" in load_pointer(empty)["saved"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-d1", id="essay-traps-d1")])
def test_an_unchanged_reference_list_can_be_approved(case_id, workspace):
    """essay-traps-d1: If the reference list is right and unchanged, say so and approve."""
    assert case_id == "essay-traps-d1"
    template = (REPO / "src" / "essay_writer" / "prompts" / "stages" / "09.md").read_text()
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text()
    snapshot = json.loads((REPO / "tests" / "snapshots" / "prompts.json").read_text())
    assert NEW_STAGE9 in template
    assert OLD_STAGE9 not in template
    assert f"- {NEW_STAGE9}" in helpers
    assert OLD_STAGE9 not in helpers
    assert "### 10. Complete and submit your final draft" in helpers
    assert NEW_STAGE9 in CHECKLISTS["9"]
    assert OLD_STAGE9 not in "\n".join(CHECKLISTS["9"])
    leftovers = (REPO / "tests" / "test_leftovers_stage9_asks.py").read_text(encoding="utf-8")
    assert OLD_STAGE9 not in leftovers
    for key in ("9:none", "9:essay", "9:report", "9:diary"):
        assert NEW_STAGE9 in snapshot["stage_rules"][key]
        assert OLD_STAGE9 not in snapshot["stage_rules"][key]
    for launch in (stage_launch("9"), cursor_stage_launch("9")):
        assert NEW_STAGE9 in launch["settings"]["rules"]
        assert OLD_STAGE9 not in launch["settings"]["rules"]
    assert stage_launch("9")["settings"]["rules"] == cursor_stage_launch("9")["settings"]["rules"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-e1", id="essay-traps-e1")])
def test_earlier_cover_promise_and_answer_cases_still_hold(case_id, workspace):
    """essay-traps-e1: The Word-cover, promise, and stored-answer cases still hold on this tip."""
    assert case_id == "essay-traps-e1"
    cover = REPO / "tests" / "test_essay_cover.py"
    promise = REPO / "tests" / "test_essay_promise.py"
    answers = REPO / "tests" / "test_stored_brief_answer.py"
    for name in COVER_IDS:
        _seat_once(cover, name)
    for name in PROMISE_IDS:
        _seat_once(promise, name)
    for name in ASK_IDS:
        _seat_once(answers, name)

    assert stage_title("2", None) == "Establish the focus"
    assert stage_title("3", None) == "Write the plan"
    assert stage_title("10") == "Finish the Word file"
    assert "does not submit" in confirm_line("10", None)
    assert 'version = "0.9.5"' in (REPO / "pyproject.toml").read_text(encoding="utf-8")

    seq = _plant("TRP1601AA", SILENT_BRIEF)
    folder = essay_dir("TRP1601AA")
    brief = folder / "brief.md"
    before = brief.read_bytes()
    assert not (folder / "brief-meta.json").exists()
    reply = essay_stage(
        seq,
        "1",
        "draft",
        "A sentence of my own for this stage.",
        formatAnswer="essay",
        questionAnswer=QUESTION,
    )
    assert reply["ok"] is True, reply
    assert reply.get("refused") != "guidance-only"
    assert brief.read_bytes() == before
    seen = read_assignment(seq)
    assert seen["format"] == "essay"
    assert seen["question"] == QUESTION
    assert stage_title("2", None) == "Establish the focus"

    typed = open_sequence("TRP1602AA")
    waiting = essay_stage(typed, "1", "draft", SENTENCE)
    assert waiting["stored"] is False
    saved = essay_stage(typed, "1", "confirm", "yes")
    assert saved["stored"] is True, saved
    assert load_pointer(typed)["saved"] == ["1"]
    assert load_pointer(typed)["current"] == "2"

    _stage5_autosave("TRP1603AA")

    silent_lines = _silent_cover("TRP1604AA")
    assert silent_lines[0] == TITLE
    for line in PROGRAMME_LINES:
        assert line not in silent_lines
    assert COVER_NOTED not in silent_lines
    assert COVER_OPEN not in silent_lines
    assert NAME not in silent_lines
    assert NUMBER not in silent_lines
    assert (
        title_page_spec("Module code: TRP1604AA\nStudents meet on Tuesdays.\n")["programme"]
        is False
    )

    asked = _plant(
        "TRP1605AA",
        "Genre: essay\nQuestion: How does the corridor hold?\nTitle page: programme name and partner institution.\n",
    )
    asked_body = pack(asked)
    asked_body["title"] = TITLE
    asked_lines = cover_lines(asked, asked_body, _report(TITLE, asked_body["sections"]))
    for line in PROGRAMME_LINES:
        assert line in asked_lines
    assert asked_lines[0] == TITLE
    assert "Name:" not in asked_lines
    programme_name = title_page_spec("Title page: programme name and partner institution.")
    assert programme_name["name"] == "silent"
    for phrase in (
        "Title page: name of the programme and partner institution.",
        "Title page: programme's name and partner institution.",
    ):
        spec = title_page_spec(phrase)
        assert spec["name"] == "silent", phrase
        assert spec["programme"] is True, phrase


@pytest.mark.parametrize("case_id", [pytest.param("essay-traps-f1", id="essay-traps-f1")])
def test_a_partial_change_does_not_leave_the_traps(case_id, workspace):
    """essay-traps-f1: A partial update must not leave the refused next, the redirects, or the cover filler wrong."""
    assert case_id == "essay-traps-f1"
    seq = open_sequence("TRP1701AA")
    _through(seq, "4a")
    draft = essay_stage(seq, "4a", "draft", _look("4a"))
    refused = essay_stage(seq, "4a", "confirm", _look("4a"), **picked(draft))
    assert refused["next"] == SOURCE_NEXT
    assert refused["card"]["stage"] == "4a"
    assert SOURCE_REASON in refused["reason"]
    assert not refused["next"].startswith("Open the Confirm card")

    later = open_sequence("TRP1702AA")
    _through(later, "4b")
    drafted = essay_stage(later, "4b", "draft", _look("4b"))
    _clear_sources(later)
    blocked = essay_stage(later, "4b", "confirm", _look("4b"), **picked(drafted))
    assert blocked["next"] == BIBLIOGRAPHY_NEXT
    assert blocked["card"]["stage"] == "4b"
    assert "4b" not in load_pointer(later)["saved"]

    assert redirect_for("write my essay") == WHOLE
    assert redirect_for("just write it") == WHOLE
    assert redirect_for("finish the essay for me") == WHOLE
    assert redirect_for("can we skip ahead") == ORDER
    assert redirect_for("write the whole essay now") == WHOLE
    assert redirect_for("skip the stages") == ORDER
    for near in ("write my essay plan", "I wrote the essay introduction", "skip the questions"):
        assert redirect_for(near) is None
    assert ALL_FINE in STAGE7_LINE
    assert answers_mean_no_change("all fine") is True
    assert "all fine saves" not in STAGE7_LINE.casefold()

    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    template = (REPO / "src" / "essay_writer" / "prompts" / "stages" / "09.md").read_text()
    assert OLD_STAGE9 not in template
    assert OLD_STAGE9 not in helpers
    assert NEW_STAGE9 in template
    assert f"- {NEW_STAGE9}" in helpers

    folder_module = "TRP1703AA"
    brief_text = f"Module code: {folder_module}\nStudents meet on Tuesdays.\n"
    answered = _plant(folder_module, brief_text)
    folder = essay_dir(folder_module)
    brief = folder / "brief.md"
    meta = folder / "brief-meta.json"
    before = brief.read_bytes()
    assert not meta.exists()
    quiet = essay_stage(answered, "1", "draft", SENTENCE)
    assert quiet["ok"] is True, quiet
    assert brief.read_bytes() == before
    assert not meta.exists()
    reply = essay_stage(
        answered,
        "1",
        "draft",
        formatAnswer="report",
        questionAnswer="How should the firm publish the figure?",
    )
    assert reply.get("refused") != "guidance-only"
    assert brief.read_bytes() == before
    assert read_assignment(answered)["format"] == "report"

    _stage5_autosave("TRP1704AA")
    lines = _silent_cover("TRP1705AA")
    assert lines[0] == TITLE
    for line in PROGRAMME_LINES:
        assert line not in lines
    assert COVER_NOTED not in lines
    assert COVER_OPEN not in lines
    assert NAME not in lines
    assert NUMBER not in lines
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert stage_launch("9")["settings"]["rules"] == cursor_stage_launch("9")["settings"]["rules"]
