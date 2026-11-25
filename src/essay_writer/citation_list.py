"""One citation list for a sequence, written when stage 4b finishes.

The student research notes, the writer, and the reviewer all read this list.
Each entry keeps the gathered author, year, title, and DOI, the short
in-text citation, and the full Harvard reference line. Those two forms are
stored when the entry is written. Later steps copy them. They do not compose
a second wording. A newer uploaded file is the exception: the opened source,
the research note, and the citation list all take the new source id, DOI,
author, year, and title, and the stored short form is taken from that refresh.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer.durable import replace_text
from essay_writer.paths import work_dir, workspace_root
from essay_writer.records import read_json, write_json
from essay_writer.sources import (
    identifier_keys,
    part_names,
    same_source,
    short_form,
    stored_for_part,
    token_matches,
)
from essay_writer.textutil import (
    PAREN,
    fold_name,
    in_text_forms,
    token_allowed,
)

# Fields the Harvard line is built from. The list keeps them so a later check
# reads the same journal, report, or plan the line was printed from.
_PRINT_FIELDS = (
    "container",
    "place",
    "publisher",
    "volume",
    "issue",
    "pages",
    "url",
    "accessed",
    "edition",
    "article_number",
)
_FROZEN = (
    "source_id",
    "locator",
    "author",
    "year",
    "title",
    "doi",
    "in_text",
    "reference",
    *_PRINT_FIELDS,
)
_OFFICIAL = ("source_id", "doi", "author", "year", "title")
MISSING_NOTE = "The research note for {label} is missing."
FIELD_CONFLICT = (
    "The stored details for {label} do not agree across the opened source, "
    "the research note, and the citation list."
)
NOTE_DETAIL_GAP = "The research note for {label} is missing a stored detail."
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


def short_in_text(author: object, year: object) -> str:
    """Short Harvard citation stored on the entry. Empty when the name or year is missing."""
    return short_form({"author": author, "year": year})


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


def _norm_official(value: str, key: str) -> str:
    text = re.sub(r"\s+", " ", value).strip().casefold()
    if key == "doi":
        return text.rstrip(".")
    return text


def _official_from_source(source: dict[str, Any]) -> dict[str, str]:
    return {
        "source_id": _text(source.get("id")),
        "doi": _text(source.get("doi")),
        "author": _text(source.get("author")),
        "year": _text(source.get("year")),
        "title": _text(source.get("title")),
    }


def _official_from_entry(entry: dict[str, Any]) -> dict[str, str]:
    return {key: _text(entry.get(key)) for key in _OFFICIAL}


def _note_record_path(note_raw: str) -> Path | None:
    """The note's own record. It is not stored inside the citation list."""
    if not note_raw.strip():
        return None
    path = _resolve_note(note_raw)
    return path.with_name(f"{path.stem}.record.json")


def _source_record_path(essay_id: str, source_id: str) -> Path | None:
    """The opened source's own record. It is not stored inside the citation list."""
    ident = source_id.strip().replace("\\", "_").replace("/", "_")
    if not ident or ident in {".", ".."}:
        return None
    return work_dir(essay_id) / "output" / "source-records" / f"{ident}.record.json"


def _present_official(data: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {key: _text(data.get(key)) for key in _OFFICIAL if key in data}


def _file_digest(locator: str) -> str:
    if not locator.strip():
        return ""
    path = _resolve_note(locator)
    if not path.is_file():
        return ""
    try:
        from essay_writer.canon import file_sha256

        return file_sha256(path)
    except OSError:
        return ""


def _source_payload(official: dict[str, str], locator: str, digest: str) -> dict[str, str]:
    body = {key: _text(official.get(key)) for key in _OFFICIAL}
    body["locator"] = locator
    body["file_sha256"] = digest
    return body


def _ensure_note_record(note_raw: str, official: dict[str, str]) -> None:
    """Store the note's own copy when the note is written.

    A later heading is not read, and a stored field is not replaced from it.
    """
    record_path = _note_record_path(note_raw)
    if record_path is None:
        return
    current = read_json(record_path)
    data = current if isinstance(current, dict) else {}
    stored: dict[str, str] = {}
    changed = not record_path.is_file()
    for key in _OFFICIAL:
        if key in data:
            stored[key] = _text(data.get(key))
            continue
        stored[key] = _text(official.get(key))
        changed = True
    if changed:
        write_json(record_path, stored, mkdir=True)


def _ensure_source_record(essay_id: str, source: dict[str, Any]) -> None:
    """Store the opened source's own copy once. A later edit does not move it."""
    path = _source_record_path(essay_id, _text(source.get("id")))
    if path is None or path.is_file():
        return
    locator = _text(source.get("locator"))
    payload = _source_payload(_official_from_source(source), locator, _file_digest(locator))
    write_json(path, payload, mkdir=True)


def _load_source_record(essay_id: str, source_id: str) -> dict[str, Any] | None:
    path = _source_record_path(essay_id, source_id)
    if path is None or not path.is_file():
        return None
    data = read_json(path)
    return data if isinstance(data, dict) else None


def _opened_source(essay_id: str, entry: dict[str, Any]) -> dict[str, Any] | None:
    """The opened source for this entry. Heading text is not used.

    The source id is the link. A stored id that no longer matches is still the
    opened file when the locator is the one on the list, so that id can disagree.
    """
    source_id = _text(entry.get("source_id"))
    locator = _text(entry.get("locator"))
    found_id = None
    found_locator = None
    for source in all_gathered(essay_id):
        if source_id and _text(source.get("id")) == source_id and found_id is None:
            found_id = source
        if locator and _text(source.get("locator")) == locator and found_locator is None:
            found_locator = source
    if found_locator is not None and _text(found_locator.get("id")) != source_id:
        return found_locator
    if found_id is not None:
        return found_id
    return found_locator


def _refresh_official(entry: dict[str, Any], opened: dict[str, Any]) -> dict[str, str]:
    """Official fields for a newer file. The note heading is not read."""
    official = _official_from_source(opened)
    if not official["source_id"]:
        official["source_id"] = _text(entry.get("source_id"))
    return official


def _store_source_official(
    essay_id: str,
    official: dict[str, str],
    locator: str,
    digest: str,
) -> bool:
    path = _source_record_path(essay_id, official["source_id"])
    if path is None:
        return False
    write_json(path, _source_payload(official, locator, digest), mkdir=True)
    return True


def _store_note_official(note_raw: str, official: dict[str, str]) -> bool:
    record_path = _note_record_path(note_raw)
    if record_path is None:
        return False
    write_json(record_path, {key: official[key] for key in _OFFICIAL}, mkdir=True)
    return True


def _store_list_official(
    essay_id: str,
    entry: dict[str, Any],
    official: dict[str, str],
    opened: dict[str, Any],
    locator: str,
) -> dict[str, str] | None:
    """Write the list's own copy, including the short form taken from the refresh."""
    record = _raw(essay_id)
    entries = [dict(item) for item in record.get("entries") or []]
    source_id = _text(entry.get("source_id"))
    previous_locator = _text(entry.get("locator"))
    found = None
    for item in entries:
        if source_id and _text(item.get("source_id")) == source_id:
            found = item
            break
    if found is None:
        for item in entries:
            if previous_locator and _text(item.get("locator")) == previous_locator:
                found = item
                break
    if found is None:
        return None
    for key in _OFFICIAL:
        found[key] = official[key]
    if locator:
        found["locator"] = locator
    found["in_text"] = short_in_text(official["author"], official["year"])
    basis = dict(opened)
    basis["id"] = official["source_id"]
    for key in _OFFICIAL:
        if key != "source_id":
            basis[key] = official[key]
    found["reference"] = full_reference(basis)
    for key in _PRINT_FIELDS:
        found[key] = _text(opened.get(key))
    record["entries"] = entries
    _save(essay_id, record)
    stored = {key: _text(found.get(key)) for key in _OFFICIAL}
    stored["in_text"] = _text(found.get("in_text"))
    stored["reference"] = _text(found.get("reference"))
    stored["locator"] = _text(found.get("locator"))
    return stored


def _refresh_source_record(
    essay_id: str,
    entry: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str] | None]:
    """The opened source's stored details, and the list copy when a newer file refreshed it.

    A published source does not change on its own. A newer file refreshes the
    opened source, the research note, and the citation list together. The note
    heading is not read. A record that cannot be written stays as it was.
    """
    source_id = _text(entry.get("source_id"))
    opened = _opened_source(essay_id, entry)
    stored = _load_source_record(essay_id, source_id)
    if stored is None and opened is not None:
        _ensure_source_record(essay_id, opened)
        stored = _load_source_record(essay_id, source_id)
    if not isinstance(stored, dict):
        return {}, None
    if opened is None:
        return _present_official(stored), None
    locator = _text(opened.get("locator")) or _text(stored.get("locator"))
    digest = _file_digest(locator)
    if not digest or digest == _text(stored.get("file_sha256")):
        return _present_official(stored), None
    official = _refresh_official(entry, opened)
    if not _store_source_official(essay_id, official, locator, digest):
        return _present_official(stored), None
    _store_note_official(_text(entry.get("note")), official)
    listed = _store_list_official(essay_id, entry, official, opened, locator)
    return {key: official[key] for key in _OFFICIAL}, listed


def _fill_note_gaps(note_raw: str, source_fields: dict[str, str], label: str) -> str:
    """Fill a missing note detail from the stored source. A heading is not read.

    A detail the source does not have yet stays a gap. It is not a conflict.
    """
    record_path = _note_record_path(note_raw)
    if record_path is None:
        return NOTE_DETAIL_GAP.format(label=label)
    current = read_json(record_path)
    data = current if isinstance(current, dict) else {}
    fields = _present_official(data)
    changed = not record_path.is_file()
    for key in _OFFICIAL:
        if key in fields:
            continue
        if key not in source_fields:
            continue
        fields[key] = source_fields[key]
        changed = True
    if changed and fields:
        kept = {key: fields[key] for key in _OFFICIAL if key in fields}
        write_json(record_path, kept, mkdir=True)
    if any(key not in fields for key in _OFFICIAL):
        return NOTE_DETAIL_GAP.format(label=label)
    return ""


def _fields_conflict(
    entry: dict[str, Any],
    source_fields: dict[str, str],
    note_raw: str,
) -> str:
    """Name a conflict when the stored copies disagree. A missing note detail is not one."""
    record_path = _note_record_path(note_raw)
    note = _present_official(read_json(record_path) if record_path is not None else None)
    listed = _official_from_entry(entry)
    for key in _OFFICIAL:
        if key not in note:
            continue
        sides = [listed[key], note[key]]
        if key in source_fields:
            sides.append(source_fields[key])
        norms = [_norm_official(value, key) for value in sides]
        if any(item != norms[0] for item in norms[1:]):
            return FIELD_CONFLICT.format(label=_label(entry))
    return ""


def _part_names(source_id: str) -> dict[str, str]:
    """The opened file, the note, and the list entry, named with the role at the back."""
    return part_names(source_id)


def _present_entry(essay_id: str, entry: dict[str, Any]) -> dict[str, Any]:
    shown = {key: entry.get(key, "") for key in _FROZEN}
    shown["note"] = _text(entry.get("note"))
    source_id = _text(shown.get("source_id"))
    if source_id:
        shown.update(_part_names(source_id))
    path = _resolve_note(shown["note"]) if shown["note"] else None
    conflict = ""
    gap = ""
    if path is None or not path.is_file():
        gap = MISSING_NOTE.format(label=_label(shown))
    else:
        source_fields, listed = _refresh_source_record(essay_id, shown)
        if listed is not None:
            for key in (*_OFFICIAL, "in_text", "reference", "locator"):
                shown[key] = listed[key]
            if _text(shown.get("source_id")):
                shown.update(_part_names(_text(shown.get("source_id"))))
        gap = _fill_note_gaps(shown["note"], source_fields, _label(shown))
        conflict = _fields_conflict(shown, source_fields, shown["note"])
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


def _match(entries: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any] | None:
    """The entry that names this work. A shared title is not enough."""
    for entry in entries:
        if same_source(entry, source):
            return entry
    return None


def _entry_from_source(source: dict[str, Any], note: str) -> dict[str, Any]:
    author = _text(source.get("author"))
    year = _text(source.get("year"))
    entry = {
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
    for key in _PRINT_FIELDS:
        entry[key] = _text(source.get(key))
    return entry


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


def entry_among(entries: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any] | None:
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
    remembered: list[dict[str, Any]] = [
        item for item in list(sources) + list(all_gathered(essay_id)) if isinstance(item, dict)
    ]
    for source in remembered:
        _ensure_source_record(essay_id, source)
    for entry in entries:
        _ensure_note_record(_text(entry.get("note")), _official_from_entry(entry))
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
    """Refuse the first draft when the list is missing, or a note is not on it.

    A gather that is still short of its floor, or that came back empty, or that
    stopped because a look-up was refused, also waits. A finished short gather
    does not.
    """
    from essay_writer.confirm import refuse
    from essay_writer.source_floor import draft_block

    waiting = draft_block(essay_id)
    if waiting:
        return refuse("citation-list", waiting, stored=False, advanced=False)
    if all_gathered(essay_id) and not list_written(essay_id):
        return refuse("citation-list", NOT_WRITTEN, stored=False, advanced=False)
    if uncovered_notes(essay_id):
        return refuse("citation-list", NOTE_UNLISTED, stored=False, advanced=False)
    if list_written(essay_id):
        named = [
            _text(entry.get("conflict"))
            for entry in load_citation_list(essay_id)["entries"]
            if _text(entry.get("conflict"))
        ]
        if named:
            return refuse("citation-list", " ".join(named), stored=False, advanced=False)
    return None


def _usable(essay_id: str) -> list[dict[str, Any]] | None:
    """Usable entries, or None when the list has not been written.

    An empty list is returned as an empty list, so a missing source is not filled
    from a second name match.
    """
    if not list_written(essay_id):
        return None
    return [
        entry for entry in load_citation_list(essay_id)["entries"] if entry.get("usable") is True
    ]


def usable_sources(essay_id: str) -> list[dict[str, Any]] | None:
    """Writer gate. Usable entries only. None when stage 4b has not written the list."""
    rows = _usable(essay_id)
    if rows is None:
        return None
    sources: list[dict[str, Any]] = []
    for entry in rows:
        row = {
            "id": entry.get("source_id"),
            "author": entry.get("author"),
            "year": entry.get("year"),
            "title": entry.get("title"),
            "doi": entry.get("doi"),
            "locator": entry.get("locator"),
            "in_text": entry.get("in_text"),
            "reference": entry.get("reference"),
        }
        for key in _PRINT_FIELDS:
            value = _text(entry.get(key))
            if value:
                row[key] = value
        sources.append(row)
    return sources


def _wording_matches(token: str, entry: dict[str, Any]) -> bool:
    """An allowed wording of this entry that is not itself the stored form."""
    if token_matches(token, entry):
        return False
    author = _text(entry.get("author"))
    year = _text(entry.get("year"))
    if not author or not year:
        return False
    return token_allowed(token, in_text_forms(author, year))


def _stored_for_part(part: str, rows: list[dict[str, Any]]) -> str | None:
    """The stored short form for this parenthesis part."""
    return stored_for_part(part, rows, _wording_matches)


def use_stored_short_form(essay_id: str, text: str) -> str:
    """Replace an in-essay citation with the short form stored on its list entry.

    The entry is found by source id. A different wording is not kept. Nothing
    is copied from a research-note heading.
    """
    if not isinstance(text, str) or not text:
        return text
    rows = _usable(essay_id)
    if not rows:
        return text

    def replace(match: re.Match[str]) -> str:
        parts = [part.strip() for part in match.group(1).split(";") if part.strip()]
        if not parts:
            return match.group(0)
        rewritten: list[str] = []
        changed = False
        for part in parts:
            stored = _stored_for_part(part, rows)
            if stored is None:
                rewritten.append(part)
                continue
            rewritten.append(stored)
            if fold_name(part).casefold() != fold_name(stored).casefold():
                changed = True
        if not changed:
            return match.group(0)
        return "(" + "; ".join(rewritten) + ")"

    return PAREN.sub(replace, text)


def reference_entries_for_token(essay_id: str, token: str) -> list[dict[str, Any]]:
    """List entries this token names, keyed by source id.

    A source id returns that one entry. The stored short form is next, and it
    beats a co-author wording. When several works store that form, every one
    of those entries is returned and none of them is chosen as the match.
    Another wording is used only when it names exactly one stored form.
    """
    rows = _usable(essay_id)
    if not rows:
        return []
    folded = fold_name(token).casefold().strip().rstrip(".")
    by_id = [entry for entry in rows if folded in identifier_keys(entry)]
    if len(by_id) == 1:
        return by_id
    if len(by_id) > 1:
        return []
    short = [entry for entry in rows if token_matches(folded, entry)]
    if short:
        return short
    return [entry for entry in rows if _wording_matches(folded, entry)]


def match_token(essay_id: str, token: str) -> dict[str, Any] | None:
    """The one list entry for this token. None when the token is not one work.

    Look-up uses the source id. A short form is used only when it is stored
    for a single work. A shared short form does not return the first work.
    """
    hits = reference_entries_for_token(essay_id, token)
    if len(hits) == 1:
        return hits[0]
    return None


def match_source(essay_id: str, source: dict[str, Any]) -> dict[str, Any] | None:
    if not list_written(essay_id):
        return None
    return _match(load_citation_list(essay_id)["entries"], source)


def stored_in_text(essay_id: str, source: dict[str, Any]) -> str | None:
    """The short citation stored for this source. None when the list does not list it."""
    if not list_written(essay_id):
        return None
    entry = _match(
        [item for item in load_citation_list(essay_id)["entries"] if item.get("usable")], source
    )
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
            # One work: its own line. A shared short form: each work's own
            # line. The first work is not used for the others.
            for entry in reference_entries_for_token(essay_id, token):
                line = _text(entry.get("reference")) if entry else ""
                if line and line not in seen:
                    seen.add(line)
                    lines.append(line)
        return lines
    for source in sources:
        if not isinstance(source, dict):
            continue
        matched = match_source(essay_id, source)
        if matched is None or matched.get("usable") is not True:
            continue
        line = _text(matched.get("reference"))
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
            next="Add that source to the citation list, then try this step again.",
        )
    note = _text(target.get("note"))
    if not note:
        from essay_writer.confirm import refuse

        return refuse(
            "citation-list",
            "That list entry has no research note to point at. Nothing was written.",
            wrote=False,
            next="Add a research note for that source, then try again.",
        )
    path = _resolve_note(note)
    replace_text(path, prose if prose.endswith("\n") else prose + "\n", mkdir=True)
    _ensure_note_record(note, _official_from_entry(target))
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
        source_id = _text(entry.get("source_id"))
        if source_id:
            names = _part_names(source_id)
            lines.append(names["part_source"])
            lines.append(names["part_note"])
            lines.append(names["part_list"])
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
