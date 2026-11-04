"""Brief weight-table fit on the landed writing pack. Stable ids: AC1–AC4.

The synth-mark fixture brief and its frozen drafts live under
tests/fixtures/. Everything here is fixture-only synthetic. A weighted
section the draft does not carry is a note, never a block.
"""

import json
import re
from pathlib import Path

from helpers import open_sequence

from essay_writer.mark_fit import (
    mark_fit_notes,
    missing_weighted_sections,
    unweighted_headings,
    weighted_sections,
)
from essay_writer.paths import essay_dir
from essay_writer.validate import essay_pack_validate

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
MODULE = "SYN6004AA"
BRIEF = (FIXTURES / "synth-mark-brief-v1.md").read_text(encoding="utf-8")
KEY = json.loads((FIXTURES / "synth-mark-answer-key-v1.json").read_text(encoding="utf-8"))
EXPECTED = ("Introduction", "Drivers of sustainability-centric SCM")


def _plant(workspace: Path, text: str = BRIEF) -> str:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")
    return open_sequence(MODULE)


def _sections(name: str) -> list[dict[str, str]]:
    """A frozen draft as pack sections: level-two headings only, no title line."""
    text = (FIXTURES / str(KEY["drafts"][name]["file"])).read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    sections: list[dict[str, str]] = []
    for part in parts:
        heading, _sep, body = part.partition("\n")
        sections.append({"heading": heading.strip(), "body": body.strip()})
    return sections


def _pack(seq: str, sections: list[dict[str, str]]) -> dict:
    return {
        "essay_id": seq,
        "title": "Sustainability and the chain",
        "referencing": "harvard",
        "assessment": "Individual report",
        "genre": "report",
        "conclusion": "open",
        "sections": sections,
    }


def test_ac1_the_fixture_brief_prints_its_weights():
    """AC1. The seven fixture weights are read, and headings are not weights."""
    weights = weighted_sections(BRIEF)
    assert [row["name"] for row in weights] == [
        "Introduction",
        "Drivers of sustainability-centric SCM",
        "Benefits of integrating sustainability",
        "Integration to competitive advantage",
        "Recession relevance",
        "Conclusion",
        "Presentation and referencing",
    ]
    assert [row["weight"] for row in weights] == [5, 20, 20, 30, 10, 5, 10]
    assert weighted_sections("Genre: essay\nWrite 2,000 words.\n") == []
    assert KEY["label"] == "fixture-only synthetic"
    assert "fixture-only" in BRIEF.casefold()


def test_ac2_frozen_drafts_match_the_answer_key():
    """AC2. Weak misses two weighted sections; mid and strong miss none."""
    weights = weighted_sections(BRIEF)
    for name, expected in KEY["drafts"].items():
        missing = missing_weighted_sections(_sections(name), weights)
        assert [row["name"] for row in missing] == expected["missing_weighted"], name


def test_ac3_a_missing_weighted_section_is_a_note_not_a_block(workspace):
    """AC3. The student path names the gap in notes, and no block is added for it."""
    seq = _plant(workspace)
    report = essay_pack_validate(seq, _pack(seq, _sections("weak")), "draft")
    notes = [item for item in report["notes"] if item["code"] == "mark-fit-section"]
    assert len(notes) == 2
    reasons = " ".join(item["reason"] for item in notes)
    assert "Integration to competitive advantage" in reasons
    assert "30%" in reasons
    assert "Recession relevance" in reasons
    assert [item for item in report["blockers"] if item["code"] == "mark-fit-section"] == []


def test_ac4_a_brief_without_weights_adds_no_note(workspace):
    """AC4. Daily use with no weight table stays quiet."""
    seq = _plant(workspace, "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n")
    assert mark_fit_notes(seq, _sections("weak"), []) == []
    assert weighted_sections("") == []


def test_ac5_an_unweighted_heading_is_named_and_diary_stays_diary(workspace):
    """AC5. A heading the brief does not weight is a note; a diary brief gets none."""
    weights = weighted_sections(BRIEF)
    assert unweighted_headings(_sections("offbrief"), weights) == [
        "Literature review",
        "Recommendations",
    ]
    for name in ("weak", "mid", "strong"):
        assert unweighted_headings(_sections(name), weights) == [], name

    diary_brief = (
        "Genre: reflective diary\n"
        "Question: Reflect on the decisions in the watch.\n"
        "Section weights:\n"
        "| Section | Weight |\n"
        "| --- | ---: |\n"
        "| Entry one | 50% |\n"
        "| Entry two | 50% |\n"
    )
    seq = _plant(workspace, diary_brief)
    assert mark_fit_notes(seq, _sections("offbrief"), []) == []


def test_ac6_the_reviewer_prompt_names_weighted_gaps_and_invents_no_band():
    """AC6. The reviewer may name a weighted gap. It invents no band or weight."""
    from essay_writer.specialists.eqr import REVIEW_PROMPT
    from essay_writer.stage_llm import stage_settings
    from essay_writer.student_voice import student_surface_hits

    assert "may name a weighted section the draft does not carry" in REVIEW_PROMPT
    assert "does not fail the review by itself" in REVIEW_PROMPT
    assert "Do not invent a band descriptor, a criterion, or a weight" in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []
    assert stage_settings("eqr")["prompt_overlay"] == REVIEW_PROMPT


def test_ac7_a_named_supply_chain_is_required_by_the_brief(workspace):
    """AC7. The brief's chain list is read, and a generic draft gets one note."""
    from essay_writer.mark_fit import chain_allow_list, generic_chain_note

    names = chain_allow_list(BRIEF)
    assert names[:3] == ["Inditex", "Zara", "Toyota"]
    assert "AstraZeneca" in names
    for name in ("weak",):
        assert generic_chain_note(_sections(name), BRIEF), name
    for name in ("mid", "strong", "offbrief"):
        assert generic_chain_note(_sections(name), BRIEF) is None, name

    seq = _plant(workspace)
    report = essay_pack_validate(seq, _pack(seq, _sections("weak")), "draft")
    chain_notes = [item for item in report["notes"] if item["code"] == "mark-fit-chain"]
    assert len(chain_notes) == 1
    assert "one named supply chain" in chain_notes[0]["reason"]
    assert [item for item in report["blockers"] if item["code"] == "mark-fit-chain"] == []
    clean = essay_pack_validate(seq, _pack(seq, _sections("strong")), "draft")
    assert [item for item in clean["notes"] if item["code"] == "mark-fit-chain"] == []


GENERIC_SOURCES = [
    {
        "id": "src-1",
        "author": "Web Desk",
        "year": "2025",
        "title": "Sustainable supply chains explained",
        "url": "https://example.org/supply-chains",
        "locator": "uploads/SYN6004AA/web.md",
    }
]
SPECIALIST_SOURCES = [
    {
        "id": "src-1",
        "author": "Lloyd's List",
        "year": "2025",
        "title": "Carrier fuel rules and container rates",
        "url": "https://lloydslist.example/rates",
        "locator": "uploads/SYN6004AA/lloyds.md",
    }
]


def test_ac8_a_specialist_source_class_is_read_and_flagged_softly(workspace):
    """AC8. The brief's source class is read; a generic source set gets one note."""
    from essay_writer.mark_fit import specialist_source_classes, specialist_source_note

    assert specialist_source_classes(BRIEF) == [
        "Statista",
        "Lloyd's List",
        "Clarksons",
        "FT",
        "CILT Focus",
    ]
    assert specialist_source_note(BRIEF, GENERIC_SOURCES, _sections("weak"))
    assert specialist_source_note(BRIEF, SPECIALIST_SOURCES, _sections("mid")) is None
    # The strong fixture names the classes in its own prose.
    assert specialist_source_note(BRIEF, GENERIC_SOURCES, _sections("strong")) is None

    seq = _plant(workspace)
    report = essay_pack_validate(
        seq, {**_pack(seq, _sections("weak")), "sources": GENERIC_SOURCES}, "draft"
    )
    source_notes = [item for item in report["notes"] if item["code"] == "mark-fit-source"]
    assert len(source_notes) == 1
    assert "specialist industry source" in source_notes[0]["reason"]
    assert "Lloyd's List" in source_notes[0]["reason"]
    assert [item for item in report["blockers"] if item["code"] == "mark-fit-source"] == []


def test_ac9_the_fixture_band_is_4000_plus_or_minus_ten_percent():
    """AC9. The fixture's 4000 ±10% band is read as 3600–4400, with no new gate."""
    from essay_writer.rewrite_baseline import band_edges
    from essay_writer.textutil import word_band_from_brief_text

    rules = word_band_from_brief_text(BRIEF)
    assert rules["limit"] == 4000
    assert band_edges(rules) == (3600, 4400)
    assert "tables, figures, and references" in BRIEF


SMITH = (
    "Smith, J. (2020). Chokepoints and crude.\n"
    "This article presents Inditex's integration of supplier audits into the buying decision "
    "as a competitive advantage that a single supplier cannot copy.\n"
    "It argues that the 2008 recession cut order runs, and that the audited suppliers kept "
    "their water and energy saving through the downturn.\n"
)


def _with_gathered_source(workspace, seq):
    from helpers import plant_gathered_source, write_upload

    plant_gathered_source(seq)
    write_upload(workspace, essay_id=MODULE, name="smith.md", text=SMITH)
    return {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{MODULE}/smith.md",
        "author": "Smith, J.",
        "year": "2020",
        "quote": "Inditex's integration of supplier audits into the buying decision is a competitive advantage.",
    }


def test_ac10_target_a_one_rewrite_lifts_the_missing_weighted_sections(workspace):
    """AC10 (Target A). One lift adds the two weighted sections from gathered claims."""
    from essay_writer.specialists.writer import lift_missing_sections

    seq = _plant(workspace)
    source = _with_gathered_source(workspace, seq)
    pack = {**_pack(seq, _sections("weak2")), "sources": [source]}
    result = lift_missing_sections(seq, pack)
    assert result["added"] == ["Integration to competitive advantage", "Recession relevance"]
    sections = result["pack"]["sections"]
    headings = [section["heading"] for section in sections]
    assert headings.index("Integration to competitive advantage") < headings.index("Conclusion")
    assert headings.index("Recession relevance") < headings.index("Conclusion")
    for section in sections:
        if section["heading"] in result["added"]:
            assert "(Smith, 2020)" in section["body"]
            assert len(section["body"].split()) >= 10
    assert result["pack"]["mark_fit_lift"]["skipped"] == []
    notes = mark_fit_notes(seq, sections, [source])
    assert [item for item in notes if item["code"] == "mark-fit-section"] == []


def test_ac11_target_b_review_then_rewrite_clears_eighty_percent(workspace):
    """AC11 (Target B). The start notes are named, one rewrite clears them, strong stays clean."""
    from essay_writer.specialists.eqr import REVIEW_PROMPT
    from essay_writer.specialists.writer import lift_missing_sections

    seq = _plant(workspace)
    source = _with_gathered_source(workspace, seq)
    weak = {**_pack(seq, _sections("weak2")), "sources": [source]}
    start = mark_fit_notes(seq, weak["sections"], [source])
    assert len(start) == 2
    assert KEY["targets"]["B"]["start_mark_fit_notes"] == len(start)
    # The review path names a weighted gap, and it names no invented band.
    assert "weighted section the draft does not carry" in REVIEW_PROMPT
    assert all("weight" not in item["reason"].casefold() or "weights" in item["reason"] for item in start)
    lifted = lift_missing_sections(seq, weak)["pack"]
    remaining = mark_fit_notes(seq, lifted["sections"], [source])
    cleared = 1 - (len(remaining) / len(start))
    assert cleared >= 0.8, (len(start), len(remaining))
    assert KEY["targets"]["B"]["after_one_review_then_lift_mark_fit_notes"] == len(remaining)

    strong = {**_pack(seq, _sections("strong")), "sources": [source]}
    assert mark_fit_notes(seq, strong["sections"], [source]) == []
    assert lift_missing_sections(seq, strong)["added"] == []


OKAVANGO_BRIEF = (FIXTURES / "okavango-brief-v1.md").read_text(encoding="utf-8")


def _okavango_sections(name: str) -> list[dict[str, str]]:
    text = (FIXTURES / f"okavango-{name}-v1.md").read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    sections: list[dict[str, str]] = []
    for part in parts:
        heading, _sep, body = part.partition("\n")
        sections.append({"heading": heading.strip(), "body": body.strip()})
    return sections


def test_ac12_target_c_named_case_generalises_to_a_second_fixture(workspace):
    """AC12 (Target C). A non-MAR named case is read, and a generic draft is noted softly."""
    from essay_writer.mark_fit import generic_case_note, named_case_kind

    assert named_case_kind(OKAVANGO_BRIEF) == "case"
    assert named_case_kind(BRIEF) is None
    assert generic_case_note(_okavango_sections("weak"), OKAVANGO_BRIEF)
    assert generic_case_note(_okavango_sections("strong"), OKAVANGO_BRIEF) is None
    # The MAR chain rule stays the chain rule, and a named draft stays clean.
    assert generic_case_note(_sections("weak"), BRIEF) is None
    assert generic_case_note(_sections("weak2"), BRIEF) is None

    seq = _plant(workspace)
    report = essay_pack_validate(seq, _pack(seq, _sections("weak")), "draft")
    assert [item for item in report["notes"] if item["code"] == "mark-fit-case"] == []
    assert [item for item in report["notes"] if item["code"] == "mark-fit-chain"]

    oka_seq = open_sequence("PHIL5001HK")
    folder = essay_dir("PHIL5001HK")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(OKAVANGO_BRIEF, encoding="utf-8")
    oka_report = essay_pack_validate(
        oka_seq,
        {
            "essay_id": oka_seq,
            "title": "Whose interests count",
            "referencing": "harvard",
            "assessment": "Individual essay",
            "genre": "essay",
            "conclusion": "open",
            "sections": _okavango_sections("weak"),
        },
        "draft",
    )
    case_notes = [item for item in oka_report["notes"] if item["code"] == "mark-fit-case"]
    assert len(case_notes) == 1
    assert "named case" in case_notes[0]["reason"]
    assert "Okavango Delta" in case_notes[0]["reason"]
    assert [item for item in oka_report["blockers"] if item["code"] == "mark-fit-case"] == []


def test_ac13_target_a_also_holds_on_the_locked_weak_fixture(workspace):
    """AC13. On the weak fixture the same lift clears the two section notes."""
    from essay_writer.specialists.writer import lift_missing_sections

    seq = _plant(workspace)
    source = _with_gathered_source(workspace, seq)
    pack = {**_pack(seq, _sections("weak")), "sources": [source]}
    before = [item for item in mark_fit_notes(seq, pack["sections"], [source]) if item["code"] == "mark-fit-section"]
    assert len(before) == 2
    lifted = lift_missing_sections(seq, pack)
    assert set(lifted["added"]) == {
        "Integration to competitive advantage",
        "Recession relevance",
    }
    after = mark_fit_notes(seq, lifted["pack"]["sections"], [source])
    assert [item for item in after if item["code"] == "mark-fit-section"] == []
    # The source note stays soft. The chain note clears only because the lifted
    # claim names Inditex from the opened file, not because anything was invented.
    codes = [item["code"] for item in after]
    assert "mark-fit-source" in codes
    if "mark-fit-chain" not in codes:
        text = "\n".join(section["body"] for section in lifted["pack"]["sections"])
        assert "Inditex" in text
