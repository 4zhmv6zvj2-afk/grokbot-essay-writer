"""Stage 7 ask, then edit. The delta lists changed claim and limit sentences.

Word saves at stage 7 and stage 9 rewrite first-draft.md in the sequence
folder in that same step. That note is not a second student file.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from essay_writer.paths import work_dir

_QUESTIONS = (
    "Does the structure still match the brief?",
    "Does the argument still answer the question?",
    "Which sentences are unclear?",
    "Which claims should be checked for currency?",
    "Which lines are too vague to defend from the sources?",
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_GLOSSARY = re.compile(r"\b(means|stands for|short for|that is)\b", re.IGNORECASE)
_LOCATOR = re.compile(r"\b(available at|doi:|pp?\.\s*\d+)\b", re.IGNORECASE)
_CLAIM = re.compile(r"\b(because|shows|finds|limit|claim)\b", re.IGNORECASE)


def _record_path(essay_id: str):
    return work_dir(essay_id) / "tracking" / "stage7.json"


def load_stage7(essay_id: str) -> dict[str, Any]:
    path = _record_path(essay_id)
    blank: dict[str, Any] = {
        "asked": False,
        "edited": False,
        "questions": [],
        "answers": "",
        "delta": [],
        "comments": "",
    }
    if not path.is_file():
        return blank
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return blank
    if not isinstance(data, dict):
        return blank
    blank["asked"] = data.get("asked") is True
    blank["edited"] = data.get("edited") is True
    questions = data.get("questions")
    if isinstance(questions, list):
        blank["questions"] = [item for item in questions if isinstance(item, str)]
    answers = data.get("answers")
    if isinstance(answers, str):
        blank["answers"] = answers
    delta = data.get("delta")
    if isinstance(delta, list):
        blank["delta"] = [item for item in delta if isinstance(item, str)]
    comments = data.get("comments")
    if isinstance(comments, str):
        blank["comments"] = comments
    return blank


def save_stage7(essay_id: str, record: dict[str, Any]) -> None:
    path = _record_path(essay_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def stage7_edited(essay_id: str) -> bool:
    return load_stage7(essay_id).get("edited") is True


_NO_CHANGE_PARTS = frozenset(
    {
        "all fine",
        "all good",
        "none",
        "no change",
        "no changes",
        "nothing",
        "nothing to change",
    }
)


def answers_mean_no_change(answers: str | None) -> bool:
    """True when the reply says the draft should stay as it is."""
    if not isinstance(answers, str):
        return False
    folded = re.sub(r"\s+", " ", answers).strip().casefold().strip(" .!")
    if not folded:
        return False
    parts = [
        part.strip(" .!")
        for part in re.split(r"\s*/\s*|\s*,\s*|\s+and\s+", folded)
        if part.strip(" .!")
    ]
    return bool(parts) and all(part in _NO_CHANGE_PARTS for part in parts)


_SKIP_PROBES = frozenset(
    {
        "skip",
        "skipped",
        "skip it",
        "skip this",
        "skip them",
        "skip the questions",
        "skip questions",
        "skip question",
    }
)


def answers_mean_skip(answers: str | None) -> bool:
    """True when the reply is only a request to skip the stage 7 questions."""
    if not isinstance(answers, str):
        return False
    folded = re.sub(r"\s+", " ", answers).strip().casefold().strip(" .!?")
    if not folded or len(folded) > 48:
        return False
    if folded in _SKIP_PROBES:
        return True
    return folded.startswith("skip ")


def note_questions(essay_id: str) -> dict[str, Any]:
    """Grok Bot has read the stage 6 draft and asked. No edit yet."""
    record = load_stage7(essay_id)
    record["asked"] = True
    record["questions"] = questions_for(essay_id)
    record["edited"] = False
    save_stage7(essay_id, record)
    return {
        "questions": record["questions"],
        "draft_read": bool(draft_text(essay_id)),
        "file_work": "chat",
        "delta": [],
        "chain_started": False,
    }


ASK_FIRST = "Ask the questions in this chat before editing from the answers."
NEED_ANSWERS = "The edits need the answers to those questions."
NEED_EDIT = (
    "Send the edited sentences from those answers, or say there are no changes. "
    "Do not invent the sentences."
)
NEED_CHECK = (
    "The light check needs currency, and academic tone or clarity, before the edit is kept."
)


def _stage7_block(reason: str) -> dict[str, Any]:
    """A missed stage 7 step names the next ask. It does not sit silent."""
    return {"ok": False, "reason": reason, "next": reason}


def note_edits(
    essay_id: str,
    *,
    answers: str | None,
    edited: str | None,
    web_check: object,
) -> dict[str, Any]:
    """Edits from the answers, after the questions. The door does not invent sentences."""
    record = load_stage7(essay_id)
    if not record.get("asked"):
        return _stage7_block(ASK_FIRST)
    if not isinstance(answers, str) or not answers.strip():
        return _stage7_block(NEED_ANSWERS)
    no_change = answers_mean_no_change(answers)
    kept = edited if isinstance(edited, str) else ""
    if not kept.strip():
        if no_change:
            # Nothing new was written. Keep the stage 6 draft that is already there.
            kept = draft_text(essay_id)
        else:
            return _stage7_block(NEED_EDIT)
    if web_check is None and no_change:
        # "No changes" is the light check: currency and tone already stand.
        web_check = {"currency": True, "tone": True, "clarity": True}
    if not web_check_ready(web_check):
        return _stage7_block(NEED_CHECK)
    delta = claim_delta(draft_text(essay_id), kept)
    record["edited"] = True
    record["answers"] = answers.strip()
    record["delta"] = delta
    record["comments"] = comment_text(
        {
            "questions": record.get("questions") or questions_for(essay_id),
            "answers": answers.strip(),
            "delta": delta,
        }
    )
    save_stage7(essay_id, record)
    return {
        "ok": True,
        "answers": answers.strip(),
        "edited": kept,
        "webCheck": web_check,
        "questions": record.get("questions") or [],
        "draft_read": bool(draft_text(essay_id)),
        "file_work": "chat",
        "delta": delta,
        "chain_started": False,
    }


def draft_text(essay_id: str) -> str:
    """Text of the stage 6 Word file, when that file is already saved."""
    path = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    if not path.is_file():
        return ""
    from docx import Document

    document = Document(str(path))
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(lines)


def questions_for(essay_id: str) -> list[str]:
    return list(_QUESTIONS)


def web_check_ready(value: object) -> bool:
    """Currency, plus academic tone or clarity. No new look-up."""
    if not isinstance(value, dict):
        return False
    if value.get("currency") is not True:
        return False
    return value.get("tone") is True or value.get("clarity") is True


def _sentences(text: str) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    return [part.strip() for part in _SENTENCE_END.split(text.strip()) if part.strip()]


def _claim_or_limit(sentence: str) -> bool:
    if _GLOSSARY.search(sentence):
        return False
    if _LOCATOR.search(sentence) and not _CLAIM.search(sentence):
        return False
    return True


def claim_delta(before: str, after: str) -> list[str]:
    """Every claim or limit sentence that changed. Not only glossary or locator lines."""
    before_claims = [sentence for sentence in _sentences(before) if _claim_or_limit(sentence)]
    after_claims = [sentence for sentence in _sentences(after) if _claim_or_limit(sentence)]
    before_set = set(before_claims)
    changed: list[str] = []
    for sentence in before_claims:
        if sentence not in after_claims and sentence not in changed:
            changed.append(sentence)
    for sentence in after_claims:
        if sentence not in before_set and sentence not in changed:
            changed.append(sentence)
    return changed


def comment_text(record: dict[str, Any]) -> str:
    lines: list[str] = []
    questions = record.get("questions") or []
    if questions:
        lines.append("Questions")
        lines.extend(f"- {item}" for item in questions if isinstance(item, str))
    answers = record.get("answers")
    if isinstance(answers, str) and answers.strip():
        lines.append("Answers")
        lines.append(answers.strip())
    delta = record.get("delta") or []
    if delta:
        lines.append("Sentences whose claim or limit changed")
        lines.extend(f"- {item}" for item in delta if isinstance(item, str))
    return "\n".join(lines)


def rewrite_first_draft_md(essay_id: str, docx_path) -> None:
    """Rewrite the sequence note from the saved Word file. Same step. Not chat."""
    from docx import Document

    document = Document(str(docx_path))
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    target = work_dir(essay_id) / "first-draft.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".md.tmp")
    temporary.write_text("\n\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(temporary, target)
