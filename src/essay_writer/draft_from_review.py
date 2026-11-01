"""First draft is authored from stage 4b critical-review markdowns.

One markdown per paper. A source paper is re-opened only for a gap that
markdown does not cover. A quotation must be an exact span of the markdown,
or of the re-opened passage. This module does not write Word and does not
confirm. invent-forbid still applies when the quotation is in neither text.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer.assignment_gate import mark_scheme_text, question_is_answered
from essay_writer.paths import work_dir

CRITICAL_REVIEW = "critical-review"
INVENT = "invent-forbid"
ARGUMENT = "argument"

_CITE = re.compile(r"\([^)]*\d{4}[^)]*\)")
_SECTION_HEAD = re.compile(r"(?im)^\s*(?:#{1,3}\s*)?(?:section titles|sections)\s*:?\s*$")
_SECTION_ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
_SECTION_NAMED = re.compile(r"(?im)^\s*section\s*:\s*(.+?)\s*$")
_MD_HEAD = re.compile(r"(?m)^#{1,3}\s+(.+?)\s*$")
_NOTE_LABEL = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:aim|aims|method|methods|methodology|scope|"
    r"limitations?|findings|critical review|"
    r"what (?:the text|it) adds|what (?:the text|it) leaves out)\s*:"
)
_PAPER_HEAD = re.compile(
    r"(?im)^\s*(?:#{1,3}\s*)?(?:paper\s+\d+\b|critical review\s*(?:of\b|:))"
)
_CITE_HEAD = re.compile(
    r"(?m)^\s*(?:#{1,3}\s*)?[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+)?\s+\(\d{4}\)\s*$"
)


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _issue(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "reason": reason}


def reviews_by_paper(
    reviews: object,
) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    """One non-empty markdown per paper id. A second markdown is refused."""
    if not isinstance(reviews, list) or not reviews:
        return None, [
            _issue(CRITICAL_REVIEW, "4b needs one critical-review markdown per paper.")
        ]
    found: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for index, item in enumerate(reviews):
        label = f"critical_reviews[{index}]"
        if not isinstance(item, dict):
            issues.append(_issue(CRITICAL_REVIEW, f"{label} must be one paper and its markdown."))
            continue
        paper_id = _text(item.get("paper_id"))
        markdown = item.get("markdown")
        if paper_id is None:
            issues.append(_issue(CRITICAL_REVIEW, f"{label} needs a paper id."))
            continue
        if paper_id in found:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"4b keeps one markdown per paper. {paper_id} has more than one.",
                )
            )
            continue
        if not isinstance(markdown, str) or not markdown.strip():
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{label} needs the critical-review markdown for {paper_id}.",
                )
            )
            continue
        found[paper_id] = markdown
    if issues:
        return None, issues
    return found, []


def _reopens(
    reopens: object,
    by_paper: dict[str, str],
    issues: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    if reopens is None:
        return {}
    if not isinstance(reopens, list):
        issues.append(
            _issue(
                CRITICAL_REVIEW,
                "reopen must list gaps the critical-review markdowns do not cover.",
            )
        )
        return {}
    found: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(reopens):
        label = f"reopen[{index}]"
        if not isinstance(item, dict):
            issues.append(
                _issue(CRITICAL_REVIEW, f"{label} must name the paper, the gap, and the passage.")
            )
            continue
        paper_id = _text(item.get("paper_id"))
        gap = _text(item.get("gap"))
        passage = item.get("passage")
        if paper_id is None:
            issues.append(_issue(CRITICAL_REVIEW, f"{label} needs a paper id."))
            continue
        markdown = by_paper.get(paper_id)
        if markdown is None:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{paper_id} has no critical-review markdown to leave a gap in.",
                )
            )
            continue
        if gap is None:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{label} needs the gap the critical-review markdown does not cover.",
                )
            )
            continue
        if gap in markdown:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{paper_id} gap is already in the critical-review markdown. "
                    "Do not re-open the source paper.",
                )
            )
            continue
        if (paper_id, gap) in seen:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{paper_id} already names that gap.",
                )
            )
            continue
        if not isinstance(passage, str) or not passage.strip():
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"{label} needs the passage from the source paper that covers the gap.",
                )
            )
            continue
        seen.add((paper_id, gap))
        found.setdefault(paper_id, []).append({"gap": gap, "passage": passage})
    return found


def first_draft_blockers(
    sources: list[dict[str, Any]],
    reviews: object,
    reopens: object = None,
) -> list[dict[str, str]]:
    """Blockers for a first draft authored from 4b markdowns.

    sources use id and quote, the same fields a gathered source already has.
    """
    by_paper, issues = reviews_by_paper(reviews)
    if by_paper is None:
        return issues
    opened = _reopens(reopens, by_paper, issues)
    for source in sources:
        if not isinstance(source, dict):
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    "Each gathered paper needs an id and one critical-review markdown.",
                )
            )
            continue
        paper_id = _text(source.get("id"))
        if paper_id is None:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    "Each gathered paper needs an id and one critical-review markdown.",
                )
            )
            continue
        markdown = by_paper.get(paper_id)
        if markdown is None:
            issues.append(
                _issue(
                    CRITICAL_REVIEW,
                    f"First draft needs one critical-review markdown for {paper_id}. "
                    "Write that draft from the markdown.",
                )
            )
            continue
        quote = source.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            continue
        quote = quote.strip()
        if quote in markdown:
            continue
        passages = opened.get(paper_id, [])
        if any(quote in item["passage"] for item in passages):
            continue
        if passages:
            issues.append(
                _issue(
                    INVENT,
                    f"{paper_id} quote is not in the critical-review markdown or the re-opened passage. "
                    "Do not invent it.",
                )
            )
            continue
        issues.append(
            _issue(
                CRITICAL_REVIEW,
                f"{paper_id} quote is not in its critical-review markdown. "
                "Re-open the source paper only when that markdown does not cover the gap.",
            )
        )
    return issues


def _authored_rows(
    sources: list[dict[str, Any]],
    by_paper: dict[str, str],
    opened: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        paper_id = _text(source.get("id")) if isinstance(source, dict) else None
        quote = source.get("quote") if isinstance(source, dict) else None
        if paper_id is None or not isinstance(quote, str) or not quote.strip():
            continue
        quote = quote.strip()
        markdown = by_paper.get(paper_id, "")
        if quote in markdown:
            rows.append({"paper_id": paper_id, "quote": quote, "from": "critical-review"})
            continue
        for item in opened.get(paper_id, []):
            if quote in item["passage"]:
                rows.append(
                    {
                        "paper_id": paper_id,
                        "quote": quote,
                        "from": "reopen",
                        "gap": item["gap"],
                    }
                )
                break
    return rows


def scheme_section_titles(text: str) -> list[str]:
    """Section titles the mark scheme lists. An unlisted scheme adds none."""
    if not isinstance(text, str) or not text.strip():
        return []
    named = [item.strip() for item in _SECTION_NAMED.findall(text) if item.strip()]
    if named:
        return named
    titles: list[str] = []
    capture = False
    for line in text.splitlines():
        if _SECTION_HEAD.match(line.strip()):
            capture = True
            continue
        if not capture:
            continue
        if not line.strip():
            if titles:
                break
            continue
        item = _SECTION_ITEM.match(line)
        if item:
            titles.append(item.group(1).strip())
            continue
        break
    return titles


def _plain_prose(text: str) -> str:
    stripped = _CITE.sub(" ", text)
    return re.sub(r"\s+", " ", stripped).strip().casefold()


def notes_shaped(text: str) -> bool:
    """True when the text is critical-review notes or a stack of paper digests.

    A short quotation inside an argument is not this shape. Labeled note
    fields, repeated paper heads, or bare author-year heads are.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    labels = {
        re.sub(r"\s+", " ", match.group(0).split(":", 1)[0]).strip().casefold()
        for match in _NOTE_LABEL.finditer(text)
    }
    if len(labels) >= 3:
        return True
    if len(_PAPER_HEAD.findall(text)) >= 2:
        return True
    return len(_CITE_HEAD.findall(text)) >= 2


_TOKEN = re.compile(r"[a-z0-9']+")
_NGRAM = 5


def _tokens(prose: str) -> list[str]:
    return _TOKEN.findall(prose)


def _ngrams(tokens: list[str], size: int = _NGRAM) -> set[tuple[str, ...]]:
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def _copy_overlap(body: str, note: str) -> float:
    """Share of the body's five-word runs that also run through the note."""
    body_tokens = _tokens(body)
    note_tokens = _tokens(note)
    body_grams = _ngrams(body_tokens)
    if not body_grams:
        return 0.0
    return len(body_grams & _ngrams(note_tokens)) / len(body_grams)


def _retells_one_paper(body: str, by_paper: dict[str, str]) -> str | None:
    """The paper id when this section is that paper's 4b note, not an argument.

    A short quotation that also appears in the note is evidence. It is not a
    retell. A light rewrite of the note keeps most of its five-word runs, so the
    same check refuses it. A developed argument is longer than the note and is
    left alone.
    """
    prose = _plain_prose(body)
    if len(prose) < 80:
        return None
    body_len = len(_tokens(prose))
    for paper_id, markdown in by_paper.items():
        note = _plain_prose(markdown)
        if len(note) < 80:
            continue
        if note in prose:
            return paper_id
        if prose in note and len(prose) >= int(len(note) * 0.8):
            return paper_id
        note_len = len(_tokens(note))
        if not note_len or not body_len:
            continue
        if body_len > int(note_len * 1.6):
            continue
        if _copy_overlap(prose, note) >= 0.5:
            return paper_id
    return None


def argument_blockers(
    essay_id: str,
    sections: list[dict[str, Any]],
    reviews: object,
) -> list[dict[str, str]]:
    """Stage 5 is the report or essay. A one-paper retell is not that draft.

    4b markdowns stay source material. Headings follow mark-scheme section titles
    when the scheme lists them. This does not treat one module as the only report.
    """

    issues: list[dict[str, str]] = []
    titles = scheme_section_titles(mark_scheme_text(essay_id))
    if titles:
        headings: list[str] = []
        for section in sections:
            if isinstance(section, dict):
                raw_heading = section.get("heading")
                headings.append(raw_heading.strip() if isinstance(raw_heading, str) else "")
            else:
                headings.append("")
        if [item.casefold() for item in headings] != [item.casefold() for item in titles]:
            issues.append(
                _issue(
                    ARGUMENT,
                    "Headings are the mark-scheme section titles. "
                    "The draft is the report or essay those titles name.",
                )
            )
    by_paper, _shape = reviews_by_paper(reviews)
    question = essay_assignment_gate.read_assignment(essay_id).get("question") or ""
    if not isinstance(question, str):
        question = ""
    asked = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        raw_body = section.get("body")
        body = raw_body if isinstance(raw_body, str) else ""
        raw_heading_value = section.get("heading")
        raw_heading = raw_heading_value if isinstance(raw_heading_value, str) else ""
        heading = raw_heading.strip() or "This draft"
        if isinstance(by_paper, dict):
            paper_id = _retells_one_paper(body, by_paper)
            if paper_id:
                asked = True
                if question_is_answered(body, question):
                    reason = (
                        f"{heading} pastes the note for {paper_id} as the draft. "
                        "Stage 5 is the report or essay argument. The 4b notes stay source material."
                    )
                else:
                    reason = (
                        f"{heading} only retells {paper_id} and does not answer the assignment question. "
                        "Stage 5 is the report or essay argument. The 4b notes stay source material."
                    )
                issues.append(_issue(ARGUMENT, reason))
                continue
        if notes_shaped(body) or notes_shaped(f"{heading}\n{body}"):
            asked = True
            issues.append(
                _issue(
                    ARGUMENT,
                    f"{heading} is critical-review notes, not the report or essay argument. "
                    "Stage 5 answers the assignment. The 4b notes stay source material.",
                )
            )
    if not asked and notes_shaped(
        "\n".join(
            f"{section.get('heading', '')}\n{section.get('body', '')}"
            for section in sections
            if isinstance(section, dict)
        )
    ):
        issues.append(
            _issue(
                ARGUMENT,
                "This draft is critical-review notes, not the report or essay argument. "
                "Stage 5 answers the assignment. The 4b notes stay source material.",
            )
        )
    return issues


def look_sections(text: str) -> list[dict[str, str]]:
    """Markdown headings become sections. Prose stays one section."""
    if not isinstance(text, str):
        return [{"heading": "", "body": ""}]
    matches = list(_MD_HEAD.finditer(text))
    if not matches:
        return [{"heading": "", "body": text}]
    sections: list[dict[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append({"heading": "", "body": preamble})
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append({"heading": match.group(1).strip(), "body": text[start:end].strip()})
    return sections


def stored_critical_reviews(essay_id: str) -> list[dict[str, str]]:
    """4b markdowns already on this sequence. Missing notes are not invented."""

    folder = work_dir(essay_id) / "output" / "reviews"
    if not folder.is_dir():
        return []
    rows: list[dict[str, str]] = []
    for path in sorted(folder.glob("*.md")):
        try:
            markdown = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if markdown.strip():
            rows.append({"paper_id": path.stem, "markdown": markdown})
    return rows


def stage5_draft_blockers(essay_id: str, look: str) -> list[dict[str, str]]:
    """Stage 5 look against argument_blockers. Notes pasted as the draft fail."""
    reviews = stored_critical_reviews(essay_id)
    return argument_blockers(essay_id, look_sections(look), reviews or None)


def author_from_reviews(
    reviews: object,
    quotes: object,
    reopens: object = None,
) -> dict[str, object]:
    """Check a first draft against 4b markdowns. Writes nothing."""
    if quotes is None:
        quote_rows: list[object] = []
    elif not isinstance(quotes, list):
        return {
            "ok": False,
            "wrote": False,
            "stored": False,
            "issues": [_issue(INVENT, "quotes must be a list of paper id and quote.")],
            "sources": [],
        }
    else:
        quote_rows = list(quotes)
    sources = [
        {
            "id": item.get("paper_id") if isinstance(item, dict) else None,
            "quote": item.get("quote") if isinstance(item, dict) else None,
        }
        for item in quote_rows
    ]
    issues = first_draft_blockers(sources, reviews, reopens)
    by_paper, _shape = reviews_by_paper(reviews)
    authored: list[dict[str, Any]] = []
    if by_paper is not None:
        opened = _reopens(reopens, by_paper, [])
        authored = _authored_rows(sources, by_paper, opened)
    return {
        "ok": not issues,
        "wrote": False,
        "stored": False,
        "issues": issues,
        "sources": authored,
    }
