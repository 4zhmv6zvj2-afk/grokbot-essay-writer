"""Source id, stored details, and quotation checks.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. They are not parametrize labels.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from helpers import open_sequence
from test_citation_list import (
    _entry,
    _plant,
    _proof,
    _ready,
    _source,
    _walk,
)
from test_student_plain_close import _assert_plain

from essay_writer.build_office import stage_launch
from essay_writer.citation_list import load_citation_list, student_list_text
from essay_writer.cite_fit import apply_body_cites, load_record
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.paths import uploads_dir, work_dir, workspace_root
from essay_writer.review import PERSON_BLOCK, eqr_verdict, essay_review, writer_clears_left
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state

REPO = Path(__file__).resolve().parents[1]
KEITH_ID = "10.1371_journal.pone.0340369"
KEITH_SHORT = "(Keith et al., 2026)"
KEITH_HEADING = (
    "Keith, A., Jones, B., Smith, C. and Patel, D. A different title than the stored one "
    "(1999). doi:10.1371/journal.pone.0340369.\n\nThe count after the closure is the point.\n"
)
PLAIN_HEADING = "Notes from the closure paper.\n\nThe count is what the paper adds.\n"
PORT_SENTENCE = "The port stayed open after the closure."
COPIED_SENTENCE = "The stock stayed outside safe biological limits after the closure."
LIST_KEYS = {
    "source_id",
    "locator",
    "author",
    "year",
    "title",
    "doi",
    "in_text",
    "reference",
    "note",
}


def _plant_keith() -> str:
    seq = open_sequence()
    row = _source(
        seq,
        KEITH_ID,
        "Keith, A., Jones, B., Smith, C. and Patel, D.",
        "2026",
        title="Counting fish after the closure",
        doi="10.1371/journal.pone.0340369",
    )
    _plant(seq, [row])
    _walk(seq)
    return seq


def _note_path(entry: dict) -> Path:
    return workspace_root() / entry["note"]


def _note_record(entry: dict) -> Path:
    note = _note_path(entry)
    return note.with_name(f"{note.stem}.record.json")


def _source_record(seq: str, source_id: str) -> Path:
    return work_dir(seq) / "output" / "source-records" / f"{source_id}.record.json"


def _write_heading(entry: dict, text: str) -> None:
    path = _note_path(entry)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def _save_draft(seq: str, text: str) -> str:
    draft = essay_stage(seq, "5", "draft", text)
    assert draft["ok"] is True, draft
    assert draft.get("stored") is True, draft
    look = _note_look(seq, "5") or ""
    assert look.strip()
    return look


def _opened_file(seq: str, source_id: str, text: str) -> Path:
    folder = uploads_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{source_id}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_three_parts_share_one_source_id(workspace):
    """AC-cite-id-1: The opened file, the note, and the list entry share one source id."""
    seq, _rows = _ready()
    listed = student_list_text(seq)
    for ident in ("smith", "froese"):
        assert f"{ident}:source" in listed
        assert f"{ident}:note" in listed
        assert f"{ident}:list" in listed
        entry = _entry(seq, ident)
        assert entry["part_source"] == f"{ident}:source"
        assert entry["part_note"] == f"{ident}:note"
        assert entry["part_list"] == f"{ident}:list"
        note_record = json.loads(_note_record(entry).read_text(encoding="utf-8"))
        source_record = json.loads(_source_record(seq, ident).read_text(encoding="utf-8"))
        assert note_record["source_id"] == ident
        assert source_record["source_id"] == ident
        assert entry["source_id"] == ident
        assert _note_record(entry) != _source_record(seq, ident)
    raw = json.loads((work_dir(seq) / "citation-list.json").read_text(encoding="utf-8"))
    for item in raw["entries"]:
        assert set(item) == LIST_KEYS
    _proof("citation-list-source-id-extract.txt", listed + "\n")
    assert workspace is not None


def test_a_year_left_off_the_first_line_stays_usable(workspace):
    """AC-cite-id-2: A first line that leaves out the year stays usable, including 1371."""
    seq = _plant_keith()
    entry = _entry(seq, KEITH_ID)
    _write_heading(entry, KEITH_HEADING)
    shown = _entry(seq, KEITH_ID)
    assert shown["usable"] is True
    assert shown["conflict"] == ""
    assert shown["gap"] == ""
    assert shown["year"] == "2026"
    assert shown["in_text"] == KEITH_SHORT
    look = _save_draft(seq, f"The count after the closure used the stored paper {KEITH_SHORT}.")
    assert KEITH_SHORT in look
    _proof("saved-draft-year-omitted.txt", look + "\n")
    assert workspace is not None


def test_a_plain_heading_stays_usable(workspace):
    """AC-cite-id-3: A research note does not have to use a Harvard heading."""
    seq = _plant_keith()
    entry = _entry(seq, KEITH_ID)
    _write_heading(entry, PLAIN_HEADING)
    shown = _entry(seq, KEITH_ID)
    assert shown["usable"] is True
    assert shown["conflict"] == ""
    assert "Harvard" not in _note_path(shown).read_text(encoding="utf-8")
    held = apply_body_cites(seq, "5", f"The count stands {KEITH_SHORT}.")
    assert KEITH_SHORT in held["text"]
    assert workspace is not None


def test_an_in_text_citation_uses_the_stored_short_form(workspace):
    """AC-cite-id-4: An in-text citation is found by source id and keeps the stored short form."""
    seq = _plant_keith()
    text = (
        "The count used the stored paper (10.1371_journal.pone.0340369). "
        "Another wording is (Keith and others, 2026). "
        "A made-up year (Keith, 1999) is not this paper."
    )
    look = _save_draft(seq, text)
    assert KEITH_SHORT in look
    assert "10.1371_journal.pone.0340369" not in look
    assert "Keith and others" not in look
    assert "(Keith, 1999)" not in look
    _proof("saved-draft-stored-short-form.txt", look + "\n")
    assert workspace is not None


def test_an_unlisted_citation_is_left_out(workspace):
    """AC-cite-id-5: An off-list citation is removed and is not saved as a used citation."""
    seq = _plant_keith()
    text = (
        f"Closure advice was not taken {KEITH_SHORT}. "
        "A paper outside the gathered set is not used (Nobody, 1999)."
    )
    look = _save_draft(seq, text)
    assert KEITH_SHORT in look
    assert "(Nobody, 1999)" not in look
    record = load_record(seq)
    assert not any("nobody" in item.casefold() for item in record["ok"])
    _proof("saved-draft-unlisted-cite.txt", look + "\n")
    assert workspace is not None


def test_stored_details_must_match_across_the_three_records(workspace):
    """AC-cite-id-6: A conflict is a stored-detail mismatch, not a heading difference."""
    seq = _plant_keith()
    entry = _entry(seq, KEITH_ID)
    note_record = _note_record(entry)
    source_record = _source_record(seq, KEITH_ID)
    original_note = note_record.read_text(encoding="utf-8")
    original_source = source_record.read_text(encoding="utf-8")
    _write_heading(entry, KEITH_HEADING)
    headed = _entry(seq, KEITH_ID)
    assert headed["usable"] is True
    assert headed["conflict"] == ""
    assert headed["year"] == "2026"
    kept = apply_body_cites(seq, "5", f"The count stands {KEITH_SHORT}.")
    assert KEITH_SHORT in kept["text"]

    note_data = json.loads(original_note)
    note_data.pop("year")
    note_record.write_text(json.dumps(note_data, indent=2) + "\n", encoding="utf-8")
    filled = _entry(seq, KEITH_ID)
    assert filled["usable"] is True
    assert filled["conflict"] == ""
    assert filled["gap"] == ""
    assert json.loads(note_record.read_text(encoding="utf-8"))["year"] == "2026"
    assert "(1999)" in _note_path(filled).read_text(encoding="utf-8")

    note_data = json.loads(note_record.read_text(encoding="utf-8"))
    source_data = json.loads(source_record.read_text(encoding="utf-8"))
    note_data.pop("year")
    source_data.pop("year")
    note_record.write_text(json.dumps(note_data, indent=2) + "\n", encoding="utf-8")
    source_record.write_text(json.dumps(source_data, indent=2) + "\n", encoding="utf-8")
    missing = _entry(seq, KEITH_ID)
    assert missing["usable"] is False
    assert missing["conflict"] == ""
    assert "missing a stored detail" in missing["gap"].casefold()
    dropped = apply_body_cites(seq, "5", f"The count stands {KEITH_SHORT}.")
    assert KEITH_SHORT not in dropped["text"]

    note_record.write_text(original_note, encoding="utf-8")
    source_record.write_text(original_source, encoding="utf-8")
    restored = _entry(seq, KEITH_ID)
    assert restored["usable"] is True
    mismatched = original_note.replace('"year": "2026"', '"year": "1999"', 1)
    note_record.write_text(mismatched, encoding="utf-8")
    conflicted = _entry(seq, KEITH_ID)
    assert conflicted["usable"] is False
    assert "stored details" in conflicted["conflict"].casefold()
    assert "do not agree" in conflicted["conflict"].casefold()
    assert conflicted["year"] == "2026"
    assert json.loads(source_record.read_text(encoding="utf-8"))["year"] == "2026"
    assert '"year": "1999"' in note_record.read_text(encoding="utf-8")
    blocked = apply_body_cites(seq, "5", f"The count stands {KEITH_SHORT}.")
    assert KEITH_SHORT not in blocked["text"]

    note_record.write_text(original_note, encoding="utf-8")
    state = load_state(seq)
    state["research"]["summary"]["sources"][0]["year"] = "1998"
    save_state(seq, state)
    untouched = _entry(seq, KEITH_ID)
    assert untouched["usable"] is True
    assert untouched["conflict"] == ""
    assert json.loads(source_record.read_text(encoding="utf-8"))["year"] == "2026"
    _opened_file(seq, KEITH_ID, "A newer file for the same paper.\n")
    refreshed = _entry(seq, KEITH_ID)
    assert json.loads(source_record.read_text(encoding="utf-8"))["year"] == "1998"
    assert refreshed["year"] == "2026"
    assert json.loads(note_record.read_text(encoding="utf-8"))["year"] == "2026"
    assert refreshed["usable"] is False
    assert "do not agree" in refreshed["conflict"].casefold()
    held = apply_body_cites(seq, "5", f"The count stands {KEITH_SHORT}.")
    assert KEITH_SHORT not in held["text"]
    assert workspace is not None


def test_a_short_fragment_does_not_block_the_pass(workspace):
    """AC-quote-1: e.g. and the fragment g. do not refuse a pass."""
    seq, _rows = _ready()
    _opened_file(
        seq,
        "smith",
        "Examples are marked in the text.\ne.\ng.\n" + PORT_SENTENCE + "\n",
    )
    look = _save_draft(
        seq,
        "The harbour note uses e.g. as an example of the closure (Smith, 2020).",
    )
    assert "e.g." in look
    preview = essay_review(seq, "6", "PASS", "draft")
    assert preview["ok"] is True, preview
    assert "without quotation marks" not in str(preview.get("reason") or "")
    stored = essay_review(seq, "6", "PASS", "confirm")
    assert stored["stored"] is True, stored
    assert eqr_verdict(seq, "6") == "PASS"
    word = work_dir(seq) / "output" / f"{seq}.docx"
    assert word.is_file()
    _proof("review-response-fragment.txt", "pass recorded\n" + look + "\n")
    assert workspace is not None


def test_an_unquoted_sentence_is_refused(workspace):
    """AC-quote-2: A gathered sentence without quotation marks is refused and not recorded."""
    seq, _rows = _ready()
    _opened_file(seq, "smith", COPIED_SENTENCE + "\n")
    look = _save_draft(seq, f"{COPIED_SENTENCE} The harbour note cites the closure (Smith, 2020).")
    assert COPIED_SENTENCE in look
    refused = essay_review(seq, "6", "PASS", "draft")
    assert refused["ok"] is False
    assert refused["stored"] is False
    assert "without quotation marks" in str(refused.get("reason") or "")
    assert "Nothing was recorded" in str(refused.get("reason") or "")
    assert eqr_verdict(seq, "6") is None
    word = work_dir(seq) / "output" / f"{seq}.docx"
    assert not word.is_file()
    _proof("review-response-unquoted-sentence.txt", str(refused.get("reason") or "") + "\n")
    assert workspace is not None


def test_the_writer_cannot_clear_the_review(workspace):
    """AC-quote-3: The writer cannot clear the review."""
    seq = open_sequence()
    refused = essay_review(seq, "6", "PASS", seat="writer")
    assert refused["reason"] == PERSON_BLOCK
    assert refused["stored"] is False
    assert writer_clears_left() == 0
    assert workspace is not None


def test_public_wording_covers_both_shells(workspace):
    """AC-public-1: Public wording, one rule list, and the version stays 0.9.15."""
    stages = ("4b", "5", "6", "eqr")
    for stage in stages:
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
    shared = "\n".join(stage_launch(stage)["settings"]["rules"] for stage in ("4b", "5", "6"))
    review_rules = stage_launch("eqr")["settings"]["rules"]
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    _assert_plain(shared, allow={"p-3", "p-10"})
    assert "Do not treat e.g. or the fragment g." in review_rules
    assert "Critical note" not in shared
    assert "Critical note" not in review_rules
    assert "Critical note" not in changelog
    assert "Build covered" in changelog
    assert "Cursor and Grok Build" in changelog
    version = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.9.15"' in version
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_the_three_parts_share_one_source_id": "AC-cite-id-1",
        "test_a_year_left_off_the_first_line_stays_usable": "AC-cite-id-2",
        "test_a_plain_heading_stays_usable": "AC-cite-id-3",
        "test_an_in_text_citation_uses_the_stored_short_form": "AC-cite-id-4",
        "test_an_unlisted_citation_is_left_out": "AC-cite-id-5",
        "test_stored_details_must_match_across_the_three_records": "AC-cite-id-6",
        "test_a_short_fragment_does_not_block_the_pass": "AC-quote-1",
        "test_an_unquoted_sentence_is_refused": "AC-quote-2",
        "test_the_writer_cannot_clear_the_review": "AC-quote-3",
        "test_public_wording_covers_both_shells": "AC-public-1",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert f'id="{ident}"' not in source
    seq, _rows = _ready()
    _assert_plain(student_list_text(seq))
    listed = load_citation_list(seq)
    assert listed["written"] is True
    assert workspace is not None
