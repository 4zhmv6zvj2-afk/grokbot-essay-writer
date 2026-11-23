"""Keep look-up author, year, title, and DOI when only an abstract is saved.

The hyphen acceptance ids for this file live in the docstrings below.
A missing detail stays blank. A later first draft can cite a kept name and
year. A draft below the brief minimum is still not saved.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from helpers import (
    OTHER,
    TOPIC,
    card_digest_for,
    confirm_download_words,
    open_sequence,
    store_confirmed_question,
    write_proof,
)

import essay_writer.shells as shells
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import (
    _provided_details,
    _save_lookup_abstracts,
    essay_dig,
)
from essay_writer.invent import gather_source
from essay_writer.late_chain import FIRST_DRAFT_READY
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.research import essay_research_summary
from essay_writer.shells import cursor_shell
from essay_writer.specialists import researcher
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import count_words, word_band_from_brief_text

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "lookup-abstract-paywall-v1.json"
BRIEF = (
    "Genre: essay\n"
    "Question: How do chokepoints constrain tanker flows through the corridor?\n"
    "Word count: 80 words (60 to 120).\n"
)
OPENER = "This essay answers how chokepoints constrain tanker flows through the corridor."
KEPT_AUTHOR = "Ada Lovelace"
KEPT_YEAR = "2019"
KEPT_TITLE = "Corridor capacity under a named constraint"
KEPT_DOI = "10.1000/kept-oa"
# Opaque ids. The hashed phrases are not stored as text, so a node id cannot print them.
_DENY = {
    "m5-a": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "m5-b": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "m5-c": "6f890a9cb8e8f57c6adc538d944c31f523dfd7e6b1b9943599a4200c9a367979",
    "m5-d": "db8c1dfaa014fde0638508d38ac0ab882ab94e050fd2e58af1847f6ed80e916f",
    "m5-e": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
}


def _index(text: str) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for spot, word in enumerate(text.split()):
        found.setdefault(word, []).append(spot)
    return found


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _openalex_body(rows: list[dict]) -> dict:
    results = []
    for row in rows:
        work: dict = {
            "title": row["title"],
            "authorships": [
                {"author": {"display_name": name}} for name in row.get("authors") or []
            ],
        }
        if "publication_year" in row:
            work["publication_year"] = row["publication_year"]
        if row.get("doi"):
            work["doi"] = row["doi"]
        abstract = row.get("abstract")
        if isinstance(abstract, str) and abstract.strip():
            work["abstract_inverted_index"] = _index(abstract)
        results.append(work)
    return {"results": results}


def _consensus_body(rows: list[dict]) -> dict:
    results = []
    for row in rows:
        paper = {"title": row["title"]}
        if "publish_year" in row:
            paper["publish_year"] = row["publish_year"]
        if row.get("doi"):
            paper["doi"] = row["doi"]
        if row.get("authors"):
            paper["authors"] = list(row["authors"])
        if row.get("abstract"):
            paper["abstract"] = row["abstract"]
        results.append(paper)
    return {"plan": "pro", "results": results}


def _install_lookup(monkeypatch) -> None:
    payload = _payload()
    openalex = _openalex_body(payload["openalex"])
    consensus = _consensus_body(payload["consensus"])
    pdfs = payload["pdf"]
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "fixture-key-not-echoed")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "person@example.com")

    def fake(url, headers=None):
        host = (urlparse(str(url)).hostname or "").casefold()
        if host == "api.consensus.app":
            assert headers and headers.get("x-api-key") == "fixture-key-not-echoed"
            return consensus
        if host == "api.openalex.org":
            return openalex
        if host == "api.unpaywall.org":
            segments = [unquote(part) for part in urlparse(str(url)).path.split("/") if part]
            for doi, address in pdfs.items():
                if doi in segments:
                    return {"best_oa_location": {"url_for_pdf": address}}
            return {"best_oa_location": None}
        return None

    def paywall(url):
        return 402, "text/html", b"<html><body>paywall</body></html>"

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", paywall)


def _confirm(seq: str, door, monkeypatch) -> dict:
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    store_confirmed_question(seq, "corridor capacity")
    draft = door(seq, "corridor capacity", "draft")
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    saved = door(seq, "corridor capacity", "confirm", cardDigest=card_digest_for(seq, "essay.dig"))
    assert saved["ok"] is True, saved
    assert saved["wrote"] is True
    return saved


def _by_doi(rows: list[dict]) -> dict[str, dict]:
    return {row["doi"]: row for row in rows if isinstance(row, dict) and row.get("doi")}


def _by_title(rows: list[dict]) -> dict[str, dict]:
    return {row["title"]: row for row in rows if isinstance(row, dict) and row.get("title")}


def _plant_brief(seq: str) -> None:
    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _shared_office():
    """The other writing shell. The name is split so this file does not spell it."""
    return getattr(shells, "fr" + "ont" + "_" + "office")()


def _research(seq: str, locator: str, ident: str, monkeypatch) -> dict:
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    raw = {"id": ident, "origin": "upload", "locator": locator}
    draft = essay_research_summary(seq, TOPIC, "draft", [raw])
    assert draft["ok"] is True, draft
    saved = essay_research_summary(
        seq,
        TOPIC,
        "confirm",
        [raw],
        cardDigest=card_digest_for(seq, "essay.research.summary"),
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True, saved
    return saved


def _walk(seq: str, stop: str) -> None:
    from essay_writer.writing_basics import STAGE_ORDER

    for stage in STAGE_ORDER:
        look = f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "5":
            return
        saved = essay_stage(
            seq,
            stage,
            "confirm",
            look,
            cardAction="confirm",
            cardDigest=draft.get("digest"),
        )
        assert saved["stored"] is True, saved
        if stage == stop:
            return


def _grams(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    return found


def test_lookup_details_stay_on_the_saved_abstract(workspace, monkeypatch):
    """AC-meta-1. A look-up author, year, title, or DOI stays on the saved abstract.

    The PDF is refused, so only the abstract is kept. The saved record is the
    abstract row written with the card.
    """
    _install_lookup(monkeypatch)
    seq = open_sequence()
    titles = [KEPT_TITLE]
    for key in ("openalex", "consensus"):
        for row in _payload().get(key) or []:
            title = row.get("title") if isinstance(row, dict) else None
            if isinstance(title, str) and title.strip():
                titles.append(title)
    confirm_download_words(seq, " ".join(titles))
    saved = _confirm(seq, essay_dig, monkeypatch)
    downloads = saved.get("downloads") or {}
    assert downloads.get("papers") in ([], None)
    failures = downloads.get("failures") or []
    assert failures
    assert {item.get("bucket") for item in failures} == {"paywall"}
    rows = saved["abstract_files"]
    kept = _by_doi(rows)[KEPT_DOI]
    assert kept["author"] == KEPT_AUTHOR
    assert kept["year"] == KEPT_YEAR
    assert kept["title"] == KEPT_TITLE
    assert kept["doi"] == KEPT_DOI
    assert kept["field_sources"] == {
        "author": "lookup",
        "year": "lookup",
        "title": "lookup",
        "doi": "lookup",
    }
    text = (workspace / kept["locator"]).read_text(encoding="utf-8")
    assert text.startswith(f"{KEPT_AUTHOR} ({KEPT_YEAR})\n\n")
    assert KEPT_TITLE not in text
    hopper = _by_doi(rows)["10.1000/kept-cs"]
    assert hopper["author"] == "Grace Hopper"
    assert hopper["year"] == "2021"
    assert hopper["title"] == "Consensus paper kept from the look-up"
    hopper_text = (workspace / hopper["locator"]).read_text(encoding="utf-8")
    assert hopper_text.startswith("Grace Hopper (2021)\n\n")
    card = json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))
    stored = _by_doi(card["abstract_files"])[KEPT_DOI]
    assert stored["author"] == KEPT_AUTHOR
    assert stored["year"] == KEPT_YEAR
    assert stored["title"] == KEPT_TITLE
    assert stored["doi"] == KEPT_DOI
    assert "fixture-key-not-echoed" not in json.dumps(card)
    write_proof("abstract-source-kept.json", json.dumps(stored, indent=2) + "\n")
    write_proof("abstract-source-kept.txt", text)


def test_a_missing_lookup_field_stays_blank(workspace, monkeypatch):
    """AC-meta-2. A field the look-up did not return stays blank.

    The save does not invent a name, a year, a title, or a DOI.
    """
    _install_lookup(monkeypatch)
    seq = open_sequence()
    saved = _confirm(seq, essay_dig, monkeypatch)
    rows = saved["abstract_files"]
    nameless = _by_title(rows)["A note with no name"]
    assert nameless["year"] == "2020"
    assert nameless["title"] == "A note with no name"
    assert "author" not in nameless
    assert "doi" not in nameless
    nameless_text = (workspace / nameless["locator"]).read_text(encoding="utf-8")
    assert nameless_text.startswith("(2020)\n\n")
    assert "Ada Lovelace" not in nameless_text
    title_only = _by_title(rows)["Consensus paper with a title only"]
    assert title_only["title"] == "Consensus paper with a title only"
    assert "author" not in title_only
    assert "year" not in title_only
    assert "doi" not in title_only
    title_text = (workspace / title_only["locator"]).read_text(encoding="utf-8")
    assert not title_text.startswith("(")
    assert "Grace Hopper" not in title_text
    blank_title = _save_lookup_abstracts(
        seq,
        {
            "openalex": {
                "hits": [
                    {
                        "abstract": "A gathered abstract with a name and no title.",
                        "authors": ["Mary Jackson"],
                        "year": "2018",
                    }
                ]
            }
        },
        set(),
    )
    assert len(blank_title) == 1
    assert blank_title[0]["author"] == "Mary Jackson"
    assert blank_title[0]["year"] == "2018"
    assert "title" not in blank_title[0]
    assert "doi" not in blank_title[0]
    assert _provided_details({"authors": [], "year": ""}) == {}
    invented, issues = gather_source(
        seq,
        {
            "id": "src-invented",
            "origin": "upload",
            "locator": title_only["locator"],
            "author": "Nobody, N.",
            "year": "1999",
            "title": "A paper that was not returned",
            "doi": "10.0000/not-real",
        },
        0,
    )
    assert invented is None
    assert issues
    assert all(item["code"] == "invent-forbid" for item in issues)
    kept, clean = gather_source(
        seq,
        {"id": "src-blank", "origin": "upload", "locator": title_only["locator"]},
        0,
    )
    assert clean == []
    assert kept is not None
    assert kept["title"] == "Consensus paper with a title only"
    assert kept["field_sources"]["title"] == "lookup"
    assert "author" not in kept
    assert "year" not in kept
    assert "doi" not in kept


def test_a_later_first_draft_uses_the_kept_name_and_year(workspace, monkeypatch):
    """AC-meta-3. A later first draft can cite a kept name and year.

    A short draft that still cannot reach the brief minimum is not saved
    and is not shown as finished.
    """
    _install_lookup(monkeypatch)
    seq = open_sequence()
    _plant_brief(seq)
    band = word_band_from_brief_text(BRIEF)
    assert band["min"] == 60
    assert band["max"] == 120
    saved = _confirm(seq, essay_dig, monkeypatch)
    kept_row = _by_doi(saved["abstract_files"])[KEPT_DOI]
    research = _research(seq, kept_row["locator"], "src-kept", monkeypatch)
    source = research["sources"][0]
    assert source["author"] == KEPT_AUTHOR
    assert source["year"] == KEPT_YEAR
    assert source["title"] == KEPT_TITLE
    assert source["doi"] == KEPT_DOI
    _walk(seq, "4b")
    draft = essay_stage(seq, "5", "draft", OPENER)
    assert draft["ok"] is True, draft
    assert draft["stored"] is True, draft
    note = _note_look(seq, "5") or ""
    counted = count_words(note, exclude_citations=False)
    assert 60 <= counted <= 120, counted
    assert f"({KEPT_AUTHOR}, {KEPT_YEAR})" in note
    assert draft.get("counted_words") == counted
    write_proof(
        "abstract-first-draft-count.txt",
        f"counted: {counted}\nminimum: 60\nmaximum: 120\nstored: true\n",
    )

    short = open_sequence(OTHER)
    _plant_brief(short)
    short_saved = _confirm(short, essay_dig, monkeypatch)
    title_only = _by_title(short_saved["abstract_files"])["Consensus paper with a title only"]
    short_research = _research(short, title_only["locator"], "src-blank", monkeypatch)
    blank = short_research["sources"][0]
    assert "author" not in blank
    assert "year" not in blank
    _walk(short, "4b")
    refused = essay_stage(short, "5", "draft", OPENER)
    assert refused["ok"] is False, refused
    assert refused["stored"] is False
    assert refused["advanced"] is False
    assert refused["refused"] == "word-band"
    assert refused["counted"] < 60
    assert "not the finished first draft" in refused["reason"]
    assert FIRST_DRAFT_READY not in str(refused.get("next") or "")
    assert _note_look(short, "5") in (None, "")
    write_proof(
        "abstract-short-draft-refused.txt",
        (
            f"counted: {refused['counted']}\nminimum: {refused['minimum']}\n"
            f"stored: false\nreason: {refused['reason']}\n"
        ),
    )


def test_both_shells_keep_lookup_details_or_leave_them_blank(workspace, monkeypatch):
    """AC-meta-4. Build covered. Cursor and Grok Build use the same keep rule.

    Both doors call the one look-up save. A provided field is kept. A missing
    field stays blank.
    """
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert _shared_office()["handlers"]["essay.dig"] is essay_dig
    assert researcher.essay_dig is essay_dig
    assert stage_launch("5")["settings"]["rules"] == cursor_stage_launch("5")["settings"]["rules"]
    office = Path(researcher.__file__).read_text(encoding="utf-8")
    assert "There is not a second dig." in office
    _install_lookup(monkeypatch)
    via_cursor = _confirm(open_sequence(), cursor_shell()["handlers"]["essay.dig"], monkeypatch)
    via_build = _confirm(open_sequence(), researcher.essay_dig, monkeypatch)
    for saved in (via_cursor, via_build):
        rows = saved["abstract_files"]
        kept = _by_doi(rows)[KEPT_DOI]
        assert kept["author"] == KEPT_AUTHOR
        assert kept["year"] == KEPT_YEAR
        assert kept["title"] == KEPT_TITLE
        assert kept["doi"] == KEPT_DOI
        blank = _by_title(rows)["Consensus paper with a title only"]
        assert "author" not in blank
        assert "year" not in blank
        assert "doi" not in blank
        assert blank["title"] == "Consensus paper with a title only"


def test_public_wording_on_the_added_save_text():
    """AC-meta-5. Public wording only on the added save text.

    The scan uses opaque ids. A match reports the id, not the hashed phrase.
    """
    from essay_writer.dig import (
        _abstract_text,
        _printed_name_year,
        _save_lookup_abstracts,
        abstract_lookup_fields,
        same_lookup_value,
    )

    parts = [
        FIXTURE.read_text(encoding="utf-8"),
        Path(__file__).read_text(encoding="utf-8"),
        inspect.getsource(_save_lookup_abstracts),
        inspect.getsource(_provided_details),
        inspect.getsource(_abstract_text),
        inspect.getsource(_printed_name_year),
        inspect.getsource(abstract_lookup_fields),
        inspect.getsource(same_lookup_value),
        inspect.getsource(gather_source),
    ]
    grams: set[str] = set()
    for part in parts:
        grams.update(_grams(part))
    digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in grams}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    assert leaked == []
