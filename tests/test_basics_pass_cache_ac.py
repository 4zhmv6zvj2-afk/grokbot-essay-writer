"""Basics pass seed and approved-look cache. Stable ids: AC1–AC6."""

from pathlib import Path

from helpers import ESSAY, open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.server import HANDLERS
from essay_writer.specialists.grok_bot import basics_pass_lines, cached_approved_look
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import _opening_look, essay_stage
from essay_writer.state import load_state

REPO = Path(__file__).resolve().parents[1]
QUESTION = "How should the firm manage the corridor?"
DUMP = (
    "Band 6 — excellent analysis of corridor risk.\n"
    "Band 5 — good use of sources.\n"
    "Band 4 — adequate structure.\n"
)


def _brief(text: str) -> None:
    from essay_writer.paths import essay_dir

    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _opened(seq: str) -> str:
    return "\n".join(basics_pass_lines(seq))


def test_ac1_draft_missing_basics_seeds_instead_of_refuse(workspace):
    """AC1. Active assignment drafts missing the Basics pass are seeded on draft."""
    _brief(f"Genre: report\nQuestion: {QUESTION}\n")
    seq = open_sequence()
    lines = basics_pass_lines(seq)
    buried = essay_stage(seq, "1", "draft", DUMP)
    assert buried["ok"] is True, buried
    assert buried.get("basics_seeded") is True
    assert buried["basics_pass"] == list(lines)
    payload = buried.get("digest")
    assert isinstance(payload, str) and payload

    wrong = "\n".join(
        (
            "The mark scheme scores the wrong band.",
            "Format: report.",
            f"Question: {QUESTION}",
        )
    )
    refused = essay_stage(seq, "1", "draft", wrong)
    assert refused["ok"] is False
    assert refused["refused"] == "basics-pass"
    assert refused.get("basics_seeded") is not True


def test_ac2_approved_look_cached_and_reused(workspace):
    """AC2. Confirm caches look per essay_id and later stages reuse it."""
    _brief(f"Genre: report\nQuestion: {QUESTION}\n")
    seq = open_sequence()
    look = _opened(seq) + "\nStage one plan notes."
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["ok"] is True, draft
    saved = essay_stage(seq, "1", "confirm", look, **picked(draft))
    assert saved["stored"] is True, saved
    assert cached_approved_look(seq) == look
    assert load_state(seq).get("approved_look") == look

    for stage in ("2", "3"):
        kept = essay_stage(seq, stage, "draft", look)
        assert kept["ok"] is True, kept
        essay_stage(seq, stage, "confirm", look, **picked(kept))

    plant_gathered_source(seq)
    for stage in ("4a", "4b"):
        kept = essay_stage(seq, stage, "draft", look)
        assert kept["ok"] is True, kept
        essay_stage(seq, stage, "confirm", look, **picked(kept))

    stage5 = essay_stage(seq, "5", "draft", look)
    assert stage5["stored"] is True, stage5

    empty_tail = essay_stage(seq, "6", "draft", DUMP)
    assert empty_tail["ok"] is True, empty_tail
    assert empty_tail.get("basics_seeded") is True
    assert _opening_look(seq) == look


def test_ac3_wrong_basics_still_refuses(workspace):
    """AC3. Replacing the three Basics lines with wrong shaped content still blocks."""
    _brief(f"Genre: report\nQuestion: {QUESTION}\n")
    seq = open_sequence()
    look = _opened(seq)
    draft = essay_stage(seq, "1", "draft", look)
    essay_stage(seq, "1", "confirm", look, **picked(draft))
    for stage in ("2", "3"):
        d = essay_stage(seq, stage, "draft", look)
        essay_stage(seq, stage, "confirm", look, **picked(d))
    basics_pass_lines(seq)
    wrong = "\n".join(
        (
            "The mark scheme scores the wrong band.",
            "Format: invented.",
            "Question: invented?",
        )
    )
    blocked = essay_stage(seq, "4a", "draft", wrong)
    assert blocked["ok"] is False
    assert blocked["refused"] in {"basics-pass", "misses"}
    if blocked["refused"] == "misses":
        assert any(item["code"] == "basics-pass" for item in blocked["misses"])


def test_ac4_stage5_skips_basics_gate(workspace):
    """AC4. Stage 5 still skips the Basics pass gate."""
    _brief(f"Genre: report\nQuestion: {QUESTION}\n")
    seq = open_sequence()
    look = _opened(seq)
    draft = essay_stage(seq, "1", "draft", look)
    essay_stage(seq, "1", "confirm", look, **picked(draft))
    for stage in ("2", "3"):
        d = essay_stage(seq, stage, "draft", look)
        essay_stage(seq, stage, "confirm", look, **picked(d))
    plant_gathered_source(seq)
    for stage in ("4a", "4b"):
        d = essay_stage(seq, stage, "draft", look)
        essay_stage(seq, stage, "confirm", look, **picked(d))
    quiet = essay_stage(seq, "5", "draft", look)
    assert quiet["ok"] is True, quiet
    assert quiet["stored"] is True
    assert "basics_pass" not in quiet
    assert load_state(seq).get("approved_look") == look


def test_ac5_daily_use_without_brief_unchanged(workspace):
    """AC5. No active assignment — no forced Basics template on draft."""
    seq = open_sequence()
    plain = essay_stage(seq, "1", "draft", "A short note with no brief on the module.")
    assert plain["ok"] is True, plain
    assert plain.get("basics_seeded") is not True
    assert "basics_pass" not in plain
    assert cached_approved_look(seq) is None


def test_ac6_build_covered_shared_essay_stage():
    """AC6. Cursor and Grok Build share essay.stage and stage settings."""
    assert HANDLERS["essay.stage"] is essay_stage
    item = stage_settings("4a")
    build = stage_launch("4a")
    cursor = cursor_stage_launch("4a")
    assert build["source"] == "essay_writer.stage_llm.stage_settings"
    assert cursor["source"] == "essay_writer.stage_llm.stage_settings"
    assert build["settings"]["rules"] == item["rules"]
    assert cursor["settings"]["rules"] == item["rules"]
    assert "Basics pass" in item["prompt_overlay"] or "Basics pass" in " ".join(item["rules"])
