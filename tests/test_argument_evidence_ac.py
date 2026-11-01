"""Evidence strength in the argument bullets. Stable ids: AC1–AC3.

Stages 5 and 8 already keep the writer's hedge. This adds the other half:
a claim may not be stronger than the evidence under it. Prompt text only,
read from the same stage row on both launchers, mirrored once in the shared
helper note. No new pass/fail gate.
"""

from pathlib import Path

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import EVIDENCE_STRENGTH, basics_lines

REPO = Path(__file__).resolve().parents[1]
HELPERS = REPO / "docs" / "academic-writing-helpers.md"
GENRES = (None, "diary", "essay", "report")
WRITING = ("5", "8")
OTHER = ("1", "2", "3", "4a", "4b", "6", "7", "9", "10")


def test_ac1_writing_stages_carry_the_evidence_strength_bullet():
    """AC1. Stage 5 and stage 8 carry it for every genre; other stages do not."""
    for stage in WRITING:
        for genre in GENRES:
            item = stage_settings(stage, genre)
            assert EVIDENCE_STRENGTH in item["rules"]
            assert EVIDENCE_STRENGTH in item["prompt_overlay"]
            assert student_surface_hits(item["prompt_overlay"]) == []
            assert student_surface_hits(item["rules"]) == []
    for stage in OTHER:
        assert EVIDENCE_STRENGTH not in stage_settings(stage)["rules"]


def test_ac2_the_helper_note_and_both_launchers_read_the_same_bullet():
    """AC2. One copy in the helper note, one row on both launchers."""
    helpers = HELPERS.read_text(encoding="utf-8")
    assert helpers.count(EVIDENCE_STRENGTH) == 2
    for stage in WRITING:
        for line in basics_lines(stage):
            assert line in helpers
        shared = stage_settings(stage)
        assert stage_launch(stage)["settings"]["rules"] == shared["rules"]
        cursor = cursor_stage_launch(stage)
        assert cursor["settings"]["rules"] == shared["rules"]
        assert EVIDENCE_STRENGTH in cursor["settings"]["rules"]
        assert EVIDENCE_STRENGTH in stage_launch(stage)["command"][
            stage_launch(stage)["command"].index("--rules") + 1
        ]


def test_ac3_the_bullet_names_the_ceilings_and_stays_prompt_only():
    """AC3. Case, correlation, and sample ceilings are named. No gate, no invented limit."""
    for phrase in (
        "A claim is no stronger than the evidence under it.",
        "One case does not show a general trend",
        "a correlation does not show a cause",
        "a small sample does not show a wide effect",
        "Keep the limit the source states",
        "write the claim at the size the evidence supports",
    ):
        assert phrase in EVIDENCE_STRENGTH
    assert student_surface_hits(EVIDENCE_STRENGTH) == []
    folded = EVIDENCE_STRENGTH.casefold()
    for invented in ("invent a limit", "add a limitation", "assume", "estimate the effect"):
        assert invented not in folded
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    assert "EVIDENCE_STRENGTH" not in gates
    assert "EVIDENCE_STRENGTH" not in validate
    writing = (REPO / "src" / "essay_writer" / "writing_basics.py").read_text(encoding="utf-8")
    assert writing.count("EVIDENCE_STRENGTH = (") == 1
