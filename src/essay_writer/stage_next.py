"""The one writer for the stage "what happens next" sentence.

Every essay.stage reply stores that sentence here. The stage reply, hold,
landing, and finish paths do not assign it. Dig, shelf, setup, intake,
review, and projects still write their own next sentence. Cleaning the
words a person reads does not choose which stage sentence wins.
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
_STAGE7_ASK = re.compile(r"\bplease answer these questions\b", re.IGNORECASE)

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

# Spoken when the final Word stays in this chat because the Mac folder is absent.
STAGE10_UNMOUNTED = (
    "The Mac folder is not on this computer. "
    "The final Word stays in this chat and on this sequence. "
    "This tool does not submit."
)
_KEEP_COPY = "Keep a copy. This tool does not submit."
_CLOSED = "The last stage is already saved. This tool does not submit."


def write_stage_next(body: dict[str, Any], sentence: str) -> dict[str, Any]:
    """Store the one stage next sentence. This is the only such store."""
    body["next"] = sentence
    return body


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


def confirm_in_speech(text: str) -> bool:
    """True when a progress line still names the save card or its fields."""
    return bool(_CONFIRM_SPEECH.search(text))


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


def wait_fallback() -> str:
    return "Wait while this step finishes in this chat."


def quiet_stage_line(stage: str, *, armed: bool, blocked: bool, place: str) -> str | None:
    """The quiet line after an armed late stage. None leaves the sentence alone."""
    if not armed:
        return None
    if blocked:
        return "Read the independent review note in this chat before the final Word file."
    if stage == "10":
        return place
    return None


def _questions(body: dict[str, Any]) -> list[str]:
    raw = body.get("questions")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _title(body: dict[str, Any]) -> str:
    title = body.get("stage_title")
    return title if isinstance(title, str) else ""


def write_draft_stage_next(body: dict[str, Any], *, stage: str, essay_id: str) -> dict[str, Any]:
    """The draft sentence: upload line, stage 7 ask, mid-run wait, or the card."""
    from essay_writer.specialists.grok_bot import card_next, stage7_lead
    from essay_writer.stage7 import stage7_edited

    upload_next = upload_reconcile_next(body.get("download_check"))
    stage7_ask = stage == "7" and not stage7_edited(essay_id)
    title = _title(body)
    if upload_next:
        sentence = upload_next
    elif stage7_ask:
        sentence = stage7_lead(_questions(body), title)
    elif body.get("mid_started") is True:
        sentence = mid_run_wait_next(stage, title)
    else:
        sentence = card_next(stage, title)
    return write_stage_next(body, sentence)


def write_following_stage_next(
    body: dict[str, Any], following: str | None, title: str
) -> dict[str, Any]:
    """The sentence after a save. The last stage keeps a copy and does not submit."""
    if following:
        from essay_writer.specialists.grok_bot import saved_next

        return write_stage_next(body, saved_next(following, title))
    return write_stage_next(body, _KEEP_COPY)


def write_revisit_stage_next(
    body: dict[str, Any], *, stage: str, genre: str | None
) -> dict[str, Any]:
    """After a saved revisit, open the plan or the first draft."""
    from essay_writer.specialists.grok_bot import revisit_plan_next, saved_next
    from essay_writer.stage_llm import stage_title

    if stage == "2":
        return write_stage_next(body, revisit_plan_next(stage_title("3", genre)))
    return write_stage_next(body, saved_next("5", stage_title("5", genre)))


def write_replay_card_next(body: dict[str, Any], stage: str, title: str) -> dict[str, Any]:
    """A replayed card names that card."""
    from essay_writer.specialists.grok_bot import card_next

    return write_stage_next(body, card_next(stage, title))


def write_critical_reviews_next(body: dict[str, Any]) -> dict[str, Any]:
    """Name the saved critical-review file, then the following sentence."""
    from essay_writer.specialists.grok_bot import critical_reviews_delivery_next

    current = body.get("next")
    text = current if isinstance(current, str) else ""
    body.pop("delivery_speech", None)
    spoken = critical_reviews_delivery_next(text)
    delivery = body.get("delivery")
    if isinstance(delivery, dict):
        note = delivery.get("student_note")
        if isinstance(note, str) and note.strip() and note.strip() not in spoken:
            spoken = f"{spoken} {note.strip()}"
    return write_stage_next(body, spoken)


def write_closed_stage_next(body: dict[str, Any]) -> dict[str, Any]:
    """An already saved last stage names that fact."""
    reason = body.get("reason")
    sentence = reason if isinstance(reason, str) and reason else _CLOSED
    return write_stage_next(body, sentence)


def write_missing_confirm_next(
    body: dict[str, Any], stage: str, title: str, *, say_it: bool = False
) -> dict[str, Any]:
    """A missing card still names the card, with the typed fallback."""
    from essay_writer.specialists.grok_bot import missing_confirm_next

    sentence = missing_confirm_next(stage, title)
    return write_stage_next(body, say(sentence) if say_it else sentence)


def write_blocked_card_next(
    body: dict[str, Any], opened_next: object, *, stage: str, title: str
) -> dict[str, Any]:
    """Use the open card's sentence, or name the missing card."""
    if isinstance(opened_next, str) and opened_next.strip():
        return write_stage_next(body, opened_next)
    return write_missing_confirm_next(body, stage, title)


def write_stage7_skip_next(
    body: dict[str, Any], *, reason: str, questions: list[str], title: str
) -> dict[str, Any]:
    """A skipped stage 7 ask is said again. It does not save."""
    from essay_writer.specialists.grok_bot import stage7_lead

    lead = stage7_lead(questions, title)
    return write_stage_next(body, say(f"{reason} {lead}"))


def write_reoffer_next(
    body: dict[str, Any],
    *,
    lead: str | None,
    replayed: bool,
    stage: str,
    title: str,
) -> dict[str, Any]:
    """A confirm that does not save still says what to do."""
    if isinstance(lead, str) and lead.strip():
        return write_stage_next(body, say(lead.strip()))
    if not replayed:
        return write_missing_confirm_next(body, stage, title, say_it=True)
    return body


def write_reason_next(body: dict[str, Any]) -> dict[str, Any]:
    """Say the reason already stored on a stopped reply."""
    reason = body.get("reason")
    text = reason if isinstance(reason, str) else ""
    return write_stage_next(body, say(text))


def append_conclusion_next(body: dict[str, Any], line: str) -> dict[str, Any]:
    """Add the written-conclusion sentence after the stage sentence."""
    current = body.get("next")
    if isinstance(current, str) and current.strip():
        if line in current:
            return body
        return write_stage_next(body, f"{current.rstrip()} {line}")
    return write_stage_next(body, line)


def apply_finished_stage_next(
    body: dict[str, Any],
    essay_id: str,
    stage: str,
    *,
    armed: bool,
    place: str,
) -> dict[str, Any]:
    """The finish-path sentence. The caller has already stored the other fields."""
    if body.get("stored") and armed and stage in {"7", "8", "9"}:
        run = body.get("next_run")
        blocked = bool(run.get("blocked")) if isinstance(run, dict) else False
        line = quiet_stage_line(stage, armed=True, blocked=blocked, place=place)
        if line:
            write_stage_next(body, say(line))
    elif armed and stage in {"8", "9"} and not body.get("stored"):
        line = quiet_stage_line(stage, armed=True, blocked=False, place=place)
        if line:
            write_stage_next(body, say(line))
    if stage == "10" and body.get("stored"):
        final = body.get("final_word")
        if body.get("ok") is False and body.get("refused") == "word":
            write_reason_next(body)
        elif isinstance(final, dict) and final.get("reason") == "mac-not-mounted":
            write_stage_next(body, say(STAGE10_UNMOUNTED))
        elif isinstance(final, dict):
            findings = final.get("findings_place") or ""
            note = f" The review note is {findings}." if findings else ""
            write_stage_next(
                body,
                say(f"Open {final['place']} and keep a copy.{note} This tool does not submit."),
            )
    elif stage == "10" and armed and not body.get("stored"):
        from essay_writer.spine import final_review

        blocked_text, _verdict = final_review(essay_id)
        if blocked_text:
            write_stage_next(body, say(blocked_text))
    if stage == "9" and body.get("stored"):
        from essay_writer.specialists.grok_bot import STAGE9_OWN_WORDS

        current = body.get("next")
        text = current if isinstance(current, str) else ""
        if STAGE9_OWN_WORDS not in text:
            write_stage_next(body, say(f"{STAGE9_OWN_WORDS} {text}".strip()))
    return body


def rewritten_stage_next(body: dict[str, Any], *, mid_started: bool) -> str | None:
    """The essay.stage rewrite. None means this reply has no next sentence to store.

    A returned string, including an empty one, replaces the sentence. The upload
    line, the stage 7 ask, the mid-run wait, and Confirm wording stripped during
    a mid-run are decided here.
    """
    stage = body.get("stage") if isinstance(body.get("stage"), str) else None
    allow_confirm = may_speak_confirm(body, mid_started=mid_started)
    upload_next = upload_reconcile_next(body.get("download_check"))
    if upload_next:
        return upload_next
    nxt = body.get("next")
    if not isinstance(nxt, str):
        return None
    stage7_ask = stage == "7" and waiting_confirm_card(body) and _STAGE7_ASK.search(say(nxt))
    if stage7_ask:
        return say(nxt)
    if mid_started or not allow_confirm:
        if _CARD_NEXT.match(say(nxt)) or _CONFIRM_SPEECH.search(nxt):
            return mid_run_wait_next(stage or "") if stage else say(wait_fallback())
        return sanitize_progress_line(nxt, allow_confirm=False, stage=stage)
    return say(nxt)


def rewrite_essay_stage_next(body: dict[str, Any], *, mid_started: bool) -> dict[str, Any]:
    """Store the rewritten essay.stage sentence. A refusal is left as it was."""
    if body.get("ok") is False:
        return body
    sentence = rewritten_stage_next(body, mid_started=mid_started)
    if sentence is None:
        return body
    return write_stage_next(body, sentence)
