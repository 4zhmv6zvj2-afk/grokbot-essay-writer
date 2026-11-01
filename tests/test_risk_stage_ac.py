"""Regressions for stage 7 no-change and a copied stage 2 or 3 lock.

A finished "all fine", "no changes", or "none" opens Confirm and does not
save, even when the waiting card is copied into that same call. On a copied
sequence the parent save is named first. Confirm for that stage waits for
revise or an explicit re-lock, and that choice keeps the parent final look.
"""

from __future__ import annotations

from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.fo_chat_locks import extract_final_look
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import STAGE_ORDER
from essay_writer.stage_track import essay_stage, load_pointer

LOOK = "The task is a short report on the corridor."
MODULE = "RPT5001AA"
DIARY_BRIEF = """
Assignment title: Individual reflective diary
Module title: Practice module
Module code: RPT5001AA
Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.
One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.
Title page: module title, module code, assignment title, registration number, and the word count.
# Marking criteria/feedback form
|| Criterion | 70+ |
| Clarity | exact |
"""
ENTRY_LOCK = (
    "North occasion: the firm chose the corridor route.\n"
    "South occasion: the team delayed the launch.\n"
    "East occasion: the budget was re-cut.\n"
    "West occasion: the client asked for proof."
)
PARENT_SENTENCE = "the firm chose the corridor route"


def _note(seq: str, stage: str) -> str:
    return (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")


def _final(seq: str, stage: str) -> str:
    return extract_final_look(_note(seq, stage))


def _through(seq: str, stop: str) -> None:
    """Confirm every stage before stop. Stage 5 stores on its draft."""
    for stage in STAGE_ORDER:
        if stage == stop:
            return
        draft = essay_stage(seq, stage, "draft", LOOK)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", **picked(draft))
        assert saved["stored"] is True, saved


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(DIARY_BRIEF, encoding="utf-8")


def _look(seq: str, *extra: str) -> str:
    lines = list(basics_pass_lines(seq))
    lines.extend(extra)
    return "\n".join(lines)


def _save_stage(seq: str, stage: str, look: str) -> dict:
    draft = essay_stage(seq, stage, "draft", look)
    assert draft["ok"] is True, draft
    saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
    assert saved["stored"] is True, saved
    return saved


def _parent_with_stage2_lock() -> str:
    _brief()
    draft = essay_sequence_new(MODULE, "draft")
    assert draft["ok"] is True, draft
    parent = essay_sequence_new(MODULE, "confirm")["sequence_id"]
    _save_stage(parent, "1", _look(parent, "Task noted for the diary."))
    _save_stage(parent, "2", _look(parent, ENTRY_LOCK))
    return parent


def _child_ready(parent: str) -> tuple[str, dict]:
    draft = essay_sequence_new(MODULE, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(MODULE, "confirm", parent)
    assert opened["ok"] is True, opened
    child = opened["sequence_id"]
    stage1 = essay_stage(child, "1", "draft", _look(child, "Child opens on stage 1."))
    assert stage1["ok"] is True, stage1
    saved = essay_stage(child, "1", "confirm", **picked(stage1))
    assert saved["stored"] is True, saved
    assert load_pointer(child)["current"] == "2"
    return child, saved


def test_stage7_no_change_with_the_waiting_card_does_not_save(workspace):
    """All fine, no changes, and none do not save. Skip asks the questions again."""
    seq = open_sequence()
    _through(seq, "7")
    asked = essay_stage(seq, "7", "draft", LOOK)
    assert asked["ok"] is True, asked
    assert asked["stored"] is False
    digest = asked["cardDigest"]

    for words in ("all fine", "no changes", "none"):
        reply = essay_stage(
            seq,
            "7",
            "confirm",
            words,
            cardAction="confirm",
            cardDigest=digest,
        )
        assert reply["stored"] is not True, reply
        assert reply["advanced"] is not True
        assert reply.get("confirmPhase") == "draft", reply
        assert reply.get("card", {}).get("kind") == "confirm"
        assert reply.get("card", {}).get("stage") == "7"
        assert load_pointer(seq)["current"] == "7"
        assert "7" not in load_pointer(seq)["saved"]
        assert "Status: final" not in _note(seq, "7")
        digest = reply["cardDigest"]

    skipped = essay_stage(
        seq,
        "7",
        "confirm",
        "skip",
        cardAction="confirm",
        cardDigest=digest,
    )
    assert skipped["ok"] is False, skipped
    assert skipped["stored"] is not True
    assert "Please answer these questions" in skipped["next"]
    assert load_pointer(seq)["current"] == "7"
    assert "7" not in load_pointer(seq)["saved"]
    assert "Status: final" not in _note(seq, "7")


def test_copied_stage2_names_the_parent_look_before_confirm(workspace):
    """Confirm before revise or re-lock does not save, and does not drop the parent look."""
    parent = _parent_with_stage2_lock()
    parent_look = _final(parent, "2")
    assert PARENT_SENTENCE in parent_look
    child, saved1 = _child_ready(parent)
    card = saved1.get("card")
    assert not (isinstance(card, dict) and card.get("stage") == "2")
    assert saved1.get("cardAction") is None
    named = saved1.get("prior_saved_lock")
    assert isinstance(named, dict)
    assert PARENT_SENTENCE in named.get("look", "")

    sneak = essay_stage(
        child,
        "2",
        "confirm",
        cardAction="confirm",
        cardDigest=saved1.get("cardDigest"),
    )
    assert sneak.get("stored") is not True, sneak
    assert "2" not in load_pointer(child)["saved"]
    assert sneak.get("prior_saved_lock", {}).get("look")
    assert PARENT_SENTENCE in sneak["prior_saved_lock"]["look"]

    revised = essay_stage(
        child,
        "2",
        "confirm",
        "A revised scope for this sequence.",
        lockChoice="revise",
        cardAction="confirm",
        cardDigest=saved1.get("cardDigest"),
    )
    assert revised.get("stored") is not True, revised
    assert revised.get("card", {}).get("kind") == "confirm"
    assert revised.get("confirmPhase") == "draft"
    assert PARENT_SENTENCE in _note(child, "2")
    assert "2" not in load_pointer(child)["saved"]
    saved_revise = essay_stage(child, "2", "confirm", **picked(revised))
    assert saved_revise["stored"] is True, saved_revise
    assert PARENT_SENTENCE in _final(child, "2")
    assert "2" in load_pointer(child)["saved"]
    assert load_pointer(child)["current"] == "3"

    child_relock, _saved = _child_ready(parent)
    relocked = essay_stage(
        child_relock,
        "2",
        "draft",
        "Re-lock with one added line.",
        lockChoice="relock",
    )
    assert relocked.get("stored") is not True, relocked
    assert relocked.get("card", {}).get("kind") == "confirm"
    assert PARENT_SENTENCE in _note(child_relock, "2")
    assert "2" not in load_pointer(child_relock)["saved"]

    child_keep, _saved = _child_ready(parent)
    kept = essay_stage(child_keep, "2", "draft", lockChoice="keep")
    assert kept["stored"] is True, kept
    assert kept.get("inherited_keep") is True
    assert "card" not in kept
    assert kept.get("cardAction") is None
    assert kept.get("cardDigest") is None
    assert load_pointer(child_keep)["current"] == "3"
    assert _final(child_keep, "2") == parent_look
