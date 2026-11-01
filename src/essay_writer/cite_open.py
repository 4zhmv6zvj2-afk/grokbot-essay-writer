"""Open a gathered PDF for the citation check.

A .pdf is opened, including a file larger than 2MB. Author, year, and page
are checked against that text. The publication year is the year on that
file's own cite line. A page with no extractable text is recorded
in pdf-read-gaps.json and is not quoted. A gap file from the read chop is
used when it is already there.

The surname comes from the article's own author line when a download cover
or a please-cite token inverts a compound surname. A reference page is a
number the file prints. The PDF viewer index is not a page. An article
number stays in the article-number slot.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from essay_writer.known_paths import research_file
from essay_writer.paths import workspace_root
from essay_writer.pdf_read import GAPS_NAME, load_gaps, record_read_gaps
from essay_writer.pdf_year import publication_year

_PLEASE_CITE = re.compile(
    r"please\s+cite(?:\s+this\s+article)?\s+as:\s*([^\n]+)",
    re.IGNORECASE,
)
_PLEASE_AUTHOR = re.compile(
    r"^([A-Z][A-Za-z'’\-]+),\s*([A-Z](?:\s*\.?\s*[A-Z])*\.?)"
)
_SURNAME_FIRST = re.compile(
    r"^([A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+)+),\s+([A-Z](?:\.[A-Z])*\.?|[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+)*)\.?$"
)
_BYLINE = re.compile(r"^([A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+){1,6})$")
_ARTICLE = re.compile(
    r"\barticle\s*(?:number|no\.?)\s*[:.]?\s*([A-Za-z]?\d{3,8})\b",
    re.IGNORECASE,
)
_NARRATIVE_PAGE = re.compile(
    # A joint label ("Smith and Jones") or an et al. label names every
    # author the page check has to look at, not only the last one.
    r"\b([A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+)*"
    r"(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+)?"
    r"(?:\s+et\s+al\.?)?)\s+\(\s*\d{4}[a-z]?,\s*pp?\.\s*([0-9]+(?:\s*[–-]\s*[0-9]+)?)\)"
)
_YEAR_TOKEN = re.compile(r"^(?:1[6-9]\d{2}|20\d{2})$")
_BRACKET_WITH_YEAR = re.compile(r"\(([^()\n]*\d{4}[^()\n]*)\)")
_PAGE_ITEM = re.compile(
    r"\s*([^,;()\n]+),\s*(\d{4}[a-z]?),\s*pp?\.\s*(\d+(?:\s*[–-]\s*\d+)?)\s*"
)
_ET_AL_LABEL = re.compile(r"\s+et\s+al\.?", re.IGNORECASE)
_UNQUOTED = (
    " A page with no extractable text is recorded in pdf-read-gaps.json and is not quoted."
)


@dataclass(frozen=True)
class OpenedPaper:
    text: str
    printed_pages: tuple[str, ...]
    article_number: str | None
    author: str | None
    unquoted: bool
    gaps_name: str = GAPS_NAME
    year: str | None = None


def _unescape(raw: bytes) -> str:
    inner = raw[1:-1]
    text = bytearray()
    index = 0
    while index < len(inner):
        byte = inner[index]
        if byte == 0x5C and index + 1 < len(inner):
            nxt = inner[index + 1]
            mapping = {ord("n"): ord("\n"), ord("r"): ord("\r"), ord("t"): ord("\t")}
            text.append(mapping.get(nxt, nxt))
            index += 2
            continue
        text.append(byte)
        index += 1
    return text.decode("latin-1", errors="ignore")


def _objects(data: bytes) -> dict[int, bytes]:
    found: dict[int, bytes] = {}
    for match in re.finditer(rb"(\d{1,9})\s+0\s+obj(.*?)endobj", data, re.DOTALL):
        found[int(match.group(1))] = match.group(2)
    return found


def _streams(body: bytes) -> list[bytes]:
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", body, re.DOTALL):
        raw = match.group(1).rstrip(b"\r\n")
        header = body[max(0, match.start() - 200) : match.start()]
        if b"FlateDecode" in header:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
        chunks.append(raw)
    return chunks


def _paren_text(blob: bytes) -> str:
    pieces = [_unescape(match.group()) for match in re.finditer(rb"\((?:\\.|[^\\)])*\)", blob)]
    return "\n".join(piece for piece in pieces if piece.strip())


def _page_texts(data: bytes) -> list[str]:
    objects = _objects(data)
    pages: list[tuple[int, str]] = []
    for number, body in objects.items():
        if not re.search(rb"/Type\s*/Page(?!s)\b", body):
            continue
        contents = re.findall(rb"/Contents\s+(\d+)\s+0\s+R", body)
        blobs: list[bytes] = []
        for content_id in contents:
            content = objects.get(int(content_id))
            if content is None:
                continue
            streams = _streams(content)
            blobs.append(b"\n".join(streams) if streams else content)
        if not blobs:
            streams = _streams(body)
            blobs = streams or [body]
        pages.append((number, "\n".join(_paren_text(blob) for blob in blobs)))
    if pages:
        pages.sort()
        return [text for _, text in pages]
    streams = _streams(data)
    blob = b"\n".join(streams) if streams else data
    return [_paren_text(blob)]


def _mask_gaps(data: bytes, gaps: list[dict[str, Any]]) -> bytes:
    if not gaps:
        return data
    masked = bytearray(data)
    for gap in gaps:
        offset = gap.get("offset")
        length = gap.get("length")
        if not isinstance(offset, int) or not isinstance(length, int) or length <= 0:
            continue
        end = min(len(masked), offset + length)
        if offset < 0 or offset >= end:
            continue
        masked[offset:end] = b" " * (end - offset)
    return bytes(masked)


_PAGE_OF = re.compile(r"^\s*page\s+(\d{1,4})\s+of\s+\d{1,4}\s*$", re.IGNORECASE)


def _printed_numbers(page_texts: list[str], article_number: str | None) -> tuple[str, ...]:
    found: list[str] = []
    for text in page_texts:
        for line in text.splitlines():
            token = line.strip()
            if not re.fullmatch(r"\d{1,4}", token):
                # A Word export prints its folio as "Page 32 of 40". That
                # leading number is the page the file prints.
                page_of = _PAGE_OF.match(token)
                if page_of is None:
                    continue
                token = page_of.group(1)
            if _YEAR_TOKEN.fullmatch(token):
                continue
            if article_number and token == article_number:
                continue
            found.append(token)
    return tuple(found)


def _initials(tokens: list[str]) -> str:
    rendered: list[str] = []
    for token in tokens:
        chunks = [piece for piece in token.split("-") if piece]
        if len(chunks) > 1:
            rendered.append(".-".join(chunk[0] for chunk in chunks) + ".")
        elif token:
            rendered.append(token[0] + ".")
    return "".join(rendered)


def _please_author(text: str) -> tuple[str, list[str]] | None:
    match = _PLEASE_CITE.search(text)
    if not match:
        return None
    head = _PLEASE_AUTHOR.match(match.group(1).strip())
    if not head:
        return None
    return head.group(1), re.findall(r"[A-Z]", head.group(2))


def _article_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip().strip(".")
        if not line or _PLEASE_CITE.search(line):
            continue
        lines.append(line)
    return lines


def _surname_and_given(text: str) -> tuple[str | None, list[str]]:
    """Surname as the article author line prints it, not the please-cite token."""
    lines = _article_lines(text)
    for line in lines:
        match = _SURNAME_FIRST.match(line)
        if not match:
            continue
        surname = match.group(1).strip()
        if len(surname.split()) < 2:
            continue
        given = [piece for piece in match.group(2).replace(".", " ").split() if piece]
        words = [piece for piece in given if len(piece) > 1]
        return surname, words or given
    bylines = [line for line in lines if _BYLINE.match(line)]
    for line in bylines:
        tokens = line.split()
        if len(tokens) < 3:
            continue
        for size in range(len(tokens) - 1, 1, -1):
            surname = " ".join(tokens[-size:])
            if surname in lines and surname != line:
                return surname, tokens[:-size]
    return None, []


def compound_author(text: str) -> str | None:
    """Harvard author when a please-cite token inverts the author-line surname.

    Fosso Wamba on the author line stays Fosso Wamba. It does not become
    Wamba, S.F. A Western two-initial name is left as printed when the
    author line does not state a longer surname.
    """
    please = _please_author(text)
    if please is None:
        return None
    inverted_surname, inverted_initials = please
    surname, given = _surname_and_given(text)
    if not surname or not given:
        return None
    words = surname.split()
    if len(words) < 2 or words[-1].casefold() != inverted_surname.casefold():
        return None
    given_initials = [token[0].upper() for token in given]
    if inverted_initials[: len(given_initials)] != given_initials:
        return None
    extra = inverted_initials[len(given_initials) :]
    head = words[:-1]
    if [word[0].upper() for word in head] != extra:
        return None
    return f"{surname}, {_initials(given)}"


def article_number_in(text: str) -> str | None:
    match = _ARTICLE.search(text)
    if not match:
        return None
    return match.group(1)


def _gap_key(gap: dict[str, Any]) -> tuple[object, ...]:
    return (gap.get("source"), gap.get("part"), gap.get("reason"))


def _record_blank_pages(path: Path, page_texts: list[str], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {_gap_key(gap) for gap in existing}
    fresh: list[dict[str, Any]] = []
    for index, text in enumerate(page_texts, start=1):
        if text.strip():
            continue
        gap = {
            "source": path.name,
            "part": index,
            "reason": "no extractable text",
            "bytes_on_machine": True,
            "quoted": False,
        }
        if _gap_key(gap) in known:
            continue
        fresh.append(gap)
    if fresh:
        try:
            record_read_gaps(path.parent, fresh)
        except OSError:
            return []
    return fresh


def open_for_citation(path: Path, essay_id: str | None = None) -> OpenedPaper:
    """Read one PDF for citation. Size is not a reason to refuse the file."""
    target = Path(path)
    if essay_id:
        from essay_writer.known_paths import research_file

        allowed = research_file(essay_id, str(target))
        if allowed is None:
            return OpenedPaper("", (), None, None, True)
        target = allowed
    source_gaps = [gap for gap in load_gaps(target.parent) if gap.get("source") == target.name]
    try:
        data = target.read_bytes()
    except OSError as exc:
        gap = {
            "source": target.name,
            "part": 1,
            "reason": "unreadable",
            "detail": str(exc),
            "bytes_on_machine": False,
            "quoted": False,
        }
        try:
            record_read_gaps(target.parent, [gap])
        except OSError:
            pass
        return OpenedPaper("", (), None, None, True)
    page_texts = _page_texts(_mask_gaps(data, source_gaps))
    text = "\n".join(page for page in page_texts if page.strip())
    number = article_number_in(text)
    blank = _record_blank_pages(target, page_texts, source_gaps)
    unquoted = bool(blank or source_gaps)
    first_page = page_texts[0] if page_texts else ""
    return OpenedPaper(
        text,
        _printed_numbers(page_texts, number),
        number,
        compound_author(text),
        unquoted,
        year=publication_year(first_page),
    )


def _essay_from_source(source: dict[str, Any]) -> str | None:
    locator = source.get("locator")
    if not isinstance(locator, str):
        return None
    parts = locator.strip().replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] in {"uploads", "Essay-writer", "KB1"}:
        return parts[1]
    return None


def pdf_from_source(source: dict[str, Any], essay_id: str | None = None) -> Path | None:

    essay = essay_id or _essay_from_source(source)
    for key in ("locator", "path"):
        raw = source.get(key)
        if not isinstance(raw, str) or not raw.lower().endswith(".pdf"):
            continue
        candidate = Path(raw)
        if not candidate.is_file():
            candidate = workspace_root() / raw.strip().replace("\\", "/")
        if essay:
            allowed = research_file(essay, str(candidate))
            if allowed is None or not allowed.is_file():
                continue
            return allowed
        if candidate.is_file():
            return candidate
    return None


def printed_pages_for(source: dict[str, Any], essay_id: str | None = None) -> tuple[str, ...] | None:
    """Printed page numbers, or None when the source is not a PDF."""
    path = pdf_from_source(source, essay_id)
    if path is None:
        return None
    return open_for_citation(path, essay_id or _essay_from_source(source)).printed_pages


_PAGE_RANGE = re.compile(r"^\d+\s*[-–—]\s*\d+$")
# A lone printed page line is 1–4 digits. A longer number, or a letter
# plus digits, is an article id that Crossref often puts in the page field.
_ARTICLE_ID = re.compile(r"^(?:[A-Za-z]\d{2,8}|\d{5,8})$")


def page_value_kind(value: str) -> str:
    """Classify a page field: range, article, or page.

    A hyphenated span is a page range. A value that cannot be a lone
    printed page line is an article id. A 1–4 digit value is a page.
    """
    text = value.strip()
    if _PAGE_RANGE.fullmatch(text):
        return "range"
    if _ARTICLE_ID.fullmatch(text):
        return "article"
    return "page"


def page_span_printed(claimed: str, printed: tuple[str, ...]) -> bool:
    """True when every claimed page is in the printed list.

    A hyphen, en dash, or em dash between two numbers is that whole span.
    A comma keeps the named pages only. A page the file does not print is
    not a printed page.
    """
    if not isinstance(claimed, str) or not claimed.strip() or not printed:
        return False
    pieces = re.findall(r"\d+\s*[-–—]\s*\d+|\d+", claimed)
    if not pieces:
        return False
    have = set(printed)
    needed: list[str] = []
    for piece in pieces:
        span = re.fullmatch(r"(\d+)\s*[-–—]\s*(\d+)", piece)
        if span is None:
            needed.append(piece)
            continue
        start = int(span.group(1))
        end = int(span.group(2))
        if end < start or end - start > 2000:
            return False
        needed.extend(str(number) for number in range(start, end + 1))
    return all(number in have for number in needed)


def quote_refusal(quote_missing: bool, opened: OpenedPaper | None) -> str | None:
    if not quote_missing:
        return None
    reason = "quote is not an exact span of the gathered text."
    if opened is not None and opened.unquoted:
        reason += _UNQUOTED
    return reason


def _is_inverted_claim(claimed: str, corrected: str) -> bool:
    if "," not in claimed or "," not in corrected:
        return False
    claim_surname = claimed.split(",", 1)[0].strip().casefold()
    full = corrected.split(",", 1)[0].strip()
    words = full.split()
    if len(words) < 2:
        return False
    return claim_surname == words[-1].casefold()


def author_kept(claimed: str, opened: OpenedPaper) -> str | None:
    """Corrected author when the claim is the author line or the inverted token."""
    if not opened.author:
        return None
    if claimed.casefold() == opened.author.casefold() or _is_inverted_claim(claimed, opened.author):
        return opened.author
    return None


_CITE_YEAR = r"(?:1[6-9]\d{2}|20\d{2})"
_CITE_NAME = r"[A-Z][A-Za-z'’\-]+(?:\s+[A-Z][A-Za-z'’\-]+)*"
_CITE_NAMES = rf"{_CITE_NAME}(?:\s+(?:and|&)\s+{_CITE_NAME})*"
_YEAR_GLOSS = rf"(?:(?:\s*(?:…|\.{{2,}})\s*|\s*,\s*|\s+)treated\s+as\s+{_CITE_YEAR})"
_NARRATIVE_CITE = re.compile(
    rf"\b(?P<names>{_CITE_NAMES})\s*\(\s*(?P<year>{_CITE_YEAR})(?P<gloss>{_YEAR_GLOSS})?\s*\)",
    re.IGNORECASE,
)
_PAREN_CITE = re.compile(
    rf"\(\s*(?P<names>{_CITE_NAMES})\s*,\s*(?P<year>{_CITE_YEAR})(?P<gloss>{_YEAR_GLOSS})?\s*\)",
    re.IGNORECASE,
)
_LEFTOVER_GLOSS = re.compile(
    rf"\s*(?:…|\.{{2,}})?\s*,?\s*treated\s+as\s+{_CITE_YEAR}",
    re.IGNORECASE,
)


def _surnames(author: str) -> set[str]:
    parts = re.split(r"\s+and\s+|\s*&\s*", author.strip(), flags=re.IGNORECASE)
    names: set[str] = set()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "," in part:
            part = part.split(",", 1)[0].strip()
        tokens = [token.strip(".") for token in part.split() if token.strip(".")]
        if tokens:
            names.add(tokens[-1].casefold())
    return names


def _opened_year_rows(essay_id: str) -> list[tuple[set[str], str]]:
    """Publication year on each opened PDF's own cite line."""
    from essay_writer.pdf_year import citation_year
    from essay_writer.research_packs import bibliography_sources

    rows: list[tuple[set[str], str]] = []
    for source in bibliography_sources(essay_id):
        author = source.get("author")
        if not isinstance(author, str) or not author.strip():
            continue
        path = pdf_from_source(source, essay_id)
        if path is None:
            continue
        year = citation_year(path, essay_id)
        if not year:
            continue
        names = _surnames(author)
        if names:
            rows.append((names, year))
    return rows


def _year_for(names: set[str], rows: list[tuple[set[str], str]]) -> str | None:
    """Year for this author set. One surname of a joint paper is a different author."""
    exact = [year for surnames, year in rows if surnames == names]
    if exact:
        return exact[0]
    return None


def _rewrite_cites(text: str, rows: list[tuple[set[str], str]], pattern: re.Pattern[str], *, paren: bool) -> str:
    def replace(match: re.Match[str]) -> str:
        names = match.group("names")
        year = match.group("year")
        gloss = match.group("gloss")
        opened = _year_for(_surnames(names), rows)
        kept = opened or year
        if opened is None and not gloss:
            return match.group(0)
        if paren:
            return f"({names}, {kept})"
        return f"{names} ({kept})"

    return pattern.sub(replace, text)


def cite_look(essay_id: str, text: str) -> str:
    """Plan and cite looks use the opened PDF's publication year.

    A line such as '2025 treated as 2023' is not written. When the opened
    PDF's own cite line prints a year, a look that cites that author with
    another year is rewritten to it before the stage file is saved. A look
    that cites some other author is left as written. No second year is
    invented when the cite line does not print one.
    """
    if not isinstance(text, str) or not text:
        return text
    if not re.search(rf"\b{_CITE_YEAR}\b", text) and "treated as" not in text.casefold():
        return text
    rows = _opened_year_rows(essay_id) if essay_id else []
    rewritten = _rewrite_cites(text, rows, _NARRATIVE_CITE, paren=False)
    rewritten = _rewrite_cites(rewritten, rows, _PAREN_CITE, paren=True)
    return _LEFTOVER_GLOSS.sub("", rewritten)


def _pages_marked_lookup(source: dict[str, Any], value: str) -> bool:
    """True when this page value was stored from a matching look-up."""
    provenance = source.get("field_sources")
    if not isinstance(provenance, dict) or provenance.get("pages") != "lookup":
        return False
    current = source.get("pages")
    return isinstance(current, str) and current.strip() == value.strip()


def lookup_page_covers(source: dict[str, Any], claimed: str) -> bool:
    """True when a looked-up page field holds the claimed page.

    A stored page range covers a page inside it. A page the opened file
    prints is checked against the file, not against this look-up.
    """
    provenance = source.get("field_sources")
    if not isinstance(provenance, dict) or provenance.get("pages") != "lookup":
        return False
    stored = source.get("pages")
    if not isinstance(stored, str) or not stored.strip():
        return False
    stored_text = re.sub(r"\s+", "", re.sub(r"^pp?\.\s*", "", stored, flags=re.IGNORECASE))
    claimed_text = re.sub(r"\s+", "", claimed)
    if not stored_text or not claimed_text:
        return False
    if stored_text == claimed_text:
        return True
    span = re.fullmatch(r"(\d+)[-–—](\d+)", stored_text)
    if span is None or not claimed_text.isdigit():
        return False
    return int(span.group(1)) <= int(claimed_text) <= int(span.group(2))


def promote_lookup_article_page(source: dict[str, Any]) -> dict[str, object]:
    """Move a look-up article id out of the page field.

    Crossref sometimes returns that id in `page` when the work has no range.
    It is an article number, not `pp.`. A page range is left as pages.
    """
    pages = source.get("pages")
    if not isinstance(pages, str):
        return source
    text = pages.strip()
    if page_value_kind(text) != "article" or not _pages_marked_lookup(source, text):
        return source
    updated = dict(source)
    updated.pop("pages", None)
    if not updated.get("article_number"):
        updated["article_number"] = text
    return updated


def apply_opened_citation(source: dict[str, Any], essay_id: str | None = None) -> dict[str, object]:
    """Apply the opened PDF to one citation. A missing locator stays blank.

    A look-up page stays when the PDF has no lone printed page lines, and a
    look-up article id is stored as an article number. A page with neither
    of those, and no printed line, stays blank.
    """
    path = pdf_from_source(source, essay_id)
    if path is None:
        return promote_lookup_article_page(source)
    opened = open_for_citation(path, essay_id or _essay_from_source(source))
    updated = dict(source)
    corrected = opened.author
    claimed = updated.get("author")
    if isinstance(corrected, str) and isinstance(claimed, str):
        if claimed.strip().casefold() == corrected.casefold() or _is_inverted_claim(claimed, corrected):
            updated["author"] = corrected
    pages = updated.get("pages")
    page_text = str(pages).strip() if pages is not None and not isinstance(pages, bool) else ""
    if page_text:
        kind = page_value_kind(page_text)
        looked_up = _pages_marked_lookup(updated, page_text)
        if looked_up and kind in {"range", "page"}:
            # A matching look-up keeps its page, including a lone page. A
            # page range stays even when the file prints no page lines.
            updated["pages"] = page_text
        elif not (kind == "article" and looked_up) and not page_span_printed(
            page_text, opened.printed_pages
        ):
            updated.pop("pages", None)
    if opened.article_number:
        updated["article_number"] = opened.article_number
    if opened.year:
        updated["year"] = opened.year
    else:
        updated.pop("year", None)
    return promote_lookup_article_page(updated)


def _label_names(label: str) -> list[str]:
    """Family names a cite label names, with `et al.` taken off."""
    text = _ET_AL_LABEL.sub("", label)
    return [part.strip() for part in re.split(r"\s+and\s+|\s*&\s*", text) if part.strip()]


def _matches_author(label: str, source: dict[str, Any]) -> bool:
    author = source.get("author")
    if not isinstance(author, str) or not author.strip():
        return False
    surname = author.split(",", 1)[0].strip().casefold()
    return any(name.casefold() == surname for name in _label_names(label))


# A short lead-in before the name in a bracket. It is not part of the label.
_LEAD_IN = re.compile(
    r"^(?:see\s+(?:also\s+)?|cf\.?\s+|e\.g\.,?\s+|i\.e\.,?\s+|compare\s+|also\s+)",
    re.IGNORECASE,
)


def _matches_page_label(label: str, source: dict[str, Any]) -> bool:
    """True when the page label names this author, with a lead-in read off."""
    return _matches_author(_LEAD_IN.sub("", label).strip(), source)


def in_text_page_issues(
    sections: list[dict[str, Any]], sources: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """In-text pages only when that author's opened file prints them."""
    issues: list[dict[str, str]] = []
    pdf_sources = [source for source in sources if pdf_from_source(source) is not None]
    if not pdf_sources:
        return issues
    for section in sections:
        body = section.get("body")
        if not isinstance(body, str):
            continue
        found: list[tuple[str, str]] = []
        for bracket in _BRACKET_WITH_YEAR.finditer(body):
            for part in bracket.group(1).split(";"):
                item = _PAGE_ITEM.fullmatch(part)
                if item is not None:
                    found.append((item.group(1), item.group(3)))
        found.extend((match.group(1), match.group(2)) for match in _NARRATIVE_PAGE.finditer(body))
        for label, page in found:
            owners = [source for source in pdf_sources if _matches_page_label(label, source)]
            if not owners:
                continue
            printed_lists = [printed_pages_for(owner) or () for owner in owners]
            token = re.sub(r"\s+", "", page)
            if any(page_span_printed(token, printed) for printed in printed_lists):
                continue
            # A matching look-up supports the page when the opened file
            # prints no page lines of its own. A printed page still wins.
            if any(
                not printed and lookup_page_covers(owner, token)
                for owner, printed in zip(owners, printed_lists, strict=False)
            ):
                continue
            issues.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"In-text page {token} is not printed in the opened file. "
                        "Omit the page. Do not cite the PDF viewer index."
                    ),
                }
            )
    return issues
