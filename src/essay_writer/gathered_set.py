"""One gate for every writing type that gathers sources.

Same opened text, or the same DOI, is one work. A later file is not a
second paper and does not get a second annotation. Annotation paragraphs
on the kept set must differ. Each kept source is tied to an entry name
when the assignment record has entry names, and otherwise to the
assignment ask.

Stage 4a and stage 4b both enter through research prepare, so the set
that is stored is the set this gate kept.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer.assignment_gate import ask_content_words, ask_word_in_text

_SPACE = re.compile(r"\s+")
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)

CODE = "gathered-set"


def _flat(text: str) -> str:
    return _SPACE.sub(" ", text.casefold()).strip()


def _doi(source: dict[str, Any]) -> str | None:
    raw = source.get("doi")
    if not isinstance(raw, str) or not raw.strip():
        return None
    token = _DOI_PREFIX.sub("", raw.strip()).casefold()
    return token or None


def collapse_same_work(
    sources: list[dict[str, Any]],
    texts: dict[str, str],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Keep the first file when a later file is the same work."""
    kept: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    seen_doi: set[str] = set()
    dropped: set[str] = set()
    for source in sources:
        locator = source.get("locator")
        raw_text = texts.get(locator, "") if isinstance(locator, str) else ""
        text_key = _flat(raw_text)
        doi = _doi(source)
        if (text_key and text_key in seen_text) or (doi and doi in seen_doi):
            ident = source.get("id")
            if isinstance(ident, str) and ident.strip():
                dropped.add(ident.strip())
            continue
        if text_key:
            seen_text.add(text_key)
        if doi:
            seen_doi.add(doi)
        kept.append(source)
    return kept, dropped


def _entry_names(record: dict[str, Any]) -> list[str]:
    """Entry names only. A report's named sections are headings, not entries."""
    if record.get("named_parts_source") == "report":
        return []
    names: list[str] = []
    for name in record.get("named_entries") or []:
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def _annotation_issues(notes: dict[str, str]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for source_id, note in notes.items():
        if not isinstance(note, str):
            continue
        key = _flat(note)
        if not key:
            continue
        prior = seen.get(key)
        if prior is None:
            seen[key] = source_id
            continue
        issues.append(
            {
                "code": CODE,
                "reason": (
                    f"{prior} and {source_id} use the same annotation paragraph. "
                    "Each kept source needs its own."
                ),
            }
        )
    return issues


def _tie_issues(
    essay_id: str,
    sources: list[dict[str, Any]],
    texts: dict[str, str],
) -> list[dict[str, str]]:

    record = essay_assignment_gate.read_assignment(essay_id)
    if record.get("active") is not True:
        return []
    names = _entry_names(record)
    question = record.get("question")
    ask = question.strip() if isinstance(question, str) and question.strip() else ""
    if names:
        target = "entry"
    elif ask and ask_content_words(ask):
        target = "ask"
    else:
        return []
    issues: list[dict[str, str]] = []
    for source in sources:
        locator = source.get("locator")
        text = texts.get(locator, "") if isinstance(locator, str) else ""
        label = str(source.get("id") or "source")
        if target == "entry":
            match = next((name for name in names if _flat(name) in _flat(text)), None)
            if match is None:
                issues.append(
                    {
                        "code": CODE,
                        "reason": f"{label} is not tied to an entry this assignment names.",
                    }
                )
                continue
            source["tied_to"] = match
            continue
        if not ask_word_in_text(text, ask):
            issues.append(
                {
                    "code": CODE,
                    "reason": f"{label} is not tied to the assignment ask.",
                }
            )
            continue
        source["tied_to"] = ask
    return issues


def gathered_set_issues(
    essay_id: str,
    sources: list[dict[str, Any]],
    texts: dict[str, str],
    notes: dict[str, str],
) -> list[dict[str, str]]:
    """Refuse a shared annotation paragraph or a source with nothing to tie to."""
    issues = _annotation_issues(notes)
    issues.extend(_tie_issues(essay_id, sources, texts))
    return issues
