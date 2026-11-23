"""Stage 10 final Word file: the essay opening appears once, after any short cover.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. Opaque ids name a deny-list hit. The phrases
themselves are not parametrize labels.

Sibling Word writes, mapped before the cover change:

- write_docx: stages 6, 7, 9, and the stage 10 final. The cover is written
  before the essay. This is the write that repeated the opening above the cover.
- write_first_draft_word: the first-draft file. Essay paragraphs only, no cover.
- write_findings_note: the findings file a student opens.
- write_annotation_docx: the annotated bibliography.
- write_critical_review_docx: a source review.
- downloads._save_docx: the download list.
- late_chain._write_comments: the comments file copied with the final.
- projects._rewrite_docx: a copied Word file whose properties are updated.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from docx import Document
from helpers import open_sequence, picked
from test_stage10_close_and_findings import _leaked
from test_word_references_4a import NUMBER, _park_stage10
from test_word_title_limit import (
    LIMIT,
    MODULE,
    OPENING,
    STORED_TITLE,
    _brief,
    _rows,
)

from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import stage_launch
from essay_writer.citation_list import list_written, load_citation_list, short_in_text
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.downloads import _save_docx
from essay_writer.late_chain import _write_comments, write_stage10
from essay_writer.paths import module_code, work_dir
from essay_writer.projects import _rewrite_docx
from essay_writer.research_packs import ship_4b, write_annotation_docx
from essay_writer.specialists.eqr import NORTH_STAR, write_findings_note
from essay_writer.stage_llm import HOUSE_MODEL
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path, blank_pointer, load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.word import (
    cover_lines,
    write_critical_review_docx,
    write_docx,
    write_first_draft_word,
)

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")


def _proof(name: str, payload: str | bytes) -> None:
    if not ARTIFACTS.is_dir():
        return
    target = ARTIFACTS / name
    if isinstance(payload, bytes):
        target.write_bytes(payload)
        return
    target.write_text(payload, encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def _paragraphs(path: Path) -> list[str]:
    return [paragraph.text for paragraph in Document(str(path)).paragraphs]


def _title_of(path: Path) -> str:
    title = Document(str(path)).core_properties.title
    return title if isinstance(title, str) else ""


def _final_file(seq: str) -> Path:
    found = sorted((work_dir(seq) / "output").rglob("*-final.docx"))
    assert len(found) == 1, [str(path) for path in found]
    return found[0]


def _reference_lines(seq: str) -> list[str]:
    listed = load_citation_list(seq)
    return [
        str(entry.get("reference") or "").strip()
        for entry in listed["entries"]
        if str(entry.get("reference") or "").strip()
    ]


def _essay_paragraphs(seq: str) -> list[str]:
    cites = [short_in_text(row["author"], row["year"]) for row in _rows()]
    return [
        OPENING,
        f"The brief asks for an essay of about 2,000 words {cites[0]}.",
        f"The opened file states the limit {cites[1]}.",
    ]


def _clear_saved_pack(seq: str) -> None:
    state = load_state(seq)
    state.pop("saved_pack", None)
    save_state(seq, state)


def _write_live_draft(seq: str, paragraphs: list[str], *, title: str) -> Path:
    """First-draft file: essay paragraphs, a short document title, no cover line."""
    path = work_dir(seq) / "output" / f"{seq}.docx"
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.core_properties.title = title
    for line in paragraphs:
        document.add_paragraph(line)
    document.add_heading("References", level=1)
    for line in _reference_lines(seq):
        document.add_paragraph(line)
    document.save(str(path))
    return path


def _live_fixture(*, title: str) -> tuple[str, list[str], Path]:
    """The live leftover: a long opening and the short title ENVS5003HK-1."""
    seq = open_sequence(MODULE)
    _brief()
    remember_registration(seq, NUMBER)
    rows = _rows()
    delivered = ship_4b(
        seq,
        rows,
        {row["id"]: "The opened file states the limit." for row in rows},
    )
    assert delivered.get("wrote") is not False, delivered
    assert list_written(seq) is True
    paragraphs = _essay_paragraphs(seq)
    assert paragraphs[0].startswith("When is it fair to close a fishery")
    assert len(paragraphs[0]) > LIMIT
    _park_stage10(seq)
    _clear_saved_pack(seq)
    path = _write_live_draft(seq, paragraphs, title=title)
    assert _title_of(path) == title
    return seq, paragraphs, path


def _assert_opening_once(path: Path, draft: list[str], *, short: str) -> list[str]:
    """The opening is the first essay paragraph after the cover, and only there."""
    paragraphs = _paragraphs(path)
    flats = [_flat(text) for text in paragraphs]
    opening = _flat(draft[0])
    hits = [index for index, text in enumerate(flats) if text == opening]
    assert hits, paragraphs
    assert len(hits) == 1, paragraphs
    index = hits[0]
    assert short in flats[:index], paragraphs
    assert opening not in flats[:index]
    for line in draft:
        assert flats[:index].count(_flat(line)) == 0
    blanks = 0
    cursor = index - 1
    while cursor >= 0 and not paragraphs[cursor].strip():
        blanks += 1
        cursor -= 1
    assert blanks <= 1
    body: list[str] = []
    for text in flats[index:]:
        if text.casefold() == "references":
            break
        if text:
            body.append(text)
    assert body == [_flat(line) for line in draft]
    assert "references" in [text.casefold() for text in flats[index:]]
    return paragraphs


def test_stage10_close_writes_the_opening_once_after_the_cover(workspace, monkeypatch, tmp_path):
    """AC-cover-1: When the citation check already passes, Stage 10 writes a new final Word file whose name is not the first-draft name, stores the step, and can close. The essay opening paragraph appears only once in that file, as the first paragraph of the essay body after any short cover. It must not also appear above the cover line."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq, paragraphs, draft_path = _live_fixture(title=STORED_TITLE)
    assert seq == STORED_TITLE
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
    shown = _assert_opening_once(final, paragraphs, short=STORED_TITLE)
    _proof(
        "final-cover-close.json",
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
    _proof("final-cover-opening.docx", final.read_bytes())
    _proof(
        "final-cover-paragraphs.txt",
        "\n".join(f"{index:02d} {text}" for index, text in enumerate(shown)) + "\n",
    )
    assert workspace is not None


def test_the_live_opening_is_not_repeated_above_the_short_cover(workspace, monkeypatch, tmp_path):
    """AC-cover-2: A fixture that repeats the live leftover — a first-draft opening longer than 255 characters beginning “When is it fair to close a fishery…”, and a short document title ENVS5003HK-1 — must write a final file that does not place that opening once above a short cover line and again as the first essay paragraph."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq, paragraphs, _draft_path = _live_fixture(title=STORED_TITLE)
    assert seq == STORED_TITLE
    assert len(OPENING) == 620
    written = write_stage10(seq)
    assert written["ok"] is True, written
    assert written.get("pack_path") == "pack_from_docx"
    final = _final_file(seq)
    _assert_opening_once(final, paragraphs, short=STORED_TITLE)
    _proof("final-cover-live.docx", final.read_bytes())
    assert workspace is not None


def test_the_essay_after_the_cover_matches_the_first_draft(workspace, monkeypatch, tmp_path):
    """AC-cover-3: After any short cover line (and at most one blank paragraph after it), the essay paragraphs in the final Word file match the first-draft essay exactly once. A References section may follow with the citation-list lines. This cut does not change the essay wording to remove the leftover."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq, paragraphs, _draft_path = _live_fixture(title=STORED_TITLE)
    references = _reference_lines(seq)
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    shown = _assert_opening_once(final, paragraphs, short=STORED_TITLE)
    flats = [_flat(text) for text in shown]
    opening_at = flats.index(_flat(OPENING))
    assert OPENING not in "\n".join(flats[:opening_at])
    reference_at = next(
        index for index, text in enumerate(flats) if text.casefold() == "references"
    )
    assert reference_at > opening_at
    followed = flats[reference_at + 1 :]
    for line in references:
        assert _flat(line) in followed
    _proof(
        "final-cover-body.txt",
        "\n".join(paragraphs) + "\n---\n" + "\n".join(shown) + "\n",
    )
    assert workspace is not None


def test_the_final_document_title_stays_the_short_title(workspace, monkeypatch, tmp_path):
    """AC-cover-4: The final Word file’s document title remains the short title already on the first-draft Word file (for the live essay, ENVS5003HK-1). If no short title is stored, it is the assessment id or the file name without .docx. It is never the opening paragraph, and it is at most 255 characters."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq, _paragraphs, _draft_path = _live_fixture(title=STORED_TITLE)
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    title = _title_of(final)
    assert title == STORED_TITLE
    assert len(title) <= LIMIT
    assert title != OPENING
    assert not title.startswith("When is it fair to close a fishery")
    _proof("final-cover-title.txt", title + "\n")

    other, _other_paragraphs, _other_draft = _live_fixture(title="")
    assert _title_of(work_dir(other) / "output" / f"{other}.docx") == ""
    again = write_stage10(other)
    assert again["ok"] is True, again
    other_final = _final_file(other)
    fallback = _title_of(other_final)
    assert len(fallback) <= LIMIT
    assert fallback != OPENING
    assert fallback == other
    assert workspace is not None


def test_sibling_word_files_do_not_repeat_the_opening(workspace, tmp_path):
    """AC-cover-5: Sibling Word writes are mapped before the first patch. First-draft, findings, annotation, and any other student-facing Word file this product writes must not gain this duplicated-opening leftover. The first-draft Word file stays the essay paragraphs only, with no opening copied above a cover."""
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
    first_lines = [text for text in _paragraphs(first_path) if text.strip()]
    assert first_lines == [OPENING]
    assert first_lines.count(OPENING) == 1

    findings = "\n".join([NORTH_STAR, OPENING, "The draft does the assignment."])
    written = write_findings_note(seq, findings, documents=tmp_path)
    assert written["wrote"] is True, written
    findings_path = tmp_path / module_code(seq) / f"{module_code(seq)}-findings.docx"
    findings_lines = [text for text in _paragraphs(findings_path) if text.strip()]
    assert findings_lines[0] == "Findings"
    assert findings_lines.count(OPENING) == 1
    assert findings_lines[0] != OPENING

    annotation = work_dir(seq) / "output" / "annotation.docx"
    write_annotation_docx(
        annotation,
        [{"parts": [(OPENING, False)], "paragraph": OPENING}],
        empty_note="None.",
    )
    annotation_lines = [text for text in _paragraphs(annotation) if text.strip()]
    assert annotation_lines.count(OPENING) == 1

    review = work_dir(seq) / "output" / "reviews" / "plaice.docx"
    write_critical_review_docx(review, OPENING)
    assert [text for text in _paragraphs(review) if text.strip()].count(OPENING) == 1

    downloads = work_dir(seq) / "output" / "download-list.docx"
    _save_docx(
        downloads,
        [
            ("Sources to download", True, False),
            (OPENING, False, False),
        ],
    )
    download_lines = [text for text in _paragraphs(downloads) if text.strip()]
    assert download_lines[0] == "Sources to download"
    assert download_lines.count(OPENING) == 1

    comments = work_dir(seq) / "output" / f"{module_code(seq)}-comments.docx"
    state = load_state(seq)
    state["eqr"] = {
        "9": {"seat": "reviewer", "word_opened": True, "findings": OPENING, "verdict": "PASS"}
    }
    save_state(seq, state)
    _write_comments(seq, comments)
    assert [text for text in _paragraphs(comments) if text.strip()].count(OPENING) == 1

    report = {
        "sources": [],
        "sections": [{"heading": OPENING, "body": "The opened file states the limit."}],
        "figures": [],
        "tables": [],
    }
    pack = {
        "essay_id": seq,
        "title": OPENING,
        "assessment": OPENING,
        "referencing": "harvard",
        "sections": report["sections"],
        "sources": [],
    }
    report["cover"] = cover_lines(seq, pack, report)
    final_like = work_dir(seq) / "output" / "sibling-final.docx"
    write_docx(seq, pack, report, final_like)
    sibling = [text for text in _paragraphs(final_like) if text.strip()]
    assert sibling.count(OPENING) == 1
    assert sibling[0] != OPENING

    copied = work_dir(seq) / "output" / "copied.docx"
    document = Document()
    document.core_properties.title = STORED_TITLE
    document.add_paragraph(OPENING)
    document.add_paragraph("A later LIMIT stays in the essay.")
    copied.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(copied))
    _rewrite_docx(copied, "LIMIT", "WORD")
    copied_lines = [text for text in _paragraphs(copied) if text.strip()]
    assert copied_lines.count(OPENING) == 1
    assert copied_lines[0] == OPENING
    assert workspace is not None


def test_an_off_list_cite_and_a_missing_line_are_still_refused(workspace):
    """AC-cover-6: A citation in the text that is not on the list, such as (Nobody, 1999), and a genuinely missing reference line, are still refused. The step is not stored, no final Word file is written from that refusal, and a good first-draft Word file is not overwritten."""
    seq, paragraphs, first = _live_fixture(title=STORED_TITLE)
    extra = paragraphs + ["An unlisted paper is not added (Nobody, 1999)."]
    _write_live_draft(seq, extra, title=STORED_TITLE)
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
    _proof("final-cover-unlisted-refusal.txt", str(refused.get("reason") or "") + "\n")

    other, _other_paragraphs, other_first = _live_fixture(title=STORED_TITLE)
    path = work_dir(other) / "citation-list.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    target = next(entry for entry in saved["entries"] if entry.get("year") == "2026")
    target["reference"] = ""
    path.write_text(json.dumps(saved), encoding="utf-8")
    other_before = other_first.read_bytes()
    missing = write_stage10(other)
    assert missing["ok"] is False, missing
    assert missing["refused"] == "references-cites"
    assert missing.get("stored") is not True
    assert "keith, 2026" in str(missing.get("reason") or "").casefold()
    assert other_first.read_bytes() == other_before
    assert not list((work_dir(other) / "output").rglob("*-final.docx"))
    assert first.read_bytes() == before
    _proof("final-cover-missing-line-refusal.txt", str(missing.get("reason") or "") + "\n")
    assert workspace is not None


def test_findings_heading_stays_overall_judgement(workspace, tmp_path):
    """AC-cover-7: A findings Word file a student would open still uses the heading “Overall judgement”, and stays free of “North-star judgement”, “north-star”, “Critical note”, and model names."""
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
    lines = [line.strip() for line in _paragraphs(path) if line.strip()]
    text = "\n".join(lines)
    assert lines[0] == "Findings"
    assert lines[1] == "Overall judgement"
    assert _leaked(text) == []
    _proof("final-cover-findings-lines.txt", "\n".join(lines[:6]) + "\n")
    assert workspace is not None


def test_the_final_write_does_not_prepend_the_opening(workspace, monkeypatch, tmp_path):
    """AC-span-1: After the last-step citation check passes, the final Word write may add a short cover and a References section, but must not prepend a copy of the opening paragraph above that cover."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq, paragraphs, _draft_path = _live_fixture(title=STORED_TITLE)
    state = load_state(seq)
    state["saved_pack"] = {
        "essay_id": seq,
        "title": OPENING,
        "assessment": OPENING,
        "referencing": "harvard",
        "conclusion": "noted",
        "references_markdown": "\n".join(_reference_lines(seq)),
        "sections": [
            {"heading": paragraphs[0], "body": "\n".join(paragraphs[1:])},
        ],
    }
    save_state(seq, state)
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    _assert_opening_once(final, paragraphs, short=STORED_TITLE)
    flats = [_flat(text) for text in _paragraphs(final)]
    assert "references" in [text.casefold() for text in flats]
    assert any(text == STORED_TITLE for text in flats)
    assert workspace is not None


def test_public_wording_covers_cursor_and_grok_build(workspace):
    """AC-public-1: Public wording only in the repo, commits, and pull request. Cursor and Grok Build share the same final-file body rule, or a residual is named. Opaque deny-list test ids. Build covered."""
    from essay_writer.word import _cover_without_opening

    for stage in ("6", "9", "10"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["rules"] == build["settings"]["rules"]
    assert "_cover_without_opening(" in inspect.getsource(cover_lines)
    assert "_cover_without_opening(" in inspect.getsource(write_docx)
    version = REPO.joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.9.15"' in version
    init = REPO.joinpath("src/essay_writer/__init__.py").read_text(encoding="utf-8")
    assert '__version__ = "0.9.15"' in init
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("@pytest.mark." + "parametrize") not in source
    seated = {
        "test_stage10_close_writes_the_opening_once_after_the_cover": "AC-cover-1",
        "test_the_live_opening_is_not_repeated_above_the_short_cover": "AC-cover-2",
        "test_the_essay_after_the_cover_matches_the_first_draft": "AC-cover-3",
        "test_the_final_document_title_stays_the_short_title": "AC-cover-4",
        "test_sibling_word_files_do_not_repeat_the_opening": "AC-cover-5",
        "test_an_off_list_cite_and_a_missing_line_are_still_refused": "AC-cover-6",
        "test_findings_heading_stays_overall_judgement": "AC-cover-7",
        "test_the_final_write_does_not_prepend_the_opening": "AC-span-1",
        "test_public_wording_covers_cursor_and_grok_build": "AC-public-1",
    }
    for name, ident in seated.items():
        doc = inspect.getdoc(globals()[name]) or ""
        assert doc.startswith(ident), doc
        assert source.count(f'"""{ident}:') == 1
    kept = _cover_without_opening(
        [OPENING, STORED_TITLE],
        [{"heading": OPENING, "body": "The opened file states the limit."}],
    )
    assert kept == [STORED_TITLE]
    assert workspace is not None
