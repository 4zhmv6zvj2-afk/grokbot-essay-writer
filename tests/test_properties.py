"""Property checks for the parsers that decide a count, a line, or a title.

Each test names its invariant in the docstring. Draws come from a fixed
counter, not the clock and not the network. A failure prints the smallest
input that still fails.

Invariant map:

- word band of a bare count is the ten-percent band
- an explicit word range wins over the ten-percent band
- a section length is not the whole-piece band
- the source rate is ceil(words / 1000 * 8), and a missing length uses 8
- the source cap is 12 works per 1,000 words, and a stated count above it raises it
- distinct works follow the documented identity rules
- a repeated record does not add a work, and order does not change the count
- a Harvard line keeps author, year, title quotes, and italics
- et al. starts at the fourth author
- a parenthetical cite is removed and the sentence stays
- a narrative cite that was the subject is an unreadable draft
- a doubled comma is an unreadable draft, and a plain sentence is not
- a Word title is at most 255 characters and is never the opening paragraph
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import pytest
from helpers import open_sequence

from essay_writer.cite_fit import strip_token
from essay_writer.essay_cites import essay_cite_bounds
from essay_writer.harvard_4a import harvard_4a_line, harvard_4a_parts, in_text_uses_et_al
from essay_writer.model_contract import StripReport
from essay_writer.paths import essay_dir
from essay_writer.source_floor import cap_for_words, rate_for_words
from essay_writer.sources import (
    author_text,
    distinct_works,
    doi_key,
    fold_piece,
    title_text,
    year_text,
)
from essay_writer.specialists.writer import first_draft_unreadable
from essay_writer.textutil import word_band_from_brief_text
from essay_writer.word import document_title

SEED = 20261125
ROUNDS = 40


class Draw:
    """One fixed counter. The same seed always yields the same sequence."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def below(self, limit: int) -> int:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        if limit <= 1:
            return 0
        return self.state % limit


def _size(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 1
    if isinstance(value, int):
        return abs(value)
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return 1 + sum(_size(item) for item in value)
    if isinstance(value, dict):
        return 1 + sum(_size(key) + _size(item) for key, item in value.items())
    return 1


def _smaller(value: object) -> list[object]:
    found: list[object] = []
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, int):
        if value > 0:
            found.extend((0, value // 2, value - 1))
        elif value < 0:
            found.extend((0, value // 2, value + 1))
        return found
    if isinstance(value, str):
        if not value:
            return found
        mid = max(1, len(value) // 2)
        found.append(value[:mid])
        found.append(value[mid:])
        if len(value) > 1:
            found.append(value[1:])
            found.append(value[:-1])
        return found
    if isinstance(value, list):
        for index in range(len(value)):
            found.append(value[:index] + value[index + 1 :])
        for index, item in enumerate(value):
            for child in _smaller(item):
                copy = list(value)
                copy[index] = child
                found.append(copy)
        return found
    if isinstance(value, dict):
        for key in value:
            copy = dict(value)
            del copy[key]
            found.append(copy)
        for key, item in value.items():
            for child in _smaller(item):
                copy = dict(value)
                copy[key] = child
                found.append(copy)
    return found


def _shrink(value: object, fails: Callable[[object], bool]) -> object:
    current = value
    for _ in range(400):
        moved = False
        for candidate in _smaller(current):
            if _size(candidate) >= _size(current):
                continue
            if fails(candidate):
                current = candidate
                moved = True
                break
        if not moved:
            return current
    return current


def check(
    draw: Callable[[Draw], object], holds: Callable[[Any], bool], *, rounds: int = ROUNDS
) -> None:
    rng = Draw(SEED)
    for _ in range(rounds):
        value = draw(rng)
        try:
            ok = holds(value)
            error: BaseException | None = None
        except Exception as caught:
            ok = False
            error = caught
        if ok:
            continue

        kind = type(error) if error is not None else None

        def fails(
            candidate: object,
            bound: Callable[[Any], bool] = holds,
            failed_as: type[BaseException] | None = kind,
        ) -> bool:
            try:
                return failed_as is None and not bound(candidate)
            except Exception as caught:
                return failed_as is not None and type(caught) is failed_as

        small = _shrink(value, fails)
        detail = f"{type(error).__name__}: {error}" if error else "invariant failed"
        raise AssertionError(f"{detail}\nminimal repro: {small!r}")


def _pick(rng: Draw, options: tuple[Any, ...]) -> Any:
    return options[rng.below(len(options))]


def test_a_failing_bound_prints_the_smallest_input() -> None:
    """The checker names the smallest input that still breaks the claim."""

    def draw(rng: Draw) -> int:
        return rng.below(30)

    def holds(number: int) -> bool:
        return number < 4

    with pytest.raises(AssertionError) as caught:
        check(draw, holds, rounds=20)
    assert "minimal repro: 4" in str(caught.value)


def test_a_bare_word_count_uses_the_ten_percent_band() -> None:
    """N words is round(N * 0.9) to round(N * 1.1). 800 words is 720 to 880."""

    def draw(rng: Draw) -> int:
        return 1 + rng.below(20000)

    def holds(words: int) -> bool:
        band = word_band_from_brief_text(f"The assignment is {words} words.")
        low = round(words * 0.9)
        high = round(words * 1.1)
        return (
            band.get("min") == low
            and band.get("max") == high
            and low <= band.get("limit", -1) <= high
        )

    check(draw, holds)


def test_an_explicit_word_range_wins() -> None:
    """A printed range next to the word count is the band. The ten-percent band is not used."""

    def draw(rng: Draw) -> list[int]:
        low = 50 + rng.below(4000)
        high = low + 1 + rng.below(4000)
        return [low, high]

    def holds(pair: list[int]) -> bool:
        low, high = pair
        band = word_band_from_brief_text(f"The assignment is {low} to {high} words.")
        return band.get("min") == low and band.get("max") == high

    check(draw, holds)


def test_a_section_length_is_not_the_whole_piece_band() -> None:
    """A length for each section does not set the whole-piece word band."""

    def draw(rng: Draw) -> int:
        return 1 + rng.below(5000)

    def holds(words: int) -> bool:
        return word_band_from_brief_text(f"Each section is {words} words.") == {}

    check(draw, holds)


def test_the_source_rate_is_eight_per_thousand_words() -> None:
    """ceil(words / 1000 * 8). Zero, a negative, and a missing length use the 1,000-word rate."""

    def draw(rng: Draw) -> int:
        return rng.below(30001) - 5

    def holds(words: int) -> bool:
        if words <= 0:
            return rate_for_words(words) == 8
        return rate_for_words(words) == math.ceil(words * 8 / 1000)

    check(draw, holds)
    assert rate_for_words(None) == 8
    assert rate_for_words(True) == 8


def test_the_source_cap_is_twelve_per_thousand_words() -> None:
    """max(1, words * 12 // 1000). No whole-piece length means no cap."""

    def draw(rng: Draw) -> int:
        return rng.below(30001) - 5

    def holds(words: int) -> bool:
        if words <= 0:
            return cap_for_words(words) is None
        return cap_for_words(words) == max(1, (words * 12) // 1000)

    check(draw, holds)
    assert cap_for_words(None) is None
    assert cap_for_words(True) is None


def _brief(seq: str, words: int, stated: int) -> None:
    lines = [
        "Question: How do ports shape coastal trade?",
        f"The assignment is {words} words.",
    ]
    if stated:
        lines.append(f"Use at least {stated} sources.")
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_a_stated_count_above_the_cap_raises_the_cap(workspace) -> None:
    """A stated count is the minimum. Above the rate cap, it is also the maximum.

    The rate is not added to the stated number. A silent brief uses the rate and the cap.
    """
    assert workspace.is_dir()

    def draw(rng: Draw) -> list[int]:
        words = 200 + rng.below(8000)
        stated = rng.below(41)
        return [words, stated]

    def holds(pair: list[int]) -> bool:
        words, stated = pair
        seq = open_sequence()
        _brief(seq, words, stated)
        bounds = essay_cite_bounds(seq)
        rate = math.ceil(words * 8 / 1000)
        cap = max(1, (words * 12) // 1000)
        if stated:
            return bounds["minimum"] == stated and bounds["maximum"] == max(cap, stated)
        return bounds["minimum"] == rate and bounds["maximum"] == cap and bounds["from"] != "stated"

    check(draw, holds)


def documented_work_count(records: list[object]) -> int:
    """How many works the identity rules keep.

    The same source id is one work. The same DOI is one work. A DOI record and
    a no-DOI record with the same title, year, and author are one work. Two
    different DOIs stay two. A record missing author, title, or year is not a
    work.
    """
    rows = [
        record
        for record in records
        if isinstance(record, dict)
        and title_text(record)
        and year_text(record)
        and author_text(record)
    ]
    parent = list(range(len(rows)))

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

    seen_id: dict[str, int] = {}
    seen_doi: dict[str, int] = {}
    for index, record in enumerate(rows):
        for field in ("source_id", "id"):
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                key = value.strip()
                if key in seen_id:
                    union(index, seen_id[key])
                else:
                    seen_id[key] = index
                break
        doi = doi_key(record.get("doi"))
        if doi:
            if doi in seen_doi:
                union(index, seen_doi[doi])
            else:
                seen_doi[doi] = index
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, record in enumerate(rows):
        key = (
            fold_piece(title_text(record)),
            year_text(record),
            fold_piece(author_text(record)),
        )
        if all(key):
            groups[key].append(index)
    for indexes in groups.values():
        no_doi = [index for index in indexes if not doi_key(rows[index].get("doi"))]
        with_doi = [index for index in indexes if doi_key(rows[index].get("doi"))]
        for index in no_doi[1:]:
            union(no_doi[0], index)
        dois = {doi_key(rows[index].get("doi")) for index in with_doi}
        if len(dois) == 1 and no_doi:
            for index in with_doi:
                union(index, no_doi[0])
    return len({find(index) for index in range(len(rows))})


def _draw_record(rng: Draw) -> dict[str, object]:
    record: dict[str, object] = {
        "author": _pick(rng, ("Ada Lovelace", "Grace Hopper", "Ng")),
        "title": _pick(rng, ("Port trade", "Coastal routes", "Harbour law")),
        "year": _pick(rng, (1999, 2019, "2020")),
        "doi": _pick(rng, ("", "10.1000/one", "10.1000/two")),
        "id": _pick(rng, ("", "src-1", "src-2")),
    }
    if rng.below(5) == 0:
        del record["author"]
    return record


def _draw_records(rng: Draw) -> list[dict[str, object]]:
    return [_draw_record(rng) for _ in range(rng.below(6))]


def test_distinct_works_follow_the_documented_identity_rules() -> None:
    """One id is one work, one DOI is one work, and two different DOIs stay two."""

    def holds(records: list[dict[str, object]]) -> bool:
        return len(distinct_works(records)) == documented_work_count(records)

    # Hand-counted examples. The expected numbers are not produced by the checker.
    same_doi = [
        {"author": "Ng", "title": "Port trade", "year": 2019, "doi": "10.1000/one"},
        {"author": "Ada Lovelace", "title": "Other", "year": 2020, "doi": "10.1000/one"},
    ]
    two_dois = [
        {"author": "Ng", "title": "Port trade", "year": 2019, "doi": "10.1000/one"},
        {"author": "Ng", "title": "Port trade", "year": 2019, "doi": "10.1000/two"},
    ]
    doi_and_plain = [
        {"author": "Ng", "title": "Port trade", "year": 2019, "doi": "10.1000/one"},
        {"author": "Ng", "title": "Port trade", "year": 2019},
    ]
    two_authors = [
        {"author": "Ng", "title": "Port trade", "year": 2019},
        {"author": "Ada Lovelace", "title": "Port trade", "year": 2019},
    ]
    assert len(distinct_works(same_doi)) == 1
    assert len(distinct_works(two_dois)) == 2
    assert len(distinct_works(doi_and_plain)) == 1
    assert len(distinct_works(two_authors)) == 2
    check(_draw_records, holds)


def test_a_repeated_record_does_not_add_a_work() -> None:
    """Appending a copy of a record leaves the distinct-work count unchanged."""

    def holds(records: list[dict[str, object]]) -> bool:
        base = len(distinct_works(records))
        if not records:
            return base == 0
        return len(distinct_works(records + [records[0]])) == base

    check(_draw_records, holds)


def test_work_order_does_not_change_the_count() -> None:
    """The same records in reverse order are the same number of works."""

    def holds(records: list[dict[str, object]]) -> bool:
        return len(distinct_works(records)) == len(distinct_works(list(reversed(records))))

    check(_draw_records, holds)


def test_a_harvard_line_keeps_the_documented_pieces() -> None:
    """Author and year stay together. A journal title is quoted. The container is italic.

    A book title is italic. The line ends with a stop. An empty source is Untitled download.
    """

    def draw(rng: Draw) -> dict[str, str]:
        return {
            "author": _pick(rng, ("", "Ng", "Ada Lovelace")),
            "year": _pick(rng, ("", "2019", "2020")),
            "title": _pick(rng, ("", "Port trade", "Coastal routes")),
            "container": _pick(rng, ("", "Journal of Ports")),
        }

    def holds(source: dict[str, str]) -> bool:
        line = harvard_4a_line(source)
        parts = harvard_4a_parts(source)
        if not line or line[-1] not in ".!?":
            return False
        author = source["author"]
        year = source["year"]
        title = source["title"]
        container = source["container"]
        if author and year and f"{author} ({year})" not in line:
            return False
        if author and not year and not line.startswith(author):
            return False
        if container and title and f"'{title}'" not in line:
            return False
        italics = [piece for piece, italic in parts if italic]
        if container and container not in italics:
            return False
        if container and title and title in italics:
            return False
        if title and not container and title not in italics:
            return False
        if not any((author, year, title, container)):
            return line == "Untitled download."
        return True

    check(draw, holds)


def test_et_al_starts_at_the_fourth_author() -> None:
    """Two or three authors are all named. The fourth author is et al. The brief does not change it."""

    def draw(rng: Draw) -> int:
        return rng.below(12) - 1

    def holds(count: int) -> bool:
        return in_text_uses_et_al(count, "spell every author") is (count >= 4)

    check(draw, holds)


def test_a_parenthetical_cite_is_removed_and_the_sentence_stays() -> None:
    """The removed span is reported. The words around a parenthetical cite stay, with no subject gap."""

    def draw(rng: Draw) -> list[str]:
        return [
            _pick(rng, ("Ng", "Ada", "Grace")),
            _pick(rng, ("1999", "2019", "2020")),
            _pick(rng, ("The ports grew", "Coastal trade held", "The harbour stayed open")),
            _pick(rng, ("after the storm", "through the decade", "along the coast")),
        ]

    def holds(parts: list[str]) -> bool:
        name, year, lead, tail = parts
        original = f"{lead} ({name}, {year}) {tail}."
        report = strip_token(original, f"{name}, {year}")
        if not isinstance(report, StripReport) or report.subject_gap:
            return False
        if f"({name}, {year})" in report.text:
            return False
        if lead not in report.text or tail not in report.text:
            return False
        return any(name in span and year in span for span in report.removed)

    check(draw, holds)


def test_a_narrative_cite_that_was_the_subject_is_unreadable() -> None:
    """Removing the name that governed the verb marks a subject gap, and the draft is not readable."""

    def draw(rng: Draw) -> list[str]:
        return [
            _pick(rng, ("Ng", "Ada", "Grace")),
            _pick(rng, ("1999", "2019", "2020")),
        ]

    def holds(parts: list[str]) -> bool:
        name, year = parts
        report = strip_token(f"{name} ({year}) shows the port.", f"{name}, {year}")
        if not isinstance(report, StripReport) or not report.subject_gap:
            return False
        refused = first_draft_unreadable(report)
        return isinstance(refused, dict) and refused.get("readable") is False

    check(draw, holds)


def test_a_doubled_comma_is_unreadable_and_a_plain_sentence_is_not() -> None:
    """A comma glued to a comma is not a finished first draft. A plain sentence is left alone."""

    def draw(rng: Draw) -> str:
        return _pick(rng, ("The ports grew", "Coastal trade held", "The harbour stayed open"))

    def holds(lead: str) -> bool:
        broken = first_draft_unreadable(f"{lead},, still.")
        plain = first_draft_unreadable(f"{lead}.")
        return isinstance(broken, dict) and broken.get("readable") is False and plain is None

    check(draw, holds)


def test_a_word_title_stays_within_255_and_is_not_the_opening(workspace) -> None:
    """The document title is at most 255 characters. The opening paragraph is never the title.

    A short stored title that is not the opening is kept. A longer one is not returned whole.
    """
    assert workspace.is_dir()

    def draw(rng: Draw) -> dict[str, str]:
        word = _pick(rng, ("Port", "Trade", "Coast", "Harbour", "Route", "Law"))
        stored = " ".join(word for _ in range(1 + rng.below(80)))
        opening = "The ports grew along the coast"
        if rng.below(4) == 0:
            opening = stored
        fallback = "" if rng.below(5) == 0 else "Harbour note"
        return {"stored": stored, "opening": opening, "fallback": fallback}

    def holds(case: dict[str, str]) -> bool:
        title = document_title(case["stored"], opening=case["opening"], fallback=case["fallback"])
        opening = " ".join(case["opening"].split())
        stored = " ".join(case["stored"].split())
        if len(title) > 255:
            return False
        if opening and title == opening:
            return False
        if stored and len(stored) <= 255 and stored != opening:
            return title == stored
        if len(stored) > 255 and title == stored:
            return False
        return True

    check(draw, holds)
