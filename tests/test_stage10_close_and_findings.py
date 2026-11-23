"""Stage 10 close for a stored short form, and the findings heading.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. Opaque ids name a deny-list hit. The phrases
themselves are not parametrize labels.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from docx import Document
from helpers import open_sequence, picked
from test_word_references_4a import (
    MODULE,
    NUMBER,
    _brief,
    _diary_pack,
    _park_stage10,
    _plant_stage10_pack,
)

from essay_writer.build_office import stage_launch
from essay_writer.citation_list import list_written, load_citation_list, short_in_text
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.harvard_ref_check import _author_year_present
from essay_writer.late_chain import write_stage10
from essay_writer.paths import module_code, work_dir
from essay_writer.research_packs import ship_4a, ship_4b
from essay_writer.specialists.eqr import (
    CLAIM_CHECKS,
    NORTH_STAR,
    student_findings_text,
    write_findings_note,
)
from essay_writer.stage_llm import HOUSE_MODEL
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.word import write_first_draft_word
from essay_writer.word_references import _line_covers_cite, cite_reference_gaps, token_is_covered

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")
HYPHEN = "\u2010"
NOTE = "The opened file states the limit, and the year is the one stored on the list."
# Opaque ids. A hit reports the id, not the phrase.
_DENY = {
    "h-1": "c0b7e932ecce97879ac9e9a94cc8d2af82adccf03fdf1bfa8a854f4dc7abf6ba",
    "h-2": "b59e69febb78bfb221db05c452f1e98d4f14a50edde0c7ec8754dda5a7575a9e",
    "h-3": "f73d3f95d9fedff94a4a4b54b65bb5b2794170c702e6b3ab3fd35783050faed8",
}


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


def _pieces(text: str) -> set[str]:
    folded = text.casefold()
    tokens = re.findall(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", folded)
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    found.update(line.strip() for line in folded.splitlines() if line.strip())
    return found


def _leaked(text: str) -> list[str]:
    digests = {hashlib.sha256(piece.encode()).hexdigest() for piece in _pieces(text)}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    if HOUSE_MODEL.casefold() in text.casefold():
        leaked.append("h-4")
    return leaked


def _long_authors(lead: str, minimum: int = 270) -> str:
    names = [lead]
    index = 1
    while len(" and ".join(names)) + 2 < minimum:
        names.append(f"Person{index} Family{index}")
        index += 1
    return " and ".join(names)


def _year_at(line: str) -> int:
    match = re.search(r"\((\d{4})", line)
    assert match is not None, line
    return match.start(1)


def _source(ident: str, author: str, year: str, title: str) -> dict[str, str]:
    return {
        "id": ident,
        "author": author,
        "year": year,
        "title": title,
        "doi": f"10.1000/{ident}",
    }


def _rows() -> list[dict[str, str]]:
    return [
        _source(
            "dickey",
            _long_authors(f"Mark Dickey{HYPHEN}Collas"),
            "2010",
            "Herring recovery",
        ),
        _source("beare", _long_authors("Doug Beare", 300), "2013", "Plaice box"),
        _source("keith", _long_authors("David Keith", 330), "2026", "Recovery potential"),
        _source("froese", "Rainer Froese and Martin Quaas", "2012", "Cod advice"),
    ]


def _body(rows: list[dict[str, str]]) -> str:
    sentences = []
    for row in rows:
        cite = short_in_text(row["author"], row["year"]).replace(HYPHEN, "-")
        sentences.append(f"The opened file states the limit {cite}.")
    return " ".join(sentences)


def _listed(seq: str) -> str:
    rows = _rows()
    delivered = ship_4b(seq, rows, {row["id"]: NOTE for row in rows})
    assert delivered.get("wrote") is not False, delivered
    assert list_written(seq) is True
    return _body(rows)


def _stored_markdown(seq: str) -> str:
    listed = load_citation_list(seq)
    lines = [
        str(entry.get("reference") or "").strip()
        for entry in listed["entries"]
        if str(entry.get("reference") or "").strip()
    ]
    return "\n".join(lines)


def _plant(seq: str, body: str) -> dict:
    _brief()
    from essay_writer.brief_contract import remember_registration

    remember_registration(seq, NUMBER)
    _park_stage10(seq)
    pack = _diary_pack(seq, body=body, references_markdown=_stored_markdown(seq))
    _plant_stage10_pack(seq, pack)
    return pack


def _final_file(seq: str) -> Path:
    found = sorted((work_dir(seq) / "output").rglob("*-final.docx"))
    assert len(found) == 1, [str(path) for path in found]
    return found[0]


def _seed_first_draft(seq: str) -> Path:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph("The first draft stays on this sequence.")
    document.save(str(path))
    return path


def test_stage10_stores_the_close_and_writes_the_final_file(workspace, monkeypatch, tmp_path):
    """AC-close-1: Stored short forms on long Harvard lines close and write a new final Word file."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    body = _listed(seq)
    listed = load_citation_list(seq)
    distances = {}
    for entry in listed["entries"]:
        if entry.get("year") in {"2010", "2013", "2026"}:
            distances[entry["year"]] = _year_at(entry["reference"])
            assert distances[entry["year"]] > 250
    assert distances["2010"] >= 273 or distances["2010"] > 250
    _plant(seq, body)
    draft = essay_stage(seq, "10", "draft", "The final file is ready.")
    assert draft["ok"] is True, draft
    stored = essay_stage(seq, "10", "confirm", "The final file is ready.", **picked(draft))
    assert stored["ok"] is True, stored
    assert stored["stored"] is True, stored
    assert stored["closed"] is True, stored
    final = _final_file(seq)
    assert final.name != f"{seq}.docx"
    assert "first-draft" not in final.name
    text = _docx_text(final)
    assert "(Dickey-Collas et al., 2010)" in text or f"(Dickey{HYPHEN}Collas et al., 2010)" in text
    assert "(Beare et al., 2013)" in text
    assert "(Keith et al., 2026)" in text
    assert "(Froese and Quaas, 2012)" in text
    _proof(
        "stage10-close-response.txt",
        json.dumps(
            {
                "ok": stored["ok"],
                "stored": stored["stored"],
                "closed": stored["closed"],
                "final": final.name,
            },
            indent=2,
        )
        + "\n",
    )
    _proof("stage10-final.docx", final.read_bytes())
    _proof("stage10-year-distances.txt", json.dumps(distances, indent=2) + "\n")
    assert workspace is not None


def test_long_harvard_lines_stay_covered(workspace):
    """AC-close-2: Short forms stay covered when the year sits more than 250 characters along the line."""
    rows = _rows()
    lines = []
    body = _body(rows)
    from essay_writer.citation_list import full_reference

    for row in rows:
        line = full_reference(row)
        lines.append(line)
        if row["year"] in {"2010", "2013", "2026"}:
            assert _year_at(line) > 250
        else:
            assert _year_at(line) < 80
    assert cite_reference_gaps(lines, [{"heading": "Body", "body": body}]) == []
    seq = open_sequence(MODULE)
    _listed(seq)
    assert token_is_covered("dickey-collas et al., 2010", [], seq) is True
    assert token_is_covered(f"dickey{HYPHEN}collas et al., 2010", [], seq) is True
    assert token_is_covered("beare et al., 2013", [], seq) is True
    assert token_is_covered("keith et al., 2026", [], seq) is True
    assert token_is_covered("froese and quaas, 2012", [], seq) is True
    assert "{0,200}" not in inspect.getsource(_line_covers_cite)
    assert "{0,200}" not in inspect.getsource(_author_year_present)
    assert workspace is not None


def test_an_unlisted_citation_does_not_write_the_final_file(workspace):
    """AC-close-3: A citation that is not on the list is refused and does not replace the first draft."""
    seq = open_sequence(MODULE)
    body = _listed(seq)
    _plant(seq, body + " An unlisted paper is not added (Nobody, 1999).")
    first = _seed_first_draft(seq)
    before = first.read_bytes()
    refused = write_stage10(seq)
    assert refused["ok"] is False, refused
    assert refused.get("stored") is not True
    assert refused["refused"] == "references-cites"
    assert "nobody, 1999" in str(refused.get("reason") or "")
    assert first.read_bytes() == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    pointer = load_pointer(seq)
    assert pointer["current"] == "10"
    assert pointer["closed"] is False
    _proof("stage10-unlisted-refusal.txt", str(refused.get("reason") or "") + "\n")
    assert workspace is not None


def test_a_missing_reference_line_is_refused_and_a_hyphen_still_writes(workspace):
    """AC-close-4: A missing reference line is refused. A hyphen-only name still writes the final file."""
    seq = open_sequence(MODULE)
    author = f"Dickey{HYPHEN}Collas, M."
    ship_4b(
        seq,
        [_source("dickey", author, "2010", "Herring recovery")],
        {"dickey": NOTE},
    )
    cite = short_in_text(author, "2010").replace(HYPHEN, "-")
    assert HYPHEN not in cite
    assert HYPHEN in short_in_text(author, "2010")
    _plant(seq, f"The opened file states the limit {cite}.")
    written = write_stage10(seq)
    assert written["ok"] is True, (written.get("refused"), written.get("reason"))
    final = _final_file(seq)
    assert cite in _docx_text(final)
    before = final.read_bytes()
    working = work_dir(seq) / "output" / f"{seq}.docx"
    working_before = working.read_bytes()

    other = open_sequence(MODULE)
    rows = _rows()[:2]
    ship_4b(other, rows, {row["id"]: NOTE for row in rows})
    path = work_dir(other) / "citation-list.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    target = next(entry for entry in saved["entries"] if entry.get("year") == "2013")
    target["reference"] = ""
    path.write_text(json.dumps(saved), encoding="utf-8")
    shown = load_citation_list(other)
    blank = next(entry for entry in shown["entries"] if entry.get("year") == "2013")
    assert not str(blank.get("reference") or "").strip()
    body = _body(rows)
    _plant(other, body)
    first = _seed_first_draft(other)
    first_before = first.read_bytes()
    refused = write_stage10(other)
    assert refused["ok"] is False, refused
    assert refused["refused"] == "references-cites"
    assert refused.get("stored") is not True
    assert first.read_bytes() == first_before
    assert not list((work_dir(other) / "output").rglob("*-final.docx"))
    assert final.read_bytes() == before
    assert working.read_bytes() == working_before
    _proof("stage10-missing-line-refusal.txt", str(refused.get("reason") or "") + "\n")
    assert workspace is not None


def test_the_close_uses_the_stored_short_form(workspace):
    """AC-span-1: The last step reads the citation list and the stored short form with the draft."""
    seq = open_sequence(MODULE)
    body = _listed(seq)
    sections = [{"heading": "One decision", "body": body}]
    assert cite_reference_gaps([], sections, seq) == []
    source = inspect.getsource(token_is_covered)
    assert "match_token" in source
    assert "list_written" in source
    gate = inspect.getsource(cite_reference_gaps)
    assert "citation_tokens(" in gate
    assert "token_is_covered" in gate
    assert workspace is not None


def test_findings_word_uses_overall_judgement(workspace, tmp_path):
    """AC-findings-1: A findings Word file uses Overall judgement and leaves house shorthand out."""
    seq = open_sequence(MODULE)
    findings = "\n".join(
        [
            NORTH_STAR,
            "How to score high: the mark scheme scores the argument.",
            "Format: essay.",
            "The draft does the assignment.",
            CLAIM_CHECKS,
            "Claim checks against the opened files.",
        ]
    )
    assert NORTH_STAR == "Overall judgement"
    written = write_findings_note(seq, findings, documents=tmp_path)
    assert written["wrote"] is True, written
    path = tmp_path / module_code(seq) / f"{module_code(seq)}-findings.docx"
    assert path.is_file()
    text = _docx_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[0] == "Findings"
    assert lines[1] == "Overall judgement"
    assert _leaked(text) == []
    house = "\n".join(
        [
            "North-star judgement",
            "How to score high: the mark scheme scores the argument.",
            "Format: essay.",
            "The draft does the assignment.",
            "Critical note: " + HOUSE_MODEL,
            CLAIM_CHECKS,
        ]
    )
    cleaned = student_findings_text(house)
    assert cleaned.splitlines()[0] == "Overall judgement"
    assert _leaked(cleaned) == []
    again = write_findings_note(seq, house, documents=tmp_path)
    assert again["wrote"] is True, again
    opened = _docx_text(path)
    assert opened.splitlines()[1].strip() == "Overall judgement"
    assert _leaked(opened) == []
    _proof("findings-first-lines.txt", "\n".join(opened.splitlines()[:6]) + "\n")
    _proof("findings.docx", path.read_bytes())
    assert workspace is not None


def test_other_student_word_files_stay_plain(workspace, monkeypatch, tmp_path):
    """AC-findings-2: Annotation, download list, first draft, final, and source reviews stay plain."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence()
    source = {
        "id": "src-1",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "doi": "10.1000/strait",
    }
    note = "Smith argues the corridor is narrow and the limit is stated in the opened text."
    ship_4a(seq, [source], {"src-1": note})
    delivered = ship_4b(seq, [source], {"src-1": note})
    folder = work_dir(seq) / "output"
    names = [
        folder / "annotation.docx",
        folder / "download-list.docx",
    ]
    review = delivered["reviews"][0]
    review_path = (workspace / str(review["markdown_path"])).with_suffix(".docx")
    names.append(review_path)
    look = "The corridor stayed open after the closure, and the limit is named in the file."
    note_path = _note_path(seq, "5")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        render_tracking("5", status="final", look=look, essay_id=seq),
        encoding="utf-8",
    )
    from essay_writer.stage_state import blank_pointer

    pointer_path = work_dir(seq) / "tracking" / "stage.json"
    pointer = (
        json.loads(pointer_path.read_text(encoding="utf-8"))
        if pointer_path.is_file()
        else blank_pointer()
    )
    saved_stages = list(pointer.get("saved") or [])
    if "5" not in saved_stages:
        saved_stages.append("5")
    pointer["saved"] = saved_stages
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    first = write_first_draft_word(seq)
    assert first.get("wrote") is True, first
    names.append(folder / f"{seq}.docx")
    scanned = []
    for path in names:
        assert path.is_file(), path
        text = _docx_text(path)
        assert _leaked(text) == [], path.name
        assert "Overall judgement" not in text or path.name.endswith("-findings.docx")
        scanned.append(path.name)
    diary = open_sequence(MODULE)
    body = _listed(diary)
    _plant(diary, body)
    written = write_stage10(diary)
    assert written["ok"] is True, written
    final = _final_file(diary)
    final_text = _docx_text(final)
    assert _leaked(final_text) == []
    scanned.append(final.name)
    _proof("student-word-scan.txt", "\n".join(scanned) + "\n")
    assert workspace is not None


def test_public_wording_is_shared(workspace):
    """AC-public-1: Public wording. Cursor and Grok Build share the close and the findings heading. Build covered."""
    for stage in ("6", "9", "10", "eqr"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
    rules = stage_launch("eqr")["settings"]["rules"]
    assert "Overall judgement" in rules
    assert _leaked(rules) == []
    assert "match_token" in inspect.getsource(token_is_covered)
    gate = inspect.getsource(stage_launch)
    assert "Cursor reads that same row" in gate or "stage_settings" in gate
    version = REPO.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.9.15"' in version
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_stage10_stores_the_close_and_writes_the_final_file": "AC-close-1",
        "test_long_harvard_lines_stay_covered": "AC-close-2",
        "test_an_unlisted_citation_does_not_write_the_final_file": "AC-close-3",
        "test_a_missing_reference_line_is_refused_and_a_hyphen_still_writes": "AC-close-4",
        "test_the_close_uses_the_stored_short_form": "AC-span-1",
        "test_findings_word_uses_overall_judgement": "AC-findings-1",
        "test_other_student_word_files_stay_plain": "AC-findings-2",
        "test_public_wording_is_shared": "AC-public-1",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert f'id="{ident}"' not in source
    assert workspace is not None
