"""#26 publication year is the opened PDF's own cite line.

The same rule feeds cite looks, 4a and 4b lines, and the reference list.
It is not a stage rule and it does not read the file's modified time.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from helpers import ESSAY, open_sequence

from essay_writer.cite_open import cite_look, open_for_citation
from essay_writer.paths import work_dir
from essay_writer.pdf_year import apply_citation_year, citation_year, publication_year
from essay_writer.research_packs import ship_4a, ship_4b
from essay_writer.stage_track import essay_stage
from essay_writer.textutil import reference_line

REPO = Path(__file__).resolve().parents[1]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_lines(lines: list[str]) -> bytes:
    commands = " ".join(f"({_escape(line)}) Tj" for line in lines)
    stream = f"BT /F1 12 Tf 72 720 Td {commands} ET".encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Length "
        + str(len(stream)).encode()
        + b">>stream\n"
        + stream
        + b"\nendstream\nendobj\ntrailer<<>>\n%%EOF\n"
    )


def _docx(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _look_body(seq: str, stage: str) -> str:
    note = (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")
    _rules, heading, body = note.partition("## Working look")
    if heading != "## Working look":
        _rules, heading, body = note.partition("## Final look")
    assert heading in {"## Working look", "## Final look"}
    return body


def _plant(seq: str, name: str, **source: object) -> dict:
    from essay_writer.state import load_state, save_state

    row = {
        "id": "src-author",
        "author": "Author, A.",
        "year": "1901",
        "title": "Ports and crude",
        "locator": f"uploads/{ESSAY}/{name}",
    }
    row.update(source)
    state = load_state(seq)
    research = state.setdefault("research", {})
    research["summary"] = {"sources": [row]}
    save_state(seq, state)
    return row


def test_ac1_own_cite_year_beats_a_cited_work(workspace):
    """Author (2022) is the cite line. (1901) in an earlier header string is not."""
    cited_first = [
        "Lee (1901) argued an older claim in the header.",
        "Author (2022)",
        "Ports and crude",
    ]
    assert publication_year("\n".join(cited_first)) == "2022"
    please = "\n".join(
        [
            "Lee (1901) argued an older claim in the header.",
            "Please cite this article as: Author, A. (2022). Ports and crude.",
        ]
    )
    assert publication_year(please) == "2022"

    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "author-2022.pdf"
    path.write_bytes(_pdf_lines(cited_first))
    opened = open_for_citation(path)
    assert opened.year == "2022"
    assert citation_year(path) == "2022"

    seq = open_sequence()
    source = _plant(seq, path.name)
    narrative = "Author (1901) sets the corridor limit for this task."
    other = "Ng (1999) keeps a different claim about the same corridor."
    assert cite_look(seq, narrative) == "Author (2022) sets the corridor limit for this task."
    assert cite_look(seq, "(Author, 1901) remains in the note.") == "(Author, 2022) remains in the note."
    assert cite_look(seq, other) == other

    look = f"{narrative} {other}"
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["ok"] is True, draft
    saved = _look_body(seq, "1")
    assert "Author (2022)" in saved
    assert "1901" not in saved
    assert "Ng (1999)" in saved

    ship_4a(seq, [source], {})
    annotation = _docx(workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / "annotation.docx")
    assert "(2022)" in annotation
    assert "(1901)" not in annotation

    reviewed = ship_4b(seq, [source], None)
    review = workspace / reviewed["reviews"][0]["markdown_path"]
    review_text = review.read_text(encoding="utf-8")
    assert "(2022)" in review_text
    assert "(1901)" not in review_text

    line = reference_line(source)
    assert "(2022)" in line
    assert "(1901)" not in line

    stage_src = (REPO / "src" / "essay_writer" / "stage_track.py").read_text(encoding="utf-8")
    cite_at = stage_src.index("text = cite_look(essay_id, text)")
    assert 'if stage == "5"' not in stage_src[cite_at - 500 : cite_at]


def test_ac2_cite_line_without_a_year_omits_the_year(workspace):
    """No year on the cite line. A cited year and a 2024 mtime stay off the citation."""
    lines = [
        "Please cite this article as: Author, A. Ports and crude.",
        "Lee (1901) argued an older claim in the header.",
    ]
    assert publication_year("\n".join(lines)) is None
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "author-undated.pdf"
    path.write_bytes(_pdf_lines(lines))
    stamped = datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamped, stamped))
    assert citation_year(path) is None
    assert open_for_citation(path).year is None
    dropped = apply_citation_year(
        {"author": "Author, A.", "year": "2024", "title": "Ports and crude"},
        path,
    )
    assert "year" not in dropped

    seq = open_sequence()
    source = _plant(seq, path.name, year="2024")
    ship_4a(seq, [source], {})
    annotation = _docx(workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / "annotation.docx")
    assert "Author, A." in annotation
    assert "(2024)" not in annotation
    assert "(1901)" not in annotation
    line = reference_line(source)
    assert "Author, A." in line
    assert "(2024)" not in line
    assert "(1901)" not in line
    year_source = (REPO / "src" / "essay_writer" / "pdf_year.py").read_text(encoding="utf-8")
    assert "st_mtime" not in year_source


def test_ac3_another_authors_year_is_left_alone(workspace):
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "author-2022.pdf"
    path.write_bytes(
        _pdf_lines(
            [
                "Lee (1901) argued an older claim in the header.",
                "Author (2022)",
                "Ports and crude",
            ]
        )
    )
    seq = open_sequence()
    _plant(seq, path.name)
    other = "Ng (1999) keeps a different claim about the same corridor."
    assert cite_look(seq, other) == other
    draft = essay_stage(seq, "1", "draft", other)
    assert draft["ok"] is True, draft
    saved = _look_body(seq, "1")
    assert other in saved
    assert "2022" not in saved
