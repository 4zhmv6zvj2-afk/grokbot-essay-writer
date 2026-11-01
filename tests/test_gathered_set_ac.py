"""Batch 4 gathered-set gate. Stable ids: AC1, AC2, AC3, AC-NT6.

One gate for every writing type that gathers sources. Same opened text
collapses to one work. Identical annotation paragraphs are refused.
A kept source ties to an entry name when the assignment record has
entry names, and otherwise to the assignment ask.
"""

import zipfile
from pathlib import Path

from docx import Document
from helpers import CLARIFY_OPEN, open_sequence, write_upload

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import (
    FINDINGS_NONE,
    register_mapping,
    unregister_mapping,
)
from essay_writer.canon import file_sha256
from essay_writer.diary import entry_count, named_entries, title_page_spec
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.state import load_state

QUOTE = "The Strait handles a large share of flows."
SAME = (
    "Smith, J. (2020) Chokepoints and crude.\n"
    f"{QUOTE}\n"
)
KEPT_NOTE = (
    "The paper measured the share of flows and reported it. "
    "The finding is that share of flows. "
    "It helps this assignment by naming the share."
)
DROPPED_NOTE = (
    "The second file repeats the same opened text and must not be a second paper. "
    "That copy is not kept. "
    "The bibliography lists one work."
)
SHARED_NOTE = (
    "The paper measured one limit and reported it in the file. "
    "The finding is that measured limit. "
    "It helps this assignment by supplying the limit."
)
DIARY = """
Assignment title: Individual reflective diary

Assignment task: Write two entries. Each entry names one decision and analyses it with theory.

Entries
1. Quay watch
2. Tide log
"""
ESSAY = """
Genre: essay
Question: How do chokepoints constrain the corridor?

Entries
1. Quay watch
2. Tide log
"""
FIELDNOTE = """
Genre: fieldnote

Question: What did the quay show on that watch?

Entries
1. Quay watch
2. Tide log
"""
UNTIED = (
    "Adey, P. (2021) Enrolment notes.\n"
    "The office counted the forms on the desk.\n"
)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(text: str, mark: bytes) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET".encode()
    content = (
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream"
    )
    page = b"<< /Type /Page /Parent 2 0 R /Contents 3 0 R >>"
    chunks = [
        b"%PDF-1.4\n%" + mark + b"\n",
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [4 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n" + content + b"\nendobj\n",
        b"4 0 obj\n" + page + b"\nendobj\n",
        b"%%EOF\n",
    ]
    return b"".join(chunks)


def _brief(workspace: Path, module: str, text: str) -> None:
    folder = workspace / "Essay-writer" / module
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _upload_pdf(workspace: Path, module: str, name: str, text: str, mark: bytes) -> Path:
    folder = workspace / "uploads" / module
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(_pdf(text, mark))
    return path


def _row(module: str, name: str, source_id: str, **extra: object) -> dict:
    item = {
        "id": source_id,
        "origin": "upload",
        "locator": f"uploads/{module}/{name}",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "quote": QUOTE,
    }
    item.update(extra)
    return item


def _docx(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _map_fieldnote(text: str, *, has_scheme: bool) -> dict:
    names = named_entries(text)
    count = entry_count(text)
    return {
        "named_entries": names,
        "named_by_brief": bool(names),
        "part_count": count,
        "unnamed_note": None,
        "lock": "notes",
        "title_page": title_page_spec(text),
        "findings_opening": FINDINGS_NONE,
    }


def test_ac1_same_text_pdfs_with_different_hashes_keep_one(workspace):
    """AC1. Two PDFs, same opened text, different file hashes. One work remains."""
    module = "DUP9001HK"
    first = _upload_pdf(workspace, module, "copy-a.pdf", SAME, b"copy-a")
    second = _upload_pdf(workspace, module, "copy-b.pdf", SAME, b"copy-b")
    assert file_sha256(first) != file_sha256(second)
    seq = open_sequence(module)
    rows = [
        _row(module, "copy-a.pdf", "src-1", annotation=KEPT_NOTE),
        _row(module, "copy-b.pdf", "src-2", annotation=DROPPED_NOTE),
    ]
    draft = essay_research_summary(seq, "chokepoints", "draft", rows)
    assert draft["ok"] is True, draft
    assert [source["id"] for source in draft["sources"]] == ["src-1"]
    assert draft["sources"][0]["locator"].endswith("copy-a.pdf")
    saved = essay_research_summary(seq, "chokepoints", "confirm", rows)
    assert saved["stored"] is True, saved
    assert [source["id"] for source in saved["sources"]] == ["src-1"]
    annotation = _docx(work_dir(seq) / "output" / "annotation.docx")
    assert KEPT_NOTE.split(". ")[0] in annotation
    assert "must not be a second paper" not in annotation
    papers = zipfile.ZipFile(work_dir(seq) / "output" / "papers.zip")
    assert papers.namelist() == ["copy-a.pdf"]

    reviews = [
        {"paper_id": "src-1", "markdown": f'The paper reports the share. "{QUOTE}"'},
        {"paper_id": "src-2", "markdown": "This duplicate note must stay out of the zip."},
    ]
    full = essay_research_full(
        seq,
        "chokepoints",
        "draft",
        rows,
        clarify_context=CLARIFY_OPEN,
        reviews=reviews,
    )
    assert full["ok"] is True, full
    assert [source["id"] for source in full["sources"]] == ["src-1"]
    confirmed = essay_research_full(
        seq,
        "chokepoints",
        "confirm",
        rows,
        clarify_context=CLARIFY_OPEN,
        reviews=reviews,
    )
    assert confirmed["stored"] is True, confirmed
    archive = zipfile.ZipFile(work_dir(seq) / "output" / "critical-reviews.zip")
    assert archive.namelist() == ["src-1.docx"]
    assert not any(name.endswith(".md") for name in archive.namelist())


def test_same_doi_keeps_one_work(workspace):
    """Same DOI is one work even when the opened text differs."""
    module = "DOI9001HK"
    write_upload(
        workspace,
        essay_id=module,
        name="first.md",
        text=(
            "Nash, R. (2020) First copy.\n"
            "The first copy states the result.\n"
            "doi:10.1000/same-work\n"
        ),
    )
    write_upload(
        workspace,
        essay_id=module,
        name="second.md",
        text=(
            "Nash, R. (2020) Second copy.\n"
            "The second copy states another sentence.\n"
            "https://doi.org/10.1000/same-work\n"
        ),
    )
    seq = open_sequence(module)
    rows = [
        {
            "id": "src-1",
            "origin": "upload",
            "locator": f"uploads/{module}/first.md",
            "author": "Nash, R.",
            "year": "2020",
            "title": "First copy",
            "doi": "10.1000/same-work",
            "quote": "The first copy states the result.",
        },
        {
            "id": "src-2",
            "origin": "upload",
            "locator": f"uploads/{module}/second.md",
            "author": "Nash, R.",
            "year": "2020",
            "title": "Second copy",
            "doi": "https://doi.org/10.1000/same-work",
            "quote": "The second copy states another sentence.",
        },
    ]
    draft = essay_research_summary(seq, "copies", "draft", rows)
    assert draft["ok"] is True, draft
    assert [source["id"] for source in draft["sources"]] == ["src-1"]


def test_ac2_identical_annotation_paragraphs_are_refused(workspace):
    """AC2. Three different files with one shared annotation paragraph are refused."""
    module = "ANN9001HK"
    bodies = (
        ("north.pdf", "src-1", "Smith, J.", "2020", "North gauge", "The north gauge measured eleven units."),
        ("south.pdf", "src-2", "Lee, A.", "2019", "South gauge", "The south gauge measured twenty units."),
        ("east.pdf", "src-3", "Ng, K.", "2018", "East gauge", "The east gauge measured thirty units."),
    )
    rows = []
    for name, source_id, author, year, title, sentence in bodies:
        text = f"{author} ({year}) {title}.\n{sentence}\n"
        _upload_pdf(workspace, module, name, text, name.encode())
        rows.append(
            {
                "id": source_id,
                "origin": "upload",
                "locator": f"uploads/{module}/{name}",
                "author": author,
                "year": year,
                "title": title,
                "quote": sentence,
                "annotation": SHARED_NOTE,
            }
        )
    seq = open_sequence(module)
    draft = essay_research_summary(seq, "gauges", "draft", rows)
    assert draft["ok"] is False, draft
    assert draft["refused"] == "gathered-set"
    assert "same annotation paragraph" in draft["reason"]
    assert draft["stored"] is False
    assert draft["wrote"] is False
    confirmed = essay_research_summary(seq, "gauges", "confirm", rows)
    assert confirmed["ok"] is False, confirmed
    assert confirmed["refused"] == "gathered-set"
    assert confirmed["stored"] is False
    assert not (work_dir(seq) / "output" / "annotation.docx").exists()
    assert load_state(seq)["research"]["summary"] is None

    own = (
        "The north gauge measured eleven units and reported them. "
        "The finding is those eleven units. "
        'The paper says "The north gauge measured eleven units."'
    )
    south = (
        "The south gauge measured twenty units and reported them. "
        "The finding is those twenty units. "
        'The paper says "The south gauge measured twenty units."'
    )
    east = (
        "The east gauge measured thirty units and reported them. "
        "The finding is those thirty units. "
        'The paper says "The east gauge measured thirty units."'
    )
    for row, note in zip(rows, (own, south, east), strict=False):
        row["annotation"] = note
    distinct = essay_research_summary(seq, "gauges", "draft", rows)
    assert distinct["ok"] is True, distinct
    assert [source["id"] for source in distinct["sources"]] == ["src-1", "src-2", "src-3"]


def test_ac3_source_untied_to_any_entry_is_refused(workspace):
    """AC3. A file that meets no named entry is refused."""
    module = "ENT9001HK"
    _brief(workspace, module, DIARY)
    write_upload(workspace, essay_id=module, name="ade.md", text=UNTIED)
    seq = open_sequence(module)
    record = read_assignment(seq)
    assert record["named_entries"] == ["Quay watch", "Tide log"]
    row = {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{module}/ade.md",
        "author": "Adey, P.",
        "year": "2021",
        "title": "Enrolment notes",
        "quote": "The office counted the forms on the desk.",
    }
    draft = essay_research_summary(seq, "entries", "draft", [row])
    assert draft["ok"] is False, draft
    assert draft["refused"] == "gathered-set"
    assert "not tied to an entry" in draft["reason"]
    assert draft["stored"] is False
    assert draft["wrote"] is False
    confirmed = essay_research_summary(seq, "entries", "confirm", [row])
    assert confirmed["ok"] is False
    assert confirmed["refused"] == "gathered-set"
    assert load_state(seq)["research"]["summary"] is None


def test_ac_nt6_entry_tie_or_ask_for_a_third_writing_type(workspace):
    """AC-NT6. Entry names tie the source. No names tie it to the ask.

    A third writing type uses the same gate. An essay record with no
    entry names does not start requiring those names.
    """
    register_mapping("fieldnote", _map_fieldnote)
    try:
        module = "FLD9001HK"
        _brief(workspace, module, FIELDNOTE)
        write_upload(
            workspace,
            essay_id=module,
            name="quay.md",
            text=(
                "Adey, P. (2021) Quay watch notes.\n"
                "The Quay watch recorded the crane stop.\n"
            ),
        )
        seq = open_sequence(module)
        record = read_assignment(seq)
        assert record["writing_type"] == "fieldnote"
        assert record["named_entries"] == ["Quay watch", "Tide log"]
        row = {
            "id": "src-1",
            "origin": "upload",
            "locator": f"uploads/{module}/quay.md",
            "author": "Adey, P.",
            "year": "2021",
            "title": "Quay watch notes",
            "quote": "The Quay watch recorded the crane stop.",
            "annotation": (
                "The note records the Quay watch and the crane stop. "
                "The finding is that stop. "
                "It helps the Quay watch entry by naming the stop."
            ),
        }
        draft = essay_research_summary(seq, "quay", "draft", [row])
        assert draft["ok"] is True, draft
        assert draft["sources"][0]["tied_to"] == "Quay watch"
        saved = essay_research_summary(seq, "quay", "confirm", [row])
        assert saved["stored"] is True, saved
        assert saved["sources"][0]["tied_to"] == "Quay watch"
    finally:
        unregister_mapping("fieldnote")

    essay_module = "ASK9001HK"
    _brief(workspace, essay_module, ESSAY)
    write_upload(workspace, essay_id=essay_module, name="smith.md")
    essay = open_sequence(essay_module)
    essay_record = read_assignment(essay)
    assert essay_record["writing_type"] == "essay"
    assert essay_record["named_entries"] == []
    assert essay_record["question"]
    from helpers import source

    kept = essay_research_summary(essay, "chokepoints", "draft", [source(essay_module)])
    assert kept["ok"] is True, kept
    assert kept["sources"][0]["tied_to"] == essay_record["question"]
    assert "Quay watch" not in kept["sources"][0]["tied_to"]

    write_upload(workspace, essay_id=essay_module, name="ade.md", text=UNTIED)
    missed = {
        "id": "src-2",
        "origin": "upload",
        "locator": f"uploads/{essay_module}/ade.md",
        "author": "Adey, P.",
        "year": "2021",
        "title": "Enrolment notes",
        "quote": "The office counted the forms on the desk.",
    }
    refused = essay_research_summary(essay, "chokepoints", "draft", [missed])
    assert refused["ok"] is False, refused
    assert refused["refused"] == "gathered-set"
    assert "assignment ask" in refused["reason"]
