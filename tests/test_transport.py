import asyncio
import json
import os
import re
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from essay_writer.server import HANDLERS, build_server

ROOT = Path(__file__).resolve().parents[1]


def test_in_process_health_tool(workspace):
    server = build_server()

    async def run():
        tools = await server.list_tools()
        result = await server.call_tool("essay.health", {})
        return tools, result

    tools, result = asyncio.run(run())
    assert {tool.name for tool in tools} == set(HANDLERS)
    payload = json.loads(result.content[0].text)
    assert payload["alive"] is True
    assert payload["essay_ids"] == []


def test_stdio_health(workspace):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "essay_writer"],
            cwd=str(ROOT),
            env={
                "PYTHONPATH": str(ROOT / "src"),
                "ESSAY_WRITER_ROOT": str(workspace),
                "PATH": os.environ.get("PATH", ""),
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                called = await session.call_tool("essay.health", {})
                return listed, called

    listed, called = asyncio.run(run())
    names = {tool.name for tool in listed.tools}
    assert names == set(HANDLERS)
    assert "essay.stage" in names
    assert "essay.download.leftovers" in names
    assert "essay.health" in names
    assert "essay.pack.render_word" in names
    assert "essay.research.full" in names
    text = called.content[0].text
    assert json.loads(text)["alive"] is True


# Cursor writes each tool to tools/<sanitized>.json and has dropped a tools/list
# near 220KB. Dots become underscores. Both later doors must survive that path.
_HOST_FILE = re.compile(r"[^a-zA-Z0-9_-]")
_HOST_CATALOG_BUDGET = 120_000


def test_host_catalog_keeps_stage_and_leftovers():
    server = build_server()

    async def run():
        return await server.list_tools()

    tools = asyncio.run(run())
    names = {tool.name for tool in tools}
    assert names == set(HANDLERS)
    assert "essay.stage" in names
    assert "essay.download.leftovers" in names
    payload = [
        tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools
    ]
    assert len(json.dumps(payload).encode()) < _HOST_CATALOG_BUDGET
    files = [_HOST_FILE.sub("_", name) for name in names]
    assert len(files) == len(set(files))
    assert "essay_stage" in files
    assert "essay_download_leftovers" in files
