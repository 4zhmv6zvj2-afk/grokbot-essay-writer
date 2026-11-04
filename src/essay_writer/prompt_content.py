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

__all__ = [
    "ANTI_GLUE", "VOICE_LIMIT", "PLAIN_WORDS", "TEMPLATE_OPENERS", "STUDENT_VOICE",
    "EVIDENCE_STRENGTH", "OPEN_GAP", "MARK_TABLE_LEAN", "CRAFT_COMMITMENT", "CRAFT_ANCHOR",
    "CRAFT_REVISE", "CRAFT_SOURCES", "CRAFT_REFUSAL", "CRAFT_LINES",
    "ENCOURAGE_FACT_RULE", "CHECKLISTS", "SHARED_STAGES", "GENRE_ADDITIONS",
    "MCP_DOWN_SPEECH", "SERVER_BASICS_NOTE", "GENRE_LOCK_LINE", "STAGE7_AGENT",
    "SHARED_REVISIT", "REPORT_REVISIT", "ESSAY_REVISIT", "DIARY_REVISIT", "REVISIT_DOOR",
]
