"""Stage rules are trimmed copies. The checklist stays a flat bullet list.

Opaque ids. The acceptance label for each case is in the docstring.
"""

from __future__ import annotations

import inspect

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.harvard_4a import ANNOTATION_SENTENCES, FOUR_A_FORMAT
from essay_writer.prompt_loader import bullets
from essay_writer.prompt_loader import sections as prompt_sections
from essay_writer.stage_llm import stage_settings
from essay_writer.writing_basics import CHECKLISTS, basics_lines

STUDENT_VOICE = prompt_sections("craft/voice.md")["student_voice"]

OWNERSHIP = "The draft is model-assisted; the student owns what they submit."
OPENER = "Do not open with a general sentence built only from the topic nouns."
CLOSER = "Do not close with an automatic In conclusion that only restates the topic."
MARK_SCHEME_WORDS = "Keep mark-scheme words the brief uses, and gloss each one in plain English the first time."
CHATBOT = "If a chatbot produced"


def test_case_1():
    """AC1: Duplicated rules were merged or relocated. Bullets stay flat.

    The stage 5 shared checklist is 12 bullets. The ownership sentence lives
    once, in the craft rule. The essay opener and closer bans live once, in
    the anti-glue rule. The annotation how-to lives once, on the annotation
    bullet. The chatbot rewrite lives once, in the craft revise rule. Cursor
    and Grok Build read those same rules. The prompt loader still returns one
    flat bullet per line that starts with a dash.
    """
    assert len(CHECKLISTS["5"]) == 12
    assert CHECKLISTS["5"] == bullets("stages/05.md", "shared")
    assert all("\n" not in line for line in CHECKLISTS["5"])
    assert OWNERSHIP not in "\n".join(CHECKLISTS["5"])
    assert "does not read or edit Word" in "\n".join(CHECKLISTS["5"])
    assert "Chat for this step stays quiet" in "\n".join(CHECKLISTS["5"])
    stage5 = stage_settings("5")["rules"]
    assert stage5.count(OWNERSHIP) == 1
    assert OWNERSHIP in STUDENT_VOICE
    essay = basics_lines("5", "essay")
    assert OPENER not in "\n".join(essay)
    assert CLOSER not in "\n".join(essay)
    essay_rules = stage_settings("5", "essay")["rules"]
    assert essay_rules.count(OPENER) == 1
    assert essay_rules.count(CLOSER) == 1
    assert "road map of the main ideas" in "\n".join(essay)
    assert MARK_SCHEME_WORDS in ANNOTATION_SENTENCES
    assert MARK_SCHEME_WORDS not in FOUR_A_FORMAT
    assert "what the paper did" in FOUR_A_FORMAT
    overlay_4a = stage_settings("4a")["prompt_overlay"]
    assert overlay_4a.count(MARK_SCHEME_WORDS) == 1
    assert FOUR_A_FORMAT in overlay_4a
    stage8 = stage_settings("8")["rules"]
    assert stage8.count(CHATBOT) == 1
    assert CHATBOT not in "\n".join(CHECKLISTS["8"])
    for stage, lines in CHECKLISTS.items():
        for line in lines:
            assert "\n" not in line, stage
            folded = line.casefold()
            assert not folded.startswith("must-do"), stage
            assert not folded.startswith("must-not"), stage
    source = inspect.getsource(bullets)
    assert 'startswith("- ")' in source
    for stage in ("4a", "5", "8"):
        rules = stage_settings(stage)["rules"]
        assert stage_launch(stage)["settings"]["rules"] == rules
        assert cursor_stage_launch(stage)["settings"]["rules"] == rules
