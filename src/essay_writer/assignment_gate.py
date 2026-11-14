"""Conditional constitution. Shared by Grok Bot, Writer, and EQR.

No mark scheme and no brief: daily-use essay or report. The gate does not block
and does not invent a mark scheme, a question, a format, or a band.

A brief with no mark scheme: format and question come from the brief. A missing
mark scheme does not block, and no band is invented.

A mark scheme: mark scheme, prescribed format, and assignment ask come first.
The aim is the highest band on that scheme, not merely a pass. On a conflict
with the brief, the mark scheme wins.

This is not mechanical gate 1. A missing brief is not a failure.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer.diary import extract_marking_table
from essay_writer.paths import essay_dir, module_code
from essay_writer.textutil import (
    content_words,
    genre_from_brief_text,
    module_brief_text,
    unmarked_labels,
)

_SCHEME_NAMES = (
    "mark-scheme.md",
    "mark-scheme.txt",
    "mark-scheme.docx",
    "marking-guideline.md",
    "marking-guideline.txt",
    "marking-guideline.docx",
    "rubric.md",
    "rubric.txt",
    "rubric.docx",
    "marking-table.md",
    "marking-table.txt",
)
_SCHEME_HEAD = re.compile(r"(?im)^#{0,3}\s*(mark scheme|marking guidelines?|rubric)\s*:?\s*(.*)$")
_WEIGHTS_HEAD = re.compile(r"(?im)^#{0,3}\s*(section\s+weights?)\s*:?\s*(.*)$")
_FORMAT_LINE = re.compile(r"(?im)^\s*format\s*:\s*(essay|report)\b")
# Same question, whichever field the brief uses. Question wins over Title.
_QUESTION_FIELDS = (
    re.compile(r"(?im)^\s*assignment\s+question\s*:\s*(.+)$"),
    re.compile(r"(?im)^\s*question\s*:\s*(.+)$"),
    re.compile(r"(?im)^\s*task\s*:\s*(.+)$"),
    re.compile(r"(?im)^\s*assignment\s+ask\s*:\s*(.+)$"),
    re.compile(r"(?im)^\s*ask\s*:\s*(.+)$"),
    re.compile(r"(?im)^\s*title\s*:\s*(.+)$"),
)
_QUESTION_LABELS = (
    "assignment question",
    "question",
    "task",
    "assignment ask",
    "ask",
    "title",
)
_FIELD_LINE = re.compile(r"(?i)^[A-Za-z][A-Za-z ]{0,40}:\s*\S")
_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "into",
        "your",
        "their",
        "have",
        "been",
        "will",
        "when",
        "what",
        "which",
        "where",
        "should",
        "include",
        "about",
        "only",
        "than",
        "then",
        "them",
        "they",
        "also",
        "such",
        "each",
        "over",
        "under",
        "after",
        "before",
    }
)
_RANGE = re.compile(r"(\d{1,3})\s*[-–]\s*(\d{1,3})")
_NUMERIC_BAND = re.compile(r"(?<!\d)(?P<label>\d{1,3}\s*\+|\d{1,3}\s*[-–]\s*\d{1,3})(?!\d)")
_BAND_LINE = re.compile(
    r"(?im)^(?P<label>high distinction|distinction|excellent|outstanding|"
    r"first class|first|merit|credit|pass|fail)\b[^\n]{0,80}"
)
_RANK = {
    "high distinction": 100,
    "outstanding": 95,
    "excellent": 90,
    "distinction": 85,
    "first class": 84,
    "first": 80,
    "merit": 70,
    "credit": 65,
    "pass": 50,
    "fail": 0,
}

# Spoken gap lines. The same sentences reach the chat from every seat, so they
# live here as the one definition. Nothing is written back to the brief.
FORMAT_UNREAD = "Format: I could not read a format from this brief."
QUESTION_UNREAD = "Question: I could not read the assignment question from this brief."
FORMAT_NAMED_ONE = "Format: the brief does not name one."
QUESTION_NAMED_ONE = "Question: the brief does not name one."
PERCENTAGE_WEIGHTS = "The brief lists percentage weights, not grade bands."
NO_MARK_SCHEME = "No mark scheme is on this module."

# A format word a reader can see in prose, and a task verb that sets the job.
_FORMAT_WORD = re.compile(r"(?i)\b(?:report|essay|reflective\s+diary|diary|reflection)\b")
_TASK_VERB = re.compile(
    r"(?i)\b(?:evaluate|analyse|analyze|assess|discuss|compare|contrast|"
    r"criticise|criticize|define|describe|explain|justify|outline|review|"
    r"summarise|summarize)\b"
)
_PERCENT = re.compile(r"(?<!\d)(\d{1,3})\s*%")
_LABELLED_FIELD = re.compile(
    r"(?i)^\s*(?:genre|format|assignment\s+question|question|task|assignment\s+ask|"
    r"ask|title|assignment\s+title)\s*:"
)


def _prose_text(essay_id: str) -> str:
    """Brief text with the mark scheme block left out. The file is not changed."""
    return _brief_without_scheme(_brief_text(essay_id))


def _prose_signal_text(essay_id: str) -> str:
    """Unlabelled prose only. A labelled field is read by its own reader.

    A Genre, Format, Question, Task, assignment ask, or Title line already
    answers one requirement, so its words do not stand in for prose the
    reader failed to read. Every other line is prose.
    """
    kept: list[str] = []
    for line in unmarked_labels(_prose_text(essay_id)).splitlines():
        if _LABELLED_FIELD.match(line):
            continue
        kept.append(line)
    return "\n".join(kept)


def prose_has_format_signal(essay_id: str) -> bool:
    """True when the unlabelled prose shows a format word, a task verb, or a question mark.

    One test serves both spoken gap lines. A brief that shows any of these is
    not silent on the assignment, so the line says the read failed instead.
    """
    text = _prose_signal_text(essay_id)
    if not text:
        return False
    return bool(_FORMAT_WORD.search(text) or _TASK_VERB.search(text) or "?" in text)


def format_gap_line(essay_id: str, format_value: object) -> str:
    """The spoken format line. A named format speaks for itself.

    An unset format with a visible signal in the prose says the read failed.
    A brief that carries no signal at all keeps the older silent sentence.
    """
    if isinstance(format_value, str) and format_value.strip():
        return f"Format: {format_value.strip()}."
    if prose_has_format_signal(essay_id):
        return FORMAT_UNREAD
    return FORMAT_NAMED_ONE


def question_gap_line(essay_id: str, question: object) -> str:
    """The spoken question line. A stored question is said in the student's words."""
    if isinstance(question, str) and question.strip():
        return f"Question: {question.strip()}"
    if prose_has_format_signal(essay_id):
        return QUESTION_UNREAD
    return QUESTION_NAMED_ONE


def _scheme_percentages(essay_id: str) -> list[int]:
    """Percentages printed on the module's mark scheme, in reading order."""
    return [int(value) for value in _PERCENT.findall(_scheme_source(essay_id))]


def _scheme_source(essay_id: str) -> str:
    """Scheme text the spoken line reads: the filed scheme, then the brief.

    A filed scheme is already a mark scheme. A brief may print its weights
    under a mark scheme heading or under `Section weights:`, so both blocks
    are read here. A block of percentages has no named band, which the shared
    scheme reader treats as absent; this reader still sees it, which is how the
    percentage sentence replaces the no-scheme sentence.
    """
    filed = _scheme_file(essay_id)
    if filed:
        return filed
    brief = _brief_text(essay_id)
    return _scheme_block(brief) or _weights_block(brief)


def _band_search_text(scheme: str) -> str:
    """The scheme with table pipes gone and each line stripped.

    A band name often sits in a table row, where a leading pipe and padding
    would stop a band pattern that starts at the line. Reading the same lines
    with the pipes replaced and the edges trimmed finds that name. Nothing is
    added, reordered, or invented.
    """
    lines = [line.replace("|", " ").strip() for line in scheme.splitlines()]
    return "\n".join(lines)


def percentage_weights_only(essay_id: str) -> bool:
    """True when the scheme lists percentages but names no band and no range.

    A scheme with a named band or a numeric range keeps today's reading, so
    this returns False there. Nothing is invented from the percentages.
    """
    scheme = _scheme_source(essay_id)
    if not scheme.strip():
        return False
    weights = _scheme_percentages(essay_id)
    if not weights:
        return False
    if any(value <= 0 or value > 100 for value in weights):
        return False
    searchable = _band_search_text(scheme)
    return _highest_band(searchable) is None and _RANGE.search(searchable) is None


def _read(path) -> str:
    from essay_writer.invent import read_gathered_text

    try:
        return read_gathered_text(path)
    except (OSError, ValueError):
        return ""


def _brief_text(essay_id: str) -> str:

    return module_brief_text(essay_id).strip()


def _scheme_file(essay_id: str) -> str:

    folder = essay_dir(module_code(essay_id))
    if not folder.is_dir():
        return ""
    chunks: list[str] = []
    for name in _SCHEME_NAMES:
        path = folder / name
        if path.is_file() and path.stat().st_size > 0:
            text = _read(path).strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _block_after(brief: str, head: re.Pattern[str]) -> str:
    """Lines under one heading, up to a blank line or the next heading.

    The heading pattern names its label in group 1 and any text after the
    label in group 2. A blank line between the heading and its first content
    line is skipped, so a heading followed by a table is captured. Once content
    has started, a blank line or a new heading ends the block. The brief file
    is only read.
    """
    if not brief:
        return ""
    taken: list[str] = []
    capture = False
    for line in brief.splitlines():
        match = head.match(line.strip())
        if match:
            capture = True
            rest = match.group(2).strip()
            if rest:
                taken.append(rest)
            continue
        if not capture:
            continue
        if not line.strip():
            if taken:
                break
            continue
        if line.startswith("#"):
            break
        taken.append(line.strip())
    return "\n".join(taken).strip()


def _scheme_block(brief: str) -> str:
    """Text under a mark scheme heading in the brief, whether or not it names bands."""
    return _block_after(brief, _SCHEME_HEAD)


def _weights_block(brief: str) -> str:
    """Text under a section weights heading in the brief.

    A brief may print its weights under `Section weights:` rather than under a
    mark scheme heading. That block is a percentage list too, so it is read by
    the same tests that read a mark scheme block.
    """
    return _block_after(brief, _WEIGHTS_HEAD)


def _scheme_in_brief(brief: str) -> str:
    captured = _scheme_block(brief)
    if not captured:
        return ""
    if _highest_band(captured) is None and _RANGE.search(captured) is None:
        return ""
    return captured


def _format_of(text: str) -> str | None:
    if not text:
        return None

    genre = genre_from_brief_text(text)
    if genre == "diary":
        return "reflective diary"
    if genre:
        return genre
    match = _FORMAT_LINE.search(unmarked_labels(text))
    if match:
        return match.group(1).casefold()
    return None


def _brief_without_scheme(brief: str) -> str:
    lines: list[str] = []
    skip = False
    for line in brief.splitlines():
        if _SCHEME_HEAD.match(line.strip()):
            skip = True
            continue
        if skip:
            if not line.strip():
                skip = False
            continue
        lines.append(line)
    return "\n".join(lines)


def _question_of(text: str) -> str | None:
    """Question from Question, Task, assignment ask, or Title.

    An unlabeled paragraph is not a question. The brief file is not rewritten.
    """
    if not text:
        return None

    labeled = unmarked_labels(text)
    for pattern in _QUESTION_FIELDS:
        match = pattern.search(labeled)
        if match and match.group(1).strip():
            return match.group(1).strip()
    lines = labeled.splitlines()
    for label in _QUESTION_LABELS:
        for index, line in enumerate(lines):
            if line.strip().casefold() != label:
                continue
            for nxt in lines[index + 1 :]:
                nxt = nxt.strip()
                if not nxt:
                    continue
                if nxt.casefold() in _QUESTION_LABELS or _FIELD_LINE.match(nxt):
                    break
                return nxt
    return None


def _content_words(text: str) -> list[str]:
    """The shared extractor with this gate's vocabulary, in first-seen order.

    Kept as a named binding because the review seat imports this helper. The
    implementation is textutil.content_words; this module does not tokenize.
    """
    return content_words(text, stopwords=_STOP, ordered=True)


def _numeric_band(label: str) -> tuple[float, str] | None:
    compact = re.sub(r"\s+", "", label)
    plus = re.fullmatch(r"(\d{1,3})\+", compact)
    if plus:
        low = int(plus.group(1))
        if low > 100:
            return None
        return (low + 0.5, re.sub(r"\s+", "", label))
    numbers = re.fullmatch(r"(\d{1,3})[-–](\d{1,3})", compact)
    if numbers is None:
        return None
    left = int(numbers.group(1))
    right = int(numbers.group(2))
    if left > right:
        left, right = right, left
    if right > 100 or right <= left:
        return None
    return (float(right), re.sub(r"\s+", "", label))


def _highest_band(text: str) -> str | None:
    """Top descriptor written on the mark scheme. Nothing is invented."""
    if not text.strip():
        return None
    best_label: str | None = None
    best_score = -1.0
    for match in _BAND_LINE.finditer(text):
        label = re.sub(r"\s+", " ", match.group("label")).strip()
        window = text[match.start() : match.end() + 40]
        numbers = _RANGE.search(window)
        if numbers:
            score = float(max(int(numbers.group(1)), int(numbers.group(2))))
        else:
            score = float(_RANK.get(label.casefold(), -1))
        if score > best_score:
            best_score = score
            best_label = label
    for match in _NUMERIC_BAND.finditer(text):
        parsed = _numeric_band(match.group("label"))
        if parsed is None:
            continue
        score, printed = parsed
        if score > best_score:
            best_score = score
            best_label = printed
    return best_label


def _covers(text: str, words: list[str]) -> bool:
    if not words:
        return True
    folded = text.casefold()
    need = 1 if len(words) == 1 else 2
    hits = sum(1 for word in words if word in folded)
    return hits >= need


def mark_scheme_text(essay_id: str) -> str:
    """Mark scheme file, a scheme section, or a table copied out of the brief."""
    filed = _scheme_file(essay_id)
    if filed:
        return filed
    brief = _brief_text(essay_id)
    inline = _scheme_in_brief(brief)
    if inline:
        return inline

    return extract_marking_table(essay_id)


def assignment_requirements(essay_id: str) -> dict[str, Any]:
    """One requirement list from the brief and mark scheme. Product and plan read this."""
    return read_assignment(essay_id)


def study_defaults_allowed(essay_id: str) -> bool:
    """Studied module tables apply in daily use only, not when a brief or scheme is active."""
    return read_assignment(essay_id).get("active") is not True


def assignment_silence_gaps(essay_id: str) -> list[str]:
    """Gap sentences when the brief or scheme is active but silent on a requirement."""
    from essay_writer.brief_contract import assignment_silence_gaps as _gaps

    return _gaps(essay_id)


def read_assignment(essay_id: str) -> dict[str, Any]:
    """What the documents actually say. Missing documents stay off."""
    brief = _brief_text(essay_id)
    scheme = mark_scheme_text(essay_id)
    has_brief = bool(brief)
    has_scheme = bool(scheme)
    if not has_brief and not has_scheme:
        return {
            "ok": True,
            "active": False,
            "mapped": True,
            "mode": "daily",
            "brief": False,
            "mark_scheme": False,
            "format": None,
            "question": None,
            "highest_band": None,
            "named_entries": [],
            "named_by_brief": False,
            "named_parts_source": None,
            "part_count": None,
            "unnamed_note": None,
            "lock": None,
            "title_page": {
                "fields": [],
                "registration": False,
                "name": "silent",
                "programme": False,
            },
            "page_layout": {},
            "findings_opening": "none",
        }
    brief_body = _brief_without_scheme(brief)
    scheme_format = _format_of(scheme)
    brief_format = _format_of(brief_body)
    prescribed: str | None
    if scheme_format and brief_format and scheme_format != brief_format:
        prescribed = scheme_format
    else:
        prescribed = scheme_format or brief_format
    if brief_format == "reflective diary" or scheme_format == "reflective diary":
        from essay_writer.diary import diary_ask

        question = diary_ask(brief_body) or _question_of(brief_body) or _question_of(scheme)
    else:
        question = _question_of(brief_body) or _question_of(scheme)
    band = _highest_band(scheme) if has_scheme else None
    if has_scheme:
        mode = "both" if has_brief else "mark_scheme"
    else:
        mode = "brief"
    from essay_writer.brief_contract import contract_for, writing_type_of

    contract = contract_for(
        writing_type_of(prescribed),
        brief_body or brief,
        has_scheme=has_scheme,
        scheme=scheme,
    )
    mapped = contract.get("mapped") is not False
    record: dict[str, Any] = {
        "ok": mapped,
        "active": True,
        "mapped": mapped,
        "mode": mode,
        "brief": has_brief,
        "mark_scheme": has_scheme,
        "format": prescribed,
        "question": question,
        "highest_band": band,
        "named_entries": list(contract.get("named_entries") or []),
        "named_by_brief": contract.get("named_by_brief") is True,
        "named_parts_source": contract.get("named_parts_source"),
        "part_count": contract.get("part_count"),
        "unnamed_note": contract.get("unnamed_note"),
        "lock": contract.get("lock"),
        "title_page": contract.get("title_page"),
        "page_layout": contract.get("page_layout")
        if isinstance(contract.get("page_layout"), dict)
        else {},
        "findings_opening": contract.get("findings_opening"),
        "writing_type": contract.get("writing_type"),
    }
    if not mapped:
        record["reason"] = str(contract.get("reason") or "")
    title_page = record.get("title_page")
    if isinstance(title_page, dict):
        from essay_writer.diary import scrub_title_page_labels

        record["title_page"] = scrub_title_page_labels(title_page, brief_body or brief)
    return record


def question_is_answered(text: str, question: str | None) -> bool:
    """True when the text uses the assignment question's own words."""
    if not question:
        return False
    return _covers(text or "", content_words(question, stopwords=_STOP, ordered=True))


def ask_content_words(question: str | None) -> list[str]:
    """Words of the assignment ask. Short words and stop words are left out."""
    if not isinstance(question, str) or not question.strip():
        return []
    return content_words(question, stopwords=_STOP, ordered=True)


def ask_word_in_text(text: str, question: str | None) -> bool:
    """True when the opened text uses one word of the assignment ask."""
    words = ask_content_words(question)
    if not words:
        return False
    folded = text.casefold() if isinstance(text, str) else ""
    return any(word in folded for word in words)


def north_star_gate(essay_id: str, text: str) -> dict[str, Any]:
    """Mark scheme, prescribed format, and whether the draft does the assignment.

    Daily use, with no brief and no mark scheme, passes. A miss does not
    invent a scheme, a format, or a question. The same check is assignment_gate.
    """
    record = read_assignment(essay_id)
    report = assignment_gate(essay_id, text, seat="writer")
    missing = [item for item in report.get("missing") or [] if isinstance(item, str)]
    passed = report.get("ok") is True
    active = record.get("active") is True
    return {
        "passed": passed,
        "active": active,
        "mark_scheme": bool(record.get("mark_scheme")),
        "mark_scheme_met": (not record.get("mark_scheme")) or ("highest_band" not in missing),
        "format": record.get("format"),
        "format_met": "format" not in missing and "record" not in missing,
        "question": record.get("question"),
        "does_assignment": "question" not in missing and "record" not in missing,
        "missing": missing,
        "reason": "" if passed else str(report.get("reason") or ""),
    }


def assignment_gate(essay_id: str, text: str, *, seat: str) -> dict[str, Any]:
    """Whether this save may go ahead. Daily use returns active false."""
    record = read_assignment(essay_id)
    if record["active"] is False:
        return record
    if record.get("mapped") is False:
        record["ok"] = False
        record["missing"] = ["mapping"]
        return record
    submitted = text.strip() if isinstance(text, str) else ""
    missing: list[str] = []
    if not submitted:
        missing.append("record")
    if record["format"] and record["format"] not in submitted.casefold():
        missing.append("format")
    question_words = content_words(record["question"] or "", stopwords=_STOP, ordered=True)
    if record["question"] and not _covers(submitted, question_words):
        missing.append("question")
    band = record["highest_band"]
    # EQR judges opened student Word against engagement asks. The top band is
    # already on the assignment record from the brief or mark scheme; it is not
    # pasted into the student's cover or body.
    if (
        seat != "eqr"
        and record["mark_scheme"]
        and band
        and band.casefold() not in submitted.casefold()
    ):
        missing.append("highest_band")
    if not missing:
        record["ok"] = True
        return record
    record["ok"] = False
    record["missing"] = missing
    record["reason"] = _reason(record, seat)
    return record


def _reason(record: dict[str, Any], seat: str) -> str:
    from essay_writer.specialists.eqr import HIGHEST_BAND as EQR_BAND
    from essay_writer.specialists.writer import HIGHEST_BAND as WRITER_BAND

    parts: list[str] = []
    if "record" in record["missing"]:
        parts.append("Write what this assignment asks before saving.")
    if ("format" in record["missing"] and record["format"]) or "question" in record["missing"]:
        parts.append("Add the format and the assignment question in this chat, then save.")
    if "highest_band" in record["missing"] and record["highest_band"]:
        owned = EQR_BAND if seat == "eqr" else WRITER_BAND
        parts.append(f"{owned} The top band here is {record['highest_band']}.")
    if not parts:
        parts.append("The assignment check is not met yet.")
    return " ".join(parts)
