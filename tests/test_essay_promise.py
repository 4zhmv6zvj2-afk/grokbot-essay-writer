"""Stage 5 promise, opening choices, and titles until the genre is known.

The student decides when each stage is saved. The first full draft is saved
when it is written, then shown. Stage 5 still saves on that draft. Stages 2
and 3 use one neutral title until a label, a cue, or a stored answer names
the genre. Stage 10 is Finish the Word file.

Ids are seated once. The id is the docstring and the pytest id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import open_sequence

from essay_writer.assignment_gate import (
    FORMAT_NAMED_ONE,
    QUESTION_NAMED_ONE,
    read_assignment,
)
from essay_writer.health import essay_health
from essay_writer.paths import essay_dir
from essay_writer.prompt_loader import render_tokens, text
from essay_writer.server import INSTRUCTIONS
from essay_writer.specialists.grok_bot import STAGE5_SAVE_LINE, confirm_line, saved_next
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage_llm import STAGE_TITLES, brief_genre, stage_settings, stage_title
from essay_writer.stage_track import essay_stage
from essay_writer.student_turns import (
    FIRST_TURN_CARD,
    OPENING_CONTINUE,
    OPENING_NEW,
    OPENING_ROLL,
)

REPO = Path(__file__).resolve().parents[1]
BOT = REPO / "docs" / "templates" / "bot.md"
SNAPSHOT = REPO / "tests" / "snapshots" / "prompts.json"
CHAT = REPO / "src" / "essay_writer" / "prompts" / "front_office" / "chat.md"
BRIEFING = REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md"
READ_LIST = (
    "Read the draft and edit it yourself. Look for a fact made smoother or more "
    "important than the source, a line that says experts say or research shows with "
    "no source you opened, and a quotation, page, or finding you cannot find in the "
    "opened file. Also look for empty praise, an empty contrast, a decorative list "
    "of three, and use *is* instead of *serves as*. A real contrast stays. This is "
    "not a score, and the draft is not rewritten for you."
)
OLD_PHRASE = "serves as where is would do"
NEUTRAL_TWO = "Establish the focus"
NEUTRAL_THREE = "Write the plan"
STAGE_TEN = "Finish the Word file"
OLD_STAGE_TEN = "Submit the final draft"
SILENT = "Module code: PRM1001AA\nStudents meet on Tuesdays in the seminar room.\n"
QUESTION = "Evaluate how Northwind Components could close the material loop."
COURSE_RULES = "Check what your course allows for AI — I do not know the rules for your course."
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


def _plant(module: str, brief: str) -> str:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return open_sequence(module)


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-a1", id="essay-promise-a1")])
def test_the_opening_card_states_both_save_facts(case_id):
    """essay-promise-a1: The card says who saves each stage, and that the first draft is saved when written."""
    assert case_id == "essay-promise-a1"
    card = text("front_office/chat.md", "first_turn_card")
    assert card == FIRST_TURN_CARD
    assert "you decide when each stage is saved, except the first full draft" in card
    assert STAGE5_SAVE_LINE in card
    assert "I do not submit it" in card
    assert COURSE_RULES in card
    assert OLD_PHRASE not in card
    assert "nothing is saved until you say so" not in card
    assert render_tokens("{{chat:first_turn_card}}") == card
    assert card in INSTRUCTIONS
    assert card in BOT.read_text(encoding="utf-8")
    assert card in BRIEFING.read_text(encoding="utf-8") or (
        "{{chat:first_turn_card}}" in BRIEFING.read_text(encoding="utf-8")
    )
    assert essay_health()["first_turn_card"] == card
    assert _snapshot()["instructions"].count(card) == INSTRUCTIONS.count(card)
    assert card in _snapshot()["instructions"]


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-a2", id="essay-promise-a2")])
def test_the_line_that_opens_stage_5_names_the_save(case_id):
    """essay-promise-a2: Opening stage 5 says the draft is saved when it is written, then shown."""
    assert case_id == "essay-promise-a2"
    opened = saved_next("5", "Write your first draft")
    assert opened == ("Start Stage 5 — Write your first draft in this chat. " + STAGE5_SAVE_LINE)
    assert "Confirm" not in opened
    assert "checklist" not in opened.casefold()
    assert stage_uses_confirm_card("5") is False
    assert advances_without_confirm("5") == "6"
    assert "Confirm card" not in saved_next("5", stage_title("5"))


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-a3", id="essay-promise-a3")])
def test_three_opening_choices_are_pinned_student_lines(case_id):
    """essay-promise-a3: New, continue, and roll forward each have one short student line."""
    assert case_id == "essay-promise-a3"
    assert text("front_office/chat.md", "opening_new") == OPENING_NEW == "Start a new essay."
    assert (
        text("front_office/chat.md", "opening_continue")
        == OPENING_CONTINUE
        == "Continue a sequence you name."
    )
    assert (
        text("front_office/chat.md", "opening_roll")
        == OPENING_ROLL
        == "Copy an earlier sequence into a new one."
    )
    spoken = f"{OPENING_NEW} {OPENING_CONTINUE} {OPENING_ROLL}"
    assert "essay.sequence.new" not in spoken
    assert spoken.count(".") == 3
    rendered = render_tokens("{{chat:opening_new}} {{chat:opening_continue}} {{chat:opening_roll}}")
    assert rendered == spoken
    assert OPENING_NEW in INSTRUCTIONS
    assert OPENING_CONTINUE in INSTRUCTIONS
    assert OPENING_ROLL in INSTRUCTIONS
    bot = BOT.read_text(encoding="utf-8")
    assert OPENING_NEW in bot
    assert OPENING_CONTINUE in bot
    assert OPENING_ROLL in bot
    host = text("front_office/chat.md", "opening_choice")
    assert "essay.sequence.new" in host
    assert "A is a new essay" in host


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-a4", id="essay-promise-a4")])
def test_the_stage_6_read_list_changes_one_phrase(case_id):
    """essay-promise-a4: The stage 6 read list changes one phrase and keeps every other line."""
    assert case_id == "essay-promise-a4"
    read_list = text("front_office/chat.md", "stage6_read_list")
    assert read_list == READ_LIST
    assert "use *is* instead of *serves as*" in read_list
    assert OLD_PHRASE not in read_list
    assert read_list.count("\n") == 0
    chat = CHAT.read_text(encoding="utf-8")
    assert chat.count("use *is* instead of *serves as*") == 1
    reviewer = (REPO / "src" / "essay_writer" / "prompts" / "review" / "eqr.md").read_text(
        encoding="utf-8"
    )
    assert "serves as where the sentence means is" in reviewer
    assert "use *is* instead of *serves as*" not in reviewer


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-b1", id="essay-promise-b1")])
def test_an_unset_genre_uses_the_neutral_titles(case_id, workspace):
    """essay-promise-b1: Until the genre is known, the titles are Establish the focus and Write the plan."""
    assert case_id == "essay-promise-b1"
    assert stage_title("2", None) == NEUTRAL_TWO
    assert stage_title("3", None) == NEUTRAL_THREE
    assert STAGE_TITLES["2"] == NEUTRAL_TWO
    assert STAGE_TITLES["3"] == NEUTRAL_THREE

    seq = _plant("PRM2101AA", SILENT)
    folder = essay_dir("PRM2101AA")
    before = (folder / "brief.md").read_bytes()
    assert read_assignment(seq)["format"] is None
    assert brief_genre(seq) is None
    assert stage_title("2", brief_genre(seq)) == NEUTRAL_TWO
    assert stage_title("3", brief_genre(seq)) == NEUTRAL_THREE
    assert (folder / "brief.md").read_bytes() == before
    assert not (folder / "brief-meta.json").exists()

    both = _plant(
        "PRM2102AA",
        "This assignment is an essay or a report.\nStudents should evaluate sources in class.\n",
    )
    assert read_assignment(both)["format"] is None
    assert brief_genre(both) is None
    assert stage_title("2", brief_genre(both)) == NEUTRAL_TWO
    assert stage_title("3", brief_genre(both)) == NEUTRAL_THREE

    ignored = _plant("PRM2103AA", SILENT)
    essay_stage(ignored, "1", "draft", formatAnswer="novel")
    assert read_assignment(ignored)["format"] is None
    assert stage_title("2", brief_genre(ignored)) == NEUTRAL_TWO
    assert stage_title("3", brief_genre(ignored)) == NEUTRAL_THREE


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-b2", id="essay-promise-b2")])
def test_a_named_genre_keeps_its_single_label(case_id, workspace):
    """essay-promise-b2: A label, a cue, or a stored answer that names the genre keeps that label."""
    assert case_id == "essay-promise-b2"
    labelled = _plant("PRM3101AA", "Genre: essay\nStudents meet on Tuesdays.\n")
    assert brief_genre(labelled) == "essay"
    assert stage_title("2", brief_genre(labelled)) == "Establish a thesis"
    assert stage_title("3", brief_genre(labelled)) == "Write an essay plan"

    cue = _plant("PRM3102AA", "Assessment: Individual report\nStudents meet on Tuesdays.\n")
    assert read_assignment(cue)["format"] == "report"
    assert brief_genre(cue) == "report"
    assert stage_title("2", brief_genre(cue)) == "Establish purpose and scope"
    assert stage_title("3", brief_genre(cue)) == "Write a report plan"

    diary = _plant("PRM3103AA", "Assessment: reflective diary\nWhat changed on the ward?\n")
    assert brief_genre(diary) == "diary"
    assert stage_title("2", brief_genre(diary)) == "Establish the entries"
    assert stage_title("3", brief_genre(diary)) == "Write a diary plan"

    for module, answer, genre, second, third in (
        ("PRM3201AA", "essay", "essay", "Establish a thesis", "Write an essay plan"),
        ("PRM3202AA", "report", "report", "Establish purpose and scope", "Write a report plan"),
        ("PRM3203AA", "reflective diary", "diary", "Establish the entries", "Write a diary plan"),
    ):
        seq = _plant(module, SILENT.replace("PRM1001AA", module))
        essay_stage(seq, "1", "draft", formatAnswer=answer)
        assert read_assignment(seq)["format"] == answer
        assert brief_genre(seq) == genre
        assert stage_title("2", brief_genre(seq)) == second
        assert stage_title("3", brief_genre(seq)) == third

    won = _plant("PRM3301AA", "Assessment: Individual report\nStudents meet on Tuesdays.\n")
    essay_stage(won, "1", "draft", formatAnswer="essay")
    assert read_assignment(won)["format"] == "report"
    assert brief_genre(won) == "report"
    assert stage_title("2", brief_genre(won)) == "Establish purpose and scope"


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-b3", id="essay-promise-b3")])
def test_stage_10_is_finish_the_word_file(case_id):
    """essay-promise-b3: Stage 10 is Finish the Word file, and the card still says the tool does not submit."""
    assert case_id == "essay-promise-b3"
    assert STAGE_TITLES["10"] == STAGE_TEN
    assert stage_title("10") == STAGE_TEN
    assert stage_title("10", "essay") == STAGE_TEN
    assert stage_title("10", "report") == STAGE_TEN
    assert stage_title("10", "diary") == STAGE_TEN
    assert "does not submit" in confirm_line("10", None)
    rules = _snapshot()["stage_rules"]
    for genre in ("none", "essay", "report", "diary"):
        body = stage_settings("10", None if genre == "none" else genre)["rules"]
        assert body.startswith(f"Rules for stage 10 — {STAGE_TEN}.")
        assert rules[f"10:{genre}"] == body
        assert OLD_STAGE_TEN not in body
    roots = (REPO / "src", REPO / "docs", REPO / "tools", REPO / "tests")
    hits: list[str] = []
    for root in roots:
        for item in root.rglob("*"):
            if not item.is_file() or item.suffix not in {".py", ".md", ".json"}:
                continue
            if item.resolve() == Path(__file__).resolve():
                continue
            if OLD_STAGE_TEN in item.read_text(encoding="utf-8", errors="ignore"):
                hits.append(item.relative_to(REPO).as_posix())
    assert hits == []


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-c1", id="essay-promise-c1")])
def test_stored_answers_cues_and_gap_lines_still_hold(case_id, workspace):
    """essay-promise-c1: A stored answer, a cue, and an honest gap line still hold. The brief file stays."""
    assert case_id == "essay-promise-c1"
    folder = essay_dir("PRM4101AA")
    folder.mkdir(parents=True, exist_ok=True)
    brief = folder / "brief.md"
    brief.write_text(SILENT, encoding="utf-8")
    before = brief.read_bytes()
    seq = open_sequence("PRM4101AA")
    reply = essay_stage(seq, "1", "draft", formatAnswer="report", questionAnswer=QUESTION)
    assert reply["ok"] is True, reply
    assert reply.get("refused") != "guidance-only"
    seen = read_assignment(seq)
    assert seen["format"] == "report"
    assert seen["question"] == QUESTION
    assert brief.read_bytes() == before
    assert "Question:" not in brief.read_text(encoding="utf-8")
    assert brief_genre(seq) == "report"

    cue = _plant(
        "PRM4102AA",
        "Assessment: Individual report\nEvaluate how the firm should publish the figure.\n",
    )
    record = read_assignment(cue)
    assert record["format"] == "report"
    assert record["question"] == "Evaluate how the firm should publish the figure."
    assert "Genre:" not in (essay_dir("PRM4102AA") / "brief.md").read_text(encoding="utf-8")

    silent = _plant("PRM4103AA", "Module code: PRM4103AA\n")
    assert read_assignment(silent)["format"] is None
    assert read_assignment(silent)["question"] is None
    from essay_writer.specialists.grok_bot import basics_pass_lines

    _scores, format_line, question_line = basics_pass_lines(silent)
    assert format_line == FORMAT_NAMED_ONE
    assert question_line == QUESTION_NAMED_ONE
    assert stage_title("2", brief_genre(silent)) == NEUTRAL_TWO


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-c2", id="essay-promise-c2")])
def test_parent_answer_cases_are_still_seated(case_id, workspace):
    """essay-promise-c2: The stored-answer cases from essay-ask-a1 through essay-ask-d1 are still seated."""
    assert case_id == "essay-promise-c2"
    parent = (REPO / "tests" / "test_stored_brief_answer.py").read_text(encoding="utf-8")
    for name in ASK_IDS:
        assert parent.count(f'id="{name}"') == 1
        assert parent.count(f'"""{name}:') == 1
    seq = _plant("PRM5101AA", SILENT)
    folder = essay_dir("PRM5101AA")
    before = (folder / "brief.md").read_bytes()
    reply = essay_stage(seq, "1", "draft", formatAnswer="essay", questionAnswer=QUESTION)
    assert reply.get("refused") != "guidance-only"
    assert read_assignment(seq)["format"] == "essay"
    assert read_assignment(seq)["question"] == QUESTION
    assert (folder / "brief.md").read_bytes() == before
    assert stage_title("2", brief_genre(seq)) == "Establish a thesis"


@pytest.mark.parametrize("case_id", [pytest.param("essay-promise-d1", id="essay-promise-d1")])
def test_a_partial_update_does_not_leave_the_copies_apart(case_id, workspace):
    """essay-promise-d1: The card, the stage 10 title, the brief, and the stage 5 save stay in step."""
    assert case_id == "essay-promise-d1"
    card = text("front_office/chat.md", "first_turn_card")
    bot = BOT.read_text(encoding="utf-8")
    snapshot = _snapshot()
    assert card in bot
    assert card in snapshot["instructions"]
    assert card in INSTRUCTIONS
    assert "nothing is saved until you say so" not in bot
    assert "nothing is saved until you say so" not in snapshot["instructions"]
    assert OLD_STAGE_TEN not in bot
    assert OLD_STAGE_TEN not in snapshot["instructions"]
    assert OLD_STAGE_TEN not in json.dumps(snapshot["stage_rules"])
    assert STAGE_TEN in snapshot["stage_rules"]["10:none"]
    assert advances_without_confirm("5") == "6"
    assert STAGE5_SAVE_LINE in saved_next("5", stage_title("5"))

    seq = _plant("PRM6101AA", SILENT)
    folder = essay_dir("PRM6101AA")
    before = (folder / "brief.md").read_bytes()
    assert brief_genre(seq) is None
    assert stage_title("2", brief_genre(seq)) == NEUTRAL_TWO
    assert stage_title("3", brief_genre(seq)) == NEUTRAL_THREE
    assert read_assignment(seq)["format"] is None
    assert read_assignment(seq)["question"] is None
    assert (folder / "brief.md").read_bytes() == before
    assert not (folder / "brief-meta.json").exists()
    version = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.9.4"' in version
