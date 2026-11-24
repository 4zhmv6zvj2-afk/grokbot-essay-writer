"""How many distinct works the essay itself cites.

The citation list may be long. The essay cites works that bear on the
confirmed question and the saved plan. A work is not added only because
it is on the list.

When the assignment states no source count, the essay cites at least
ceil(words / 1000 * 8) distinct works. A count stated on the assignment
is that minimum, and it is not added to the word rate. The essay cites
at most 12 distinct works per 1,000 words. A stated count above that
cap is the cap as well: the stated number wins, and the rate is not
combined with it.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer.textutil import citation_tokens, fold_name

_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "which",
        "who",
        "with",
    }
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def essay_cite_bounds(essay_id: str) -> dict[str, Any]:
    """Minimum and maximum distinct works for the essay, not the citation list.

    A stated count is the minimum. When it is above the rate cap, it is also
    the maximum. The rate is not added to the stated number.
    """
    from essay_writer.source_floor import assignment_floor, cap_for_words

    floor = assignment_floor(essay_id)
    raw_floor = floor.get("floor")
    minimum = raw_floor if isinstance(raw_floor, int) and not isinstance(raw_floor, bool) else 0
    words = floor.get("words")
    counted = words if isinstance(words, int) and not isinstance(words, bool) else None
    maximum = cap_for_words(counted)
    if maximum is not None and minimum > maximum:
        maximum = minimum
    return {
        "minimum": minimum,
        "maximum": maximum,
        "words": counted,
        "from": floor.get("floor_from") or "",
    }


def _plan(essay_id: str) -> str:
    from essay_writer.stage_note import _note_look

    look = _note_look(essay_id, "3")
    return look.strip() if isinstance(look, str) else ""


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(text: str) -> set[str]:
    found: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", text.casefold()):
        if len(word) < 4 or word in _STOP:
            continue
        found.add(_stem(word))
    return found


def work_is_relevant(work: dict[str, Any], question: str, plan: str) -> bool:
    """True when the title bears on both the question and the plan.

    Being on the citation list is not relevance.
    """
    title = work.get("title")
    if not isinstance(title, str) or not title.strip():
        return False
    if not question.strip() or not plan.strip():
        return False
    title_words = _words(title)
    if not title_words:
        return False
    return bool(title_words & _words(question)) and bool(title_words & _words(plan))


def _inner(source: dict[str, Any]) -> str:
    stored = source.get("in_text")
    if not isinstance(stored, str):
        return ""
    text = stored.strip()
    if text.startswith("(") and text.endswith(")"):
        return text[1:-1].strip()
    return text


def _id_match(token: str, source: dict[str, Any]) -> bool:
    ident = source.get("id")
    if not isinstance(ident, str) or not ident.strip():
        return False
    return fold_name(token).casefold() == fold_name(ident).casefold()


def _short_match(token: str, source: dict[str, Any]) -> bool:
    from essay_writer.textutil import in_text_forms, token_allowed

    inner = _inner(source)
    if inner and fold_name(inner).casefold() == fold_name(token).casefold():
        return True
    author = source.get("author")
    year = source.get("year")
    if not isinstance(author, str) or not author.strip() or year is None or year == "":
        return False
    return token_allowed(token, in_text_forms(author, str(year)))


def works_for_token(token: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Works named by this token.

    A source id names that work. A short form names a work only when one
    stored work uses it. A shared short form does not choose one work.
    """
    by_id = [source for source in sources if _id_match(token, source)]
    if by_id:
        return by_id[:1] if len(by_id) == 1 else []
    short = [source for source in sources if _short_match(token, source)]
    if len(short) == 1:
        return short
    return []


def cited_source_ids(text: str, sources: list[dict[str, Any]]) -> list[str]:
    """Distinct source ids the essay text cites. The list length is not a count."""
    found: list[str] = []
    seen: set[str] = set()
    for token in citation_tokens(text):
        hits = works_for_token(token, sources)
        if len(hits) != 1:
            continue
        ident = hits[0].get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            continue
        seen.add(ident)
        found.append(ident)
    return found


def _attach(text: str, citation: str) -> str:
    shown = citation.strip()
    if not shown:
        return text
    if not (shown.startswith("(") and shown.endswith(")")):
        shown = f"({shown})"
    if shown.casefold() in text.casefold():
        return text
    parts = _SENTENCE.split(text.strip())
    if not parts:
        return text
    sentence = parts[0]
    stripped = sentence.rstrip()
    if stripped.endswith((".", "!", "?")):
        parts[0] = f"{stripped[:-1].rstrip()} {shown}{stripped[-1]}"
    else:
        parts[0] = f"{stripped} {shown}."
    return " ".join(parts)


def _shared_short_form(source: dict[str, Any], sources: list[dict[str, Any]]) -> bool:
    inner = _inner(source)
    if not inner:
        return False
    matches = [item for item in sources if _short_match(inner, item)]
    return len(matches) != 1


def fit_essay_cites(essay_id: str, text: Any) -> Any:
    """Cite enough relevant works in the essay, and not more than the cap.

    The citation list is left as it is. Nothing is added for a work that
    does not bear on the question and the plan. A missing question or a
    missing plan leaves the essay text unchanged.
    """
    from essay_writer.model_contract import StripReport

    if isinstance(text, StripReport):
        gap = text.subject_gap
        text = text.text
    elif not isinstance(text, str) or not text.strip():
        return text if isinstance(text, str) else ""
    else:
        gap = False
    from essay_writer.citation_list import list_written, usable_sources
    from essay_writer.cite_fit import carry_subject_gap
    from essay_writer.source_floor import confirmed_question

    def finish(value: str) -> Any:
        return carry_subject_gap(value, gap)

    if not list_written(essay_id):
        return finish(text)
    sources = [row for row in (usable_sources(essay_id) or []) if isinstance(row, dict)]
    if not sources:
        return finish(text)
    question = confirmed_question(essay_id)
    plan = _plan(essay_id)
    if not question or not plan:
        return finish(text)
    bounds = essay_cite_bounds(essay_id)
    minimum = int(bounds["minimum"])
    maximum = bounds["maximum"]
    if not isinstance(maximum, int):
        maximum = None
    relevant = [source for source in sources if work_is_relevant(source, question, plan)]
    relevant.sort(key=lambda source: str(source.get("id") or ""))
    by_id = {str(source.get("id")): source for source in sources if source.get("id")}

    def cited() -> list[str]:
        return cited_source_ids(text, sources)

    current = cited()
    if maximum is not None and len(current) > maximum:
        # Drop works that are not relevant first, then later ids. The essay
        # is not taken below its minimum.
        relevant_ids = {str(item.get("id")) for item in relevant}
        irrelevant = sorted(ident for ident in current if ident not in relevant_ids)
        keepers = sorted(ident for ident in current if ident in relevant_ids)
        ordered = irrelevant + list(reversed(keepers))
        for ident in ordered:
            if len(cited()) <= maximum:
                break
            if len(cited()) <= minimum:
                break
            source = by_id.get(ident)
            if source is None or _shared_short_form(source, sources):
                continue
            inner = _inner(source)
            if not inner:
                continue
            from essay_writer.cite_fit import strip_token

            text = strip_token(text, inner)
            if isinstance(text, StripReport):
                gap = gap or text.subject_gap
                text = text.text
    current = cited()
    if len(current) >= minimum:
        return finish(text)
    have = set(current)
    for source in relevant:
        if len(have) >= minimum:
            break
        if maximum is not None and len(have) >= maximum:
            break
        ident = str(source.get("id") or "")
        if not ident or ident in have or _shared_short_form(source, sources):
            continue
        citation = source.get("in_text")
        if not isinstance(citation, str) or not citation.strip():
            continue
        updated = _attach(text, citation)
        if updated == text:
            continue
        text = updated
        have.add(ident)
    return finish(text)
