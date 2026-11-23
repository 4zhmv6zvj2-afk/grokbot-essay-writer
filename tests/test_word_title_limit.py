"""Stage 10 close when the opening paragraph is longer than Word's title limit.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. Opaque ids name a deny-list hit. The phrases
themselves are not parametrize labels.

Sibling Word writes, mapped before the title change:

- write_docx: stages 6, 7, 9, and the stage 10 final. This is the write that
  used the opening paragraph as the document title.
- write_first_draft_word: the first-draft file. The title is the assessment id.
- write_findings_note: the findings file a student opens.
- write_annotation_docx: the annotated bibliography.
- write_critical_review_docx: a source review.
- downloads._save_docx: the download list.
- late_chain._write_comments: the comments file copied with the final.
- projects._rewrite_docx: a copied Word file whose properties are updated.
"""

from __future__ import annotations

import inspect
import io
import json
import re
import zipfile
from pathlib import Path

from docx import Document
from helpers import open_sequence, picked
from test_stage10_close_and_findings import _leaked
from test_word_references_4a import (
    NUMBER,
    _diary_pack,
    _park_stage10,
    _plant_stage10_pack,
)

from essay_writer import __version__
from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import stage_launch
from essay_writer.citation_list import list_written, load_citation_list, short_in_text
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.downloads import _save_docx
from essay_writer.late_chain import _write_comments, write_stage10
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.projects import _rewrite_docx
from essay_writer.research_packs import write_annotation_docx
from essay_writer.specialists.eqr import NORTH_STAR, write_findings_note
from essay_writer.stage_llm import HOUSE_MODEL
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path, blank_pointer, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.word import write_critical_review_docx, write_docx, write_first_draft_word
from essay_writer.word_references import cite_reference_gaps

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")
MODULE = "ENVS5003HK"
STORED_TITLE = "ENVS5003HK-1"
OPENING = (
    "When is it fair to close a fishery so that a fish stock can recover? This essay answers "
    "that question for one named case, the North Sea. The closure it treats in detail is the "
    "Plaice Box, a nursery area closed to large trawlers in the North Sea flatfish fishery. "
    "Fairness is used here as a judgement about purpose, evidence, and who bears the cost. "
    "It is not a slogan, and it is not filled in where a gathered file is silent. The brief "
    "allows the North Sea, Chesapeake Bay, or the Mekong Delta. The gathered files that can "
    "be read are about the North Sea, so Chesapeake Bay and the Mekong Delta are not used as "
    "the case."
)
LIMIT = 255
BRIEF = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: ENVS5003HK

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Title page: module title, module code, assignment title, and the word count.
Include your student ID.
The name stays off the title page and the file.

Pages: Arial, size 12. 2.5 cm margins on all sides. Page numbers in the lower right.
"""


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


def _title_of(path: Path) -> str:
    title = Document(str(path)).core_properties.title
    return title if isinstance(title, str) else ""


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
        _source("beare", "Doug Beare", "2013", "Plaice box"),
        _source("keith", "David Keith", "2026", "Recovery potential"),
    ]


def _cited_body() -> str:
    rows = _rows()
    sentences = [OPENING]
    for row in rows:
        cite = short_in_text(row["author"], row["year"])
        sentences.append(f"The opened file states the limit {cite}.")
    return " ".join(sentences)


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _listed(seq: str) -> str:
    from essay_writer.research_packs import ship_4b

    rows = _rows()
    note = "The opened file states the limit, and the year is the one stored on the list."
    delivered = ship_4b(seq, rows, {row["id"]: note for row in rows})
    assert delivered.get("wrote") is not False, delivered
    assert list_written(seq) is True
    return _cited_body()


def _stored_markdown(seq: str) -> str:
    listed = load_citation_list(seq)
    lines = [
        str(entry.get("reference") or "").strip()
        for entry in listed["entries"]
        if str(entry.get("reference") or "").strip()
    ]
    return "\n".join(lines)


def _plant(seq: str, body: str, *, title: str | None = None) -> dict:
    _brief()
    remember_registration(seq, NUMBER)
    _park_stage10(seq)
    pack = _diary_pack(seq, body=body, references_markdown=_stored_markdown(seq))
    if title is not None:
        pack["title"] = title
        pack["assessment"] = title
    _plant_stage10_pack(seq, pack)
    return pack


def _draft_file(seq: str, title: str, paragraphs: list[str]) -> Path:
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.core_properties.title = title
    for line in paragraphs:
        document.add_paragraph(line)
    document.save(str(path))
    return path


def _final_file(seq: str) -> Path:
    found = sorted((work_dir(seq) / "output").rglob("*-final.docx"))
    assert len(found) == 1, [str(path) for path in found]
    return found[0]


def _force_core_title(path: Path, title: str) -> None:
    """Put a long property on a Word file without going through the 255-character setter."""
    raw = path.read_bytes()
    source = zipfile.ZipFile(io.BytesIO(raw))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dest:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                text = payload.decode("utf-8")
                escaped = title.replace("&", "&amp;").replace("<", "&lt;")
                text = re.sub(
                    r"<dc:title>.*?</dc:title>",
                    f"<dc:title>{escaped}</dc:title>",
                    text,
                    count=1,
                )
                payload = text.encode("utf-8")
            dest.writestr(item, payload)
    path.write_bytes(out.getvalue())


def _assert_short_title(path: Path, *, banned: str) -> str:
    title = _title_of(path)
    assert len(title) <= LIMIT, title
    assert title != banned
    assert not title.startswith("When is it fair to close a fishery")
    return title


def test_stage10_close_writes_the_final_when_the_opening_is_long(workspace, monkeypatch, tmp_path):
    """AC-title-1: When the citation check already passes, Stage 10 writes a new final Word file whose name is not the first-draft name, stores the step, and can close, even when the first paragraph is longer than 255 characters."""
    assert len(OPENING) == 620
    assert len(OPENING) > LIMIT
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    assert seq == STORED_TITLE
    body = _listed(seq)
    assert cite_reference_gaps([], [{"heading": "One decision", "body": body}], seq) == []
    _plant(seq, body, title=OPENING)
    draft_path = _draft_file(seq, STORED_TITLE, [OPENING, "The opened file states the limit."])
    assert _title_of(draft_path) == STORED_TITLE
    draft = essay_stage(seq, "10", "draft", "The final file is ready.")
    assert draft["ok"] is True, draft
    stored = essay_stage(seq, "10", "confirm", "The final file is ready.", **picked(draft))
    assert stored["ok"] is True, stored
    assert stored["stored"] is True, stored
    assert stored["closed"] is True, stored
    final = _final_file(seq)
    assert final.name != draft_path.name
    assert final.name != f"{seq}.docx"
    assert "first-draft" not in final.name
    text = _docx_text(final)
    assert OPENING in text
    _proof(
        "word-title-close-response.json",
        json.dumps(
            {
                "ok": stored["ok"],
                "stored": stored["stored"],
                "closed": stored["closed"],
                "final": final.name,
                "title": _title_of(final),
            },
            indent=2,
        )
        + "\n",
    )
    _proof("word-title-final.docx", final.read_bytes())
    assert workspace is not None


def test_the_live_opening_does_not_raise_the_title_limit(workspace, monkeypatch, tmp_path):
    """AC-title-2: A fixture that repeats the live fail — a first paragraph longer than 255 characters, as in the 620-character opening paragraph beginning “When is it fair to close a fishery…” — must write the final Word file and must not raise a 255-character title-limit error."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    body = _listed(seq)
    _plant(seq, body, title=OPENING)
    _draft_file(seq, STORED_TITLE, [OPENING])
    written = write_stage10(seq)
    assert written["ok"] is True, written
    assert "255" not in str(written.get("reason") or "")
    final = _final_file(seq)
    assert final.is_file()
    assert OPENING in _docx_text(final)
    _proof("word-title-live-final.docx", final.read_bytes())
    assert workspace is not None


def test_the_final_document_title_is_the_short_title_already_stored(
    workspace, monkeypatch, tmp_path
):
    """AC-title-3: The final Word file’s document title is the short title already on the first-draft Word file (for the live essay, ENVS5003HK-1). If no short title is stored, it is the assessment id or the file name without .docx. It is never the opening paragraph, and it is at most 255 characters."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    body = _listed(seq)
    _plant(seq, body, title=OPENING)
    _draft_file(seq, "Plaice Box", [OPENING])
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    assert _assert_short_title(final, banned=OPENING) == "Plaice Box"
    _proof("word-title-property.txt", _title_of(final) + "\n")

    other = open_sequence(MODULE)
    other_body = _listed(other)
    _plant(other, other_body, title=OPENING)
    _draft_file(other, "", [OPENING])
    assert _title_of(work_dir(other) / "output" / f"{other}.docx") == ""
    again = write_stage10(other)
    assert again["ok"] is True, again
    other_final = _final_file(other)
    fallback = _assert_short_title(other_final, banned=OPENING)
    assert fallback in {other, other_final.stem, Path(f"{other}.docx").stem}
    assert fallback == other
    assert workspace is not None


def test_the_final_keeps_the_draft_wording(workspace, monkeypatch, tmp_path):
    """AC-title-4: The essay wording and in-text citations in the final Word file stay the same as the draft being closed. This cut does not change the body to make the title fit."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    body = _listed(seq)
    cites = [short_in_text(row["author"], row["year"]) for row in _rows()]
    _plant(seq, body, title=OPENING)
    _draft_file(seq, STORED_TITLE, [body])
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final_text = _docx_text(_final_file(seq))
    assert OPENING in final_text
    assert len(OPENING) == 620
    for cite in cites:
        assert cite in body
        assert cite in final_text
    assert workspace is not None


def test_sibling_word_writes_survive_a_long_opening(workspace, tmp_path):
    """AC-title-5: Sibling Word writes are mapped before the first patch. First-draft, findings, annotation, and any other student-facing Word file this product writes must not fail the same 255-character title limit when a long first paragraph is present."""
    seq = open_sequence(MODULE)
    _brief()
    remember_registration(seq, NUMBER)
    note_path = _note_path(seq, "5")
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(
        render_tracking("5", status="final", look=OPENING, essay_id=seq),
        encoding="utf-8",
    )
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
    first_path = work_dir(seq) / "output" / f"{seq}.docx"
    assert _assert_short_title(first_path, banned=OPENING) == seq
    assert OPENING in _docx_text(first_path)

    findings = "\n".join([NORTH_STAR, OPENING, "The draft does the assignment."])
    written = write_findings_note(seq, findings, documents=tmp_path)
    assert written["wrote"] is True, written
    findings_path = tmp_path / module_code(seq) / f"{module_code(seq)}-findings.docx"
    assert _assert_short_title(findings_path, banned=OPENING) in {"", findings_path.stem}
    assert "Overall judgement" in _docx_text(findings_path)

    annotation = work_dir(seq) / "output" / "annotation.docx"
    write_annotation_docx(
        annotation,
        [{"parts": [(OPENING, False)], "paragraph": OPENING}],
        empty_note="None.",
    )
    assert _title_of(annotation) == "Annotated bibliography"
    assert OPENING in _docx_text(annotation)

    review = work_dir(seq) / "output" / "reviews" / "plaice.docx"
    write_critical_review_docx(review, OPENING)
    assert _title_of(review) == "Critical review"
    assert OPENING in _docx_text(review)

    downloads = work_dir(seq) / "output" / "download-list.docx"
    _save_docx(
        downloads,
        [
            ("Sources to download", True, False),
            (OPENING, False, False),
        ],
    )
    assert _title_of(downloads) == "Sources to download"

    comments = work_dir(seq) / "output" / f"{module_code(seq)}-comments.docx"
    state = load_state(seq)
    state["eqr"] = {
        "9": {"seat": "reviewer", "word_opened": True, "findings": OPENING, "verdict": "PASS"}
    }
    save_state(seq, state)
    _write_comments(seq, comments)
    assert comments.is_file()
    assert _assert_short_title(comments, banned=OPENING) in {"", comments.stem}
    assert OPENING in _docx_text(comments)

    report = {
        "sources": [],
        "sections": [{"heading": "One decision", "body": OPENING}],
        "figures": [],
        "tables": [],
        "cover": [],
    }
    pack = {
        "essay_id": seq,
        "title": OPENING,
        "assessment": OPENING,
        "referencing": "harvard",
        "sections": report["sections"],
        "sources": [],
    }
    final_like = work_dir(seq) / "output" / "sibling-final.docx"
    write_docx(seq, pack, report, final_like)
    assert _assert_short_title(final_like, banned=OPENING) == seq
    assert OPENING in _docx_text(final_like)

    copied = work_dir(seq) / "output" / "copied.docx"
    document = Document()
    document.core_properties.title = "SHORT TOKEN"
    document.add_paragraph(OPENING)
    copied.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(copied))
    _force_core_title(copied, OPENING + " TOKEN")
    _rewrite_docx(copied, "TOKEN", "WORD")
    rewritten = _assert_short_title(copied, banned=OPENING)
    assert rewritten
    assert OPENING in _docx_text(copied)
    assert workspace is not None


def test_an_off_list_cite_and_a_missing_line_are_still_refused(workspace):
    """AC-title-6: A citation in the text that is not on the list, such as (Nobody, 1999), and a genuinely missing reference line, are still refused. The step is not stored, no final Word file is written from that refusal, and a good first-draft Word file is not overwritten."""
    seq = open_sequence(MODULE)
    body = _listed(seq)
    _plant(seq, body + " An unlisted paper is not added (Nobody, 1999).", title=OPENING)
    first = _draft_file(seq, STORED_TITLE, [OPENING])
    before = first.read_bytes()
    refused = write_stage10(seq)
    assert refused["ok"] is False, refused
    assert refused.get("stored") is not True
    assert refused["refused"] == "references-cites"
    assert "nobody, 1999" in str(refused.get("reason") or "").casefold()
    assert first.read_bytes() == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    pointer = load_pointer(seq)
    assert pointer["current"] == "10"
    assert pointer["closed"] is False
    _proof("word-title-unlisted-refusal.txt", str(refused.get("reason") or "") + "\n")

    other = open_sequence(MODULE)
    rows = _rows()
    from essay_writer.research_packs import ship_4b

    note = "The opened file states the limit, and the year is the one stored on the list."
    ship_4b(other, rows, {row["id"]: note for row in rows})
    path = work_dir(other) / "citation-list.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    target = next(entry for entry in saved["entries"] if entry.get("year") == "2026")
    target["reference"] = ""
    path.write_text(json.dumps(saved), encoding="utf-8")
    missing_body = _cited_body()
    _plant(other, missing_body, title=OPENING)
    other_first = _draft_file(other, STORED_TITLE, [OPENING])
    other_before = other_first.read_bytes()
    missing = write_stage10(other)
    assert missing["ok"] is False, missing
    assert missing["refused"] == "references-cites"
    assert missing.get("stored") is not True
    assert "keith, 2026" in str(missing.get("reason") or "").casefold()
    assert other_first.read_bytes() == other_before
    assert not list((work_dir(other) / "output").rglob("*-final.docx"))
    assert first.read_bytes() == before
    _proof("word-title-missing-line-refusal.txt", str(missing.get("reason") or "") + "\n")
    assert workspace is not None


def test_findings_heading_stays_overall_judgement(workspace, tmp_path):
    """AC-title-7: A findings Word file a student would open still uses the heading “Overall judgement”, and stays free of “North-star judgement”, “north-star”, “Critical note”, and model names."""
    seq = open_sequence(MODULE)
    house = "\n".join(
        [
            "North-star judgement",
            OPENING,
            "Critical note: " + HOUSE_MODEL,
            "The draft does the assignment.",
        ]
    )
    written = write_findings_note(seq, house, documents=tmp_path)
    assert written["wrote"] is True, written
    path = tmp_path / module_code(seq) / f"{module_code(seq)}-findings.docx"
    text = _docx_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[0] == "Findings"
    assert lines[1] == "Overall judgement"
    assert _leaked(text) == []
    assert _assert_short_title(path, banned=OPENING) in {"", path.stem}
    _proof("word-title-findings-lines.txt", "\n".join(lines[:6]) + "\n")
    assert workspace is not None


def test_the_word_write_sets_a_short_title_after_the_citation_check(
    workspace, monkeypatch, tmp_path
):
    """AC-span-1: After the last-step citation check passes, the Word write must set a short safe document title and finish the file. A long first paragraph must not stop that write."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    body = _listed(seq)
    assert cite_reference_gaps([], [{"heading": "One decision", "body": body}], seq) == []
    _plant(seq, body, title=OPENING)
    _draft_file(seq, STORED_TITLE, [OPENING])
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    title = _assert_short_title(final, banned=OPENING)
    assert title == STORED_TITLE
    assert final.is_file()
    assert workspace is not None


def test_public_wording_covers_cursor_and_grok_build(workspace):
    """AC-public-1: Public wording only in the repo, commits, and pull request. Cursor and Grok Build share the same title rule, or a residual is named. Opaque deny-list test ids. Build covered."""
    from essay_writer.word import _word_document_title, document_title

    for stage in ("6", "9", "10"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
    assert "core_properties.title" not in inspect.getsource(cursor_stage_launch)
    assert "core_properties.title" not in inspect.getsource(stage_launch)
    assert "document_title(" in inspect.getsource(_word_document_title)
    assert "_word_document_title(" in inspect.getsource(write_docx)
    assert "document_title(" in inspect.getsource(write_first_draft_word)
    version = REPO.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in version
    init = REPO.joinpath("src/essay_writer/__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{__version__}"' in init
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_stage10_close_writes_the_final_when_the_opening_is_long": "AC-title-1",
        "test_the_live_opening_does_not_raise_the_title_limit": "AC-title-2",
        "test_the_final_document_title_is_the_short_title_already_stored": "AC-title-3",
        "test_the_final_keeps_the_draft_wording": "AC-title-4",
        "test_sibling_word_writes_survive_a_long_opening": "AC-title-5",
        "test_an_off_list_cite_and_a_missing_line_are_still_refused": "AC-title-6",
        "test_findings_heading_stays_overall_judgement": "AC-title-7",
        "test_the_word_write_sets_a_short_title_after_the_citation_check": "AC-span-1",
        "test_public_wording_covers_cursor_and_grok_build": "AC-public-1",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert source.count(f'"""{ident}:') == 1
    chosen = document_title(STORED_TITLE, OPENING, fallback=STORED_TITLE, opening=OPENING)
    assert chosen == STORED_TITLE
    assert len(chosen) <= LIMIT
    missed = document_title("", OPENING, fallback=STORED_TITLE, opening=OPENING)
    assert missed == STORED_TITLE
    assert workspace is not None
