"""Each high-risk payload refuses a malformed, missing, extra, or contradictory shape."""

from __future__ import annotations

from essay_writer.model_contract import (
    MISSING_QUESTION,
    VERDICT_SHAPE,
    ContractRefusal,
    parse_confirmed_question,
    parse_draft_tie,
    parse_findings,
    parse_smaller_questions,
    parse_stage_draft,
    parse_strip_report,
    parse_verdict,
    parse_word_title,
)

QUESTION = "How do ports shape coastal trade?"


def _refusal(parsed: object, code: str) -> ContractRefusal:
    assert isinstance(parsed, ContractRefusal)
    assert parsed.code == code
    assert parsed.reason
    return parsed


def test_confirmed_question_refuses_each_bad_shape() -> None:
    assert parse_confirmed_question(QUESTION).text == QUESTION
    missing = _refusal(parse_confirmed_question("  "), "missing")
    assert missing.reason == MISSING_QUESTION
    malformed = _refusal(parse_confirmed_question(12), "malformed")
    assert "confirmed question" in malformed.reason
    extra = _refusal(parse_confirmed_question({"question": QUESTION, "also": True}), "extra")
    assert "confirmed question" in extra.reason
    contradictory = _refusal(
        parse_confirmed_question(f"site:example.org {QUESTION}"), "contradictory"
    )
    assert "confirmed question" in contradictory.reason


def test_smaller_questions_refuse_each_bad_shape() -> None:
    assert parse_smaller_questions(None).questions == ()
    assert parse_smaller_questions(["What do harbours export?"], QUESTION).questions == (
        "What do harbours export?",
    )
    missing = _refusal(parse_smaller_questions({"question": QUESTION}), "missing")
    assert "smaller questions" in missing.reason
    malformed = _refusal(parse_smaller_questions(["What do harbours export?", 3]), "malformed")
    assert "smaller questions" in malformed.reason
    extra = _refusal(
        parse_smaller_questions({"questions": ["What do harbours export?"], "also": 1}), "extra"
    )
    assert "smaller questions" in extra.reason
    contradictory = _refusal(
        parse_smaller_questions(
            {"questions": ["What do harbours export?"], "question": "How do tides work?"},
            QUESTION,
        ),
        "contradictory",
    )
    assert "smaller questions" in contradictory.reason


def test_stage_draft_refuses_each_bad_shape() -> None:
    assert parse_stage_draft("Ports shape coastal trade.").text == "Ports shape coastal trade."
    missing = _refusal(parse_stage_draft("  "), "missing")
    assert "stage-5 draft" in missing.reason
    malformed = _refusal(parse_stage_draft(["Ports shape coastal trade."]), "malformed")
    assert "stage-5 draft" in malformed.reason
    extra = _refusal(
        parse_stage_draft({"text": "Ports shape coastal trade.", "band": 1000}), "extra"
    )
    assert "stage-5 draft" in extra.reason
    contradictory = _refusal(
        parse_stage_draft({"text": "Ports shape coastal trade.", "readable": False}),
        "contradictory",
    )
    assert "stage-5 draft" in contradictory.reason


def test_strip_report_refuses_each_bad_shape() -> None:
    kept = parse_strip_report(
        {"text": "The count stays.", "removed": ["Ada (2020)"], "subject_gap": True}
    )
    assert kept.text == "The count stays."
    assert kept.subject_gap is True
    missing = _refusal(parse_strip_report({"removed": ["Ada (2020)"]}), "missing")
    assert "strip report" in missing.reason
    malformed = _refusal(parse_strip_report("The count stays."), "malformed")
    assert "strip report" in malformed.reason
    extra = _refusal(parse_strip_report({"text": "The count stays.", "note": "gap"}), "extra")
    assert "strip report" in extra.reason
    contradictory = _refusal(
        parse_strip_report(
            {"text": "Ada (2020) found it.", "removed": ["Ada (2020)"], "subject_gap": True}
        ),
        "contradictory",
    )
    assert "strip report" in contradictory.reason


def test_verdict_and_draft_tie_refuse_each_bad_shape() -> None:
    assert parse_verdict("PASS").verdict == "PASS"
    missing = _refusal(parse_verdict(None), "missing")
    assert missing.reason == VERDICT_SHAPE
    malformed = _refusal(parse_verdict("MAYBE"), "malformed")
    assert malformed.reason == VERDICT_SHAPE
    extra = _refusal(parse_verdict({"verdict": "PASS", "seat": "writer"}), "extra")
    assert "review verdict" in extra.reason
    contradictory = _refusal(
        parse_verdict({"verdict": "FAIL", "draft_text": "Ports shape coastal trade."}),
        "contradictory",
    )
    assert "review verdict" in contradictory.reason
    saved = "Ports shape coastal trade."
    assert parse_draft_tie(saved, saved).draft_text == saved
    tie_missing = _refusal(parse_draft_tie(saved, None), "missing")
    assert "draft tie" in tie_missing.reason
    tie_malformed = _refusal(parse_draft_tie(saved, 5), "malformed")
    assert "draft tie" in tie_malformed.reason
    tie_extra = _refusal(
        parse_verdict({"verdict": "PASS", "draft_text": saved, "also": True}), "extra"
    )
    assert "review verdict" in tie_extra.reason
    tie_contradictory = _refusal(parse_draft_tie(saved, "A later rewrite."), "contradictory")
    assert "draft tie" in tie_contradictory.reason


def test_findings_refuse_each_bad_shape() -> None:
    missing = _refusal(parse_findings(""), "missing")
    assert "findings" in missing.reason
    malformed = _refusal(parse_findings(4), "malformed")
    assert "findings" in malformed.reason
    extra = _refusal(parse_findings({"text": "Overall judgement", "score": 1}), "extra")
    assert "findings" in extra.reason
    contradictory = _refusal(parse_findings("Overall judgement\nClaim checks"), "contradictory")
    assert "findings" in contradictory.reason


def test_word_title_refuses_each_bad_shape() -> None:
    assert parse_word_title("Coastal trade").text == "Coastal trade"
    missing = _refusal(parse_word_title("  "), "missing")
    assert "Word title" in missing.reason
    malformed = _refusal(parse_word_title("C" * 256), "malformed")
    assert "Word title" in malformed.reason
    extra = _refusal(parse_word_title({"title": "Coastal trade", "opening": "Ports."}), "extra")
    assert "Word title" in extra.reason
    contradictory = _refusal(
        parse_word_title("Ports shape coastal trade.", "Ports shape coastal trade."),
        "contradictory",
    )
    assert "Word title" in contradictory.reason
