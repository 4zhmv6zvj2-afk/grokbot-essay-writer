"""Command-line entry point for first-run setup.

The parser, usage text, and main dispatch live here. `essay_writer.first_run`
remains the importable facade, so callers keep importing `main` from there.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from essay_writer import first_run_common, first_run_host, first_run_install, first_run_mac


def _parse(args: list[str]) -> dict[str, Any]:
    reviewer = True
    upload: str | None = None
    dest: str | None = None
    action = "install"
    copy_path: str | None = None
    mac_handoff: str | None = None
    allow_cursor_install: bool | None = None
    cursor_sha256: str | None = None
    upload_sha256: str | None = None
    index = 0
    while index < len(args):
        token = args[index]
        if token == "--reviewer":
            reviewer = True
        elif token == "--no-reviewer":
            reviewer = False
        elif token == "--install-cursor":
            allow_cursor_install = True
        elif token == "--no-install-cursor":
            allow_cursor_install = False
        elif token == "--cursor-sha256":
            index += 1
            if index >= len(args):
                raise ValueError("--cursor-sha256 needs a 64-character hex SHA-256")
            value = args[index].strip().casefold()
            if first_run_install._SHA256_HEX.fullmatch(value) is None:
                raise ValueError("--cursor-sha256 needs a 64-character hex SHA-256")
            cursor_sha256 = value
        elif token == "--upload-sha256":
            index += 1
            if index >= len(args):
                raise ValueError("--upload-sha256 needs a 64-character hex SHA-256")
            value = args[index].strip().casefold()
            if first_run_install._SHA256_HEX.fullmatch(value) is None:
                raise ValueError("--upload-sha256 needs a 64-character hex SHA-256")
            upload_sha256 = value
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
    if action in {"copy", "remember_mac"} and allow_cursor_install is not None:
        raise ValueError("--install-cursor does not copy or remember")
    if action in {"copy", "remember_mac"} and cursor_sha256 is not None:
        raise ValueError("--cursor-sha256 does not copy or remember")
    if upload_sha256 is not None and not upload:
        raise ValueError("--upload-sha256 needs --upload ZIP")
    return {
        "action": action,
        "reviewer": reviewer,
        "upload": upload,
        "dest": dest,
        "copy_path": copy_path,
        "mac_handoff": mac_handoff,
        "allow_cursor_install": allow_cursor_install,
        "cursor_sha256": cursor_sha256,
        "upload_sha256": upload_sha256,
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
            "usage: first_run.py [--upload ZIP --upload-sha256 SHA256] [--dest FOLDER]\n"
            "       [--no-reviewer] [--install-cursor | --no-install-cursor]\n"
            "       [--cursor-sha256 SHA256]\n"
            "       essay-writer [--install-upload ZIP --upload-sha256 SHA256] [--attach-mcp]\n"
            "       [--copy-to-mac PATH] [--remember-mac-dir FOLDER] [--no-reviewer]\n"
            "       [--install-cursor] [--cursor-sha256 SHA256]\n"
            f"{exc}\n"
        )
        return 2
    if parsed["action"] == "remember_mac":
        result = first_run_mac.choose_mac_handoff(parsed["mac_handoff"])
    elif parsed["action"] == "copy":
        from essay_writer.build_office import build_deliverable_handoff

        result = build_deliverable_handoff(Path(parsed["copy_path"]))
        _record_copy_handoff(parsed["copy_path"], result)
    elif parsed["action"] == "attach":
        root = first_run_common.package_root()
        cursor_cli = first_run_install.ensure_cursor_agent(
            allow_install=parsed["allow_cursor_install"],
            expected_sha256=parsed["cursor_sha256"],
        )
        cursor = first_run_host.attach_custom_mcp(root, reviewer=parsed["reviewer"])
        build = first_run_host.attach_build_mcp(root, reviewer=parsed["reviewer"])
        result = dict(cursor)
        result["cursor_cli"] = cursor_cli
        result["build"] = build
        result["ok"] = bool(cursor.get("ok") and build.get("ok"))
        if result["ok"]:
            health_check = first_run_install.install_self_check()
            result["health_check"] = health_check
            if not health_check.get("ok"):
                result["ok"] = False
                result["reason"] = "essay.health did not pass after attach."
            first_run_mac.attach_friend_upgrade_fo_card(result, root=root)
    else:
        upload = Path(parsed["upload"]) if parsed["upload"] else None
        dest = Path(parsed["dest"]) if parsed["dest"] else None
        if isinstance(parsed["upload"], str) and first_run_common._clone_url(parsed["upload"]):
            result = first_run_common._fail(
                "Nothing is cloned. Pass the uploaded zip, not a git URL."
            )
        else:
            result = first_run_install.install_uploaded_copy(
                upload,
                dest=dest,
                reviewer=parsed["reviewer"],
                allow_cursor_install=parsed["allow_cursor_install"],
                cursor_sha256=parsed["cursor_sha256"],
                upload_sha256=parsed["upload_sha256"],
            )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
