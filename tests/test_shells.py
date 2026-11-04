"""One core. Cursor and Grok Bot call the same doors. No second catalogue."""

import ast
import json
import re

import pytest

from essay_writer import tools as tool_catalogue
from essay_writer.doors import DOORS
from essay_writer.first_run import (
    install_uploaded_copy,
    package_root,
    render_server_table,
)
from essay_writer.review import essay_review
from essay_writer.server import (
    HANDLERS,
    INSTRUCTIONS,
    REVIEW_HANDLERS,
    _mount,
    build_server,
    call_local,
    intake_with_image,
)
from essay_writer.shells import (
    SHELLS,
    cursor_shell,
    front_office,
    front_office_call,
    mcp_entry,
    mount_handler,
)


def test_both_shells_hold_the_writer_handlers():
    grok_bot = front_office()
    cursor = cursor_shell()
    assert SHELLS == ("cursor", "grok_bot")
    assert grok_bot["owns_handlers"] is False
    assert cursor["owns_handlers"] is False
    assert grok_bot["handlers"] is cursor["handlers"] is HANDLERS
    assert grok_bot["role"] == "front office"
    assert grok_bot["entry"] == cursor["entry"]
    assert grok_bot["entry"]["command"] == "essay-writer"
    assert grok_bot["entry"]["args"] == []
    assert grok_bot["entry"]["source"] == "placeholders/mcp.config.json"
    assert "Do not keep a second copy of a door." in grok_bot["briefing"]
    assert grok_bot["briefing"] is INSTRUCTIONS
    assert "You are Grok Bot, the front office." in INSTRUCTIONS


def test_writer_doors_match_the_handler_map_and_exclude_the_reviewer():
    tools = {door["tool"] for door in DOORS}
    assert tools == set(HANDLERS)
    assert set(REVIEW_HANDLERS) == {"essay.review"}
    assert set(REVIEW_HANDLERS).isdisjoint(HANDLERS)
    assert REVIEW_HANDLERS["essay.review"] is essay_review
    for tool, handler in HANDLERS.items():
        assert handler.__module__.startswith("essay_writer.")
        mounted = mount_handler(tool)
        if tool == "essay.intake":
            assert mounted is intake_with_image
        else:
            assert getattr(mounted, "__wrapped__", None) is handler
    assert "essay_intake" in intake_with_image.__code__.co_names
    with pytest.raises(KeyError):
        mount_handler("essay.review")


def test_tool_catalogue_is_the_handler_map():
    exported = {handler.__name__ for handler in HANDLERS.values()}
    assert set(tool_catalogue.__all__) == exported
    for handler in HANDLERS.values():
        assert getattr(tool_catalogue, handler.__name__) is handler
    assert not hasattr(tool_catalogue, "essay_review")


def test_mount_refuses_a_second_handler_map():
    with pytest.raises(RuntimeError, match="HANDLERS"):
        _mount(object(), DOORS, dict(HANDLERS))


def test_front_office_call_is_the_handler(workspace):
    report = call_local("essay.health", {})
    assert report["alive"] is True
    assert {door["tool"] for door in report["doors"]} == set(HANDLERS)
    direct = front_office_call("essay.health", {})
    assert {door["tool"] for door in direct["doors"]} == set(HANDLERS)
    with pytest.raises(KeyError):
        front_office_call("essay.review", {})


def test_stdio_mount_uses_the_same_tool_names(workspace):
    server = build_server()

    async def listed():
        return await server.list_tools()

    import asyncio

    tools = asyncio.run(listed())
    assert {tool.name for tool in tools} == set(HANDLERS)


def test_committed_configs_share_the_local_command():
    entry = mcp_entry()
    review = mcp_entry(reviewer=True)
    assert review["args"] == ["--reviewer"]
    assert review["command"] == entry["command"] == "essay-writer"
    rendered = render_server_table(entry["name"], {"command": entry["command"], "args": entry["args"]})
    cursor = json.loads((package_root() / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    writer = cursor["mcpServers"]["essay-writer"]
    assert writer["command"] == entry["command"]
    assert writer["args"] == entry["args"]
    assert "url" not in writer
    grok = (package_root() / ".grok" / "config.toml").read_text(encoding="utf-8")
    template = (package_root() / "placeholders" / "mcp.config.json").read_text(encoding="utf-8")
    assert rendered.strip() in grok
    for text in (grok, template, json.dumps(cursor)):
        assert "http://" not in text
        assert "https://" not in text
        assert "serverUrl" not in text


def test_install_writes_both_configs_from_that_template(tmp_path):
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    def pip_ok(command, cwd):
        return {"returncode": 0, "stdout": "", "stderr": ""}

    result = install_uploaded_copy(source, pip_runner=pip_ok, attach=True)
    assert result["ok"] is True
    from essay_writer.first_run import mcp_launch_command

    entry = mcp_entry()
    launch = mcp_launch_command()
    cursor = json.loads((source / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert cursor["mcpServers"]["essay-writer"]["command"] == launch
    assert cursor["mcpServers"]["essay-writer"]["args"] == entry["args"]
    grok = (source / ".grok" / "config.toml").read_text(encoding="utf-8")
    assert f'command = "{launch}"' in grok
    assert "args = []" in grok
    assert "https://" not in grok


def test_hosted_template_is_refused(monkeypatch):
    def hosted():
        return {"essay-writer": {"command": "essay-writer", "args": [], "url": "https://example.test/mcp"}}

    monkeypatch.setattr("essay_writer.first_run.mcp_template", hosted)
    with pytest.raises(RuntimeError, match="local"):
        mcp_entry()


def test_door_functions_are_defined_once():
    root = package_root() / "src" / "essay_writer"
    watched = {handler.__name__ for handler in HANDLERS.values()}
    watched.update({"prepare_photo", "stage_settings", "chat_docx", "stage_launch"})
    found: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in watched:
                found.setdefault(node.name, []).append(path.name)
    duplicates = {name: places for name, places in found.items() if len(places) > 1}
    assert duplicates == {}


def test_bot_sheet_names_only_writer_doors():
    text = (package_root() / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "switched on" in text.casefold()
    assert "not switched on" not in text.casefold()
    assert "essay-bot.share.json" in text
    assert "not a second product" in text.casefold()
    named = set(re.findall(r"essay\.[a-z0-9_.]+", text))
    assert named
    assert named <= {door["tool"] for door in DOORS}
    assert "essay.review" not in named


def test_shells_module_does_not_keep_a_second_dig():
    shells = (package_root() / "src" / "essay_writer" / "shells.py").read_text(encoding="utf-8")
    assert "essay_writer.dig" not in shells
    assert "consensus_status" not in shells
    assert "ESSAY_WRITER_CONSENSUS" not in shells
