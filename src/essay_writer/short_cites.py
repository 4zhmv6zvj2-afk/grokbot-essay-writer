"""Short cites: one or two sentences per cited point, not a mini review.

A student can ask for the citations to be shortened to about one or two
sentences. That ask is remembered on the sequence, so the writer keeps the
same length on the later saves, and a cited point that already runs long is
cut down before the body is stored.

Nothing is invented and no paper is lost. A sentence is only cut when every
paper it cites is already cited in the sentences that stay, so each paper
keeps its place in the body and in the reference list. The sentences that
were cut are reported, so the cut is said out loud rather than made silently.
Quoted text is not cut.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import work_dir

# A verb a student uses for the ask, then the word for the citation itself.
_ASK = re.compile(
    r"(?i)\b(?:shorten|short|trim|tighten|condense|compress|cut down|reduce|keep|limit)\b"
    r"[^.!?\n]{0,80}?\b(?:cites?|citations?|quotes?|quotations?|references?)\b"
)
# The length the ask names. A limit is read only next to that ask.
_LIMIT = re.compile(
    r"(?i)(?:\b(?:1|one)\s*(?:-|–|—|to|or|/)\s*(?:2|two)\b"
    r"|\b(?:1|one|2|two)\s+(?:short\s+)?(?:sentences?|lines?)\b"
    r"|\b(?:at most|no more than|up to|max(?:imum)?(?: of)?)\s+"
    r"(?:1|2|one|two)\s+(?:short\s+)?(?:sentences?|lines?)\b)"
)
_ONE = re.compile(r"(?i)\b(?:1|one|single)\b")
_TWO = re.compile(r"(?i)\b(?:2|two)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_QUOTED = re.compile(r"[\"“”]")
_HEADING = re.compile(r"^\s*#{1,6}\s")
DEFAULT_LIMIT = 2


def _record_path(essay_id: str):

    return work_dir(essay_id) / "short-cites.json"


def _read_record(essay_id: str) -> dict[str, Any]:
    path = _record_path(essay_id)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    limit = data.get("max_sentences")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return {}
    return {"max_sentences": limit, "asked_at": data.get("asked_at")}


def limit_for(essay_id: str) -> int | None:
    """The length the student asked for on this sequence, if there is one."""
    limit = _read_record(essay_id).get("max_sentences")
    return limit if isinstance(limit, int) and limit >= 1 else None


def remember_limit(essay_id: str, limit: int) -> None:
    """Keep the ask for the later stages. A shorter ask wins."""

    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return
    current = limit_for(essay_id)
    if current is not None and current <= limit:
        return
    from datetime import datetime, timezone

    path = _record_path(essay_id)
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    asked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    body = json.dumps(
        {"max_sentences": limit, "asked_at": asked_at}, indent=2, ensure_ascii=False
    ) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(body, encoding="utf-8")
    os.replace(temporary, path)


def parse_limit(text: str | None) -> int | None:
    """The sentence count a student asks for, or None when that ask is absent."""
    if not isinstance(text, str) or not text.strip():
        return None
    if _ASK.search(text) is None:
        return None
    match = _LIMIT.search(text)
    if match is None:
        # "Shorten the cites" with no length named leaves the length to the writer.
        return None
    return 1 if _ONE.search(match.group(0)) and not _TWO.search(match.group(0)) else DEFAULT_LIMIT


def _pairs(sentence: str) -> list[str]:
    from essay_writer.cite_fit import cited_pairs

    return cited_pairs(sentence)


def _empty_report(text: str, limit: int | None) -> dict[str, Any]:
    return {
        "limit": limit,
        "cut": [],
        "sentences_before": 0,
        "sentences_after": 0,
        "applied": False,
        "text": text,
    }


def shorten(text: str, limit: int = DEFAULT_LIMIT) -> tuple[str, dict[str, Any]]:
    """Cut long cited stretches to ``limit`` sentences per cited paper.

    A sentence with no citation is never cut. A quoted sentence is never cut.
    A cited sentence is cut only when every paper it cites is already cited
    in the sentences that stay.
    """
    if not isinstance(text, str) or not text.strip():
        return text, _empty_report(text if isinstance(text, str) else "", limit)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return text, _empty_report(text, limit)
    cut: list[str] = []
    written = 0
    kept_count = 0
    paragraphs: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip() or _HEADING.match(paragraph):
            paragraphs.append(paragraph)
            continue
        sentences = [part for part in _SENTENCE.split(paragraph) if part.strip()]
        written += len(sentences)
        seen: dict[str, int] = {}
        kept: list[str] = []
        for sentence in sentences:
            tokens = _pairs(sentence)
            if not tokens or _QUOTED.search(sentence):
                kept.append(sentence.strip())
                for token in tokens:
                    seen[token] = seen.get(token, 0) + 1
                continue
            if all(seen.get(token, 0) >= limit for token in tokens):
                cut.append(sentence.strip())
                continue
            kept.append(sentence.strip())
            for token in tokens:
                seen[token] = seen.get(token, 0) + 1
        kept_count += len(kept)
        paragraphs.append(" ".join(kept))
    report = {
        "limit": limit,
        "cut": cut,
        "sentences_before": written,
        "sentences_after": kept_count,
        "applied": bool(cut),
    }
    return "\n".join(paragraphs), report


def shorten_sections(sections: list[object], limit: int) -> tuple[list[object], list[str]]:
    """Shorten each body in a pack. A section that does not change is left alone."""
    cleaned: list[object] = []
    cut: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            cleaned.append(section)
            continue
        row = dict(section)
        body = row.get("body")
        if isinstance(body, str) and body.strip():
            shortened, report = shorten(body, limit)
            row["body"] = shortened
            cut.extend(report["cut"])
        cleaned.append(row)
    return cleaned, cut


def apply_short_cite_request(
    essay_id: str,
    text: str,
    *,
    answers: str | None = None,
    edited: str | None = None,
    rewrite: bool = True,
) -> dict[str, Any]:
    """Read a student ask, remember it, and cut long cited stretches.

    ``applied`` is true only when the text changed. ``asked`` is true when
    this call carried the ask, so the front office can say the length back.
    """
    asked = parse_limit(answers) or parse_limit(text)
    if asked is not None:
        remember_limit(essay_id, asked)
    limit = limit_for(essay_id)
    incoming = text if isinstance(text, str) else ""
    edited_text = edited if isinstance(edited, str) else None
    result: dict[str, Any] = {
        "text": incoming,
        "edited": edited,
        "limit": limit,
        "asked": asked is not None,
        "cut": [],
        "applied": False,
    }
    if limit is None or not rewrite:
        return result
    cleaned, report = shorten(incoming, limit)
    cleaned_edited = edited_text
    cut = list(report["cut"])
    if isinstance(edited_text, str):
        cleaned_edited, edited_report = shorten(edited_text, limit)
        cut.extend(edited_report["cut"])
    result["text"] = cleaned
    result["edited"] = cleaned_edited if edited_text is not None else edited
    result["cut"] = cut
    result["applied"] = bool(cut) and (cleaned != incoming or cleaned_edited != edited_text)
    return result


def short_line(limit: int) -> str:
    """The line the front office says when the cite length is set."""
    if limit <= 1:
        return "Each cited point now stays in one sentence."
    if limit == 2:
        return "Each cited point now stays to two sentences."
    return f"Each cited point now stays to {limit} sentences."
