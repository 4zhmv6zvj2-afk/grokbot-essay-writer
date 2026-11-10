"""Content check on the draft, the first read, and the independent review.

The check keeps a specific finding and names a stretched opened paper.
Naming that paper does not fail the review and does not block the Word file.
No rewrite-to-sound-human pass, no phrase list, and no detector.
"""

import inspect
from pathlib import Path

from helpers import open_sequence

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch, remote_cloud_argv
from essay_writer.late_chain import (
    FIRST_DRAFT_READY,
    STAGE6_OPEN,
    STAGE6_READ_LIST,
    quiet_stage5,
)
from essay_writer.paths import work_dir
from essay_writer.prompt_loader import text
from essay_writer.specialists.eqr import (
    CLAIM_CHECKS,
    NORTH_STAR,
    REVIEW_PROMPT,
    findings_note_clears,
)
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
CONTENT = text("craft/voice.md", "content_check")
PHRASEBANK = text("craft/voice.md", "phrasebank_pointer")
RECHECK = text("craft/voice.md", "edit_recheck")
STRETCH = (
    "The findings note may also name a leftover chatbot habit, an overconfident claim, "
    "or a real opened paper stretched past what it found."
)
CLEAR_STILL = "Naming it does not fail the review and does not block the Word file."
INVENTED_STILL = "Invented sources still fail on the existing source check."
PHRASE_HOST = "phrasebank.manchester.ac.uk"
PHRASE_URL = "https://www.phrasebank.manchester.ac.uk/"
DISSERTATION_LINE = "this is the first comprehensive investigation"
BANNED_TOOLS = (
    "humanizer",
    "gptzero",
    "turnitin",
    "grammarly",
    "pangram",
)


def _clear_findings(extra: str = "") -> str:
    lines = [
        NORTH_STAR,
        "What the mark scheme scores is the argument.",
        "Format: the sections the brief names.",
        "The assignment asks for a judgement on the question.",
        CLAIM_CHECKS,
        "One gathered sentence was checked against the opened file.",
    ]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _stage5_helpers() -> str:
    body = HELPERS.read_text(encoding="utf-8")
    start = body.index("### 5. Write your first draft")
    end = body.index("### 6. Re-read and make changes")
    return body[start:end]


def test_stage5_and_stage8_carry_the_content_check_and_stay_quiet():
    """Stage 5 writes the check into the draft. Stage 8 re-reads a tightened sentence."""
    for genre in (None, "essay", "report", "diary"):
        stage5 = stage_settings("5", genre)["rules"]
        stage8 = stage_settings("8", genre)["rules"]
        assert CONTENT in stage5
        assert CONTENT in stage8
        assert PHRASEBANK in stage5
        assert RECHECK in stage8
        assert "Chat for this step stays quiet." in stage5
        assert student_surface_hits(stage5) == []
        assert student_surface_hits(stage8) == []
    helpers = _stage5_helpers()
    assert CONTENT in helpers
    assert PHRASE_HOST in helpers
    assert "://" not in stage_settings("5")["rules"]
    style = HELPERS.read_text(encoding="utf-8")
    assert PHRASE_URL in style
    assert "Do not copy phrase lists" in style
    assert "Methods and results phrasing from that site is only for a research report" in style
    assert DISSERTATION_LINE not in style
    folded = "\n".join(
        stage_settings(stage)["rules"] for stage in ("1", "2", "3", "4a", "4b", "7", "9", "10")
    ).casefold()
    assert "phrasebank.manchester.ac.uk" not in folded
    for name in BANNED_TOOLS:
        assert name not in stage_settings("5")["rules"].casefold()
        assert name not in style.casefold()


def test_first_read_speaks_the_list_once_without_a_gate(workspace):
    """The first read says the short list beside the existing openers. No card and no blocker."""
    seq = open_sequence()
    waiting = quiet_stage5({"stored": False, "ok": True}, seq)
    assert waiting["chat"] == STAGE6_OPEN
    assert waiting["next"] == STAGE6_OPEN
    assert waiting["read_list"] == STAGE6_READ_LIST
    assert waiting["checklist_in_chat"] is False
    assert "card" not in waiting
    assert waiting.get("blocked") is not True
    assert "Basics checklist" not in waiting["chat"]
    assert "Basics checklist" not in waiting["read_list"]
    assert student_surface_hits(waiting["read_list"]) == []
    assert "edit it yourself" in waiting["read_list"]
    assert "This is not a score" in waiting["read_list"]
    assert "not rewritten for you" in waiting["read_list"]
    rules = stage_settings("6")["rules"]
    assert "show the short read list once, then stop" in rules
    assert "Do not rewrite the draft for them." in rules
    assert "Do not add a gate, a score, or a blocker." in rules
    word = work_dir(seq) / "output" / f"{seq}.docx"
    word.parent.mkdir(parents=True, exist_ok=True)
    word.write_bytes(b"")
    ready = quiet_stage5({"stored": True, "ok": True}, seq)
    assert ready["chat"] == FIRST_DRAFT_READY
    assert ready["next"] == FIRST_DRAFT_READY
    assert ready["read_list"] == STAGE6_READ_LIST
    assert "card" not in ready
    assert "When a reply includes read_list, say that list once" in (
        REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md"
    ).read_text(encoding="utf-8")


def test_review_names_a_stretched_paper_and_still_clears():
    """A real opened paper used past its finding is named. The note still clears."""
    assert STRETCH in REVIEW_PROMPT
    assert CLEAR_STILL in REVIEW_PROMPT
    assert INVENTED_STILL in REVIEW_PROMPT
    assert "Do not rewrite the line." in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []
    named = _clear_findings(
        "A real opened paper is stretched past what it found. Naming it does not block the Word file."
    )
    assert findings_note_clears(named) is True
    assert findings_note_clears(_clear_findings()) is True
    assert findings_note_clears("The independent review recorded a pass.") is False
    source = inspect.getsource(findings_note_clears)
    for token in ("stretched", "detector", "phrasebank", "read_list"):
        assert token.casefold() not in source.casefold()
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    for blob in (gates, validate):
        assert "phrasebank" not in blob.casefold()
        assert "read_list" not in blob
        assert "stretched past" not in blob.casefold()


def test_both_shells_read_the_same_content_check():
    """Cursor and Grok Build load the same stage rules."""
    for stage in ("5", "8"):
        shared = stage_settings(stage)["rules"]
        assert stage_launch(stage)["settings"]["rules"] == shared
        assert cursor_stage_launch(stage)["settings"]["rules"] == shared
        assert CONTENT in shared
    review = stage_settings("eqr")["rules"]
    assert STRETCH in review
    assert stage_launch("eqr")["settings"]["rules"] == review
    assert cursor_stage_launch("eqr")["settings"]["rules"] == review
    for stage in ("5", "6", "8", "eqr"):
        assert remote_cloud_argv(stage_launch(stage)["command"]) is False
    prose = stage_launch("5")["command"] + ["Read https://www.phrasebank.manchester.ac.uk/ before the draft."]
    assert remote_cloud_argv(prose) is False
    assert remote_cloud_argv(["agent", "https://cursor.com/agents/bc-1"]) is True
    assert remote_cloud_argv(["agent", "--cloud-agent=true"]) is True
    assert remote_cloud_argv(["agent", "--remote-agent=1"]) is True
    assert remote_cloud_argv(["agent", "--endpoint=https://remote.example"]) is True
    assert remote_cloud_argv(["agent", "-e", "https://remote.example"]) is True
    assert remote_cloud_argv(["agent", "--model", "cloud-agent"]) is False
    assert remote_cloud_argv(["agent", "--model=cloud-agent"]) is False
