"""Structured JSONL for operators and shells.

Students stay off. The stream records stage, confirm, digest, paths, shell,
and outcome events. It is not a chat transcript. On and off follow
essay_writer.debug_log.debug_enabled (ESSAY_WRITER_DEBUG, setup debug true,
and the operator end-to-end flag). Setup where alone does not.

Cursor and Grok Build share this writer. note_call is the only door hook.
The file is essay_writer.debug_log.ml_events_path, the same path
wipe_operator_log_files clears with debug.log. There is no second wipe door.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from essay_writer.debug_log import ML_EVENTS_FILENAME as FILENAME  # noqa: F401
from essay_writer.debug_log import ml_events_path
from essay_writer.paths import (
    ESSAY_ID,
    SEQUENCE_ID,
    module_code,
    sequence_number,
    work_dir,
    workspace_root,
)

KINDS = ("stage", "confirm", "digest", "paths", "shell", "outcome")

_STAGE_IDS = frozenset({"1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9", "10", "eqr"})
_PHASES = frozenset({"draft", "confirm", "read"})
_SHELLS = frozenset({"Cursor", "Build"})
_SHELL_EVENTS = frozenset({"start", "done", "exit"})
_TOKEN = re.compile(r"^[a-z][a-z0-9._-]{0,48}$")
_SHORT = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,40}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_RELATIVE = re.compile(r"^(?:Essay-writer|uploads|KB1|unassigned)/[A-Za-z0-9_./-]{1,160}$")
_DOCUMENTS = re.compile(
    r"^Documents/(?:Essay Bot/[A-Z0-9]+/[A-Z0-9]+-[0-9]+/|[A-Z0-9]+-10/)[A-Z0-9]+-final\.docx$"
)
_SUFFIXES = frozenset({"docx", "zip", "pdf", "md", "json", "txt"})
_STAGE_TOOLS = frozenset({"essay.stage", "essay.review"})


def events_enabled() -> bool:
    """Same split as debug.log. Students off. Cloud where alone stays off."""
    from essay_writer.debug_log import debug_enabled

    return debug_enabled()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _body(result: object) -> dict[str, object] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict):
                return item
    return None


def _tool(tool: object) -> str:
    if isinstance(tool, str) and _TOKEN.fullmatch(tool):
        return tool
    return "unknown"


def _id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()

    if ESSAY_ID.fullmatch(text) or SEQUENCE_ID.fullmatch(text):
        return text
    return None


def _phase(arguments: dict[str, object], body: dict[str, object] | None) -> str:
    raw = arguments.get("confirmPhase")
    if raw not in _PHASES and isinstance(body, dict):
        raw = body.get("confirmPhase")
    if raw in _PHASES:
        return raw
    return "read"


def _stage_id(value: object) -> str | None:
    if isinstance(value, str) and value in _STAGE_IDS:
        return value
    return None


def _flag(body: dict[str, object] | None, key: str) -> bool | None:
    if not isinstance(body, dict):
        return None
    value = body.get(key)
    if isinstance(value, bool):
        return value
    return None


def _sha(value: object) -> str | None:
    if isinstance(value, str) and _SHA.fullmatch(value):
        return value
    return None


def _prose_chars(value: object) -> int:
    if isinstance(value, str) and value.strip() and _sha(value) is None:
        return len(value)
    return 0


def _essay_id(arguments: dict[str, object], body: dict[str, object] | None) -> str | None:
    found = _id(arguments.get("essay_id"))
    if found:
        return found
    if isinstance(body, dict):
        return _id(body.get("essay_id"))
    return None


def _file_record(path: Path, display: str, *, mounted: bool | None = None) -> dict[str, object] | None:
    if ".." in display:
        return None
    if not (_RELATIVE.fullmatch(display) or _DOCUMENTS.fullmatch(display)):
        return None
    record: dict[str, object] = {"display": display, "exists": path.is_file()}
    if mounted is not None:
        record["mounted"] = mounted
    if not record["exists"]:
        return record
    try:
        record["mtime_ns"] = path.stat().st_mtime_ns
        record["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        record["exists"] = False
        record.pop("mtime_ns", None)
        record.pop("sha256", None)
    return record


def _stage10_files(essay_id: str) -> list[dict[str, object]]:
    from essay_writer.late_chain import documents_root, final_place

    module = module_code(essay_id)
    number = sequence_number(essay_id)
    if number is None:
        display = f"Essay-writer/{module}/output/{essay_id}.docx"
    else:
        display = f"Essay-writer/{module}/sequences/{number}/output/{essay_id}.docx"
    files: list[dict[str, object]] = []
    sequence = _file_record(work_dir(essay_id) / "output" / f"{essay_id}.docx", display)
    if sequence is not None:
        files.append(sequence)
    place = final_place(essay_id)
    root = documents_root()
    if root is None:
        documents = None
        if _DOCUMENTS.fullmatch(place):
            documents = {"display": place, "exists": False, "mounted": False}
    else:
        documents = _file_record(
            root / f"{module}-10" / f"{module}-final.docx",
            place,
            mounted=True,
        )
    if documents is not None:
        files.append(documents)
    return files


def _relative_file(display: object) -> dict[str, object] | None:
    if not isinstance(display, str):
        return None
    text = display.strip()
    if not _RELATIVE.fullmatch(text) or ".." in text:
        return None

    return _file_record(workspace_root() / text, text)


def _suffix(value: str) -> str:
    match = re.search(r"\.([A-Za-z0-9]{1,5})$", value.strip())
    if match and match.group(1).casefold() in _SUFFIXES:
        return match.group(1).casefold()
    return "other"


def _local_summary(arguments: dict[str, object], body: dict[str, object] | None) -> tuple[int, list[str]]:
    raw = arguments.get("localPaths")
    if raw is None and isinstance(body, dict):
        raw = body.get("local")
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, list):
        items = [item for item in raw if isinstance(item, str)]
    else:
        items = []
    if not items:
        return 0, []
    return len(items), sorted({_suffix(item) for item in items})


def _gate_code(value: object) -> str | None:
    if isinstance(value, str) and _TOKEN.fullmatch(value.strip()):
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return str(value)
    return None


def _failed_gate(body: dict[str, object] | None) -> str | None:
    """The first failed essay.gates check. An essay-id refusal has no gate."""
    if not isinstance(body, dict):
        return None
    gates = body.get("gates")
    if isinstance(gates, list):
        for item in gates:
            if not isinstance(item, dict) or item.get("passed") is not False:
                continue
            name = _gate_code(item.get("name"))
            if name:
                return name
            number = _gate_code(item.get("gate"))
            if number:
                return number
    plagiarism = body.get("plagiarism")
    if isinstance(plagiarism, dict) and plagiarism.get("passed") is False:
        code = _gate_code(plagiarism.get("code"))
        if code:
            return code
    blockers = body.get("before_word")
    if isinstance(blockers, list):
        for item in blockers:
            if not isinstance(item, dict):
                continue
            code = _gate_code(item.get("code"))
            if code:
                return code
    return None


def _gates_failed(body: dict[str, object] | None) -> bool:
    if not isinstance(body, dict):
        return False
    ok = _flag(body, "ok")
    if ok is None:
        ok = _flag(body, "passed")
    return ok is False


def _outcome(
    tool: str,
    arguments: dict[str, object],
    body: dict[str, object] | None,
    error: BaseException | None,
    when: str,
    phase: str,
    essay_id: str | None,
) -> dict[str, object]:
    event: dict[str, object] = {"kind": "outcome", "t": when, "tool": tool, "phase": phase}
    if essay_id:
        event["essay_id"] = essay_id
    module = _id(arguments.get("module"))
    if module and module != essay_id:
        event["module"] = module
    if error is not None:
        event["ok"] = False
        name = type(error).__name__
        if _SHORT.fullmatch(name):
            event["error"] = name
    else:
        ok = _flag(body, "ok")
        if ok is None:
            ok = _flag(body, "passed")
        if ok is not None:
            event["ok"] = ok
    for key in ("wrote", "stored", "advanced"):
        flag = _flag(body, key)
        if flag is not None:
            event[key] = flag
    if isinstance(body, dict):
        refused = _gate_code(body.get("refused"))
        if refused:
            event["refused"] = refused
    if tool == "essay.gates" and _gates_failed(body):
        event["ok"] = False
        gate = _failed_gate(body)
        if gate:
            event["gate"] = gate
        if "refused" not in event:
            event["refused"] = gate or "gates"
    return event


def _stage_event(
    tool: str,
    arguments: dict[str, object],
    body: dict[str, object] | None,
    when: str,
    phase: str,
    essay_id: str | None,
) -> dict[str, object] | None:
    stage = _stage_id(arguments.get("stage"))
    if stage is None and isinstance(body, dict):
        stage = _stage_id(body.get("stage"))
    if tool not in _STAGE_TOOLS and stage is None:
        return None
    if tool not in _STAGE_TOOLS:
        return None
    event: dict[str, object] = {"kind": "stage", "t": when, "tool": tool, "phase": phase}
    if essay_id:
        event["essay_id"] = essay_id
    if stage:
        event["stage"] = stage
    for key in ("stored", "advanced"):
        flag = _flag(body, key)
        if flag is not None:
            event[key] = flag
    if isinstance(body, dict):
        current = _stage_id(body.get("current"))
        if current:
            event["current"] = current
        if "next_stage" in body:
            nxt = body.get("next_stage")
            if nxt is None or _stage_id(nxt):
                event["next_stage"] = nxt if nxt is None else _stage_id(nxt)
    return event


def _confirm_event(
    tool: str,
    arguments: dict[str, object],
    body: dict[str, object] | None,
    when: str,
    phase: str,
    essay_id: str | None,
) -> dict[str, object] | None:
    action = arguments.get("cardAction")
    if not isinstance(action, str) or not _TOKEN.fullmatch(action):
        action = None
    if phase != "confirm" and action != "confirm":
        return None
    event: dict[str, object] = {
        "kind": "confirm",
        "t": when,
        "tool": tool,
        "phase": phase,
        "card_present": isinstance(body, dict) and isinstance(body.get("card"), dict),
    }
    if essay_id:
        event["essay_id"] = essay_id
    stage = _stage_id(arguments.get("stage"))
    if stage is None and isinstance(body, dict):
        stage = _stage_id(body.get("stage"))
    if stage:
        event["stage"] = stage
    if action:
        event["card_action"] = action
    for key in ("stored", "advanced", "wrote"):
        flag = _flag(body, key)
        if flag is not None:
            event[key] = flag
    return event


def _digest_sources(arguments: dict[str, object], body: dict[str, object] | None) -> list[tuple[str, object]]:
    sources: list[tuple[str, object]] = [("card_digest", arguments.get("cardDigest"))]
    if isinstance(body, dict):
        sources.append(("card_digest", body.get("cardDigest")))
        sources.append(("payload", body.get("digest")))
        card = body.get("card")
        if isinstance(card, dict):
            sources.append(("posted", card.get("digest")))
            sources.append(("card_digest", card.get("cardDigest")))
    return sources


def _digest_event(
    tool: str,
    arguments: dict[str, object],
    body: dict[str, object] | None,
    when: str,
    essay_id: str | None,
) -> dict[str, object] | None:
    found: dict[str, str] = {}
    omitted = 0
    seen = False
    for key, value in _digest_sources(arguments, body):
        if not isinstance(value, str) or not value.strip():
            continue
        seen = True
        hashed = _sha(value)
        if hashed:
            found.setdefault(key, hashed)
            continue
        omitted = max(omitted, _prose_chars(value))
    if not seen:
        return None
    event: dict[str, object] = {"kind": "digest", "t": when, "tool": tool}
    if essay_id:
        event["essay_id"] = essay_id
    event.update(found)
    if omitted:
        event["omitted"] = True
        event["chars"] = omitted
    return event


def _paths_event(
    tool: str,
    arguments: dict[str, object],
    body: dict[str, object] | None,
    when: str,
    phase: str,
    essay_id: str | None,
) -> dict[str, object] | None:
    files: list[dict[str, object]] = []
    stage = _stage_id(arguments.get("stage"))
    if stage is None and isinstance(body, dict):
        stage = _stage_id(body.get("stage"))
    if tool == "essay.stage" and stage == "10" and phase == "confirm" and essay_id:
        files.extend(_stage10_files(essay_id))
    if isinstance(body, dict):
        extra = _relative_file(body.get("path"))
        if extra is not None and all(item.get("display") != extra.get("display") for item in files):
            files.append(extra)
    count, suffixes = _local_summary(arguments, body)
    if not files and count == 0:
        return None
    event: dict[str, object] = {"kind": "paths", "t": when, "tool": tool, "files": files}
    if essay_id:
        event["essay_id"] = essay_id
    if count:
        event["local_count"] = count
        event["local_suffixes"] = suffixes
    return event


def _shell_event(
    tool: str,
    body: dict[str, object] | None,
    when: str,
    essay_id: str | None,
) -> dict[str, object] | None:
    if not isinstance(body, dict):
        return None
    event_name = body.get("mid_office")
    shell = body.get("mid_shell")
    if event_name not in _SHELL_EVENTS or shell not in _SHELLS:
        return None
    event: dict[str, object] = {
        "kind": "shell",
        "t": when,
        "tool": tool,
        "shell": shell,
        "event": event_name,
    }
    if essay_id:
        event["essay_id"] = essay_id
    if event_name == "start":
        stage = _stage_id(body.get("stage"))
        if stage:
            event["stage"] = stage
        model = body.get("model")
        if isinstance(model, str) and model.strip() and " " not in model:
            event["model"] = model.strip()
        reasoning = body.get("reasoning")
        if isinstance(reasoning, str) and reasoning in {"low", "medium", "high", "xhigh"}:
            event["reasoning"] = reasoning
        fast = body.get("fast")
        if isinstance(fast, bool):
            event["fast"] = fast
        window = body.get("context_window")
        if isinstance(window, int) and not isinstance(window, bool):
            event["context_window"] = window
    if event_name in {"done", "exit"}:
        code = body.get("mid_exit_code")
        if isinstance(code, int) and not isinstance(code, bool):
            event["exit_code"] = code
        cli_line = body.get("mid_stderr")
        if isinstance(cli_line, str) and cli_line.strip():
            event["stderr"] = " ".join(cli_line.split())[:160]
    return event


def _events(
    tool: str,
    arguments: dict[str, object],
    result: object,
    error: BaseException | None,
) -> list[dict[str, object]]:
    body = _body(result)
    when = _now()
    name = _tool(tool)
    phase = _phase(arguments, body)
    essay_id = _essay_id(arguments, body)
    built = [
        _outcome(name, arguments, body, error, when, phase, essay_id),
        _stage_event(name, arguments, body, when, phase, essay_id),
        _confirm_event(name, arguments, body, when, phase, essay_id),
        _digest_event(name, arguments, body, when, essay_id),
        _paths_event(name, arguments, body, when, phase, essay_id),
        _shell_event(name, body, when, essay_id),
    ]
    return [item for item in built if item is not None]


def note_stage10_rewrite_paths(essay_id: str) -> None:
    """Paths event after write_stage10 rewrites the sequence Word file on disk.

    Stage 10 confirm already emits paths through note_call; a direct rewrite
    (for example pack_from_docx recovery) must refresh the same stream.
    """
    if not events_enabled():
        return
    found = _id(essay_id.strip() if isinstance(essay_id, str) else "")
    if not found:
        return
    try:
        files = _stage10_files(found)
        if not files:
            return
        event: dict[str, object] = {
            "kind": "paths",
            "t": _now(),
            "tool": "essay.stage",
            "essay_id": found,
            "files": files,
        }
        path = ml_events_path(found)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return


def handoff_outcome(result: dict[str, object] | None) -> str:
    """copy_only when a handoff copied existing files. rebuilt when it wrote them. refused otherwise."""
    if not isinstance(result, dict):
        return "refused"
    if result.get("rebuilt") is True:
        return "rebuilt"
    if result.get("ok") is False or result.get("copied") is not True:
        return "refused"
    return "copy_only"


def _map_refuse_reason(text: str) -> str:
    cleaned = " ".join(text.split())
    folded = cleaned.casefold().rstrip(".")
    if folded in {"mac-not-mounted", "documents unmounted", "unmounted"} or folded.endswith(
        " unmounted"
    ):
        return "unmounted"
    if (
        folded in {"missing file", "that deliverable is not a file"}
        or "not a file" in folded
        or "no such file" in folded
    ):
        return "missing file"
    if len(cleaned) > 160:
        return cleaned[:160].rstrip()
    return cleaned


def handoff_refuse_reason(result: dict[str, object] | None) -> str:
    """Short copy-to-Mac refuse reason: unmounted, missing file, or the return."""
    if not isinstance(result, dict):
        return "no return"
    raw = result.get("reason")
    if isinstance(raw, str) and raw.strip():
        return _map_refuse_reason(raw)
    files = result.get("files")
    if isinstance(files, list):
        if not files and result.get("copied") is not True:
            return "missing file"
        for item in files:
            if not isinstance(item, dict) or item.get("copied") is True:
                continue
            nested = handoff_refuse_reason(item)
            if nested and nested not in {"no return", "not copied"}:
                return nested
    if result.get("ok") is False or result.get("copied") is not True:
        return "not copied"
    return ""


def note_cli_handoff(
    flag: str, essay_id: str | None, outcome: str, reason: str = ""
) -> None:
    """One ml-events row for an off-door CLI handoff. Off when the stream is off."""
    if outcome not in {"copy_only", "rebuilt", "refused"}:
        return
    if not isinstance(flag, str) or not flag.startswith("--") or len(flag) > 40:
        return
    if not events_enabled():
        return
    try:
        event: dict[str, object] = {
            "kind": "outcome",
            "t": _now(),
            "tool": "essay-writer",
            "flag": flag,
            "outcome": outcome,
        }
        if outcome == "refused" and isinstance(reason, str) and reason.strip():
            event["reason"] = " ".join(reason.split())[:160]
        found = _id(essay_id) if isinstance(essay_id, str) else None
        if found:
            event["essay_id"] = found
        path = ml_events_path(found)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        return


def _prepare_sequence_land_header(path: Path, essay_id: str) -> None:
    """First ml-events row when a sequence trail opens. Mirrors debug.log land header."""
    if path.is_file():
        return
    from essay_writer.debug_log import land_sha

    found = _id(essay_id)
    if not found:
        return
    land = land_sha()
    event: dict[str, object] = {
        "kind": "outcome",
        "t": _now(),
        "tool": "essay-writer.land",
        "essay_id": found,
        "ok": True,
        "wrote": False,
        "land": land,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    path.write_text(line + "\n", encoding="utf-8")


def note_events(
    tool: str,
    arguments: dict[str, object] | None = None,
    result: object = None,
    error: BaseException | None = None,
) -> None:
    """Append structured events when the stream is on. Never raises into the door."""
    from essay_writer.debug_log import DEBUG_WIPE_TOOL

    if tool == DEBUG_WIPE_TOOL:
        return
    if not events_enabled():
        return
    try:
        args = arguments if isinstance(arguments, dict) else {}
        lines = [
            json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            for event in _events(tool, args, result, error)
        ]
        if not lines:
            return
        body = _body(result)
        essay_id = _essay_id(args, body)
        path = ml_events_path(essay_id)
        if essay_id:
            _prepare_sequence_land_header(path, essay_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except Exception:
        return
