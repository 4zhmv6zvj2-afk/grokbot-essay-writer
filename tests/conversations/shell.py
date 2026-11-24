"""A shell that calls the mounted doors and keeps the student reply.

The handlers are the same map the MCP server mounts. This shell does not
start a model, a network client, or another process.
"""

from __future__ import annotations

from typing import Any

from essay_writer.server import HANDLERS, REVIEW_HANDLERS


class FakeShell:
    """One student host. Each call is one door the host would send."""

    def __init__(self) -> None:
        self.replies: list[dict[str, Any]] = []

    def call(self, tool: str, **kwargs: Any) -> dict[str, Any]:
        handler = HANDLERS.get(tool)
        if handler is None:
            handler = REVIEW_HANDLERS[tool]
        result = handler(**kwargs)
        if not isinstance(result, dict):
            result = {"ok": False, "reason": "the door did not return an object"}
        self.replies.append({"tool": tool, "result": result})
        return result

    def student_line(self, result: dict[str, Any]) -> str:
        """The sentence a student would read on this reply."""
        for key in ("next", "reason"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
