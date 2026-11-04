"""Essay door catalogue. Health and the MCP server both read this list."""

from __future__ import annotations

from essay_writer.prompt_loader import json_data, render_tokens

DOORS = tuple(
    {**door, "description": render_tokens(door["description"])}
    for door in json_data("front_office/tools.json")
)

# The full notes stay on the writer instructions, once. Pasting them onto each
# door made tools/list about 230KB, and the host catalog then kept an older
# shorter list that omitted later doors.

