"""Stage 5 writes the first draft inside the brief's word band.

The hyphen acceptance ids for this file live in the docstrings below.
"""

from helpers import open_sequence, plant_gathered_source, write_upload

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.late_chain import FIRST_DRAFT_READY, STAGE6_OPEN
from essay_writer.paths import essay_dir, module_code
from essay_writer.review import essay_review, writer_clears_left
from essay_writer.specialists.writer import (
    draft_word_count,
    first_draft_below_minimum,
)
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_note import _note_look
from essay_writer.stage_run import essay_stage
from essay_writer.textutil import count_words

QUESTION = "How do chokepoints constrain tanker flows through the corridor?"
OPENER = "This essay answers how chokepoints constrain tanker flows through the corridor."
BRIEF = f"Genre: essay\nQuestion: {QUESTION}\nWord count: 2,000 words (1,800 to 2,200).\n"
BAND_RULE = (
    "When the brief states a word band, write the first draft inside that band, "
    "counting both ends as inside."
)


def _save_through(seq: str, stop: str) -> None:
    from essay_writer.writing_basics import STAGE_ORDER

    for stage in STAGE_ORDER:
        look = f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            if stage == stop:
                return
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked_for(draft))
        assert saved["stored"] is True, saved
        if stage == stop:
            return


def picked_for(draft: dict) -> dict:
    from helpers import picked

    return picked(draft)


def _plant_brief(seq: str) -> None:
    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _gathered() -> str:
    lines = ["Smith, J. (2020). Chokepoints and crude."]
    for index in range(80):
        lines.append(
            f"This study {index} presents the measured share of tanker flows "
            f"as well as the named corridor risk for lane {index}."
        )
    return "\n".join(lines) + "\n"


def _exact_words(total: int) -> str:
    base = OPENER.strip()
    have = count_words(base, exclude_citations=False)
    assert have < total
    extra = " ".join(f"point{index}" for index in range(total - have))
    text = f"{base} {extra}"
    assert count_words(text, exclude_citations=False) == total, count_words(
        text, exclude_citations=False
    )
    return text


def _written_first_draft(workspace) -> tuple[str, dict, str, int]:
    seq = open_sequence()
    _save_through(seq, "4b")
    _plant_brief(seq)
    write_upload(
        workspace,
        essay_id=module_code(seq),
        name="smith.md",
        text=_gathered(),
    )
    draft = essay_stage(seq, "5", "draft", OPENER)
    saved = _note_look(seq, "5") or ""
    counted = count_words(saved, exclude_citations=False)
    return seq, draft, saved, counted


def test_stage_five_writes_the_first_draft_inside_the_band(workspace):
    """AC-wd-1. Stage 5 writes the first draft inside the brief's word band.

    A short opening is not stored or shown as the finished first draft.
    The assertion message is the counted word total from this run.
    """
    _seq, draft, saved, counted = _written_first_draft(workspace)
    assert draft["ok"] is True, draft
    assert draft["stored"] is True, draft
    assert 1800 <= counted <= 2200, counted
    assert draft_word_count(_seq, saved) == counted
    assert counted == draft["counted_words"]
    assert saved.strip() != OPENER
    assert draft["next"] != OPENER
    assert draft["chat"] != OPENER
    assert f"Counted words: {counted}." in draft["next"]
    assert STAGE6_OPEN in draft["next"]
    assert FIRST_DRAFT_READY not in draft["next"]


def test_a_short_first_draft_fails_the_length_check(workspace):
    """AC-wd-2. The project fails a first draft below the brief's minimum.

    The 502-word case fails. 1,799 words fail. 1,800 words pass.
    """
    seq = open_sequence()
    _save_through(seq, "4b")
    _plant_brief(seq)
    short = _exact_words(502)
    blocked = first_draft_below_minimum(seq, short)
    assert blocked is not None
    assert blocked["ok"] is False
    assert blocked["counted"] == 502
    assert blocked["minimum"] == 1800
    assert blocked["maximum"] == 2200
    held = essay_stage(seq, "5", "draft", short)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["advanced"] is False
    assert held["counted"] == 502
    assert held["refused"] == "word-band"
    assert "502" in held["reason"]
    assert "1800" in held["reason"]
    assert "2200" in held["reason"]
    assert held.get("next") != short
    assert STAGE6_OPEN not in str(held.get("next") or "")
    assert FIRST_DRAFT_READY not in str(held.get("next") or "")
    assert first_draft_below_minimum(seq, _exact_words(1799)) is not None
    assert first_draft_below_minimum(seq, _exact_words(1800)) is None


def test_the_writer_cannot_clear_its_own_independent_review(workspace):
    """AC-wd-3. The writer cannot mark its own independent review clear."""
    seq = open_sequence()
    refused = essay_review(seq, "6", "PASS", seat="writer")
    assert refused["ok"] is False
    assert refused["stored"] is False
    assert refused["wrote"] is False
    assert refused["writer_clears_left"] == 0
    assert writer_clears_left() == 0
    assert "clear this review" in refused["reason"].casefold()
    again = essay_review(seq, "9", "PASS", seat="writer")
    assert again["ok"] is False
    assert again["writer_clears_left"] == 0


def test_both_shells_carry_the_first_draft_word_band():
    """AC-wd-4. Build covered. Cursor and Grok Build carry the same word-band rule.

    Both shells read the stage 5 rules, and the first draft is written on that shared path.
    """
    shared = stage_settings("5")["rules"]
    build = stage_launch("5")
    cursor = cursor_stage_launch("5")
    assert BAND_RULE in shared
    assert build["settings"]["rules"] == shared
    assert cursor["settings"]["rules"] == shared
    rules = build["command"][build["command"].index("--rules") + 1]
    assert BAND_RULE in rules
    assert BAND_RULE in cursor["settings"]["rules"]
    assert "A short draft is not the finished first draft." in shared


def test_the_shown_first_draft_names_the_counted_words(workspace):
    """AC-wd-5. The shown first draft names a counted total inside the brief band.

    The count is the product's own line for this run, not a caption beside it.
    """
    _seq, draft, saved, counted = _written_first_draft(workspace)
    assert draft["stored"] is True, draft
    assert 1800 <= counted <= 2200, counted
    assert f"Counted words: {counted}." in draft["chat"]
    assert f"Counted words: {counted}." in draft["next"]
    assert draft["chat"] == draft["next"]
    assert count_words(saved, exclude_citations=False) == counted
    assert OPENER not in draft["chat"]
