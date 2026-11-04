"""Confirm text has one editable source: prompts/front_office/confirm.md."""

from __future__ import annotations

from essay_writer.prompt_loader import raw, render_tokens, sections

CONFIRM = sections("front_office/confirm.md")
BRIEFING = raw("front_office/briefing.md")
TOOLS = raw("front_office/tools.md")
DOORS = raw("front_office/tools.json")


def test_confirm_values_are_not_duplicated() -> None:
    for key, value in CONFIRM.items():
        assert value not in BRIEFING, key
        assert value not in TOOLS, key
        assert value not in DOORS, key


def test_confirm_tokens_render_the_source() -> None:
    for key, value in CONFIRM.items():
        token = f"{{{{confirm:{key}}}}}"
        assert token in BRIEFING or token in TOOLS or token in DOORS, key
        assert render_tokens(token) == value
