"""Word References: pack markdown and gathered sources."""

from __future__ import annotations

import re

from essay_writer.confirm import refuse
from essay_writer.textutil import citation_tokens, reference_line, reference_parts

PACK_REFERENCES_MARKDOWN = "references_markdown"
_CITE_TOKEN = re.compile(r"(.+),\s*(\d{4}[a-z]?)\Z", re.IGNORECASE)
_ET_AL = re.compile(r"\s+et al\.?\Z", re.IGNORECASE)


def references_markdown_lines(pack: dict[str, object]) -> list[str]:
    raw = pack.get(PACK_REFERENCES_MARKDOWN)
    if isinstance(raw, str):
        return [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(raw, list):
        return []
    lines: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            lines.append(item.strip())
    return lines


def source_reference_lines(sources: list[object]) -> list[str]:

    lines: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        line = reference_line(source).strip()
        if line:
            lines.append(line)
    return lines


def reference_lines_origin(pack: dict[str, object]) -> str:
    """Where Word reference lines come from. Logging only; the lines are unchanged.

    saved-path: the pack already has reference text.
    generated-path: lines are built from gathered sources.
    """
    if references_markdown_lines(pack):
        return "saved-path"
    return "generated-path"


_QUOTED_TITLE = re.compile(r"['‘][^'’]+['’],\s+")
_YEAR_THEN_TITLE = re.compile(r"\(\d{4}[a-z]?\)\s+")
_CONTAINER_BREAK = re.compile(r",\s+(?=pp\.|\d|\()", re.IGNORECASE)
_TITLE_MARK = re.compile(r"[.!?]")
_CHAPTER_LEAD = re.compile(r"^in\s+", re.IGNORECASE)
_EDITOR_END = re.compile(r"\(\s*eds?\.?\s*\)\s*", re.IGNORECASE)
_ABBREVIATION_BEFORE = re.compile(
    r"(?:\b[A-Z]|\b(?:pp?|vol|no|fig|ed|eds|edn|Dr|Mr|Mrs|Ms|Prof))$"
)


def _drop_empty(parts: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    return [(text, italic) for text, italic in parts if text]


def _title_break_end(rest: str) -> int:
    """Where a work title ends in a saved line.

    A full stop inside an initial (U.S.) or a short abbreviation does not
    end the title. A question mark or exclamation mark does, and it belongs
    to the title. A dot on the end of a title does not belong to it.
    """
    for match in _TITLE_MARK.finditer(rest):
        index = match.start()
        mark = match.group(0)
        if mark in "!?":
            return index + 1
        before = rest[:index]
        after = rest[index + 1 :]
        if _ABBREVIATION_BEFORE.search(before):
            continue
        if before.endswith(tuple("0123456789")) and after[:1].isdigit():
            continue
        return index
    return -1


def runs_for_saved_reference_line(line: str) -> list[tuple[str, bool]]:
    """Italicise the journal or work title in one saved Harvard line.

    The line text stays as saved. A journal title after the quoted article
    is italic. A book, report, or web title after the year is italic.
    """
    text = line.strip()
    if not text:
        return []
    quoted = _QUOTED_TITLE.search(text)
    if quoted:
        start = quoted.end()
        rest = text[start:]
        if _CHAPTER_LEAD.match(rest):
            editor = _EDITOR_END.search(rest)
            if editor:
                title_start = editor.end()
                end = _title_break_end(rest[title_start:])
                if end > 0:
                    return _drop_empty(
                        [
                            (text[:start], False),
                            (rest[:title_start], False),
                            (rest[title_start : title_start + end], True),
                            (rest[title_start + end :], False),
                        ]
                    )
        break_at = _CONTAINER_BREAK.search(rest)
        # A dot inside an abbreviation (A.I., U.S.) does not end the
        # journal title. The title-end rule reads that dot the same way it
        # reads one in a book or report title.
        end = break_at.start() if break_at else _title_break_end(rest)
        if end < 0:
            end = len(rest)
        journal = rest[:end]
        if journal.strip():
            return _drop_empty(
                [
                    (text[:start], False),
                    (journal, True),
                    (rest[end:], False),
                ]
            )
    year = _YEAR_THEN_TITLE.search(text)
    if year and not text[year.end() :].startswith(("'", "‘")):
        start = year.end()
        rest = text[start:]
        end = _title_break_end(rest)
        if end > 0:
            return _drop_empty(
                [
                    (text[:start], False),
                    (rest[:end], True),
                    (rest[end:], False),
                ]
            )
    return [(text, False)]


def styled_reference_runs(line: str, sources: list[object]) -> list[tuple[str, bool]]:
    """Runs for one reference line.

    A gathered source whose plain line matches is printed from its parts,
    so the journal title stays italic. Any other saved line is marked here.
    """
    cleaned = line.strip()
    if not cleaned:
        return []

    for source in sources:
        if not isinstance(source, dict):
            continue
        parts = [(text, italic) for text, italic in reference_parts(source) if text]
        plain = "".join(text for text, _italic in parts).strip()
        if plain == cleaned:
            return parts
    return runs_for_saved_reference_line(cleaned)


def usable_word_reference_lines(sources: list[object], pack: dict[str, object]) -> list[str]:
    """Lines the Word References section prints.

    Saved references_markdown wins when it has entries. Gathered sources are
    the fallback when that markdown is absent.
    """
    markdown = references_markdown_lines(pack)
    if markdown:
        return markdown
    return source_reference_lines(sources)


def without_withheld_reference_lines(
    essay_id: str,
    lines: list[str],
    kept_sources: list[object],
) -> list[str]:
    """Drop a reference line for a cite the gate withheld or the student rejected.

    A line that also covers a source still kept stays. The record is not
    changed. A rejected surname counts on its own, so a saved reference list
    that a snapshot restore brought back does not print that paper again.
    """
    from essay_writer.cite_fit import load_record, rejected_names

    record = load_record(essay_id)
    withheld = [
        token.strip()
        for token in (record.get("withheld") or [])
        if isinstance(token, str) and token.strip()
    ]
    rejected = rejected_names(record)
    if (not withheld and not rejected) or not lines:
        return lines
    kept_tokens: list[str] = []
    for source in kept_sources:
        if not isinstance(source, dict):
            continue
        author = source.get("author")
        year = source.get("year")
        if author and year is not None and year != "":
            from essay_writer.textutil import family_name

            kept_tokens.append(f"{family_name(str(author))}, {year}")
    kept: list[str] = []
    for line in lines:
        covers_withheld = any(_line_covers_cite(line, token) for token in withheld)
        covers_rejected = any(_line_names_surname(line, name) for name in rejected)
        covers_kept = any(_line_covers_cite(line, token) for token in kept_tokens)
        if (covers_withheld or covers_rejected) and not covers_kept:
            continue
        kept.append(line)
    return kept


_PAGE_AFTER_YEAR = re.compile(
    r"(\d{4}[a-z]?),\s*pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?"
    r"(?:\s*,\s*\d+(?:\s*[-–—]\s*\d+)?)*"
    r"(?=\s*[,;)])"
)


_NARRATIVE_ET_AL = re.compile(
    r"\b([A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+)*)\s+et\s+al\.?\s*"
    r"\(\s*(\d{4}[a-z]?)\s*\)"
)


def _cites_without_pages(body: str) -> str:
    """A page locator is read for the page check, not for the author-year pair."""
    return _PAGE_AFTER_YEAR.sub(r"\1", body)


def _readable_cites(body: str) -> str:
    """`Smith et al. (2020)` in brackets so the author-date pair is read."""
    return _NARRATIVE_ET_AL.sub(r"(\1 et al., \2)", body)


def readable_cite_text(body: str) -> str:
    """Read a page locator or a narrative et al. cite as an author-date pair.

    The stored body is not changed. This copy is for reading a citation.
    """
    return _readable_cites(_cites_without_pages(body))


def _section_bodies(sections: list[object]) -> list[str]:
    bodies: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        body = section.get("body")
        if isinstance(body, str) and body.strip():
            bodies.append(readable_cite_text(body))
    return bodies


def _cite_display(token: str) -> str | None:
    match = _CITE_TOKEN.fullmatch(token.strip())
    if match is None:
        return None
    name = _ET_AL.sub("", match.group(1)).strip()
    year = match.group(2)
    if not name or not year:
        return None
    return f"({name}, {year})"


def _line_names_surname(line: str, surname: str) -> bool:
    """True when the entry's author zone carries this family name.

    A name printed inside the title is not the author of this entry, so the
    check stops at the entry's first bracket.
    """
    needle = _plain_quotes(str(surname)).casefold().strip()
    if not needle:
        return False
    author_zone = _plain_quotes(line).casefold().split("(", 1)[0]
    return re.search(rf"\b{re.escape(needle)}\b", author_zone) is not None


def _line_covers_cite(line: str, token: str) -> bool:
    shown = _cite_display(token)
    if shown is None:
        return True
    inner = shown[1:-1]
    name, _, year = inner.rpartition(", ")
    # The entry has to carry the family name that comes first in the text.
    # A joint cite names more than one author, so the first name is the one
    # before the first comma, not the last word of the whole label.
    first = re.split(r"\s+and\s+|\s*&\s*", name, flags=re.IGNORECASE)[0].strip()
    first = first.split(",")[0].strip()
    surname = first.split()[-1].rstrip(".") if first else ""
    if not surname or not year:
        return True
    if not _line_names_surname(line, surname):
        return False
    folded = _plain_quotes(line).casefold()
    # The year has to sit in brackets straight after that name. A year
    # printed elsewhere in the entry is not this citation's year.
    pattern = (
        rf"\b{re.escape(_plain_quotes(surname).casefold())}\b"
        rf"[^()\n]{{0,200}}\(\s*{re.escape(year.casefold())}\s*[a-z]?\s*\)"
    )
    return re.search(pattern, folded) is not None


def _plain_quotes(text: str) -> str:
    """One apostrophe spelling, for matching a name and not for printing it."""
    return text.replace("’", "'").replace("‘", "'")


def cite_reference_gaps(lines: list[str], sections: list[object]) -> list[str]:
    """In-text citations that the References lines do not cover."""

    missing: list[str] = []
    seen: set[str] = set()
    for body in _section_bodies(sections):
        for token in citation_tokens(body):
            if token in seen:
                continue
            seen.add(token)
            if any(_line_covers_cite(line, token) for line in lines):
                continue
            shown = _cite_display(token)
            if shown:
                missing.append(shown)
    return missing


def empty_references_refusal(
    sources: list[object], pack: dict[str, object]
) -> dict[str, object] | None:
    if usable_word_reference_lines(sources, pack):
        return None

    return refuse(
        "empty-references",
        (
            "The References section has no entries. Add reference lines before "
            "this step can close."
        ),
        wrote=False,
    )


def stage10_reference_block(
    sources: list[object],
    pack: dict[str, object],
    sections: list[object],
) -> dict[str, object] | None:
    """Close gate: no heading-only References, and every in-text cite is listed."""
    lines = usable_word_reference_lines(sources, pack)
    if not lines:
        return empty_references_refusal(sources, pack)
    gaps = cite_reference_gaps(lines, sections)
    if not gaps:
        return None

    shown = ", ".join(gaps[:5])
    return refuse(
        "references-cites",
        (
            "The References list does not include every citation in the text. "
            f"Add a line for {shown} before this step can close."
        ),
        wrote=False,
    )
