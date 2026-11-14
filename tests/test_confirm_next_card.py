"""A saved stage names the next stage and does not mint its Confirm card.

A guidance-only look is refused and writes no final look.
AC2: a closed pack or the wrong sequence does not mint a postable card.
AC3: the briefing posts only the door card for the current open sequence.
AC4: Build covered. Cursor and Grok Build share that Confirm path.
"""

import inspect
import json
from pathlib import Path

from helpers import open_sequence

from essay_writer.build_office import stage_launch
from essay_writer.confirm import save_draft
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.paths import essay_dir, work_dir
from essay_writer.prompt_loader import text as prompt_text
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.setup import SHELL_CURSOR, SHELL_GROK_BUILD
from essay_writer.shells import cursor_shell, front_office, mount_handler
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_replies import _save_confirm
from essay_writer.stage_state import TOOL, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.writing_basics import STAGE_ORDER

STAGE_CONFIRM_EACH = prompt_text("front_office/confirm.md", "stage_confirm_each")

REPO = Path(__file__).resolve().parents[1]
BOT = REPO / "docs" / "templates" / "bot.md"
WORKFLOW = REPO / "docs" / "workflow.md"
OPEN_CARD = (
    "Post a Confirm only when its cardDigest matches the door's latest result "
    "for the current open sequence. "
    "Refuse a closed pack, a wrong sequence, and inventing the next stage."
)
DIARY = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: RPT5001AA

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

The main body of the report is the diary. First person is allowed.

One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the decisions | thin | partial | sound | clear | exact and evidenced |
"""
REPORT = "Genre: report\nQuestion: How should the firm manage the corridor?\n"
SCHEME = "High Distinction (80-100): the question is answered with evidence\n"


def _brief(module: str, text: str, scheme: str | None = None) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")
    if scheme:
        (folder / "mark-scheme.md").write_text(scheme, encoding="utf-8")


def _live(**kwargs):
    """The function the stdio server mounts for essay.stage."""
    return mount_handler("essay.stage")(**kwargs)


def _card(body: dict, stage: str, essay_id: str) -> None:
    card = body["card"]
    assert card["kind"] == "confirm"
    assert card["stage"] == stage
    assert card["essay_id"] == essay_id
    assert body["cardAction"] == "confirm"
    assert body["cardDigest"] == card["digest"]
    assert len(body["cardDigest"]) == 64
    assert body.get("digest") != body["cardDigest"]


def _close(seq: str) -> str:
    pointer = load_pointer(seq)
    pointer["current"] = "10"
    pointer["saved"] = list(STAGE_ORDER)
    pointer["closed"] = True
    pointer["waiting_stage"] = None
    pointer["waiting_digest"] = None
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer), encoding="utf-8")
    return save_draft(
        seq,
        TOOL,
        {"essay_id": seq, "stage": "10", "look": "The final look stays on this pack."},
        {"stage": "10"},
    )


STUDENT = "Task: evaluate the corridor."
GUIDANCE_REASON = "Add your own sentence for this stage; the checklist alone is not a save"
GUIDANCE_NEXT = "One sentence of your own is the look. Add it in this chat, then save."
CHECKLIST_SENTENCE = "Before the save, the chat opens with a short Basics pass"
STAGE1_RULE = (
    "The Basics pass opens the reply, the task analysis is the look, "
    "and a reply that is only the Basics pass is refused."
)
CARD_SENTENCE = "The Confirm card for that stage is in this reply."


def _own(seq: str) -> str:
    return "\n".join(basics_pass_lines(seq)) + "\n" + STUDENT


def _save_stage1(module: str = "MOD1004AA") -> tuple[str, str, dict]:
    _brief(module, REPORT, SCHEME)
    seq = open_sequence(module)
    look = _own(seq)
    draft = _live(essay_id=seq, stage="1", confirmPhase="draft", look=look)
    assert draft["ok"] is True, draft
    saved = _live(
        essay_id=seq,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=draft["cardDigest"],
    )
    assert saved["stored"] is True, saved
    return seq, look, saved


def _refused(body: dict) -> None:
    assert body["ok"] is False, body
    assert body["refused"] == "guidance-only"
    assert body["reason"] == GUIDANCE_REASON
    assert body["next"] == GUIDANCE_NEXT
    assert body["wrote"] is False
    assert body["stored"] is False
    assert body.get("card") is None
    assert body.get("cardAction") is None
    assert body.get("cardDigest") is None


def test_confirm_names_the_next_stage_and_does_not_mint_its_card(workspace):
    """essay-u1-a1: a saved stage names the next stage and leaves the card fields off the reply.

    Both waiting fields are clear. saved_next does not say the Confirm card is in this reply.
    The confirm path does not mint the next card and does not roll the save back.
    """
    seq, _look, saved = _save_stage1()
    assert saved["next"].startswith("Start Stage 2 —")
    assert "in this chat" in saved["next"]
    assert CARD_SENTENCE not in saved["next"]
    assert saved.get("card") is None
    assert saved.get("cardAction") is None
    assert saved.get("cardDigest") is None
    pointer = load_pointer(seq)
    assert "1" in pointer["saved"]
    assert pointer["current"] == "2"
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None
    note = (work_dir(seq) / "tracking" / "1.md").read_text(encoding="utf-8")
    assert STUDENT in note
    assert "## Final look" in note
    from essay_writer.specialists.grok_bot import saved_next
    from essay_writer.stage_hold import _commit_with_next_card

    assert CARD_SENTENCE not in saved_next("2", "Title")
    assert CARD_SENTENCE not in saved_next("5", "Title")
    assert CARD_SENTENCE not in inspect.getsource(saved_next)
    commit = inspect.getsource(_commit_with_next_card)
    assert "_draft_next_card(" not in commit
    assert "_hold_confirm(" not in commit


def test_confirm_without_a_new_draft_does_not_advance(workspace):
    """essay-u1-a2: confirming the next stage with no new draft does not store it."""
    seq, _look, _saved = _save_stage1()
    pressed = _live(essay_id=seq, stage="2", confirmPhase="confirm")
    assert pressed.get("stored") is not True
    pointer = load_pointer(seq)
    assert pointer["current"] == "2"
    assert "2" not in pointer["saved"]
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None


def test_guidance_only_draft_writes_no_look(workspace):
    """essay-u1-b1: a draft with no look is refused, and confirming it does not store.

    waiting_stage and waiting_digest stay None. No tracking note is created.
    A later real note is left byte for byte when the empty look is sent again.
    """
    seq, look, _saved = _save_stage1()
    empty = _live(essay_id=seq, stage="2", confirmPhase="draft")
    _refused(empty)
    pointer = load_pointer(seq)
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None
    note = work_dir(seq) / "tracking" / "2.md"
    assert not note.is_file()
    pressed = _live(essay_id=seq, stage="2", confirmPhase="confirm")
    assert pressed.get("stored") is not True
    again = _live(essay_id=seq, stage="2", confirmPhase="confirm", look="")
    assert again.get("stored") is not True
    assert not note.is_file()
    assert "2" not in load_pointer(seq)["saved"]
    real = _live(
        essay_id=seq,
        stage="2",
        confirmPhase="draft",
        look="The corridor needs a second reading.",
    )
    assert real["ok"] is True, real
    before = note.read_bytes()
    repeat = _live(essay_id=seq, stage="2", confirmPhase="draft")
    _refused(repeat)
    assert note.read_bytes() == before
    text = note.read_text(encoding="utf-8")
    assert CHECKLIST_SENTENCE not in text.split("## Working look", 1)[-1]
    assert look not in text


def test_guidance_blocks_and_the_previous_look_are_refused(workspace):
    """essay-u1-b2: basics, the stage overlay, and the previous stage's text are not a look.

    Joining those blocks in either order is still refused. Confirm does not store.
    """
    from essay_writer.stage_llm import prompt_overlay

    seq, previous, _saved = _save_stage1()
    basics = "\n".join(basics_pass_lines(seq))
    overlay = prompt_overlay("2", "report")
    looks = (
        basics,
        overlay,
        previous,
        basics.swapcase(),
        f"{basics}\n{overlay}",
        f"{overlay}\n{basics}",
    )
    note = work_dir(seq) / "tracking" / "2.md"
    for look in looks:
        drafted = _live(essay_id=seq, stage="2", confirmPhase="draft", look=look)
        _refused(drafted)
        confirmed = _live(essay_id=seq, stage="2", confirmPhase="confirm", look=look)
        _refused(confirmed)
        assert not note.is_file()
        assert "2" not in load_pointer(seq)["saved"]
        assert load_pointer(seq)["waiting_stage"] is None
        assert load_pointer(seq)["waiting_digest"] is None


def test_a_student_sentence_returns_a_card_and_confirm_clears_waiting(workspace):
    """essay-u1-b3: one sentence of the student's own returns a card, and Confirm stores that stage.

    A short real note also saves. Both waiting fields are None after the save.
    """
    seq, _look, _saved = _save_stage1()
    sentence = "The corridor needs a second reading."
    draft = _live(essay_id=seq, stage="2", confirmPhase="draft", look=sentence)
    assert draft["ok"] is True, draft
    assert draft["card"]["stage"] == "2"
    assert draft["cardAction"] == "confirm"
    assert draft["cardDigest"]
    saved = _live(
        essay_id=seq,
        stage="2",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=draft["cardDigest"],
    )
    assert saved["stored"] is True, saved
    assert saved.get("card") is None
    pointer = load_pointer(seq)
    assert "2" in pointer["saved"]
    assert "3" not in pointer["saved"]
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None
    short = open_sequence("RPT1008AA")
    brief = _live(essay_id=short, stage="1", confirmPhase="draft", look="Pass.")
    assert brief["ok"] is True, brief
    assert brief["card"]["stage"] == "1"
    kept = _live(
        essay_id=short,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=brief["cardDigest"],
    )
    assert kept["stored"] is True, kept
    assert "Pass." in (work_dir(short) / "tracking" / "1.md").read_text(encoding="utf-8")


def test_stage1_rule_refuses_a_basics_only_reply(workspace):
    """essay-u1-c1: the stage 1 rule says a Basics-only reply is refused, and the draft agrees.

    The sentence is in the stage 1 checklist, not in the checklist walk.
    """
    import json

    from essay_writer.specialists.grok_bot import CHECKLIST_WALK
    from essay_writer.stage_llm import stage_rules

    for genre in (None, "essay", "report", "diary"):
        assert STAGE1_RULE in stage_rules("1", genre)
    snapshot = json.loads((REPO / "tests" / "snapshots" / "prompts.json").read_text(encoding="utf-8"))
    for key in ("1:none", "1:essay", "1:report", "1:diary"):
        assert STAGE1_RULE in snapshot["stage_rules"][key]
    assert STAGE1_RULE not in CHECKLIST_WALK
    _brief("MOD1004AA", REPORT, SCHEME)
    seq = open_sequence("MOD1004AA")
    basics = _live(
        essay_id=seq,
        stage="1",
        confirmPhase="draft",
        look="\n".join(basics_pass_lines(seq)),
    )
    _refused(basics)
    assert not (work_dir(seq) / "tracking" / "1.md").is_file()


def test_stage5_still_stores_a_look_the_predicate_would_refuse(workspace):
    """essay-u1-c2: stage 5 stores on the draft and starts stage 6, including a guidance-only look.

    There is no second refusal. AUTO_START is unchanged.
    """
    from essay_writer.spine import AUTO_START
    from essay_writer.stage_body import look_is_confirmable

    assert AUTO_START == {"5": "6"}
    seq = open_sequence("MOD1004AA")
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
    basics = "\n".join(basics_pass_lines(seq))
    assert look_is_confirmable(seq, "5", None, basics) is False
    path.write_text(json.dumps(planted), encoding="utf-8")
    stored = _live(essay_id=seq, stage="5", confirmPhase="draft", look=basics)
    assert stored["ok"] is True, stored
    assert stored["stored"] is True
    assert stored.get("refused") != "guidance-only"
    assert load_pointer(seq)["current"] == "6"
    assert "5" in load_pointer(seq)["saved"]
    path.write_text(json.dumps(planted), encoding="utf-8")
    empty = _live(essay_id=seq, stage="5", confirmPhase="draft", look="")
    assert empty["stored"] is True, empty
    assert empty.get("refused") != "guidance-only"
    assert load_pointer(seq)["current"] == "6"


def test_empty_look_omits_the_heading(workspace):
    """essay-u1-e1: an empty look omits the look heading on every stage, including stage 5.

    A non-empty look still gets the heading and the student's sentence under it.
    """
    from essay_writer.stage_note import render_tracking

    for stage in ("1", "2", "5", "10"):
        for status in ("draft", "final"):
            empty = render_tracking(stage, status=status, look="", essay_id="MOD1004AA-1")
            blank = render_tracking(stage, status=status, look="   ", essay_id="MOD1004AA-1")
            assert "## Working look" not in empty
            assert "## Final look" not in empty
            assert "## Working look" not in blank
            assert "## Final look" not in blank
            filled = render_tracking(
                stage,
                status=status,
                look="A student sentence.",
                essay_id="MOD1004AA-1",
            )
            heading = "Final look" if status == "final" else "Working look"
            assert f"## {heading}\n\nA student sentence.\n" in filled


def test_ac2_closed_or_wrong_sequence_does_not_mint_a_card(workspace):
    """AC2. A closed pack and a foreign digest do not mint a card for that pack."""
    closed = open_sequence("RPT5001AA")
    closed_digest = _close(closed)
    opened = open_sequence("RPT5001AA")
    draft = essay_stage(opened, "1", "draft", "The open sequence starts at stage 1.")
    assert draft["ok"] is True, draft
    assert draft["card"]["essay_id"] == opened

    for stage in ("10", "9", "1"):
        for digest in (closed_digest, draft["cardDigest"]):
            body = _live(
                essay_id=closed,
                stage=stage,
                confirmPhase="confirm",
                cardAction="confirm",
                cardDigest=digest,
            )
            assert body.get("stored") is not True
            assert body.get("card") is None
            assert body.get("cardAction") is None
            assert body.get("cardDigest") is None
    assert load_pointer(closed)["closed"] is True
    assert load_pointer(closed)["current"] == "10"

    foreign = _live(
        essay_id=opened,
        stage="1",
        confirmPhase="confirm",
        cardAction="confirm",
        cardDigest=closed_digest,
    )
    assert foreign.get("stored") is not True
    assert load_pointer(opened)["current"] == "1"
    assert "1" not in load_pointer(opened)["saved"]
    card = foreign.get("card") or {}
    assert card.get("essay_id") != closed
    assert foreign.get("cardDigest") != closed_digest
    assert load_pointer(closed)["closed"] is True


def test_ac3_briefing_posts_only_the_open_sequence_card():
    """AC3. INSTRUCTIONS, bot.md, and workflow post only the open sequence's door card."""
    bot = BOT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert OPEN_CARD in STAGE_CONFIRM_EACH
    for text in (INSTRUCTIONS, bot, workflow):
        assert "Essay Bot may only show the Confirm card the door returned" in text
        assert "does not pick the next stage itself" in text
        assert OPEN_CARD in text
        assert "current open sequence" in text
        assert "closed pack" in text
        assert "wrong sequence" in text
        assert "inventing the next stage" in text


def test_ac4_build_covered_shares_the_confirm_next_card_path(monkeypatch):
    """Build covered. Cursor and Grok Build share essay.stage and the atomic confirm write."""
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    assert HANDLERS["essay.stage"] is essay_stage
    assert mount_handler("essay.stage").__wrapped__ is essay_stage
    assert "return _commit_with_next_card(" in inspect.getsource(_save_confirm)
    assert "_commit_with_next_card" not in inspect.getsource(stage_launch)
    assert "_commit_with_next_card" not in inspect.getsource(cursor_stage_launch)
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_CURSOR)
    cursor = stage_host_launch("1")
    monkeypatch.setattr("essay_writer.setup.persisted_shell", lambda: SHELL_GROK_BUILD)
    grok = stage_host_launch("1")
    assert cursor["settings"]["rules"] == grok["settings"]["rules"]
    assert (
        cursor_shell()["entry"]["command"] == front_office()["entry"]["command"] == "essay-writer"
    )
