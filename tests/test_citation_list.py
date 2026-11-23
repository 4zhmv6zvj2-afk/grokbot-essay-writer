"""The citation list written at the end of stage 4b.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. They are not parametrize labels.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from docx import Document
from helpers import open_sequence, picked, write_proof
from test_student_plain_close import _assert_plain, _close_pack, _final_file
from test_word_references_4a import JONES_LINE, MODULE, QIN_LINE, _plant_stage10_pack

from essay_writer import __version__
from essay_writer.build_office import stage_launch
from essay_writer.citation_list import (
    attach_note,
    load_citation_list,
    research_note_for,
    short_in_text,
    student_list_text,
)
from essay_writer.cite_fit import apply_body_cites
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import _open_candidates, _save_lookup_pdfs
from essay_writer.harvard_4a import harvard_4a_line
from essay_writer.late_chain import write_stage10
from essay_writer.paths import module_code, work_dir
from essay_writer.research_packs import ship_4b
from essay_writer.review import PERSON_BLOCK, essay_review, writer_clears_left
from essay_writer.specialists.writer import UNREADABLE_DRAFT, first_draft_unreadable
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.word_references import stage10_reference_block, usable_word_reference_lines
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
HYPHEN = "\u2010"
NOT_WRITTEN = (
    "The citation list has not been written. The first draft waits until that list is saved."
)
NOTE_UNLISTED = (
    "A gathered research note is not on the citation list. "
    "The first draft waits until every note is listed."
)
UNFINISHED = (
    "A gathered research note is not on the citation list. "
    "This step is not finished until every note is listed."
)
EMPTY_REFERENCES = (
    "The References section has no entries. Add reference lines before this step can close."
)
DRAFT = (
    "Closure advice for North Sea cod was not taken, and the stock stayed outside safe limits "
    "(Smith, 2020). Effort limits had cut fishing mortality by the middle of the decade "
    "(Froese and Quaas, 2012). A paper outside the gathered set is not used (Nobody, 1999)."
)


def _docx_text(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _source(
    seq: str,
    ident: str,
    author: str,
    year: str,
    *,
    title: str,
    doi: str = "",
) -> dict[str, str]:
    module = module_code(seq)
    row = {
        "id": ident,
        "author": author,
        "year": year,
        "title": title,
        "locator": f"uploads/{module}/{ident}.md",
        "origin": "upload",
    }
    if doi:
        row["doi"] = doi
    return row


def _plant(seq: str, rows: list[dict[str, str]]) -> None:
    state = load_state(seq)
    state["research"] = {"summary": {"sources": rows}, "full": None}
    save_state(seq, state)


def _walk(seq: str, stop_before: str | None = "5") -> None:
    for stage in STAGE_ORDER:
        if stage == stop_before:
            return
        look = f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, (stage, draft)
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, (stage, saved)


def _ready(seq: str | None = None) -> tuple[str, list[dict[str, str]]]:
    seq = open_sequence() if seq is None else seq
    rows = [
        _source(
            seq, "smith", "Smith, J.", "2020", title="Chokepoints and crude", doi="10.1000/strait"
        ),
        _source(
            seq,
            "froese",
            "Froese, R. and Quaas, M.",
            "2012",
            title="Rebuilding fisheries",
            doi="10.1000/rebuild",
        ),
    ]
    _plant(seq, rows)
    _walk(seq)
    return seq, rows


def _entry(seq: str, ident: str) -> dict:
    found = [item for item in load_citation_list(seq)["entries"] if item.get("source_id") == ident]
    assert len(found) == 1, load_citation_list(seq)
    return found[0]


def _reviews(seq: str) -> Path:
    return work_dir(seq) / "output" / "reviews"


def _word_path(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def test_citation_list_is_written_when_stage_4b_finishes(workspace):
    """AC-cite-lib-1: Stage 4b writes the citation list before the first draft, one entry each."""
    seq, rows = _ready()
    listed = load_citation_list(seq)
    assert listed["written"] is True
    assert (work_dir(seq) / "citation-list.json").is_file()
    identifiers = {item["source_id"] for item in listed["entries"]}
    assert identifiers == {row["id"] for row in rows}
    extract = student_list_text(seq)
    for row in rows:
        assert row["author"] in extract
        assert row["year"] in extract
    write_proof("citation-list-stage-4b.txt", extract + "\n")
    assert workspace is not None


def test_student_research_notes_show_the_same_list(workspace):
    """AC-cite-lib-2: The research notes, the writer, and the reviewer use one list."""
    seq, rows = _ready()
    listed = student_list_text(seq)
    review = next(_reviews(seq).glob("*.docx"))
    text = _docx_text(review)
    assert text.splitlines()[0].startswith("Froese") or text.splitlines()[0].startswith("Smith")
    assert "Citation list" in text
    assert listed in text
    for row in rows:
        assert row["title"] in text
        assert "Research note:" in text
        assert row["id"] in text
    write_proof("citation-list-student-extract.txt", text + "\n")
    assert workspace is not None


def test_first_draft_uses_the_list_citation(workspace):
    """AC-cite-lib-3: The stored first draft and its Word file use the list citation."""
    seq, _rows = _ready()
    saved = essay_stage(seq, "5", "draft", DRAFT)
    assert saved["ok"] is True, saved
    look = _note_look(seq, "5") or ""
    assert "(Smith, 2020)" in look
    assert "(Froese and Quaas, 2012)" in look
    assert "(Nobody, 1999)" not in look
    assert writer_clears_left() == 0
    refused = essay_review(seq, "6", "PASS", "confirm", seat="writer")
    assert refused["ok"] is False
    assert refused["reason"] == PERSON_BLOCK
    waiting = essay_review(seq, "6", "PASS", "draft")
    assert waiting["ok"] is True, waiting
    stored = essay_review(seq, "6", "PASS", "confirm")
    assert stored["stored"] is True, stored
    text = _docx_text(_word_path(seq))
    assert "(Smith, 2020)" in text
    assert "(Froese and Quaas, 2012)" in text
    assert "Nobody" not in text
    write_proof("citation-list-stored-draft.txt", look + "\n")
    write_proof("citation-list-word-extract.txt", text + "\n")
    assert workspace is not None


def test_later_reference_lines_come_from_the_list(workspace, monkeypatch):
    """AC-cite-lib-4: Later reference lines are the lines stored on the list."""
    seq, rows = _ready()
    smith = _entry(seq, "smith")
    stored_line = smith["reference"]
    assert stored_line == harvard_4a_line(rows[0])

    def _rebuilt(_source: dict) -> str:
        raise AssertionError("reference line rebuilt")

    monkeypatch.setattr("essay_writer.harvard_4a.harvard_4a_line", _rebuilt)
    pack = {
        "essay_id": seq,
        "sections": [
            {"heading": "Findings", "body": "The stock stayed outside safe limits (Smith, 2020)."}
        ],
    }
    lines = usable_word_reference_lines([rows[0]], pack, seq)
    assert lines == [stored_line]
    assert workspace is not None


def test_a_new_source_is_listed_before_it_can_be_cited(workspace):
    """AC-cite-lib-5: A source added mid-run is listed before a draft can cite it."""
    seq, rows = _ready()
    added = (
        "A later paper records the same corridor limit (Jones, 2021). "
        "The stock stayed outside safe limits after that reading."
    )
    early = apply_body_cites(seq, "5", added)
    assert "(Jones, 2021)" not in early["text"]
    fresh = _source(
        seq,
        "jones",
        "Jones, A.",
        "2021",
        title="A second corridor paper",
        doi="10.1000/second",
    )
    note = "The second paper records the corridor limit in plain sentences.\n"
    delivered = ship_4b(seq, [*rows, fresh], {"jones": note})
    assert delivered["student_note"]
    assert "already" in delivered["student_note"].casefold()
    jones = _entry(seq, "jones")
    assert jones["usable"] is True
    assert jones["in_text"] == "(Jones, 2021)"
    saved = essay_stage(seq, "5", "draft", added)
    assert saved["ok"] is True, saved
    look = _note_look(seq, "5") or ""
    assert "(Jones, 2021)" in look
    assert workspace is not None


def test_first_write_waits_for_the_list_and_does_not_invent(workspace):
    """AC-cite-lib-6: No list means no first draft, and an empty list invents nothing."""
    seq, _rows = _ready()
    (work_dir(seq) / "citation-list.json").unlink()
    held = essay_stage(seq, "5", "draft", DRAFT)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["reason"] == NOT_WRITTEN
    assert (_note_look(seq, "5") or "") == ""

    state = load_state(seq)
    state["research"] = {"summary": {"sources": []}, "full": None}
    save_state(seq, state)
    delivered = ship_4b(seq, [], None)
    listed = load_citation_list(seq)
    assert listed["written"] is True
    assert listed["entries"] == []
    assert listed["gap"] == "No gathered source was saved."
    assert "No gathered source was saved." in delivered["student_note"]
    cleaned = apply_body_cites(
        seq,
        "5",
        "The stock stayed outside safe limits (Nobody, 1999).",
    )
    assert "(Nobody, 1999)" not in cleaned["text"]
    assert "Nobody" not in cleaned["text"]
    write_proof("citation-list-empty-gap.txt", student_list_text(seq) + "\n")
    assert workspace is not None


def test_lookup_fields_hyphen_and_existing_refusals_stay(workspace):
    """AC-cite-lib-7: Look-up fields stay, a hyphen still matches, and the old refusals stay."""
    seq = open_sequence()
    hyphen_author = f"Dickey{HYPHEN}Collas, M."
    rows = [
        _source(
            seq, "smith", "Smith, J.", "2020", title="Chokepoints and crude", doi="10.1000/strait"
        ),
        _source(
            seq, "dickey", hyphen_author, "2010", title="Herring recovery", doi="10.1000/herring"
        ),
    ]
    _plant(seq, rows)
    _walk(seq)
    bare = "Burg (2007) compares climate pressure with a local development scenario."
    assert first_draft_unreadable(bare) is None
    held = essay_stage(seq, "5", "draft", bare)
    assert held["reason"] == UNREADABLE_DRAFT
    assert held["stored"] is False
    broken = "compares the stock after the author name was removed from this sentence."
    assert first_draft_unreadable(broken) is not None
    again = essay_stage(seq, "5", "draft", broken)
    assert again["reason"] == UNREADABLE_DRAFT
    assert not _word_path(seq).is_file()
    assert writer_clears_left() == 0
    refused = essay_review(seq, "6", "PASS", "confirm", seat="writer")
    assert refused["reason"] == PERSON_BLOCK
    assert not _word_path(seq).is_file()
    dickey = _entry(seq, "dickey")
    assert dickey["author"] == hyphen_author
    assert HYPHEN in dickey["author"]
    assert dickey["year"] == "2010"
    assert dickey["title"] == "Herring recovery"
    assert dickey["doi"] == "10.1000/herring"
    body = (
        "Herring collapsed and later recovered (Dickey-Collas, 2010). "
        "The stock stayed outside safe limits (Smith, 2020)."
    )
    saved = essay_stage(seq, "5", "draft", body)
    assert saved["ok"] is True, saved
    look = _note_look(seq, "5") or ""
    assert "(Dickey-Collas, 2010)" in look
    assert HYPHEN not in look

    pdf_rows = _save_lookup_pdfs(
        {
            "openalex": {
                "hits": [
                    {
                        "doi": "10.1000/kept-pdf",
                        "authors": ["Ada Lovelace"],
                        "year": "2019",
                        "title": "Corridor capacity under a named constraint",
                    }
                ]
            }
        },
        [{"path": "uploads/MOD1004AA/kept.pdf", "doi": "10.1000/kept-pdf"}],
    )
    kept = pdf_rows[0]
    assert kept["author"] == "Ada Lovelace"
    assert kept["year"] == "2019"
    assert kept["title"] == "Corridor capacity under a named constraint"
    assert kept["doi"] == "10.1000/kept-pdf"
    assert kept["field_sources"]["author"] == "lookup"
    listed = ship_4b(
        seq,
        [
            *rows,
            {
                "id": "lovelace",
                "author": kept["author"],
                "year": kept["year"],
                "title": kept["title"],
                "doi": kept["doi"],
            },
        ],
        None,
    )
    lovelace = _entry(seq, "lovelace")
    assert lovelace["author"] == "Ada Lovelace"
    assert lovelace["year"] == "2019"
    assert lovelace["title"] == "Corridor capacity under a named constraint"
    assert lovelace["doi"] == "10.1000/kept-pdf"
    assert listed["stage"] == "4b"

    reference = (
        f"Dickey{HYPHEN}Collas, M. (2010) 'Herring recovery', Fisheries Journal, 1(1), pp. 1-9."
    )
    assert (
        stage10_reference_block(
            [],
            {"references_markdown": reference},
            [
                {
                    "heading": "Findings",
                    "body": "Herring collapsed and later recovered (Dickey-Collas, 2010).",
                }
            ],
        )
        is None
    )
    empty = stage10_reference_block(
        [],
        {},
        [
            {
                "heading": "Findings",
                "body": "Herring collapsed and later recovered (Dickey-Collas, 2010).",
            }
        ],
    )
    assert empty is not None
    assert empty["reason"] == EMPTY_REFERENCES

    diary = open_sequence(MODULE)
    pack = _close_pack(
        diary, references=QIN_LINE, body="One decision used (Qin, 2021) as evidence for this diary."
    )
    written = write_stage10(diary)
    assert written["ok"] is True, written
    path = _final_file(diary)
    before = path.read_bytes()
    working = work_dir(diary) / "output" / f"{diary}.docx"
    working_before = working.read_bytes()
    pack["sections"][0]["body"] = "One decision used (Patel, 2014) and the list has no such line."
    pack["references_markdown"] = JONES_LINE
    _plant_stage10_pack(diary, pack)
    refused_final = write_stage10(diary)
    assert refused_final["ok"] is False, refused_final
    assert refused_final["refused"] == "references-cites"
    assert path.read_bytes() == before
    assert working.read_bytes() == working_before
    assert workspace is not None


def test_a_kept_pdf_without_a_doi_keeps_the_lookup_fields():
    """A kept PDF matches its hit by URL, locator, or title with author. A bare title does not."""
    card = {
        "openalex": {
            "hits": [
                {
                    "authors": ["Ada Lovelace"],
                    "year": "2019",
                    "title": "Harbour capacity without a DOI",
                    "pdf_url": "https://oa.example/harbour.pdf",
                },
                {
                    "authors": ["Grace Hopper"],
                    "year": "2018",
                    "title": "Harbour capacity without a DOI",
                    "doi": "10.1000/hopper",
                    "pdf_url": "https://oa.example/hopper.pdf",
                },
            ]
        },
        "consensus": {"hits": []},
        "unpaywall": [],
    }
    opened = _open_candidates(card)
    by_url = {item["url"]: item for item in opened}
    assert "doi" not in by_url["https://oa.example/harbour.pdf"]
    assert by_url["https://oa.example/harbour.pdf"]["title"] == "Harbour capacity without a DOI"
    assert by_url["https://oa.example/hopper.pdf"]["doi"] == "10.1000/hopper"
    rows = _save_lookup_pdfs(
        card,
        [
            {
                "path": "uploads/MOD1004AA/harbour.pdf",
                "url": "https://oa.example/harbour.pdf",
            },
            {
                "path": "uploads/MOD1004AA/hopper.pdf",
                "url": "https://oa.example/hopper.pdf",
            },
            {
                "path": "uploads/MOD1004AA/title-only.pdf",
                "title": "Harbour capacity without a DOI",
            },
            {
                "path": "uploads/MOD1004AA/named.pdf",
                "title": "Harbour capacity without a DOI",
                "author": "Ada Lovelace",
            },
        ],
    )
    by_path = {row["locator"]: row for row in rows}
    harbour = by_path["uploads/MOD1004AA/harbour.pdf"]
    assert harbour["author"] == "Ada Lovelace"
    assert harbour["year"] == "2019"
    assert harbour["title"] == "Harbour capacity without a DOI"
    assert "doi" not in harbour
    assert harbour["field_sources"] == {
        "author": "lookup",
        "year": "lookup",
        "title": "lookup",
    }
    hopper = by_path["uploads/MOD1004AA/hopper.pdf"]
    assert hopper["author"] == "Grace Hopper"
    assert hopper["doi"] == "10.1000/hopper"
    assert "uploads/MOD1004AA/title-only.pdf" not in by_path
    named = by_path["uploads/MOD1004AA/named.pdf"]
    assert named["author"] == "Ada Lovelace"
    assert named["year"] == "2019"
    assert "doi" not in named


def test_public_wording_and_shared_rules():
    """AC-cite-lib-8: Public wording. Cursor and Grok Build share the student-facing rules."""
    for stage in ("4b", "5", "6", "9"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
    rules = stage_launch("4b")["settings"]["rules"]
    _assert_plain(rules, stage_launch("5")["settings"]["rules"], allow={"p-3", "p-10"})
    assert "citation list" in rules.casefold()
    assert "(Smith, 2020)" in rules
    draft_rules = stage_launch("5")["settings"]["rules"]
    assert "citation list" in draft_rules.casefold()
    assert "do not write a different citation" in draft_rules.casefold()
    gate = inspect.getsource(stage_launch)
    assert "Cursor reads that same row" in gate
    version = REPO.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in version
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_citation_list_is_written_when_stage_4b_finishes": "AC-cite-lib-1",
        "test_student_research_notes_show_the_same_list": "AC-cite-lib-2",
        "test_first_draft_uses_the_list_citation": "AC-cite-lib-3",
        "test_later_reference_lines_come_from_the_list": "AC-cite-lib-4",
        "test_a_new_source_is_listed_before_it_can_be_cited": "AC-cite-lib-5",
        "test_first_write_waits_for_the_list_and_does_not_invent": "AC-cite-lib-6",
        "test_lookup_fields_hyphen_and_existing_refusals_stay": "AC-cite-lib-7",
        "test_public_wording_and_shared_rules": "AC-cite-lib-8",
        "test_a_missing_research_note_stays_visible": "AC-cite-lib-9",
        "test_a_note_without_an_entry_blocks_the_draft": "AC-cite-lib-10",
        "test_a_disagreement_is_named_and_not_silently_resolved": "AC-cite-lib-11",
        "test_a_source_already_listed_is_reused": "AC-cite-lib-12",
        "test_each_entry_stores_the_short_form_and_the_full_line": "AC-cite-lib-13",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert f'id="{ident}"' not in source


def test_a_missing_research_note_stays_visible(workspace):
    """AC-cite-lib-9: A lost research note stays visible, and nothing invents a replacement."""
    seq, rows = _ready()
    smith = _entry(seq, "smith")
    path = Path(smith["note"])
    if not path.is_absolute():
        from essay_writer.paths import workspace_root

        path = workspace_root() / smith["note"]
    original = path.read_text(encoding="utf-8")
    path.unlink()
    shown = _entry(seq, "smith")
    assert shown["source_id"] == "smith"
    assert shown["usable"] is False
    assert "missing" in shown["gap"].casefold()
    assert shown["author"] == rows[0]["author"]
    assert shown["year"] == rows[0]["year"]
    for seat in ("writer", "reviewer"):
        read = research_note_for(seq, "smith", seat=seat)
        assert read["invented"] is False
        assert read["text"] == ""
        assert "missing" in read["gap"].casefold()
    again = ship_4b(seq, rows, None)
    assert path.is_file() is False
    assert all("smith" not in str(item.get("markdown_path")) for item in again["reviews"])
    attached = attach_note(seq, "smith", original)
    assert attached["wrote"] is True
    assert attached["invented"] is False
    restored = _entry(seq, "smith")
    assert restored["usable"] is True
    assert restored["author"] == rows[0]["author"]
    assert restored["year"] == rows[0]["year"]
    assert restored["in_text"] == smith["in_text"]
    assert restored["reference"] == smith["reference"]
    assert path.read_text(encoding="utf-8") == original
    names = [item.name for item in _reviews(seq).glob("*.md")]
    assert names.count(path.name) == 1
    assert workspace is not None


def test_a_note_without_an_entry_blocks_the_draft(workspace):
    """AC-cite-lib-10: A research note that is not on the list blocks stage 4b and the first draft."""
    seq = open_sequence()
    row = _source(
        seq, "smith", "Smith, J.", "2020", title="Chokepoints and crude", doi="10.1000/strait"
    )
    _plant(seq, [row])
    _walk(seq, stop_before="4b")
    folder = _reviews(seq)
    folder.mkdir(parents=True, exist_ok=True)
    extra = folder / "extra-note.md"
    extra.write_text("A gathered note that has not been listed.\n", encoding="utf-8")
    look = "Saved from the brief. This sentence belongs to stage 4b."
    draft = essay_stage(seq, "4b", "draft", look)
    assert draft["ok"] is True, draft
    refused = essay_stage(seq, "4b", "confirm", look, **picked(draft))
    assert refused["stored"] is not True
    assert refused["reason"] == UNFINISHED
    extra.unlink()
    draft = essay_stage(seq, "4b", "draft", look)
    saved = essay_stage(seq, "4b", "confirm", look, **picked(draft))
    assert saved["stored"] is True, saved
    later = _reviews(seq) / "later-note.md"
    later.write_text("A note added after the list was written.\n", encoding="utf-8")
    blocked = essay_stage(seq, "5", "draft", DRAFT)
    assert blocked["ok"] is False, blocked
    assert blocked["reason"] == NOTE_UNLISTED
    fresh = _source(
        seq, "later-note", "Jones, A.", "2021", title="Added after the list", doi="10.1000/later"
    )
    ship_4b(seq, [row, fresh], None)
    assert later.is_file()
    assert _entry(seq, "later-note")["usable"] is True
    kept = (
        "The stock stayed outside safe limits (Smith, 2020). "
        "A later paper records the same corridor limit (Jones, 2021)."
    )
    stored = essay_stage(seq, "5", "draft", kept)
    assert stored["ok"] is True, stored
    assert "(Jones, 2021)" in (_note_look(seq, "5") or "")
    assert workspace is not None


def test_a_disagreement_is_named_and_not_silently_resolved(workspace):
    """AC-cite-lib-11: A stored-detail conflict is named, and neither record is rewritten."""
    seq, rows = _ready()
    smith = _entry(seq, "smith")
    from essay_writer.paths import workspace_root

    path = workspace_root() / smith["note"]
    record_path = path.with_name(f"{path.stem}.record.json")
    original = path.read_text(encoding="utf-8")
    stored = record_path.read_text(encoding="utf-8")
    path.write_text(original.replace("(2020)", "(1999)", 1), encoding="utf-8")
    headed = _entry(seq, "smith")
    assert headed["usable"] is True
    assert headed["conflict"] == ""
    assert headed["year"] == "2020"
    held_heading = apply_body_cites(seq, "5", DRAFT)
    assert "(Smith, 2020)" in held_heading["text"]
    record_path.write_text(stored.replace('"year": "2020"', '"year": "1999"', 1), encoding="utf-8")
    conflicted = _entry(seq, "smith")
    assert conflicted["usable"] is False
    assert "stored details" in conflicted["conflict"].casefold()
    assert "do not agree" in conflicted["conflict"].casefold()
    assert conflicted["author"] == rows[0]["author"]
    assert conflicted["year"] == "2020"
    assert conflicted["title"] == rows[0]["title"]
    assert conflicted["doi"] == rows[0]["doi"]
    assert conflicted["in_text"] == smith["in_text"]
    assert conflicted["reference"] == smith["reference"]
    assert path.read_text(encoding="utf-8") == original.replace("(2020)", "(1999)", 1)
    assert '"year": "1999"' in record_path.read_text(encoding="utf-8")
    state = load_state(seq)
    sources = state["research"]["summary"]["sources"]
    assert sources[0]["year"] == "2020"
    held = apply_body_cites(seq, "5", DRAFT)
    assert "(Smith, 2020)" not in held["text"]
    assert "(Froese and Quaas, 2012)" in held["text"]
    record_path.write_text(stored, encoding="utf-8")
    restored = _entry(seq, "smith")
    assert restored["usable"] is True
    assert restored["conflict"] == ""
    assert restored["year"] == "2020"
    assert restored["author"] == rows[0]["author"]
    saved = essay_stage(seq, "5", "draft", DRAFT)
    assert saved["ok"] is True, saved
    assert "(Smith, 2020)" in (_note_look(seq, "5") or "")
    assert workspace is not None


def test_a_source_already_listed_is_reused(workspace):
    """AC-cite-lib-12: A source already on the list keeps its entry and its note."""
    seq, rows = _ready()
    smith = _entry(seq, "smith")
    from essay_writer.paths import workspace_root

    note = workspace_root() / smith["note"]
    before = note.read_bytes()
    notes_before = sorted(path.name for path in _reviews(seq).glob("*.md"))
    copy = dict(rows[0])
    copy["id"] = "smith-copy"
    fresh = _source(
        seq, "jones", "Jones, A.", "2021", title="A second corridor paper", doi="10.1000/second"
    )
    early = apply_body_cites(
        seq,
        "5",
        "A later paper records the same corridor limit (Jones, 2021). The stock stayed outside safe limits.",
    )
    assert "(Jones, 2021)" not in early["text"]
    delivered = ship_4b(
        seq, [copy, fresh], {"jones": "The second paper is a new gathered source.\n"}
    )
    assert "already" in delivered["student_note"].casefold()
    assert "(Smith, 2020)" in delivered["student_note"]
    assert note.read_bytes() == before
    notes_after = sorted(path.name for path in _reviews(seq).glob("*.md"))
    assert notes_before.count(note.name) == 1
    assert notes_after.count(note.name) == 1
    identifiers = [item["source_id"] for item in load_citation_list(seq)["entries"]]
    assert identifiers.count("smith") == 1
    assert "smith-copy" not in identifiers
    assert "jones" in identifiers
    saved = essay_stage(
        seq,
        "5",
        "draft",
        "The stock stayed outside safe limits (Smith, 2020). A later paper records the same corridor limit (Jones, 2021).",
    )
    assert saved["ok"] is True, saved
    look = _note_look(seq, "5") or ""
    assert "(Jones, 2021)" in look
    assert "(Smith, 2020)" in look
    assert workspace is not None


def test_each_entry_stores_the_short_form_and_the_full_line(workspace, monkeypatch):
    """AC-cite-lib-13: Each entry stores the short citation and the full Harvard line."""
    seq, rows = _ready()
    smith = _entry(seq, "smith")
    froese = _entry(seq, "froese")
    assert smith["in_text"] == "(Smith, 2020)"
    assert smith["in_text"] == short_in_text("Smith, J.", "2020")
    assert smith["reference"] == harvard_4a_line(rows[0])
    assert froese["in_text"] == "(Froese and Quaas, 2012)"
    assert froese["reference"] == harvard_4a_line(rows[1])
    assert smith["author"] == "Smith, J."
    assert smith["year"] == "2020"
    assert smith["title"] == "Chokepoints and crude"
    assert smith["doi"] == "10.1000/strait"
    extract = student_list_text(seq)
    assert "(Smith, 2020)" in extract
    assert smith["reference"] in extract
    assert "(Froese and Quaas, 2012)" in extract
    assert froese["reference"] in extract
    write_proof("citation-list-forms.txt", extract + "\n")
    saved = essay_stage(seq, "5", "draft", DRAFT)
    assert saved["ok"] is True, saved
    assert "(Smith, 2020)" in (_note_look(seq, "5") or "")
    assert "(Froese and Quaas, 2012)" in (_note_look(seq, "5") or "")

    def _rebuilt(_source: dict) -> str:
        return "A different reference line."

    monkeypatch.setattr("essay_writer.citation_list.full_reference", _rebuilt)
    monkeypatch.setattr("essay_writer.harvard_4a.harvard_4a_line", _rebuilt)
    lines = usable_word_reference_lines(
        rows,
        {"essay_id": seq, "sections": [{"heading": "Findings", "body": DRAFT}]},
        seq,
    )
    assert smith["reference"] in lines
    assert froese["reference"] in lines
    assert "A different reference line." not in lines
    assert _entry(seq, "smith")["in_text"] == "(Smith, 2020)"
    assert _entry(seq, "smith")["reference"] == smith["reference"]
    assert workspace is not None
