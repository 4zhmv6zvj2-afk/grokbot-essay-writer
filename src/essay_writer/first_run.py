"""First-run glue for an uploaded copy.

Unpack a zip onto the cloud computer, pip install -e ., and write the Cursor
Custom MCP entries for essay-writer and essay-reviewer. Pass --no-reviewer to
attach only the writer. When the Cursor agent CLI is missing on the Grok Bot
computer, install it, then enable those servers. Never install that CLI on the
Mac, and never install grok.
Word and zip files already on disk can be copied to the Mac. This module does
not write those files. A successful copy remembers that Mac path on the sequence.
OK on the Mac handoff card creates Documents/Essay Bot on the friend's Mac
and remembers that path. Later or skip does not create a folder.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from essay_writer import paths as essay_paths
from essay_writer.build_office import RESIDUALS
from essay_writer.known_paths import RepoSaveRefused, refuse_repo_write
from essay_writer.paths import SETUP_DIRNAME, kb1_root, work_dir, workspace_root
from essay_writer.student_voice import say

INSTALL_DIRNAME = "essay-writer-install"
MAC_DIRNAME = "Essay-writer-deliverables"
MAC_HANDOFF_SECRET = "ESSAY_WRITER_MAC_DIR"
RECOMMENDED_MAC_HANDOFF_NAME = "Essay Bot"
MAC_FOUR_WAY_CARD = (
    "Word copies go to Documents/Essay Bot — OK, another folder, later, or skip."
)
MAC_FOUR_WAY_FRIEND_SPEECH = (
    "OK runs essay-writer --remember-mac-dir ok (choose_mac_handoff ok) to create "
    "Documents/Essay Bot on the Mac. Another needs the folder path before remember-mac-dir. "
    "Later or skip without a path stays chat-only; do not say the Mac folder is ready."
)
MAC_DELIVERABLES_NAME = "mac-deliverables.json"
# Names copy_to_mac writes for a sequence. Not a directory listing.
KNOWN_MAC_DELIVERABLE_NAMES = (
    "annotation.docx",
    "download-list.docx",
    "papers.zip",
    "critical-reviews.zip",
)
DELIVERABLE_SUFFIXES = frozenset({".docx", ".zip"})
CURSOR_AGENT_INSTALL = "curl https://cursor.com/install -fsS | bash"
MCP_RESIDUAL = (
    "Wrote the Cursor Custom MCP entry in mcp.json and enabled it with "
    "`agent mcp enable` when the Cursor CLI is installed. "
    "This package cannot call vscode.cursor.mcp.registerServer, "
    "so an already-open chat does not gain the server from this file alone."
)
MAC_RESIDUAL = (
    "No Mac folder is available. Set ESSAY_WRITER_MAC_DIR to a folder on the Mac. "
    "This helper only copies an existing .docx or .zip."
)
MAC_NOT_MOUNTED_CHAT = (
    "The Mac handoff folder is not available on this computer. "
    "The Word or zip file stays where it is. "
    "Set ESSAY_WRITER_MAC_DIR to a mounted Mac folder, or copy the file yourself."
)
UPGRADE_REREAD_SPEECH = (
    "After this install or upgrade, read CHANGELOG.txt at the zip root when one is present, "
    "then re-read FIRST-RUN.txt and docs/templates/bot.md before student chat. "
    "Do not recite install steps to the student."
)
UPGRADE_REREAD_MARKER = ".essay-writer-upgrade-reread.json"

PipRunner = Callable[[list[str], Path], dict[str, Any]]
Enable = Callable[[str], dict[str, Any]]


def package_root() -> Path:
    """Repo root that contains pyproject.toml and src/essay_writer."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "essay_writer").is_dir():
            return parent
    return here.parents[2]


def prompt_path() -> Path:
    packaged = Path(__file__).resolve().parent / "FIRST-RUN.txt"
    if packaged.is_file():
        return packaged
    return package_root() / "FIRST-RUN.txt"


def first_run_prompt() -> str:
    """Prompt text that ships in this copy and inside the package."""
    return prompt_path().read_text(encoding="utf-8")


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


def _launch_entry(entry: dict[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(entry))
    if copied.get("command") == "essay-writer":
        copied["command"] = mcp_launch_command()
    return copied


def expose_writer_on_path() -> str | None:
    """Link the script into a directory this shell already searches.

    Skipped under pytest. Returns the bare name when the link is on PATH.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if shutil.which("essay-writer"):
        return "essay-writer"
    script = writer_script()
    if script is None:
        return None
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder:
            continue
        dest_dir = Path(folder)
        if not dest_dir.is_dir() or not os.access(dest_dir, os.W_OK):
            continue
        dest = dest_dir / "essay-writer"
        if dest.exists():
            continue
        try:
            dest.symlink_to(script)
        except OSError:
            continue
        if shutil.which("essay-writer"):
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


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _internal_volume(path: Path) -> bool:
    return any(part.casefold() == "researchdrive" for part in path.parts)


def _clone_url(value: str) -> bool:
    text = value.strip()
    folded = text.casefold()
    if folded.startswith(("http://", "https://", "git@", "ssh://", "git://")):
        return True
    return folded.endswith(".git") and "://" in folded


def _fail(reason: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "installed": False, "reason": reason}
    body.update(extra)
    return body


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


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _member_target(dest: Path, name: str) -> Path:
    if not name or "\x00" in name:
        raise ValueError(name or "empty zip member")
    pure = Path(name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(name)
    target = (dest / pure).resolve()
    if not _under(target, dest):
        raise ValueError(name)
    return target


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    planned: list[tuple[zipfile.ZipInfo, Path]] = []
    root = dest.resolve()
    for info in archive.infolist():
        filename = info.filename
        if not filename or filename.endswith("/"):
            continue
        if _is_symlink(info):
            raise ValueError(filename)
        planned.append((info, _member_target(root, filename)))
    for info, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))


def _project_root(dest: Path) -> Path | None:
    matches = [path.parent for path in dest.rglob("pyproject.toml")]
    if (dest / "pyproject.toml").is_file() and dest not in matches:
        matches.append(dest)
    named = []
    for root in matches:
        try:
            text = (root / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            continue
        if 'name = "essay-writer"' in text or "name = 'essay-writer'" in text:
            named.append(root)
    pool = named or matches
    if not pool:
        return None
    pool.sort(key=lambda path: len(path.resolve().relative_to(dest.resolve()).parts))
    return pool[0]


def _blocked_dest(dest: Path) -> str | None:
    if _internal_volume(dest):
        return "That folder is not an install path on this computer. Name a folder on this computer, or use the cloud computer."
    if (dest / "setup.json").is_file() and (dest / "app").is_dir():
        return "That folder is the save tree. Install the copy beside it, not inside it."
    if dest.exists() and not dest.is_dir():
        return "That install path is a file."
    return None


def install_folder(dest: Path | None = None) -> Path | None:
    """Cloud install folder. A named dest wins. Documents is not a fallback."""
    if dest is not None:
        return Path(dest).expanduser()
    cloud = essay_paths.CLOUD_WORKSPACE
    if cloud.is_dir():
        return cloud / INSTALL_DIRNAME
    return None


def grok_config_home() -> str:
    """Grok CLI config home. Not the essay code install folder."""
    override = os.environ.get("GROK_HOME")
    if override is not None and override.strip():
        return str(Path(override).expanduser())
    return str(Path.home() / ".grok")


def _run_pip(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 1, "stdout": "", "stderr": str(exc)}
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def _ensure_prompt(root: Path) -> bool:
    target = root / "FIRST-RUN.txt"
    if target.is_file():
        return True
    source = prompt_path()
    if not source.is_file() or source.resolve() == target.resolve():
        return False
    shutil.copyfile(source, target)
    return True


def _on_mac() -> bool:
    return sys.platform == "darwin"


def _run_cursor_installer() -> dict[str, Any]:
    """Run the Cursor agent installer. Tests pass their own installer instead."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "skipped-under-test",
            "command": CURSOR_AGENT_INSTALL,
        }
    try:
        completed = subprocess.run(
            ["bash", "-lc", CURSOR_AGENT_INSTALL],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 1, "stdout": "", "stderr": str(exc), "command": CURSOR_AGENT_INSTALL}
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-500:],
        "stderr": (completed.stderr or "")[-500:],
        "command": CURSOR_AGENT_INSTALL,
    }


def ensure_cursor_agent(
    installer: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Install the Cursor agent CLI when it is missing. Never on the Mac. Never grok."""
    from essay_writer.setup import cursor_cli_binary, cursor_cli_version

    binary = cursor_cli_binary()
    if binary:
        version = cursor_cli_version(binary)
        return {
            "ok": bool(version),
            "installed": True,
            "ran_install": False,
            "path": binary,
            "version": version,
            "reason": None if version else "agent-version-missing",
        }
    if _on_mac():
        return {
            "ok": False,
            "installed": False,
            "ran_install": False,
            "path": None,
            "version": None,
            "reason": "mac-no-install",
        }
    if installer is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return {
            "ok": False,
            "installed": False,
            "ran_install": False,
            "path": None,
            "version": None,
            "reason": "skipped-under-test",
        }
    runner = installer or _run_cursor_installer
    report = runner()
    if not isinstance(report, dict):
        report = {"returncode": 1}
    binary = cursor_cli_binary()
    version = cursor_cli_version(binary) if binary else None
    if not binary:
        reason = "agent-cli-missing"
    elif not version:
        reason = "agent-version-missing"
    elif report.get("returncode") != 0:
        reason = "agent-install-failed"
    else:
        reason = None
    return {
        "ok": reason is None,
        "installed": binary is not None,
        "ran_install": True,
        "path": binary,
        "version": version,
        "reason": reason,
        "installer": {"returncode": report.get("returncode"), "command": CURSOR_AGENT_INSTALL},
    }


def enable_mcp_server(identifier: str) -> dict[str, Any]:
    """Approve one server already written to mcp.json. No-op under pytest."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"identifier": identifier, "enabled": False, "reason": "skipped-under-test"}
    from essay_writer.setup import cursor_cli_binary, cursor_cli_version

    agent = cursor_cli_binary()
    if not agent:
        return {"identifier": identifier, "enabled": False, "reason": "agent-cli-missing"}
    if not cursor_cli_version(agent):
        return {"identifier": identifier, "enabled": False, "reason": "agent-version-missing", "path": agent}
    try:
        completed = subprocess.run(
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


def enable_build_mcp(identifier: str) -> dict[str, Any]:
    """Approve one server already written to .grok/config.toml. No-op under pytest."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"identifier": identifier, "enabled": False, "reason": "skipped-under-test"}
    grok = shutil.which("grok")
    if not grok:
        return {"identifier": identifier, "enabled": False, "reason": "grok-cli-missing"}
    try:
        completed = subprocess.run(
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


def resolve_user_config(user_config: Path | None = None, *, include_user: bool | None = None) -> Path | None:
    if user_config is not None:
        return Path(user_config).expanduser()
    if include_user is False:
        return None
    if include_user is None and os.environ.get("PYTEST_CURRENT_TEST"):
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
    include_user: bool | None = None,
    enable: Enable | None = None,
) -> dict[str, Any]:
    """Merge essay-writer into the project Cursor mcp.json. Reviewer is on by default."""
    template = mcp_template()
    writer = template.get("essay-writer")
    if not isinstance(writer, dict):
        return {"ok": False, "reason": "The essay-writer MCP entry is missing."}
    servers: dict[str, Any] = {"essay-writer": _launch_entry(writer)}
    if reviewer:
        review = template.get("essay-reviewer")
        if not isinstance(review, dict):
            return {"ok": False, "reason": "The essay-reviewer MCP entry is missing."}
        servers["essay-reviewer"] = _launch_entry(review)

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
    servers = {"essay-writer": _launch_entry(writer)}
    if reviewer:
        review = template.get("essay-reviewer")
        if not isinstance(review, dict):
            raise ValueError("The essay-reviewer MCP entry is missing.")
        servers["essay-reviewer"] = _launch_entry(review)
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


def resolve_build_config(user_config: Path | None = None, *, include_user: bool | None = None) -> Path | None:
    """User grok config. Project .grok/config.toml is always written separately."""
    if user_config is not None:
        return Path(user_config).expanduser()
    if include_user is False:
        return None
    if include_user is None and os.environ.get("PYTEST_CURRENT_TEST"):
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
    include_user: bool | None = None,
    enable: Enable | None = None,
) -> dict[str, Any]:
    """Merge essay-writer into project .grok/config.toml. Reviewer is on by default.

    Grok Build reads [mcp_servers.<name>] from that file. Compat load of
    .cursor/mcp.json can be turned off, so this file is the attach.
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
        "residual_id": "40a-open-session",
        "residual": RESIDUALS["40a-open-session"],
        "bot_share": str(share),
    }


def install_uploaded_copy(
    upload: Path | None = None,
    *,
    dest: Path | None = None,
    reviewer: bool = True,
    pip_runner: PipRunner | None = None,
    attach: bool = True,
    enable: Enable | None = None,
    cursor_installer: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Unpack a zip when given one, then pip install -e . in that same call.

    A directory upload is already unpacked. No upload installs the tree that
    contains this file.
    """
    if isinstance(upload, str) and _clone_url(upload):
        return _fail("Nothing is cloned. Pass the uploaded zip, not a git URL.")
    unpacked = False
    if upload is None:
        root = package_root()
        if not (root / "pyproject.toml").is_file():
            return _fail("This folder has no project to install.")
    else:
        source = Path(upload).expanduser()
        if _clone_url(str(source)):
            return _fail("Nothing is cloned. Pass the uploaded zip, not a git URL.")
        if source.is_dir():
            found = _project_root(source)
            if found is None:
                return _fail("That folder does not contain the essay-writer project.", upload=str(source))
            root = found
        elif source.is_file():
            folder = install_folder(dest)
            if folder is None:
                return _fail(
                    "This computer has no cloud workspace. "
                    "Name dest to install on this computer. Documents is not used.",
                    upload=str(source),
                )
            blocked = _blocked_dest(folder)
            if blocked:
                return _fail(blocked, upload=str(source), dest=str(folder))
            folder.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(source) as archive:
                    _safe_extract(archive, folder)
            except (OSError, zipfile.BadZipFile, ValueError) as exc:
                return _fail(f"The upload was not unpacked: {exc}", upload=str(source), dest=str(folder))
            found = _project_root(folder)
            if found is None:
                return _fail(
                    "That upload does not contain the essay-writer project.",
                    upload=str(source),
                    dest=str(folder),
                    unpacked=True,
                )
            root = found
            unpacked = True
        else:
            return _fail("That upload is not on disk.", upload=str(source))

    prompt_present = _ensure_prompt(root)
    command = [sys.executable, "-m", "pip", "install", "-e", "."]
    runner = pip_runner or _run_pip
    report = runner(command, root)
    pip_body = {"command": command, "cwd": str(root), **report}
    if report.get("returncode") != 0:
        return _fail(
            "pip install -e . did not finish.",
            unpacked=unpacked,
            root=str(root),
            pip=pip_body,
            prompt_present=prompt_present,
        )
    expose_writer_on_path()
    cursor_cli = None
    if cursor_installer is not None or not os.environ.get("PYTEST_CURRENT_TEST"):
        cursor_cli = ensure_cursor_agent(installer=cursor_installer)
    launch = mcp_launch_command()
    mcp = attach_custom_mcp(root, reviewer=reviewer, enable=enable) if attach else None
    build_mcp = attach_build_mcp(root, reviewer=reviewer) if attach else None
    unpack_parent = install_folder(dest) if unpacked else None
    health_check = install_self_check()
    if not health_check.get("ok"):
        return _fail(
            "essay.health did not pass after install.",
            unpacked=unpacked,
            root=str(root),
            pip=pip_body,
            prompt_present=prompt_present,
            health_check=health_check,
        )
    payload: dict[str, Any] = {
        "ok": True,
        "installed": True,
        "unpacked": unpacked,
        "root": str(root),
        "code_install_folder": str(root),
        "unpack_parent": str(unpack_parent) if unpack_parent is not None else None,
        "grok_config_home": grok_config_home(),
        "pip": pip_body,
        "prompt_present": prompt_present,
        "writer_command": launch,
        "cursor_cli": cursor_cli,
        "mcp": mcp,
        "build_mcp": build_mcp,
        "health_check": health_check,
        "install_residual_id": "40b-install-root",
        "install_residual": RESIDUALS["40b-install-root"],
    }
    return attach_friend_upgrade_fo_card(payload, root=root)


def _process_home() -> Path:
    """Home of this process. On Grok Bot that is the Linux computer, not the Mac."""
    return Path.home()


def _under_dir(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _one_mounted_mac_home() -> Path | None:
    """One Mac home already visible on this computer. Never creates /Users."""
    users = Path("/Users")
    if not users.is_dir():
        return None
    found: list[Path] = []
    try:
        children = list(users.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir() or child.name.startswith(".") or child.name in {"Shared", "root"}:
            continue
        if (child / "Documents").is_dir() or (child / "Library").is_dir():
            found.append(child)
    if len(found) == 1:
        return found[0]
    return None


def friend_mac_home() -> Path | None:
    """Home folder on the friend's Mac when this computer can already see it.

    Darwin uses this process home. Grok Bot Linux does not: that home is the
    bot computer. A mounted Mac home is ESSAY_WRITER_MAC_HOME when that
    directory already exists, or the one /Users home this computer can see.
    This function does not create the home.
    """
    if _on_mac():
        home = _process_home()
        return home if home.is_dir() else None
    override = os.environ.get("ESSAY_WRITER_MAC_HOME")
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        home = Path(text).expanduser()
        return home if home.is_dir() else None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    return _one_mounted_mac_home()


def recommended_mac_handoff_dir() -> Path | None:
    """Documents/Essay Bot on the friend's Mac. Not the Grok Bot Linux home."""
    home = friend_mac_home()
    if home is None:
        return None
    return home / "Documents" / RECOMMENDED_MAC_HANDOFF_NAME


def visible_canonical_mac_handoff_dir() -> Path | None:
    """Documents/Essay Bot when this computer already sees that folder on the Mac."""
    target = recommended_mac_handoff_dir()
    if target is None or not target.is_dir():
        return None
    return target


def upgrade_reread_tip_sha() -> str:
    """Stable id for the one-shot upgrade FO card. PR bodies cite this."""
    return hashlib.sha256(UPGRADE_REREAD_SPEECH.encode("utf-8")).hexdigest()[:12]


def _upgrade_reread_marker_path(root: Path) -> Path:
    return Path(root) / UPGRADE_REREAD_MARKER


def _take_upgrade_reread_card(root: Path) -> str | None:
    path = _upgrade_reread_marker_path(root)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and data.get("shown") is True:
            return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"shown": True}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return UPGRADE_REREAD_SPEECH
    return UPGRADE_REREAD_SPEECH


def attach_friend_upgrade_fo_card(result: dict[str, Any], *, root: Path) -> dict[str, Any]:
    """One-shot operator card after friend install or Custom MCP upgrade. Not student chat."""
    if not result.get("ok"):
        return result
    card = _take_upgrade_reread_card(root)
    if card:
        result["fo_card"] = card
        result["upgrade_reread_tip_sha"] = upgrade_reread_tip_sha()
    return result


def install_self_check() -> dict[str, Any]:
    """Read-only essay.health after install or attach. Cursor and Grok Build share this."""
    from essay_writer.health import essay_health

    health = essay_health()
    doors = health.get("doors")
    tool_count = len(doors) if isinstance(doors, list) else 0
    ok = bool(health.get("ok") and health.get("alive") and tool_count > 0)
    return {
        "ok": ok,
        "tool": "essay.health",
        "alive": health.get("alive"),
        "tool_count": tool_count,
    }


def _folder_on_friend_mac(path: Path | str) -> tuple[Path | None, str | None]:
    """Where a handoff path is created. The second value blocks a Linux mkdir."""
    raw = str(path).strip()
    if raw.casefold() == "open":
        return Path(raw), None
    if _on_mac():
        if raw.startswith("~") or Path(raw).is_absolute():
            return Path(raw).expanduser(), None
        home = friend_mac_home()
        if home is None:
            return None, "mac-not-mounted"
        return home / raw, None
    home = friend_mac_home()
    if raw.startswith("~"):
        if home is None:
            return None, "mac-not-mounted"
        rest = raw[1:].lstrip("/")
        return (home / rest) if rest else home, None
    folder = Path(raw).expanduser()
    if not folder.is_absolute():
        if home is None:
            return None, "mac-not-mounted"
        return home / folder, None
    process = _process_home()
    cloud = essay_paths.CLOUD_WORKSPACE
    if _under_dir(folder, process):
        if home is None:
            return None, "mac-not-mounted"
        tail = folder.resolve().relative_to(process.resolve())
        return home / tail, None
    if _under_dir(folder, cloud):
        return None, "mac-not-mounted"
    return folder, None


def _mac_handoff_store_path() -> Path | None:
    from essay_writer.setup import _secrets_path

    record = essay_paths.saved_setup_path()
    if record is not None:
        return _secrets_path(record)
    if essay_paths.CLOUD_WORKSPACE.is_dir():
        return essay_paths.CLOUD_WORKSPACE / SETUP_DIRNAME / "setup.secrets.json"
    return None


def read_mac_handoff_dir() -> Path | None:
    """Mac handoff folder from ESSAY_WRITER_MAC_DIR or setup.secrets.json."""
    override = os.environ.get(MAC_HANDOFF_SECRET)
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        return Path(text).expanduser()
    from essay_writer.setup import read_setup_secret

    stored = read_setup_secret(MAC_HANDOFF_SECRET)
    if stored:
        return Path(stored).expanduser()
    return None


_SKIP_HANDOFF = frozenset({"later", "skip", "decline"})
_OK_HANDOFF = frozenset({"ok", "okay", "confirm"})
_ANOTHER_HANDOFF = frozenset({"another", "another folder", "another path"})


def choose_mac_handoff(choice: str, *, folder: str | None = None) -> dict[str, Any]:
    """Apply the four-way Mac card. OK and a named folder are created on the Mac.

    Later, skip, and decline do not create a folder and do not set
    ESSAY_WRITER_MAC_DIR. Cursor and Grok Build both call this function.
    """
    text = choice.strip()
    folded = text.casefold()
    if folded in _SKIP_HANDOFF:
        return {
            "ok": True,
            "remembered": False,
            "created": False,
            "choice": "skip",
            "chat_only": True,
            "mac_folder_ready": False,
        }
    if folded in _OK_HANDOFF or folded == f"documents/{RECOMMENDED_MAC_HANDOFF_NAME}".casefold():
        target = recommended_mac_handoff_dir()
        if target is None:
            return {
                "ok": False,
                "remembered": False,
                "created": False,
                "choice": "ok",
                "reason": "mac-not-mounted",
                "chat_only": False,
                "mac_folder_ready": False,
            }
        result = remember_mac_handoff_dir(target)
        result["choice"] = "ok"
        result["remembered"] = bool(result.get("ok"))
        result["created"] = bool(result.get("ok"))
        result["chat_only"] = False
        result["mac_folder_ready"] = bool(result.get("ok"))
        return result
    if folded in _ANOTHER_HANDOFF and (not isinstance(folder, str) or not folder.strip()):
        return {
            "ok": False,
            "remembered": False,
            "created": False,
            "choice": "another",
            "reason": "Name the Mac folder.",
            "chat_only": False,
            "mac_folder_ready": False,
        }
    named = folder.strip() if folded in _ANOTHER_HANDOFF and isinstance(folder, str) else text
    if not named:
        return {
            "ok": False,
            "remembered": False,
            "created": False,
            "reason": "Name the Mac folder.",
            "chat_only": False,
            "mac_folder_ready": False,
        }
    result = remember_mac_handoff_dir(named)
    result["choice"] = "another"
    result["remembered"] = bool(result.get("ok"))
    result["created"] = bool(result.get("ok"))
    result["chat_only"] = False
    result["mac_folder_ready"] = bool(result.get("ok"))
    return result


def remember_mac_handoff_dir(path: Path | str) -> dict[str, Any]:
    """Remember the Mac handoff folder for copy_to_mac and mac_deliverables_dir.

    The folder is created on the friend's Mac. A Grok Bot Linux home path is
    not created and is not stored as ESSAY_WRITER_MAC_DIR.
    """
    located, blocked = _folder_on_friend_mac(path)
    if blocked:
        return {"ok": False, "reason": blocked, "remembered": False, "created": False}
    folder = located if located is not None else Path(path).expanduser()
    if any(part.casefold() == "researchdrive" for part in folder.parts):
        return {"ok": False, "reason": "That folder is not a copy path on this computer."}
    if folder.name.casefold() == "open":
        return {"ok": False, "reason": "Name the Mac handoff folder. The word open is not a folder."}
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    if not folder.is_dir():
        return {"ok": False, "reason": "The Mac handoff path is not a folder."}
    resolved = str(folder.resolve())
    store = _mac_handoff_store_path()
    if store is not None:
        existing: dict[str, str] = {}
        if store.is_file():
            try:
                data = json.loads(store.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            if isinstance(data, dict):
                existing = {
                    key: value
                    for key, value in data.items()
                    if isinstance(key, str) and isinstance(value, str) and value.strip()
                }
        existing[MAC_HANDOFF_SECRET] = resolved
        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
            os.chmod(store, 0o600)
        except OSError as exc:
            return {"ok": False, "reason": str(exc), "path": resolved}
    return {"ok": True, "path": resolved}


def mac_deliverables_dir() -> Path | None:
    """Mac handoff root: ESSAY_WRITER_MAC_DIR, else visible Documents/Essay Bot on the Mac."""
    override = os.environ.get(MAC_HANDOFF_SECRET)
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        return Path(text).expanduser()
    in_test = bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("ESSAY_WRITER_ROOT"))
    remembered = read_mac_handoff_dir() if not in_test else None
    if remembered is not None:
        return remembered
    return visible_canonical_mac_handoff_dir()


def module_mac_deliverables_dir(module: str) -> Path | None:
    """Documents/Essay Bot/<module> when the Mac handoff root is remembered."""
    if not isinstance(module, str) or not module.strip():
        return None
    base = mac_deliverables_dir()
    if base is None:
        return None
    return base / module.strip()


def module_shared_mac_deliverables_dir(essay_id: str) -> Path | None:
    """Documents/Essay Bot/<module>/shared for module-common Mac copies."""
    if not isinstance(essay_id, str) or not essay_id.strip():
        return None
    module = essay_paths.module_code(essay_id.strip())
    parent = module_mac_deliverables_dir(module)
    if parent is None:
        return None
    return parent / "shared"


def sequence_mac_deliverables_dir(essay_id: str) -> Path | None:
    """Documents/Essay Bot/<module>/<essay_id> when the Mac handoff root is remembered."""
    if not isinstance(essay_id, str) or not essay_id.strip():
        return None
    module = essay_paths.module_code(essay_id.strip())
    parent = module_mac_deliverables_dir(module)
    if parent is None:
        return None
    return parent / essay_id.strip()


def sequence_mac_handoff_place(essay_id: str, leaf: str) -> str:
    """Chat display path under Documents/Essay Bot/<module>/<essay_id>/."""
    text = essay_id.strip()
    module = essay_paths.module_code(text)
    return f"Documents/Essay Bot/{module}/{text}/{leaf}"


def ensure_sequence_mac_folder(essay_id: str) -> dict[str, Any]:
    """Create module, shared, and per-sequence Mac folders. Stage 1 Confirm calls this."""
    module_dir = module_mac_deliverables_dir(essay_paths.module_code(essay_id))
    shared_dir = module_shared_mac_deliverables_dir(essay_id)
    folder = sequence_mac_deliverables_dir(essay_id)
    if folder is None or module_dir is None or shared_dir is None:
        return {
            "ok": True,
            "created": False,
            "remembered": False,
            "reason": "mac-not-mounted",
        }
    for target in (module_dir, shared_dir, folder):
        if _internal_volume(target):
            return {
                "ok": False,
                "created": False,
                "remembered": True,
                "reason": "That folder is not a copy path on this computer.",
            }
    existed = folder.is_dir()
    try:
        module_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "created": False, "remembered": True, "reason": str(exc)}
    if not folder.is_dir():
        return {
            "ok": False,
            "created": False,
            "remembered": True,
            "reason": "The Mac copy path is not a folder.",
        }
    return {
        "ok": True,
        "created": not existed,
        "remembered": True,
        "path": str(folder.resolve()),
        "module_path": str(module_dir.resolve()),
        "shared_path": str(shared_dir.resolve()),
    }


def _mac_copy_folder(source: Path, mac_dir: Path | None) -> Path | None:
    if mac_dir is not None:
        return Path(mac_dir).expanduser()
    from essay_writer.build_office import essay_id_from_deliverable_path

    essay_id = essay_id_from_deliverable_path(source)
    if essay_id:
        seq_folder = sequence_mac_deliverables_dir(essay_id)
        if seq_folder is not None:
            return seq_folder
    return mac_deliverables_dir()


def mac_deliverables_record(essay_id: str) -> Path:
    """Where this sequence remembers Mac copies. One file. No folder listing."""

    return work_dir(essay_id) / MAC_DELIVERABLES_NAME


def remember_mac_deliverable(source: Path, target: Path) -> None:
    """Store one copied Word or zip path on the sequence it came from."""
    from essay_writer.build_office import essay_id_from_deliverable_path

    essay_id = essay_id_from_deliverable_path(source)
    if not essay_id or target.suffix.lower() not in DELIVERABLE_SUFFIXES:
        return
    try:
        expanded = target.expanduser()
    except OSError:
        return
    if expanded.is_symlink() or not expanded.is_file():
        return
    try:
        resolved = expanded.resolve()
    except OSError:
        return
    if any(part.casefold() == "researchdrive" for part in resolved.parts):
        return
    for root in (workspace_root(), kb1_root()):
        try:
            base = root.resolve()
        except OSError:
            base = root
        if resolved == base or resolved.is_relative_to(base):
            return
    path = mac_deliverables_record(essay_id)
    try:
        refuse_repo_write(path)
    except RepoSaveRefused:
        return
    existing: list[str] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        raw = data.get("paths") if isinstance(data, dict) else None
        if isinstance(raw, list):
            existing = [item for item in raw if isinstance(item, str) and item.strip()]
    stored = str(resolved)
    if stored not in existing:
        existing.append(stored)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"paths": existing}, indent=2) + "\n"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return


def sequence_mac_candidates(essay_id: str) -> list[str]:
    """Saved copy_to_mac paths, then exact default names in the Mac handoff folder.

    Does not list Documents, home, or the handoff folder.
    """
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = raw.strip()
        if not text or text in seen:
            return
        seen.add(text)
        found.append(text)

    record = mac_deliverables_record(essay_id)
    if record.is_file():
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        paths = data.get("paths") if isinstance(data, dict) else None
        if isinstance(paths, list):
            for item in paths:
                if isinstance(item, str):
                    add(item)
    folder = sequence_mac_deliverables_dir(essay_id)
    if folder is not None:
        try:
            base = folder.expanduser()
        except OSError:
            base = folder
        if not base.is_absolute():
            base = base.resolve()
        for name in (f"{essay_id}.docx", *KNOWN_MAC_DELIVERABLE_NAMES):
            add(str(base / name))
    return found


def copy_deliverable_to_mac(source: Path, *, mac_dir: Path | None = None) -> dict[str, Any]:
    """Copy an existing .docx or .zip onto the Mac. Other files stay where they are.

    A directory copies each Word file and zip sitting directly in it.
    """
    path = Path(source).expanduser()
    if path.is_dir():
        files = [
            child
            for child in sorted(path.iterdir())
            if child.is_file() and child.suffix.lower() in DELIVERABLE_SUFFIXES
        ]
        copies = [copy_deliverable_to_mac(child, mac_dir=mac_dir) for child in files]
        return {
            "ok": all(item.get("ok", False) for item in copies) if copies else True,
            "copied": any(item.get("copied") for item in copies),
            "source": str(path),
            "files": copies,
        }
    if path.suffix.lower() not in DELIVERABLE_SUFFIXES:
        return {
            "ok": False,
            "copied": False,
            "source": str(path),
            "reason": "Only a Word .docx or a .zip is copied.",
        }
    if not path.is_file():
        return {"ok": False, "copied": False, "source": str(path), "reason": "That deliverable is not a file."}
    folder = _mac_copy_folder(path, mac_dir)
    if folder is None:
        return {
            "ok": True,
            "copied": False,
            "source": str(path),
            "reason": "mac-not-mounted",
            "residual": MAC_RESIDUAL,
            "next": say(MAC_NOT_MOUNTED_CHAT),
        }
    if _internal_volume(folder):
        return {
            "ok": False,
            "copied": False,
            "source": str(path),
            "reason": "That folder is not a copy path on this computer.",
        }
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / path.name
        if target.exists() and not target.is_file():
            return {
                "ok": False,
                "copied": False,
                "source": str(path),
                "reason": "The Mac copy path is a folder.",
            }
        if path.resolve() == target.resolve():
            cleared = _clear_delivered(target)
            remember_mac_deliverable(path, target)
            return {
                "ok": True,
                "copied": True,
                "source": str(path),
                "path": str(target),
                "already": True,
                "quarantine": cleared,
            }
        replaced = target.is_file()
        shutil.copy2(path, target)
        cleared = _clear_delivered(target)
    except OSError as exc:
        return {"ok": False, "copied": False, "source": str(path), "reason": str(exc)}
    remember_mac_deliverable(path, target)
    return {
        "ok": True,
        "copied": True,
        "source": str(path),
        "path": str(target),
        "replaced": replaced,
        "quarantine": cleared,
    }


def _clear_delivered(path: Path) -> dict[str, Any]:
    """Quarantine and provenance come off the Documents copy before handoff."""
    from essay_writer.quarantine import clear_mac_quarantine

    return clear_mac_quarantine(path)


def _parse(args: list[str]) -> dict[str, Any]:
    reviewer = True
    upload: str | None = None
    dest: str | None = None
    action = "install"
    copy_path: str | None = None
    mac_handoff: str | None = None
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--reviewer":
            reviewer = True
        elif token == "--no-reviewer":
            reviewer = False
        elif token == "--remember-mac-dir":
            action = "remember_mac"
            index += 1
            if index >= len(args):
                raise ValueError("--remember-mac-dir needs a folder")
            mac_handoff = args[index]
        elif token in {"--upload", "--install-upload"}:
            action = "install"
            index += 1
            if index >= len(args):
                raise ValueError(f"{token} needs a zip path")
            upload = args[index]
        elif token == "--dest":
            index += 1
            if index >= len(args):
                raise ValueError("--dest needs a folder")
            dest = args[index]
        elif token == "--attach-mcp":
            action = "attach"
        elif token == "--copy-to-mac":
            action = "copy"
            index += 1
            if index >= len(args):
                raise ValueError("--copy-to-mac needs a file or folder")
            copy_path = args[index]
        else:
            raise ValueError(token)
        index += 1
    if action == "copy" and (upload or dest):
        raise ValueError("--copy-to-mac does not unpack or install")
    if action == "attach" and upload:
        raise ValueError("--attach-mcp does not take a zip")
    if action == "remember_mac" and (upload or dest or copy_path):
        raise ValueError("--remember-mac-dir does not unpack, install, or copy")
    return {
        "action": action,
        "reviewer": reviewer,
        "upload": upload,
        "dest": dest,
        "copy_path": copy_path,
        "mac_handoff": mac_handoff,
    }


def _record_copy_handoff(copy_path: str | None, result: dict[str, Any]) -> None:
    """One ml-events row for --copy-to-mac. The stream stays off when debug is off."""
    from essay_writer.build_office import essay_id_from_deliverable_path
    from essay_writer.ml_events import handoff_outcome, handoff_refuse_reason, note_cli_handoff

    payload = result if isinstance(result, dict) else None
    essay_id = payload.get("essay_id") if isinstance(payload, dict) else None
    if not isinstance(essay_id, str) or not essay_id.strip():
        essay_id = essay_id_from_deliverable_path(Path(copy_path or ""))
    outcome = handoff_outcome(payload)
    reason = handoff_refuse_reason(payload) if outcome == "refused" else ""
    note_cli_handoff(
        "--copy-to-mac",
        essay_id if isinstance(essay_id, str) else None,
        outcome,
        reason,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        parsed = _parse(args)
    except ValueError as exc:
        sys.stderr.write(
            "usage: first_run.py [--upload ZIP] [--dest FOLDER] [--no-reviewer]\n"
            "       essay-writer [--install-upload ZIP] [--attach-mcp] [--copy-to-mac PATH]\n"
            "       [--remember-mac-dir FOLDER] [--no-reviewer]\n"
            f"{exc}\n"
        )
        return 2
    if parsed["action"] == "remember_mac":
        result = choose_mac_handoff(parsed["mac_handoff"])
    elif parsed["action"] == "copy":
        from essay_writer.build_office import build_deliverable_handoff

        result = build_deliverable_handoff(Path(parsed["copy_path"]))
        _record_copy_handoff(parsed["copy_path"], result)
    elif parsed["action"] == "attach":
        root = package_root()
        cursor_cli = ensure_cursor_agent()
        cursor = attach_custom_mcp(root, reviewer=parsed["reviewer"])
        build = attach_build_mcp(root, reviewer=parsed["reviewer"])
        result = dict(cursor)
        result["cursor_cli"] = cursor_cli
        result["build"] = build
        result["ok"] = bool(cursor.get("ok") and build.get("ok"))
        if result["ok"]:
            health_check = install_self_check()
            result["health_check"] = health_check
            if not health_check.get("ok"):
                result["ok"] = False
                result["reason"] = "essay.health did not pass after attach."
            attach_friend_upgrade_fo_card(result, root=root)
    else:
        upload = Path(parsed["upload"]) if parsed["upload"] else None
        dest = Path(parsed["dest"]) if parsed["dest"] else None
        if isinstance(parsed["upload"], str) and _clone_url(parsed["upload"]):
            result = _fail("Nothing is cloned. Pass the uploaded zip, not a git URL.")
        else:
            result = install_uploaded_copy(upload, dest=dest, reviewer=parsed["reviewer"])
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
