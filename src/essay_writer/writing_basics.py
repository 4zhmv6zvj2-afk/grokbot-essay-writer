"""Writing-base checklists per stage.

Canonical prose, clue words, report sections, and source-use rules:
docs/academic-writing-helpers.md. The bullets are the stage's Basics checklist,
not a paste of the whole source page. Shared voice and craft rules are rendered
once from prompts/craft/voice.md by stage_llm; this module does not re-export
them.
"""

from __future__ import annotations

from essay_writer.prompt_content import (
    CHECKLISTS,
    DIARY_REVISIT,
    ESSAY_REVISIT,
    GENRE_ADDITIONS,
    REPORT_REVISIT,
    SHARED_REVISIT,
)

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
