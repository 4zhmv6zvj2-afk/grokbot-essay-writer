from __future__ import annotations

import hashlib
import re

from essay_writer.debug_log import (
    DEBUG_WIPE_TOOL,
    _cover_audit_fields,
    _secret_values,
    debug_enabled,
    scrub,
)
from essay_writer.operator_event import OperatorEvent, emit
from essay_writer.paths import ESSAY_ID, SEQUENCE_ID, work_dir

_STAGE_IDS = frozenset({"1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9", "10", "eqr"})
_PHASES = frozenset({"draft", "confirm", "read"})
_SHELLS = frozenset({"Cursor", "Build"})
_SHELL_EVENTS = frozenset({"start", "done", "exit"})
_TOKEN = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")
_SHORT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_HANDOFF_REASONS = frozenset({"unmounted", "missing file", "not copied", "no return"})


def events_enabled() -> bool:
    """Same split as debug.log. Students off. Cloud where alone stays off."""
    return debug_enabled()


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
        return str(raw)
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


def _sequence_sha(essay_id: str) -> str | None:
    path = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    if not path.is_file():
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _digest(arguments: dict[str, object], body: dict[str, object] | None) -> str | None:
    values: list[object] = [arguments.get("cardDigest")]
    if isinstance(body, dict):
        values.append(body.get("cardDigest"))
        values.append(body.get("digest"))
        card = body.get("card")
        if isinstance(card, dict):
            values.append(card.get("digest"))
            values.append(card.get("cardDigest"))
    for value in values:
        if isinstance(value, str) and _SHA.fullmatch(value):
            return value
    return None


def _scrubbed(value: object, secrets: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = scrub(value, secrets)
    return cleaned or None


def _door_event(
    tool: str,
    arguments: dict[str, object],
    result: object,
    error: BaseException | None,
) -> OperatorEvent:
    body = _body(result)
    name = _tool(tool)
    phase = _phase(arguments, body)
    essay_id = _id(arguments.get("essay_id"))
    if essay_id is None and isinstance(body, dict):
        essay_id = _id(body.get("essay_id"))
    secrets = _secret_values(dict(arguments))
    event: OperatorEvent = {"t": "", "tool": name, "phase": phase}
    if essay_id:
        event["essay_id"] = essay_id
    module = _id(arguments.get("module"))
    if module and module != essay_id:
        event["module"] = module
    parent = _id(arguments.get("parent"))
    if parent:
        event["parent"] = parent
    stage = _stage_id(arguments.get("stage"))
    if stage is None and isinstance(body, dict):
        stage = _stage_id(body.get("stage"))
    if stage:
        event["stage"] = stage
    if error is not None:
        event["ok"] = False
        kind = type(error).__name__
        if _SHORT.fullmatch(kind):
            event["error"] = kind
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
        saved = body.get("saved_pack_state")
        if isinstance(saved, str) and saved.strip() and "/" not in saved and "\\" not in saved:
            event["saved_pack"] = saved.strip()
        if body.get("chain_armed") is True:
            event["chain_armed"] = True
        references = body.get("references")
        if isinstance(references, list):
            event["refs_n"] = len(references)
        sources = body.get("sources")
        if isinstance(sources, list):
            event["sources_n"] = len(sources)
        cover = body.get("cover")
        if isinstance(cover, list) and essay_id:
            cover_fields = _cover_audit_fields(essay_id, cover)
            event["cover_n"] = cover_fields["cover_n"]
            event["cover_sequence_id"] = cover_fields["cover_sequence_id"]
            event["cover_title_line"] = cover_fields["cover_title_line"]
            event["cover_counted_words"] = cover_fields["cover_counted_words"]
        title = _scrubbed(body.get("title"), secrets)
        if title:
            event["title"] = title
        reason = _scrubbed(body.get("reason"), secrets)
        if reason is None:
            reason = _scrubbed(body.get("mid_exit_reason"), secrets)
        if reason:
            event["reason"] = reason
    query = _scrubbed(arguments.get("query"), secrets)
    if query:
        event["query"] = query
    if name == "essay.gates" and event.get("ok") is False:
        gate = _failed_gate(body)
        if gate:
            event["gate"] = gate
        if "refused" not in event:
            event["refused"] = gate or "gates"
    action = arguments.get("cardAction")
    if phase == "confirm" or action == "confirm":
        event["card_present"] = isinstance(body, dict) and isinstance(body.get("card"), dict)
    found = _digest(arguments, body)
    if found:
        event["digest"] = found
    if (
        name == "essay.stage"
        and stage == "10"
        and phase == "confirm"
        and essay_id
        and "sha256" not in event
    ):
        digest = _sequence_sha(essay_id)
        if digest:
            event["sha256"] = digest
    if isinstance(body, dict):
        shell_event = body.get("mid_office")
        shell = body.get("mid_shell")
        if (
            isinstance(shell, str)
            and isinstance(shell_event, str)
            and shell in _SHELLS
            and shell_event in _SHELL_EVENTS
        ):
            event["shell"] = shell
            event["shell_event"] = shell_event
            if shell_event in {"done", "exit"}:
                code = body.get("mid_exit_code")
                if isinstance(code, int) and not isinstance(code, bool):
                    event["exit_code"] = code
                stderr = _scrubbed(body.get("mid_stderr"), secrets)
                if stderr:
                    event["stderr"] = stderr
    return event


def note_events(
    tool: str,
    arguments: dict[str, object] | None = None,
    result: object = None,
    error: BaseException | None = None,
) -> None:
    """Append one record when the stream is on. Never raises into the door."""
    if tool == DEBUG_WIPE_TOOL:
        return
    if not events_enabled():
        return
    try:
        args = arguments if isinstance(arguments, dict) else {}
        emit(_door_event(tool, args, result, error))
    except Exception:
        return


def note_stage10_sha(essay_id: str) -> None:
    found = _id(essay_id.strip() if isinstance(essay_id, str) else "")
    if not found:
        return
    try:
        digest = _sequence_sha(found)
        if not digest:
            return
        emit(
            {
                "t": "",
                "tool": "essay.stage",
                "essay_id": found,
                "stage": "10",
                "sha256": digest,
            }
        )
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


def note_cli_handoff(flag: str, essay_id: str | None, outcome: str, reason: str = "") -> None:
    if outcome not in {"copy_only", "rebuilt", "refused"}:
        return
    if not isinstance(flag, str) or not flag.startswith("--") or len(flag) > 40:
        return
    try:
        event: OperatorEvent = {"t": "", "tool": "essay-writer", "flag": flag, "handoff": outcome}
        if outcome == "refused" and isinstance(reason, str) and reason.strip():
            short = _map_refuse_reason(reason)
            if short in _HANDOFF_REASONS:
                event["reason"] = short
        found = _id(essay_id) if isinstance(essay_id, str) else None
        if found:
            event["essay_id"] = found
        emit(event)
    except Exception:
        return
