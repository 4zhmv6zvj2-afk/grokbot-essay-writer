"""Status text has one editable source: prompts/status/mid.md."""

from __future__ import annotations

from essay_writer.prompt_loader import raw, render_tokens, sections

STATUS = sections("status/mid.md")
BRIEFING = raw("front_office/briefing.md")
TOOLS = raw("front_office/tools.md")
DOORS = raw("front_office/tools.json")


def test_status_values_are_not_duplicated() -> None:
    for key, value in STATUS.items():
        assert value not in BRIEFING, key
        assert value not in TOOLS, key
        assert value not in DOORS, key


def test_status_tokens_render_the_source() -> None:
    token = "{{status:body}}"
    assert token in BRIEFING or token in TOOLS or token in DOORS
    assert render_tokens(token) == STATUS["body"]
    for key, value in STATUS.items():
        token = f"{{{{status:{key}}}}}"
        if token in BRIEFING or token in TOOLS or token in DOORS:
            assert render_tokens(token) == value
