"""One citation list for a sequence, written when stage 4b finishes.

The student research notes, the writer, and the reviewer all read this list.
Each entry keeps the gathered author, year, title, and DOI, the short
in-text citation, and the full Harvard reference line. Those two forms are
stored when the entry is written. Later steps copy them. They do not compose
a second wording, and they do not correct an author or a year after the entry
exists.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer.paths import work_dir, workspace_root
from essay_writer.records import read_json, write_json
from essay_writer.textutil import _is_initial, fold_name, in_text_forms, token_allowed

_FROZEN = ("source_id", "locator", "author", "year", "title", "doi", "in_text", "reference")
_YEAR = re.compile(r"\b((?:1[0-9]{3}|20[0-9]{2})[a-z]?)\b")
_DOI = re.compile(r"10\.\d{4,9}/\S+", re.IGNORECASE)
MISSING_NOTE = "The research note for {label} is missing."
CONFLICT = "The citation list and the research note for {label} do not agree."
EMPTY_GAP = "No gathered source was saved."
NOT_WRITTEN = (
    "The citation list has not been written. The first draft waits until that list is saved."
)
NOTE_UNLISTED = (
    "A gathered research note is not on the citation list. "
    "The first draft waits until every note is listed."
)
ALREADY = "This source was already on the citation list: {label}."


def _path(essay_id: str) -> Path:
    return work_dir(essay_id) / "citation-list.json"


def _blank() -> dict[str, Any]:
    return {"written": False, "entries": []}


def _raw(essay_id: str) -> dict[str, Any]:
    data = read_json(_path(essay_id))
    if not isinstance(data, dict):
        return _blank()
    entries = data.get("entries")
    record = _blank()
    record["written"] = data.get("written") is True
    if isinstance(entries, list):
        record["entries"] = [dict(item) for item in entries if isinstance(item, dict)]
    gap = data.get("gap")
    if isinstance(gap, str):
        record["gap"] = gap
    return record


def _save(essay_id: str, record: dict[str, Any]) -> None:
    stored = {
        "written": record.get("written") is True,
        "entries": [dict(item) for item in record.get("entries") or [] if isinstance(item, dict)],
    }
    gap = record.get("gap")
    if isinstance(gap, str) and gap.strip():
        stored["gap"] = gap.strip()
    write_json(_path(essay_id), stored, mkdir=True)


def list_written(essay_id: str) -> bool:
    return _raw(essay_id).get("written") is True


def _text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def _display_surname(words: list[str]) -> str:
    kept = list(words)
    while kept and _is_initial(kept[0]):
        kept = kept[1:]
    while kept and _is_initial(kept[-1]):
        kept = kept[:-1]
    if not kept:
        return ""
    return kept[-1].rstrip(".")


def _author_groups(author: str) -> list[list[str]]:
    """Co-authors as words. The author's own hyphen character is kept."""
    text = re.sub(r"\s+et\s+al\.?$", "", author.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s+and\s+others$", "", text, flags=re.IGNORECASE)
    chunks = [
        chunk.strip()
        for chunk in re.split(r"\s*(?:&|\band\b)\s*", text, flags=re.IGNORECASE)
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


def short_in_text(author: object, year: object) -> str:
    """Short Harvard citation stored on the entry. Empty when the name or year is missing."""
    year_text = _text(year)
    author_text = _text(author)
    if not year_text or not author_text:
        return ""
    groups = _author_groups(author_text)
    if len(groups) == 1 and "," not in author_text:
        shown = " ".join(groups[0]).strip()
        if not shown:
            return ""
        return f"({shown}, {year_text})"
    surnames = [name for name in (_display_surname(words) for words in groups) if name]
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
    return f"({shown}, {year_text})"


def full_reference(source: dict[str, Any]) -> str:
    """Full Harvard line stored on the entry. The later print copies this string."""
    from essay_writer.harvard_4a import harvard_4a_line

    return harvard_4a_line(source)


def _label(entry: dict[str, Any]) -> str:
    shown = _text(entry.get("in_text"))
    if shown:
        return shown
    author = _text(entry.get("author"))
    year = _text(entry.get("year"))
    if author and year:
        return f"{author} ({year})"
    return _text(entry.get("title")) or _text(entry.get("source_id")) or "this source"


def _surnames(author: str) -> list[str]:
    return [name for name in (_display_surname(words) for words in _author_groups(author)) if name]


def _resolve_note(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return workspace_root() / raw


def review_dir(essay_id: str) -> Path:
    return work_dir(essay_id) / "output" / "reviews"


def note_files(essay_id: str) -> list[Path]:
    folder = review_dir(essay_id)
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.glob("*.md") if path.is_file())


def _read_note(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _disagreement(entry: dict[str, Any], text: str) -> str:
    """Name a conflict only when the note states a different author, year, title, or DOI.

    A note that does not repeat those fields is still the record of what was read.
    Neither side is rewritten here.
    """
    if not text.strip():
        return ""
    first = ""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            break
    years = set(_YEAR.findall(first))
    entry_year = _text(entry.get("year"))
    if entry_year and years and entry_year not in years:
        return CONFLICT.format(label=_label(entry))
    if entry_year and entry_year in years:
        families = _surnames(_text(entry.get("author")))
        folded = fold_name(first).casefold()
        if families and not any(fold_name(name).casefold() in folded for name in families):
            return CONFLICT.format(label=_label(entry))
        title = _text(entry.get("title"))
        if len(title) >= 6 and title.casefold() not in text.casefold():
            return CONFLICT.format(label=_label(entry))
    doi = _text(entry.get("doi")).casefold().rstrip(".")
    stated = [item.rstrip(".").casefold() for item in _DOI.findall(text)]
    if doi and stated and doi not in stated and not any(doi in item for item in stated):
        return CONFLICT.format(label=_label(entry))
    return ""


def _present_entry(_essay_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    shown = {key: entry.get(key, "") for key in _FROZEN}
    shown["note"] = _text(entry.get("note"))
    path = _resolve_note(shown["note"]) if shown["note"] else None
    conflict = ""
    gap = ""
    if path is None or not path.is_file():
        gap = MISSING_NOTE.format(label=_label(shown))
    else:
        conflict = _disagreement(shown, _read_note(path))
    shown["gap"] = gap
    shown["conflict"] = conflict
    shown["usable"] = not gap and not conflict
    return shown


def load_citation_list(essay_id: str) -> dict[str, Any]:
    """The shared list. Bibliographic fields stay as stored. Gaps are read, not invented."""
    record = _raw(essay_id)
    entries = [_present_entry(essay_id, item) for item in record.get("entries") or []]
    gap = _text(record.get("gap"))
    if record.get("written") is True and not entries and not gap:
        gap = EMPTY_GAP
    return {"written": record.get("written") is True, "gap": gap, "entries": entries}


def _equal_token(left: object, right: object) -> bool:
    a = _text(left)
    b = _text(right)
    if len(a) < 6 or len(b) < 6:
        return False
    if a.casefold() == b.casefold():
        return True
    sa = re.sub(r"[^a-z0-9]+", "", a.casefold())
    sb = re.sub(r"[^a-z0-9]+", "", b.casefold())
    return len(sa) >= 6 and sa == sb


def _same(entry: dict[str, Any], source: dict[str, Any]) -> bool:
    if _text(source.get("id")) and _text(source.get("id")) == _text(entry.get("source_id")):
        return True
    left_locator = _text(entry.get("locator"))
    right_locator = _text(source.get("locator"))
    if left_locator and right_locator and left_locator == right_locator:
        return True
    pairs = (
        (entry.get("doi"), source.get("doi")),
        (entry.get("title"), source.get("title")),
        (entry.get("source_id"), source.get("id")),
        (entry.get("doi"), source.get("url")),
        (source.get("doi"), entry.get("locator")),
    )
    return any(_equal_token(left, right) for left, right in pairs)


def _match(entries: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any] | None:
    for entry in entries:
        if _same(entry, source):
            return entry
    return None


def _entry_from_source(source: dict[str, Any], note: str) -> dict[str, Any]:
    author = _text(source.get("author"))
    year = _text(source.get("year"))
    return {
        "source_id": _text(source.get("id")),
        "locator": _text(source.get("locator")),
        "author": author,
        "year": year,
        "title": _text(source.get("title")),
        "doi": _text(source.get("doi")),
        "in_text": short_in_text(author, year),
        "reference": full_reference(source),
        "note": note,
    }


def _freeze(previous: dict[str, Any], note: str) -> dict[str, Any]:
    """Keep the stored citation. A later supply does not rewrite author, year, or wording."""
    kept = {key: previous.get(key, "") for key in _FROZEN}
    kept["note"] = note or _text(previous.get("note"))
    return kept


def all_gathered(essay_id: str) -> list[dict[str, Any]]:
    """Every gathered source on the summary and the full research record."""
    from essay_writer.state import load_state

    state = load_state(essay_id)
    research = state.get("research") if isinstance(state, dict) else None
    found: list[dict[str, Any]] = []
    if not isinstance(research, dict):
        return found
    for depth in ("summary", "full"):
        record = research.get(depth)
        if not isinstance(record, dict):
            continue
        sources = record.get("sources")
        if not isinstance(sources, list):
            continue
        for item in sources:
            if isinstance(item, dict) and _match(found, item) is None:
                found.append(item)
    return found


def entry_among(
    entries: list[dict[str, Any]], source: dict[str, Any]
) -> dict[str, Any] | None:
    """The entry in this batch that names the same gathered source."""
    return _match(entries, source)


def matching_entry(essay_id: str, source: dict[str, Any]) -> dict[str, Any] | None:
    """The stored entry for this source, or None when the list does not have it yet."""
    if not isinstance(source, dict):
        return None
    return _match(list(_raw(essay_id).get("entries") or []), source)


def note_file(entry: dict[str, Any] | None) -> Path | None:
    """The research note a stored entry points at."""
    if not isinstance(entry, dict):
        return None
    raw = _text(entry.get("note"))
    if not raw:
        return None
    return _resolve_note(raw)


def receive_sources(
    essay_id: str,
    sources: list[dict[str, Any]],
    notes: dict[str, str],
) -> dict[str, Any]:
    """Add gathered sources to the one list. A source already listed keeps its entry and its note.

    ``notes`` maps a source id to the research-note path written for this supply.
    An empty supply still records the list, with the gap visible.
    """
    record = _raw(essay_id)
    entries: list[dict[str, Any]] = [dict(item) for item in record.get("entries") or []]
    already: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        previous = _match(entries, source)
        note = notes.get(_text(source.get("id")), "")
        if previous is not None:
            kept_note = _text(previous.get("note")) or note
            replacement = _freeze(previous, kept_note)
            index = entries.index(previous)
            entries[index] = replacement
            already.append(ALREADY.format(label=_label(replacement)))
            continue
        ident = _text(source.get("id"))
        entries.append(_entry_from_source(source, notes.get(ident, "")))
    for source in all_gathered(essay_id):
        if _match(entries, source) is None:
            ident = _text(source.get("id"))
            entries.append(_entry_from_source(source, notes.get(ident, "")))
    gap = ""
    if not entries:
        gap = EMPTY_GAP
    saved = {"written": True, "entries": entries, "gap": gap}
    _save(essay_id, saved)
    presented = load_citation_list(essay_id)
    presented["already"] = already
    return presented


def uncovered_notes(essay_id: str) -> list[str]:
    """Research notes on disk that no list entry points at."""
    listed = {
        Path(_text(entry.get("note"))).name
        for entry in _raw(essay_id).get("entries") or []
        if _text(entry.get("note"))
    }
    return [path.name for path in note_files(essay_id) if path.name not in listed]


def unfinished_stage_reason(essay_id: str) -> str | None:
    """Stage 4b is unfinished while a gathered note has no list entry."""
    if uncovered_notes(essay_id):
        return (
            "A gathered research note is not on the citation list. "
            "This step is not finished until every note is listed."
        )
    return None


def first_write_block(essay_id: str) -> dict[str, Any] | None:
    """Refuse the first draft when the list is missing, or a note is not on it."""
    from essay_writer.confirm import refuse

    if all_gathered(essay_id) and not list_written(essay_id):
        return refuse("citation-list", NOT_WRITTEN, stored=False, advanced=False)
    if uncovered_notes(essay_id):
        return refuse("citation-list", NOTE_UNLISTED, stored=False, advanced=False)
    return None


def _usable(essay_id: str) -> list[dict[str, Any]] | None:
    """Usable entries, or None when the list has not been written.

    An empty list is returned as an empty list, so a missing source is not filled
    from a second name match.
    """
    if not list_written(essay_id):
        return None
    return [entry for entry in load_citation_list(essay_id)["entries"] if entry.get("usable") is True]


def usable_sources(essay_id: str) -> list[dict[str, Any]] | None:
    """Writer gate. Usable entries only. None when stage 4b has not written the list."""
    rows = _usable(essay_id)
    if rows is None:
        return None
    sources: list[dict[str, Any]] = []
    for entry in rows:
        sources.append(
            {
                "id": entry.get("source_id"),
                "author": entry.get("author"),
                "year": entry.get("year"),
                "title": entry.get("title"),
                "doi": entry.get("doi"),
                "locator": entry.get("locator"),
                "in_text": entry.get("in_text"),
                "reference": entry.get("reference"),
            }
        )
    return sources


def _token_matches(token: str, entry: dict[str, Any]) -> bool:
    stored = _text(entry.get("in_text"))
    inner = stored[1:-1] if stored.startswith("(") and stored.endswith(")") else stored
    if inner and fold_name(inner).casefold() == fold_name(token).casefold():
        return True
    author = _text(entry.get("author"))
    year = _text(entry.get("year"))
    if not author or not year:
        return False
    return token_allowed(token, in_text_forms(author, year))


def match_token(essay_id: str, token: str) -> dict[str, Any] | None:
    rows = _usable(essay_id)
    if rows is None:
        return None
    for entry in rows:
        if _token_matches(token, entry):
            return entry
    return None


def match_source(essay_id: str, source: dict[str, Any]) -> dict[str, Any] | None:
    if not list_written(essay_id):
        return None
    return _match(load_citation_list(essay_id)["entries"], source)


def stored_in_text(essay_id: str, source: dict[str, Any]) -> str | None:
    """The short citation stored for this source. None when the list does not list it."""
    if not list_written(essay_id):
        return None
    entry = _match([item for item in load_citation_list(essay_id)["entries"] if item.get("usable")], source)
    if entry is None:
        return None
    text = _text(entry.get("in_text"))
    return text or None


def stored_reference_lines(
    essay_id: str,
    sources: list[object],
    pack: dict[str, object],
) -> list[str] | None:
    """Reference lines for citations actually used, copied from the list.

    None when the list has not been written, so an older file keeps its own lines.
    """
    if not list_written(essay_id):
        return None
    from essay_writer.textutil import citation_tokens

    tokens: list[str] = []
    sections = pack.get("sections") if isinstance(pack, dict) else None
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            body = section.get("body")
            if isinstance(body, str):
                tokens.extend(citation_tokens(body))
    lines: list[str] = []
    seen: set[str] = set()
    if tokens:
        for token in tokens:
            entry = match_token(essay_id, token)
            line = _text(entry.get("reference")) if entry else ""
            if line and line not in seen:
                seen.add(line)
                lines.append(line)
        return lines
    for source in sources:
        if not isinstance(source, dict):
            continue
        entry = match_source(essay_id, source)
        if entry is None or entry.get("usable") is not True:
            continue
        line = _text(entry.get("reference"))
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    if lines:
        return lines
    return None


def reviewer_sources(essay_id: str) -> list[dict[str, Any]] | None:
    """The same entries the writer uses. None when the list has not been written."""
    return usable_sources(essay_id)


def research_note_for(essay_id: str, source_id: str, *, seat: str) -> dict[str, Any]:
    """Read the note an entry points at. The writer and the reviewer do not create one."""
    del seat
    presented = load_citation_list(essay_id)
    found = None
    for entry in presented["entries"]:
        if _text(entry.get("source_id")) == source_id.strip():
            found = entry
            break
    if found is None:
        return {"found": False, "text": "", "gap": "", "invented": False}
    path = _resolve_note(_text(found.get("note"))) if _text(found.get("note")) else None
    return {
        "found": True,
        "text": _read_note(path),
        "gap": _text(found.get("gap")),
        "conflict": _text(found.get("conflict")),
        "usable": found.get("usable") is True,
        "invented": False,
    }


def attach_note(essay_id: str, source_id: str, prose: str) -> dict[str, Any]:
    """Point the existing entry at a note the caller wrote. Author and year stay as stored."""
    record = _raw(essay_id)
    entries = [dict(item) for item in record.get("entries") or []]
    target = None
    for entry in entries:
        if _text(entry.get("source_id")) == source_id.strip():
            target = entry
            break
    if target is None:
        from essay_writer.confirm import refuse

        return refuse(
            "citation-list",
            "That source is not on the citation list. Nothing was written.",
            wrote=False,
        )
    note = _text(target.get("note"))
    if not note:
        from essay_writer.confirm import refuse

        return refuse(
            "citation-list",
            "That list entry has no research note to point at. Nothing was written.",
            wrote=False,
        )
    path = _resolve_note(note)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prose if prose.endswith("\n") else prose + "\n", encoding="utf-8")
    _save(essay_id, {"written": True, "entries": entries, "gap": record.get("gap") or ""})
    shown = load_citation_list(essay_id)
    shown["wrote"] = True
    shown["invented"] = False
    return shown


def student_list_text(essay_id: str) -> str:
    """Plain list for the research notes the student already receives."""
    presented = load_citation_list(essay_id)
    lines = ["Citation list"]
    entries = presented["entries"]
    if not entries:
        lines.append(_text(presented.get("gap")) or EMPTY_GAP)
        return "\n".join(lines)
    for entry in entries:
        in_text = _text(entry.get("in_text"))
        reference = _text(entry.get("reference"))
        if in_text:
            lines.append(in_text)
        if reference:
            lines.append(reference)
        note_name = Path(_text(entry.get("note"))).name if _text(entry.get("note")) else ""
        if note_name:
            lines.append(f"Research note: {note_name}")
        elif _text(entry.get("source_id")):
            lines.append(f"Research note: {_text(entry.get('source_id'))}")
        if _text(entry.get("gap")):
            lines.append(_text(entry.get("gap")))
        if _text(entry.get("conflict")):
            lines.append(_text(entry.get("conflict")))
    return "\n".join(lines)


def already_note(labels: list[str]) -> str:
    return " ".join(label for label in labels if label).strip()
