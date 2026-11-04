"""Rewrite and EQR length pressure against the opened Word file.

A word band the mark scheme or brief states still fails a draft that sits
outside it. A tighter ceiling the writer or a studied default invented does
not fail a draft that is only longer than that ceiling when the opened Word
file already exceeds it. An invented per-section split is the same kind of
pressure. No opened file leaves the existing word-band and brief gates as
they are.

Cursor and Grok Build call this function through their office modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeGuard

from essay_writer.diary import section_plan_for

# Mid-office parity for this slice. Ready quotes this line.
BUILD_COVERED_LINE = "Build covered"

_REFERENCES = frozenset({"references", "reference list", "bibliography"})


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def band_edges(rules: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Low and high for a word-band dict. A missing pair is no band."""
    if not isinstance(rules, dict):
        return None, None
    low = rules.get("min")
    high = rules.get("max")
    if _is_int(low) and _is_int(high):
        return low, high
    limit = rules.get("limit")
    tolerance = rules.get("tolerance")
    if (
        _is_int(limit)
        and isinstance(tolerance, (int, float))
        and not isinstance(tolerance, bool)
        and limit > 0
    ):
        span = float(tolerance)
        return round(limit * (1 - span)), round(limit * (1 + span))
    return None, None


def _count(text: str, *, counter: str, exclude_citations: bool) -> int:
    if counter == "words":
        from essay_writer.textutil import count_words

        return count_words(text, exclude_citations=exclude_citations)
    return len(text.split())


def _key(value: str) -> str:
    return " ".join(value.split()).casefold()


def stricter_invented_max(
    essay_id: str,
    rules: dict[str, Any] | None,
    *,
    high: int | None = None,
) -> int | None:
    """Applied max when it is tighter than the document band, or invented with no document band.

    The document band is the mark scheme, then the brief. That ceiling is not
    invented. A lower max from a pack rule or a studied default is.
    """
    from essay_writer.specialists.writer import document_word_band

    _low, edges_high = band_edges(rules)
    applied = high if _is_int(high) else edges_high
    if applied is None:
        return None
    _doc_low, doc_high = band_edges(document_word_band(essay_id))
    if doc_high is None:
        return applied
    if applied < doc_high:
        return applied
    return None


def _baseline_path(essay_id: str) -> Path | None:
    from essay_writer.user_place import finished_word_copies

    try:
        copies = finished_word_copies(essay_id)
    except (OSError, ValueError):
        return None
    student = next((item for item in copies if item.get("role") == "student"), None)
    chosen = student or (copies[0] if copies else None)
    if not isinstance(chosen, dict):
        return None
    path = chosen.get("path")
    if not isinstance(path, Path) or not path.is_file():
        return None
    return path


def _known_headings(essay_id: str, sections: list[dict[str, Any]] | None) -> set[str]:
    names: set[str] = set()
    for section in sections or []:
        if isinstance(section, dict):
            heading = section.get("heading") or section.get("name")
            if isinstance(heading, str) and heading.strip():
                names.add(_key(heading))
    try:
        from essay_writer.diary import section_plan_for

        plan = section_plan_for(essay_id)
    except (OSError, ValueError):
        return names
    if isinstance(plan, dict):
        for row in plan.get("sections") or []:
            if isinstance(row, dict) and isinstance(row.get("name"), str):
                names.add(_key(row["name"]))
    return names


def _read_opened(
    essay_id: str,
    sections: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Student Word file on disk. None when that file is not opened."""
    path = _baseline_path(essay_id)
    if path is None:
        return None
    from zipfile import BadZipFile

    from docx.opc.exceptions import PackageNotFoundError

    try:
        from docx import Document

        document = Document(str(path))
    except (OSError, ValueError, KeyError, BadZipFile, PackageNotFoundError):
        return None
    known = _known_headings(essay_id, sections)
    chunks: list[str] = []
    heading = ""
    parsed: list[dict[str, str]] = []
    body_lines: list[str] = []

    def flush() -> None:
        parsed.append({"heading": heading, "body": "\n".join(chunks)})

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = ""
        style_obj = paragraph.style
        if style_obj is not None and isinstance(style_obj.name, str):
            style = style_obj.name
        if text.casefold() in _REFERENCES:
            break
        is_heading = style.casefold().startswith("heading") or _key(text) in known
        if is_heading:
            flush()
            chunks = []
            heading = text
            body_lines.append(text)
            continue
        chunks.append(text)
        body_lines.append(text)
    flush()
    return {"text": "\n".join(body_lines), "sections": parsed}


def _draft_counts(
    sections: list[dict[str, Any]] | None,
    *,
    counter: str,
    exclude_citations: bool,
) -> dict[str, int]:
    found: dict[str, int] = {}
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading") or section.get("name")
        if not isinstance(heading, str) or not heading.strip():
            continue
        counted = section.get("counted")
        if _is_int(counted):
            found[_key(heading)] = counted
            continue
        body = section.get("body")
        if isinstance(body, str):
            found[_key(heading)] = _count(body, counter=counter, exclude_citations=exclude_citations)
    return found


def _baseline_counts(
    parsed: list[dict[str, str]],
    *,
    counter: str,
    exclude_citations: bool,
) -> dict[str, int]:
    found: dict[str, int] = {}
    for section in parsed:
        key = _key(section.get("heading") or "")
        if not key:
            continue
        found[key] = found.get(key, 0) + _count(
            section.get("body") or "",
            counter=counter,
            exclude_citations=exclude_citations,
        )
    return found


def waived_invented_sections(
    essay_id: str,
    sections: list[dict[str, Any]] | None,
    baseline_sections: list[dict[str, str]] | None,
    *,
    counter: str,
    exclude_citations: bool,
) -> list[str]:
    """Invented per-section caps the opened Word section already exceeds.

    A length the brief stated for that section is not waived. No opened file
    waives nothing, and it does not add a new section-budget fail.
    """
    if not baseline_sections:
        return []

    plan = section_plan_for(essay_id)
    if not isinstance(plan, dict):
        return []
    draft = _draft_counts(sections, counter=counter, exclude_citations=exclude_citations)
    baseline = _baseline_counts(baseline_sections, counter=counter, exclude_citations=exclude_citations)
    waived: list[str] = []
    for row in plan.get("sections") or []:
        if not isinstance(row, dict) or row.get("from_brief") is not False:
            continue
        high = row.get("max")
        name = row.get("name")
        if not _is_int(high) or not isinstance(name, str) or not name.strip():
            continue
        key = _key(name)
        draft_count = draft.get(key)
        base_count = baseline.get(key)
        if draft_count is None or base_count is None:
            continue
        if draft_count > high and base_count > high:
            waived.append(name.strip())
    return waived


def rewrite_vs_opened_word(
    essay_id: str,
    draft: str = "",
    band: dict[str, Any] | None = None,
    *,
    sections: list[dict[str, Any]] | None = None,
    counted: int | None = None,
    high: int | None = None,
    counter: str = "split",
    exclude_citations: bool = False,
) -> dict[str, Any]:
    """Whether rewrite or EQR may fail this draft for invented length pressure.

    waive_word is true only when the draft is over an invented max and the
    opened Word file is already over that same max. A stated document band
    that the draft still misses stays a fail (document_still_fails).
    """
    rules = band if isinstance(band, dict) else {}
    if not exclude_citations:
        exclude_citations = bool(rules.get("exclude_in_text_citations"))
    draft_words = (
        counted
        if _is_int(counted)
        else _count(draft or "", counter=counter, exclude_citations=exclude_citations)
    )
    applied_high = high if _is_int(high) else band_edges(rules)[1]
    invented_high = stricter_invented_max(
        essay_id,
        rules,
        high=applied_high if _is_int(applied_high) else None,
    )
    opened = _read_opened(essay_id, sections)
    baseline_words: int | None = None
    if opened is not None:
        baseline_words = _count(opened["text"], counter=counter, exclude_citations=exclude_citations)
    waive_word = False
    if invented_high is not None and baseline_words is not None:
        waive_word = draft_words > invented_high and baseline_words > invented_high
    doc_low, doc_high = band_edges(_document_band(essay_id))
    document_still_fails = False
    document_reason = ""
    if waive_word and doc_low is not None and doc_high is not None:
        if draft_words < doc_low or draft_words > doc_high:
            document_still_fails = True
            document_reason = (
                f"The body is outside the word band ({draft_words} counted, {doc_low}–{doc_high})."
            )
    reason = ""
    if waive_word and not document_still_fails:
        reason = "The opened Word file already exceeds this invented band."
    waived = waived_invented_sections(
        essay_id,
        sections,
        None if opened is None else opened["sections"],
        counter=counter,
        exclude_citations=exclude_citations,
    )
    return {
        "baseline": opened is not None,
        "invented": invented_high is not None,
        "waive_word": waive_word,
        "document_still_fails": document_still_fails,
        "reason": reason,
        "document_reason": document_reason,
        "waived_sections": waived,
        "applied_high": applied_high if _is_int(applied_high) else invented_high,
        "baseline_words": baseline_words,
        "draft_words": draft_words,
    }


def _document_band(essay_id: str) -> dict[str, Any]:
    from essay_writer.specialists.writer import document_word_band

    band = document_word_band(essay_id)
    return band if isinstance(band, dict) else {}
