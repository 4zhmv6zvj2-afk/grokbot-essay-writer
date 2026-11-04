"""Bug #25 and AC-NT3. One standard opening for the findings note and the mid tip.

The opening is standard_opening. A diary table prints How to score high.
An essay or a report with a scheme prints what the mark scheme scores.
A later writing type uses that same function. It does not grow a second sentence.
"""

import inspect

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import (
    FINDINGS_HOW_TO_SCORE_HIGH,
    FINDINGS_MARK_SCHEME,
    FINDINGS_NONE,
    register_mapping,
    unregister_mapping,
)
from essay_writer.build_office import report_phase as build_report_phase
from essay_writer.build_status import MID_BUILD_STATUS, basis_for, reset_status
from essay_writer.cursor_office import report_phase
from essay_writer.diary import title_page_spec
from essay_writer.paths import essay_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.review import eqr_verdict
from essay_writer.specialists.eqr import (
    CLAIM_CHECKS,
    NORTH_STAR,
    build_findings,
    findings_note_clears,
)
from essay_writer.specialists.grok_bot import basics_pass_lines, standard_opening
from essay_writer.state import load_state, save_state
from essay_writer.word import essay_pack_render_word

DIARY = "LIG9001HK"
ESSAY = "LIG9002HK"
REPORT = "LIG9003HK"
FUTURE = "LIG9004HK"
TITLES = ("North occasion", "South occasion", "East occasion", "West occasion")
ASK = (
    "Understand the practice by reflecting on your own decisions. "
    "Each entry names one decision and critically analyses it with theory and evidence."
)
DIARY_BRIEF = f"""
Assignment title: Individual reflective diary

Module title: Practice module
Module code: {DIARY}

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.

Each entry is about 500 words, plus or minus 10%.
The whole diary is 2,000 words, plus or minus 10%.

Title page: module title, module code, assignment title, registration number, and the word count.
The name stays off the title page and the file.

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the decisions | thin | partial | sound | clear | exact and evidenced |
"""
ESSAY_BRIEF = (
    "Genre: essay\n"
    "Question: Should the council publish the figure?\n"
)
ESSAY_SCHEME = "High Distinction (80-100): evidenced\nPass (50-59): adequate\n"
REPORT_BRIEF = (
    "Genre: report\n"
    "Question: How should the firm report the corridor?\n"
)
REPORT_SCHEME = "Distinction (70-79): evidenced\nPass (50-59): adequate\n"
FUTURE_BRIEF = """
Genre: fieldnote

Assignment title: Quay notes

Question: What did the quay show on that watch?

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the watch | thin | partial | sound | clear | exact and evidenced |
"""
INVENTED = ("Distinction", "Merit", "First")


def _open(module: str) -> str:
    draft = essay_sequence_new(module, "draft")
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm")
    assert opened["ok"] is True, opened
    return opened["sequence_id"]


def _write_brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _findings(seq: str) -> str:
    return build_findings(seq, {"text": "", "opened": False}, {"pdfs": [], "ran": False})


def _judgement(findings: str) -> str:
    rows = [line.strip() for line in findings.splitlines() if line.strip()]
    assert rows[0] == NORTH_STAR
    assert CLAIM_CHECKS in rows
    return rows[1]


def _diary_pack(seq: str) -> dict:
    body = (
        "Format reflective diary. "
        + ASK
        + " 70+."
    )
    return {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "open",
        "registration_number": "445566",
        "sections": [{"heading": title, "body": body} for title in TITLES],
    }


def _map_future(text: str, *, has_scheme: bool) -> dict:
    return {
        "named_entries": [],
        "named_by_brief": False,
        "part_count": None,
        "unnamed_note": None,
        "lock": "notes",
        "title_page": title_page_spec(text),
        "findings_opening": FINDINGS_HOW_TO_SCORE_HIGH if has_scheme else FINDINGS_NONE,
    }


def test_ac1_diary_how_to_score_high_clears_word(workspace):
    """AC1. Top column 70+ clears the findings note and the stage 6 Word path."""
    _write_brief(DIARY, DIARY_BRIEF)
    seq = _open(DIARY)
    assert read_assignment(seq)["findings_opening"] == FINDINGS_HOW_TO_SCORE_HIGH
    assert read_assignment(seq)["highest_band"] == "70+"

    findings = _findings(seq)
    line = _judgement(findings)
    assert line.startswith("How to score high")
    assert "70+" in line
    assert line == standard_opening(seq)
    assert line == basics_pass_lines(seq)[0]
    assert findings_note_clears(findings, seq) is True
    for invented in INVENTED:
        assert invented not in findings
        assert invented not in line

    rewritten = findings.replace(line, "The mark scheme scores 70+.", 1)
    assert findings_note_clears(rewritten, seq) is False

    state = load_state(seq)
    state["eqr"] = {
        "6": {
            "verdict": "PASS",
            "seat": "reviewer",
            "stage": "6",
            "findings": findings,
        }
    }
    save_state(seq, state)
    assert eqr_verdict(seq, "6") == "PASS"
    preview = essay_pack_render_word(seq, _diary_pack(seq), "draft", stage="6")
    assert preview.get("eqr") == "PASS", {
        "eqr": preview.get("eqr"),
        "refused": preview.get("refused"),
        "reason": preview.get("reason"),
        "ok": preview.get("ok"),
    }
    assert preview.get("refused") != "eqr"


def test_ac2_essay_mark_scheme_line_still_clears(workspace):
    """AC2. An essay line that says what the mark scheme scores still clears."""
    _write_brief(ESSAY, ESSAY_BRIEF)
    folder = essay_dir(ESSAY)
    (folder / "mark-scheme.md").write_text(ESSAY_SCHEME, encoding="utf-8")
    seq = _open(ESSAY)
    assert read_assignment(seq)["findings_opening"] == FINDINGS_MARK_SCHEME
    findings = _findings(seq)
    line = _judgement(findings)
    assert line.startswith("The mark scheme scores")
    assert "High Distinction" in line
    assert line == standard_opening(seq)
    assert findings_note_clears(findings, seq) is True


def test_ac3_one_line_pass_still_fails(workspace):
    """AC3. A one-line PASS does not clear, with or without an assignment id."""
    assert findings_note_clears("PASS") is False
    assert findings_note_clears("The independent review recorded a pass.") is False
    _write_brief(DIARY, DIARY_BRIEF)
    seq = _open(DIARY)
    assert findings_note_clears("PASS", seq) is False
    state = load_state(seq)
    state["eqr"] = {
        "6": {"verdict": "PASS", "seat": "reviewer", "stage": "6", "findings": "PASS"}
    }
    save_state(seq, state)
    assert eqr_verdict(seq, "6") is None


def test_ac4_diary_mid_tip_says_how_to_score_high(workspace):
    """AC4. Both shells use the diary opening. Neither renames it to mark scheme."""
    _write_brief(DIARY, DIARY_BRIEF)
    seq = _open(DIARY)
    opening = standard_opening(seq)
    assert basis_for(seq) == opening
    assert opening.startswith("How to score high")
    assert "70+" in basis_for(seq)
    assert "mark scheme" not in basis_for(seq).casefold()
    for invented in INVENTED:
        assert invented not in basis_for(seq)
    assert "How to score high" in MID_BUILD_STATUS
    assert "Do not rename a diary column" in MID_BUILD_STATUS
    assert "Never invent a band." in MID_BUILD_STATUS

    reset_status()
    cursor_tip = report_phase(seq, "check")
    reset_status()
    build_tip = build_report_phase(seq, "check")
    assert cursor_tip == build_tip
    spoken = " ".join(cursor_tip)
    assert "How to score high" in spoken
    assert "70+" in spoken
    assert "mark scheme" not in spoken.casefold()
    reset_status()


def test_ac_nt3_one_opening_for_diary_essay_and_a_later_type(workspace):
    """AC-NT3. findings_note_clears and basis_for read standard_opening.

    A later type does not add a branch in the clear. It sets the opening
    label, and the shared sentence follows that label.
    """
    clear_source = inspect.getsource(findings_note_clears)
    basis_source = inspect.getsource(basis_for)
    assert "standard_opening" in clear_source
    assert "standard_opening" in basis_source
    assert "reflective diary" not in clear_source
    assert "how_to_score_high" not in clear_source

    _write_brief(DIARY, DIARY_BRIEF)
    diary = _open(DIARY)
    _write_brief(ESSAY, ESSAY_BRIEF)
    (essay_dir(ESSAY) / "mark-scheme.md").write_text(ESSAY_SCHEME, encoding="utf-8")
    essay = _open(ESSAY)
    _write_brief(REPORT, REPORT_BRIEF)
    (essay_dir(REPORT) / "mark-scheme.md").write_text(REPORT_SCHEME, encoding="utf-8")
    report = _open(REPORT)

    diary_line = standard_opening(diary)
    essay_line = standard_opening(essay)
    report_line = standard_opening(report)
    assert diary_line.startswith("How to score high")
    assert essay_line.startswith("The mark scheme scores")
    assert report_line.startswith("The mark scheme scores")
    assert basis_for(diary) == diary_line
    assert basis_for(essay) == essay_line
    assert basis_for(report) == report_line
    assert findings_note_clears(_findings(diary), diary) is True
    assert findings_note_clears(_findings(essay), essay) is True
    assert findings_note_clears(_findings(report), report) is True
    assert findings_note_clears(_findings(essay), diary) is False
    assert findings_note_clears(_findings(diary), essay) is False

    register_mapping("fieldnote", _map_future)
    try:
        _write_brief(FUTURE, FUTURE_BRIEF)
        future = _open(FUTURE)
        seen = read_assignment(future)
        assert seen["writing_type"] == "fieldnote"
        assert seen["findings_opening"] == FINDINGS_HOW_TO_SCORE_HIGH
        future_line = standard_opening(future)
        assert future_line.startswith("How to score high")
        assert "70+" in future_line
        assert future_line == basics_pass_lines(future)[0]
        assert basis_for(future) == future_line
        assert findings_note_clears(_findings(future), future) is True
        assert "mark scheme" not in future_line.casefold()
    finally:
        unregister_mapping("fieldnote")
