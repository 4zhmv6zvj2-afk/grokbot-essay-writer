"""Stage 3 encourage asks and writer/reviewer voice limits. Stable ids: AC1–AC7.

Fixture: tests/fixtures/encourage-plan-v1.txt (encourage-plan-v1).
Brief fixture: tests/fixtures/encourage-brief-reflection-v1.txt.
Build covered: Cursor cursor_stage_launch and Grok Build stage_launch both
read essay_writer.stage_llm.stage_settings, including the voice limit on
stages 5–8 and the reviewer limit on eqr. Pax: skipped (prompt / FO copy only).
"""

import json
from pathlib import Path

from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.encourage import (
    DEPTH_PROMPT,
    EXAMPLE_PROMPT,
    SURPRISED_PROMPT,
    ask_order,
    student_facts,
)
from essay_writer.shells import front_office_call
from essay_writer.specialists.eqr import REVIEW_LIMIT, REVIEW_PROMPT, review_limit_sha
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import (
    ANTI_GLUE,
    ENCOURAGE_FACT_RULE,
    VOICE_LIMIT,
    voice_limit_sha,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE_ID = "encourage-plan-v1"
PLAN = (REPO / "tests" / "fixtures" / "encourage-plan-v1.txt").read_text(encoding="utf-8")
BRIEF = (REPO / "tests" / "fixtures" / "encourage-brief-reflection-v1.txt").read_text(encoding="utf-8")
STAGES = ("5", "6", "7", "8")
GENRES = (None, "diary", "essay", "report")
POISON = (
    "Chokepoints do not constrain the corridor",
    "The Strait does not handle flows",
    "A theme that does not constrain the corridor",
)
OWN = "the night shift handover"
INVENTED = "invented case about NASA"


def _plant_brief(workspace: Path) -> None:
    folder = workspace / "Essay-writer" / "MOD1004AA"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def _look(seq: str, extra: str) -> str:
    from essay_writer.specialists.grok_bot import basics_pass_lines

    return "\n".join(basics_pass_lines(seq)) + "\n" + extra


def _confirm_plan(workspace: Path) -> tuple[str, dict]:
    _plant_brief(workspace)
    seq = open_sequence()
    for stage in ("1", "2"):
        draft = essay_stage(seq, stage, "draft", _look(seq, "Kept."))
        assert draft["ok"] is True, draft
        saved = essay_stage(seq, stage, "confirm", _look(seq, "Kept."), **picked(draft))
        assert saved["stored"] is True, saved
    draft = essay_stage(seq, "3", "draft", _look(seq, PLAN))
    assert draft["ok"] is True, draft
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "3",
            "confirmPhase": "confirm",
            "look": _look(seq, PLAN),
            **picked(draft),
        },
    )
    assert saved["stored"] is True, saved
    assert saved["advanced"] is True, saved
    return seq, saved


def _labels(ask: dict) -> list[str]:
    return [item["label"] for item in ask["options"]]


def _prompts(blob: str) -> list[str]:
    return [prompt for prompt in (DEPTH_PROMPT, EXAMPLE_PROMPT, SURPRISED_PROMPT) if prompt in blob]


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def test_ac1_one_encourage_ask_after_plan_confirm(workspace):
    """AC1. Fixture encourage-plan-v1. One ask, sections from the locked plan, type-own, skip."""
    assert FIXTURE_ID in (REPO / "tests" / "fixtures" / "encourage-plan-v1.txt").name
    seq, saved = _confirm_plan(workspace)
    encourage = saved["encourage"]
    assert encourage["count"] == 1
    ask = encourage["ask"]
    assert ask["id"] == "depth"
    assert ask["prompt"] == DEPTH_PROMPT
    labels = _labels(ask)
    assert "Supply chain context" in labels
    assert "Analysis and findings" in labels
    assert "Conclusion" in labels
    assert "Port delays" in labels
    assert labels[-2:] == ["Type your own", "Skip"]
    for label in labels[:-2]:
        assert label in PLAN or label in BRIEF
    speech = saved["next"]
    assert DEPTH_PROMPT in speech
    assert "Type your own" in speech
    assert "Skip" in speech
    assert _prompts(speech) == [DEPTH_PROMPT]
    assert _prompts(json.dumps(encourage)) == [DEPTH_PROMPT]
    assert student_facts(seq) == {}
    assert load_pointer(seq)["current"] == "4a"
    assert "3" in load_pointer(seq)["saved"]


def test_ac2_second_ask_only_after_answer_or_skip(workspace):
    """AC2. Silence keeps the same ask. Skip opens the next one. Never a four-ask dump."""
    seq, saved = _confirm_plan(workspace)
    assert saved["encourage"]["count"] == 1
    assert len(ask_order(seq)) == 3
    assert len(ask_order(seq)) < 4
    silent = essay_stage(seq, "3", encourageChoice="")
    assert silent["blocked"] is False
    assert silent["invented"] is False
    assert silent["silence"] is True
    assert silent["accepted"] is False
    assert silent["encourage"]["count"] == 1
    assert silent["encourage"]["ask"]["id"] == "depth"
    assert _prompts(silent["next"]) == [DEPTH_PROMPT]
    assert student_facts(seq) == {}
    assert load_pointer(seq)["current"] == "4a"
    skipped = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "3", "encourageChoice": "skip"},
    )
    assert skipped["blocked"] is False
    assert skipped["invented"] is False
    assert skipped["encourage"]["count"] == 1
    assert skipped["encourage"]["ask"]["id"] == "example"
    assert _prompts(skipped["next"]) == [EXAMPLE_PROMPT]
    assert "Strait of Hormuz" in _labels(skipped["encourage"]["ask"])
    assert load_pointer(seq)["current"] == "4a"
    again = essay_stage(seq, "3", encourageChoice="skip")
    assert again["encourage"]["ask"]["id"] == "surprised"
    assert _prompts(again["next"]) == [SURPRISED_PROMPT]
    assert again["encourage"]["count"] == 1
    done = essay_stage(seq, "3", encourageChoice="skip")
    assert done["encourage"]["count"] == 0
    assert _prompts(done["next"]) == []
    assert student_facts(seq) == {}


def test_ac3_skip_and_silence_do_not_block_or_invent(workspace):
    """AC3. Skip and silence leave the stage saved. Later stages gain no invented detail."""
    seq = open_sequence()
    answered = open_sequence()
    look = "Saved from the brief."
    for stage in ("1", "2", "3", "4a", "4b", "5"):
        text = PLAN if stage == "3" else look
        draft = essay_stage(seq, stage, "draft", text)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["student_detail"] == {}
            assert "Strait of Hormuz" not in json.dumps(draft["student_detail"])
            assert INVENTED not in json.dumps(draft)
            assert "Strait of Hormuz" not in (draft.get("next") or "")
            assert draft["stored"] is True
            break
        saved = essay_stage(seq, stage, "confirm", text, **picked(draft))
        assert saved["stored"] is True, saved
        if stage == "3":
            assert saved["advanced"] is True
            assert student_facts(seq) == {}
            silent = essay_stage(seq, "3", encourageChoice="")
            assert silent["blocked"] is False
            assert silent["invented"] is False
            assert student_facts(seq) == {}
            assert load_pointer(seq)["current"] == "4a"

    for stage in ("1", "2"):
        draft = essay_stage(answered, stage, "draft", look)
        saved = essay_stage(answered, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
    draft = essay_stage(answered, "3", "draft", PLAN)
    saved = essay_stage(answered, "3", "confirm", PLAN, **picked(draft))
    assert saved["stored"] is True, saved
    owned = essay_stage(answered, "3", encourageChoice=f"type-own: {OWN}")
    assert owned["accepted"] is True
    assert owned["invented"] is False
    assert student_facts(answered) == {"depth": OWN}
    refused = essay_stage(answered, "3", encourageChoice=INVENTED)
    assert refused["accepted"] is False
    assert refused["invented"] is False
    assert student_facts(answered) == {"depth": OWN}
    assert refused["encourage"]["ask"]["id"] == "example"
    skipped = essay_stage(answered, "3", encourageChoice="skip")
    assert skipped["invented"] is False
    assert "example" not in student_facts(answered)
    assert INVENTED not in student_facts(answered).values()
    for stage in ("4a", "4b"):
        draft = essay_stage(answered, stage, "draft", look)
        if stage == "4a":
            plant_gathered_source(answered)
        saved = essay_stage(answered, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
    stage5 = essay_stage(answered, "5", "draft", look)
    assert stage5["ok"] is True, stage5
    assert stage5["student_detail"] == {"depth": OWN}
    assert INVENTED not in json.dumps(stage5["student_detail"])
    assert "Strait of Hormuz" not in json.dumps(stage5["student_detail"])
    assert OWN not in stage5["rules"]
    number = answered.rsplit("-", 1)[1]
    note = (
        workspace / "Essay-writer" / "MOD1004AA" / "sequences" / number / "tracking" / "5.md"
    ).read_text(encoding="utf-8")
    final = note.split("## Final look", 1)[1]
    assert OWN not in final
    assert "Strait of Hormuz" not in final
    assert INVENTED not in final


def test_ac4_options_do_not_contradict_the_locked_plan(workspace):
    """AC4. Fixture encourage-plan-v1. Choices that fight the theme or the research stay out."""
    seq, saved = _confirm_plan(workspace)
    depth = _labels(saved["encourage"]["ask"])
    for poison in POISON:
        assert poison not in depth
    example = essay_stage(seq, "3", encourageChoice="skip")
    example_labels = _labels(example["encourage"]["ask"])
    assert "Strait of Hormuz" in example_labels
    for poison in POISON:
        assert poison not in example_labels
    surprised = essay_stage(seq, "3", encourageChoice="skip")
    surprised_labels = _labels(surprised["encourage"]["ask"])
    assert surprised["encourage"]["ask"]["id"] == "surprised"
    for poison in POISON:
        assert poison not in surprised_labels
    assert "Supply chain context" in surprised_labels
    for label in depth[:-2] + example_labels[:-2] + surprised_labels[:-2]:
        assert label in PLAN or label in BRIEF


def test_ac5_writer_voice_limits_on_stages_5_to_8():
    """AC5. Rhythm, connectors, diary opening, no planted-error instruction. Prompt text only."""
    source = (REPO / "src" / "essay_writer" / "writing_basics.py").read_text(encoding="utf-8")
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    for sentence in (
        "Vary the sentence rhythm.",
        "Cut AI connectors such as Furthermore, Moreover, In conclusion, and It is important to note.",
        "Do not open a diary with a polished line such as In this reflective diary I will.",
        "A diary may be slightly fragmented.",
        "Prefer a concrete detail over an abstract line.",
        "Do not plant grammar errors.",
    ):
        assert sentence in source
        assert sentence in helpers
    assert VOICE_LIMIT in helpers
    assert voice_limit_sha() == __import__("hashlib").sha256(VOICE_LIMIT.encode("utf-8")).hexdigest()
    assert len(voice_limit_sha()) == 64
    folded = source.casefold()
    for banned in ("plant a grammar error", "add a typo", "deliberate mistake", "insert an error"):
        assert banned not in folded
    for stage in STAGES:
        for genre in GENRES:
            text = stage_settings(stage, genre)["rules"]
            assert "Vary the sentence rhythm." in text
            assert "Furthermore" in text
            assert "Moreover" in text
            assert "In conclusion" in text
            assert "It is important to note" in text
            assert "In this reflective diary I will" in text
            assert "slightly fragmented" in text
            assert "Harvard Referencing" in text
            assert "Prefer a concrete detail over an abstract line." in text
            assert "Do not plant grammar errors." in text
            assert ENCOURAGE_FACT_RULE in text
            assert ANTI_GLUE in text
            assert student_surface_hits(stage_settings(stage, genre)["prompt_overlay"]) == []
    gates = (REPO / "src" / "essay_writer" / "gates.py").read_text(encoding="utf-8")
    validate = (REPO / "src" / "essay_writer" / "validate.py").read_text(encoding="utf-8")
    assert "VOICE_LIMIT" not in gates
    assert "VOICE_LIMIT" not in validate
    assert "Furthermore" not in gates


def test_ac6_reviewer_limits_facts_structure_and_citations():
    """AC6. Reviewer prompt stays on facts, structure, and citations. No elegance polish."""
    source = (REPO / "src" / "essay_writer" / "specialists" / "eqr.py").read_text(encoding="utf-8")
    assert REVIEW_LIMIT in REVIEW_PROMPT
    assert REVIEW_LIMIT in source
    assert review_limit_sha() == __import__("hashlib").sha256(REVIEW_LIMIT.encode("utf-8")).hexdigest()
    assert "Do not polish voice, elegance, or parallelism." in REVIEW_PROMPT
    assert "Keep the student's voice and the writer's voice." in REVIEW_PROMPT
    folded = REVIEW_PROMPT.casefold()
    for banned in ("improve the elegance", "more elegant", "smooth the voice", "fix the parallelism"):
        assert banned not in folded
    assert "It does not check format." in REVIEW_PROMPT
    assert "Format and citations stay with the writer." in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []
    assert stage_settings("eqr")["prompt_overlay"] == REVIEW_PROMPT


def test_ac7_build_covered_cursor_and_grok_launch_the_same_limits():
    """AC7. Build covered. Both mid-office shells read the same stage_settings row."""
    for stage in STAGES:
        shared = stage_settings(stage)["rules"]
        build = stage_launch(stage)
        cursor = cursor_stage_launch(stage)
        assert build["settings"]["rules"] == shared
        assert cursor["settings"]["rules"] == shared
        assert VOICE_LIMIT in _rules(build["command"])
        assert VOICE_LIMIT in cursor["settings"]["rules"]
        assert ANTI_GLUE in _rules(build["command"])
        assert build["source"] == cursor["source"] == "essay_writer.stage_llm.stage_settings"
    review = stage_settings("eqr")["rules"]
    build = stage_launch("eqr")
    cursor = cursor_stage_launch("eqr")
    assert REVIEW_LIMIT in review
    assert build["settings"]["rules"] == review
    assert cursor["settings"]["rules"] == review
    assert REVIEW_LIMIT in _rules(build["command"])
    assert REVIEW_LIMIT in cursor["settings"]["rules"]
