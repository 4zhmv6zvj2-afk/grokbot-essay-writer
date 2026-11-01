"""Harvard reference list in Word: journal italics and looked-up pages.

essay-ref-a1: saved references_markdown italicises the journal title.
essay-ref-a2: gathered parts on the first write italicise the journal title.
essay-ref-a3: a look-up page range is still pp. start-end when the PDF has no lone page lines.
essay-ref-a4: a look-up page value that is an article id is stored and printed as an article number.
essay-ref-a5: with neither a page range nor an article number, pages stay blank.
essay-ref-a6: gather keeps a single page only from a matching look-up; a bare page stays blank.
essay-ref-a7: gather keeps a DOI only from a matching look-up.
essay-ref-a8: a web page with a publisher or place still prints its access date.
"""

import inspect

from docx import Document
from helpers import ESSAY, open_sequence

from essay_writer.build_office import stage_launch
from essay_writer.cite_open import apply_opened_citation
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.invent import gather_source
from essay_writer.late_chain import write_stage10
from essay_writer.resolvers import crossref_lookup
from essay_writer.state import load_state, save_state
from essay_writer.textutil import reference_line
from essay_writer.word import essay_pack_render_word, write_docx

JOURNAL = "Journal of Practice"
SAVED_LINE = (
    "Qin, Y. (2021) 'Stakeholder mapping', Journal of Practice, 8(1), pp. 2-9. "
    "Available at: doi:10.1000/stake."
)
SECOND_LINE = "Jones, A. (2019) 'Second line', Practice, 1(1), pp. 1-2."
QUOTE = "The Strait handles a large share of flows."
CONTAINER = "Journal of Transport Geography"
ARTICLE_ID = "104567"
PAGE_RANGE = "101-112"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET".encode()
    content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>",
        4: content,
    }
    chunks = [b"%PDF-1.4\n"]
    for number in sorted(objects):
        chunks.append(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    chunks.append(b"%%EOF\n")
    return b"".join(chunks)


def _paper(workspace, name: str) -> str:
    """One PDF with no lone 1–4 digit page lines and no article-number line."""
    text = "\n".join(
        [
            "Smith, J. (2020) Chokepoints and crude",
            QUOTE,
            f"Published in {CONTAINER}.",
        ]
    )
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(_pdf(text))
    return f"uploads/{ESSAY}/{name}"


def _plant_lookup(seq: str, locator: str, pages: str, **extra: object) -> None:
    source = {
        "id": "src-1",
        "origin": "upload",
        "locator": locator,
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "container": CONTAINER,
        "pages": pages,
        "field_sources": {"pages": "lookup"},
    }
    for field, value in extra.items():
        source[field] = value
        source["field_sources"][field] = "lookup"
    state = load_state(seq)
    state["research"] = {"summary": {"sources": [source]}, "full": None}
    save_state(seq, state)


def _raw(locator: str, **extra: object) -> dict:
    row = {
        "id": "src-1",
        "origin": "upload",
        "locator": locator,
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "container": CONTAINER,
        "quote": QUOTE,
    }
    row.update(extra)
    return row


def _write(seq: str, path, sources: list, *, markdown: str | None = None) -> None:
    pack = {"assessment": "Individual report", "referencing": "harvard"}
    if markdown is not None:
        pack["references_markdown"] = markdown
    write_docx(
        seq,
        pack,
        {
            "title": "Chokepoints on the corridor",
            "word_count": {"counted": 12},
            "sections": [{"heading": "Introduction", "body": "The corridor is narrow."}],
            "figures": [],
            "tables": [],
            "sources": sources,
        },
        path,
    )


def _paragraph(path, needle: str):
    return next(paragraph for paragraph in Document(str(path)).paragraphs if needle in paragraph.text)


def _italic_journal(path, journal: str, *, marker: str | None = None) -> list[str]:
    paragraph = _paragraph(path, marker or journal)
    assert len(paragraph.runs) > 1
    assert not any(
        not run.italic and (run.text or "").strip() == paragraph.text.strip() for run in paragraph.runs
    )
    return [run.text for run in paragraph.runs if run.italic and (run.text or "") == journal]


def test_essay_ref_a1_saved_lines_italicise_journal_title(workspace, tmp_path):
    """essay-ref-a1. Saved references_markdown is not one roman run."""
    seq = open_sequence()
    target = tmp_path / "saved.docx"
    _write(seq, target, [], markdown="\n".join([SAVED_LINE, SECOND_LINE]))
    assert _paragraph(target, "Qin, Y.").text == SAVED_LINE
    assert _italic_journal(target, JOURNAL, marker="Qin, Y.") == [JOURNAL]
    assert _italic_journal(target, "Practice", marker="Jones, A.") == ["Practice"]
    plain = [run.text for run in _paragraph(target, JOURNAL).runs if not run.italic]
    assert any("Stakeholder mapping" in piece for piece in plain)


def test_essay_ref_a2_gathered_parts_italicise_journal_title(workspace, tmp_path):
    """essay-ref-a2. The first write from gathered parts italicises the journal title."""
    seq = open_sequence()
    source = {
        "id": "src-1",
        "author": "Qin, Y.",
        "year": "2021",
        "title": "Stakeholder mapping",
        "container": JOURNAL,
        "volume": "8",
        "issue": "1",
        "pages": "2-9",
        "doi": "10.1000/stake",
    }
    target = tmp_path / "parts.docx"
    _write(seq, target, [source])
    paragraph = _paragraph(target, JOURNAL)
    assert "pp. 2-9" in paragraph.text
    assert _italic_journal(target, JOURNAL) == [JOURNAL]
    plain = [run.text for run in paragraph.runs if not run.italic]
    assert any("Stakeholder mapping" in piece for piece in plain)


def test_essay_ref_a3_lookup_page_range_survives_missing_lone_lines(workspace, tmp_path):
    """essay-ref-a3. A look-up page range is not deleted for missing lone page lines."""
    record = crossref_lookup(
        "Chokepoints and crude",
        fetch=lambda _query: {
            "message": {
                "items": [
                    {
                        "title": ["Chokepoints and crude"],
                        "page": PAGE_RANGE,
                        "container-title": [CONTAINER],
                    }
                ]
            }
        },
    )
    assert record is not None
    assert record["pages"] == PAGE_RANGE
    assert "article_number" not in record

    seq = open_sequence()
    locator = _paper(workspace, "range.pdf")
    _plant_lookup(seq, locator, PAGE_RANGE)
    kept, issues = gather_source(seq, _raw(locator, pages=PAGE_RANGE), 0)
    assert issues == []
    assert kept is not None
    assert kept["pages"] == PAGE_RANGE
    assert kept["field_sources"]["pages"] == "lookup"
    opened = apply_opened_citation(kept, seq)
    assert opened["pages"] == PAGE_RANGE

    target = tmp_path / "range.docx"
    _write(seq, target, [kept])
    text = _paragraph(target, CONTAINER).text
    assert f"pp. {PAGE_RANGE}" in text
    assert _italic_journal(target, CONTAINER) == [CONTAINER]


def test_essay_ref_a4_lookup_article_id_is_not_dropped(workspace, tmp_path):
    """essay-ref-a4. A Crossref page value that is an article id is stored and printed as one."""
    record = crossref_lookup(
        "Chokepoints and crude",
        fetch=lambda _query: {
            "message": {
                "items": [
                    {
                        "title": ["Chokepoints and crude"],
                        "page": ARTICLE_ID,
                        "container-title": [CONTAINER],
                    }
                ]
            }
        },
    )
    assert record is not None
    assert record["article_number"] == ARTICLE_ID
    assert "pages" not in record

    seq = open_sequence()
    locator = _paper(workspace, "article.pdf")
    _plant_lookup(seq, locator, ARTICLE_ID)
    kept, issues = gather_source(seq, _raw(locator, pages=ARTICLE_ID), 0)
    assert issues == []
    assert kept is not None
    assert kept["article_number"] == ARTICLE_ID
    assert "pages" not in kept
    legacy = {
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "container": CONTAINER,
        "pages": ARTICLE_ID,
        "locator": locator,
        "field_sources": {"pages": "lookup"},
    }
    opened = apply_opened_citation(legacy, seq)
    assert opened["article_number"] == ARTICLE_ID
    assert "pages" not in opened
    assert "pp." not in reference_line(opened)

    target = tmp_path / "article.docx"
    _write(seq, target, [kept])
    text = _paragraph(target, CONTAINER).text
    assert ARTICLE_ID in text
    assert "pp." not in text


def test_essay_ref_a5_blank_when_no_range_or_article_number(workspace, tmp_path):
    """essay-ref-a5. Pages stay blank when the opened source has neither. Nothing is invented."""
    seq = open_sequence()
    locator = _paper(workspace, "blank.pdf")
    kept, issues = gather_source(seq, _raw(locator), 0)
    assert issues == []
    assert kept is not None
    assert "pages" not in kept
    assert "article_number" not in kept
    line = reference_line(kept)
    assert "pp." not in line
    assert ARTICLE_ID not in line

    viewer, viewer_issues = gather_source(seq, _raw(locator, pages="1"), 0)
    assert viewer_issues == []
    assert viewer is not None
    assert "pages" not in viewer
    assert "pp." not in reference_line(viewer)

    target = tmp_path / "blank.docx"
    _write(seq, target, [kept])
    text = _paragraph(target, CONTAINER).text
    assert "pp." not in text
    assert "1-1" not in text


def test_essay_ref_a6_gather_keeps_a_looked_up_single_page(workspace):
    """essay-ref-a6. Gather keeps a single page only from a matching look-up."""
    seq = open_sequence()
    locator = _paper(workspace, "single.pdf")
    _plant_lookup(seq, locator, "27")
    kept, issues = gather_source(seq, _raw(locator, pages="27"), 0)
    assert issues == []
    assert kept is not None
    assert kept["pages"] == "27"
    assert kept["field_sources"]["pages"] == "lookup"
    assert "p. 27" in reference_line(kept)
    opened = apply_opened_citation(kept, seq)
    assert opened["pages"] == "27"

    bare, bare_issues = gather_source(seq, _raw(locator, pages="28"), 0)
    assert bare_issues == []
    assert bare is not None
    assert "pages" not in bare
    assert "p. 28" not in reference_line(bare)


def test_essay_ref_a7_gather_keeps_a_looked_up_doi(workspace):
    """essay-ref-a7. Gather keeps a DOI only from a matching look-up."""
    seq = open_sequence()
    locator = _paper(workspace, "lookup-doi.pdf")
    _plant_lookup(seq, locator, "27", doi="10.1000/looked")
    kept, issues = gather_source(seq, _raw(locator, pages="27", doi="10.1000/looked"), 0)
    assert issues == []
    assert kept is not None
    assert kept["doi"] == "10.1000/looked"
    assert kept["field_sources"]["doi"] == "lookup"
    assert reference_line(kept).endswith("Available at: doi:10.1000/looked.")

    bare, bare_issues = gather_source(seq, _raw(locator, doi="10.1000/other"), 0)
    assert bare is None
    assert bare_issues[0]["code"] == "invent-forbid"
    assert "10.1000/other" in bare_issues[0]["reason"]


def test_essay_ref_a8_a_web_page_keeps_its_access_date_with_a_publisher():
    """essay-ref-a8. A place or publisher on a web entry does not hide the access date."""
    source = {
        "author": "World Bank",
        "year": "2022",
        "title": "Corridor review",
        "place": "Washington, DC",
        "publisher": "World Bank",
        "url": "https://example.org/corridor",
        "accessed": "17 May 2022",
    }
    line = reference_line(source)
    assert "Washington, DC: World Bank" in line
    assert "Available at: https://example.org/corridor (Accessed: 17 May 2022)" in line

    journal = {
        "author": "Qin, Y.",
        "year": "2021",
        "title": "Stakeholder mapping",
        "container": JOURNAL,
        "volume": "8",
        "issue": "1",
        "pages": "2-9",
        "doi": "10.1000/stake",
        "accessed": "17 May 2022",
    }
    assert "(Accessed:" not in reference_line(journal)


def test_build_covered_cursor_and_build_share_write_docx():
    """Build covered. Cursor and Build both print the essay through write_docx."""
    assert write_docx.__module__ == "essay_writer.word"
    assert "write_docx(" in inspect.getsource(essay_pack_render_word)
    assert "write_docx(" in inspect.getsource(write_stage10)
    for stage in ("6", "9"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"]["model"] == build["settings"]["model"]
        assert cursor["settings"]["fast"] is False
        assert build["settings"]["fast"] is False
