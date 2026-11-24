"""Always-on metadata for a fallback, a repair, or a refusal.

One JSON line in the app folder. The line has a code, a severity, and a
disposition. It does not have essay text, a prompt, or a file body. Rotation,
wipe, and the support bundle are a later workstream.
"""

from __future__ import annotations

import json
from pathlib import Path

_SEVERITY = frozenset({"warn", "info"})
_DISPOSITION = frozenset({"retry", "fallback", "refuse"})


def incident_path() -> Path:
    from essay_writer.paths import workspace_root

    return workspace_root() / "incident.jsonl"


def note(
    code: str,
    *,
    severity: str,
    disposition: str,
    tool: str = "",
    stage: str = "",
) -> None:
    """Append one metadata line. A logging failure does not stop the student."""
    if severity not in _SEVERITY or disposition not in _DISPOSITION:
        return
    if not code or any(character.isspace() for character in code):
        return
    payload = {
        "code": code,
        "disposition": disposition,
        "severity": severity,
        "stage": stage,
        "tool": tool,
    }
    line = json.dumps(payload, sort_keys=True) + "\n"
    path = incident_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            previous = path.read_text(encoding="utf-8").splitlines()
            if previous:
                last = json.loads(previous[-1])
                if isinstance(last, dict) and last.get("code") == code and last.get("tool") == tool:
                    return
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except (OSError, json.JSONDecodeError):
        return
