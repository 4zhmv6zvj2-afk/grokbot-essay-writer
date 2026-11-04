"""Student-facing progress and next lines from door replies.

Operator briefing text must not be spoken aloud. Confirm is named only when
the latest result carries a waiting card and file work is not still running.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer.student_voice import say

_OPERATOR_CONFIRM = re.compile(
    r"(?:do not|don't)\s+(?:show|click|press|open|post|save|invent|warn).{0,120}?\bconfirm\b",
    re.IGNORECASE,
)
_CONFIRM_SPEECH = re.compile(
    r"\bconfirm\b|\bbutton above\b|carddigest|cardaction|not yet to keep",
    re.IGNORECASE,
)
_CARD_NEXT = re.compile(r"^open the confirm card\b", re.IGNORECASE)
_PHANTOM_STAGE = re.compile(
    r"(?:do not|don't)\s+click\b.{0,80}?\bstage\s+([0-9]+[a-z]?)\b",
    re.IGNORECASE,
)
_GATHERING = re.compile(r"\bgathering\b", re.IGNORECASE)

_MID_WAIT: dict[str, str] = {
    "4a": "Wait while the sources are gathered for this step.",
    "4b": "Wait while the notes on each source are written for this step.",
    "5": "Wait while the first draft is written.",
    "6": "Wait while this step finishes in this chat.",
    "7": "Wait while this step finishes in this chat.",
    "8": "Wait while this step finishes in this chat.",
    "9": "Wait while this step finishes in this chat.",
    "10": "Wait while this step finishes in this chat.",
}


def waiting_confirm_card(body: dict[str, Any]) -> bool:
    card = body.get("card")
    if not isinstance(card, dict) or card.get("kind") != "confirm":
        return False
    digest = body.get("cardDigest") or card.get("digest")
    return isinstance(digest, str) and len(digest) == 64


def upload_reconcile_next(check: object) -> str | None:
    """After a PDF lands on disk, name the file and continue the stage work."""
    if not isinstance(check, dict):
        return None
    matched = check.get("matched")
    if not isinstance(matched, list) or not matched:
        return None
    names = [
        str(item.get("name")).strip()
        for item in matched
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item.get("name")
    ]
    if not names:
        return None
    if len(names) == 1:
        return say(f"I saved {names[0]}. I am continuing this step.")
    if len(names) == 2:
        return say(f"I saved {names[0]} and {names[1]}. I am continuing this step.")
    head = ", ".join(names[:-1])
    return say(f"I saved {head}, and {names[-1]}. I am continuing this step.")


def mid_run_wait_next(stage: str, title: str = "") -> str:
    del title
    return say(_MID_WAIT.get(stage, "Wait while this step finishes in this chat."))


def may_speak_confirm(body: dict[str, Any], *, mid_started: bool) -> bool:
    if mid_started:
        return False
    if upload_reconcile_next(body.get("download_check")):
        return False
    return waiting_confirm_card(body)


def _strip_confirm_speech(text: str) -> str:
    if not text:
        return text
    cleaned = _OPERATOR_CONFIRM.sub("", text)
    cleaned = _PHANTOM_STAGE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .")
    return cleaned


def _line_ok_for_stage(line: str, stage: str | None) -> bool:
    if not stage or stage != "4b":
        return True
    lowered = line.casefold()
    if "stage 4a" in lowered and "stage 4b" not in lowered:
        return False
    if _GATHERING.search(line) and "annotat" not in lowered:
        return False
    return True


def sanitize_progress_line(line: str, *, allow_confirm: bool, stage: str | None) -> str:
    if not isinstance(line, str) or not line.strip():
        return ""
    spoken = say(line.strip())
    if not _line_ok_for_stage(spoken, stage):
        return ""
    if allow_confirm:
        return spoken
    if _CONFIRM_SPEECH.search(spoken):
        spoken = _strip_confirm_speech(spoken)
        spoken = _CONFIRM_SPEECH.sub("", spoken)
        spoken = re.sub(r"\s{2,}", " ", spoken).strip(" .")
    return spoken


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
    upload_next = upload_reconcile_next(body.get("download_check"))

    filtered: list[str] = []
    for line in status_lines:
        cleaned = sanitize_progress_line(line, allow_confirm=allow_confirm, stage=stage)
        if cleaned:
            filtered.append(cleaned)
    if filtered:
        body["status"] = filtered
    elif "status" in body:
        body["status"] = []

    if upload_next:
        body["next"] = upload_next
    else:
        nxt = body.get("next")
        if isinstance(nxt, str):
            if mid_started or not allow_confirm:
                if _CARD_NEXT.match(say(nxt)) or _CONFIRM_SPEECH.search(nxt):
                    body["next"] = mid_run_wait_next(stage or "") if stage else say(wait_fallback())
                else:
                    body["next"] = sanitize_progress_line(nxt, allow_confirm=False, stage=stage)
            else:
                body["next"] = say(nxt)

    for key in ("chat", "reason"):
        value = body.get(key)
        if isinstance(value, str):
            if not allow_confirm and _CONFIRM_SPEECH.search(value):
                continue
            body[key] = sanitize_progress_line(value, allow_confirm=allow_confirm, stage=stage)
    from essay_writer.encourage import append_encourage_speech

    return append_encourage_speech(body)


def wait_fallback() -> str:
    return "Wait while this step finishes in this chat."
