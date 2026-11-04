"""Harvard reference check for the final Word file.

The writer runs this before a stage 10 Word file is treated as done.
The independent reviewer runs the same check and clears only when it is
green. A pass cannot be marked without the check. The writer cannot clear
a reviewer finding.

The check reads Word runs and structured source fields. A markdown string
is not evidence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer.confirm import refuse
from essay_writer.state import load_state
from essay_writer.textutil import family_name

HANDBOOK_NAME = "docs/referencing-harvard.md"

_PP = re.compile(
    r"\b(p{1,2})\.\s*"
    r"([0-9]+(?:\s*[-–—]\s*[0-9]+)?(?:\s*,\s*[0-9]+(?:\s*[-–—]\s*[0-9]+)?)*)"
)
_DOI = re.compile(r"\bdoi:\s*(\S+)", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_ACCESSED = re.compile(r"\(Accessed:\s*([^)]*)\)", re.IGNORECASE)
_ARTICLE_IN_PAGES = re.compile(r"\bpp?\.\s*([A-Za-z]\d{2,8}|\d{5,8})\b", re.IGNORECASE)
_DOI_PREFIX = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/|doi\.org/|doi:\s*)", re.IGNORECASE
)


def claim_reference_pass(seat: str = "writer") -> dict[str, object]:
    """Refuse. A pass exists only after the check runs. The writer cannot mark one."""
    from essay_writer.review import PERSON_BLOCK, writer_clears_left

    if seat != "reviewer":
        return refuse(
            "harvard-references",
            "The Harvard reference check has not run. A pass cannot be marked. " + PERSON_BLOCK,
            checked=False,
            writer_clears_left=writer_clears_left(),
        )
    return refuse(
        "harvard-references",
        "The independent reviewer cannot clear without running the Harvard reference check.",
        checked=False,
        seat="reviewer",
    )


def writer_reference_block(
    essay_id: str,
    path: Path,
    sources: list[Any],
) -> dict[str, object] | None:
    """Run the check. There is no argument that marks a pass."""
    misses = compliance_misses(path, sources, essay_id=essay_id)
    if not misses:
        return None

    return refuse(
        "harvard-references",
        _reason(misses),
        misses=misses,
        checked=True,
        handbook=HANDBOOK_NAME,
        seat="writer",
    )


def clear_reference_findings(
    essay_id: str,
    path: Path,
    *,
    seat: str,
) -> dict[str, object]:
    """Re-run the check. The reviewer clears only when it is green.

    The writer cannot clear a reviewer finding.
    """
    from essay_writer.review import PERSON_BLOCK, writer_clears_left

    if seat != "reviewer":
        return refuse(
            "seat",
            PERSON_BLOCK,
            cleared=False,
            checked=False,
            writer_clears_left=writer_clears_left(),
        )
    misses = compliance_misses(path, reference_sources(essay_id), essay_id=essay_id)
    if misses:
        return refuse(
            "harvard-references",
            _reason(misses),
            misses=misses,
            cleared=False,
            checked=True,
            handbook=HANDBOOK_NAME,
            seat="reviewer",
        )
    return {
        "ok": True,
        "cleared": True,
        "checked": True,
        "seat": "reviewer",
        "misses": [],
        "handbook": HANDBOOK_NAME,
    }


def reference_sources(essay_id: str) -> list[dict[str, object]]:
    """Gathered sources for this sequence. A caller list is not a pass."""
    from essay_writer.late_chain import _pack_sources

    state = load_state(essay_id)
    pack = state.get("saved_pack")
    if not isinstance(pack, dict):
        pack = {}
    rows = _pack_sources(essay_id, pack)
    return [row for row in rows if isinstance(row, dict)]


def italic_journal_title(line: str, sources: list[Any], essay_id: str | None = None) -> str | None:
    """Journal title to italicise when this line is that gathered source."""
    source = _match_source(line, sources, essay_id)
    if source is None:
        return None
    container = _text(source.get("container"))
    if not container or container not in line:
        return None
    return container


def compliance_misses(
    path: Path,
    sources: list[Any],
    *,
    essay_id: str | None = None,
) -> list[dict[str, str]]:
    """Concrete misses against the Harvard referencing note and the Word runs."""
    misses: list[dict[str, str]] = []
    handbook = _handbook_problem()
    if handbook:
        misses.append({"code": "handbook", "detail": handbook})
    document = _open(path)
    if document is None:
        misses.append(
            {
                "code": "word",
                "detail": "The Word file could not be opened for the Harvard reference check.",
            }
        )
        return misses
    body, references = _split(document)
    prepared = [_normalized(source, essay_id) for source in sources if isinstance(source, dict)]
    if references:
        from essay_writer.textutil import citation_tokens
        from essay_writer.word_references import readable_cite_text

        body_text = readable_cite_text("\n".join(paragraph.text for paragraph in body))
        seen: set[str] = set()
        for token in citation_tokens(body_text):
            if token in seen:
                continue
            seen.add(token)
            if _cite_covered(token, references):
                continue
            shown = token.strip()
            misses.append(
                {
                    "code": "author-date",
                    "detail": f"In-text citation ({shown}) has no matching reference list entry.",
                }
            )
        for source in prepared:
            paragraph = _match_paragraph(references, source)
            if paragraph is None:
                continue
            misses.extend(_source_misses(paragraph, source))
    return misses


def _reason(misses: list[dict[str, str]]) -> str:
    details = [item["detail"] for item in misses if item.get("detail")]
    shown = " ".join(details[:8])
    if not shown:
        return "Harvard reference check failed."
    return f"Harvard reference check failed. {shown}"


def _handbook_problem() -> str | None:
    from essay_writer.handbook import handbook_path

    path = handbook_path()
    if not path.is_file():
        return f"The Harvard referencing note {HANDBOOK_NAME} could not be read."
    try:
        text = path.read_text(encoding="utf-8").casefold()
    except OSError:
        return f"The Harvard referencing note {HANDBOOK_NAME} could not be read."
    if "italic" not in text or "pp." not in text or "doi" not in text:
        return f"The Harvard referencing note {HANDBOOK_NAME} is missing a reference-list rule."
    return None


def _open(path: Path):
    from zipfile import BadZipFile

    from docx.opc.exceptions import PackageNotFoundError

    if not Path(path).is_file():
        return None
    try:
        from docx import Document

        return Document(str(path))
    except (OSError, ValueError, KeyError, BadZipFile, PackageNotFoundError):
        return None


def _split(document) -> tuple[list[Any], list[Any]]:
    body: list[Any] = []
    references: list[Any] = []
    seen = False
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style is not None else ""
        heading = style.startswith("Heading")
        if not seen and text.casefold() == "references":
            seen = True
            continue
        if seen:
            if heading and text and text.casefold() != "references":
                break
            if text:
                references.append(paragraph)
            continue
        if text:
            body.append(paragraph)
    return body, references


def _normalized(source: dict[str, object], essay_id: str | None) -> dict[str, object]:
    from essay_writer.cite_open import apply_opened_citation

    opened = apply_opened_citation(source, essay_id)
    return opened if isinstance(opened, dict) else dict(source)


def _text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _surname(author: str) -> str:

    return family_name(author).split()[-1] if author else ""


def _year_present(text: str, year: str) -> bool:
    if not year:
        return False
    return re.search(rf"(?<![0-9]){re.escape(year)}(?![0-9a-z])", text, re.IGNORECASE) is not None


def _name_present(text: str, surname: str) -> bool:
    if not surname:
        return False
    return re.search(rf"\b{re.escape(surname)}\b", text, re.IGNORECASE) is not None


def _author_year_present(text: str, surname: str, year: str) -> bool:
    """True when the year sits in brackets after that family name."""
    if not surname or not year:
        return False
    pattern = (
        rf"\b{re.escape(surname)}\b[^()\n]{{0,200}}"
        rf"\(\s*{re.escape(year)}[a-z]?\s*\)"
    )
    return re.search(pattern, text, re.IGNORECASE) is not None


def _match_paragraph(paragraphs: list[Any], source: dict[str, object]):
    author = _text(source.get("author"))
    year = _text(source.get("year"))
    surname = _surname(author)
    if not surname or not year:
        return None
    candidates = [
        paragraph for paragraph in paragraphs if _name_present(paragraph.text, surname)
    ]
    if not candidates:
        return None
    for paragraph in candidates:
        if _author_year_present(paragraph.text, surname, year):
            return paragraph
    # The author is listed but this year is not. Check that entry so the
    # first pass can name the missing year instead of skipping the source.
    return candidates[0]


def _match_source(line: str, sources: list[Any], essay_id: str | None) -> dict[str, object] | None:
    for source in sources:
        if not isinstance(source, dict):
            continue
        normalized = _normalized(source, essay_id)
        author = _text(normalized.get("author"))
        year = _text(normalized.get("year"))
        surname = _surname(author)
        if surname and year and _name_present(line, surname) and _year_present(line, year):
            return normalized
    return None


def _cite_covered(token: str, paragraphs: list[Any]) -> bool:
    name, _, year = token.rpartition(", ")
    year = year.strip()
    name = re.sub(r"\bet al\.?", "", name, flags=re.IGNORECASE).strip()
    primary = re.split(r"\s+and\s+|,", name)[0].strip()
    surname = primary.split()[-1] if primary else ""
    if not surname or not year:
        return False
    from essay_writer.word_references import _line_covers_cite

    # The year has to sit in brackets straight after that name. A year
    # printed in the title of another year's entry is not this cite's year.
    return any(_line_covers_cite(paragraph.text or "", token) for paragraph in paragraphs)


def _norm_span(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("–", "-").replace("—", "-")


def _norm_doi(value: str) -> str:
    return value.strip().rstrip(".,;)").casefold()


def _norm_url(value: str) -> str:
    return value.strip().rstrip(".,;)")


def _norm_date(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().rstrip(".")


def _norm_name(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip().casefold()
    return text.replace("’", "'").replace("‘", "'")


def _source_misses(paragraph, source: dict[str, object]) -> list[dict[str, str]]:
    misses: list[dict[str, str]] = []
    author = _text(source.get("author"))
    year = _text(source.get("year"))
    label = _surname(author) or "this source"
    if year:
        label = f"{label} ({year})"
    text = paragraph.text or ""
    if author and _norm_name(author) not in _norm_name(text):
        misses.append(
            {
                "code": "author",
                "detail": f"Reference for {label} should show {author}, not a surname alone.",
            }
        )
    entry_surname = _surname(author)
    if year and entry_surname and not _author_year_present(text, entry_surname, year):
        misses.append(
            {
                "code": "year",
                "detail": (
                    f"Reference for {label} should show ({year}) after the author. "
                    "Use the gathered year, not another one."
                ),
            }
        )
    container = _text(source.get("container"))
    if container:
        italic = "".join(run.text or "" for run in paragraph.runs if run.italic)
        if container.casefold() not in italic.casefold():
            misses.append(
                {
                    "code": "journal-italic",
                    "detail": f"Journal title {container} is not italic for {label}.",
                }
            )
        # The article title is in single quotation marks and is not italic.
        # A saved line may carry its own title, so only a title printed
        # before the journal is read for its quote shape.
        title = _text(source.get("title"))
        if title:
            lowered = text.casefold()
            title_at = lowered.find(title.casefold())
            container_at = lowered.find(container.casefold())
            if 0 <= title_at < container_at:
                before = text[:title_at].rstrip()
                after = text[title_at + len(title) :].lstrip()
                if not (before.endswith(("'", "‘")) and after.startswith(("'", "’"))):
                    misses.append(
                        {
                            "code": "article-quotes",
                            "detail": (
                                f"Article title for {label} needs single quotation marks."
                            ),
                        }
                    )
    page_hits = list(_PP.finditer(text))
    printed_pages = [_norm_span(match.group(2)) for match in page_hits]
    stored_pages = re.sub(r"^pp?\.\s*", "", _text(source.get("pages")), flags=re.IGNORECASE)
    pages = _norm_span(stored_pages)
    expected = "pp." if re.search(r"[-–—,]", pages) else "p."
    if pages and container:
        # The printer writes a page range only on the journal branch. A book
        # or web line keeps the page field blank rather than inventing one.
        if pages not in printed_pages:
            shown = ", ".join(printed_pages) if printed_pages else "none"
            misses.append(
                {
                    "code": "pages",
                    "detail": (
                        f"Reference for {label} should show {expected} {pages}. It shows {shown}."
                    ),
                }
            )
        elif any(item != pages for item in printed_pages):
            extra = ", ".join(item for item in printed_pages if item != pages)
            misses.append(
                {
                    "code": "invented-pages",
                    "detail": f"Reference for {label} prints pp. {extra}, which is not a gathered page.",
                }
            )
        shown_labels = [
            match.group(1) + "."
            for match in page_hits
            if _norm_span(match.group(2)) == pages
        ]
        if expected not in shown_labels:
            shown = ", ".join(shown_labels) if shown_labels else "none"
            misses.append(
                {
                    "code": "pages-label",
                    "detail": (
                        f"Reference for {label} should show {expected} {pages}. "
                        f"It shows {shown}."
                    ),
                }
            )
    elif printed_pages and container:
        shown = ", ".join(printed_pages)
        misses.append(
            {
                "code": "invented-pages",
                "detail": f"Reference for {label} prints pp. {shown}, which is not a gathered page.",
            }
        )
    volume = _text(source.get("volume"))
    issue = _text(source.get("issue"))
    if (volume or issue) and container:
        # The printer writes the volume(issue) slot only on the journal branch.
        vol = re.sub(r"^vol(?:ume)?\.?\s*", "", volume, flags=re.IGNORECASE).strip()
        iss = re.sub(r"^(?:no\.?|issue)\s*", "", issue, flags=re.IGNORECASE).strip()
        if iss.startswith("(") and iss.endswith(")"):
            iss = iss[1:-1].strip()
        slot = f"{vol}({iss})" if vol and iss else (vol or f"({iss})")
        if slot and slot.casefold() not in text.casefold():
            misses.append(
                {
                    "code": "volume-issue",
                    "detail": f"Reference for {label} should show {slot}.",
                }
            )
    edition = _text(source.get("edition"))
    ordinal = re.search(r"\b(\d+)(st|nd|rd|th)\b", edition, re.IGNORECASE)
    if ordinal:
        wanted = f"{ordinal.group(1)}{ordinal.group(2).lower()} edn"
        if not re.search(rf"\b{wanted}\.?", text, re.IGNORECASE):
            misses.append(
                {
                    "code": "edition",
                    "detail": f"Reference for {label} should show {wanted}.",
                }
            )
    article = _text(source.get("article_number"))
    if article and container and not re.search(rf"\b{re.escape(article)}\b", text):
        misses.append(
            {
                "code": "article-number",
                "detail": f"Reference for {label} is missing article number {article}.",
            }
        )
    in_pages = _ARTICLE_IN_PAGES.search(text)
    if in_pages:
        misses.append(
            {
                "code": "article-pages",
                "detail": (
                    f"Reference for {label} prints {in_pages.group(0)}, "
                    "which is an article number, not a page."
                ),
            }
        )
    if not container:
        # A journal branch prints the volume slot, not a place or publisher.
        # A book, report, or web title is italic. A saved line may carry its
        # own title, so only the gathered title's italics are read here.
        title = _text(source.get("title"))
        if title and title.casefold() in text.casefold():
            italic = "".join(run.text or "" for run in paragraph.runs if run.italic)
            if title.casefold() not in italic.casefold():
                misses.append(
                    {
                        "code": "title-italic",
                        "detail": f"Title {title} is not italic for {label}.",
                    }
                )
        place = _text(source.get("place"))
        if place and place.casefold() not in text.casefold():
            misses.append(
                {
                    "code": "place",
                    "detail": f"Reference for {label} should show {place}.",
                }
            )
        publisher = _text(source.get("publisher"))
        if publisher and publisher.casefold() not in text.casefold():
            misses.append(
                {
                    "code": "publisher",
                    "detail": f"Reference for {label} should show {publisher}.",
                }
            )
    found_dois = [_norm_doi(item) for item in _DOI.findall(text)]
    doi = _norm_doi(_DOI_PREFIX.sub("", _text(source.get("doi"))))
    if doi:
        if doi not in found_dois:
            shown = ", ".join(found_dois) if found_dois else "none"
            misses.append(
                {
                    "code": "doi",
                    "detail": f"Reference for {label} should show doi:{doi}. It shows doi:{shown}.",
                }
            )
        elif any(item != doi for item in found_dois):
            extra = ", ".join(item for item in found_dois if item != doi)
            misses.append(
                {
                    "code": "invented-doi",
                    "detail": f"Reference for {label} prints doi:{extra}, which is not a gathered DOI.",
                }
            )
    elif found_dois:
        # A DOI is never invented, whether the entry is a journal line or a
        # book or web line. Only the journal branch used to read this.
        shown = ", ".join(found_dois)
        misses.append(
            {
                "code": "invented-doi",
                "detail": f"Reference for {label} prints doi:{shown}, which is not a gathered DOI.",
            }
        )
    misses.extend(_web_locator_misses(text, source, label, doi, container))
    return misses


def _web_locator_misses(
    text: str,
    source: dict[str, object],
    label: str,
    doi: str,
    container: str,
) -> list[dict[str, str]]:
    """A printed web address and access date must be the gathered ones."""
    misses: list[dict[str, str]] = []
    url = _text(source.get("url"))
    wanted_url = _norm_url(url)
    found_urls = [_norm_url(item) for item in _URL.findall(text)]
    url_missing = False
    if wanted_url:
        matched = [
            item
            for item in found_urls
            if item == wanted_url or (doi and (item == _norm_url(doi) or doi in item.casefold()))
        ]
        if not matched and not doi:
            url_missing = True
            shown = ", ".join(found_urls) if found_urls else "none"
            misses.append(
                {
                    "code": "url",
                    "detail": f"Reference for {label} should show {url}. It shows {shown}.",
                }
            )
        elif any(item not in matched for item in found_urls):
            printed = ", ".join(item for item in found_urls if item not in matched)
            misses.append(
                {
                    "code": "invented-url",
                    "detail": (
                        f"Reference for {label} prints {printed}, "
                        "which is not a gathered web address."
                    ),
                }
            )
    else:
        extra = [
            item
            for item in found_urls
            if not (doi and (item == _norm_url(doi) or doi in item.casefold()))
        ]
        if extra:
            shown = ", ".join(extra)
            misses.append(
                {
                    "code": "invented-url",
                    "detail": (
                        f"Reference for {label} prints {shown}, "
                        "which is not a gathered web address."
                    ),
                }
            )
    accessed = _text(source.get("accessed"))
    wanted_date = _norm_date(accessed).casefold()
    found_dates = [_norm_date(item) for item in _ACCESSED.findall(text)]
    # A place or publisher on a web entry does not cancel the access date.
    # Only a journal container keeps the line off the web branch.
    web = bool(url) and not container
    if wanted_date:
        lowered = [item.casefold() for item in found_dates]
        if wanted_date not in lowered:
            if found_dates or (web and not url_missing):
                shown = ", ".join(found_dates) if found_dates else "none"
                misses.append(
                    {
                        "code": "accessed",
                        "detail": (
                            f"Reference for {label} should show (Accessed: {accessed}). "
                            f"It shows {shown}."
                        ),
                    }
                )
        elif any(item != wanted_date for item in lowered):
            printed_date = ", ".join(
                item for item, low in zip(found_dates, lowered, strict=False) if low != wanted_date
            )
            misses.append(
                {
                    "code": "invented-accessed",
                    "detail": (
                        f"Reference for {label} prints (Accessed: {printed_date}), "
                        "which is not the gathered access date."
                    ),
                }
            )
    elif found_dates:
        shown = ", ".join(found_dates)
        misses.append(
            {
                "code": "invented-accessed",
                "detail": (
                    f"Reference for {label} prints (Accessed: {shown}), "
                    "which is not a gathered access date."
                ),
            }
        )
    return misses
