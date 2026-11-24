"""Typed boundary for the high-risk model payloads.

A payload is parsed into a dataclass before a door uses it. A bad payload
is a ``ContractRefusal`` with student-facing copy. Prose quality is not
scored. Lower-risk payloads stay documented as safe unvalidated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MISSING_QUESTION = "Name the essay question. An empty question is not searched."
VERDICT_SHAPE = "The verdict is PASS or FAIL."

_OPERATOR = re.compile(r"site:|filetype:|(?<![A-Za-z])(?:AND|OR|NOT)(?![A-Za-z])")
_QUESTION_FIELDS = frozenset({"question"})
_SMALLER_FIELDS = frozenset({"questions", "question"})
_DRAFT_FIELDS = frozenset({"text", "readable"})
_STRIP_FIELDS = frozenset({"text", "removed", "subject_gap"})
_VERDICT_FIELDS = frozenset({"verdict", "draft_text"})
_FINDINGS_FIELDS = frozenset({"text"})

Code = Literal["missing", "malformed", "extra", "contradictory"]


@dataclass(frozen=True)
class ContractRefusal:
    """One refusal vocabulary. ``reason`` is the sentence the student reads."""

    code: Code
    reason: str


def _refuse(code: Code, part: str) -> ContractRefusal:
    if code == "missing":
        reason = f"The {part} is missing. Nothing was saved."
    elif code == "malformed":
        reason = f"The {part} is not in the shape this step expects. Nothing was saved."
    elif code == "extra":
        reason = f"The {part} has a field this step does not use. Nothing was saved."
    else:
        reason = f"The {part} disagrees with itself. Nothing was saved."
    return ContractRefusal(code, reason)


@dataclass(frozen=True)
class ConfirmedQuestion:
    text: str


@dataclass(frozen=True)
class SmallerQuestions:
    questions: tuple[str, ...]


@dataclass(frozen=True)
class StageDraft:
    text: str


@dataclass(frozen=True)
class StripReport:
    """Cleaned sentence, the spans removed, and whether the sentence still reads.

    This is not a ``str``. Callers that store or join the sentence use
    ``text``. ``subject_gap`` is true when a removed narrative cite was the
    subject or the name.
    """

    text: str
    removed: tuple[str, ...] = ()
    subject_gap: bool = False


@dataclass(frozen=True)
class ReviewVerdict:
    verdict: Literal["PASS", "FAIL"]
    draft_text: str | None = None


@dataclass(frozen=True)
class FindingsNote:
    text: str


@dataclass(frozen=True)
class WordTitle:
    text: str


def prose_of(value: object) -> str:
    """The sentence a ``StripReport`` carries, or the string itself."""
    if isinstance(value, StripReport):
        return value.text
    return value if isinstance(value, str) else ""


def parse_confirmed_question(
    value: object,
    *,
    required: bool = True,
) -> ConfirmedQuestion | ContractRefusal:
    """A confirmed question is one ordinary-language string."""
    if isinstance(value, dict):
        extra = set(value) - _QUESTION_FIELDS
        if extra:
            return _refuse("extra", "confirmed question")
        if "question" not in value:
            return _refuse("missing", "confirmed question")
        value = value.get("question")
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            return ContractRefusal("missing", MISSING_QUESTION)
        return ConfirmedQuestion("")
    if not isinstance(value, str):
        return _refuse("malformed", "confirmed question")
    text = value.strip()
    if _OPERATOR.search(text):
        return _refuse("contradictory", "confirmed question")
    return ConfirmedQuestion(text)


def parse_smaller_questions(
    value: object,
    confirmed: str = "",
) -> SmallerQuestions | ContractRefusal:
    """The dig list is strings. A bad shape is not passed to the gather."""
    if value is None:
        return SmallerQuestions(())
    if isinstance(value, dict):
        extra = set(value) - _SMALLER_FIELDS
        if extra:
            return _refuse("extra", "smaller questions")
        stated = value.get("question")
        if isinstance(stated, str) and confirmed.strip() and stated.strip() != confirmed.strip():
            return _refuse("contradictory", "smaller questions")
        if "questions" not in value:
            return _refuse("missing", "smaller questions")
        value = value.get("questions")
    if not isinstance(value, list):
        return _refuse("malformed", "smaller questions")
    if any(not isinstance(item, str) for item in value):
        return _refuse("malformed", "smaller questions")
    return SmallerQuestions(tuple(value))


def parse_stage_draft(value: object) -> StageDraft | ContractRefusal:
    """The stage-5 look is a string. Prose quality is not scored."""
    if isinstance(value, dict):
        extra = set(value) - _DRAFT_FIELDS
        if extra:
            return _refuse("extra", "stage-5 draft")
        if "text" not in value:
            return _refuse("missing", "stage-5 draft")
        if (
            value.get("readable") is False
            and isinstance(value.get("text"), str)
            and value["text"].strip()
        ):
            return _refuse("contradictory", "stage-5 draft")
        value = value.get("text")
    if value is None or (isinstance(value, str) and not value.strip()):
        return _refuse("missing", "stage-5 draft")
    if not isinstance(value, str):
        return _refuse("malformed", "stage-5 draft")
    return StageDraft(value)


def parse_strip_report(value: object) -> StripReport | ContractRefusal:
    """A strip report names the spans it removed, and those spans are gone."""
    if isinstance(value, StripReport):
        return _strip_disagreement(value)
    if not isinstance(value, dict):
        return _refuse("malformed", "strip report")
    extra = set(value) - _STRIP_FIELDS
    if extra:
        return _refuse("extra", "strip report")
    if "text" not in value:
        return _refuse("missing", "strip report")
    text = value.get("text")
    if not isinstance(text, str):
        return _refuse("malformed", "strip report")
    removed = value.get("removed", ())
    if isinstance(removed, list):
        if any(not isinstance(item, str) for item in removed):
            return _refuse("malformed", "strip report")
        spans = tuple(removed)
    elif removed == ():
        spans = ()
    else:
        return _refuse("malformed", "strip report")
    gap = value.get("subject_gap", False)
    if not isinstance(gap, bool):
        return _refuse("malformed", "strip report")
    return _strip_disagreement(StripReport(text, spans, gap))


def _strip_disagreement(report: StripReport) -> StripReport | ContractRefusal:
    for span in report.removed:
        if span and span in report.text:
            return _refuse("contradictory", "strip report")
    return report


def parse_verdict(value: object) -> ReviewVerdict | ContractRefusal:
    """The review verdict is PASS or FAIL."""
    if isinstance(value, dict):
        extra = set(value) - _VERDICT_FIELDS
        if extra:
            return _refuse("extra", "review verdict")
        if "verdict" not in value:
            return _refuse("missing", "review verdict")
        draft = value.get("draft_text")
        verdict = value.get("verdict")
        if draft is not None and verdict == "PASS" and not isinstance(draft, str):
            return _refuse("contradictory", "review verdict")
        if draft is not None and verdict == "FAIL" and isinstance(draft, str) and draft.strip():
            return _refuse("contradictory", "review verdict")
        value = verdict
    if value is None or (isinstance(value, str) and not value.strip()):
        return ContractRefusal("missing", VERDICT_SHAPE)
    if value == "PASS":
        return ReviewVerdict("PASS")
    if value == "FAIL":
        return ReviewVerdict("FAIL")
    return ContractRefusal("malformed", VERDICT_SHAPE)


def parse_draft_tie(saved: object, tied: object) -> ReviewVerdict | ContractRefusal:
    """The stored stage-6 tie is the saved first-draft look, character for character."""
    if tied is None:
        return _refuse("missing", "draft tie")
    if not isinstance(tied, str) or not isinstance(saved, str):
        return _refuse("malformed", "draft tie")
    if saved != tied:
        return _refuse("contradictory", "draft tie")
    return ReviewVerdict("PASS", tied)


def parse_findings(value: object, essay_id: str | None = None) -> FindingsNote | ContractRefusal:
    """The findings note has the review shape. The sentences inside are not scored."""
    if isinstance(value, dict):
        extra = set(value) - _FINDINGS_FIELDS
        if extra:
            return _refuse("extra", "findings note")
        if "text" not in value:
            return _refuse("missing", "findings note")
        value = value.get("text")
    if value is None or (isinstance(value, str) and not value.strip()):
        return _refuse("missing", "findings note")
    if not isinstance(value, str):
        return _refuse("malformed", "findings note")
    from essay_writer.specialists.eqr import findings_note_clears

    if not findings_note_clears(value, essay_id):
        return _refuse("contradictory", "findings note")
    return FindingsNote(value)


def parse_word_title(
    value: object,
    opening: str = "",
    *,
    limit: int = 255,
) -> WordTitle | ContractRefusal:
    """A Word document title is a short string, and it is not the opening paragraph."""
    if isinstance(value, dict):
        extra = set(value) - {"title"}
        if extra:
            return _refuse("extra", "Word title")
        if "title" not in value:
            return _refuse("missing", "Word title")
        value = value.get("title")
    if value is None or (isinstance(value, str) and not value.strip()):
        return _refuse("missing", "Word title")
    if not isinstance(value, str):
        return _refuse("malformed", "Word title")
    text = value.strip()
    if len(text) > limit:
        return _refuse("malformed", "Word title")
    if opening.strip() and text == opening.strip():
        return _refuse("contradictory", "Word title")
    return WordTitle(text)
