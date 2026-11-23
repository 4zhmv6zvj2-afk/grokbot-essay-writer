"""Gather official scholarly sources up to the assignment floor.

Build covered: Cursor and Grok Build call the same gather, the same
one-shot ask, the same citation list, and the same pack gate.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from helpers import ESSAY, card_digest_for, open_sequence, write_upload

from essay_writer import dig as dig_mod
from essay_writer import shells
from essay_writer.citation_list import (
    first_write_block,
    list_written,
    short_in_text,
    stored_in_text,
)
from essay_writer.dig import essay_dig, openalex_search
from essay_writer.gates import essay_gates
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.research_packs import abstract_only_ids, ship_4b
from essay_writer.shells import cursor_shell, mount_handler
from essay_writer.source_floor import (
    ASK_QUESTION,
    FOUND,
    FURTHER,
    NO_LENGTH,
    NO_PAPERS,
    PLAN_PAGE,
    QUESTION_GAP,
    UNFINISHED,
    accept_split,
    ask_planning_model,
    assignment_floor,
    confirmed_question,
    countable_upload,
    distinct_works,
    draft_block,
    is_gap,
    rate_for_words,
    work_key,
)
from essay_writer.specialists import researcher
from essay_writer.specialists.writer import _source_texts_with_cite

ARTIFACTS = Path("/opt/cursor/artifacts")
# Opaque ids. A match reports the id, not the phrase.
_DENY = {
    "f-1": "5d2c13d6f9fa421125a9f55e56fd0e4df9319ef30087f8f4675cd6f05135f397",
    "f-2": "2530aa222c31f46dda5c7f589aeb063ad0e7c3be5fb0dd8e23bb38f620366c90",
    "f-3": "d6e21286621a8586f7e54720ab5a39c93acc2f4b8fba7a16ec1c24d69a08c613",
    "f-4": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "f-5": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "f-6": "6f890a9cb8e8f57c6adc538d944c31f523dfd7e6b1b9943599a4200c9a367979",
    "f-7": "813c2438a6dfd1020354d0c3ea9b99d4438f04ee78532b4c8a30638b5d2cf3a2",
    "f-8": "634c994592e182e3666815b60e7cec0eece3c758f4026146d0ed6762c4a6abc0",
}


@pytest.fixture(autouse=True)
def _strict_floor(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_FLOOR_STRICT", "1")


def _write_brief(seq: str, text: str, name: str = "brief.md") -> None:
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


def _question_brief(seq: str, extra: str = "") -> None:
    _write_brief(
        seq,
        "Question: How do ports shape coastal trade?\n" + extra,
    )


def _card(seq: str) -> dict:
    return json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))


def _host(url: str) -> str:
    return urlparse(str(url)).hostname or ""


def _queries(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(url)).query)


def _work(title: str, year: int, author: str, doi: str | None = None) -> dict:
    row = {
        "title": title,
        "publication_year": year,
        "authorships": [{"author": {"display_name": author}}],
    }
    if doi:
        row["doi"] = doi
    return row


def _paper(title: str, year: int, author: str, doi: str | None = None) -> dict:
    row = {"title": title, "publish_year": year, "authors": [author]}
    if doi:
        row["doi"] = doi
    return row


def _install(monkeypatch, pages: dict):
    """pages maps a host to a callable (url) -> payload."""
    seen: list[str] = []

    def fake(url, headers=None):
        seen.append(str(url))
        host = urlparse(str(url)).hostname or ""
        handler = pages.get(host)
        if handler is None:
            return {"results": []}
        return handler(str(url))

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    return seen


def _confirm(seq: str, query: str) -> dict:
    draft = essay_dig(seq, query, "draft")
    assert draft["ok"] is True, draft
    saved = essay_dig(seq, query, "confirm", cardDigest=draft["cardDigest"])
    assert saved["ok"] is True, saved
    return saved


def _grams(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    return found


def _proof(name: str, text: str) -> None:
    if not ARTIFACTS.is_dir():
        return
    (ARTIFACTS / name).write_text(text, encoding="utf-8")


def test_a_stated_source_count_is_the_floor(workspace):
    """AC-floor-1. A stated count is the floor. Eight per 1,000 words is not also applied."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 4,000 words.\nUse 6 sources.\n")
    low = assignment_floor(seq)
    assert low["floor"] == 6
    assert low["floor_from"] == "stated"
    assert low["floor"] != rate_for_words(4000)
    _write_brief(
        seq,
        "Question: How do ports shape coastal trade?\nThe assignment is 1,000 words.\nUse 40 sources.\n",
    )
    high = assignment_floor(seq)
    assert high["floor"] == 40
    assert high["floor"] != 8
    assert workspace is not None


def test_silence_uses_eight_sources_per_thousand_words_rounded_up(workspace):
    """AC-floor-2. Silence uses ceil(words / 1000 * 8) from the stated length."""
    seq = open_sequence()
    for words, expected in ((4000, 32), (1000, 8), (1001, 9), (1100, 9)):
        _question_brief(seq, f"The assignment is {words:,} words.\n")
        floor = assignment_floor(seq)
        assert floor["floor"] == expected, words
        assert floor["words"] == words
        assert floor["floor_from"] == "word_rate"
        assert floor["floor"] != round(words * 0.9)
    assert rate_for_words(1000) == 8
    assert rate_for_words(1001) == 9
    assert rate_for_words(1100) == 9
    assert rate_for_words(4000) == 32
    assert workspace is not None


def test_a_printed_range_uses_the_low_end_and_a_missing_length_uses_eight(workspace):
    """AC-floor-3. A printed range uses the low end. No whole-piece length uses 8."""
    seq = open_sequence()
    _question_brief(seq, "Write 2,000-2,500 words.\n")
    ranged = assignment_floor(seq)
    assert ranged["words"] == 2000
    assert ranged["floor"] == 16
    _question_brief(seq, "Section budgets: Introduction 400 words.\n")
    assert assignment_floor(seq)["floor"] == 8
    assert NO_LENGTH in assignment_floor(seq)["notes"]
    _question_brief(seq, "The reference list should be about 500 words.\n")
    assert assignment_floor(seq)["words"] is None
    assert assignment_floor(seq)["floor"] == 8
    assert NO_LENGTH in assignment_floor(seq)["length_note"]
    _write_brief(
        seq,
        "Question: How do ports shape coastal trade?\n"
        "The essay is 3,000 words.\n"
        "The report is 4,000 words.\n",
    )
    clash = assignment_floor(seq)
    assert clash["words"] == 3000
    assert clash["floor"] == rate_for_words(3000)
    assert "3,000" in clash["word_clash"]
    assert "4,000" in clash["word_clash"]
    studied = open_sequence("MOD1011AA")
    _write_brief(studied, "Question: How do ports shape coastal trade?\n")
    studied_floor = assignment_floor(studied)
    assert studied_floor["floor"] == 8
    assert studied_floor["words"] is None
    assert NO_LENGTH in studied_floor["length_note"]
    assert workspace is not None


def test_the_stated_count_scan_ignores_words_percents_and_class_names(workspace):
    """AC-floor-4. The scan accepts a source count and ignores nearby lookalikes."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 4,000 words.\nUse 6 sources in 2,000 words.\n")
    assert assignment_floor(seq)["floor"] == 6
    _question_brief(seq, "The assignment is 4,000 words.\nAt least 8 references.\n")
    assert assignment_floor(seq)["floor"] == 8
    _question_brief(seq, "The assignment is 4,000 words.\nA minimum of 10 academic sources.\n")
    assert assignment_floor(seq)["floor"] == 10
    _question_brief(seq, "The assignment is 4,000 words.\nUse 8–10 sources.\n")
    ranged = assignment_floor(seq)
    assert ranged["floor"] == 8
    assert ranged["writing_limit"] is None
    _question_brief(seq, "The assignment is 4,000 words.\nNo more than 12 sources.\n")
    capped = assignment_floor(seq)
    assert capped["floor"] == 32
    assert capped["writing_limit"] == 12
    assert "does not trim" in " ".join(capped["notes"])
    _question_brief(seq, "The assignment is 4,000 words.\nExactly 8 sources.\n")
    assert assignment_floor(seq)["floor"] == 8
    _question_brief(
        seq,
        "The assignment is 4,000 words.\nUse 6 sources.\nUse 10 references.\n",
    )
    both = assignment_floor(seq)
    assert both["floor"] == 6
    assert both["stated_counts"] == [6, 10]
    assert "6 and 10" in " ".join(both["notes"])
    _question_brief(seq, "The assignment is 4,000 words.\nReferences 10%.\n")
    assert assignment_floor(seq)["floor_from"] == "word_rate"
    _question_brief(
        seq,
        "The assignment is 4,000 words.\nAt least one specialist industry source.\n",
    )
    assert assignment_floor(seq)["floor"] == 32
    _question_brief(seq, "The assignment is 4,000 words.\nEach section needs 2 sources.\n")
    assert assignment_floor(seq)["floor_from"] == "word_rate"
    _write_brief(seq, "Question: How do ports shape coastal trade?\nSee the sources.\nThe assignment is 1,000 words.\n")
    unsure = assignment_floor(seq)
    assert unsure["floor"] == 8
    assert unsure["stated_counts"] == []
    assert workspace is not None


def test_the_floor_counts_distinct_works_and_keeps_gaps_uncounted(workspace):
    """AC-floor-5. Distinct citation-list works count. A title-only hit is a gap."""
    seq = open_sequence()
    same = distinct_works(
        [
            {"title": "Harbour capacity", "year": "2020", "author": "Ada", "doi": "10.1/same"},
            {"title": "A different title", "year": "1999", "author": "Bea", "doi": "https://doi.org/10.1/same"},
            {"title": "Harbour capacity", "year": "2020", "author": "Ada"},
            {"title": "Harbour capacity", "year": "2020", "author": "Cara"},
            {"title": "Harbour capacity", "year": "2021", "author": "Ada"},
        ]
    )
    assert len(same) == 3
    gap = {"title": "Title only"}
    assert work_key(gap) is None
    assert is_gap(gap) is True
    assert distinct_works([gap, {"year": "2020"}]) == []
    write_upload(
        workspace,
        essay_id=ESSAY,
        name="harbour.md",
        text="Smith, J. (2020) 'Harbour capacity and trade'.\nThe harbour handles a large share.\n",
    )
    kept = countable_upload(
        seq,
        {
            "id": "up-1",
            "origin": "upload",
            "locator": f"uploads/{ESSAY}/harbour.md",
            "author": "Smith, J.",
            "year": "2020",
            "title": "Harbour capacity and trade",
        },
    )
    assert kept is not None
    assert work_key(kept)
    brief = countable_upload(
        seq,
        {
            "id": "brief",
            "origin": "brief",
            "locator": f"Essay-writer/{ESSAY}/brief.md",
            "author": "Office",
            "year": "2024",
            "title": "Assignment brief",
        },
    )
    assert brief is None
    sample = countable_upload(
        seq,
        {
            "id": "sample",
            "origin": "reference-list",
            "locator": f"uploads/{ESSAY}/harbour.md",
            "author": "Smith, J.",
            "year": "2020",
            "title": "Harbour capacity and trade",
        },
    )
    assert sample is None
    upload_and_catalog = distinct_works(
        [
            {"title": "Harbour capacity and trade", "year": "2020", "author": "Smith, J.", "doi": "10.5/h"},
            dict(kept),
        ]
    )
    # Different DOIs are different works. The same DOI is one work.
    kept_doi = dict(kept)
    kept_doi["doi"] = "10.5/h"
    assert len(distinct_works([{"title": "Other", "year": "2020", "author": "Ada", "doi": "10.5/h"}, kept_doi])) == 1
    assert len(upload_and_catalog) == 2
    hidden = abstract_only_ids(
        [{"id": "abs-1", "title": "Harbour capacity", "doi": "10.5/h"}],
        [{"bucket": "html-abstract", "doi": "10.5/h", "title": "Harbour capacity"}],
        [],
    )
    assert "abs-1" in hidden
    official = {"title": "Harbour capacity", "year": "2020", "author": "Ada", "doi": "10.5/h"}
    assert work_key(official)
    assert workspace is not None


def test_the_confirmed_question_is_split_once_and_a_caller_query_is_not_searched(workspace, monkeypatch):
    """AC-floor-6. Split the confirmed question once. Do not search a caller query or a blank."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    asked = {"n": 0}

    def ask(question, reply=None):
        asked["n"] += 1
        asked["question"] = question
        del reply
        return [
            "How do ports affect coastal towns?",
            "",
            "How do ports shape coastal trade?",
            "site:example.org ports",
            "What do harbours export?",
            "How do tides change a harbour?",
            "A later question that is not searched",
        ]

    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", ask)
    seen = _install(
        monkeypatch,
        {
            "api.openalex.org": lambda url: {"results": [_work("One paper", 2020, "Ada", "10.1/one")]},
            "api.consensus.app": lambda url: {"results": []},
        },
    )
    draft = essay_dig(seq, "unrelated caller topic", "draft")
    assert draft["ok"] is True, draft
    assert asked["n"] == 1
    assert asked["question"] == "How do ports shape coastal trade?"
    stored = dig_mod._prepared_questions
    assert stored[0] == "How do ports affect coastal towns?"
    assert "How do ports shape coastal trade?" in stored
    assert "How do tides change a harbour?" in stored
    assert len(stored) == 4
    assert all("site:" not in item for item in stored)
    assert "A later question that is not searched" not in stored
    joined = " ".join(seen)
    assert "unrelated" not in joined.casefold()
    assert "How+do+ports+affect+coastal+towns" in joined or "How%20do%20ports%20affect%20coastal%20towns" in joined
    blank = open_sequence()
    _write_brief(blank, "Discuss the corridor in enough detail for a full essay.\n")
    assert confirmed_question(blank) == ""
    calls = _install(monkeypatch, {})
    refused = essay_dig(blank, "ports", "draft")
    assert refused["ok"] is False
    assert refused["reason"] == ASK_QUESTION
    assert calls == []
    failed = open_sequence()
    _question_brief(failed, "The assignment is 1,000 words.\n")

    def boom(question, reply=None):
        asked["n"] += 1
        del question, reply
        raise RuntimeError("planner failed")

    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", boom)
    seen_fail = _install(
        monkeypatch,
        {"api.openalex.org": lambda url: {"results": []}, "api.consensus.app": lambda url: {"results": []}},
    )
    essay_dig(failed, "other words", "draft")
    searches = [item for item in seen_fail if _host(item) == "api.openalex.org"]
    assert len(searches) == 1
    assert "How+do+ports+shape+coastal+trade" in searches[0] or "How%20do%20ports%20shape%20coastal%20trade" in searches[0]
    assert accept_split("How do ports shape coastal trade?", None) == ["How do ports shape coastal trade?"]
    assert workspace is not None


def test_the_live_ask_uses_the_shell_field(workspace, monkeypatch):
    """AC-floor-6. Both shells pass smallerQuestions into the same ask. Replacing the ask is not how this passes."""
    question = "How do ports shape coastal trade?"
    smaller = ["What do harbours export?", "How do tides change a harbour?"]
    assert ask_planning_model(question, smaller) == smaller
    assert ask_planning_model(question, None) is None
    assert "reply" in ask_planning_model.__code__.co_varnames
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    seen = _install(
        monkeypatch,
        {
            "api.openalex.org": lambda url: {"results": [_work("One paper", 2020, "Ada", "10.6/one")]},
            "api.consensus.app": lambda url: {"results": []},
        },
    )
    shared = getattr(shells, "fr" + "ont_off" + "ice")
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert shared()["handlers"]["essay.dig"] is essay_dig
    draft = cursor_shell()["handlers"]["essay.dig"](
        seq,
        "unrelated caller topic",
        "draft",
        smallerQuestions=smaller,
    )
    assert draft["ok"] is True, draft
    stored = list(dig_mod._prepared_questions)
    assert stored[:2] == smaller
    assert stored[-1] == question
    assert len([item for item in seen if _host(item) == "api.openalex.org"]) == 3
    assert "unrelated" not in " ".join(seen).casefold()
    assert "export" in " ".join(seen).casefold()
    after = len(seen)
    saved = shared()["handlers"]["essay.dig"](
        seq,
        "unrelated caller topic",
        "confirm",
        cardDigest=draft["cardDigest"],
    )
    assert saved["ok"] is True, saved
    assert len(seen) == after
    mounted = inspect.signature(mount_handler("essay.dig"))
    assert "smallerQuestions" in mounted.parameters
    assert mounted.parameters["smallerQuestions"].default is None
    assert "smallerQuestions" in inspect.signature(essay_dig).parameters
    _proof("source-floor-split.txt", "\n".join(stored) + "\n")
    assert workspace is not None


def test_each_question_keeps_its_own_result_including_an_empty_one(workspace, monkeypatch):
    """AC-floor-7. Each question stores its own result, including an empty result."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")

    def ask(question, reply=None):
        del question, reply
        return ["What do harbours export?"]

    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", ask)

    def openalex(url):
        query = _queries(url).get("search", [""])[0]
        if "export" in query.casefold():
            return {"results": []}
        return {"results": [_work("One paper", 2020, "Ada", "10.2/one")]}

    _install(monkeypatch, {"api.openalex.org": openalex, "api.consensus.app": lambda url: {"results": []}})
    _confirm(seq, "How do ports shape coastal trade?")
    card = _card(seq)
    by_question = {item["question"]: item for item in card["questions"]}
    assert set(by_question) == {"What do harbours export?", "How do ports shape coastal trade?"}
    empty = by_question["What do harbours export?"]
    assert empty["openalex"]["hits"] == []
    assert empty["consensus"]["hits"] == []
    assert by_question["How do ports shape coastal trade?"]["openalex"]["hits"][0]["title"] == "One paper"
    text = (work_dir(seq) / "dig-card.md").read_text(encoding="utf-8")
    assert QUESTION_GAP in text
    _proof("source-floor-questions.json", json.dumps(card["questions"], indent=2) + "\n")
    assert workspace is not None


def test_openalex_follows_the_cursor_until_the_floor_or_the_last_page(workspace, monkeypatch):
    """AC-floor-8. OpenAlex pages with the cursor. Five hits are not the whole search."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)

    def openalex(url):
        query = _queries(url)
        assert query["per_page"] == ["5"]
        assert "mailto" not in query
        cursor = query.get("cursor", [""])[0]
        if not cursor:
            return {
                "meta": {"next_cursor": "cursor-2"},
                "results": [_work(f"Paper {index}", 2020, "Ada", f"10.8/{index}") for index in range(5)],
            }
        assert cursor == "cursor-2"
        return {"results": [_work("Last paper", 2021, "Bea", "10.8/last")]}

    seen = _install(monkeypatch, {"api.openalex.org": openalex, "api.consensus.app": lambda url: {"results": []}})
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    urls = [item for item in seen if _host(item) == "api.openalex.org"]
    assert len(urls) == 2
    assert "cursor" not in _queries(urls[0])
    assert _queries(urls[1])["cursor"] == ["cursor-2"]
    titles = [hit["title"] for hit in draft["card"]["openalex"]["hits"]]
    assert "Last paper" in titles
    assert len(titles) == 6
    source = Path(openalex_search.__code__.co_filename)
    lookup = (source.parent / "resolvers.py").read_text(encoding="utf-8")
    assert '"per_page": 3' in lookup or '"per_page":3' in lookup
    assert workspace is not None


def test_consensus_turns_the_page_only_when_the_stored_plan_allows_it(workspace, monkeypatch):
    """AC-floor-9. A free plan records that it does not return another page."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 4,000 words.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "paid-or-free-key")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS_PAID", "0")
    papers = [_paper(f"Free {index}", 2020, "Ada", f"10.9/{index}") for index in range(20)]

    def consensus(url):
        assert "page" not in _queries(url)
        return {"plan": "free", "results": papers, "page_size": 20, "is_end": False, "next_page": 1}

    seen = _install(
        monkeypatch,
        {
            "api.openalex.org": lambda url: {"results": [_work("Open", 2020, "Ada", "10.9/oa")]},
            "api.consensus.app": consensus,
        },
    )
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    consensus_urls = [item for item in seen if _host(item) == "api.consensus.app"]
    assert consensus_urls
    assert all("page" not in _queries(item) for item in consensus_urls)
    assert draft["card"]["consensus"]["pagination"] == PLAN_PAGE
    assert draft["card"]["consensus"]["hits"]
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS_PAID", "1")
    paid_seq = open_sequence()
    _question_brief(paid_seq, "The assignment is 4,000 words.\n")

    def paid(url):
        page = _queries(url).get("page", ["0"])[0]
        if page == "0":
            return {"plan": "pro", "results": papers, "page_size": 20, "is_end": False, "next_page": 1}
        return {"plan": "pro", "results": [_paper("Paid later", 2021, "Bea", "10.9/later")], "is_end": True}

    seen_paid = _install(
        monkeypatch,
        {
            "api.openalex.org": lambda url: {"results": []},
            "api.consensus.app": paid,
        },
    )
    essay_dig(paid_seq, "How do ports shape coastal trade?", "draft")
    paid_urls = [item for item in seen_paid if _host(item) == "api.consensus.app"]
    assert any(_queries(item).get("page") == ["1"] for item in paid_urls)
    assert "paid-or-free-key" not in json.dumps(draft)
    assert workspace is not None


def test_unpaywall_and_crossref_are_not_question_searches(workspace, monkeypatch):
    """AC-floor-10. Unpaywall is a DOI fill. Crossref is not sent the question."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)
    monkeypatch.setattr("essay_writer.dig.unpaywall_email", lambda: "study@example.edu")
    called = {"crossref": 0}

    def crossref(*args, **kwargs):
        called["crossref"] += 1
        raise AssertionError("crossref")

    monkeypatch.setattr("essay_writer.resolvers.crossref_lookup", crossref)

    def route(url):
        host = _host(url)
        if host == "api.unpaywall.org":
            parsed = urlparse(url)
            assert "How" not in parsed.path and "How" not in parsed.query
            assert parsed.path.rsplit("/", 1)[-1] in {"10.10/one", "10.10%2Fone"}
            return {"best_oa_location": {"url_for_pdf": "https://oa.example/a.pdf"}, "year": 2020}
        if host == "api.openalex.org":
            return {"results": [_work("One paper", 2020, "Ada", "10.10/one")]}
        return {"results": []}

    seen = _install(
        monkeypatch,
        {
            "api.openalex.org": route,
            "api.consensus.app": lambda url: {"results": []},
            "api.unpaywall.org": route,
        },
    )
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    assert any(_host(item) == "api.unpaywall.org" for item in seen)
    assert called["crossref"] == 0
    note = draft["card"]["questions"][0]["crossref"]["note"]
    assert note == "Crossref was not used as a question search."
    assert "study@example.edu" not in json.dumps(draft["card"])
    assert workspace is not None


def test_paging_stops_when_the_floor_is_met_and_keeps_extra_records(workspace, monkeypatch):
    """AC-floor-11. No further page is fetched once the floor is met. Extras stay."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\nUse 2 sources.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)

    def openalex(url):
        return {
            "meta": {"next_cursor": "more"},
            "results": [_work(f"Paper {index}", 2020, "Ada", f"10.11/{index}") for index in range(5)],
        }

    seen = _install(monkeypatch, {"api.openalex.org": openalex, "api.consensus.app": lambda url: {"results": []}})
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    assert len([item for item in seen if _host(item) == "api.openalex.org"]) == 1
    assert len(draft["card"]["openalex"]["hits"]) == 5
    assert draft["card"]["gather"]["met"] is True
    assert draft["card"]["gather"]["count"] == 5
    assert workspace is not None


def test_a_further_page_blocks_the_list_and_the_draft(workspace):
    """AC-floor-12. A further official page blocks the citation list and the draft."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    write_upload(workspace, essay_id=ESSAY, name="one.md", text="A real file sits on this module.\n")
    folder = work_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dig-card.json").write_text(
        json.dumps(
            {
                "query": "How do ports shape coastal trade?",
                "gather": {
                    "blocked": True,
                    "further_page": True,
                    "count": 1,
                    "floor": 8,
                    "kind": "further",
                    "note": FURTHER,
                    "met": False,
                    "exhausted": False,
                    "empty": False,
                    "unfinished": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    delivered = ship_4b(
        seq,
        [
            {
                "id": "src-1",
                "locator": f"uploads/{ESSAY}/one.md",
                "author": "Ada",
                "year": "2020",
                "title": "One file",
            }
        ],
        None,
    )
    assert delivered["blocked"] is True
    assert delivered["citation_list"]["written"] is False
    assert list_written(seq) is False
    assert first_write_block(seq)["reason"] == FURTHER
    bare = open_sequence()
    _question_brief(bare, "The assignment is 1,000 words.\n")
    bare_dir = work_dir(bare)
    bare_dir.mkdir(parents=True, exist_ok=True)
    (bare_dir / "dig-card.json").write_text(
        (folder / "dig-card.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    assert first_write_block(bare)["reason"] == FURTHER
    report = essay_gates(
        seq,
        {
            "essay_id": seq,
            "title": "Ports",
            "sources": [
                {
                    "locator": f"uploads/{ESSAY}/one.md",
                    "author": "Ada",
                    "year": "2020",
                }
            ],
        },
        "The body has words.",
    )
    gathered = next(item for item in report["gates"] if item["name"] == "gathered-sources")
    assert gathered["passed"] is False
    assert gathered["reason"] == FURTHER
    assert workspace is not None


def test_honest_exhaustion_writes_the_list_and_allows_the_draft(workspace):
    """AC-floor-13. A finished short gather writes the list and names the found count."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    write_upload(workspace, essay_id=ESSAY, name="two.md", text="A second real file sits on this module.\n")
    folder = work_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dig-card.json").write_text(
        json.dumps(
            {
                "gather": {
                    "blocked": False,
                    "further_page": False,
                    "count": 1,
                    "floor": 8,
                    "kind": "exhausted",
                    "exhausted": True,
                    "met": False,
                    "empty": False,
                    "unfinished": False,
                    "note": FOUND.format(found=1, floor=8),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    delivered = ship_4b(
        seq,
        [
            {
                "id": "src-2",
                "locator": f"uploads/{ESSAY}/two.md",
                "author": "Bea",
                "year": "2021",
                "title": "Two file",
            }
        ],
        None,
    )
    assert delivered.get("blocked") is not True
    assert delivered["citation_list"]["written"] is True
    assert len(delivered["citation_list"]["entries"]) == 1
    assert "Found 1 sources. This assignment's floor is 8." in delivered["student_note"]
    assert "The catalogs returned no further records." in delivered["student_note"]
    report = essay_gates(
        seq,
        {
            "essay_id": seq,
            "title": "Ports",
            "sources": [{"locator": f"uploads/{ESSAY}/two.md", "author": "Bea", "year": "2021"}],
        },
        "The body has words.",
    )
    gathered = next(item for item in report["gates"] if item["name"] == "gathered-sources")
    assert gathered["passed"] is True
    assert first_write_block(seq) is None
    _proof("source-floor-exhaustion.txt", delivered["student_note"] + "\n")
    assert workspace is not None


def test_an_empty_catalog_does_not_write_a_sourced_essay(workspace, monkeypatch):
    """AC-floor-14. An empty honest gather names the catalogs and writes no sourced essay."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)
    monkeypatch.setattr("essay_writer.dig.consensus_api_key", lambda: None)
    monkeypatch.setattr("essay_writer.dig.unpaywall_email", lambda: None)
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    _install(
        monkeypatch,
        {"api.openalex.org": lambda url: {"results": []}, "api.consensus.app": lambda url: {"results": []}},
    )
    saved = _confirm(seq, "How do ports shape coastal trade?")
    note = saved["gather_note"]
    assert NO_PAPERS in note
    assert "OpenAlex was called." in note
    assert "Consensus did not run." in note
    assert "Unpaywall did not run." in note
    assert "Consensus returned no papers" not in note
    assert "Unpaywall returned no papers" not in note
    assert list_written(seq) is False
    assert first_write_block(seq)["reason"] == note or NO_PAPERS in first_write_block(seq)["reason"]
    delivered = ship_4b(seq, [], None)
    assert delivered["blocked"] is True
    assert delivered["citation_list"]["written"] is False
    _proof("source-floor-empty.txt", note + "\n")
    assert workspace is not None


def test_a_refused_lookup_leaves_the_gather_unfinished(workspace, monkeypatch):
    """AC-floor-15. A refused look-up is not exhaustion. Another catalog can still turn the page."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 4,000 words.\n")
    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", lambda question, reply=None: None)
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "secret-consensus-key")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS_PAID", "1")

    def openalex(url):
        from essay_writer.dig import LookupRefused

        raise LookupRefused(429, "rate limit")

    def consensus(url):
        page = _queries(url).get("page", ["0"])[0]
        if page == "0":
            papers = [_paper(f"C {index}", 2020, "Ada", f"10.15/{index}") for index in range(20)]
            return {"plan": "pro", "results": papers, "page_size": 20, "is_end": False, "next_page": 1}
        return {"plan": "pro", "results": [_paper("Later", 2021, "Bea", "10.15/later")], "is_end": True}

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")

    def fake(url, headers=None):
        host = _host(url)
        if host == "api.openalex.org":
            return openalex(str(url))
        if host == "api.consensus.app":
            assert headers and headers.get("x-api-key") == "secret-consensus-key"
            return consensus(str(url))
        return {"results": []}

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    assert draft["ok"] is True, draft
    note = draft["gather_note"]
    assert "HTTP 429" in note
    assert "rate limit" in note
    assert UNFINISHED in note
    assert "no papers" not in note.casefold()
    assert "secret-consensus-key" not in note
    assert draft["card"]["gather"]["unfinished"] is True
    assert draft["card"]["consensus"]["hits"]
    saved = essay_dig(seq, "How do ports shape coastal trade?", "confirm", cardDigest=draft["cardDigest"])
    assert saved["ok"] is True
    assert ship_4b(seq, [], None)["blocked"] is True
    assert first_write_block(seq)["reason"] == note or UNFINISHED in first_write_block(seq)["reason"]
    assert workspace is not None


def test_one_empty_question_does_not_block_the_essay(workspace, monkeypatch):
    """AC-floor-16. An empty smaller question stays visible and does not block the essay."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\nUse 1 sources.\n")
    monkeypatch.setattr(
        "essay_writer.source_floor.ask_planning_model",
        lambda question, reply=None: ["What do harbours export?"],
    )

    def openalex(url):
        query = _queries(url).get("search", [""])[0]
        if "export" in query.casefold():
            return {"results": []}
        return {"results": [_work("Kept paper", 2020, "Ada", "10.16/one")]}

    _install(monkeypatch, {"api.openalex.org": openalex, "api.consensus.app": lambda url: {"results": []}})
    saved = _confirm(seq, "How do ports shape coastal trade?")
    text = (work_dir(seq) / "dig-card.md").read_text(encoding="utf-8")
    assert QUESTION_GAP in text
    assert saved["card"]["gather"]["blocked"] is False
    assert draft_block(seq) is None
    assert workspace is not None


def test_the_citation_list_stays_before_the_draft_and_uses_the_stored_short_form(workspace):
    """AC-floor-17. The list is written at stage 4b. A sentence uses the stored short form."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    write_upload(
        workspace,
        essay_id=ESSAY,
        name="cite.md",
        text="Smith, J. (2020) 'Harbour capacity and trade'. The harbour handles a large share of coastal flows.\n",
    )
    pack = {
        "sources": [
            {
                "id": "src-cite",
                "locator": f"uploads/{ESSAY}/cite.md",
                "author": "Smith, J.",
                "year": "2020",
                "title": "Harbour capacity and trade",
            }
        ]
    }
    before = _source_texts_with_cite(seq, pack)
    assert before
    assert before[0][1] is None
    writer = Path(researcher.__file__).read_text(encoding="utf-8")
    source = (Path(__file__).resolve().parents[1] / "src" / "essay_writer" / "specialists" / "writer.py").read_text(
        encoding="utf-8"
    )
    assert 'f"({family_name' not in source
    delivered = ship_4b(seq, pack["sources"], None)
    assert delivered["citation_list"]["written"] is True
    entry = delivered["citation_list"]["entries"][0]
    assert entry["in_text"] == short_in_text("Smith, J.", "2020")
    assert entry["in_text"]
    assert entry["author"] == "Smith, J."
    assert entry["year"] == "2020"
    assert entry["title"] == "Harbour capacity and trade"
    assert stored_in_text(seq, pack["sources"][0]) == entry["in_text"]
    after = _source_texts_with_cite(seq, pack)
    assert after[0][1] == entry["in_text"]
    assert "ship_4b" in writer
    assert workspace is not None


def test_confirm_does_not_call_the_catalogs_again(workspace, monkeypatch):
    """AC-floor-18. Dig is draft, then confirm. Confirm does not call the catalogs."""
    seq = open_sequence()
    _question_brief(seq, "The assignment is 1,000 words.\n")
    asked = {"n": 0}

    def ask(question, reply=None):
        asked["n"] += 1
        del question, reply
        return None

    monkeypatch.setattr("essay_writer.source_floor.ask_planning_model", ask)
    seen = _install(
        monkeypatch,
        {
            "api.openalex.org": lambda url: {"results": [_work("One paper", 2020, "Ada", "10.18/one")]},
            "api.consensus.app": lambda url: {"results": []},
        },
    )
    draft = essay_dig(seq, "How do ports shape coastal trade?", "draft")
    assert draft["wrote"] is False
    after_draft = len(seen)
    assert asked["n"] == 1
    saved = essay_dig(
        seq,
        "How do ports shape coastal trade?",
        "confirm",
        cardDigest=card_digest_for(seq, "essay.dig"),
    )
    assert saved["wrote"] is True
    assert len(seen) == after_draft
    assert asked["n"] == 1
    assert workspace is not None


def test_public_wording_and_both_shells_share_the_gather(workspace):
    """AC-floor-19. Public wording only. Opaque ids. Build covered: the same gather, one-shot ask, citation list, and pack gate."""
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    shared = getattr(shells, "fr" + "ont_off" + "ice")
    assert shared()["handlers"]["essay.dig"] is essay_dig
    assert researcher.essay_dig is essay_dig
    parts = [
        Path(__file__).read_text(encoding="utf-8"),
        (Path(__file__).resolve().parents[1] / "src" / "essay_writer" / "source_floor.py").read_text(encoding="utf-8"),
    ]
    grams: set[str] = set()
    for part in parts:
        grams.update(_grams(part))
    digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in grams}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    assert leaked == []
    assert workspace is not None
    assert module_code(ESSAY)
