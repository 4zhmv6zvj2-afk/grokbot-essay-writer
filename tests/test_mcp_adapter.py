"""The MCP adapter edge: schemas, private-SDK touchpoints, and prompt host lines.

The writer server mounts handlers through the SDK's private call path and relies
on ``inspect.signature`` following the ``__wrapped__`` attribute set in
shells.py. These tests fail loudly if a tool loses its typed schema, if the SDK
moves that private touchpoint, or if a host-line replacement silently no-ops
because the prompt prose changed.
"""

from __future__ import annotations

import asyncio
import inspect
from importlib.resources import files

from mcp.server.mcpserver import MCPServer

from essay_writer import server as server_mod
from essay_writer.server import (
    _ACTIVE_HOST_LINES,
    INSTRUCTIONS,
    REVIEW_INSTRUCTIONS,
    _StatusServer,
    build_server,
    house_instructions,
)


def _tools() -> dict[str, object]:
    server = build_server()

    async def listed():
        return await server.list_tools()

    return {tool.name: tool for tool in asyncio.run(listed())}


def test_every_mounted_tool_has_a_typed_input_schema():
    tools = _tools()
    assert len(tools) == 24
    for name, tool in tools.items():
        schema = tool.input_schema
        assert schema.get("type") == "object", name
        properties = schema.get("properties") or {}
        if name not in {"essay.health", "essay.debug.export"}:
            assert properties, f"{name} exposes no input properties"
    # The confirm-time card digest is part of the public dig/research schema.
    for name in ("essay.dig", "essay.research.summary", "essay.research.full"):
        assert "cardDigest" in (tools[name].input_schema.get("properties") or {}), name
    assert {"essay_id", "stage"} <= set(tools["essay.stage"].input_schema["properties"])


def test_private_sdk_call_path_is_pinned():
    """The SDK version is pinned; if this private method moves, port the adapter."""
    assert hasattr(MCPServer, "_handle_call_tool"), "mcp SDK moved _handle_call_tool"
    assert _StatusServer._handle_call_tool is not MCPServer._handle_call_tool
    source = inspect.getsource(_StatusServer._handle_call_tool)
    assert "bind_mcp_session" in source
    assert "super()._handle_call_tool" in source
    # The writer and reviewer entries both use the patched server class.
    assert isinstance(build_server(), _StatusServer)


def test_active_host_lines_are_present_and_replace():
    """A prose edit that removes a line must fail here, not silently no-op."""
    seen = 0
    for text in (INSTRUCTIONS, REVIEW_INSTRUCTIONS):
        for line in _ACTIVE_HOST_LINES:
            if line not in text:
                continue
            seen += 1
            replaced = house_instructions(text)
            assert line not in replaced
    assert seen == len(_ACTIVE_HOST_LINES), "a host line vanished from the prompts"


def test_house_instructions_switches_the_active_host(monkeypatch):
    monkeypatch.setattr(server_mod, "mid_office", lambda: "Cursor")
    line = _ACTIVE_HOST_LINES[0]
    replaced = house_instructions(f"Prefix. {line}")
    assert "Grok Build does the file work" not in replaced
    assert "Cursor does the file work" in replaced


def test_py_typed_marker_ships_with_the_package():
    assert (files("essay_writer") / "py.typed").is_file()
