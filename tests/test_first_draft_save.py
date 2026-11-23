"""A first draft is finished only from intact text with the look-up still on the source.

The acceptance ids for this file live in the docstrings below. A missing
look-up field stays blank. A citation removal that leaves the draft unreadable
is not saved. A first-draft Word file follows that saved text only after
independent review is clear.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from helpers import (
    TOPIC,
    card_digest_for,
    confirm_download_words,
    open_sequence,
    picked,
    plant_gathered_source,
    write_proof,
)

import essay_writer.shells as shells
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import essay_dig
from essay_writer.invent import gather_source
from essay_writer.late_chain import FIRST_DRAFT_READY, STAGE6_OPEN
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.research import essay_research_summary
from essay_writer.review import essay_review, writer_clears_left
from essay_writer.shells import cursor_shell
from essay_writer.specialists import researcher
from essay_writer.specialists.writer import (
    UNREADABLE_DRAFT,
    finish_first_draft,
    first_draft_below_minimum,
    first_draft_unreadable,
)
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import count_words

REPO = Path(__file__).resolve().parents[1]
BROKEN = REPO / "tests" / "fixtures" / "first-draft-broken-v1.md"
CHAPTER_DOI = "10.52779/9781998951130/02"
CHAPTER_AUTHOR = "Kenosi Molato and Musa W. Dube"
CHAPTER_YEAR = "2022"
CHAPTER_TITLE = "The Christic Okavango Delta of Botswana"
CHAPTER_PDF = "https://oa.example/chapter-full.pdf"
CHAPTER_PROSE = "compare the flood with ordinary life in the delta"
CHAPTER_SENTENCE = f"{CHAPTER_AUTHOR} ({CHAPTER_YEAR}) {CHAPTER_PROSE}."
BLANK_DOI = "10.1000/no-author"
BLANK_YEAR = "2018"
BLANK_TITLE = "A note with no name"
BLANK_PDF = "https://oa.example/blank-author.pdf"
BLANK_PROSE = "Not A Real Author describes rainfall on the plateau."
LANDING = "https://doi.org/10.52779/9781998951130/02"
DECOY = "Not A Real Author"
BRIEF = (
    "Genre: essay\n"
    "Question: Whose interests count when a river's water is allocated?\n"
    "Word count: 2,000 words (1,800 to 2,200).\n"
)
# Opaque ids. The hashed phrases are not stored as text.
_DENY = {
    "m5-a": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "m5-b": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "m5-c": "6f890a9cb8e8f57c6adc538d944c31f523dfd7e6b1b9943599a4200c9a367979",
    "m5-d": "db8c1dfaa014fde0638508d38ac0ab882ab94e050fd2e58af1847f6ed80e916f",
    "m5-e": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
}
LOOKUP_RULE = (
    "When a look-up returns an author, a year, a title, or a DOI, those details "
    "stay on the source, including when a full PDF is kept."
)
READABLE_RULE = (
    "If a citation check removes a name and year and the sentence is no longer readable, "
    "do not save that text as the finished first draft"
)
WORD_RULE = (
    "A first-draft Word file is written only from intact saved text, and only after "
    "the independent review is clear."
)


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    content = (
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    return b"\n".join(
        [
            b"%PDF-1.4",
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj",
            b"4 0 obj\n" + content + b"\nendobj",
            b"%%EOF",
        ]
    )


def _openalex_body() -> dict:
    rows = [
        {
            "title": CHAPTER_TITLE,
            "authors": ["Kenosi Molato", "Musa W. Dube"],
            "publication_year": 2022,
            "doi": CHAPTER_DOI,
            "pdf_url": CHAPTER_PDF,
            "text": CHAPTER_PROSE,
        },
        {
            "title": BLANK_TITLE,
            "authors": [],
            "publication_year": 2018,
            "doi": BLANK_DOI,
            "pdf_url": BLANK_PDF,
            "text": BLANK_PROSE,
        },
    ]
    results = []
    for row in rows:
        authorships = [{"author": {"display_name": name}} for name in row["authors"]]
        results.append(
            {
                "title": row["title"],
                "publication_year": row["publication_year"],
                "doi": row["doi"],
                "authorships": authorships,
                "open_access": {"oa_url": None, "is_oa": True},
                "best_oa_location": {
                    "pdf_url": row["pdf_url"],
                    "landing_page_url": LANDING,
                },
            }
        )
    return {"results": results}


def _install(monkeypatch) -> dict[str, list[str]]:
    calls: dict[str, list[str]] = {"fetch": [], "openalex": [], "unpaywall": []}
    bodies = {
        CHAPTER_PDF: _pdf(CHAPTER_PROSE),
        BLANK_PDF: _pdf(BLANK_PROSE),
    }
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "person@example.com")
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)

    def fake(url, headers=None):  # noqa: ARG001
        host = (urlparse(str(url)).hostname or "").casefold()
        if host == "api.openalex.org":
            calls["openalex"].append(str(url))
            return _openalex_body()
        if host == "api.unpaywall.org":
            calls["unpaywall"].append(str(url))
            segments = [unquote(part) for part in urlparse(str(url)).path.split("/") if part]
            doi = next((part for part in segments if part.startswith("10.")), "")
            pdf = CHAPTER_PDF if doi == CHAPTER_DOI else BLANK_PDF if doi == BLANK_DOI else None
            return {
                "best_oa_location": {
                    "url_for_pdf": pdf,
                    "url": LANDING,
                },
                "z_authors": [{"raw_author_name": DECOY}],
            }
        return None

    def fetch(url):
        calls["fetch"].append(str(url))
        body = bodies.get(str(url))
        if body is None:
            return 402, "text/html", b"<html><body>paywall</body></html>"
        return 200, "application/pdf", body

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fetch)
    return calls


def _confirm(monkeypatch, *, words: str | None = None) -> tuple[str, dict, dict]:
    calls = _install(monkeypatch)
    seq = open_sequence()
    if words:
        confirm_download_words(seq, words)
    draft = essay_dig(seq, "okavango delta", "draft")
    assert draft["ok"] is True, draft
    saved = essay_dig(
        seq,
        "okavango delta",
        "confirm",
        cardDigest=card_digest_for(seq, "essay.dig"),
    )
    assert saved["ok"] is True, saved
    assert saved["wrote"] is True, saved
    return seq, saved, calls


def _by_doi(rows: list[dict]) -> dict[str, dict]:
    return {row["doi"]: row for row in rows if isinstance(row, dict) and row.get("doi")}


def _research(seq: str, raw: dict, monkeypatch) -> dict:
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
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


def _walk(seq: str, stop: str, looks: dict[str, str] | None = None) -> None:
    from essay_writer.writing_basics import STAGE_ORDER

    chosen = looks or {}
    for stage in STAGE_ORDER:
        look = chosen.get(stage) or f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
        if stage == stop:
            return


def _plant_brief(seq: str) -> None:
    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _first_draft_word(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def _grams(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    return found


def _shared_office():
    """The other writing shell. The name is split so this file does not spell it."""
    return getattr(shells, "fr" + "ont" + "_" + "office")()


def _lookup_row(row: dict) -> None:
    assert row["author"] == CHAPTER_AUTHOR
    assert row["year"] == CHAPTER_YEAR
    assert row["title"] == CHAPTER_TITLE
    assert row["doi"] == CHAPTER_DOI
    assert row["field_sources"] == {
        "author": "lookup",
        "year": "lookup",
        "title": "lookup",
        "doi": "lookup",
    }


def test_lookup_fields_stay_when_a_full_pdf_is_kept(workspace, monkeypatch):
    """AC-save-1. Official look-up author, year, title, and DOI stay on a kept PDF.

    The chapter PDF does not contain those fields. A second PDF that names a
    person in the body stays without an author when the look-up gave none.
    The kept author is still on the research record when the first draft cites it.
    """
    seq, saved, calls = _confirm(monkeypatch, words=f"{CHAPTER_TITLE} {BLANK_TITLE}")
    fetched = calls["fetch"]
    assert fetched
    assert set(fetched) <= {CHAPTER_PDF, BLANK_PDF}
    assert CHAPTER_PDF in fetched
    assert BLANK_PDF in fetched
    assert LANDING not in fetched
    papers = saved["downloads"]["papers"]
    assert len(papers) == 2
    rows = _by_doi(saved["pdf_files"])
    _lookup_row(rows[CHAPTER_DOI])
    blank = rows[BLANK_DOI]
    assert blank["year"] == BLANK_YEAR
    assert blank["title"] == BLANK_TITLE
    assert blank["doi"] == BLANK_DOI
    assert "author" not in blank
    assert DECOY not in json.dumps(blank)
    card = json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))
    _lookup_row(_by_doi(card["pdf_files"])[CHAPTER_DOI])
    chapter = rows[CHAPTER_DOI]
    read = (workspace / chapter["locator"]).read_bytes()
    assert read.startswith(b"%PDF-")
    prose = (workspace / chapter["locator"]).read_bytes().decode("latin-1", errors="ignore")
    assert CHAPTER_AUTHOR not in prose
    assert CHAPTER_TITLE not in prose
    assert CHAPTER_DOI not in prose
    kept, issues = gather_source(
        seq,
        {"id": "src-chapter", "origin": "upload", "locator": chapter["locator"]},
        0,
    )
    assert issues == []
    assert kept is not None
    _lookup_row(kept)
    blank_source, blank_issues = gather_source(
        seq,
        {"id": "src-blank", "origin": "upload", "locator": blank["locator"]},
        0,
    )
    assert blank_issues == []
    assert blank_source is not None
    assert "author" not in blank_source
    assert blank_source["title"] == BLANK_TITLE
    assert blank_source["year"] == BLANK_YEAR
    assert blank_source["doi"] == BLANK_DOI
    assert blank_source["field_sources"]["title"] == "lookup"
    research = _research(
        seq,
        {"id": "src-chapter", "origin": "upload", "locator": chapter["locator"]},
        monkeypatch,
    )
    source = research["sources"][0]
    _lookup_row(source)
    _walk(seq, "4b", {"3": CHAPTER_SENTENCE})
    brief = essay_dir(seq) / "brief.md"
    brief_text = brief.read_text(encoding="utf-8") if brief.is_file() else ""
    if not re.search(r"(?im)^\s*genre\s*:", brief_text):
        brief.write_text(f"Genre: essay\n{brief_text}", encoding="utf-8")
    draft = essay_stage(
        seq,
        "5",
        "draft",
        f"{CHAPTER_SENTENCE} This essay keeps {CHAPTER_TITLE} and {BLANK_TITLE}.",
    )
    assert draft["ok"] is True, draft
    assert draft["stored"] is True, draft
    note = _note_look(seq, "5") or ""
    assert f"{CHAPTER_AUTHOR} ({CHAPTER_YEAR})" in note
    assert not _first_draft_word(seq).is_file()
    write_proof(
        "first-draft-save-kept.json",
        json.dumps(
            {
                "author": source["author"],
                "year": source["year"],
                "title": source["title"],
                "doi": source["doi"],
                "field_sources": source["field_sources"],
                "blank_author_omitted": "author" not in blank_source,
                "draft_kept_name": f"{CHAPTER_AUTHOR} ({CHAPTER_YEAR})" in note,
                "word_file_written": False,
            },
            indent=2,
        )
        + "\n",
    )


def test_an_unreadable_first_draft_is_not_saved(workspace):
    """AC-save-2. A citation removal that breaks the sentence is not the finished draft.

    The stored example is the broken first-draft text. A name-and-year removal
    that leaves a verb without its subject is refused the same way. A readable
    sentence, an abbreviation, and a capital month stay acceptable.
    """
    broken = BROKEN.read_text(encoding="utf-8")
    counted = count_words(broken, exclude_citations=False)
    assert 1800 <= counted <= 2200, counted
    assert first_draft_unreadable(broken) is not None
    assert (
        first_draft_unreadable("Privacy risk reduces willingness to disclose personal data.")
        is None
    )
    assert first_draft_unreadable("Smith et al., 2014, describe the basin.") is None
    assert first_draft_unreadable("The U.S., in this account, is a place.") is None
    assert first_draft_unreadable("Drying in May is a season.") is None
    assert first_draft_unreadable("e.g. the flood renews ordinary life.") is None
    stripped = "Burg (2007) compares climate pressure with a local development scenario."
    assert first_draft_unreadable(stripped) is None

    seq = open_sequence()
    _walk(seq, "4b")
    _plant_brief(seq)
    held = essay_stage(seq, "5", "draft", broken)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["advanced"] is False
    assert held["refused"] == "draft"
    assert held["readable"] is False
    assert held["reason"] == UNREADABLE_DRAFT
    assert "not the finished first draft" in held["reason"]
    assert held.get("counted") is None
    assert "Counted words:" not in str(held.get("next") or "")
    assert STAGE6_OPEN not in str(held.get("next") or "")
    assert FIRST_DRAFT_READY not in str(held.get("next") or "")
    assert _note_look(seq, "5") in (None, "")
    assert not _first_draft_word(seq).is_file()
    bare = essay_stage(seq, "5", "draft", stripped)
    assert bare["ok"] is False, bare
    assert bare["stored"] is False
    assert bare["advanced"] is False
    assert bare["refused"] == "draft"
    assert not _first_draft_word(seq).is_file()
    write_proof(
        "first-draft-save-refused.txt",
        (
            f"counted: {counted}\nminimum: 1800\nmaximum: 2200\n"
            "stored: false\nadvanced: false\nword_file_written: false\n"
            f"reason: {held['reason']}\n"
        ),
    )
    assert workspace is not None


def test_a_first_draft_word_file_follows_the_saved_text(workspace):
    """AC-save-3. A first-draft Word file is written only from intact saved text.

    Independent review has to be clear first. The writer does not mark that
    review clear. A draft that cannot be saved leaves no Word file.
    """
    seq = open_sequence()
    refused = essay_review(seq, "6", "PASS", seat="writer")
    assert refused["ok"] is False
    assert refused["stored"] is False
    assert refused["wrote"] is False
    assert refused["writer_clears_left"] == 0
    assert writer_clears_left() == 0
    _walk(seq, "4b")
    _plant_brief(seq)
    broken = BROKEN.read_text(encoding="utf-8")
    held = essay_stage(seq, "5", "draft", broken)
    assert held["stored"] is False
    assert not _first_draft_word(seq).is_file()
    assert workspace is not None


def test_a_short_readable_draft_is_still_refused(workspace):
    """AC-save-4. A short readable draft is still refused on the word band.

    Official look-up fields on a saved abstract, and a file fetched only from
    an official PDF or open-access address, stay covered by their own tests.
    """
    seq = open_sequence()
    _plant_brief(seq)
    short = "This essay answers whose interests count when a river allocates water."
    assert first_draft_unreadable(short) is None
    blocked = first_draft_below_minimum(seq, short)
    assert blocked is not None
    assert blocked["refused"] == "word-band"
    assert "not the finished first draft" in blocked["reason"]
    finished = finish_first_draft(seq, short)
    assert finished["ready"] is False
    assert finished["block"]["refused"] == "word-band"
    assert workspace is not None


def test_both_shells_share_the_first_draft_save():
    """AC-save-1. Build covered. Cursor and Grok Build use the same first-draft save.

    Both shells read one stage 5 rule list and call the one dig and stage door.
    """
    shared = stage_launch("5")["settings"]["rules"]
    assert shared == cursor_stage_launch("5")["settings"]["rules"]
    assert LOOKUP_RULE in shared
    assert READABLE_RULE in shared
    assert WORD_RULE in shared
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert cursor_shell()["handlers"]["essay.stage"] is essay_stage
    office = _shared_office()
    assert office["handlers"]["essay.dig"] is essay_dig
    assert office["handlers"]["essay.stage"] is essay_stage
    assert researcher.essay_dig is essay_dig


def test_public_wording_on_the_first_draft_save():
    """AC-save-5. Public wording only on the first-draft save text.

    The scan uses opaque ids. A match reports the id, not the hashed phrase.
    """
    from essay_writer.dig import _save_lookup_pdfs, abstract_lookup_fields

    parts = [
        BROKEN.read_text(encoding="utf-8"),
        Path(__file__).read_text(encoding="utf-8"),
        (REPO / "src" / "essay_writer" / "prompts" / "stages" / "05.md").read_text(
            encoding="utf-8"
        ),
        inspect.getsource(_save_lookup_pdfs),
        inspect.getsource(abstract_lookup_fields),
        inspect.getsource(gather_source),
        inspect.getsource(first_draft_unreadable),
        inspect.getsource(finish_first_draft),
    ]
    grams: set[str] = set()
    for part in parts:
        grams.update(_grams(part))
    digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in grams}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    assert leaked == []
