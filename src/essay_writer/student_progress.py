"""Student-facing progress lines from door replies.

The stage "what happens next" sentence is stored by stage_next. This module
cleans the progress lines a person reads. For every door other than
essay.stage it still stores that door's own next sentence, using the same
rewrite it used before the stage sentence moved.
"""

from __future__ import annotations

from typing import Any

from essay_writer.stage_next import (
    confirm_in_speech,
    may_speak_confirm,
    mid_run_wait_next,
    rewrite_essay_stage_next,
    rewritten_stage_next,
    sanitize_progress_line,
    upload_reconcile_next,
    wait_fallback,
)

__all__ = [
    "may_speak_confirm",
    "mid_run_wait_next",
    "rewrite_essay_stage_next",
    "sanitize_progress_line",
    "shape_student_reply",
    "upload_reconcile_next",
    "wait_fallback",
]


def _store_other_door_next(body: dict[str, Any], *, mid_started: bool) -> None:
    """Doors other than essay.stage still store their own next sentence here."""
    sentence = rewritten_stage_next(body, mid_started=mid_started)
    if sentence is None:
        return
    body["next"] = sentence


def shape_student_reply(
    body: dict[str, Any],
    *,
    tool: str,
    mid_started: bool,
    status_lines: list[str],
) -> dict[str, object]:
    """Drop operator Confirm rules from speech. Keep the card on the reply."""
    if body.get("ok") is False:
        return body
    stage = body.get("stage") if isinstance(body.get("stage"), str) else None
    if tool == "essay.stage" and not stage:
        stage = None
    allow_confirm = may_speak_confirm(body, mid_started=mid_started)

    filtered: list[str] = []
    for line in status_lines:
        cleaned = sanitize_progress_line(line, allow_confirm=allow_confirm, stage=stage)
        if cleaned:
            filtered.append(cleaned)
    if filtered:
        body["status"] = filtered
    elif "status" in body:
        body["status"] = []

    if tool == "essay.stage":
        rewrite_essay_stage_next(body, mid_started=mid_started)
    else:
        _store_other_door_next(body, mid_started=mid_started)

    for key in ("chat", "reason"):
        value = body.get(key)
        if isinstance(value, str):
            if not allow_confirm and confirm_in_speech(value):
                continue
            body[key] = sanitize_progress_line(value, allow_confirm=allow_confirm, stage=stage)
    from essay_writer.encourage import append_encourage_speech

    return append_encourage_speech(body)
