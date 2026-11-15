"""Conditional constitution. Shared by Grok Bot, Writer, and EQR.

No mark scheme and no brief: daily-use essay or report. The gate does not block
and does not invent a mark scheme, a question, a format, or a band.

A brief with no mark scheme: format and question come from the brief. A missing
mark scheme does not block, and no band is invented. When a label leaves a
field empty, one obvious cue may fill that field. A stored answer beside the
brief fills a format or a question that is still empty. The brief file is not
rewritten.

A mark scheme: mark scheme, prescribed format, and assignment ask come first.
The aim is the highest band on that scheme, not merely a pass. On a conflict
with the brief, the mark scheme wins.

This is not mechanical gate 1. A missing brief is not a failure.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
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
# An obvious format cue. A label still wins; these fill only an empty field.
# A kind counts only as the assignment type, so a topic that happens to be an
# annual report, or a type the brief tells the student not to write, is not it.
_FORMAT_KIND = r"(individual\s+report|reflective\s+diary|essay|report)"
_ASSIGNMENT_TYPE = re.compile(
    rf"(?i)(?:"
    rf"\b(?:assessment|assignment(?:\s+type)?)\s*:\s*(?:an?\s+)?{_FORMAT_KIND}\b"
    rf"|"
    rf"\bthis\s+(?:assignment|assessment|task)\s+is\s+an?\s+{_FORMAT_KIND}\b"
    rf"|"
    rf"\b(?:write|produce|submit)\s+an?\s+{_FORMAT_KIND}\b"
    rf")"
)
_EITHER_OR = re.compile(rf"(?i)\b{_FORMAT_KIND}[ \t]+or[ \t]+(?:an?[ \t]+)?{_FORMAT_KIND}\b")
# A heading line that opens with the type is the type, as in "Individual report,
# 2,000 words, due 12 December 2026." A mention later in a sentence is not.
_LINE_START_TYPE = re.compile(
    r"(?im)^[ \t]*(?:[-*•][ \t]*)?(individual[ \t]+report|reflective[ \t]+diary)\b"
)
_NEGATION = re.compile(r"(?i)\b(?:not|never|no|cannot|can['’]t|don['’]t|doesn['’]t|won['’]t)\b")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+")
_TASK_OPEN = re.compile(
    r"(?i)^(?:evaluate|analyse|analyze|assess|discuss|compare|contrast|"
    r"criticise|criticize|define|describe|explain|justify|outline|review|"
    r"summarise|summarize)\b"
)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_PERCENT = re.compile(r"(?<!\d)(\d{1,3})\s*%")
# A plain weight row, a column header such as "Section Weight", and a pipe row
# open a weights block. A labelled field or ordinary prose does not, whatever
# percentage it carries, so `Word count: ... 10%` is not read as a weight.
_PLAIN_WEIGHT_ROW = re.compile(
    r"^\s*(?:[-*•]\s*|\d{1,2}[.)]\s*)?[A-Za-z][A-Za-z &/'().,\-]{0,63}"
    r"\s*(?:—|–|-|:)?\s*\d{1,3}\s*%\s*[.]?\s*$"
)
_WEIGHT_HEADER_WORDS = frozenset(
    {
        "section",
        "sections",
        "part",
        "parts",
        "criterion",
        "criteria",
        "component",
        "components",
        "item",
        "items",
        "area",
        "areas",
        "weight",
        "weights",
        "weighting",
        "weightings",
        "mark",
        "marks",
        "percentage",
        "score",
        "%",
    }
)
# A prose sentence that starts with one of these is not a weight row.
_PROSE_OPENERS = frozenset(
    {
        "this",
        "these",
        "the",
        "a",
        "an",
        "there",
        "it",
        "you",
        "your",
        "students",
        "we",
        "each",
        "all",
        "some",
        "for",
        "in",
        "on",
        "at",
        "to",
        "and",
        "or",
        "if",
        "when",
        "where",
        "which",
        "that",
        "as",
        "by",
        "with",
    }
)


def _opens_weights(first: str) -> bool:
    """True when this first line looks like a weights table or a weight row.

    A pipe row, a plain ``Drivers 20%`` row, and a column header are accepted.
    Anything else, a labelled field or prose, ends a weights block with nothing
    captured, so a percentage in ``Word count:`` is not read as a weight.
    """
    if first.lstrip().startswith("|"):
        return True
    words = re.findall(r"[A-Za-z]+", first)
    if len(words) > 8 or (words and words[0].casefold() in _PROSE_OPENERS):
        return False
    if _PLAIN_WEIGHT_ROW.match(first):
        return True
    tokens = re.findall(r"[A-Za-z%]+", first)
    return bool(tokens) and all(token.casefold() in _WEIGHT_HEADER_WORDS for token in tokens)


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


def _block_after(
    brief: str,
    head: re.Pattern[str],
    *,
    skip_blank: bool = False,
    opens: Callable[[str], bool] | None = None,
) -> str:
    """Lines under one heading, up to a blank line or the next heading.

    The heading pattern names its label in group 1 and any text after the
    label in group 2. An empty heading ends the block at once, so a heading
    with no content is not filled from later prose or from a labelled field.
    With ``skip_blank``, a blank line between the heading and its first
    content line is skipped, so a heading followed by a table is captured.
    With ``opens``, the block's first content line must pass that test, so a
    heading set off from a labelled field or ordinary prose captures nothing.
    Once content has started, a blank line or a new heading ends the block.
    The brief file is only read.
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
            if skip_blank:
                continue
            break
        if line.startswith("#"):
            break
        if not taken and opens is not None and not opens(line.strip()):
            break
        taken.append(line.strip())
    return "\n".join(taken).strip()


def _scheme_block(brief: str) -> str:
    """Text under a mark scheme heading in the brief, whether or not it names bands.

    A mark scheme heading with nothing under it captures nothing. Later prose
    or a labelled field is not that block, so it is not read as one.
    """
    return _block_after(brief, _SCHEME_HEAD)


def _weights_block(brief: str) -> str:
    """Text under a section weights heading in the brief.

    A brief may print its weights under `Section weights:` rather than under a
    mark scheme heading. That block is a percentage list too, so it is read by
    the same tests that read a mark scheme block. A blank line before the table
    is skipped, because a weights heading is often set off from its table.

    The first content line must look like a table or a weight row. A labelled
    field or ordinary prose ends the block with nothing captured, so a
    percentage inside `Word count:` is not read as a weight.
    """
    return _block_after(brief, _WEIGHTS_HEAD, skip_blank=True, opens=_opens_weights)


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


def _labelled_choice(scheme_format: str | None, brief_format: str | None) -> str | None:
    """A Format or Genre label. The mark scheme wins when the two labels differ."""
    if scheme_format and brief_format and scheme_format != brief_format:
        return scheme_format
    return scheme_format or brief_format


def labelled_format(essay_id: str) -> str | None:
    """Format named by a Genre or Format label. An obvious cue is not a label.

    Stage titles keep using this label. A cue can fill the shared format
    without changing the combined title.
    """
    brief = _brief_text(essay_id)
    scheme = mark_scheme_text(essay_id)
    return _labelled_choice(_format_of(scheme), _format_of(_brief_without_scheme(brief)))


def _kind_name(raw: str) -> str:
    name = re.sub(r"\s+", " ", raw).strip().casefold()
    if name == "individual report":
        return "report"
    return name


def _sentence_start(text: str, at: int) -> int:
    """Start of the sentence that contains this position."""
    start = 0
    for index in range(at):
        if text[index] in ".!?\n":
            start = index + 1
    return start


def _negated(text: str, at: int) -> bool:
    """True when a refusal such as "not", "no", "cannot", or "don't" comes first in the sentence."""
    return bool(_NEGATION.search(text[_sentence_start(text, at) : at]))


def _format_cue(text: str) -> str | None:
    """One obvious format, or nothing when two assignment types both match.

    A kind counts where the brief sets the assignment type: an Assessment or
    Assignment line, "this assignment is ...", "write an ...", or a heading
    line that opens with the type. So an annual report a student must write
    about is a topic, not a second format, and a mention later in a sentence
    is not the type either. A type the brief tells the student not to write
    is not that type. Words inside the mark scheme are not this cue. Nothing
    is written back.
    """
    if not text or not text.strip():
        return None
    body = _brief_without_scheme(unmarked_labels(text))
    if not body.strip():
        return None
    kinds: set[str] = set()
    for match in _EITHER_OR.finditer(body):
        if _negated(body, match.start()):
            continue
        for raw in match.groups():
            if raw:
                kinds.add(_kind_name(raw))
    for match in _ASSIGNMENT_TYPE.finditer(body):
        if _negated(body, match.start()):
            continue
        for raw in match.groups():
            if raw:
                kinds.add(_kind_name(raw))
    for match in _LINE_START_TYPE.finditer(body):
        if _negated(body, match.start()):
            continue
        kinds.add(_kind_name(match.group(1)))
    if "reflective diary" in kinds and ("essay" in kinds or "report" in kinds):
        return None
    if len(kinds) == 1:
        return next(iter(kinds))
    return None


def _question_cue(text: str) -> str | None:
    """One task sentence, or one question that ends in a question mark.

    The mark scheme block is left out, so a bullet under that heading is not
    the question. A labelled line is left to the label reader. Nothing is written.
    """
    if not text or not text.strip():
        return None
    body = _brief_without_scheme(unmarked_labels(text))
    for line in body.splitlines():
        stripped = _BULLET.sub("", line.strip(), count=1).strip()
        if not stripped or _FIELD_LINE.match(stripped) or _LABELLED_FIELD.match(stripped):
            continue
        for sentence in _SENTENCE_BREAK.split(stripped):
            sentence = sentence.strip()
            if not sentence:
                continue
            words = re.findall(r"[A-Za-z0-9']+", sentence)
            if len(words) < 3:
                continue
            if _TASK_OPEN.match(sentence) or sentence.endswith("?"):
                return sentence
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


def _question_of(text: str, *, cues: bool = True) -> str | None:
    """Question from a label, or one obvious cue when the brief left it empty.

    Question, Task, assignment ask, and Title win. A cue is one task sentence
    or one question that ends in a question mark, and it is not taken from a
    mark-scheme bullet. The brief file is not rewritten.
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
    if not cues:
        return None
    return _question_cue(text)


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


_BRIEF_META = "brief-meta.json"
_FORMAT_ANSWERS = {
    "essay": "essay",
    "report": "report",
    "reflective diary": "reflective diary",
}
_NO_BRIEF_REASON = "There is no brief to store an answer beside."
_STORE_REASON = "I could not store that answer beside the brief."


def _brief_digest(text: str) -> str:
    """SHA-256 of the brief text ``read_assignment`` already reads."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _brief_meta_path(essay_id: str):
    return essay_dir(essay_id) / _BRIEF_META


def _no_assignment_document(essay_id: str) -> bool:
    """True when ``read_assignment`` would take the no-document return.

    This does not open ``brief-meta.json``.
    """
    if _brief_text(essay_id):
        return False
    return not bool(_scheme_file(essay_id))


def _allowed_format(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return _FORMAT_ANSWERS.get(re.sub(r"\s+", " ", value).strip().casefold())


def _read_brief_meta(essay_id: str) -> dict[str, Any] | None:
    """The side file when it is a readable object. A bad file is ignored.

    The file is not deleted. ``highest_band``, ``named_entries``, and
    ``mark_scheme`` in the file are not read.
    """
    path = _brief_meta_path(essay_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    digest = data.get("brief_sha256")
    if not isinstance(digest, str) or not digest.strip():
        return None
    stored_format = data.get("format")
    if "format" in data and stored_format is not None and not isinstance(stored_format, str):
        return None
    if (
        "question" in data
        and data.get("question") is not None
        and not isinstance(data.get("question"), str)
    ):
        return None
    return data


def _accepted_brief_meta(essay_id: str, brief: str) -> dict[str, Any] | None:
    """A side file whose hash matches this brief text. A mismatch is ignored."""
    data = _read_brief_meta(essay_id)
    if data is None:
        return None
    if data.get("brief_sha256") != _brief_digest(brief):
        return None
    return data


def _no_brief_refusal() -> dict[str, Any]:
    from essay_writer.confirm import refuse

    return refuse(
        "no-brief",
        _NO_BRIEF_REASON,
        next="Add the assignment brief, then answer the format or the question.",
    )


def _store_refusal() -> dict[str, Any]:
    from essay_writer.confirm import refuse

    return refuse(
        "answer",
        _STORE_REASON,
        next="The brief is unchanged. This stage was not saved.",
    )


def _rollback_brief_meta(path, before: bytes | None) -> None:
    """Put the previous side file back. Drop a new file that is not the old bytes."""
    import os
    import tempfile

    try:
        if before is None:
            if path.is_file() or path.is_symlink():
                path.unlink()
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(before)
            os.replace(temporary, path)
        except OSError:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            if path.is_file():
                try:
                    current = path.read_bytes()
                except OSError:
                    current = b""
                if current != before:
                    path.unlink()
    except OSError:
        return


def _publish_brief_meta(path, record: dict[str, Any]) -> None:
    """Write the side file, or leave the previous bytes when the write fails."""
    from essay_writer.records import write_json

    before = path.read_bytes() if path.is_file() else None
    try:
        write_json(path, record, mkdir=True)
        written = path.read_bytes()
        parsed = json.loads(written.decode("utf-8"))
        if not isinstance(parsed, dict) or parsed.get("brief_sha256") != record["brief_sha256"]:
            raise OSError("the answer file was not complete")
        if parsed.get("format") != record.get("format") or parsed.get("question") != record.get(
            "question"
        ):
            raise OSError("the answer file was not complete")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _rollback_brief_meta(path, before)
        raise OSError("the answer file was not complete") from exc


def store_brief_answer(
    essay_id: str,
    format_answer: str | None,
    question_answer: str | None,
) -> dict[str, Any] | None:
    """Write or clear the answer beside the brief. A refusal writes nothing.

    Called only for a draft that sent ``formatAnswer`` or ``questionAnswer``.
    An empty string clears that field. Any other format value is ignored.
    When both fields are empty the side file is removed. The brief file is
    not opened for writing.
    """
    if _no_assignment_document(essay_id):
        return _no_brief_refusal()
    brief = _brief_text(essay_id)
    saved = _accepted_brief_meta(essay_id, brief)
    kept_format = _allowed_format(saved.get("format")) if saved is not None else None
    kept_question = None
    if saved is not None:
        raw_question = saved.get("question")
        if isinstance(raw_question, str) and raw_question.strip():
            kept_question = raw_question.strip()
    if isinstance(format_answer, str):
        if format_answer == "":
            kept_format = None
        else:
            allowed = _allowed_format(format_answer)
            if allowed is not None:
                kept_format = allowed
    if isinstance(question_answer, str):
        if question_answer == "":
            kept_question = None
        elif question_answer.strip():
            kept_question = question_answer.strip()
    path = _brief_meta_path(essay_id)
    if kept_format is None and kept_question is None:
        before = path.read_bytes() if path.is_file() else None
        if before is None:
            return None
        try:
            path.unlink()
        except OSError:
            _rollback_brief_meta(path, before)
            return _store_refusal()
        return None
    record: dict[str, Any] = {"brief_sha256": _brief_digest(brief)}
    if kept_format is not None:
        record["format"] = kept_format
    if kept_question is not None:
        record["question"] = kept_question
    try:
        _publish_brief_meta(path, record)
    except OSError:
        return _store_refusal()
    return None


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
    prescribed = _labelled_choice(scheme_format, brief_format)
    if prescribed is None:
        prescribed = _format_cue(brief_body)
    # Labels, scheme lines, and obvious cues win. The side file fills only a
    # field that is still empty, and only when its hash matches this brief.
    saved_answer = _accepted_brief_meta(essay_id, brief) if prescribed is None else None
    if prescribed is None and saved_answer is not None:
        prescribed = _allowed_format(saved_answer.get("format"))
    if (
        brief_format == "reflective diary"
        or scheme_format == "reflective diary"
        or prescribed == "reflective diary"
    ):
        from essay_writer.diary import diary_ask

        question = (
            diary_ask(brief_body) or _question_of(brief_body) or _question_of(scheme, cues=False)
        )
    else:
        question = _question_of(brief_body) or _question_of(scheme, cues=False)
    if not question:
        if saved_answer is None:
            saved_answer = _accepted_brief_meta(essay_id, brief)
        if saved_answer is not None:
            raw_question = saved_answer.get("question")
            if isinstance(raw_question, str) and raw_question.strip():
                question = raw_question.strip()
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
