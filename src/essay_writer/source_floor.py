"""How many official works a gather must reach before a sourced essay.

A count stated on the assignment is the floor. When the assignment states
no count, the floor is eight works for each 1,000 words of the stated
length, rounded up. The citation list is still written at stage 4b.
Nothing here invents an author, a year, a title, a DOI, or a URL.
"""

from __future__ import annotations

import json
import re
from typing import Any

NO_LENGTH = "The assignment stated no length."
FOUND = (
    "Found {found} sources. This assignment's floor is {floor}. "
    "The catalogs returned no further records."
)
NO_PAPERS = (
    "The catalogs returned no papers for the confirmed question, "
    "so no sourced essay will be written."
)
UNFINISHED = "The gather is not finished."
ASK_QUESTION = "Name the essay question. An empty question is not searched."
PLAN_PAGE = "This plan does not return another page."
QUESTION_GAP = "This question returned no records."
CROSSREF_NOTE = "Crossref was not used as a question search."
FURTHER = "The source floor is not met, and more official records were still available."
GAP_ONLY = (
    "A returned record is missing a name or a year, so it is not counted. "
    "No sourced essay will be written."
)
DID_NOT_RUN = "{name} did not run."
PAGE_BUDGET = "OpenAlex page budget"

_SOURCE_WORD = re.compile(r"(?i)\b(?:sources?|references?|citations?)\b")
_CLASS_NAME = re.compile(r"(?i)\bspecialist industry sources?\b")
_SECTION_BUDGET = re.compile(
    r"(?i)\bsection budgets?\b|\b(?:each|per|every)\s+(?:section|entry|part)\b"
)
_RANGE_COUNT = re.compile(
    r"(?i)\b(?:between\s+)?(\d[\d,]*)\s*(?:–|-|—|to|and)\s*(\d[\d,]*)\s+"
    r"(?:(?:academic|scholarly|peer-reviewed|relevant|credible)\s+)*"
    r"(?:sources?|references?|citations?)\b"
)
_UP_TO = re.compile(
    r"(?i)\bup\s+to\s+(\d[\d,]*)\s+"
    r"(?:(?:academic|scholarly|peer-reviewed|relevant|credible)\s+)*"
    r"(?:sources?|references?|citations?)\b"
)
_AT_LEAST = re.compile(r"(?i)\b(?:at\s+least|a\s+minimum\s+of|minimum\s+of)\s+(\d[\d,]*)\b")
_EXACTLY = re.compile(r"(?i)\bexactly\s+(\d[\d,]*)\b")
_MAXIMUM = re.compile(r"(?i)\b(?:no\s+more\s+than|a\s+maximum\s+of|maximum\s+of)\s+(\d[\d,]*)\b")
_BARE_COUNT = re.compile(
    r"(?i)\b(\d[\d,]*)\s+"
    r"(?:(?:academic|scholarly|peer-reviewed|relevant|credible)\s+)*"
    r"(?:sources?|references?|citations?)\b"
)
_WORD_COUNT = re.compile(r"(?i)\b(\d[\d,]*)\s+words?\b")
_WORD_RANGE = re.compile(r"(?i)\b(\d[\d,]*)\s*(?:–|-|—|to)\s*(\d[\d,]*)\s+words?\b")
_PERCENT = re.compile(r"(\d[\d,]*)\s*%")
_PART_SUBJECT = re.compile(
    r"(?i)^\s*(?:(?:the|a|an|your|its|this|that)\s+)?"
    r"(?:abstract|executive summary|lists? of references?|reference lists?|"
    r"references?|bibliography|appendix|appendices|contents|title page|cover page)\b"
)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_OPERATOR = re.compile(r"site:|filetype:|(?<![A-Za-z])(?:AND|OR|NOT)(?![A-Za-z])")
_UPLOAD_HEAD = re.compile(
    r"^(?P<author>.+?)\s+\((?P<year>1[0-9]{3}|20[0-9]{2})\)\s+"
    r"['\"]?(?P<title>.+?)['\"]?\.?\s*$"
)
_DOI = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)


def confirmed_question(essay_id: str) -> str:
    """The labelled question, or the stored answer. A loose cue is not used."""
    from essay_writer import assignment_gate as gate

    brief = gate._brief_text(essay_id)
    scheme = gate.mark_scheme_text(essay_id)
    if not brief and not scheme:
        return ""
    brief_body = gate._brief_without_scheme(brief)
    question = gate._question_of(brief_body, cues=False) or gate._question_of(scheme, cues=False)
    if not question:
        record = gate.read_assignment(essay_id)
        if record.get("format") == "reflective diary":
            from essay_writer.diary import diary_ask

            question = diary_ask(brief_body)
    if not question:
        saved = gate._accepted_brief_meta(essay_id, brief)
        if isinstance(saved, dict):
            raw = saved.get("question")
            if isinstance(raw, str) and raw.strip():
                question = raw.strip()
    if isinstance(question, str) and question.strip():
        return " ".join(question.split())
    return ""


def ask_planning_model(question: str, reply: Any = None) -> Any:
    """One-shot ask. The shell supplies the smaller questions on this call.

    Both shells pass them as smallerQuestions on the gather. A missing reply
    is a failed call. This does not invent a question, and it does not ask again.
    """
    if not isinstance(question, str) or not question.strip():
        return None
    return reply


def accept_split(question: str, reply: Any) -> list[str]:
    """Smaller questions the model returned, then the confirmed question.

    Blanks, duplicates, and strings the model did not return are left out.
    At most three smaller questions are kept. A failed reply leaves only
    the confirmed question.
    """
    confirmed = " ".join(question.split())
    if not confirmed:
        return []
    smaller: list[str] = []
    seen = {_norm(confirmed)}
    for item in _reply_strings(reply):
        text = " ".join(item.split())
        if not text or _OPERATOR.search(text):
            continue
        key = _norm(text)
        if not key or key in seen:
            continue
        seen.add(key)
        smaller.append(text)
        if len(smaller) == 3:
            break
    return smaller + [confirmed]


def assignment_floor(essay_id: str) -> dict[str, Any]:
    """The stored floor for this sequence. A stated count wins over the word rate."""
    from essay_writer.assignment_gate import mark_scheme_text
    from essay_writer.brief_checks import stated_word_totals, word_total_clash
    from essay_writer.textutil import module_brief_text, word_band_from_brief_text

    scheme = mark_scheme_text(essay_id)
    brief = module_brief_text(essay_id)
    stated = _stated_counts(scheme)
    stated = _merge_counts(stated, _stated_counts(brief))
    scheme_band = word_band_from_brief_text(scheme)
    band_text = scheme if scheme_band else brief
    # A whole-piece count is read from that same text. A section line beside
    # it does not erase the count, and a part length is not used as one.
    words = _whole_piece_words(band_text) if band_text else None
    clash = word_total_clash(band_text) if band_text else None
    totals = stated_word_totals(band_text) if band_text else []
    return _floor_record(stated, words, clash, totals)


def rate_for_words(words: int | None = None) -> int:
    """ceil(words / 1000 * 8). A missing length uses the 1,000-word rate."""
    if isinstance(words, bool) or not isinstance(words, int) or words <= 0:
        words = 1000
    return (words * 8 + 999) // 1000


def cap_for_words(words: int | None) -> int | None:
    """max(1, words * 12 // 1000). None when no whole-piece length was stated."""
    if isinstance(words, bool) or not isinstance(words, int) or words <= 0:
        return None
    return max(1, (words * 12) // 1000)


def _fold_piece(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _identity_keys(record: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for field in ("source_id", "id"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            keys.append("id:" + value.strip())
            break
    doi = doi_key(record.get("doi"))
    if doi:
        keys.append("doi:" + doi)
    title = _fold_piece(title_text(record))
    year = year_text(record)
    author = _fold_piece(author_text(record))
    if title and year and author:
        keys.append(f"tya:{title}|{year}|{author}")
    return keys


def work_key(record: dict[str, Any]) -> str | None:
    """None when author, title, or year is missing. Otherwise one identity token."""
    if not title_text(record) or not year_text(record) or not author_text(record):
        return None
    keys = _identity_keys(record)
    return keys[0] if keys else None


def distinct_works(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def is_gap(record: dict[str, Any]) -> bool:
    """A title or a year without the fields a short citation needs."""
    if work_key(record) is not None:
        return False
    return bool(title_text(record) or year_text(record))


def countable_upload(essay_id: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    """A student file that would be kept and can be cited. The brief is not one."""
    from essay_writer.invent import gather_source

    if not isinstance(raw, dict):
        return None
    origin = raw.get("origin")
    if origin in {"sample", "samples", "reference-list", "brief"}:
        return None
    locator = raw.get("locator")
    if isinstance(locator, str) and _is_brief_locator(locator):
        return None
    kept, issues = gather_source(essay_id, raw, 0)
    if issues or not isinstance(kept, dict):
        return None
    if work_key(kept) is None:
        return None
    return kept


def saved_upload_records(essay_id: str) -> list[dict[str, Any]]:
    """Upload files whose own first line already names the author, year, and title."""
    from essay_writer.paths import module_code, uploads_dir

    folder = uploads_dir(essay_id)
    if not folder.is_dir():
        return []
    module = module_code(essay_id)
    found: list[dict[str, Any]] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        header = _upload_header(text)
        if header is None:
            continue
        raw = {
            "id": path.stem,
            "origin": "upload",
            "locator": f"uploads/{module}/{path.name}",
            "author": header["author"],
            "year": header["year"],
            "title": header["title"],
        }
        kept = countable_upload(essay_id, raw)
        if kept is not None:
            found.append(kept)
    return found


def page_cap_note(found: int, floor: int, uploads: int, cursor: str | None) -> str:
    """Found count, floor, page-budget name, and either a saved cursor or a stop."""
    source_word = "source" if found == 1 else "sources"
    file_word = "file" if uploads == 1 else "files"
    base = (
        f"Found {found} official {source_word}. Uploaded {file_word}: {uploads}. "
        f"This assignment's floor is {floor}. "
        f"The {PAGE_BUDGET} stopped this gather."
    )
    if cursor:
        return base + " The OpenAlex cursor is saved for a later gather."
    return base + " No more official pages are available."


def decide_gather(
    questions: list[dict[str, Any]],
    floor: dict[str, Any],
    countable: int,
    further_page: bool,
    uploads: int = 0,
    *,
    page_capped: bool = False,
    page_cursor: str | None = None,
) -> dict[str, Any]:
    """What the gather may do with the works already in hand."""
    raw_floor = floor.get("floor")
    if isinstance(raw_floor, int) and not isinstance(raw_floor, bool):
        needed = raw_floor
    else:
        needed = rate_for_words(None)
    found = max(0, int(countable))
    upload_count = max(0, int(uploads))
    refused = _discovery_refused(questions)
    openalex_called = any(_called(item.get("openalex")) for item in questions)
    consensus_called = any(_called(item.get("consensus")) for item in questions)
    hits = _any_hits(questions)
    empty_hits = _all_empty(questions)
    met = found >= needed
    blocked = False
    kind = "met"
    note = _quiet_notes(floor)
    if not met and further_page:
        blocked = True
        kind = "further"
        note = FURTHER
    elif not met and refused:
        blocked = True
        kind = "unfinished"
        note = (_refusal_sentence(questions) + " " + UNFINISHED).strip()
    elif not met and not openalex_called:
        blocked = True
        kind = "unfinished"
        note = DID_NOT_RUN.format(name="OpenAlex") + " " + UNFINISHED
    elif not met and found == 0 and empty_hits and not refused:
        blocked = True
        kind = "empty"
        note = _empty_sentence(questions, openalex_called, consensus_called)
    elif not met and found == 0 and hits and not refused:
        blocked = True
        kind = "gaps"
        note = GAP_ONLY
    elif not met and found > 0 and not refused and not further_page:
        kind = "exhausted"
        note = FOUND.format(found=found, floor=needed)
        extra = _quiet_notes(floor)
        if extra:
            note = note + " " + extra
    if page_capped and not refused:
        note = page_cap_note(found, needed, upload_count, page_cursor)
        if page_cursor:
            blocked = True
            kind = "page_cap"
        elif found == 0:
            blocked = True
            kind = "empty"
        else:
            blocked = False
            kind = "exhausted"
    elif "Official sources:" not in note:
        note = f"{note} Official sources: {found}. Uploaded files: {upload_count}.".strip()
    body = {
        "floor": needed,
        "floor_from": floor.get("floor_from") or "word_rate",
        "words": floor.get("words"),
        "count": found,
        "uploads": upload_count,
        "further_page": bool(further_page) and not met,
        "met": met,
        "exhausted": kind == "exhausted",
        "empty": kind == "empty",
        "unfinished": kind == "unfinished",
        "blocked": blocked,
        "kind": kind,
        "note": note,
        "stated_counts": list(floor.get("stated_counts") or []),
        "writing_limit": floor.get("writing_limit"),
        "length_note": floor.get("length_note") or "",
        "word_clash": floor.get("word_clash") or "",
        "openalex_called": openalex_called,
        "consensus_called": consensus_called,
    }
    if page_cursor:
        body["openalex_cursor"] = page_cursor
    return body


def draft_block(essay_id: str) -> str | None:
    """Why a sourced list or a sourced draft must wait. None when it may proceed."""
    gather = load_gather(essay_id)
    if isinstance(gather, dict) and gather.get("blocked") is True:
        note = gather.get("note")
        if isinstance(note, str) and note.strip():
            return note.strip()
        return UNFINISHED
    if empty_saved_gather(essay_id):
        return NO_PAPERS
    return None


def gate_block(essay_id: str) -> str | None:
    """The pack gate uses the same wait. A finished short gather does not fail."""
    return draft_block(essay_id)


def exhaustion_sentence(essay_id: str) -> str:
    """The found-count sentence. Empty when the gather is not in that case."""
    gather = load_gather(essay_id)
    if not isinstance(gather, dict) or gather.get("exhausted") is not True:
        return ""
    note = gather.get("note")
    return note.strip() if isinstance(note, str) else ""


def load_gather(essay_id: str) -> dict[str, Any] | None:
    """The gather record on the saved source card. None when the card has none."""
    from essay_writer.paths import work_dir

    path = work_dir(essay_id) / "dig-card.json"
    if not path.is_file():
        return None
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(stored, dict):
        return None
    gather = stored.get("gather")
    if not isinstance(gather, dict):
        return None
    return gather


def question_lines(questions: list[dict[str, Any]]) -> list[str]:
    """One line per stored question. An empty result stays visible."""
    lines: list[str] = []
    for item in questions:
        text = item.get("question")
        if not isinstance(text, str) or not text.strip():
            continue
        openalex_value = item.get("openalex")
        openalex = openalex_value if isinstance(openalex_value, dict) else {}
        consensus_value = item.get("consensus")
        consensus = consensus_value if isinstance(consensus_value, dict) else {}
        hits = list(openalex.get("hits") or []) + list(consensus.get("hits") or [])
        gaps = [hit for hit in hits if isinstance(hit, dict) and is_gap(hit)]
        if not hits:
            lines.append(f"- {text.strip()}: {QUESTION_GAP}")
        elif gaps and not any(isinstance(hit, dict) and work_key(hit) for hit in hits):
            lines.append(f"- {text.strip()}: a returned record is missing a name or a year.")
        else:
            lines.append(
                f"- {text.strip()}: {len(distinct_works([h for h in hits if isinstance(h, dict)]))} sources."
            )
        pagination = consensus.get("pagination")
        if isinstance(pagination, str) and pagination.strip():
            lines.append(f"- {pagination.strip()}")
        note = item.get("crossref")
        if isinstance(note, dict) and isinstance(note.get("note"), str):
            lines.append(f"- {note['note']}")
    return lines


def author_text(record: dict[str, Any]) -> str:
    authors = record.get("authors")
    if isinstance(authors, list):
        names = [item.strip() for item in authors if isinstance(item, str) and item.strip()]
        if names:
            return " and ".join(names)
    author = record.get("author")
    if isinstance(author, str) and author.strip():
        return author.strip()
    return ""


def year_text(record: dict[str, Any]) -> str:
    year = record.get("year")
    if isinstance(year, bool):
        return ""
    if isinstance(year, int):
        return str(year)
    if isinstance(year, str) and year.strip().isdigit():
        return year.strip()
    return ""


def title_text(record: dict[str, Any]) -> str:
    title = record.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return ""


def doi_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _DOI.sub("", value.strip()).casefold()


def _floor_record(
    stated: dict[str, Any],
    words: int | None,
    clash: str | None,
    totals: list[int],
) -> dict[str, Any]:
    counts = list(stated.get("counts") or [])
    limit = stated.get("writing_limit")
    notes: list[str] = []
    if len(counts) >= 2:
        shown = " and ".join(str(item) for item in counts)
        notes.append(f"The assignment states {shown} sources. The floor uses {counts[0]}.")
    if isinstance(limit, int) and limit > 0:
        notes.append(
            f"The assignment states a writing limit of {limit} sources. "
            "Gathering does not trim to that limit."
        )
    if isinstance(clash, str) and clash.strip():
        notes.append(clash.strip())
    if counts:
        return {
            "floor": counts[0],
            "floor_from": "stated",
            "words": words,
            "stated_counts": counts,
            "writing_limit": limit,
            "length_note": "",
            "word_clash": clash or "",
            "word_totals": totals,
            "notes": notes,
        }
    if isinstance(words, int) and words > 0:
        return {
            "floor": rate_for_words(words),
            "floor_from": "word_rate",
            "words": words,
            "stated_counts": [],
            "writing_limit": limit,
            "length_note": "",
            "word_clash": clash or "",
            "word_totals": totals,
            "notes": notes,
        }
    notes.insert(0, NO_LENGTH)
    return {
        "floor": rate_for_words(None),
        "floor_from": "no_length",
        "words": None,
        "stated_counts": [],
        "writing_limit": limit,
        "length_note": NO_LENGTH,
        "word_clash": clash or "",
        "word_totals": totals,
        "notes": notes,
    }


def _quiet_notes(floor: dict[str, Any]) -> str:
    notes = [item for item in floor.get("notes") or [] if isinstance(item, str) and item.strip()]
    return " ".join(notes)


def _stated_counts(text: str) -> dict[str, Any]:
    counts: list[int] = []
    limit: int | None = None
    if not isinstance(text, str) or not text.strip():
        return {"counts": counts, "writing_limit": limit}
    for sentence in _sentences(text):
        parsed = _sentence_count(sentence)
        if parsed is None:
            continue
        number = parsed.get("floor")
        if isinstance(number, int) and number > 0 and number not in counts:
            counts.append(number)
        cap = parsed.get("writing_limit")
        if isinstance(cap, int) and cap > 0 and limit is None:
            limit = cap
    return {"counts": counts, "writing_limit": limit}


def _merge_counts(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    counts = list(first.get("counts") or [])
    for number in second.get("counts") or []:
        if number not in counts:
            counts.append(number)
    limit = first.get("writing_limit")
    if not isinstance(limit, int):
        limit = second.get("writing_limit")
    return {"counts": counts, "writing_limit": limit}


def _source_count(sentence: str, pattern: re.Pattern[str]) -> int | None:
    """The first source count in ``pattern``. A word count in the same sentence is skipped."""
    for match in pattern.finditer(sentence):
        token = match.group(1)
        if re.match(r"(?i)\s+words?\b", sentence[match.end() :]):
            continue
        if _number_is_word_or_percent(sentence, token):
            continue
        number = _number(token)
        if number > 0:
            return number
    return None


def _sentence_count(sentence: str) -> dict[str, Any] | None:
    if not _SOURCE_WORD.search(sentence):
        return None
    if _SECTION_BUDGET.search(sentence):
        return None
    if _CLASS_NAME.search(sentence) and not re.search(r"\d", sentence):
        return None
    source_at_least = _source_count(sentence, _AT_LEAST)
    source_exactly = _source_count(sentence, _EXACTLY)
    ranged = _RANGE_COUNT.search(sentence) is not None
    capped = _UP_TO.search(sentence) is not None or _MAXIMUM.search(sentence) is not None
    if (
        _wordish(sentence)
        and not _BARE_COUNT.search(sentence)
        and source_at_least is None
        and source_exactly is None
        and not ranged
        and not capped
    ):
        return None
    writing_limit = None
    maximum = _MAXIMUM.search(sentence)
    if maximum and not _number_is_word_or_percent(sentence, maximum.group(1)):
        writing_limit = _number(maximum.group(1))
    up_to = _UP_TO.search(sentence)
    if up_to and not _number_is_word_or_percent(sentence, up_to.group(1)):
        writing_limit = _number(up_to.group(1))
    floor = None
    span = _RANGE_COUNT.search(sentence)
    if span and not _number_is_word_or_percent(sentence, span.group(1)):
        low = _number(span.group(1))
        high = _number(span.group(2))
        if low > 0 and high > low:
            floor = low
    elif source_at_least is not None or source_exactly is not None:
        floor = source_at_least if source_at_least is not None else source_exactly
    elif up_to is None and maximum is None:
        bare = _BARE_COUNT.search(sentence)
        if bare and not _number_is_word_or_percent(sentence, bare.group(1)):
            floor = _number(bare.group(1))
    if floor is not None and floor <= 0:
        floor = None
    if floor is None and writing_limit is None:
        return None
    return {"floor": floor, "writing_limit": writing_limit}


def _whole_piece_words(text: str) -> int | None:
    """The printed whole-piece length. A range uses its low end. Edges are not used."""
    if not isinstance(text, str) or not text.strip():
        return None
    for sentence in _sentences(text):
        if _SECTION_BUDGET.search(sentence) or _PART_SUBJECT.search(sentence):
            continue
        if re.search(r"(?i)\b(?:each|per|every)\s+(?:section|entry|part|paragraph)\b", sentence):
            continue
        span = _WORD_RANGE.search(sentence)
        if span:
            low = _number(span.group(1))
            high = _number(span.group(2))
            if low > 0 and high > low:
                return low
        match = _WORD_COUNT.search(sentence)
        if match:
            value = _number(match.group(1))
            if value > 0:
                return value
    return None


def _sentences(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        for sentence in _SENTENCE.split(line.strip()):
            sentence = sentence.strip()
            if sentence:
                found.append(sentence)
    return found


def _number(token: str) -> int:
    try:
        return int(token.replace(",", ""))
    except ValueError:
        return 0


def _number_is_word_or_percent(sentence: str, token: str) -> bool:
    for match in _WORD_COUNT.finditer(sentence):
        if match.group(1) == token:
            return True
    for match in _PERCENT.finditer(sentence):
        if match.group(1) == token:
            return True
    return False


def _wordish(sentence: str) -> bool:
    return _WORD_COUNT.search(sentence) is not None


def _reply_strings(reply: Any) -> list[str]:
    if reply is None:
        return []
    if isinstance(reply, list):
        return [item for item in reply if isinstance(item, str)]
    if isinstance(reply, str):
        text = reply.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, str)]
        lines = []
        for line in text.splitlines():
            cleaned = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip()
            if cleaned:
                lines.append(cleaned)
        return lines
    return []


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _called(block: object) -> bool:
    return isinstance(block, dict) and block.get("called") is True


def _discovery_refused(questions: list[dict[str, Any]]) -> bool:
    for item in questions:
        for key in ("openalex", "consensus"):
            block = item.get(key)
            if isinstance(block, dict) and isinstance(block.get("refused"), dict):
                return True
    return False


def _any_hits(questions: list[dict[str, Any]]) -> bool:
    for item in questions:
        for key in ("openalex", "consensus"):
            block = item.get(key)
            hits = block.get("hits") if isinstance(block, dict) else None
            if isinstance(hits, list) and hits:
                return True
    return False


def _all_empty(questions: list[dict[str, Any]]) -> bool:
    if not questions:
        return False
    return not _any_hits(questions)


def _refusal_sentence(questions: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in questions:
        for name, key in (("OpenAlex", "openalex"), ("Consensus", "consensus")):
            block = item.get(key)
            if not isinstance(block, dict):
                continue
            refused = block.get("refused")
            if not isinstance(refused, dict):
                continue
            detail = refused.get("detail")
            if not isinstance(detail, str) or not detail.strip():
                detail = "no reason given"
            status = refused.get("status")
            code = (
                f"HTTP {status}: "
                if isinstance(status, int) and not isinstance(status, bool) and status
                else ""
            )
            lines.append(f"{name} refused the look-up. {code}{detail.strip()[:200]}")
    return " ".join(lines)


def _empty_sentence(
    questions: list[dict[str, Any]],
    openalex_called: bool,
    consensus_called: bool,
) -> str:
    parts: list[str] = []
    called = [
        name
        for name, flag in (("OpenAlex", openalex_called), ("Consensus", consensus_called))
        if flag
    ]
    if len(called) == 1:
        parts.append(f"{called[0]} was called.")
    elif len(called) == 2:
        parts.append("OpenAlex and Consensus were called.")
    if not consensus_called:
        parts.append(DID_NOT_RUN.format(name="Consensus"))
    if _unpaywall_missing(questions):
        parts.append(DID_NOT_RUN.format(name="Unpaywall"))
    parts.append(NO_PAPERS)
    return " ".join(parts)


def _unpaywall_missing(questions: list[dict[str, Any]]) -> bool:
    for item in questions:
        rows = item.get("unpaywall")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("skipped") == "no-email":
                return True
        if item.get("unpaywall_skipped") == "no-email":
            return True
    return False


def _is_brief_locator(locator: str) -> bool:
    name = locator.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return name in {"brief.md", "brief.txt", "brief.docx"}


def _upload_header(text: str) -> dict[str, str] | None:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _UPLOAD_HEAD.match(stripped)
        if match is None:
            return None
        author = match.group("author").strip(" '\"")
        title = match.group("title").strip(" '\"")
        if not author or not title:
            return None
        return {"author": author, "year": match.group("year"), "title": title}
    return None


def _citation_path(essay_id: str):
    from essay_writer.paths import work_dir

    return work_dir(essay_id) / "citation-list.json"


def _read_json(path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def saved_research_works(essay_id: str) -> bool:
    """True when a gathered source, a source record, or a citation entry exists."""
    from essay_writer.paths import work_dir
    from essay_writer.state import load_state

    state = load_state(essay_id)
    research = state.get("research") if isinstance(state, dict) else None
    if isinstance(research, dict):
        for depth in ("summary", "full"):
            record = research.get(depth)
            sources = record.get("sources") if isinstance(record, dict) else None
            if isinstance(sources, list) and any(isinstance(item, dict) for item in sources):
                return True
    folder = work_dir(essay_id) / "output" / "source-records"
    if folder.is_dir() and any(path.is_file() for path in folder.glob("*.record.json")):
        return True
    data = _read_json(_citation_path(essay_id))
    entries = data.get("entries") if isinstance(data, dict) else None
    return isinstance(entries, list) and any(isinstance(item, dict) for item in entries)


def empty_saved_gather(essay_id: str) -> bool:
    """True when the citation list is on disk and no work was saved."""
    if _read_json(_citation_path(essay_id)) is None:
        return False
    return not saved_research_works(essay_id)


def record_empty_gather(essay_id: str) -> None:
    """Remember an empty gather without writing a sourced citation list."""
    path = _citation_path(essay_id)
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"written": False, "entries": []}) + "\n",
        encoding="utf-8",
    )
