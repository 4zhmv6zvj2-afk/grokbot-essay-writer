"""One source identity and one record shape.

This module is pure. It imports nothing from the rest of the package.
A stored id is kept. A new id is minted from a DOI, then from the author,
title, and year, then from the file locator. ``same_source`` is that
identity: an id, then a canonical DOI, then the normalized title, year,
and author. A title on its own is not enough. A catalog filename overlap
is a separate check and is not this identity.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

TOKEN_MIN = 6
_ID_LIMIT = 80
_TITLE_KEEP = 48

LOOKUP = "lookup"
FILE = "file"
OPENED = "opened"
NOTE = "note"
BLANK = ""
_KNOWN_MARKS = frozenset({LOOKUP, FILE, OPENED, NOTE, BLANK})

BIBLIO_FIELDS = (
    "author",
    "title",
    "year",
    "container",
    "volume",
    "issue",
    "pages",
    "doi",
    "url",
    "accessed",
    "publisher",
    "place",
    "edition",
)
FILE_BIBLIO_FIELDS = ("author", "title", "year", "edition")
LOOKUP_KEPT = (
    "author",
    "title",
    "year",
    "doi",
    "volume",
    "issue",
    "pages",
    "url",
    "publisher",
    "place",
    "container",
    "accessed",
)
ABSTRACT_KEPT = ("author", "year", "title", "doi")
PDF_LOOKUP_FIELDS = ABSTRACT_KEPT
ABSTRACT_FIELDS = (
    "author",
    "year",
    "title",
    "doi",
    "oa_url",
    "pdf_url",
    "journal",
    "pages",
    "volume",
    "url",
)

_SUPPLIED = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")
_DOI_URL = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)
_DOI_LABEL = re.compile(r"^doi:\s*", re.IGNORECASE)
_FLOOR_DOI = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)
_YEAR_TAIL = r"\d{4}[a-z]?"


def text(value: object) -> str:
    """String form of a stored field. Booleans and other objects are blank."""
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def canonical_doi(value: object) -> str:
    """DOI with the URL and ``doi:`` label removed, trailing dot dropped, case folded."""
    raw = text(value)
    if not raw:
        return ""
    raw = _DOI_URL.sub("", raw)
    raw = _DOI_LABEL.sub("", raw)
    return raw.strip().rstrip(".").casefold()


def doi_key(value: object) -> str:
    """DOI key used when counting distinct works. A non-string is blank."""
    if not isinstance(value, str):
        return ""
    return _FLOOR_DOI.sub("", value.strip()).casefold()


def fold_piece(value: str) -> str:
    """Letters and digits only, for a title or an author comparison."""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def slug(value: object) -> str:
    """Letters and digits run together. A non-string is blank."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _fold_name(value: str) -> str:
    return value.replace("\u2019", "'").replace("\u2018", "'").replace("\u2010", "-")


def _is_initial(token: str) -> bool:
    bare = token.rstrip(".")
    return len(bare) == 1 and bare.isalpha() and bare[0].isupper()


def family_name(author: str) -> str:
    """The text before a comma, with the spacing collapsed."""
    return re.sub(r"\s+", " ", author.split(",", 1)[0]).strip()


def family_token(author: str) -> str:
    """The text before a comma, stripped, for a rejected-name comparison."""
    return text(author).split(",", 1)[0].strip()


def surname(author: str) -> str:
    """The last word of the family name. A blank author is blank."""
    if not author:
        return ""
    family = family_name(author)
    if not family:
        return ""
    return family.split()[-1]


def author_year_present(body: str, family: str, year: str) -> bool:
    """True when the year is the first bracket after that family name."""
    if not family or not year:
        return False
    pattern = (
        rf"\b{re.escape(_fold_name(family))}\b[^()\n]*"
        rf"\(\s*{re.escape(year)}[a-z]?\s*\)"
    )
    return re.search(pattern, _fold_name(body), re.IGNORECASE) is not None


def author_text(record: Mapping[str, Any]) -> str:
    """Joined author string. A list of names uses ``and`` between them."""
    authors = record.get("authors")
    if isinstance(authors, list):
        names = [item.strip() for item in authors if isinstance(item, str) and item.strip()]
        if names:
            return " and ".join(names)
    author = record.get("author")
    if isinstance(author, str) and author.strip():
        return author.strip()
    return ""


def year_text(record: Mapping[str, Any]) -> str:
    """A calendar year. Anything that is not a whole number is blank."""
    year = record.get("year")
    if isinstance(year, bool):
        return ""
    if isinstance(year, int):
        return str(year)
    if isinstance(year, str) and year.strip().isdigit():
        return year.strip()
    return ""


def title_text(record: Mapping[str, Any]) -> str:
    title = record.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return ""


def _field_map(record: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = record.get("field_sources")
    if isinstance(raw, Mapping):
        return raw
    return {}


def field_value(record: Mapping[str, Any], field: str) -> str:
    """Stored text of one field. Blank when the field is missing or not text."""
    if field == "author" and not text(record.get("author")):
        return author_text(record)
    return text(record.get(field))


def field_is_known(record: Mapping[str, Any], field: str) -> bool:
    """True when the field has text and the record is not in conflict.

    A blank value is unknown. A conflict on the record makes the field
    unknown. A provenance of lookup, file, opened, or note is known, and so
    is a value that was stored with no provenance mark.
    """
    if text(record.get("conflict")):
        return False
    if not field_value(record, field):
        return False
    mark = _field_map(record).get(field, BLANK)
    if not isinstance(mark, str):
        return False
    return mark in _KNOWN_MARKS


@dataclass(frozen=True)
class SourceRecord:
    """One stored work. Provenance is ``(field, mark)`` pairs."""

    source_id: str = ""
    doi: str = ""
    authors: tuple[str, ...] = ()
    year: str = ""
    title: str = ""
    locator: str = ""
    origin: str = ""
    gathered: bool = False
    fields: tuple[tuple[str, str], ...] = ()
    conflict: str = ""


def _authors(record: Mapping[str, Any]) -> tuple[str, ...]:
    raw = record.get("authors")
    if isinstance(raw, list):
        names = tuple(item.strip() for item in raw if isinstance(item, str) and item.strip())
        if names:
            return names
    author = author_text(record)
    if author:
        return (author,)
    return ()


def _provenance(record: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    for key, value in _field_map(record).items():
        if isinstance(key, str) and isinstance(value, str):
            found.append((key, value))
    return tuple(found)


def as_record(record: SourceRecord | Mapping[str, Any]) -> SourceRecord:
    """The record view of a stored mapping. A record is returned as itself."""
    if isinstance(record, SourceRecord):
        return record
    if not isinstance(record, Mapping):
        return SourceRecord()
    return SourceRecord(
        source_id=text(record.get("source_id")),
        doi=text(record.get("doi")),
        authors=_authors(record),
        year=year_text(record) or text(record.get("year")),
        title=title_text(record),
        locator=text(record.get("locator")).replace("\\", "/"),
        origin=text(record.get("origin")),
        gathered=record.get("gathered") is True,
        fields=_provenance(record),
        conflict=text(record.get("conflict")),
    )


def _mapping(record: SourceRecord | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(record, SourceRecord):
        data: dict[str, Any] = {
            "source_id": record.source_id,
            "id": record.source_id,
            "doi": record.doi,
            "authors": list(record.authors),
            "year": record.year,
            "title": record.title,
            "locator": record.locator,
            "origin": record.origin,
            "gathered": record.gathered,
            "conflict": record.conflict,
        }
        if record.authors:
            data["author"] = " and ".join(record.authors)
        if record.fields:
            data["field_sources"] = dict(record.fields)
        return data
    if isinstance(record, Mapping):
        return record
    return {}


def valid_source_id(value: object) -> str:
    """The supplied id when it is safe to persist, otherwise empty."""
    raw = text(value)
    if not _SUPPLIED.fullmatch(raw):
        return ""
    if ".." in raw.split("/"):
        return ""
    return raw


def _title_token(title: str) -> str:
    if len(title) <= _TITLE_KEEP:
        return title
    return hashlib.sha256(title.encode()).hexdigest()[:20]


def _fit_work(author: str, title: str, year: str) -> str:
    body = f"{author}|{_title_token(title)}|{year}"
    ident = f"work:{body}"
    if len(ident) <= _ID_LIMIT:
        return ident
    return "work:" + hashlib.sha256(body.encode()).hexdigest()[:24]


def _ids_author(record: Mapping[str, Any]) -> str:
    authors = record.get("authors")
    if isinstance(authors, list):
        names = [item.strip() for item in authors if isinstance(item, str) and item.strip()]
        if names:
            return " and ".join(names)
    return text(record.get("author"))


def _ids_year(record: Mapping[str, Any]) -> str:
    year = record.get("year")
    if isinstance(year, bool) or year is None:
        return ""
    if isinstance(year, int):
        return str(year)
    raw = text(year)
    return raw if raw.isdigit() else ""


def stable_source_id(record: Mapping[str, Any]) -> str:
    """Id of this work. Empty when the record has nothing stable to name.

    A DOI is the id. Without a DOI, the author, title, and year are the id.
    A long title is hashed so the filename stays short. A file locator is
    next. List position is never an id. A supplied id is not read here.
    """
    if not isinstance(record, dict):
        return ""
    doi = canonical_doi(record.get("doi"))
    if doi:
        return "doi:" + doi
    title = fold_piece(text(record.get("title")))
    year = _ids_year(record)
    author = fold_piece(_ids_author(record))
    if title and year and author:
        return _fit_work(author, title, year)
    locator = text(record.get("locator")).replace("\\", "/")
    if locator:
        return "loc:" + locator.casefold()
    return ""


def mint_source_id(record: SourceRecord | Mapping[str, Any]) -> str:
    """The id to store. A stored id is kept. A valid supplied id is kept.

    Anything else is minted. Minting does not replace an id already on the
    record. The caller still prefers an id already written to disk.
    """
    data = _mapping(record)
    view = as_record(data)
    if view.source_id:
        return view.source_id
    supplied = valid_source_id(data.get("id"))
    if supplied:
        return supplied
    minted = stable_source_id(data)
    if minted:
        return minted
    locator = text(data.get("locator")).replace("\\", "/")
    if locator:
        return "loc:" + locator.casefold()
    return ""


def _identity_keys(record: Mapping[str, Any]) -> list[str]:
    keys: list[str] = []
    for field in ("source_id", "id"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            keys.append("id:" + value.strip())
            break
    doi = doi_key(record.get("doi"))
    if doi:
        keys.append("doi:" + doi)
    title = fold_piece(title_text(record))
    year = year_text(record)
    author = fold_piece(author_text(record))
    if title and year and author:
        keys.append(f"tya:{title}|{year}|{author}")
    return keys


def work_key(record: Mapping[str, Any]) -> str | None:
    """None when author, title, or year is missing. Otherwise one identity token."""
    if not isinstance(record, dict):
        return None
    if not title_text(record) or not year_text(record) or not author_text(record):
        return None
    keys = _identity_keys(record)
    return keys[0] if keys else None


def distinct_works(records: list[Any]) -> list[dict[str, Any]]:
    """Countable works, first occurrence kept.

    The same source id is one work. The same DOI is one work. A DOI record
    and a no-DOI record with the same normalized title, year, and author are
    one work. Two works that share a title and a year and name different
    authors stay two. Two different DOIs stay two.
    """
    countable = [record for record in records if isinstance(record, dict) and work_key(record)]
    parent = list(range(len(countable)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    by_key: dict[str, int] = {}
    for index, record in enumerate(countable):
        for key in _identity_keys(record):
            if key.startswith("tya:"):
                continue
            previous = by_key.get(key)
            if previous is None:
                by_key[key] = index
            else:
                union(index, previous)
    grouped: dict[str, list[int]] = {}
    for index, record in enumerate(countable):
        for key in _identity_keys(record):
            if key.startswith("tya:"):
                grouped.setdefault(key, []).append(index)
    for indexes in grouped.values():
        with_doi = [index for index in indexes if doi_key(countable[index].get("doi"))]
        without_doi = [index for index in indexes if index not in with_doi]
        for index in without_doi[1:]:
            union(without_doi[0], index)
        distinct_dois = {doi_key(countable[index].get("doi")) for index in with_doi}
        if len(distinct_dois) == 1 and without_doi:
            union(with_doi[0], without_doi[0])
    kept: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, record in enumerate(countable):
        root = find(index)
        if root in seen:
            continue
        seen.add(root)
        kept.append(record)
    return kept


def _id_set(record: Mapping[str, Any]) -> set[str]:
    found: set[str] = set()
    for field in ("source_id", "id"):
        value = text(record.get(field))
        if value:
            found.add(value)
    return found


def _tya(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        fold_piece(title_text(record)),
        year_text(record),
        fold_piece(author_text(record)),
    )


def same_source(
    left: SourceRecord | Mapping[str, Any],
    right: SourceRecord | Mapping[str, Any],
) -> bool:
    """True when both sides name one work.

    An id matches first, then a locator, then a canonical DOI. A normalized
    title, year, and author match when the two DOIs do not disagree. A title
    on its own does not match. Two different DOIs stay two works.
    """
    one = _mapping(left)
    other = _mapping(right)
    one_view = as_record(one)
    other_view = as_record(other)
    if one_view.source_id and one_view.source_id == other_view.source_id:
        return True
    left_ids = _id_set(one)
    right_ids = _id_set(other)
    if left_ids and right_ids and left_ids & right_ids:
        return True
    left_locator = text(one.get("locator"))
    right_locator = text(other.get("locator"))
    if left_locator and right_locator and left_locator == right_locator:
        return True
    left_doi = canonical_doi(one.get("doi"))
    right_doi = canonical_doi(other.get("doi"))
    if left_doi and right_doi:
        return left_doi == right_doi
    title, year, author = _tya(one)
    if title and year and author and (title, year, author) == _tya(other):
        return True
    return False


def _equal_token(left: object, right: object) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    one = left.strip()
    other = right.strip()
    if len(one) < TOKEN_MIN or len(other) < TOKEN_MIN:
        return False
    if one.casefold() == other.casefold():
        return True
    folded_one = slug(one)
    folded_other = slug(other)
    return len(folded_one) >= TOKEN_MIN and folded_one == folded_other


def token_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """True when a doi, url, title, or id token overlaps.

    This is the opened-file check. It is not ``same_source``. A short token
    does not match.
    """
    for key in ("doi", "url", "title", "id"):
        if _equal_token(left.get(key), right.get(key)):
            return True
    for record, other in ((left, right), (right, left)):
        doi = record.get("doi")
        url = other.get("url")
        if not isinstance(doi, str) or not isinstance(url, str):
            continue
        token = slug(doi)
        if len(token) >= TOKEN_MIN and token in slug(url):
            return True
    return False


def display_surname(words: list[str]) -> str:
    """Family-name word with leading and trailing initials removed."""
    kept = list(words)
    while kept and _is_initial(kept[0]):
        kept = kept[1:]
    while kept and _is_initial(kept[-1]):
        kept = kept[:-1]
    if not kept:
        return ""
    return kept[-1].rstrip(".")


def author_groups(author: str) -> list[list[str]]:
    """Co-authors as words. The author's own hyphen character is kept."""
    raw = re.sub(r"\s+et\s+al\.?$", "", author.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s+and\s+others$", "", raw, flags=re.IGNORECASE)
    chunks = [
        chunk.strip()
        for chunk in re.split(r"\s*(?:&|\band\b)\s*", raw, flags=re.IGNORECASE)
        if chunk.strip()
    ]
    people: list[list[str]] = []
    for chunk in chunks:
        current: list[str] = []
        for part in [piece.strip() for piece in chunk.split(",") if piece.strip()]:
            words = [word for word in part.split() if word]
            if words and all(_is_initial(word) for word in words):
                current.extend(words)
                continue
            if current:
                people.append(current)
            current = words
        if current:
            people.append(current)
    return people


def short_form(record: SourceRecord | Mapping[str, Any]) -> str:
    """Short Harvard citation. Empty when the name or the year is missing."""
    data = _mapping(record)
    if isinstance(record, SourceRecord):
        author = " and ".join(record.authors)
        year = record.year
    else:
        author = text(data.get("author"))
        year = text(data.get("year"))
    if not year or not author:
        return ""
    groups = author_groups(author)
    if len(groups) == 1 and "," not in author:
        shown = " ".join(groups[0]).strip()
        if not shown:
            return ""
        return f"({shown}, {year})"
    surnames = [name for name in (display_surname(words) for words in groups) if name]
    if not surnames:
        return ""
    if len(surnames) >= 4:
        shown = f"{surnames[0]} et al."
    elif len(surnames) == 2:
        shown = f"{surnames[0]} and {surnames[1]}"
    elif len(surnames) > 2:
        shown = ", ".join(surnames[:-1]) + " and " + surnames[-1]
    else:
        shown = surnames[0]
    return f"({shown}, {year})"


def part_names(source_id: str) -> dict[str, str]:
    """The opened file, the note, and the list entry, named with the role at the back."""
    ident = source_id.strip()
    return {
        "part_source": f"{ident}:source",
        "part_note": f"{ident}:note",
        "part_list": f"{ident}:list",
    }


def token_matches(token: str, entry: Mapping[str, Any]) -> bool:
    """True only when the token is the short form stored on this entry."""
    stored = text(entry.get("in_text"))
    inner = stored[1:-1] if stored.startswith("(") and stored.endswith(")") else stored
    if not inner:
        return False
    left = _fold_name(inner).casefold().rstrip(".")
    right = _fold_name(token).casefold().rstrip(".")
    return bool(left) and left == right


def identifier_keys(entry: Mapping[str, Any]) -> set[str]:
    """Source id and DOI keys long enough to name one stored work."""
    keys: set[str] = set()
    source_id = text(entry.get("source_id")).casefold()
    if source_id:
        keys.add(source_id)
        keys.update(name.casefold() for name in part_names(source_id).values())
    doi = text(entry.get("doi")).casefold().rstrip(".")
    if doi:
        keys.add(doi)
        keys.add(f"doi:{doi}")
    return {key for key in keys if len(key) >= TOKEN_MIN}


def _short_inner(entry: Mapping[str, Any]) -> str:
    stored = text(entry.get("in_text"))
    if stored.startswith("(") and stored.endswith(")"):
        return stored[1:-1]
    return stored


def stored_for_part(
    part: str,
    rows: Sequence[dict[str, Any]],
    wording_matches: Callable[[str, dict[str, Any]], bool],
) -> str | None:
    """The stored short form for this parenthesis part.

    A source id is exact. The stored short form is next, and it beats a
    co-author wording. Another wording is used only when it names exactly
    one stored form. The research-note heading is not read.
    """
    folded = re.sub(r"\s+", " ", part).strip().casefold().rstrip(".")
    exact = list(
        dict.fromkeys(
            _short_inner(entry)
            for entry in rows
            if _short_inner(entry) and token_matches(folded, entry)
        )
    )
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return None
    bare = folded.removeprefix("doi:").strip()
    hits: list[str] = []
    for entry in rows:
        inner = _short_inner(entry)
        if not inner:
            continue
        keys = identifier_keys(entry)
        matched = folded in keys or bare in keys
        if not matched:
            for key in keys:
                if re.fullmatch(re.escape(key) + rf"(?:,\s*{_YEAR_TAIL})?", bare):
                    matched = True
                    break
        if matched:
            hits.append(inner)
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    if len(unique) > 1:
        return None
    wordings = [
        _short_inner(entry)
        for entry in rows
        if _short_inner(entry) and wording_matches(folded, entry)
    ]
    wordings = list(dict.fromkeys(wordings))
    if len(wordings) == 1:
        return wordings[0]
    return None
