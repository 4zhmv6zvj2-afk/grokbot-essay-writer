"""Writing-base checklists per stage.

Canonical prose, clue words, report sections, and source-use rules:
docs/academic-writing-helpers.md. This module is what the BO LLM sees on doors
and server instructions. The bullets match that note. They are not a paste of
the whole source page.
"""

from __future__ import annotations

from essay_writer.prompt_content import (  # noqa: F401
    ANTI_GLUE,
    CHECKLISTS,
    CRAFT_ANCHOR,
    CRAFT_COMMITMENT,
    CRAFT_LINES,
    CRAFT_REFUSAL,
    CRAFT_REVISE,
    CRAFT_SOURCES,
    DIARY_REVISIT,
    ENCOURAGE_FACT_RULE,
    ESSAY_REVISIT,
    EVIDENCE_STRENGTH,
    GENRE_ADDITIONS,
    GENRE_LOCK_LINE,
    MARK_TABLE_LEAN,
    OPEN_GAP,
    PLAIN_WORDS,
    REPORT_REVISIT,
    REVISIT_DOOR,
    SERVER_BASICS_NOTE,
    SHARED_REVISIT,
    SHARED_STAGES,
    STAGE7_AGENT,
    STUDENT_VOICE,
    TEMPLATE_OPENERS,
    VOICE_LIMIT,
)
from essay_writer.specialists.grok_bot import CHECKLIST_WALK, DOOR_WALK, MCP_DOWN_SPEECH  # noqa: F401

STAGE_ORDER: tuple[str, ...] = (
    "1",
    "2",
    "3",
    "4a",
    "4b",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
)
DOOR_STAGES: dict[str, tuple[str, ...]] = {
    "essay.originals": ("1",),
    "essay.research.summary": ("4a",),
    "essay.research.full": ("4a", "4b"),
    "essay.pack.validate": ("5",),
    "essay.pack.render_word": ("5", "7", "8", "9"),
    "essay.revise": ("6", "7", "8"),
}
BASICS_MARKER = "Basics checklist"


def voice_limit_sha() -> str:
    """Stable id for the stage 5–8 voice limit. PR bodies cite this."""
    import hashlib

    return hashlib.sha256(VOICE_LIMIT.encode("utf-8")).hexdigest()


def basics_lines(stage: str, genre: str | None = None) -> tuple[str, ...]:
    """Shared stage bullets plus the additive genre section."""
    shared = CHECKLISTS.get(stage, ())
    if genre in {"essay", "report", "diary"}:
        return shared + GENRE_ADDITIONS.get((genre, stage), ())
    return shared


def revisit_note(stage: str, genre: str | None = None) -> str:
    """Post-research plan check. Stage 2 reopens only when the research breaks the lock."""
    if stage not in {"2", "3", "4a", "4b", "5"}:
        return ""
    if stage == "2":
        if genre == "report":
            return (
                "After research is saved, reopen purpose and scope only if those gathered sources break them. "
                "A thin edit of the central theme stays on the plan. "
                "If purpose and scope or the central theme breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        if genre == "essay":
            return (
                "After research is saved, reopen the thesis only if those gathered sources break it. "
                "A thin edit stays on the plan. "
                "If the thesis breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        if genre == "diary":
            return (
                "After research is saved, reopen the entries only if those gathered sources break a decision or an event. "
                "A thin edit stays on the plan. "
                "If a decision or an event breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        return (
            "After research is saved, reopen this lock only if those gathered sources break it. "
            "On an essay the lock is the thesis. On a report the lock is purpose and scope. "
            "A thin edit of the central theme stays on the plan. "
            "If the lock or the central theme breaks, approve this stage again and then approve the plan again before the first draft. "
            "Do not silently rewrite the plan into the draft."
        )
    if genre == "report":
        return REPORT_REVISIT
    if genre == "essay":
        return ESSAY_REVISIT
    if genre == "diary":
        return DIARY_REVISIT
    return SHARED_REVISIT


def genre_lock(stage: str, genre: str | None = None) -> str:
    """Front of the shared overlay. A known genre uses its own bullets instead."""
    if genre in {"essay", "report", "diary"} or stage not in {"2", "3"}:
        return ""
    if stage == "2":
        return (
            "Chat shows one label, the brief’s. "
            "An essay locks a thesis. "
            "A report locks purpose and scope. A report has no thesis."
        )
    return (
        "Chat shows one label, the brief’s. "
        "An essay plan holds the thesis. "
        "A report plan holds the central theme and the brief’s headed sections. "
        "A report has no thesis."
    )


def basics_block_markdown(stage: str) -> str:
    """Markdown block under a stage heading in docs."""
    lines = basics_lines(stage)
    if not lines:
        return ""
    bullets = "\n".join(f"- {line}" for line in lines)
    return f"**{BASICS_MARKER}:**\n{bullets}\n"


def basics_prompt_suffix(tool: str) -> str:
    """Short suffix for MCP door descriptions the BO LLM reads."""
    stages = DOOR_STAGES.get(tool, ())
    if not stages:
        return ""
    parts: list[str] = []
    for stage in stages:
        items = basics_lines(stage)
        if items:
            joined = "; ".join(items)
            parts.append(f"{BASICS_MARKER} (Basics {stage}): {joined}")
    if not parts:
        return ""
    text = " " + " ".join(parts) + " " + DOOR_WALK
    if set(stages) & {"4a", "4b", "5"}:
        text += " " + REVISIT_DOOR
    return text
