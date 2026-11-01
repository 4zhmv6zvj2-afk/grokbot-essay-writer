"""First Stage 6 Word uses full Harvard Referencing, not surname stubs.

AC1: The first Word reference list prints the gathered entry (author, year,
title, and publisher or URL), not a surname alone.
AC2: In-text cites use the same family name and year as that list.
AC3: Build covered. Cursor and Grok Build share the stage 6 rules, and the
Word printer is reference_parts.
"""

import inspect
from pathlib import Path

from docx import Document
from helpers import (
    ESSAY,
    TOPIC,
    open_sequence,
    pack,
    report_sections,
    write_upload,
)

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_summary
from essay_writer.stage_llm import stage_settings
from essay_writer.word import essay_pack_render_word, word_manifest, write_docx

QUOTE = "The Strait handles a large share of flows."
GATHERED = (
    "Smith, J. (2020) Chokepoints and crude. Bristol: Harbour Press.\n"
    f"{QUOTE}\n"
)


def _paragraphs(path: Path) -> list[str]:
    return [
        paragraph.text.strip()
        for paragraph in Document(str(path)).paragraphs
        if paragraph.text.strip()
    ]


def _references(path: Path) -> list[str]:
    texts = _paragraphs(path)
    if "References" not in texts:
        return []
    return texts[texts.index("References") + 1 :]


def _stub_pack(seq: str) -> dict:
    cite = "(Smith)"
    body = pack(seq)
    body["sections"] = report_sections(
        f"The corridor depends on a narrow strait {cite}.",
        f"One named supply chain on the corridor is in scope for this report {cite}.",
        f"{QUOTE} through that chain {cite}.",
        f"{QUOTE} {cite}.",
    )
    body["sections"].append({"heading": "References", "body": "Smith"})
    body["sources"] = [
        {
            "id": "src-1",
            "origin": "upload",
            "locator": f"uploads/{ESSAY}/smith.md",
            "author": "Smith",
            "quote": QUOTE,
        }
    ]
    return body


def _confirm_full_source(seq: str) -> None:
    source = {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{ESSAY}/smith.md",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "place": "Bristol",
        "publisher": "Harbour Press",
        "quote": QUOTE,
    }
    draft = essay_research_summary(seq, TOPIC, "draft", [source])
    assert draft["ok"] is True, draft
    saved = essay_research_summary(seq, TOPIC, "confirm", [source])
    assert saved["ok"] is True, saved


def test_ac1_first_word_refs_are_full_ctr_not_surnames(workspace):
    """AC1. A surname stub on the pack still prints the gathered CTR entry."""
    write_upload(workspace, text=GATHERED)
    seq = open_sequence()
    _confirm_full_source(seq)
    body = _stub_pack(seq)
    _prepared, report = word_manifest(seq, body)
    line = " ".join(report["references"])
    assert "Smith, J." in line
    assert "(2020)" in line
    assert "Chokepoints and crude" in line
    assert "Harbour Press" in line
    assert line.strip() not in {"Smith", "Smith."}

    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    refs = _references(path)
    joined = "\n".join(refs)
    assert refs
    assert "Smith, J. (2020)" in joined
    assert "Chokepoints and crude" in joined
    assert "Bristol: Harbour Press" in joined
    assert "Smith" not in {item.rstrip(".") for item in refs}
    assert "Smith." not in refs


def test_ac2_in_text_cites_match_the_reference_list(workspace):
    """AC2. Bare (Smith) in the draft becomes (Smith, 2020), matching the list."""
    write_upload(workspace, text=GATHERED)
    seq = open_sequence()
    _confirm_full_source(seq)
    body = _stub_pack(seq)
    preview = essay_pack_render_word(seq, body, "draft", stage="6")
    assert preview.get("references"), preview
    listed = " ".join(preview["references"])
    assert "Smith, J. (2020)" in listed
    assert "Harbour Press" in listed

    _prepared, report = word_manifest(seq, body)
    path = work_dir(seq) / "output" / f"{seq}.docx"
    write_docx(seq, body, report, path)
    texts = _paragraphs(path)
    body_text = "\n".join(texts[: texts.index("References")])
    refs = "\n".join(texts[texts.index("References") + 1 :])
    assert "(Smith, 2020)" in body_text
    assert "(Smith)" not in body_text
    assert "Smith, J. (2020)" in refs
    assert "Smith" in refs.split(",")[0] or "Smith, J." in refs


def test_ac3_build_covered_cursor_and_grok_share_ctr_rules():
    """AC3. Cursor and Grok Build read one stage 6 rule, and Word uses reference_parts."""
    from essay_writer.validate import inspect_pack
    from essay_writer.word import write_docx as writer

    cursor = cursor_stage_launch("6")
    grok = stage_launch("6")
    assert cursor["settings"]["fast"] is False
    assert grok["settings"]["fast"] is False
    assert cursor["settings"]["source"] == grok["settings"]["source"]
    assert cursor["settings"]["rules"] == grok["settings"]["rules"]
    rules = stage_settings("6")["rules"]
    assert rules == cursor["settings"]["rules"]
    assert "Harvard Referencing" in rules
    assert "surname alone is not an entry" in rules
    assert "full reference entry" in rules
    diary = stage_settings("6", "diary")["rules"]
    assert "surname alone is not an entry" in diary
    assert "reference_parts(" in inspect.getsource(writer)
    assert "prepare_word_citations(" in inspect.getsource(writer)
    assert "complete_citation_sources(" in inspect.getsource(inspect_pack)
