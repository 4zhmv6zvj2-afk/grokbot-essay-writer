from pathlib import Path

from helpers import (
    CLARIFY_OPEN,
    TOPIC,
    open_sequence,
    pack,
    report_sections,
    source,
    write_upload,
)

from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.validate import essay_pack_validate


def _confirm_summary(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    return seq


def _confirm_full(workspace, clarify=CLARIFY_OPEN):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_full(seq, TOPIC, "draft", [source()], clarify_context=clarify)
    essay_research_full(seq, TOPIC, "confirm", [source()], clarify_context=clarify)
    return seq


def test_noted_without_supporting_excerpt_is_refused(workspace):
    seq = _confirm_summary(workspace)
    unsupported = pack(
        sections=report_sections(
            "Flows will keep rising (Smith, 2020).",
            "The named supply chain is in scope (Smith, 2020).",
            "Flows will keep rising through the chain (Smith, 2020).",
            "I am 95% sure flows will keep rising (Smith, 2020).",
        ),
        conclusion="noted",
    )
    result = essay_pack_validate(seq, unsupported, "draft")
    assert result["passed"] is False
    assert any(item["code"] == "conclusion" for item in result["blockers"])


def test_same_pack_with_open_is_allowed(workspace):
    seq = _confirm_summary(workspace)
    open_pack = pack(
        sections=report_sections(
            "Flows will keep rising (Smith, 2020).",
            "The named supply chain is in scope (Smith, 2020).",
            "Flows will keep rising through the chain (Smith, 2020).",
            "I am 95% sure flows will keep rising (Smith, 2020).",
        ),
        conclusion="open",
    )
    result = essay_pack_validate(seq, open_pack, "draft")
    assert result["passed"] is True
    assert any(item["code"] == "conclusion" for item in result["notes"])


def test_guidance_left_open_blocks_noted(workspace):
    seq = _confirm_full(workspace)
    result = essay_pack_validate(seq, pack(), "draft")
    assert result["passed"] is False
    assert any("left open" in item["reason"] for item in result["blockers"])


def test_formed_view_must_be_in_body(workspace):
    seq = _confirm_summary(workspace)
    body = pack(
        conclusion="open",
        formed_views=[
            {
                "sentence": "The Strait handles a large share of flows (Smith, 2020).",
                "source_id": "src-1",
                "quote": "The Strait handles a large share of flows.",
            }
        ],
    )
    ok = essay_pack_validate(seq, body, "draft")
    assert ok["passed"] is True
    assert any(item["code"] == "formed-view" for item in ok["notes"])

    invented = pack(
        conclusion="open",
        formed_views=[
            {
                "sentence": "A sentence that was never drafted.",
                "source_id": "src-1",
                "quote": "The Strait handles a large share of flows.",
            }
        ],
    )
    refused = essay_pack_validate(seq, invented, "draft")
    assert refused["passed"] is False
    assert any("not already in the body" in item["reason"] for item in refused["blockers"])


def test_validate_does_not_flip_open_to_noted(workspace):
    seq = _confirm_summary(workspace)
    open_pack = pack(conclusion="open")
    result = essay_pack_validate(seq, open_pack, "draft")
    assert result["passed"] is True
    assert open_pack["conclusion"] == "open"


def test_memo_note_strips_firm_close_rules():
    text = Path("docs/memo-how-it-works-note.md").read_text(encoding="utf-8")
    lowered = text.casefold()
    assert "afrc" not in lowered
    assert "quinn" not in lowered
    assert "official accounting" not in lowered
    assert "clarify enough is not evidence enough" in lowered or "enough to start is not enough" in lowered
