"""Stage 10 writes the final Word file once a fair review can pass.

Harvard reference titles stay italic in the stored list and in the Word
file: a long author list, a review-style title, and a management-plan title.
A first refusal does not end the job. The writer amends and asks again.
The last step stays closed while that review is still open.

The acceptance ids for this file live in the docstrings below. Each id is
seated once, on the test that proves it.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from helpers import open_sequence, picked
from test_stage10_close_and_findings import _leaked
from test_word_references_4a import NUMBER, _park_stage10

from essay_writer import __version__
from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import opened_word_gate as build_opened_word_gate
from essay_writer.build_office import stage_launch
from essay_writer.citation_list import (
    list_written,
    load_citation_list,
    match_token,
    reference_entries_for_token,
    short_in_text,
)
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.cursor_office import opened_word_gate as cursor_opened_word_gate
from essay_writer.download_shortlist import PLAN_STEP, QUESTION_STEP, choose_downloads, missing_step
from essay_writer.essay_cites import cited_source_ids, essay_cite_bounds, work_is_relevant
from essay_writer.harvard_ref_check import compliance_misses
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.research_packs import ship_4b
from essay_writer.review import essay_review
from essay_writer.source_floor import rate_for_words
from essay_writer.specialists.eqr import REVIEW_PROMPT
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state
from essay_writer.student_voice import student_surface_hits
from essay_writer.textutil import count_words
from essay_writer.word_references import reference_runs_for_stored, styled_reference_runs

ARTIFACTS = Path("/opt/cursor/artifacts")
MODULE = "ENVS5003HK"
QUESTION = "How does a fishery closure let a herring stock recover?"
PLAN = "The plan follows a fishery closure that lets a herring stock recover."
BRIEF = f"Genre: report\nQuestion: {QUESTION}\n"
BRIEF_2000 = f"Genre: report\nQuestion: {QUESTION}\nWord count: 2000 words\n"
NOTE = "The opened file states the limit, and the year is the one stored on the list."
LONG_AUTHORS = (
    "Dickey-Collas, M., Nash, R.D.M., Brunel, T., van Damme, C.J.G., Marshall, C.T., "
    "Payne, M.R., Corten, A., Geffen, A.J., Peck, M.A., Hatfield, E.M.C., Hintzen, N.T., "
    "Enberg, K., Kell, L.T., Simmonds, E.J., Berg, C.W., Ulrich, C., "
    "Moller, H., Nielsen, J.R., and Sparholt, H."
)
JOURNAL_TITLE = "Lessons learned from stock collapse and recovery of North Sea herring: a review"
REVIEW_TITLE = "Fishery closure and herring stock recover. A review"
PLAN_TITLE = (
    "Council Regulation (EC) No 1098/2007 of 18 September 2007 establishing a "
    "multiannual plan for the cod stocks in the Baltic Sea and the fisheries "
    "exploiting those stocks, amending Regulation (EEC) No 2847/93 and repealing "
    "Regulation (EC) No 779/97"
)
LOOK = f"This report answers the assignment. {QUESTION}"
TOP_TABLE = """
| Criterion | 40-59 | 60-69 | 70-100 |
| --- | --- | --- | --- |
| Argument | lists nearby topics | states a claim | sustains an original thesis |
| Use of evidence | names some sources | uses several sources | specific gathered sources |
| Critical thinking | describes the events | explains the causes | judges the alternatives |
| Format | loose layout | tidy layout | exact margins |
| Citations | missing harvard | some harvard | exact citation lines |
"""
COPIED = "The opened file states the limit for this herring closure."


def _proof(name: str, payload: str | bytes) -> None:
    if not ARTIFACTS.is_dir():
        return
    target = ARTIFACTS / name
    if isinstance(payload, bytes):
        target.write_bytes(payload)
        return
    target.write_text(payload, encoding="utf-8")


def _brief(text: str = BRIEF) -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _plan(seq: str) -> None:
    path = _note_path(seq, "3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_tracking("3", status="final", look=PLAN, essay_id=seq), encoding="utf-8")


def _journal() -> dict[str, str]:
    return {
        "id": "herring-review-2010",
        "author": LONG_AUTHORS,
        "year": "2010",
        "title": JOURNAL_TITLE,
        "container": "ICES Journal of Marine Science",
        "volume": "67",
        "issue": "9",
        "pages": "1875-1886",
        "doi": "10.1093/icesjms/fsq033",
    }


def _review_source() -> dict[str, str]:
    return {
        "id": "herring-review-title",
        "author": "Ada North",
        "year": "2011",
        "title": REVIEW_TITLE,
        "doi": "10.1000/herring-review-title",
    }


def _plan_source() -> dict[str, str]:
    return {
        "id": "baltic-cod-plan-2009",
        "author": "European Council",
        "year": "2009",
        "title": PLAN_TITLE,
        "place": "Brussels",
        "publisher": "European Council",
        "doi": "10.1000/baltic-cod-plan-2009",
    }


def _filler(index: int) -> dict[str, str]:
    ident = f"herring-note-{index:02d}"
    return {
        "id": ident,
        "author": f"Family{index}, A.",
        "year": str(2000 + index),
        "title": f"Fishery closure and herring stock recover note {index}",
        "doi": f"10.1000/{ident}",
    }


def _specials() -> list[dict[str, str]]:
    return [_journal(), _review_source(), _plan_source()]


def _ship(seq: str, rows: list[dict[str, str]]) -> None:
    delivered = ship_4b(seq, rows, {row["id"]: NOTE for row in rows})
    assert delivered.get("blocked") is not True, delivered
    assert list_written(seq) is True


def _stored_lines(seq: str) -> list[str]:
    lines = []
    for entry in load_citation_list(seq)["entries"]:
        line = str(entry.get("reference") or "").strip()
        if line:
            lines.append(line)
    return lines


def _cite_sentence(rows: list[dict[str, str]]) -> str:
    parts = []
    for row in rows:
        cite = short_in_text(row["author"], row["year"])
        parts.append(f"The opened file states the limit {cite}.")
    return " ".join(parts)


def _essay(rows: list[dict[str, str]], *, words: int | None = None) -> str:
    opening = f"This report answers the assignment. {QUESTION} Fairness here is a judgement about evidence."
    body = opening + " " + _cite_sentence(rows)
    if words is None:
        return body
    sentence = "A fishery closure can let a herring stock recover when the evidence is specific and the cost is named."
    while count_words(body, exclude_citations=False) < words:
        body = f"{body} {sentence}"
    return body


def _plant(seq: str, body: str, rows: list[dict[str, str]]) -> None:
    remember_registration(seq, NUMBER)
    _park_stage10(seq)
    state = load_state(seq)
    state["saved_pack"] = {
        "essay_id": seq,
        "title": seq,
        "referencing": "harvard",
        "assessment": seq,
        "conclusion": "noted",
        "sources": rows,
        "references_markdown": "\n".join(_stored_lines(seq)),
        "sections": [{"heading": "Fishery closure", "body": body}],
    }
    from essay_writer.state import save_state

    save_state(seq, state)


def _arm(seq: str) -> None:
    pointer = load_pointer(seq)
    pointer["chain_armed"] = True
    path = work_dir(seq) / "tracking" / "stage.json"
    path.write_text(__import__("json").dumps(pointer, indent=2) + "\n", encoding="utf-8")


def _italic_of(runs: list[tuple[str, bool]]) -> str:
    return "".join(text for text, italic in runs if italic)


def _write_word(
    path: Path,
    body: str,
    lines: list[str],
    sources: list[dict[str, str]],
    *,
    italic: bool,
    title: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.core_properties.title = title
    document.core_properties.author = ""
    paragraph = document.add_paragraph(body)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    document.add_paragraph("References")
    for line in lines:
        written = document.add_paragraph()
        runs = styled_reference_runs(line, sources) if italic else [(line, False)]
        for text, flag in runs:
            run = written.add_run(text)
            run.italic = flag
    document.save(str(path))


def _sequence_docx(seq: str) -> Path:
    return work_dir(seq) / "output" / f"{seq}.docx"


def _final_file(seq: str) -> Path:
    found = sorted((work_dir(seq) / "output").rglob("*-final.docx"))
    assert len(found) == 1, [str(path) for path in found]
    return found[0]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _period_after_year(line: str, year: str) -> str:
    return line.replace(f"({year})", f"({year}).", 1)


def _open(text: str = BRIEF) -> str:
    _brief(text)
    return open_sequence(MODULE)


def _ready(seq: str, rows: list[dict[str, str]], *, words: int | None = None) -> str:
    _ship(seq, rows)
    _plan(seq)
    body = _essay(rows, words=words)
    _plant(seq, body, rows)
    return body


def _review(seq: str, verdict: str = "PASS") -> dict:
    draft = essay_review(seq, "9", verdict, "draft", constitution=LOOK)
    if draft.get("ok") is not True:
        return draft
    stored = essay_review(seq, "9", verdict, "confirm", constitution=LOOK)
    return stored


def _stage10(seq: str) -> dict:
    draft = essay_stage(seq, "10", "draft", LOOK)
    assert draft.get("ok") is True, draft
    return essay_stage(seq, "10", "confirm", LOOK, **picked(draft))


def test_review_titles_stay_italic_for_a_long_list_a_review_and_a_plan(workspace):
    """AC-close-1: Harvard reference titles are italic in the stored citation list and in the Word reference lines, including a long author list, a review-style title, and a management-plan title. A fair Harvard check can pass. A roman title is still refused."""
    seq = _open()
    rows = _specials()
    _ship(seq, rows)
    listed = load_citation_list(seq)["entries"]
    by_id = {str(entry.get("source_id")): entry for entry in listed}
    journal = by_id["herring-review-2010"]
    review = by_id["herring-review-title"]
    plan = by_id["baltic-cod-plan-2009"]
    assert journal.get("container") == "ICES Journal of Marine Science"
    assert len(LONG_AUTHORS) > 270
    journal_runs = reference_runs_for_stored(journal)
    review_runs = reference_runs_for_stored(review)
    plan_runs = reference_runs_for_stored(plan)
    assert "ICES Journal of Marine Science" in _italic_of(journal_runs)
    assert JOURNAL_TITLE.casefold() not in _italic_of(journal_runs).casefold()
    assert REVIEW_TITLE.casefold() in _italic_of(review_runs).casefold()
    assert PLAN_TITLE.casefold() in _italic_of(plan_runs).casefold()
    altered = [
        _period_after_year(str(journal["reference"]), "2010"),
        _period_after_year(str(review["reference"]), "2011"),
        _period_after_year(str(plan["reference"]), "2009"),
    ]
    path = work_dir(seq) / "output" / "italic-lines.docx"
    _write_word(path, _essay(rows), altered, rows, italic=True, title=seq)
    misses = compliance_misses(path, rows)
    assert misses == [], misses
    roman = work_dir(seq) / "output" / "roman-lines.docx"
    _write_word(roman, _essay(rows), altered, rows, italic=False, title=seq)
    codes = {item["code"] for item in compliance_misses(roman, rows)}
    assert "title-italic" in codes
    assert "journal-italic" in codes
    checker = inspect.getsource(compliance_misses)
    assert "title-italic" in inspect.getsource(
        __import__("essay_writer.harvard_ref_check", fromlist=["_source_misses"])._source_misses
    )
    assert "if not container" in inspect.getsource(
        __import__("essay_writer.harvard_ref_check", fromlist=["_source_misses"])._source_misses
    )
    extract = []
    for label, runs in (
        ("journal", journal_runs),
        ("review", review_runs),
        ("plan", plan_runs),
    ):
        extract.append(f"{label}: {_italic_of(runs)}")
    _proof("italic-line-extract.txt", "\n".join(extract) + "\n")
    _proof("italic-lines.docx", path.read_bytes())
    assert checker
    assert workspace is not None


def test_a_fair_review_then_writes_the_final_word_file(workspace, monkeypatch, tmp_path):
    """AC-close-2: After a fair independent review pass, Stage 10 writes a new final Word file whose name is not the first-draft name. The review is not left open only because a title was never marked italic."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = _open()
    rows = _specials()
    body = _ready(seq, rows)
    lines = [
        _period_after_year(line, year)
        for line, year in zip(_stored_lines(seq), ("2010", "2011", "2009"), strict=True)
    ]
    draft = _sequence_docx(seq)
    _write_word(draft, body, lines, rows, italic=True, title=seq)
    _arm(seq)
    before = _sha(draft)
    first_draft = draft.read_bytes()
    blocked = _stage10(seq)
    assert blocked.get("ok") is False, blocked
    assert blocked.get("refused") == "eqr"
    assert "still open" in str(blocked.get("reason") or "").casefold()
    assert _sha(draft) == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    passed = _review(seq)
    assert passed.get("stored") is True, passed
    closed = _stage10(seq)
    assert closed.get("ok") is True, closed
    final = _final_file(seq)
    assert final.name != draft.name
    assert final.name.endswith("-final.docx")
    assert "10" in (load_pointer(seq).get("saved") or [])
    _proof("fair-review-final.docx", final.read_bytes())
    _proof("fair-review-first-draft.docx", first_draft)
    assert workspace is not None


def test_an_off_list_cite_still_refuses_and_keeps_the_first_draft(workspace):
    """AC-close-3: An off-list cite such as (Nobody, 1999), and a genuinely missing reference line, are still refused. A failed last step is not stored, writes no final Word file, and does not overwrite a good first-draft Word file."""
    seq = _open()
    rows = [_plan_source()]
    body = _ready(seq, rows)
    body = f"{body} An unlisted paper is not added (Nobody, 1999)."
    _plant(seq, body, rows)
    draft = _sequence_docx(seq)
    _write_word(draft, body, _stored_lines(seq), rows, italic=True, title=seq)
    before = _sha(draft)
    refused = write_stage10(seq)
    assert refused.get("ok") is False, refused
    assert refused.get("refused") == "references-cites"
    assert "nobody, 1999" in str(refused.get("reason") or "").casefold()
    assert _sha(draft) == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    assert "10" not in (load_pointer(seq).get("saved") or [])

    other = _open()
    remember_registration(other, NUMBER)
    _park_stage10(other)
    lone = "North, A. (2011) Fishery closure and herring stock recover. A review."
    state = load_state(other)
    state["saved_pack"] = {
        "essay_id": other,
        "title": other,
        "referencing": "harvard",
        "assessment": other,
        "conclusion": "noted",
        "sources": [_review_source()],
        "references_markdown": lone,
        "sections": [
            {
                "heading": "Fishery closure",
                "body": f"This report answers the assignment. {QUESTION} (North, 2011; Nobody, 1999).",
            }
        ],
    }
    from essay_writer.state import save_state

    save_state(other, state)
    copied_list = work_dir(other) / "citation-list.json"
    if copied_list.is_file():
        copied_list.unlink()
    kept = _sequence_docx(other)
    _write_word(
        kept, "The first draft stays.", [lone], [_review_source()], italic=True, title=other
    )
    kept_hash = _sha(kept)
    missing = write_stage10(other)
    assert missing.get("ok") is False, missing
    assert missing.get("refused") == "references-cites"
    assert _sha(kept) == kept_hash
    assert not list((work_dir(other) / "output").rglob("*-final.docx"))
    assert workspace is not None


def test_two_works_that_share_a_short_cite_stay_on_their_own_ids(workspace):
    """AC-close-4: Matching and look-up use each work's unique source id. Two works that share a short citation are not crossed."""
    seq = _open()
    first = {
        "id": "simons-2014-coast",
        "author": "Simons, J.",
        "year": "2014",
        "title": "Fishery closure and herring stock recover on the coast",
        "doi": "10.1000/simons-2014-coast",
    }
    second = {
        "id": "simons-2014-inland",
        "author": "Simons, J.",
        "year": "2014",
        "title": "Fishery closure and herring stock recover inland",
        "doi": "10.1000/simons-2014-inland",
    }
    _ship(seq, [first, second])
    short = short_in_text("Simons, J.", "2014")
    assert match_token(seq, short) is None
    both = reference_entries_for_token(seq, short.strip("()"))
    assert {str(entry.get("source_id")) for entry in both} == {
        "simons-2014-coast",
        "simons-2014-inland",
    }
    coast = match_token(seq, "simons-2014-coast")
    inland = match_token(seq, "simons-2014-inland")
    assert coast is not None and inland is not None
    assert coast.get("title") != inland.get("title")
    assert coast.get("reference") != inland.get("reference")
    assert "coast" in str(coast.get("title"))
    assert "inland" in str(inland.get("title"))
    assert workspace is not None


def test_the_finished_essay_cites_within_the_locked_floor_and_cap(workspace, monkeypatch, tmp_path):
    """AC-close-5: The finished essay cites at least the locked floor and at most the locked cap, only relevant works, matched by unique source id, and a final Word file is written. A silent 2,000-word brief uses floor 16 and cap 24."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    assert rate_for_words(2000) == 16
    seq = _open(BRIEF_2000)
    rows = _specials() + [_filler(index) for index in range(1, 17)]
    assert len(rows) == 19
    body = _ready(seq, rows, words=1900)
    bounds = essay_cite_bounds(seq)
    assert bounds["minimum"] == 16
    assert bounds["maximum"] == 24
    listed = load_citation_list(seq)["entries"]
    sources = [
        {
            "id": entry.get("source_id"),
            "title": entry.get("title"),
            "in_text": entry.get("in_text"),
            "author": entry.get("author"),
            "year": entry.get("year"),
        }
        for entry in listed
    ]
    cited = cited_source_ids(body, sources)
    assert len(cited) == 19
    assert len(cited) == len(set(cited))
    for source in sources:
        assert work_is_relevant(source, QUESTION, PLAN) is True
        assert source["id"] in cited
    lines = _stored_lines(seq)
    draft = _sequence_docx(seq)
    _write_word(draft, body, lines, rows, italic=True, title=seq)
    first_draft = draft.read_bytes()
    _arm(seq)
    passed = _review(seq)
    assert passed.get("stored") is True, passed
    closed = _stage10(seq)
    assert closed.get("ok") is True, closed
    final = _final_file(seq)
    counted = "\n".join(ident for ident in cited)
    _proof("cite-count-by-source-id.txt", f"floor 16\ncap 24\ncited {len(cited)}\n{counted}\n")
    _proof("finished-essay.docx", first_draft)
    _proof("finished-essay-final.docx", final.read_bytes())
    assert workspace is not None


def test_the_final_document_title_is_the_short_title_on_the_first_draft(
    workspace, monkeypatch, tmp_path
):
    """AC-close-6: The document title on the final Word file is the short title already on the first-draft Word file, never the opening paragraph, and within Word's 255-character limit. After the cover, the essay wording still matches the first draft, once."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = _open()
    rows = _specials()
    body = _ready(seq, rows)
    lines = _stored_lines(seq)
    draft = _sequence_docx(seq)
    _write_word(draft, body, lines, rows, italic=True, title=seq)
    opening = body.split(". ")[0]
    assert len(opening) < 255
    assert Document(str(draft)).core_properties.title == seq
    assert Document(str(draft)).core_properties.title != opening
    _arm(seq)
    passed = _review(seq)
    assert passed.get("stored") is True, passed
    closed = _stage10(seq)
    assert closed.get("ok") is True, closed
    final = _final_file(seq)
    title = Document(str(final)).core_properties.title
    assert title == seq
    assert title != opening
    assert len(title) <= 255
    final_text = "\n".join(paragraph.text for paragraph in Document(str(final)).paragraphs)
    assert body in final_text
    assert final_text.count(body) == 1
    _proof("document-title.txt", f"{title}\n")
    _proof("document-title-final.docx", final.read_bytes())
    assert workspace is not None


def test_the_shortlist_and_the_missing_plan_return_stay_as_they_are(workspace):
    """AC-close-7: This cut does not change the stage 4a shortlist-before-download, or the return to the earlier step when the confirmed question or the stage 3 plan is missing."""
    assert missing_step("", "") == QUESTION_STEP
    assert missing_step(QUESTION, "") == PLAN_STEP
    assert missing_step(QUESTION, PLAN) is None
    empty = _open("")
    works = [_review_source()]
    no_question = choose_downloads(empty, works)
    assert no_question["ready"] is False
    assert no_question["shortlist"] == []
    assert no_question["return_to"] == "question-confirm"
    asked = _open()
    no_plan = choose_downloads(asked, works)
    assert no_plan["ready"] is False
    assert no_plan["shortlist"] == []
    assert no_plan["return_to"] == "plan"
    note = _note_path(asked, "3")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        render_tracking("3", status="final", look=QUESTION, essay_id=asked),
        encoding="utf-8",
    )
    ready = choose_downloads(asked, works)
    assert ready.get("return_to") is None
    assert ready["shortlist"]
    assert QUESTION_STEP == "question-confirm"
    assert workspace is not None


def test_a_title_italic_refusal_can_be_amended_and_reviewed_again(workspace, monkeypatch, tmp_path):
    """AC-close-8: After an independent review refusal, including a Harvard title-italic miss, the writer can amend and request a second review. A first refusal does not end the job, does not mark the last step done, and does not overwrite a good first-draft Word file. When the second review passes, Stage 10 writes the final Word file. The last step stays closed while the review is still open. One review error does not end the run."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = _open()
    rows = _specials()
    body = _ready(seq, rows)
    lines = [
        _period_after_year(line, year)
        for line, year in zip(_stored_lines(seq), ("2010", "2011", "2009"), strict=True)
    ]
    draft = _sequence_docx(seq)
    _write_word(draft, body, lines, rows, italic=False, title=seq)
    _arm(seq)
    before = _sha(draft)
    refused = essay_review(seq, "9", "PASS", "draft", constitution=LOOK)
    assert refused.get("ok") is False, refused
    assert refused.get("stored") is not True
    assert refused.get("refused") == "harvard-references"
    codes = {item["code"] for item in refused.get("misses") or []}
    assert "title-italic" in codes
    assert "eqr" not in load_state(seq)
    held = _stage10(seq)
    assert held.get("ok") is False, held
    assert held.get("refused") == "eqr"
    assert "still open" in str(held.get("reason") or "").casefold()
    pointer = load_pointer(seq)
    assert pointer.get("closed") is False
    assert "10" not in (pointer.get("saved") or [])
    assert _sha(draft) == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    _write_word(draft, body, lines, rows, italic=True, title=seq)
    passed = _review(seq)
    assert passed.get("stored") is True, passed
    closed = _stage10(seq)
    assert closed.get("ok") is True, closed
    final = _final_file(seq)
    assert final.name != draft.name
    record = "\n".join(
        [
            "first review: refused harvard-references title-italic",
            "last step while open: still open, not saved, first draft unchanged",
            "second review: stored",
            f"final: {final.name}",
        ]
    )
    _proof("refusal-then-pass.txt", record + "\n")
    _proof("refusal-then-pass-final.docx", final.read_bytes())
    assert workspace is not None


def _plain_word(seq: str, lines: list[str]) -> Path:
    path = _sequence_docx(seq)
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))
    return path


def _gate(seq: str, stage: str, constitution: str | None = None) -> dict:
    return essay_review(seq, stage, "PASS", "draft", constitution=constitution)


def test_each_review_gate_allows_a_second_review(workspace):
    """AC-close-9: After an independent review refusal at any review gate on the path, the writer can amend and get a second review. A first refusal does not end the job. Gates checked: Harvard title italic, no citations, the assignment question, the top band, an unquoted gathered sentence, an unreadable Word file, stage 6 question, and a stage 6 draft that is not intact. The writer seat is refused and a reviewer can still review. Residual: the opener reports an unreadable file before the separate saved-but-not-opened branch, so that branch is not a second reachable gate."""
    checked: list[str] = []

    seq = _open()
    rows = [_plan_source()]
    body = _ready(seq, rows)
    draft = _sequence_docx(seq)
    _write_word(draft, body, _stored_lines(seq), rows, italic=False, title=seq)
    first = _gate(seq, "9")
    assert first.get("stored") is not True
    assert first.get("refused") == "harvard-references"
    assert "10" not in (load_pointer(seq).get("saved") or [])
    _write_word(draft, body, _stored_lines(seq), rows, italic=True, title=seq)
    second = _review(seq)
    assert second.get("stored") is True, second
    checked.append("harvard-title")

    bare = _open()
    _plain_word(bare, [f"This report answers the assignment. {QUESTION}"])
    missed = _gate(bare, "9")
    assert missed.get("stored") is not True
    assert "no citations" in str(missed.get("reason") or "").casefold()
    _plain_word(bare, [f"This report answers the assignment. {QUESTION} (Ada, 2020)."])
    assert _review(bare).get("stored") is True
    checked.append("no-citations")

    asked = _open()
    _plain_word(asked, ["This report names a different topic (Ada, 2020)."])
    question_miss = _gate(asked, "9")
    assert question_miss.get("stored") is not True
    assert question_miss.get("refused") == "assignment-gate"
    _plain_word(asked, [f"This report answers the assignment. {QUESTION} (Ada, 2020)."])
    assert _review(asked).get("stored") is True
    checked.append("assignment-question")

    band = _open()
    folder = essay_dir(MODULE)
    (folder / "mark-scheme.md").write_text(TOP_TABLE, encoding="utf-8")
    _plain_word(band, [f"This report answers the assignment. {QUESTION} (Ada, 2020)."])
    low = _gate(band, "9")
    assert low.get("stored") is not True
    assert "top band" in str(low.get("reason") or "").casefold()
    _plain_word(
        band,
        [
            f"This report answers the assignment. {QUESTION} (Ada, 2020). "
            "It sustains an original thesis with specific gathered sources and judges the alternatives."
        ],
    )
    stored_band_review = _review(band)
    assert stored_band_review.get("stored") is True, stored_band_review
    stored_band = load_state(band).get("eqr", {}).get("9", {})
    assert stored_band.get("verdict") == "PASS"
    (folder / "mark-scheme.md").unlink()
    checked.append("top-band")

    copied = _open()
    from helpers import write_upload

    write_upload(workspace, MODULE, "herring.md", COPIED + "\n")
    state = load_state(copied)
    state["research"] = {
        "summary": {
            "sources": [
                {
                    "id": "gathered-herring",
                    "locator": f"uploads/{MODULE}/herring.md",
                    "author": "Ada North",
                    "year": "2011",
                }
            ]
        },
        "full": None,
    }
    from essay_writer.state import save_state

    save_state(copied, state)
    _plain_word(copied, [f"This report answers the assignment. {QUESTION} {COPIED} (Ada, 2020)."])
    unquoted = _gate(copied, "9")
    assert unquoted.get("stored") is not True
    assert "quotation marks" in str(unquoted.get("reason") or "").casefold()
    _plain_word(
        copied,
        [f'This report answers the assignment. {QUESTION} "{COPIED}" (Ada, 2020).'],
    )
    quoted = _review(copied)
    assert quoted.get("stored") is True, quoted
    checked.append("unquoted-sentence")

    broken = _open()
    bad = _sequence_docx(broken)
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"this is not a word file")
    unreadable = _gate(broken, "9")
    assert unreadable.get("stored") is not True
    assert "could not be opened" in str(unreadable.get("reason") or "").casefold()
    _plain_word(broken, [f"This report answers the assignment. {QUESTION} (Ada, 2020)."])
    assert _review(broken).get("stored") is True
    checked.append("unreadable-word")

    stage6 = _open()
    inherited = _sequence_docx(stage6)
    if inherited.is_file():
        inherited.unlink()
    wrong = _gate(stage6, "6", constitution="This report is about a different topic.")
    assert wrong.get("stored") is not True
    assert "assignment question" in str(wrong.get("reason") or "").casefold()
    draft = essay_review(stage6, "6", "PASS", "draft", constitution=LOOK)
    assert draft.get("ok") is True, draft
    stored = essay_review(stage6, "6", "PASS", "confirm", constitution=LOOK)
    assert stored.get("stored") is True, stored
    checked.append("stage-6-question")

    intact = _open(BRIEF_2000)
    inherited = _sequence_docx(intact)
    if inherited.is_file():
        inherited.unlink()
    pointer = load_pointer(intact)
    pointer["saved"] = ["1", "2", "3", "4a", "4b", "5"]
    path = work_dir(intact) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(pointer, indent=2) + "\n", encoding="utf-8")
    note = _note_path(intact, "5")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        render_tracking("5", status="final", look="Short.", essay_id=intact),
        encoding="utf-8",
    )
    short = _gate(intact, "6", constitution=LOOK)
    assert short.get("stored") is not True
    assert "not intact" in str(short.get("reason") or "").casefold()
    long = _essay([_plan_source()], words=1900)
    note.write_text(
        render_tracking("5", status="final", look=long, essay_id=intact), encoding="utf-8"
    )
    draft = essay_review(intact, "6", "PASS", "draft", constitution=LOOK)
    assert draft.get("ok") is True, draft
    stored = essay_review(intact, "6", "PASS", "confirm", constitution=LOOK)
    assert stored.get("stored") is True, stored
    checked.append("stage-6-not-intact")

    writer = _open()
    blocked = essay_review(writer, "9", "PASS", "confirm", seat="writer", constitution=LOOK)
    assert blocked.get("stored") is not True
    assert blocked.get("refused") == "seat"
    _plain_word(writer, [f"This report answers the assignment. {QUESTION} (Ada, 2020)."])
    assert _review(writer).get("stored") is True
    checked.append("writer-seat")

    _proof("review-gates.txt", "\n".join(checked) + "\nresidual: saved-but-not-opened\n")
    assert checked == [
        "harvard-title",
        "no-citations",
        "assignment-question",
        "top-band",
        "unquoted-sentence",
        "unreadable-word",
        "stage-6-question",
        "stage-6-not-intact",
        "writer-seat",
    ]
    assert workspace is not None


def test_public_wording_covers_cursor_and_build(workspace):
    """AC-public-1: Public wording. Cursor and Build share the review gates and the last step. Build covered."""
    for stage in ("6", "9", "10", "eqr"):
        assert (
            cursor_stage_launch(stage)["settings"]["rules"]
            == stage_launch(stage)["settings"]["rules"]
        )
        assert cursor_stage_launch(stage)["settings"] == stage_settings(stage)
    assert build_opened_word_gate is not cursor_opened_word_gate
    assert "opened_word_gate" in inspect.getsource(build_opened_word_gate)
    assert "opened_word_gate" in inspect.getsource(cursor_opened_word_gate)
    assert "A first refusal does not end the job" in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []
    assert _leaked(REVIEW_PROMPT) == []
    version = (
        Path(__file__).resolve().parents[1].joinpath("pyproject.toml").read_text(encoding="utf-8")
    )
    assert f'version = "{__version__}"' in version
    assert workspace is not None
