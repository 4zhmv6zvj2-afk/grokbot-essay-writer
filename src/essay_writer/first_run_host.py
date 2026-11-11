"""Host config and attach: Cursor and Grok Build MCP files.

This module owns the launch command written into an MCP entry, the JSON and
TOML merges, and the enable calls that make an already-open host pick up the
server. It also carries the MCP template lookup shared with the shells.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from essay_writer.build_office import RESIDUALS
from essay_writer.first_run_common import Enable, package_root

MCP_RESIDUAL = (
    "Wrote the Cursor Custom MCP entry in mcp.json and enabled it with "
    "`agent mcp enable` when the Cursor CLI is installed. "
    "This package cannot call vscode.cursor.mcp.registerServer, "
    "so an already-open chat does not gain the server from this file alone."
)


def _writer_script_candidates() -> list[Path]:
    """Places pip may have written the essay-writer script."""
    import sysconfig

    found: list[Path] = []
    for scheme in ("posix_user", "nt_user", None):
        try:
            scripts = sysconfig.get_path("scripts") if scheme is None else sysconfig.get_path("scripts", scheme)
        except (KeyError, TypeError):
            scripts = None
        if scripts:
            found.append(Path(scripts) / "essay-writer")
    found.append(Path.home() / ".local" / "bin" / "essay-writer")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def writer_script() -> Path | None:
    """Installed essay-writer script, including one sitting off PATH."""
    for path in _writer_script_candidates():
        if path.is_file():
            return path.resolve()
    return None


def mcp_launch_command() -> str:
    """Bare name when that name is on PATH. Absolute path when it is not.

    A host whose PATH omits ~/.local/bin must still start the server from the
    command written into the MCP entry.
    """
    if shutil.which("essay-writer"):
        return "essay-writer"
    script = writer_script()
    if script is not None:
        return str(script)
    return "essay-writer"


def serving_interpreter() -> Path | None:
    """Interpreter the bootstrap chose when it replaced the bare command.

    Set only when bootstrap had to change interpreters (a provisioned 3.15.2 or
    an explicit --python). The absolute path keeps the host off an old Python.
    """
    raw = os.environ.get("ESSAY_WRITER_INTERPRETER", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_file() else None


def _launch_entry(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    interpreter = serving_interpreter()
    if interpreter is not None:
        args = ["-m", "essay_writer"]
        if name == "essay-reviewer":
            args.append("--reviewer")
        return {"command": str(interpreter), "args": args}
    copied = json.loads(json.dumps(entry))
    if copied.get("command") == "essay-writer":
        copied["command"] = mcp_launch_command()
    return copied


def expose_writer_on_path(
    *,
    script: Path | None = None,
    search_dirs: list[str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    """Link the installed script into a directory this shell already searches.

    Production calls with no arguments: it resolves the installed script and
    walks PATH. Tests pass an explicit script and a temp search directory (or a
    fake ``which``) so no test writes into the system PATH. Returns the bare
    name when the link is on a searched directory.
    """
    finder = which or shutil.which
    if finder("essay-writer"):
        return "essay-writer"
    resolved = script if script is not None else writer_script()
    if resolved is None:
        return None
    dirs = os.environ.get("PATH", "").split(os.pathsep) if search_dirs is None else list(search_dirs)
    for folder in dirs:
        if not folder:
            continue
        dest_dir = Path(folder)
        if not dest_dir.is_dir() or not os.access(dest_dir, os.W_OK):
            continue
        dest = dest_dir / "essay-writer"
        if dest.exists():
            continue
        try:
            dest.symlink_to(resolved)
        except OSError:
            continue
        if dest.exists():
            return "essay-writer"
    return None


def mcp_template() -> dict[str, Any]:
    """Server entries already declared for Cursor. Reviewer stays optional."""
    path = package_root() / "placeholders" / "mcp.config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(servers, dict) or "essay-writer" not in servers:
        raise ValueError("placeholders/mcp.config.json is missing the essay-writer server")
    return servers


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def grok_config_home() -> str:
    """Grok CLI config home. Not the essay code install folder."""
    override = os.environ.get("GROK_HOME")
    if override is not None and override.strip():
        return str(Path(override).expanduser())
    return str(Path.home() / ".grok")


def enable_mcp_server(
    identifier: str,
    *,
    binary: Callable[[], str | None] | None = None,
    version: Callable[[str], str | None] | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Approve one server already written to mcp.json.

    The defaults are the real Cursor CLI lookup and ``subprocess.run``. Tests
    pass a fake binary, version, and runner so they execute this branch without
    an installed CLI or a real ``agent mcp enable`` side effect.
    """
    from essay_writer.setup import cursor_cli_binary, cursor_cli_version

    find_binary = binary or cursor_cli_binary
    find_version = version or cursor_cli_version
    agent = find_binary()
    if not agent:
        return {"identifier": identifier, "enabled": False, "reason": "agent-cli-missing"}
    if not find_version(agent):
        return {"identifier": identifier, "enabled": False, "reason": "agent-version-missing", "path": agent}
    run = runner or subprocess.run
    try:
        completed = run(
            [agent, "mcp", "enable", identifier],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"identifier": identifier, "enabled": False, "reason": str(exc)}
    return {
        "identifier": identifier,
        "enabled": completed.returncode == 0,
        "returncode": completed.returncode,
    }


def enable_build_mcp(
    identifier: str,
    *,
    which: Callable[[str], str | None] | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Approve one server already written to .grok/config.toml.

    The defaults are the real ``grok`` lookup and ``subprocess.run``. Tests
    pass a fake ``which`` and runner to exercise enable and refusal branches.
    """
    finder = which or shutil.which
    grok = finder("grok")
    if not grok:
        return {"identifier": identifier, "enabled": False, "reason": "grok-cli-missing"}
    run = runner or subprocess.run
    try:
        completed = run(
            [grok, "mcp", "enable", identifier],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"identifier": identifier, "enabled": False, "reason": str(exc)}
    return {
        "identifier": identifier,
        "enabled": completed.returncode == 0,
        "returncode": completed.returncode,
    }


def resolve_user_config(user_config: Path | None = None, *, include_user: bool = True) -> Path | None:
    """The user's ``~/.cursor/mcp.json`` unless excluded or an explicit file is given.

    ``include_user`` is an explicit policy: production leaves it True, and a
    test that must not touch the real home passes False. ``user_config`` always
    wins so a caller can name a temp file.
    """
    if user_config is not None:
        return Path(user_config).expanduser()
    if not include_user:
        return None
    cursor_dir = Path.home() / ".cursor"
    if cursor_dir.is_dir():
        return cursor_dir / "mcp.json"
    return None


def write_bot_share(project: Path, *, reviewer: bool = True) -> Path:
    """Write the shareable Essay Bot JSON beside the Grok attach file.

    The MCP tables are the same command and args the attach just wrote.
    """
    from essay_writer.shells import BOT_SHARE_NAME, bot_share_document

    payload = bot_share_document(_template_servers(reviewer))
    path = Path(project) / ".grok" / BOT_SHARE_NAME
    _write_json(path, payload)
    return path


def repo_bot_share() -> dict[str, Any]:
    """Share JSON aligned with docs/templates/essay-bot.share.json."""
    from essay_writer.shells import bot_share_document

    template = mcp_template()
    servers = {"essay-writer": template["essay-writer"]}
    return bot_share_document(servers)


def attach_custom_mcp(
    project: Path,
    *,
    reviewer: bool = True,
    user_config: Path | None = None,
    include_user: bool = True,
    enable: Enable | None = None,
) -> dict[str, Any]:
    """Merge essay-writer into the project Cursor mcp.json. Reviewer is on by default.

    ``include_user=False`` keeps the write to the project config only, which is
    what a test needs when it must not touch the real home.
    """
    template = mcp_template()
    writer = template.get("essay-writer")
    if not isinstance(writer, dict):
        return {"ok": False, "reason": "The essay-writer MCP entry is missing."}
    servers: dict[str, Any] = {"essay-writer": _launch_entry("essay-writer", writer)}
    if reviewer:
        review = template.get("essay-reviewer")
        if not isinstance(review, dict):
            return {"ok": False, "reason": "The essay-reviewer MCP entry is missing."}
        servers["essay-reviewer"] = _launch_entry("essay-reviewer", review)

    project_file = Path(project) / ".cursor" / "mcp.json"
    written = [project_file]
    _merge_mcp(project_file, servers)
    user_file = resolve_user_config(user_config, include_user=include_user)
    if user_file is not None:
        _merge_mcp(user_file, servers)
        written.append(user_file)

    approver = enable or enable_mcp_server
    enabled = [approver(name) for name in servers]
    share = write_bot_share(Path(project), reviewer=reviewer)
    return {
        "ok": True,
        "reviewer": reviewer,
        "servers": list(servers),
        "project_config": str(project_file),
        "user_config": str(user_file) if user_file is not None else None,
        "wrote": [str(path) for path in written],
        "enabled": enabled,
        "residual": MCP_RESIDUAL,
        "bot_share": str(share),
    }


def _merge_mcp(path: Path, servers: dict[str, Any]) -> None:
    current = _read_json(path)
    existing = current.get("mcpServers")
    merged = dict(existing) if isinstance(existing, dict) else {}
    merged.update(servers)
    current["mcpServers"] = merged
    _write_json(path, current)


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _template_servers(reviewer: bool) -> dict[str, dict[str, Any]]:
    template = mcp_template()
    writer = template.get("essay-writer")
    if not isinstance(writer, dict):
        raise ValueError("The essay-writer MCP entry is missing.")
    servers = {"essay-writer": _launch_entry("essay-writer", writer)}
    if reviewer:
        review = template.get("essay-reviewer")
        if not isinstance(review, dict):
            raise ValueError("The essay-reviewer MCP entry is missing.")
        servers["essay-reviewer"] = _launch_entry("essay-reviewer", review)
    return servers


def render_server_table(name: str, entry: dict[str, Any]) -> str:
    """One [mcp_servers.<name>] table. Command and args come from the shared template."""
    command = entry.get("command")
    args = entry.get("args") if isinstance(entry.get("args"), list) else None
    if not isinstance(command, str) or args is None or not all(isinstance(arg, str) for arg in args):
        raise ValueError(name)
    rendered_args = "[" + ", ".join(_toml_string(arg) for arg in args) + "]"
    return (
        f"[mcp_servers.{name}]\n"
        f"command = {_toml_string(command)}\n"
        f"args = {rendered_args}\n"
        f"enabled = true\n"
    )


def render_build_config(reviewer: bool = False) -> str:
    servers = _template_servers(reviewer)
    tables = [render_server_table(name, servers[name]).rstrip("\n") for name in servers]
    return "\n".join(tables) + "\n"


def _toml_header(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]") or stripped.startswith("[["):
        return None
    return stripped[1:-1].strip().replace('"', "")


def _strip_toml_tables(text: str, headers: set[str]) -> str:
    kept: list[str] = []
    skipping = False
    for line in text.splitlines():
        header = _toml_header(line)
        if header is not None:
            skipping = header in headers
            if skipping:
                continue
        if skipping:
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _merge_build_toml(path: Path, reviewer: bool) -> None:
    servers = _template_servers(reviewer)
    headers = {f"mcp_servers.{name}" for name in servers}
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    body = _strip_toml_tables(existing, headers)
    addition = render_build_config(reviewer).rstrip("\n")
    text = f"{body}\n\n{addition}\n" if body else addition + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def resolve_build_config(user_config: Path | None = None, *, include_user: bool = True) -> Path | None:
    """User grok config. Project .grok/config.toml is always written separately.

    ``include_user`` is an explicit policy: production leaves it True, and a
    test that must not touch the real home passes False. The documented
    GROK_HOME override still wins over the home fallback.
    """
    if user_config is not None:
        return Path(user_config).expanduser()
    if not include_user:
        return None
    override = os.environ.get("GROK_HOME")
    if override is not None and override.strip():
        root = Path(override).expanduser()
        if root.is_dir():
            return root / "config.toml"
        return None
    home = Path.home() / ".grok"
    if home.is_dir():
        return home / "config.toml"
    return None


def attach_build_mcp(
    project: Path,
    *,
    reviewer: bool = True,
    user_config: Path | None = None,
    include_user: bool = True,
    enable: Enable | None = None,
) -> dict[str, Any]:
    """Merge essay-writer into project .grok/config.toml. Reviewer is on by default.

    Grok Build reads [mcp_servers.<name>] from that file. Compat load of
    .cursor/mcp.json can be turned off, so this file is the attach.
    ``include_user=False`` keeps the write to the project config only.
    """
    try:
        servers = _template_servers(reviewer)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}
    project_file = Path(project) / ".grok" / "config.toml"
    written = [project_file]
    _merge_build_toml(project_file, reviewer)
    user_file = resolve_build_config(user_config, include_user=include_user)
    if user_file is not None:
        _merge_build_toml(user_file, reviewer)
        written.append(user_file)
    approver = enable or enable_build_mcp
    enabled = [approver(name) for name in servers]
    share = write_bot_share(Path(project), reviewer=reviewer)
    return {
        "ok": True,
        "reviewer": reviewer,
        "servers": list(servers),
        "project_config": str(project_file),
        "user_config": str(user_file) if user_file is not None else None,
        "wrote": [str(path) for path in written],
        "enabled": enabled,
        "residual_id": "open-grok-session",
        "residual": RESIDUALS["open-grok-session"],
        "bot_share": str(share),
    }
