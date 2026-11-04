"""One core product. Cursor and Grok Bot are shells.

Door functions live in this package. The writer seat mounts them once, from
essay_writer.server.HANDLERS. A shell runs the local essay-writer command
taken from placeholders/mcp.config.json. It does not keep a second copy of
a door, and it does not point at a hosted MCP URL.

Grok Bot is the front office: it says the door reply. Cursor is the other
shell: it attaches the same handlers. Grok Build remains the mid-office file
host beside Cursor (essay_writer.build_office). This module does not replace
that host and does not carry a second stage table.
"""

from __future__ import annotations

from typing import Any, cast

from essay_writer.specialists.grok_bot import LANGUAGE, front_office_call

SHELL_CURSOR = "cursor"
SHELL_GROK_BOT = "grok_bot"
SHELLS = (SHELL_CURSOR, SHELL_GROK_BOT)

CORE_COMMAND = "essay-writer"
ENTRY_SOURCE = "placeholders/mcp.config.json"

# Operator text is still written in more than one note. The doors are not.
RESIDUALS: dict[str, str] = {
    "briefing-prose": (
        "The operator briefing in server.INSTRUCTIONS, the door descriptions, "
        "docs/workflow.md, and docs/templates/bot.md are still written by hand. "
        "They are not a second door. bot.md is switched on and uses the same MCP command as Cursor. "
        "Every essay tool it names is one of the writer doors. "
        "It does not list the later doors."
    ),
}


def _servers() -> dict[str, Any]:
    from essay_writer.first_run import mcp_template

    servers = mcp_template()
    if not isinstance(servers, dict):
        raise RuntimeError("the MCP template is not an object")
    return servers


def mcp_entry(*, reviewer: bool = False) -> dict[str, Any]:
    """Command and args every shell runs. One template. No hosted URL."""
    name = "essay-reviewer" if reviewer else "essay-writer"
    entry = _servers().get(name)
    if not isinstance(entry, dict):
        raise RuntimeError(f"{name} is missing from {ENTRY_SOURCE}")
    if any(key in entry for key in ("url", "uri", "serverUrl")):
        raise RuntimeError("essay-writer MCP stays local")
    command = entry.get("command")
    args = entry.get("args")
    if command != CORE_COMMAND or not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise RuntimeError("shells run the local essay-writer command")
    return {"name": name, "command": command, "args": list(args), "source": ENTRY_SOURCE}


def writer_handlers() -> dict[str, Any]:
    from essay_writer.server import HANDLERS

    return HANDLERS


BOT_SHARE_RELATIVE = "docs/templates/essay-bot.share.json"
BOT_SHARE_NAME = "essay-bot.share.json"


def bot_share_document(servers: dict[str, Any]) -> dict[str, Any]:
    """Shareable Essay Bot JSON. MCP tables come from the shared template."""
    return {
        "name": "Essay Bot",
        "host_note": (
            "Template for Essay Bot. An operator publishes docs/templates/essay-bot.share.json "
            "through the host share tool on this computer."
        ),
        "switched_on": True,
        "instructions": "docs/templates/bot.md",
        "chat_tone": {"language": LANGUAGE},
        "front_office": "essay_writer.shells.front_office",
        "handlers": "essay_writer.server.HANDLERS",
        "mcpServers": servers,
        "delete": {
            "tool": "essay.project.delete",
            "confirmPhase": ["draft", "confirm"],
            "where": ["grokbot", "local", "both"],
            "localPaths": (
                "where local needs each Word or zip path the student names. "
                "where both, when localPaths is omitted, uses Word and zip paths already stored for that sequence, "
                "or across every sequence when the whole module is deleted, "
                "and the default handoff names when those files are already there. "
                "Ask for a path only when none are there. "
                "A path the caller names is the list. "
                "Do not guess a path. Do not search Documents or home. "
                "Show the computer list, including when it is empty."
            ),
            "sequence": (
                "Optional sequence id, such as MOD1004AA-2. "
                "Confirm removes only that sequence. "
                "Omit it to remove the whole module."
            ),
            "skip_computer_list": False,
        },
    }


def front_office() -> dict[str, Any]:
    """Grok Bot shell. It speaks. The functions are the writer handlers."""
    from essay_writer.server import INSTRUCTIONS

    return {
        "shell": SHELL_GROK_BOT,
        "role": "front office",
        "owns_handlers": False,
        "handlers": writer_handlers(),
        "briefing": INSTRUCTIONS,
        "entry": mcp_entry(),
    }


def cursor_shell() -> dict[str, Any]:
    """Cursor shell. Same handlers and the same local command as Grok Bot.

    Stage model and reasoning are cursor_stage_launch, not a second table.
    """
    return {
        "shell": SHELL_CURSOR,
        "role": "shell",
        "owns_handlers": False,
        "handlers": writer_handlers(),
        "entry": mcp_entry(),
        "stage_launch": "essay_writer.cursor_office.cursor_stage_launch",
    }


def mount_handler(tool: str) -> Any:
    """Function the stdio server mounts for one writer door.

    A photo on essay.intake is shown to the model by a transport wrapper.
    The product function stays HANDLERS['essay.intake'].
    """
    handlers = writer_handlers()
    if tool not in handlers:
        raise KeyError(tool)
    if tool == "essay.intake":
        from essay_writer.server import intake_with_image

        if "essay_intake" not in intake_with_image.__code__.co_names:
            raise RuntimeError("photo mount must call essay_intake")
        return intake_with_image
    raw = handlers[tool]

    def mounted(**arguments: Any) -> Any:
        """Live MCP speech. Same door, with status, next, and no launch payload."""
        return front_office_call(tool, arguments)

    cast(Any, mounted).__wrapped__ = raw
    mounted.__name__ = getattr(raw, "__name__", tool)
    return mounted
