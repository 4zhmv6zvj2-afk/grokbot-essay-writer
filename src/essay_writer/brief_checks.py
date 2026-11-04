"""Brief checks shown before Word.

Section lengths, contradictions, and simulation events are read from the
brief file. Nothing here invents a budget, a rubric, or a simulation.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer import textutil as essay_textutil
from essay_writer.assignment_gate import mark_scheme_text
from essay_writer.textutil import WORD, count_words, norm_space

SAFE_DEFAULT = "The safe default is the task headings and the rubric that was used."

_BUDGET_CUE = re.compile(
    r"(?i)(section budgets?|word budgets?|recommended shape and word budgets?)\s*:\s*"
)
_SKIP_LABELS = frozenset(
    {
        "total",
        "limit",
        "overall",
        "maximum",
        "minimum",
        "word count",
        "words",
        "word",
    }
)
_GENERAL = re.compile(
    r"(?i)\b(?:"
    r"it is (?:widely |generally |often )?(?:known|accepted|argued|important|clear)"
    r"|(?:many|several) (?:scholars|authors|studies|writers)"
    r"|this (?:topic|issue|subject) (?:is|has been)"
    r"|in the modern world"
    r"|in today'?s world"
    r"|as (?:noted|discussed|mentioned) above"
    r"|research (?:shows|suggests|indicates)"
    r")\b"
)
_SIMULATION = re.compile(r"(?i)\bsimulation events?\b|\bsimulation\b")
_GROUP = re.compile(r"(?i)\bgroup (?:assessment|coursework|project|report|assignment)\b")
_INDIVIDUAL = re.compile(r"(?i)\bindividual\b")
_HARVARD_APA = re.compile(r"(?i)harvard\s*/\s*apa|\bharvard\b.*\bapa\b|\bapa\b.*\bharvard\b")
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_COUNTED = re.compile(r"(\d{2,5})\s*(?:words?\b)?")
_RANGE_FOLLOWS = re.compile(r"^\s*(?:[-–—]|to\s+\d)")


def section_budgets(text: str) -> list[dict[str, Any]]:
    """Section lengths the brief lists. An absent list is empty. Nothing is invented.

    One count closes one listed name. A name that contains "and" stays one name,
    and a range such as "400-500 words" is left alone rather than read as 400.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    match = _BUDGET_CUE.search(text)
    if match is None:
        return []
    window = text[match.end() : match.end() + 600]
    window = window.split("\n\n", 1)[0]
    window = re.sub(r"(?<=\d),(?=\d{3}\b)", "", window)
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for piece in re.split(r"[,;]", window):
        piece = norm_space(piece)
        if not piece:
            continue
        last = 0
        for counted in _COUNTED.finditer(piece):
            if _RANGE_FOLLOWS.match(piece[counted.end() :]):
                last = counted.end()
                continue
            label = norm_space(piece[last : counted.start()])
            label = re.sub(r"(?i)^(?:and|plus)\b\s*", "", label).strip(" .:-")
            last = counted.end()
            if not label or label.casefold() in _SKIP_LABELS:
                continue
            words = int(counted.group(1))
            if words <= 0 or label.casefold() in seen:
                continue
            seen.add(label.casefold())
            low = int(words * 0.9)
            high = int(words * 1.1)
            found.append({"heading": label, "words": words, "low": low, "high": high})
    return found


_SECTION_NUMBER = re.compile(r"^\s*(?:\d{1,2}(?:\.\d+)*[.)]?\s*)+")


_WORD_COUNT = re.compile(r"(?i)\b(\d{1,3}(?:,\d{3})+|\d{2,5})\s+words?\b")
_TOTAL_HINT = re.compile(
    r"(?i)\b(?:total|overall|whole|words?|word\s*count|essay|report|assignment|piece|submission|coursework|diary)\b"
)
_NOT_TOTAL = re.compile(
    r"(?i)\b(?:each|per|every|entry|entries|section|sections|part|parts|minimum|maximum|least|most)\b"
)
_RANGE_TOKEN = re.compile(r"\d[\d,]*\s*(?:[-–—]|to)\s*\d[\d,]*")
_SENTENCE_LINE = re.compile(r"(?<=[.!?])\s+")
# Parts that have their own length. A count next to one is not the whole-piece
# total. Longer reference-list phrasings come first so they win over "references".
_PART_NOUNS = (
    r"abstract|executive summary|lists? of references?|reference lists?|references list|"
    r"reference list|references?|bibliography|appendix|appendices|contents|"
    r"title page|cover page"
)
_PART_LABEL = re.compile(rf"(?i)\b(?:{_PART_NOUNS})\b[\s:()\-–—]{{0,8}}$")
# The same part as the subject of a sentence: "The abstract is limited to 150 words."
_PART_SUBJECT = re.compile(
    rf"(?i)^\s*(?:(?:the|a|an|your|its|this|that)\s+)?(?:{_PART_NOUNS})\b"
)
# Words a sentence may put between that subject and the count. Anything else
# means the count belongs to something other than the part.
_PART_LIMIT_GAP = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "should",
        "must",
        "will",
        "can",
        "needs",
        "to",
        "at",
        "about",
        "around",
        "roughly",
        "approximately",
        "approx",
        "of",
        "up",
        "no",
        "more",
        "than",
        "maximum",
        "minimum",
        "least",
        "most",
        "a",
        "an",
        "the",
        "only",
        "just",
        "limited",
        "capped",
        "and",
        "or",
        "not",
    }
)


def _is_prose_part_limit(sentence: str, start: int) -> bool:
    """True when the sentence starts with a part and the count is that part's own length.

    "The abstract is limited to 150 words" and "References should be about 500
    words" are part lengths. "The essay, including references, is 2,000 words"
    is not, because the part is not the subject of the sentence.
    """
    head = sentence[:start]
    subject = _PART_SUBJECT.match(head)
    if subject is None:
        return False
    gap = head[subject.end() :]
    if len(gap) > 40:
        return False
    words = re.findall(r"[a-z']+", gap.casefold())
    return bool(words) and all(word in _PART_LIMIT_GAP for word in words)


def stated_word_totals(text: str) -> list[int]:
    """Whole-piece word counts the brief states, in the order it states them.

    A per-entry or per-section length, a part's own length (a labeled line or a
    sentence such as "The abstract is limited to 150 words"), a minimum or
    maximum, and a printed range are not this list. Nothing is inferred from a
    percentage.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    totals: list[int] = []
    for line in text.splitlines():
        for sentence in _SENTENCE_LINE.split(line):
            if _NOT_TOTAL.search(sentence) or not _TOTAL_HINT.search(sentence):
                continue
            ranges = [match.span() for match in _RANGE_TOKEN.finditer(sentence)]
            for match in _WORD_COUNT.finditer(sentence):
                if any(start <= match.start() < end for start, end in ranges):
                    continue
                if _PART_LABEL.search(sentence[max(0, match.start() - 50) : match.start()]):
                    continue
                if _is_prose_part_limit(sentence, match.start()):
                    continue
                value = int(match.group(1).replace(",", ""))
                if 100 <= value <= 20000 and value not in totals:
                    totals.append(value)
    return totals


def word_total_clash(text: str) -> str | None:
    """A notice when the brief states two different whole-piece totals.

    The band keeps following the first one. This names the clash and does not
    choose between them, and it does not block the save.
    """
    totals = stated_word_totals(text)
    if len(totals) < 2:
        return None
    shown = " and ".join(f"{value:,}" for value in totals)
    return (
        f"The brief states more than one total word count ({shown}). "
        "Check which one the brief means before planning the length."
    )


def _heading_key(value: str) -> str:
    """A heading or a listed section name, without a section number or end mark.

    The brief prints "Introduction 400" and the draft may head it "1. Introduction"
    or "Introduction:". Those are the same section. Nothing else is dropped.
    """
    text = norm_space(value).casefold()
    text = _SECTION_NUMBER.sub("", text).strip()
    return text.rstrip(" .:;-–—").strip()


def section_budget_issues(
    essay_id: str,
    sections: list[dict[str, str]],
    *,
    acknowledged: bool,
    exclude_citations: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, object]]]:
    """Block or warn when a listed section length is missed. No list means no check.

    A section budget printed in the mark scheme file counts the same as one in
    the brief. The brief is read first, and the scheme fills in only when the
    brief prints no list at all.
    """

    budgets = section_budgets(essay_textutil.module_brief_text(essay_id))
    if not budgets:
        budgets = section_budgets(mark_scheme_text(essay_id))
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, object]] = []
    if not budgets:
        return rows, issues
    by_heading = {_heading_key(section.get("heading", "")): section for section in sections}
    for budget in budgets:
        key = _heading_key(str(budget["heading"]))
        section = by_heading.get(key)
        counted = 0
        if section is not None:
            counted = count_words(section.get("body", ""), exclude_citations=exclude_citations)
        inside = section is not None and budget["low"] <= counted <= budget["high"]
        row = {
            "heading": budget["heading"],
            "words": budget["words"],
            "low": budget["low"],
            "high": budget["high"],
            "counted": counted,
            "inside": inside,
            "missing": section is None,
        }
        rows.append(row)
        if inside:
            continue
        if section is None:
            reason = (
                f"The brief lists a word budget for {budget['heading']} "
                f"({budget['low']}–{budget['high']}). That section is missing."
            )
        else:
            reason = (
                f"The brief lists a word budget for {budget['heading']} "
                f"({budget['low']}–{budget['high']}). This section has {counted} words. "
                "Fix the draft, or set section_words_acknowledged true only after a person accepts it."
            )
        issues.append({"code": "section-budget", "reason": reason, "warn": acknowledged})
    return rows, issues


def brief_contradictions(text: str) -> list[str]:
    """Contradictions the brief states. The safe default is not chosen from the clash."""
    if not isinstance(text, str) or not text.strip():
        return []
    found: list[str] = []
    if _GROUP.search(text) and _INDIVIDUAL.search(text):
        found.append("The brief says the work is both a group assessment and individual.")
    if "50%" in text and "100%" in text:
        found.append("The brief states both 50% and 100%.")
    if _HARVARD_APA.search(text):
        found.append('The brief names both Harvard and APA ("Harvard/APA" when written that way).')
    outcomes = re.search(
        r"(?is)learning outcomes?\s*:?\s*(.+?)(?:\n\s*\n|rubric\b|section budgets?\b|$)",
        text,
    )
    rubric = re.search(r"(?is)\brubric\s*:?\s*(.+?)(?:\n\s*\n|section budgets?\b|$)", text)
    if outcomes and rubric:
        left = _topic_words(outcomes.group(1))
        right = _topic_words(rubric.group(1))
        if left and right and not (left & right):
            found.append(
                "Learning outcomes and the rubric do not describe the same task. "
                "The rubric that was used is the one to satisfy."
            )
    return found


def _topic_words(chunk: str) -> set[str]:
    stop = {
        "learning",
        "outcome",
        "outcomes",
        "rubric",
        "criteria",
        "criterion",
        "marks",
        "weight",
        "section",
        "should",
        "which",
        "their",
        "about",
        "using",
        "include",
        "these",
        "those",
        "there",
        "where",
        "would",
        "could",
    }
    return {word.casefold() for word in re.findall(r"[A-Za-z]{5,}", chunk) if word.casefold() not in stop}


def simulation_in_brief(text: str) -> bool:
    return bool(isinstance(text, str) and re.search(r"(?i)simulation events?", text))


def _corpus(parts: list[str]) -> str:
    return " ".join(_flat(part) for part in parts if isinstance(part, str))


def _flat(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _sentences(text: str) -> list[str]:
    """Sentences, keeping a period inside quotation marks with that quotation."""
    if not isinstance(text, str) or not text.strip():
        return []
    held: list[str] = []

    def protect(match: re.Match[str]) -> str:
        held.append(match.group(0))
        return f"\x00{len(held) - 1}\x00"

    masked = re.sub(r'"[^"]*"|“[^”]*”', protect, text)

    def restore(match: re.Match[str]) -> str:
        return held[int(match.group(1))]

    found: list[str] = []
    for raw in _SENTENCE.findall(masked):
        sentence = norm_space(re.sub(r"\x00(\d+)\x00", restore, raw))
        if sentence:
            found.append(sentence)
    return found


def invented_simulation(
    sections: list[dict[str, str]],
    brief: str,
    gathered: list[str],
) -> list[dict[str, object]]:
    """A simulation sentence may appear only when the brief or a gathered file already has it."""
    if not simulation_in_brief(brief) and not any(_SIMULATION.search(section.get("body", "")) for section in sections):
        return []
    corpus = _corpus([brief, *gathered])
    issues: list[dict[str, object]] = []
    for section in sections:
        for sentence in _sentences(section.get("body", "")):
            if not _SIMULATION.search(sentence):
                continue
            flat = _flat(sentence)
            if len(flat) >= 12 and flat in corpus:
                continue
            if len(flat) < 12 and flat and flat in corpus:
                continue
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        "Do not invent simulation content. The brief names simulation events, "
                        "and this sentence is not in the brief or a gathered file."
                    ),
                }
            )
    return issues


def decorative_citations(text: str) -> list[str]:
    """Marker-style parked citations: a citation on a general sentence, or a citation alone."""
    if not isinstance(text, str) or not text.strip():
        return []
    parked: list[str] = []
    for sentence in _sentences(text):
        if "(" not in sentence and not re.search(r"\(\d{4}\)", sentence):
            continue
        from essay_writer.textutil import citation_tokens

        if not citation_tokens(sentence):
            continue
        stripped = re.sub(r"\([^)]*\d{4}[^)]*\)", " ", sentence)
        words = WORD.findall(stripped)
        general = _GENERAL.search(sentence) is not None
        if general or len(words) < 3:
            parked.append(sentence)
    return parked


def before_word(
    essay_id: str,
    sections: list[dict[str, str]],
    *,
    acknowledged_sections: bool,
    acknowledged_contradiction: bool,
    acknowledged_simulation: bool,
    exclude_citations: bool,
    gathered: list[str] | None = None,
) -> dict[str, Any]:
    """Checks a person must see before Word confirm."""
    brief = essay_textutil.module_brief_text(essay_id)
    rows, budget_issues = section_budget_issues(
        essay_id,
        sections,
        acknowledged=acknowledged_sections,
        exclude_citations=exclude_citations,
    )
    clashes = brief_contradictions(brief)
    word_clash = word_total_clash(brief)
    noticed = simulation_in_brief(brief)
    blockers: list[dict[str, object]] = []
    notes: list[dict[str, object]] = []
    for item in budget_issues:
        target = notes if item.get("warn") else blockers
        target.append({"code": str(item["code"]), "reason": str(item["reason"])})
    safe = SAFE_DEFAULT if clashes else None
    if clashes:
        reason = "The brief contradicts itself. " + " ".join(clashes) + " " + SAFE_DEFAULT
        item = {"code": "brief-contradiction", "reason": reason}
        if acknowledged_contradiction:
            notes.append(item)
        else:
            blockers.append(item)
    simulation: dict[str, Any] = {"noticed": noticed}
    if noticed:
        reason = (
            "The brief names simulation events. Notice only. "
            "Do not invent a simulation the materials do not contain."
        )
        simulation["reason"] = reason
        item = {"code": "simulation-events", "reason": reason}
        if acknowledged_simulation:
            notes.append(item)
        else:
            blockers.append(item)
    if word_clash:
        notes.append({"code": "brief-word-clash", "reason": word_clash})
    blockers.extend(invented_simulation(sections, brief, gathered or []))
    return {
        "section_budgets": rows,
        "brief_contradictions": clashes,
        "safe_default": safe,
        "simulation_events": simulation,
        "blockers": blockers,
        "notes": notes,
    }
