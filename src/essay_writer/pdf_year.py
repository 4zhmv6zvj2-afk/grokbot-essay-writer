"""Publication year from the opened PDF's own cite line.

The year is the one on the please-cite line, or the article's own
author and year on the first page. A year that belongs only to a work
that article cites is not the publication year. The first year token
in the file is not enough. The file's modified time is not a year.
This module does not read it.
"""

from __future__ import annotations

import re
from pathlib import Path

_YEAR = r"1[6-9]\d{2}|20\d{2}"
_WORD = r"[A-Z][A-Za-z'’\-]+"
_NAME = rf"{_WORD}(?:\s+{_WORD})*"
_NAMES = rf"{_NAME}(?:\s+(?:and|&)\s+{_NAME})*"
_INITIALS = r"[A-Z](?:\.\s*[A-Z])*\.?"
_PLEASE = re.compile(
    r"please\s+cite(?:\s+this\s+article)?\s+as:\s*",
    re.IGNORECASE,
)
_PLEASE_AUTHOR = re.compile(r"^([A-Z][A-Za-z'’\-]+),\s*[A-Z]")
_CITE = re.compile(
    rf"(?<![A-Za-z'’\-])(?P<who>{_NAMES})"
    rf"(?:,\s*(?P<initials>{_INITIALS}))?"
    rf"\s*\((?P<year>{_YEAR})[a-z]?(?P<close>\))?"
    rf"(?P<after>\s*[A-Za-z][A-Za-z'’\-]*)?"
)
_PAREN_YEAR = re.compile(rf"\(({_YEAR})[a-z]?\)?")
_BYLINE = re.compile(rf"^{_NAME}$")
_AND = re.compile(r"\s+and\s+|\s*&\s*", re.IGNORECASE)
_DOWNLOAD = re.compile(r"(?i)\b(?:downloaded|download|retrieved)\b")
_VOLUME_YEAR = re.compile(rf"(?<!\d)\d{{1,3}}\s*\((?P<year>{_YEAR})[a-z]?\)")
_LOWER_WORD = re.compile(r"\b[a-z][a-z'’\-]{3,}\b")


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _keys(who: str) -> set[str]:
    keys: set[str] = set()
    for part in _AND.split(who.strip()):
        tokens = [token.strip(".,") for token in part.split() if token.strip(".,")]
        if tokens:
            keys.add(tokens[-1].casefold())
    return keys


def _please_body(flat: str) -> str | None:
    """The please-cite citation, stopping before the next sentence."""
    match = _PLEASE.search(flat)
    if match is None:
        return None
    rest = flat[match.end() : match.end() + 220]
    cut = re.search(r"(?<![A-Z])\.\s+", rest)
    if cut:
        rest = rest[: cut.start()]
    return rest


def _year_in(body: str) -> str | None:
    """A parenthetical year. A cut-off PDF string may omit the closing paren."""
    for match in _PAREN_YEAR.finditer(body):
        if match.group(0).endswith(")"):
            return match.group(1)
        if not body[match.end() :].strip():
            return match.group(1)
    return None


def _download_cite(flat: str, start: int) -> bool:
    """True when this year sits in a download or retrieval clause."""
    window = flat[max(0, start - 80) : start]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut >= 0:
        window = window[cut + 2 :]
    return _DOWNLOAD.search(window) is not None


def _header_cites(flat: str) -> list[tuple[set[str], str]]:
    """Author+year cite lines. A lowercase word after the year is a cited work."""
    found: list[tuple[set[str], str]] = []
    for match in _CITE.finditer(flat):
        after = (match.group("after") or "").strip()
        if match.group("close") is None and after:
            continue
        if after and after[0].islower():
            continue
        if _download_cite(flat, match.start()):
            continue
        found.append((_keys(match.group("who")), match.group("year")))
    return found


def _header_volume_year(first_page: str) -> str | None:
    """Volume (year) printed in the page title or header. A download stamp is not one."""
    years: list[str] = []
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    if not lines and first_page.strip():
        lines = [first_page.strip()]
    for line in lines[:8]:
        cut = _DOWNLOAD.search(line)
        if cut:
            line = line[: cut.start()]
        if not line.strip() or _LOWER_WORD.search(line):
            continue
        for match in _VOLUME_YEAR.finditer(line):
            years.append(match.group("year"))
    unique = list(dict.fromkeys(years))
    if len(unique) == 1:
        return unique[0]
    return None


def _one_year(cites: list[tuple[set[str], str]], surnames: set[str]) -> str | None:
    if not surnames:
        return None
    years = list(dict.fromkeys(year for keys, year in cites if keys & surnames))
    if len(years) == 1:
        return years[0]
    return None


def _byline_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip().strip(".")
        if not line or _PLEASE.search(line):
            continue
        if _BYLINE.match(line) is None:
            continue
        keys.add(line.split()[-1].casefold())
    return keys


def _please_surnames(body: str) -> set[str]:
    match = _PLEASE_AUTHOR.match(body.strip())
    if match is None:
        return set()
    return {match.group(1).casefold()}


def publication_year(first_page: str) -> str | None:
    """Year on this file's own cite line.

    A please-cite line supplies the year when it prints one. Otherwise the
    year is the article author's own author+year on the first page, or the
    year printed beside the volume in the page title or header. A download
    date, a file timestamp, and a year that belongs only to a cited work
    are left off. No year is invented when the page prints none.
    """
    if not isinstance(first_page, str) or not first_page.strip():
        return None
    flat = _flat(first_page)
    body = _please_body(flat)
    if body is not None:
        year = _year_in(body)
        if year:
            return year
        return _one_year(_header_cites(flat), _please_surnames(body))
    cites = _header_cites(flat)
    years = list(dict.fromkeys(year for _names, year in cites))
    if len(years) == 1:
        return years[0]
    if len(years) > 1:
        return _one_year(cites, _byline_keys(first_page))
    return _header_volume_year(first_page)


def citation_year(path: Path, essay_id: str | None = None) -> str | None:
    """Publication year of an opened PDF. File mtime is not consulted."""
    from essay_writer.cite_open import open_for_citation

    return open_for_citation(path, essay_id).year


def apply_citation_year(source: dict[str, object], pdf_path: Path | None) -> dict[str, object]:
    """Keep a year only when the opened PDF's own cite line prints it.

    A year taken from the file's modified time is dropped when that cite
    line does not print a year. A cited work's year is not copied onto
    this source. This does not invent a year the page omits.
    """
    updated = dict(source)
    if pdf_path is None:
        return updated
    found = citation_year(pdf_path)
    if found:
        updated["year"] = found
        return updated
    updated.pop("year", None)
    return updated
