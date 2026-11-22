"""Gathered in-text citations stay when a readable first draft is saved.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. They are not parametrize labels.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from docx import Document
from helpers import open_sequence, picked
from test_student_plain_close import _assert_plain, _close_pack, _final_file
from test_word_references_4a import JONES_LINE, MODULE, QIN_LINE, _plant_stage10_pack

from essay_writer.build_office import stage_launch
from essay_writer.cite_fit import load_record
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import _save_lookup_abstracts, _save_lookup_pdfs
from essay_writer.gates import essay_gates
from essay_writer.late_chain import write_stage10
from essay_writer.paths import module_code, uploads_dir, work_dir
from essay_writer.review import PERSON_BLOCK, essay_review, writer_clears_left
from essay_writer.specialists.writer import UNREADABLE_DRAFT, first_draft_unreadable
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.textutil import citation_tokens, in_text_forms, token_allowed
from essay_writer.word_references import stage10_reference_block
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")
HYPHEN = "\u2010"
NO_CITATIONS = "The opened Word file has no citations. Nothing was recorded."
EMPTY_REFERENCES = (
    "The References section has no entries. Add reference lines before this step can close."
)
QUOTE = "The opened file records a measured change in fishing mortality for this stock."
DRAFT = (
    "Closure advice for North Sea cod was not taken, and the stock stayed outside safe limits "
    "(Froese and Quaas, 2012). Effort limits had cut fishing mortality by the middle of the decade "
    "(Horwood, O'Brien and Darby, 2006). Large trawler effort inside the Plaice Box fell sharply "
    "(Beare and others, 2013). A lower catch can resemble a zero catch over the medium term "
    "(Trijoulet and others, 2021). Herring collapsed and later recovered "
    "(Dickey-Collas and others, 2010). A paper outside the gathered set is not used (Nobody, 1999)."
)
KEPT = (
    "(Froese and Quaas, 2012)",
    "(Horwood, O'Brien and Darby, 2006)",
    "(Beare et al., 2013)",
    "(Trijoulet et al., 2021)",
    f"(Dickey{HYPHEN}Collas and Nash, 2010)",
)


def _proof(name: str, payload: str | bytes) -> None:
    if not ARTIFACTS.is_dir():
        return
    target = ARTIFACTS / name
    if isinstance(payload, bytes):
        target.write_bytes(payload)
        return
    target.write_text(payload, encoding="utf-8")


def _docx_text(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _authors() -> dict[str, tuple[str, str]]:
    return {
        "froese": ("Froese, R. and Quaas, M.", "2012"),
        "horwood": ("Joe Horwood and Ciaran O'Brien and Clive Darby", "2006"),
        "beare": (
            "Douglas Beare and Tobias Mildenberger and Florian Berg and Alex Kokkalis",
            "2013",
        ),
        "trijoulet": (
            "Vanessa Trijoulet and Florian Berg and Alexandros Kokkalis and Tobias Mildenberger",
            "2021",
        ),
        "dickey": (f"Mark Dickey{HYPHEN}Collas and Richard Nash", "2010"),
    }


def _source(seq: str, ident: str, author: str, year: str) -> dict[str, str]:
    module = module_code(seq)
    return {
        "id": ident,
        "author": author,
        "year": year,
        "title": ident,
        "locator": f"uploads/{module}/{ident}.md",
        "quote": QUOTE,
        "origin": "upload",
    }


def _plant(seq: str) -> list[dict[str, str]]:
    rows = [_source(seq, ident, author, year) for ident, (author, year) in _authors().items()]
    state = load_state(seq)
    state["research"] = {"summary": {"sources": rows}, "full": None}
    save_state(seq, state)
    return rows


def _walk(seq: str) -> None:
    for stage in STAGE_ORDER:
        if stage == "5":
            return
        look = f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, (stage, draft)
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, (stage, saved)


def _save_draft() -> tuple[str, str, dict]:
    seq = open_sequence()
    _plant(seq)
    _walk(seq)
    saved = essay_stage(seq, "5", "draft", DRAFT)
    assert saved["ok"] is True, saved
    assert saved["stored"] is True, saved
    look = _note_look(seq, "5") or ""
    assert look.strip()
    return seq, look, saved


def _word_path(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def _pass_writes_word(seq: str) -> dict:
    assert writer_clears_left() == 0
    refused = essay_review(seq, "6", "PASS", "confirm", seat="writer")
    assert refused["ok"] is False, refused
    assert refused["reason"] == PERSON_BLOCK
    assert refused["stored"] is not True
    assert not _word_path(seq).is_file()
    waiting = essay_review(seq, "6", "PASS", "draft")
    assert waiting["ok"] is True, waiting
    assert waiting["stored"] is not True
    assert not _word_path(seq).is_file()
    stored = essay_review(seq, "6", "PASS", "confirm")
    assert stored["stored"] is True, stored
    assert stored["seat"] == "reviewer"
    written = stored.get("first_draft_word")
    assert isinstance(written, dict) and written.get("wrote") is True, stored
    assert _word_path(seq).is_file()
    return stored


def _citation_gate(seq: str, body: str, sources: list[dict[str, str]]) -> dict:
    report = essay_gates(
        seq,
        {"essay_id": seq, "genre": "essay", "conclusion": "open", "sources": sources},
        body=body,
    )
    for item in report["gates"]:
        if item["name"] == "citations":
            return item
    raise AssertionError("citations")


def test_gathered_citations_remain_in_the_stored_draft(workspace):
    """AC-cite-keep-1: Stage 5 keeps gathered in-text citations in the stored draft."""
    seq, look, saved = _save_draft()
    assert "(Froese and Quaas, 2012)" in look
    assert "(Horwood, O'Brien and Darby, 2006)" in look
    assert "closure advice for north sea cod" in look.casefold()
    withheld = set(load_record(seq)["withheld"])
    assert "froese and quaas, 2012" not in withheld
    assert "horwood, o'brien and darby, 2006" not in withheld
    held = {item["token"] for item in saved.get("cite_held") or []}
    assert "froese and quaas, 2012" not in held
    assert "horwood, o'brien and darby, 2006" not in held
    _proof("cite-keep-stored-draft.txt", look + "\n")
    assert workspace is not None


def test_multi_author_and_lists_remain_after_the_save(workspace):
    """AC-cite-keep-2: Multi-author and lists, including and others, remain after the save."""
    froese_forms = in_text_forms("Froese, R. and Quaas, M.", "2012")
    display_forms = in_text_forms("Rainer Froese and Martin Quaas", "2012")
    beare_forms = in_text_forms(
        "Douglas Beare and Tobias Mildenberger and Florian Berg and Alex Kokkalis",
        "2013",
    )
    assert token_allowed("froese and quaas, 2012", froese_forms)
    assert token_allowed("froese and quaas, 2012", display_forms)
    assert token_allowed("beare and others, 2013", beare_forms)
    assert token_allowed("beare et al., 2013", beare_forms)
    assert token_allowed("smith and jones, 2020", {"smith, 2020", "jones, 2020"})
    assert token_allowed("smith and jones, 2020", in_text_forms("Smith, J.", "2020")) is False

    seq, look, _saved = _save_draft()
    for citation in KEPT:
        assert citation in look
    withheld = set(load_record(seq)["withheld"])
    for token in (
        "froese and quaas, 2012",
        "horwood, o'brien and darby, 2006",
        "beare and others, 2013",
        "trijoulet and others, 2021",
        "dickey-collas and others, 2010",
    ):
        assert token not in withheld
    _proof("cite-keep-multi-author-draft.txt", look + "\n")
    assert workspace is not None


def test_reviewer_pass_writes_the_first_draft_word_with_citations(workspace):
    """AC-cite-keep-3: After a reviewer pass, the first-draft Word file still has the citations."""
    seq, look, _saved = _save_draft()
    stored = _pass_writes_word(seq)
    text = _docx_text(_word_path(seq))
    for citation in KEPT:
        assert citation in look
        assert citation in text
    assert "Nobody" not in text
    assert stored.get("next") == "The first-draft Word file is saved from the draft that was reviewed."
    _proof("cite-keep-word-extract.txt", text + "\n")
    _proof("cite-keep-first-draft.docx", _word_path(seq).read_bytes())
    assert workspace is not None


def test_stage9_does_not_refuse_a_file_that_kept_its_citations(workspace):
    """AC-cite-keep-4: Stage 9 review does not refuse a first-draft Word file that kept its citations."""
    seq, _look, _saved = _save_draft()
    _pass_writes_word(seq)
    opened = _docx_text(_word_path(seq))
    assert citation_tokens(opened)
    review = essay_review(seq, "9", "PASS", "draft")
    assert review.get("reason") != NO_CITATIONS
    assert review["ok"] is True, review
    stored = essay_review(seq, "9", "PASS", "confirm")
    assert stored.get("reason") != NO_CITATIONS
    assert stored["ok"] is True, stored
    assert stored["stored"] is True, stored
    payload = (
        f"ok: {review['ok']}\n"
        f"stored_draft: {review.get('stored')}\n"
        f"confirm_ok: {stored['ok']}\n"
        f"confirm_stored: {stored.get('stored')}\n"
        f"reason: {review.get('reason')}\n"
        f"citations: {', '.join(citation_tokens(opened))}\n"
    )
    _proof("cite-keep-review.txt", payload)
    assert workspace is not None


def test_ungathered_hyphen_and_missing_references_still_hold(workspace):
    """AC-cite-keep-5: An ungathered citation is refused, a missing reference line is refused, and a hyphen still matches."""
    seq, look, saved = _save_draft()
    assert "Nobody" not in look
    assert f"(Dickey{HYPHEN}Collas and Nash, 2010)" in look
    assert "(Dickey-Collas and others, 2010)" not in look
    assert HYPHEN in look
    assert HYPHEN in _authors()["dickey"][0]
    held = {item["token"]: item["reason"] for item in saved["cite_held"]}
    assert held["nobody, 1999"] == "claim-fit"
    assert "nobody, 1999" in load_record(seq)["withheld"]
    rows = [
        _source(seq, ident, author, year) for ident, (author, year) in _authors().items()
    ]
    missing = _citation_gate(seq, "A paper outside the gathered set is not used (Nobody, 1999).", rows)
    assert missing["passed"] is False
    assert "nobody, 1999" in missing["reason"]
    kept = _citation_gate(seq, DRAFT.replace(" (Nobody, 1999)", ""), rows)
    assert kept["passed"] is True, kept
    hyphen_name = f"Dickey{HYPHEN}Collas"
    reference = (
        f"{hyphen_name}, M. and Nash, R. (2010) 'Herring recovery', "
        "Fisheries Journal, 1(1), pp. 1-9."
    )
    assert stage10_reference_block(
        [],
        {"references_markdown": reference},
        [{"heading": "Findings", "body": "Herring collapsed and later recovered (Dickey-Collas and others, 2010)."}],
    ) is None
    empty = stage10_reference_block(
        [],
        {},
        [{"heading": "Findings", "body": "Herring collapsed and later recovered (Dickey-Collas and others, 2010)."}],
    )
    assert empty is not None
    assert empty["reason"] == EMPTY_REFERENCES

    diary = open_sequence(MODULE)
    body = "One decision used (Qin, 2021) as evidence for this diary."
    pack = _close_pack(diary, references=QIN_LINE, body=body)
    written = write_stage10(diary)
    assert written["ok"] is True, written
    path = _final_file(diary)
    before = path.read_bytes()
    working = work_dir(diary) / "output" / f"{diary}.docx"
    working_before = working.read_bytes()
    pack["sections"][0]["body"] = "One decision used (Patel, 2014) and the list has no such line."
    pack["references_markdown"] = JONES_LINE
    _plant_stage10_pack(diary, pack)
    refused = write_stage10(diary)
    assert refused["ok"] is False, refused
    assert refused["refused"] == "references-cites"
    assert path.read_bytes() == before
    assert working.read_bytes() == working_before
    assert workspace is not None


def test_an_unreadable_draft_still_does_not_write_a_word_file(workspace):
    """AC-cite-keep-6: An unreadable first draft, including a missing-author sentence, is refused."""
    bare = "Burg (2007) compares climate pressure with a local development scenario."
    assert first_draft_unreadable(bare) is None
    seq = open_sequence()
    _plant(seq)
    _walk(seq)
    held = essay_stage(seq, "5", "draft", bare)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["advanced"] is False
    assert held["reason"] == UNREADABLE_DRAFT
    assert not _word_path(seq).is_file()
    broken = "compares the stock after the author name was removed from this sentence."
    assert first_draft_unreadable(broken) is not None
    again = essay_stage(seq, "5", "draft", broken)
    assert again["ok"] is False, again
    assert again["reason"] == UNREADABLE_DRAFT
    assert not _word_path(seq).is_file()
    assert workspace is not None


def test_student_files_stay_plain_and_lookup_fields_stay(workspace):
    """AC-cite-keep-7: Student-facing Word files stay plain, and official look-up fields stay."""
    seq, _look, _saved = _save_draft()
    stored = _pass_writes_word(seq)
    text = _docx_text(_word_path(seq))
    assert "Critical note" not in text
    assert "Critical note" not in str(stored.get("next") or "")
    _assert_plain(text, str(stored.get("next") or ""), str(stored.get("findings") or ""))
    first = text.splitlines()[0]
    assert first.startswith("Closure advice for North Sea cod")
    assert "(Froese and Quaas, 2012)" in first
    _proof("cite-keep-word-first-line.txt", first + "\n")

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
    abstract_rows = _save_lookup_abstracts(
        seq,
        {
            "openalex": {
                "hits": [
                    {
                        "doi": "10.1000/kept-abs",
                        "authors": ["Grace Hopper"],
                        "year": 2018,
                        "title": "A saved abstract title",
                        "abstract": "The abstract says the corridor is narrow.",
                    }
                ]
            }
        },
        set(),
    )
    abstract = abstract_rows[0]
    assert abstract["author"] == "Grace Hopper"
    assert abstract["year"] == "2018"
    assert abstract["title"] == "A saved abstract title"
    assert abstract["doi"] == "10.1000/kept-abs"
    saved_text = (uploads_dir(seq) / Path(str(abstract["locator"])).name).read_text(encoding="utf-8")
    assert "Grace Hopper" in saved_text
    assert workspace is not None


def test_public_wording_and_shared_rules():
    """AC-cite-keep-8: Public wording. Cursor and Grok Build share the student-facing rules. Build covered."""
    for stage in ("5", "6", "9"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
        assert cursor["settings"] is build["settings"] or (
            cursor["settings"]["model"] == build["settings"]["model"]
            and cursor["settings"]["fast"] is False
            and build["settings"]["fast"] is False
        )
    rules = stage_launch("5")["settings"]["rules"]
    _assert_plain(rules, allow={"p-3", "p-10"})
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_gathered_citations_remain_in_the_stored_draft": "AC-cite-keep-1",
        "test_multi_author_and_lists_remain_after_the_save": "AC-cite-keep-2",
        "test_reviewer_pass_writes_the_first_draft_word_with_citations": "AC-cite-keep-3",
        "test_stage9_does_not_refuse_a_file_that_kept_its_citations": "AC-cite-keep-4",
        "test_ungathered_hyphen_and_missing_references_still_hold": "AC-cite-keep-5",
        "test_an_unreadable_draft_still_does_not_write_a_word_file": "AC-cite-keep-6",
        "test_student_files_stay_plain_and_lookup_fields_stay": "AC-cite-keep-7",
        "test_public_wording_and_shared_rules": "AC-cite-keep-8",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert f'id="{ident}"' not in source
    gate = inspect.getsource(stage_launch)
    assert "Cursor reads that same row" in gate
    version = REPO.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.9.15"' in version
