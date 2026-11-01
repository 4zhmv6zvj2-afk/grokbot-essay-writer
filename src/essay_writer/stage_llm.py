"""Per-stage LLM settings for the essay door.

Fast is off on every stage. Context is 256000 on every stage, including
stage 4b and EQR. Reasoning is xhigh for EQR, the first draft (stage 5),
and stage 4b, and high for feedback and edit (stages 6, 7, and 8).

Other stages:
- 1, 2, 3 are high. The brief, the essay thesis or the report purpose
  and scope, and the plan set the later locks. They are not the deep-read tier.
  A report has no thesis. A report plan holds the central theme.
- 4a is high. Annotations stay on gathered sources. The deep read is 4b.
- 9 is high. Harvard Referencing and invent-forbid apply on
  each citation line.
- 10 is medium. Submit is out of MCP. The door does not submit.

The model is grok-4.7 on every stage. The prompt overlay is the stage
prompt the house already has: the Basics checklist, or the reviewer
instructions for EQR. This module does not add a second prompt.

rules is that same overlay under an apply-every-line header. Cursor tool
text and Grok Build both read it from stage_settings. tracking_file is
the sequence-relative path essay.stage writes.
"""

from __future__ import annotations

from typing import Any

from essay_writer.assignment_gate import assignment_requirements, study_defaults_allowed
from essay_writer.paths import module_code
from essay_writer.textutil import BRIEF_GENRE, brief_file_genre
from essay_writer.writing_basics import (
    CHECKLIST_WALK,
    CHECKLISTS,
    DOOR_STAGES,
    DOOR_WALK,
    GENRE_LOCK_LINE,
    REVISIT_DOOR,
    STAGE7_AGENT,
    STAGE_ORDER,
    basics_lines,
    genre_lock,
    revisit_note,
)

HOUSE_MODEL = "grok-4.7"
CONTEXT_WINDOW = 256_000

# EQR is the reviewer seat, not a second checklist step.
STAGE_KEYS: tuple[str, ...] = STAGE_ORDER + ("eqr",)

STAGE_TITLES: dict[str, str] = {
    "1": "Analyse the task",
    "2": "Essay: Establish a thesis. Report: Establish purpose and scope",
    "3": "Essay: Write an essay plan. Report: Write a report plan",
    "4a": "Annotated bibliography",
    "4b": "Critical review",
    "5": "Write your first draft",
    "6": "Re-read and make changes",
    "7": "Ask for feedback",
    "8": "Edit and redraft",
    "9": "References and citations",
    "10": "Submit the final draft",
    "eqr": "Independent review",
}

# One label once the brief’s genre is known. Chat shows that label.
ESSAY_STAGE_TITLES: dict[str, str] = {
    "2": "Establish a thesis",
    "3": "Write an essay plan",
}
REPORT_STAGE_TITLES: dict[str, str] = {
    "2": "Establish purpose and scope",
    "3": "Write a report plan",
}
DIARY_STAGE_TITLES: dict[str, str] = {
    "2": "Establish the entries",
    "3": "Write a diary plan",
    "8": "Edit and redraft your diary",
}

# Sequence-relative. essay.stage joins this onto the sequence work folder.
POINTER_FILE = "tracking/stage.json"
RULES_SOURCE = "essay_writer.stage_llm.stage_settings"

REASONING: dict[str, str] = {
    "1": "high",
    "2": "high",
    "3": "high",
    "4a": "high",
    "4b": "xhigh",
    "5": "xhigh",
    "6": "high",
    "7": "high",
    "8": "high",
    "9": "high",
    "10": "medium",
    "eqr": "xhigh",
}


def brief_genre(essay_id: str) -> str | None:
    """Essay or report from the assignment requirement list.

    A studied module default applies only in daily use. A brief that is
    silent on writing type leaves the genre unset so the stage names the gap.
    """

    record = assignment_requirements(essay_id)
    if record.get("active") is True:
        prescribed = record.get("format")
        if prescribed == "reflective diary":
            return "diary"
        if isinstance(prescribed, str) and prescribed.strip():
            return prescribed.strip().casefold()
        return None
    parsed = brief_file_genre(essay_id)
    if isinstance(parsed, str) and parsed.strip():
        return parsed.strip().casefold()
    if study_defaults_allowed(essay_id):
        genre = BRIEF_GENRE.get(module_code(essay_id), {}).get("genre")
        if genre in {"essay", "report"}:
            return genre
    return None


def stage_title(stage: str, genre: str | None = None) -> str:
    """Shared label names both genres. A known brief uses one label."""
    if genre == "diary":
        titled = DIARY_STAGE_TITLES.get(stage)
        if titled:
            return titled
    elif genre == "report":
        titled = REPORT_STAGE_TITLES.get(stage)
        if titled:
            return titled
    elif genre == "essay":
        titled = ESSAY_STAGE_TITLES.get(stage)
        if titled:
            return titled
    elif isinstance(genre, str) and genre not in {"essay", "report", "diary"}:
        from essay_writer.brief_contract import has_mapping

        if stage in {"2", "3"}:
            if has_mapping(genre):
                return "Establish the lock" if stage == "2" else "Write the plan"
            return "Brief mapping missing"
    return STAGE_TITLES[stage]


def prompt_overlay(stage: str, genre: str | None = None) -> str:
    """The stage prompt. The checklist walk sits above the bullets."""
    if stage == "eqr":
        from essay_writer.specialists.eqr import REVIEW_PROMPT

        return REVIEW_PROMPT
    if isinstance(genre, str) and genre not in {"essay", "report", "diary"}:
        from essay_writer.brief_contract import (
            MAPPED_TYPE_OVERLAY,
            UNMAPPED_REASON,
            has_mapping,
        )

        if not has_mapping(genre):
            return UNMAPPED_REASON
        return MAPPED_TYPE_OVERLAY
    lines = basics_lines(stage, genre)
    if not lines:
        return ""
    bullets = "\n".join(f"- {line}" for line in lines)
    parts = [CHECKLIST_WALK]
    lock = genre_lock(stage, genre)
    if lock:
        parts.append(lock)
    parts.append(bullets)
    note = revisit_note(stage, genre)
    if note:
        parts.append(note)
    return "\n".join(parts)


def next_stage(stage: str) -> str | None:
    """The following checklist stage. The independent review and stage 10 have none."""
    if stage not in STAGE_ORDER:
        return None
    index = STAGE_ORDER.index(stage)
    if index + 1 >= len(STAGE_ORDER):
        return None
    return STAGE_ORDER[index + 1]


def tracking_file(stage: str) -> str | None:
    """Sequence-relative tracking note. None for the independent review."""
    if stage not in STAGE_ORDER:
        return None
    return f"tracking/{stage}.md"


def stage_rules(stage: str, genre: str | None = None) -> str:
    """Stage guidance the agent applies as rules. The overlay text is inside."""
    if stage not in REASONING:
        raise KeyError(stage)
    title = stage_title(stage, genre)
    text = f"Rules for stage {stage} — {title}. Apply every line.\n{prompt_overlay(stage, genre)}"
    if stage == "7":
        text += "\n" + STAGE7_AGENT
    return text


def stage_settings(stage: str, genre: str | None = None) -> dict[str, Any]:
    if stage not in REASONING:
        raise KeyError(stage)
    following = next_stage(stage)
    return {
        "stage": stage,
        "model": HOUSE_MODEL,
        "reasoning": REASONING[stage],
        "fast": False,
        "context_window": CONTEXT_WINDOW,
        "prompt_overlay": prompt_overlay(stage, genre),
        "rules": stage_rules(stage, genre),
        "next_stage": following,
        "next_stage_title": stage_title(following, genre) if following else None,
        "tracking_file": tracking_file(stage),
        "pointer_file": POINTER_FILE if stage in STAGE_ORDER else None,
        "source": RULES_SOURCE,
    }


def all_stage_settings() -> dict[str, dict[str, Any]]:
    return {stage: stage_settings(stage) for stage in STAGE_KEYS}


def stage_llm_suffix(tool: str) -> str:
    """Compact line for a door that already carries stage prompts."""
    stages = DOOR_STAGES.get(tool, ())
    if not stages:
        return ""
    parts: list[str] = []
    for stage in stages:
        item = stage_settings(stage)
        parts.append(
            f"Basics {stage}: model {item['model']}, reasoning {item['reasoning']}, "
            f"fast off, context {item['context_window']}"
        )
    return (
        " Stage LLM (no-fast): "
        + "; ".join(parts)
        + ". Apply the Basics checklist already on this tool as rules. Follow every line."
    )


def stage_llm_note() -> str:
    return (
        "Per-stage LLM settings live in essay_writer.stage_llm. "
        "The model is grok-4.7 on every stage. Fast is off on every stage (no-fast). "
        "Context is 256000 on every stage, including stage 4b, the first draft, and EQR. "
        "Reasoning is xhigh for stage 4b, the first draft (stage 5), and EQR. "
        "Reasoning is high for feedback and edit (stages 6, 7, and 8). "
        "Stages 1, 2, and 3 are high: the brief, the essay thesis Confirm or the report "
        "purpose and scope, and the plan Confirm set the later locks. "
        "A report has no thesis. A report plan holds the central theme. "
        "Before the save, the chat opens with a short Basics pass. "
        "The first three lines are what the mark scheme scores, the format the brief names, "
        "and the assignment question in the student's words. Later bullets stay short. "
        "Delivering annotation.docx alone is not this pass. "
        "Record the answers in the tracking note. "
        "Do not paste the rest of the Basics checklist into the chat. "
        "Stage 5 stays quiet and does not paste the whole checklist. "
        "After 4a and 4b Confirm, revisit the stage 3 plan before stage 5. "
        "Revisit stage 2 only if research breaks that lock. "
        "If the plan changes, show the delta from the gathered sources and Confirm again "
        "before the first draft. Do not silently rewrite the plan into the draft. "
        "Stage 4a is high: annotations stay on gathered sources, and the deep read is 4b. "
        "Stage 9 is high: Harvard Referencing and invent-forbid on each citation line. "
        "Stage 10 is medium: submit is out of MCP and this door does not submit. "
        "The prompt overlay for a stage is the Basics checklist that stage already has. "
        "Apply that overlay as rules: stage_settings rules. Follow every line. "
        "EQR uses the reviewer instructions as rules. Do not add a second prompt. "
        "essay.stage writes tracking/<stage>.md on the sequence from that guidance. "
        "Confirm saves the final look in that file and advances tracking/stage.json "
        "to the next stage. Stage 10 does not submit."
    )


def first_draft_note() -> str:
    """Writer specialist text. Stage settings do not keep a second copy."""
    from essay_writer.specialists.writer import FIRST_DRAFT_NOTE

    return FIRST_DRAFT_NOTE


def eqr_llm_note() -> str:
    item = stage_settings("eqr")
    return (
        f"Stage LLM for EQR (no-fast, fast off): model {item['model']}, "
        f"reasoning {item['reasoning']}, context {item['context_window']}. "
        "Apply these reviewer instructions as rules. Follow every line.\n"
        f"{item['rules']}"
    )


def stage_rule_suffix(tool: str) -> str:
    """Next-step line so a staged tool loads that stage's rules."""
    stages = DOOR_STAGES.get(tool, ())
    if not stages:
        return ""
    parts: list[str] = []
    for stage in stages:
        following = next_stage(stage)
        if following:
            hop = f"stage {following} — {stage_title(following)}"
        else:
            hop = "no further stage"
        if stage == "5":
            move = (
                "When that draft is stored, essay.stage starts stage 6. "
                "There is no Confirm card between stage 5 and stage 6."
            )
        else:
            move = f"On confirm, essay.stage saves the final look there and moves to {hop}."
        parts.append(
            f"Apply stage {stage} — {stage_title(stage)} guidance as rules "
            f"(stage_settings rules). Follow every line. "
            f"essay.stage writes tracking/{stage}.md from that guidance. "
            f"{move}"
        )
    return " " + " ".join(parts) + " " + GENRE_LOCK_LINE


def stage_index_line() -> str:
    """Every writing stage, its tracking file, and the stage that follows."""
    parts: list[str] = []
    for stage in STAGE_ORDER:
        following = next_stage(stage)
        if following:
            hop = f" Next: {following} — {stage_title(following)}."
        else:
            hop = " Next: none. The tool does not submit."
        parts.append(
            f"Stage {stage} — {stage_title(stage)}. "
            f"File: tracking/{stage}.md.{hop}"
        )
    return " ".join(parts)


def _room_confirm_note() -> str:
    from essay_writer.build_status import MID_BUILD_DOOR
    from essay_writer.specialists.grok_bot import (
        ROOM_CONFIRM_PATH,
        STAGE7_AFTER_ANSWERS,
        STAGE_CONFIRM_EACH,
    )

    return (
        ROOM_CONFIRM_PATH
        + " "
        + STAGE_CONFIRM_EACH
        + " "
        + STAGE7_AFTER_ANSWERS
        + " "
        + MID_BUILD_DOOR
    )


def stage_tool_description() -> str:
    from essay_writer.fo_chat_locks import FO_STAGES_ROLL_FORWARD

    return (
        FO_STAGES_ROLL_FORWARD
        + " "
        "Essay: essay.stage. Draft shows a chat card (kind confirm) with the sequence id, "
        "the stage, the save line, and actions Confirm and Not yet. "
        "Send confirmPhase confirm only with cardAction confirm and cardDigest from that card, "
        "and only after the person picks Confirm on the card. "
        "A typed ok, yes, or confirm is not a pick. "
        "When a draft card is waiting, show that Confirm card again, with its digest, "
        "only while the pointer still has that stage as current and the stage is not saved. "
        "If the stage is in saved, or current is a later stage, do not show that card. "
        "Say the tool's next and the card the tool returned for current. "
        "Essay Bot may only show the Confirm card the door returned. "
        "It does not pick the next stage itself. "
        + _room_confirm_note()
        + " "
        "Typed text does not write tracking/stage.json. "
        "Not yet leaves the step unsaved. "
        "Never silent. "
        "After Stage 3 is saved, the reply may include one encourage question. "
        "Say that one question and its choices. Do not ask another question in the same turn. "
        "When the person answers or skips, call essay.stage with encourageChoice set to that reply. "
        "Do not send encourageChoice on the save that locks the plan. "
        "Silence does not block the saved stage and does not add a detail the person did not give. "
        "On a copied sequence, stage 4a researches first, then each saved paper is kept, dropped, or replaced. "
        "Call essay.stage with paperChoice set to the paper and that choice. "
        "A dropped paper leaves the list only. The file stays. "
        "A kept paper that already has a critical note is not gathered again. "
        "essay_id is a sequence id such as MOD1011AA-5. "
        "stage is 1, 2, 3, 4a, 4b, 5, 6, 7, 8, 9, or 10. "
        "Load stage_settings rules for that stage and apply every line before the stage output. "
        "The guidance is rules. Follow every line. "
        "Draft writes tracking/<stage>.md on the sequence from that guidance. "
        "A card pick saves the final look in that file, then tracking/stage.json moves to the next stage. "
        "Stage 5 stores on the draft and starts stage 6. There is no Confirm card between stage 5 and stage 6. "
        "The reply started.stage is 6, with master_ask. "
        "Stages 7, 8, and 9 keep their own cards. One card does not run the later stages. "
        "Stage 10 confirm does not submit. "
        "look is an optional plain note of the checklist answers. "
        "Omit it and the final look is the stage guidance. "
        "A changed look needs a fresh draft. "
        + DOOR_WALK
        + " "
        + GENRE_LOCK_LINE
        + " "
        + REVISIT_DOOR
        + " "
        + stage_index_line()
    )


def stage_rules_briefing() -> str:
    """Writer briefing. Each stage's rules, tracking file, and next stage."""
    chunks = [
        "Stage rules: before the save, the chat opens with a short Basics pass. "
        "The first three lines are what the mark scheme scores, the format the brief names, "
        "and the assignment question in the student's words. Later bullets stay short. "
        "Delivering annotation.docx alone is not this pass. "
        "Record the answers in the tracking note. "
        "Do not paste the rest of the Basics checklist into the chat. "
        "Stage 5 stays quiet and does not paste the whole checklist. "
        "Student chat is warm, helpful, encouraging, and concise: only what the person must know. "
        "Limits the person must know, such as Stage 1 limiting conditions, always appear in that prose. "
        "Load stage_settings rules and apply every line. "
        "Do not treat the checklist as an optional note. "
        "The lines below are the rules."
    ]
    for stage in STAGE_ORDER:
        item = stage_settings(stage)
        following = item["next_stage"]
        if following:
            hop = (
                f"Next stage after the approved save: {following} — "
                f"{item['next_stage_title']}."
            )
        else:
            hop = "No next stage. The tool does not submit."
        chunks.append(
            f"Stage {stage} — {stage_title(stage)}. "
            f"Tracking file: {item['tracking_file']}. {hop}\n"
            f"{item['rules']}"
        )
    review = stage_settings("eqr")
    chunks.append(
        "Independent review. Apply these rules. Follow every line. "
        "This seat does not write the tracking note and does not advance the stage.\n"
        f"{review['rules']}"
    )
    return "\n\n".join(chunks)


def _settings_cover_the_checklists() -> None:
    """Import-time guard: every Basics stage has a settings row."""
    missing = set(CHECKLISTS) - set(REASONING)
    if missing:
        raise RuntimeError(f"stage LLM settings missing {sorted(missing)}")


_settings_cover_the_checklists()
