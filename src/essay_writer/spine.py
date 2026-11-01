"""Stage spine.

A stage calls one specialist. This module does not score the constitution
and does not keep a second copy of a specialist door. A successful stage 5
starts stage 6 with no card. Other stage saves use the Grok Bot card.
Stages 7, 8, and 9 keep their own saves.
"""

from __future__ import annotations

from essay_writer.assignment_gate import north_star_gate

ROLE = "spine"

# Stage 5 stores on the draft and starts stage 6. Stages 8, 9, and 10 keep
# their own cards. No other stage is stored without its own Confirm.
AUTO_START = {"5": "6"}


def advances_without_confirm(stage: str) -> str | None:
    """The next stage when this one stores on the draft. None keeps the card."""
    return AUTO_START.get(stage)


def stage_uses_confirm_card(stage: str) -> bool:
    return stage not in AUTO_START


def stage_confirm_card(
    essay_id: str,
    stage: str,
    digest: str,
    summary: str,
    *,
    stage_title: str,
) -> dict[str, object]:
    from essay_writer.specialists.grok_bot import confirm_card

    return confirm_card(essay_id, stage, digest, summary, stage_title=stage_title)


def accept_stage_card(card_action: str | None):
    from essay_writer.specialists.grok_bot import accept_card_pick

    return accept_card_pick(card_action)


def gate_save(essay_id: str, text: str):
    """The Layer 2 gate, through Grok Bot. Not a second constitution check."""
    from essay_writer.specialists.grok_bot import confirm_gate

    return confirm_gate(essay_id, text)


def north_star(essay_id: str, text: str):
    """The same assignment check, recorded for stage 5. Not a second constitution."""

    return north_star_gate(essay_id, text)


def save_line(stage: str, genre: str | None, *, revisit: bool = False) -> str:
    from essay_writer.specialists.grok_bot import confirm_line

    return confirm_line(stage, genre, revisit=revisit)


def stage_bibliography(essay_id: str):
    from essay_writer.specialists.researcher import deliver_bibliography

    return deliver_bibliography(essay_id)


def stage_critical_reviews(essay_id: str):
    from essay_writer.specialists.researcher import deliver_critical_reviews

    return deliver_critical_reviews(essay_id)


def stage_reconcile(essay_id: str):
    from essay_writer.specialists.researcher import (
        real_4a_bibliography,
        reconcile_before_4b,
    )

    return real_4a_bibliography(essay_id), reconcile_before_4b(essay_id)


def final_review(essay_id: str) -> tuple[str | None, str]:
    """One read of the stage 9 review. The message is empty when it passed.

    The pass is the submit-file unlock. This read does not mark again.
    """
    from essay_writer.specialists.eqr import submit_pass_unlocked

    report = submit_pass_unlocked(essay_id)
    if report.get("unlocked") is True:
        return None, "PASS"
    if report.get("reason") == "fail":
        return (
            "The independent review did not pass. That block is shown before the final Word.",
            "FAIL",
        )
    if report.get("reason") == "citations" or _submit_file_has_no_citations(essay_id):
        return (
            "The Word file has no citations. That block is shown before the final Word.",
            "citations",
        )
    return (
        "The independent review is still open. That block is shown before the final Word.",
        "missing",
    )


def _submit_file_has_no_citations(essay_id: str) -> bool:
    from essay_writer.specialists.eqr import read_submit_word

    opened = read_submit_word(essay_id)
    return opened.get("opened") is True and opened.get("citations") is not True


def __getattr__(name: str):
    if name == "essay_stage":
        from essay_writer.stage_track import essay_stage

        return essay_stage
    raise AttributeError(name)
