"""House labels stay out of stage prompts and Word bytes."""

import re
import zipfile
from pathlib import Path

from helpers import ESSAY, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.harvard_4a import FOUR_A_FORMAT
from essay_writer.research import essay_research_summary
from essay_writer.research_packs import write_annotation_docx
from essay_writer.review import REVIEW_PROMPT
from essay_writer.stage_llm import all_stage_settings, stage_settings
from essay_writer.student_voice import (
    for_word,
    say,
    strip_word_labels,
    student_surface_hits,
)
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word
from essay_writer.writing_basics import CHECKLISTS

REPO = Path(__file__).resolve().parents[1]
JOURNAL = (
    "Smith, J. (2020) Chokepoints and crude. Maritime Policy 12(3) pp. 4-9. doi:10.1000/strait\n"
    "The Strait handles a large share of flows.\n"
    "The authors confirm the limit in the gathered file.\n"
)
NOTE = (
    'Smith (2020) argues the corridor is narrow. The authors confirm the limit. '
    'The paper says "The Strait handles a large share of flows."'
)


def _zip_text(path: Path) -> str:
    chunks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".xml"):
                chunks.append(archive.read(name).decode("utf-8"))
    return "\n".join(chunks)


def _plain(xml: str) -> str:
    return re.sub(r"<[^>]+>", "", xml)


def test_stage_prompts_and_pasted_notes_omit_house_labels():
    for stage, item in all_stage_settings().items():
        assert student_surface_hits(item["prompt_overlay"]) == [], stage
    for stage, lines in CHECKLISTS.items():
        assert student_surface_hits("\n".join(lines)) == [], stage
    assert student_surface_hits(REVIEW_PROMPT) == []
    assert stage_settings("eqr")["prompt_overlay"] == REVIEW_PROMPT
    folded = "\n".join(item["prompt_overlay"] for item in all_stage_settings().values()).casefold()
    assert "do not invent sources" in folded
    assert "do not invent sources" in stage_settings("4a")["prompt_overlay"]
    assert "do not invent sources" in stage_settings("5")["prompt_overlay"].casefold()
    assert "do not invent sources" in stage_settings("9")["prompt_overlay"].casefold()
    assert "approve" in stage_settings("8")["prompt_overlay"].casefold()
    assert FOUR_A_FORMAT in stage_settings("4a")["prompt_overlay"]
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    harvard = (REPO / "docs" / "referencing-harvard.md").read_text(encoding="utf-8")
    assert student_surface_hits(helpers) == []
    assert student_surface_hits(harvard) == []


def test_word_bytes_omit_house_labels(workspace):
    write_upload(workspace, text=JOURNAL)
    seq = open_sequence()
    row = {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{ESSAY}/smith.md",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "container": "Maritime Policy",
        "volume": "12",
        "issue": "3",
        "pages": "4-9",
        "doi": "10.1000/strait",
        "quote": "The Strait handles a large share of flows.",
        "annotation": NOTE,
    }
    essay_research_summary(seq, TOPIC, "draft", [row])
    saved = essay_research_summary(seq, TOPIC, "confirm", [row])
    assert saved["stored"] is True
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    for name in ("annotation.docx", "download-list.docx"):
        plain = _plain(_zip_text(folder / name))
        assert student_surface_hits(plain) == [], name
        assert re.search(r"\bdig\b", plain, re.IGNORECASE) is None
    assert "The authors confirm the limit." in _plain(_zip_text(folder / "annotation.docx"))

    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    preview = essay_pack_render_word(seq, pack(), "draft")
    assert preview["wrote"] is False
    written = essay_pack_render_word(seq, pack(), "confirm")
    assert written["wrote"] is True, written.get("reason")
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "2" / "output"
    essay_xml = _zip_text(folder / f"{seq}.docx")
    assert student_surface_hits(_plain(essay_xml)) == []
    assert "invent-forbid" not in essay_xml.casefold()


def test_citation_line_drops_dig_and_keeps_the_academic_verb(tmp_path):
    path = tmp_path / "annotation.docx"
    write_annotation_docx(
        path,
        [
            {
                "parts": [("How firms dig for data. invent-forbid.", False)],
                "paragraph": "The authors confirm the limit. EQR Grok Build Confirm.",
            }
        ],
        empty_note="Nothing to dig here.",
    )
    plain = _plain(_zip_text(path))
    assert student_surface_hits(plain) == []
    assert "look-up" in plain
    assert "do not invent sources" in plain
    assert "The authors confirm the limit." in plain
    assert "independent review" in plain
    assert "approve" in plain


def test_annotation_house_label_is_refused_before_word(workspace):
    write_upload(workspace, text=JOURNAL)
    seq = open_sequence()
    row = source()
    row["annotation"] = NOTE + " invent-forbid."
    refused = essay_research_summary(seq, TOPIC, "draft", [row])
    assert refused["ok"] is False
    assert refused["refused"] == "house-jargon"
    assert refused["wrote"] is False
    assert "invent-forbid" not in refused["reason"].casefold()
    assert not (workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / "annotation.docx").exists()


def test_chat_keeps_the_tool_id_and_word_does_not():
    spoken = say("Call essay.dig after you approve the save.")
    assert "essay.dig" in spoken
    worded = for_word("Call essay.dig after you approve the save.")
    assert "dig" not in worded.casefold()
    assert "look-up" in worded
    kept = strip_word_labels("The authors confirm the limit.")
    assert kept == "The authors confirm the limit."
    assert strip_word_labels("the pack size") == "the pack size"
    assert "pack" not in for_word("the pack size")
