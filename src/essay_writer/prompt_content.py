"""Content loaded from the prompts bundle. No composition logic."""

from __future__ import annotations

from essay_writer.prompt_loader import bullets, sections

_CRAFT = sections("craft/voice.md")

ANTI_GLUE = _CRAFT["anti_glue"]
VOICE_LIMIT = _CRAFT["voice_limit"]
PLAIN_WORDS = _CRAFT["plain_words"]
TEMPLATE_OPENERS = _CRAFT["template_openers"]
STUDENT_VOICE = _CRAFT["student_voice"]
EVIDENCE_STRENGTH = _CRAFT["evidence_strength"]
OPEN_GAP = _CRAFT["open_gap"]
MARK_TABLE_LEAN = _CRAFT["mark_table_lean"]
CRAFT_COMMITMENT = _CRAFT["craft_commitment"]
CRAFT_ANCHOR = _CRAFT["craft_anchor"]
CRAFT_REVISE = _CRAFT["craft_revise"]
CRAFT_SOURCES = _CRAFT["craft_sources"]
CRAFT_REFUSAL = _CRAFT["craft_refusal"]
ENCOURAGE_FACT_RULE = _CRAFT["encourage_fact_rule"]
CRAFT_LINES = (CRAFT_COMMITMENT, CRAFT_ANCHOR, CRAFT_REVISE, CRAFT_SOURCES, CRAFT_REFUSAL)

# The craft sections each writing stage renders. Stages 5 and 8 carry the full
# set; stages 6 and 7 carry the shared voice limits. The section bodies live in
# craft/voice.md, so editing that file changes the runtime rules.
CRAFT_SECTIONS: dict[str, tuple[str, ...]] = {
    "5": (
        "anti_glue",
        "voice_limit",
        "plain_words",
        "template_openers",
        "student_voice",
        "evidence_strength",
        "open_gap",
        "mark_table_lean",
        "craft_commitment",
        "craft_anchor",
        "craft_revise",
        "craft_sources",
        "craft_refusal",
        "encourage_fact_rule",
        "content_check",
        "phrasebank_pointer",
    ),
    "6": (
        "anti_glue",
        "voice_limit",
        "plain_words",
        "template_openers",
        "student_voice",
        "encourage_fact_rule",
    ),
    "7": (
        "anti_glue",
        "voice_limit",
        "plain_words",
        "template_openers",
        "student_voice",
        "encourage_fact_rule",
    ),
    "8": (
        "anti_glue",
        "voice_limit",
        "plain_words",
        "template_openers",
        "student_voice",
        "evidence_strength",
        "open_gap",
        "mark_table_lean",
        "craft_commitment",
        "craft_anchor",
        "craft_revise",
        "craft_sources",
        "craft_refusal",
        "encourage_fact_rule",
        "content_check",
        "edit_recheck",
    ),
}
CRAFT_BY_STAGE = {
    stage: tuple(_CRAFT[key] for key in keys) for stage, keys in CRAFT_SECTIONS.items()
}

_STAGE_FILES = {
    "1": "01.md", "2": "02.md", "3": "03.md", "4a": "04a.md", "4b": "04b.md",
    "5": "05.md", "6": "06.md", "7": "07.md", "8": "08.md", "9": "09.md", "10": "10.md",
}
SHARED_STAGES = frozenset({"1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9", "10"})


CHECKLISTS = {
    stage: bullets(f"stages/{name}", "shared") for stage, name in _STAGE_FILES.items()
}


def _genre_additions(genre: str, stage: str) -> tuple[str, ...]:
    try:
        return bullets(f"genres/{genre}.md", stage)
    except KeyError:
        return ()


GENRE_ADDITIONS = {
    (genre, stage): _genre_additions(genre, stage)
    for genre in ("essay", "report", "diary")
    for stage in SHARED_STAGES
}
_SHARED = sections("front_office/chat.md")
MCP_DOWN_SPEECH = _SHARED["mcp_down_speech"]
SERVER_BASICS_NOTE = _SHARED["server_basics_note"]
GENRE_LOCK_LINE = _SHARED["genre_lock_line"]
STAGE7_AGENT = _SHARED["stage7_agent"]
SHARED_REVISIT = _SHARED["shared_revisit"]
REPORT_REVISIT = _SHARED["report_revisit"]
ESSAY_REVISIT = _SHARED["essay_revisit"]
DIARY_REVISIT = _SHARED["diary_revisit"]
REVISIT_DOOR = _SHARED["revisit_door"]

# Non-craft rules that more than one stage file used to carry a copy of. They
# live once here and stage_llm renders the ones a stage needs. The plain-English
# gloss rule is already in CHECKLIST_WALK (front_office/chat.md), which every
# stage overlay starts with, so it has no section here.
PRECEDENCE = _SHARED["precedence"]
SHARED_STAGE_SECTIONS: dict[str, str] = {
    "research_path": _SHARED["shared_research_path"],
    "word_safety": _SHARED["shared_word_safety"],
    "first_draft_rewrite": _SHARED["shared_first_draft_rewrite"],
}
# Each stage renders one definition of every rule it needs. A stage can render
# more than one shared section; precedence renders on every checklist stage.
SHARED_STAGE_RULES: dict[str, tuple[str, ...]] = {
    "4a": ("research_path",),
    "4b": ("research_path",),
    "6": ("word_safety",),
    "7": ("first_draft_rewrite",),
    "8": ("word_safety",),
    "9": ("first_draft_rewrite",),
}
SHARED_STAGE_LINES: dict[str, tuple[str, ...]] = {
    stage: tuple(SHARED_STAGE_SECTIONS[key] for key in keys)
    for stage, keys in SHARED_STAGE_RULES.items()
}

__all__ = [
    "ANTI_GLUE", "VOICE_LIMIT", "PLAIN_WORDS", "TEMPLATE_OPENERS", "STUDENT_VOICE",
    "EVIDENCE_STRENGTH", "OPEN_GAP", "MARK_TABLE_LEAN", "CRAFT_COMMITMENT", "CRAFT_ANCHOR",
    "CRAFT_REVISE", "CRAFT_SOURCES", "CRAFT_REFUSAL", "CRAFT_LINES",
    "CRAFT_SECTIONS", "CRAFT_BY_STAGE",
    "ENCOURAGE_FACT_RULE", "CHECKLISTS", "SHARED_STAGES", "GENRE_ADDITIONS",
    "MCP_DOWN_SPEECH", "SERVER_BASICS_NOTE", "GENRE_LOCK_LINE", "STAGE7_AGENT",
    "SHARED_REVISIT", "REPORT_REVISIT", "ESSAY_REVISIT", "DIARY_REVISIT", "REVISIT_DOOR",
    "PRECEDENCE", "SHARED_STAGE_SECTIONS", "SHARED_STAGE_RULES", "SHARED_STAGE_LINES",
]
