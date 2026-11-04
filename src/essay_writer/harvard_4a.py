"""Harvard Referencing line for a stage 4a annotation.

The citation line below is exact. The paragraph after it is a few full
sentences a student can read aloud. A missing field is omitted. This module
does not invent a page, DOI, volume, journal, place, publisher, or access
date, and it does not read which mid office is doing the file work.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer.cite_open import page_span_printed, page_value_kind, printed_pages_for
from essay_writer.textutil import (
    bare_surname,
    citation_tokens,
    family_name,
    in_text_forms,
    token_allowed,
)

JOURNAL_SHAPE = (
    "Surname, Initial. (Year) 'Article title', Journal Title, "
    "volume(issue), pp. start-end. Available at: doi:10.xxxx/xxxxx"
)
BOOK_SHAPE = "Surname, Initial. (Year) Title. Place: Publisher."
WEB_SHAPE = "Organisation (Year) Title. Available at: URL (Accessed: date)."

ANNOTATION_SENTENCES = (
    "Each annotation is a few full sentences after the citation, written so a student can read them aloud: "
    "what the paper did, what it found, and how it helps this assignment. "
    "Keep mark-scheme words the brief uses, and gloss each one in plain English the first time. "
    "Do not delete those words."
)

FOUR_A_FORMAT = (
    "Harvard Referencing 4a format: the citation line stays exact, then a few full sentences a student can read aloud. "
    "Those sentences say what the paper did, what it found, and how it helps this assignment. "
    "Keep mark-scheme words the brief uses, and gloss each one in plain English the first time. Do not delete those words. "
    "Do not replace that paragraph with a shortened bibliography or a citation line that has no sentences. "
    f"Journal: {JOURNAL_SHAPE}. "
    f"Book: {BOOK_SHAPE} "
    f"Web page: {WEB_SHAPE} "
    "A missing page, DOI, volume, journal, place, publisher, or access date stays blank. "
    "Do not invent it. The full reference pass is stage 9."
)

_DIG = re.compile(r"\bdig\b", re.IGNORECASE)
_NOTE_BAN_WORDS = (
    (_DIG, "dig"),
    (re.compile(r"invent-forbid", re.IGNORECASE), "invent-forbid"),
    (re.compile(r"\bEQR\b"), "EQR"),
    (re.compile(r"Grok Build", re.IGNORECASE), "Grok Build"),
    (re.compile(r"\bConfirm\b"), "Confirm"),
    (re.compile(r"\b(?:mid|front)[-\s]office\b", re.IGNORECASE), "office"),
)
_NOTE_BANS = tuple(pattern for pattern, _name in _NOTE_BAN_WORDS)
_QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
_PAGE = re.compile(r"\bpp?\.\s*([0-9]+(?:\s*[-–—]\s*[0-9]+)?)")
_WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
_INITIAL = re.compile(r"\b([A-Z])\.")
_ABBREV = re.compile(r"\b(?:pp|p|vol|no|fig|Dr|Mr|Ms|Prof)\.", re.IGNORECASE)
_ET_AL = re.compile(r"\bet al\.", re.IGNORECASE)
_BIBLIO_TAIL = re.compile(r"^['‘][^'’]+['’](?:\s*,\s*[^.]*)?\.?$")
_PAGE_RANGE = re.compile(r"^\d+\s*[-–—]\s*\d+$")
_ORDINAL_EDITION = re.compile(r"^(\d+)(st|nd|rd|th)$", re.IGNORECASE)


def _clean(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    return text or None


def _page_label(value: object) -> str | None:
    """A stored page value without a p. or pp. label of its own."""
    text = _clean(value)
    if text is None:
        return None
    return re.sub(r"^pp?\.\s*", "", text, flags=re.IGNORECASE) or None


def _page_prefix(value: str) -> str:
    """One page takes p.; a range or a list of pages takes pp."""
    if _PAGE_RANGE.fullmatch(value) or "," in value:
        return "pp."
    return "p."


def _article_label(value: object) -> str | None:
    """An article number without a label of its own."""
    text = _clean(value)
    if text is None:
        return None
    stripped = re.sub(
        r"^article\s*(?:number|no\.?)?\s*[:.]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return stripped or text


def _edition_label(value: object) -> str | None:
    """A bare ordinal edition reads as the handbook's 2nd edn."""
    text = _clean(value)
    if text is None:
        return None
    ordinal = _ORDINAL_EDITION.fullmatch(text)
    if ordinal is None:
        return text
    return f"{ordinal.group(1)}{ordinal.group(2).lower()} edn."


def _volume_label(value: object) -> str | None:
    """A stored volume without a vol. label of its own."""
    text = _clean(value)
    if text is None:
        return None
    stripped = re.sub(r"^vol(?:ume)?\.?\s*", "", text, flags=re.IGNORECASE).strip()
    return stripped or text


def _issue_label(value: object) -> str | None:
    """A stored issue without its own parentheses or no. label."""
    text = _clean(value)
    if text is None:
        return None
    stripped = re.sub(r"^(?:no\.?|issue)\s*", "", text, flags=re.IGNORECASE).strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1].strip()
    return stripped or text


def _doi_label(value: object) -> str | None:
    """A stored DOI without a resolver address or a doi: label of its own."""
    text = _clean(value)
    if text is None:
        return None
    stripped = re.sub(
        r"^(?:https?://(?:dx\.)?doi\.org/|doi\.org/|doi:\s*)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return stripped or text


def _locator(doi: str | None, url: str | None, accessed: str | None, *, web: bool) -> str:
    if doi:
        return f"Available at: doi:{doi}"
    if url:
        line = f"Available at: {url}"
        if web and accessed:
            line += f" (Accessed: {accessed})"
        return line
    if web and accessed:
        return f"(Accessed: {accessed})"
    return ""


def harvard_4a_parts(source: dict[str, Any]) -> list[tuple[str, bool]]:
    """(text, italic) pieces. Article titles stay in single quotes. Journal, book, and web titles are italic."""
    author = _clean(source.get("author"))
    year = _clean(source.get("year"))
    title = _clean(source.get("title"))
    container = _clean(source.get("container"))
    volume = _volume_label(source.get("volume"))
    issue = _issue_label(source.get("issue"))
    pages = _page_label(source.get("pages"))
    if pages and page_value_kind(pages) == "article":
        # An article id is not a page. Without a look-up mark it is unclear,
        # so the page slot stays blank rather than printing pp. e12345.
        pages = None
    article_number = _article_label(source.get("article_number"))
    edition = _edition_label(source.get("edition"))
    place = _clean(source.get("place"))
    publisher = _clean(source.get("publisher"))
    url = _clean(source.get("url"))
    doi = _doi_label(source.get("doi"))
    accessed = _clean(source.get("accessed"))

    parts: list[tuple[str, bool]] = []
    if author and year:
        parts.append((f"{author} ({year})", False))
    elif author:
        parts.append((author, False))
    elif year:
        parts.append((f"({year})", False))

    def gap() -> None:
        if parts and not parts[-1][0].endswith(" "):
            parts.append((" ", False))

    if container:
        if title:
            gap()
            parts.append((f"'{title}',", False))
        gap()
        parts.append((container, True))
        detail = ""
        if volume and issue:
            detail += f", {volume}({issue})"
        elif volume:
            detail += f", {volume}"
        elif issue:
            detail += f", ({issue})"
        if article_number:
            detail += f", article {article_number}"
        if pages:
            detail += f", {_page_prefix(pages)} {pages}"
        if detail:
            parts.append((detail, False))
        locator = _locator(doi, url, accessed, web=False)
        parts.append((f". {locator}" if locator else ".", False))
        return _finish(parts)

    if title:
        gap()
        parts.append((title, True))
    extras: list[str] = []
    if edition:
        extras.append(edition)
    if place and publisher:
        extras.append(f"{place}: {publisher}")
    elif place:
        extras.append(place)
    elif publisher:
        extras.append(publisher)
    # A place or publisher on a web entry does not cancel the access date.
    # Only a journal container keeps the line off the web branch.
    web = bool(url) and not container
    locator = _locator(doi, url, accessed, web=web)
    if parts or extras:
        # A gathered edition already carries its own full stop ("2nd edn.").
        # The separator supplies the stop, so the value does not add a second.
        cleaned_extras = [
            text.rstrip().rstrip(".") for text in extras if text.rstrip().rstrip(".")
        ]
        tail = ". " + ". ".join(cleaned_extras) if cleaned_extras else "."
        if locator:
            # A place or publisher needs its own stop before the locator.
            tail += (". " if cleaned_extras else " ") + locator
        parts.append((tail, False))
    elif locator:
        parts.append((locator, False))
    if not parts:
        parts.append((_clean(source.get("locator")) or "Untitled download", False))
    return _finish(parts)


def _finish(parts: list[tuple[str, bool]]) -> list[tuple[str, bool]]:
    text = "".join(piece for piece, _italic in parts).rstrip()
    if text and text[-1] not in ".!?":
        parts.append((".", False))
    return parts


def harvard_4a_line(source: dict[str, Any]) -> str:
    return "".join(piece for piece, _italic in harvard_4a_parts(source)).strip()


def in_text_uses_et_al(author_count: int, brief: str = "") -> bool:
    """Harvard Referencing: et al. from the fourth author.

    Two or three authors are all named. A brief that says to spell every
    author in the text does not replace this rule. The argument is accepted
    and ignored.
    """
    del brief
    return author_count >= 4


def note_ban_words(text: str) -> list[str]:
    """House labels in an annotation or a paper note, in list order."""
    if not isinstance(text, str) or not text:
        return []
    return [name for pattern, name in _NOTE_BAN_WORDS if pattern.search(text)]


def uses_house_jargon(text: str) -> bool:
    """House labels that must not be saved into an annotation or a paper note."""
    return bool(note_ban_words(text))


def _protect_dots(text: str) -> str:
    text = _ET_AL.sub("et al\x00", text)
    text = _ABBREV.sub(lambda match: match.group(0)[:-1] + "\x00", text)
    text = _INITIAL.sub(lambda match: match.group(1) + "\x00", text)
    return re.sub(r"(?<=\d)\.(?=\d)", "\x00", text)


def _full_sentences(text: str) -> list[str]:
    protected = _protect_dots(text)
    found: list[str] = []
    for match in re.finditer(r"[^.!?]+[.!?]", protected):
        raw = match.group(0).replace("\x00", ".").strip()
        if len(_WORD.findall(raw)) >= 4:
            found.append(raw)
    return found


def _biblio_span(span: str) -> bool:
    text = span.strip()
    if re.search(r"Available at:", text, re.IGNORECASE):
        return True
    if re.search(r"\bpp?\.\s*\d", text, re.IGNORECASE):
        return True
    return _BIBLIO_TAIL.match(text) is not None


def _real_sentences(text: str) -> list[str]:
    return [span for span in _full_sentences(text) if not _biblio_span(span)]


def _drop_in_text(text: str, source: dict[str, Any]) -> str:
    author = _clean(source.get("author"))
    year = _clean(source.get("year"))
    if not author or not year:
        return text
    surname = author.split(",")[0].strip()
    if not surname:
        return text
    text = re.sub(
        rf"\b{re.escape(surname)}\s*,\s*(?:[A-Z]\.\s*)+\(\s*{re.escape(year)}\s*\)",
        " ",
        text,
    )
    text = re.sub(
        rf"\b{re.escape(surname)}\s*\(\s*{re.escape(year)}\s*\)",
        " ",
        text,
    )
    return re.sub(
        rf"\(\s*{re.escape(surname)}\s*,\s*{re.escape(year)}\s*\)",
        " ",
        text,
    )


def _cite_only(text: str, source: dict[str, Any], line: str) -> bool:
    if line and line in text:
        return True
    if re.search(r"Available at:", text, re.IGNORECASE):
        return True
    if re.match(r"^[A-Z][^,\n]{0,80},\s*[A-Z]\.", text) and re.search(r"\(\d{4}\)", text):
        return True
    author = _clean(source.get("author"))
    year = _clean(source.get("year"))
    if not author or not year:
        return False
    surname = author.split(",")[0].strip()
    if surname and re.search(rf"\b{re.escape(surname)}\b", text) and year in text:
        bare = re.sub(r"['’]", " ", _drop_in_text(text, source))
        return len(_WORD.findall(bare)) < 4
    return False


def _annotation_shape(label: str, source: dict[str, Any], prose: str) -> list[dict[str, str]]:
    """Refuse a fragment or a citation line. Do not score vocabulary."""
    text = " ".join(prose.split())
    line = harvard_4a_line(source).strip()
    remainder = text.replace(line, " ") if line and line in text else text
    remainder = _drop_in_text(remainder, source)
    if _real_sentences(remainder):
        return []
    if _cite_only(text, source, line):
        return [
            {
                "code": "annotation-prose",
                "reason": (
                    f"{label} is a citation line with no sentences. "
                    "Add a few full sentences a student can read aloud: "
                    "what the paper did, what it found, and how it helps this assignment."
                ),
            }
        ]
    return [
        {
            "code": "annotation-prose",
            "reason": (
                f"{label} needs full sentences. A fragment is not enough. "
                "Say what the paper did, what it found, and how it helps this assignment."
            ),
        }
    ]


def annotation_note_issue(
    label: str, source: dict[str, Any], prose: str | None
) -> dict[str, str] | None:
    """Refuse an empty annotation body or a surname stub before the file is written."""
    text = prose.strip() if isinstance(prose, str) else ""
    if not text:
        return {
            "code": "annotation-prose",
            "reason": (
                f"{label} has no sentences yet. "
                "Add a few full sentences a student can read aloud: "
                "what the paper did, what it found, and how it helps this assignment."
            ),
        }
    if _surname_only(text, source):
        return {
            "code": "annotation-prose",
            "reason": (
                f"{label} is only a surname. "
                "Add a few full sentences a student can read aloud: "
                "what the paper did, what it found, and how it helps this assignment."
            ),
        }
    return None


def _surname_only(text: str, source: dict[str, Any]) -> bool:
    token = text.strip().rstrip(".!?").strip()
    if not token or _real_sentences(text):
        return False
    if bare_surname(token):
        return True
    author = _clean(source.get("author")) or ""
    family = family_name(author) if author else ""
    last = family.split()[-1] if family else ""
    if last and re.fullmatch(
        rf"{re.escape(last)}(?:\s*,\s*[A-Z](?:\s*\.)?)*",
        token,
        flags=re.IGNORECASE,
    ):
        return True
    return re.fullmatch(r"[A-Z][A-Za-z'’\-]+", token) is not None


def prose_issues(
    label: str,
    source: dict[str, Any],
    gathered: str,
    prose: str,
    *,
    annotation: bool = False,
) -> list[dict[str, Any]]:
    """Refuse house jargon and any quotation or citation the gathered file does not hold."""
    issues: list[dict[str, Any]] = []
    words = note_ban_words(prose)
    if words:
        issues.append(
            {
                "code": "house-jargon",
                "reason": (
                    f"{label} uses wording that is left out of the "
                    "annotation and the paper notes."
                ),
                "words": words,
            }
        )
    for match in _QUOTED.finditer(prose):
        span = match.group(1) if match.group(1) is not None else match.group(2)
        if span not in gathered:
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"{label} quotes text that is not an exact span of the gathered file. "
                        "Leave the quotation out."
                    ),
                }
            )
    author = _clean(source.get("author"))
    year = _clean(source.get("year"))
    forms = in_text_forms(author, year) if author and year else set()
    from essay_writer.word_references import readable_cite_text

    for token in citation_tokens(readable_cite_text(prose)):
        if not token_allowed(token, forms):
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"{label} cites {token}, which was not gathered for this source. "
                        "Do not invent the citation."
                    ),
                }
            )
    folded = gathered.casefold()
    printed = printed_pages_for(source)
    for match in _PAGE.finditer(prose):
        page = re.sub(r"\s+", "", match.group(1))
        if printed is not None:
            if page_span_printed(page, printed):
                continue
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"{label} page {page} is not printed in the opened file. Omit the page."
                    ),
                }
            )
            continue
        if page.casefold() not in folded:
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"{label} page {page} is not in the gathered text. Omit the page."
                    ),
                }
            )
    if annotation:
        issues.extend(_annotation_shape(label, source, prose))
    return issues


def _raw_for(source: dict[str, Any], raw: list[object] | None) -> dict[str, object] | None:
    if not raw:
        return None
    for item in raw:
        if not isinstance(item, dict):
            continue
        raw_id = _clean(item.get("id"))
        if raw_id and raw_id == source.get("id"):
            return item
        locator = item.get("locator")
        if isinstance(locator, str) and locator.strip().replace("\\", "/") == source.get("locator"):
            return item
    return None


def annotation_notes(
    kept: list[dict[str, Any]],
    raw: list[object] | None,
    texts: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    notes: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for source in kept:
        item = _raw_for(source, raw)
        if item is None or "annotation" not in item or item.get("annotation") is None:
            continue
        note = item.get("annotation")
        label = f"{source['id']} annotation"
        if not isinstance(note, str) or not note.strip():
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": f"{label} must be the paragraph after the citation, or omitted.",
                }
            )
            continue
        prose = note.strip()
        issues.extend(
            prose_issues(
                label,
                source,
                texts.get(source["locator"], ""),
                prose,
                annotation=True,
            )
        )
        notes[source["id"]] = prose
    return notes, issues


def review_markdowns(
    kept: list[dict[str, Any]],
    reviews: object,
    texts: dict[str, str],
) -> tuple[dict[str, str] | None, list[dict[str, str]]]:
    """One markdown per paper when reviews are sent. None keeps a gathered-quote note."""
    if reviews is None:
        return None, []
    if not isinstance(reviews, list):
        return None, [
            {
                "code": "critical-review",
                "reason": "4b needs one markdown per paper.",
            }
        ]
    by_id = {source["id"]: source for source in kept}
    found: dict[str, str] = {}
    issues: list[dict[str, str]] = []
    for index, item in enumerate(reviews):
        label = f"reviews[{index}]"
        if not isinstance(item, dict):
            issues.append(
                {"code": "critical-review", "reason": f"{label} must be one paper and its markdown."}
            )
            continue
        paper_id = _clean(item.get("paper_id"))
        markdown = item.get("markdown")
        if paper_id is None:
            issues.append({"code": "critical-review", "reason": f"{label} needs a paper id."})
            continue
        if paper_id in found:
            issues.append(
                {
                    "code": "critical-review",
                    "reason": f"4b keeps one markdown per paper. {paper_id} has more than one.",
                }
            )
            continue
        source = by_id.get(paper_id)
        if source is None:
            issues.append(
                {
                    "code": "critical-review",
                    "reason": f"{paper_id} is not a gathered paper. Do not invent a note for it.",
                }
            )
            continue
        if not isinstance(markdown, str) or not markdown.strip():
            issues.append(
                {
                    "code": "critical-review",
                    "reason": f"{label} needs the markdown for {paper_id}.",
                }
            )
            continue
        prose = markdown.strip()
        issues.extend(
            prose_issues(
                f"{paper_id} markdown",
                source,
                texts.get(source["locator"], ""),
                prose,
            )
        )
        found[paper_id] = prose
    if issues:
        return None, issues
    missing = [source["id"] for source in kept if source["id"] not in found]
    if missing:
        return None, [
            {
                "code": "critical-review",
                "reason": (
                    "4b needs one markdown per paper. Missing "
                    + ", ".join(missing)
                    + "."
                ),
            }
        ]
    return found, []
