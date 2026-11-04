"""Module lists, archive, and sequence clones.

Continue shows the last saved sequence id. Archive, unarchive, and delete
list the module code only. Uploads, the brief, and KB1 paper notes stay on
the module. Everything else is copied onto a new sequence and then updated.
The writing pointer is not kept on that copy, whether the parent is open
or closed. The child starts open on stage 1 with no saved stages, so
stages 1–3 run again. Research and papers stay. The previous final is
parked under reference/.

Delete then asks where. grokbot clears this essay workspace. local clears
named Word and zip copies on the student's computer. both clears both.
Omitting where stays workspace-only. Local files are not searched for.
A sequence id removes only that sequence. The brief, uploads, and the
other sequences stay. where both reuses Mac copies already stored for
that sequence, or across the sequences when the whole module is removed,
and asks for a path only when those files are not there.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from essay_writer.canon import digest, file_sha256
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import (
    ESSAY_ID,
    essay_dir,
    essay_id_error,
    kb1_module_dir,
    kb1_root,
    kb1_sequence_dir,
    last_saved_path,
    read_last_saved,
    sequence_dir,
    sequence_numbers,
    uploads_dir,
    uploads_root,
    workspace_root,
    write_last_saved,
)
from essay_writer.state import empty_state
from essay_writer.student_voice import say, speak

SEQUENCE_NEW = "essay.sequence.new"
ARCHIVE = "essay.project.archive"
UNARCHIVE = "essay.project.unarchive"
DELETE = "essay.project.delete"
WHERE_GROKBOT = "grokbot"
WHERE_LOCAL = "local"
WHERE_BOTH = "both"
WHERE_CHOICES = frozenset({WHERE_GROKBOT, WHERE_LOCAL, WHERE_BOTH})
WHERE_LABELS = {
    WHERE_GROKBOT: "Essay workspace only",
    WHERE_LOCAL: "Copies on your computer only",
    WHERE_BOTH: "Essay workspace and copies on your computer",
}
LOCAL_SUFFIXES = frozenset({".docx", ".zip"})
LOCAL_REMOVAL_SENTENCE = "files on your computer will be removed"
DELETE_RESIDUAL_ID = "local-path-discovery"
DELETE_RESIDUAL = (
    "essay.project.delete does not search the Mac or Documents. "
    "A sequence delete with where both reuses Word and zip paths already stored for that sequence, "
    "and the default Mac handoff names for that sequence, when this computer can already see those files. "
    "If those files are not there, the front office asks for the full path. "
    "A module delete with where both gathers those saved and default paths across the sequences in the module, "
    "and asks for a path only when none of them are there. "
    "A path the caller names is the list. "
    "A file is removed only when this computer can already see that regular .docx or .zip. "
    "When the server runs on this computer and the Mac folder is not mounted, those copies stay until a path this computer can see is named. "
    "ESSAY_WRITER_MAC_DIR is not scanned."
)
LEAVE_BEHIND_NOTICE = say(
    "Word and zip copies on your computer stay unless you name each full path "
    "this computer can already see and choose copies on your computer only or both. "
    "If the Mac folder is not mounted here, those copies stay until you name a path this computer can open."
)


def sequence_id(module: str, number: int) -> str:
    return f"{module}-{number}"


def module_sequence_label(
    module: str,
    number: int | None = None,
    *,
    sequence: str | None = None,
) -> str:
    """User-visible module + sequence id. Bare module only when no sequence exists yet."""
    if isinstance(sequence, str) and sequence.strip():
        return sequence.strip()
    if number is not None:
        return sequence_id(module, number)
    return module


def parse_sequence_id(value: object) -> tuple[str, int] | None:
    if not isinstance(value, str) or "-" not in value:
        return None
    module, _, raw = value.rpartition("-")
    if essay_id_error(module) or not raw.isdigit() or int(raw) < 1:
        return None
    return module, int(raw)


def strip_duplicate_card_ids(row: dict[str, Any]) -> dict[str, Any]:
    """Student-facing rows: one card id, not bare module plus the same sequence twice."""
    essay_id = row.get("essay_id")
    if isinstance(essay_id, str):
        if row.get("module") == essay_id or parse_sequence_id(essay_id):
            row.pop("module", None)
    sequence = row.get("sequence_id")
    if isinstance(sequence, str) and sequence == essay_id:
        row.pop("sequence_id", None)
    return row


def latest_number(module: str) -> int | None:
    numbers = sequence_numbers(module)
    if not numbers:
        return None
    return numbers[-1]


def archived_path(module: str) -> Path:
    return essay_dir(module) / "archived.json"


def is_archived(module: str) -> bool:
    return archived_path(module).is_file()


def modules_on_disk() -> list[str]:
    found: set[str] = set()
    for folder in (workspace_root() / "Essay-writer", uploads_root(), kb1_root()):
        if not folder.is_dir():
            continue
        for child in folder.iterdir():
            if child.is_dir() and ESSAY_ID.fullmatch(child.name):
                found.add(child.name)
    return sorted(found)


def stage_name(state: dict[str, Any]) -> str:
    if state.get("shelf"):
        return "shelved"
    if state.get("revisions"):
        return "revised"
    if state.get("user_feedback"):
        return "user-feedback"
    if state.get("word"):
        return "word"
    validations = state.get("validations") or {}
    if any(isinstance(item, dict) and item.get("ok") for item in validations.values()):
        return "validated"
    research = state.get("research") or {}
    if research.get("summary") or research.get("full"):
        return "research"
    return "open"


def empty_sequence_state(module: str, number: int, *, parent: str | None, reason: str) -> dict[str, Any]:
    state = empty_state(sequence_id(module, number))
    state["sequence"] = number
    state["sequence_id"] = sequence_id(module, number)
    state["branched_from"] = parent
    state["branch_reason"] = reason
    state["reference_index"] = []
    state["unresolved_references"] = []
    return state


def load_sequence_state(module: str, number: int) -> dict[str, Any]:
    path = sequence_dir(module, number) / "state.json"
    base = empty_sequence_state(module, number, parent=None, reason="new")
    if not path.is_file():
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        base["unreadable"] = True
        return base
    if isinstance(data, dict):
        base.update(data)
    base["essay_id"] = sequence_id(module, number)
    base["sequence"] = number
    base["sequence_id"] = sequence_id(module, number)
    return base


def save_sequence_state(module: str, number: int, state: dict[str, Any]) -> None:
    path = sequence_dir(module, number) / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_last_saved(module, number)


def _module_error(module: object) -> str | None:
    if not isinstance(module, str):
        return "Name the module code, such as MOD1011AA."
    return essay_id_error(module)


def _roll_forward_fields(module: str, numbers: list[int]) -> dict[str, Any]:
    if not numbers:
        return {}
    child = max(numbers) + 1
    child_id = sequence_id(module, child)
    sequences = [sequence_id(module, number) for number in numbers]
    return {
        "roll_forward_ask": True,
        "sequence_pick": False,
        "sequences": sequences,
        "next_sequence_id": child_id,
        "roll_forward_next": say(
            f"You can keep working on the last-saved sequence, or start the next one. "
            f"To start the next one, pick which {module} sequence to copy. "
            f"The next id will be {child_id}."
        ),
    }


def _continue_row(module: str) -> dict[str, Any]:
    """One continue line. Say this to the user."""
    numbers = sequence_numbers(module)
    sequential = numbers[-1] if numbers else None
    saved = read_last_saved(module)
    if saved is None and sequential is None:
        return strip_duplicate_card_ids(
            {
                "essay_id": module,
                "next": say(f"I can't find a sequence for {module}. Start a new one?"),
            }
        )
    if saved is None:
        assert sequential is not None
        sequential_id = sequence_id(module, sequential)
        continue_row = {
            "module": module,
            "essay_id": sequential_id,
            "last_sequential_id": sequential_id,
            "last_sequential": sequential,
            "next": say(
                f"I don't have a last-saved sequence for {module}. "
                f"The last sequential id is {sequential_id}. "
                "Name the sequence, or start a new one?"
            ),
        }
        continue_row.update(_roll_forward_fields(module, numbers))
        return strip_duplicate_card_ids(continue_row)
    saved_id = sequence_id(module, saved)
    state = load_sequence_state(module, saved)
    row: dict[str, Any] = {
        "module": module,
        "essay_id": saved_id,
        "sequence_id": saved_id,
        "sequence": saved,
    }
    if state.get("unreadable"):
        row["state"] = "unreadable"
        row["next"] = say(
            f"I can't read the saved state for {saved_id}, "
            "so I won't treat it as ready to continue."
        )
    else:
        row["stage"] = stage_name(state)
    if sequential is not None and sequential != saved:
        row["last_sequential_id"] = sequence_id(module, sequential)
        row["last_sequential"] = sequential
    row.update(_roll_forward_fields(module, numbers))
    return strip_duplicate_card_ids(row)


def _roll_forward_view(module: str) -> dict[str, Any]:
    error = _module_error(module)
    if error:
        return refuse("essay-id", error)
    if is_archived(module):
        return refuse("projects", f"{module} is archived. Unarchive it before roll-forward.")
    numbers = sequence_numbers(module)
    if not numbers:
        return refuse(
            "projects",
            f"I can't find a sequence for {module}. Start a new one in this chat?",
        )
    child_id = sequence_id(module, max(numbers) + 1)
    sequences = [sequence_id(module, number) for number in numbers]
    return strip_duplicate_card_ids(
        {
            "ok": True,
            "view": "roll-forward",
            "module": module,
            "essay_id": module_sequence_label(module, numbers[-1]),
            "sequence_pick": True,
            "sequences": sequences,
            "next_sequence_id": child_id,
            "next": say(
                f"Pick which {module} sequence to copy. "
                f"I will start {child_id} as the next id on that module."
            ),
        }
    )


def essay_projects(view: str, module: str | None = None) -> dict[str, Any]:
    """Lists for the opening choice. Continue uses sequence ids. The others use module codes."""
    if view == "roll-forward":
        if not isinstance(module, str) or not module.strip():
            return refuse("projects", "Name the module code for roll-forward.")
        return _roll_forward_view(module.strip())
    if view not in {"continue", "archive", "delete", "unarchive"}:
        return refuse(
            "projects",
            "view must be continue, roll-forward, archive, delete, or unarchive.",
        )
    if view == "continue":
        rows = [
            _continue_row(module)
            for module in modules_on_disk()
            if not is_archived(module)
        ]
        return {
            "ok": True,
            "view": view,
            "rows": rows,
            "next": say(
                "A new essay starts as a new sequence. "
                "Continue only a sequence this student names. "
                "Do not continue a leftover module they did not name, and do not delete it."
            ),
        }
    if view == "unarchive":
        modules = [module for module in modules_on_disk() if is_archived(module)]
    else:
        modules = [module for module in modules_on_disk() if not is_archived(module)]
    return {"ok": True, "view": view, "modules": modules}


def _owned_tree(path: Path, root: Path) -> Path | None:
    if not path.exists():
        return None
    resolved = path.resolve()
    base = root.resolve()
    if resolved == base or not resolved.is_relative_to(base):
        return None
    return resolved


def _remove_tree(path: Path, root: Path) -> None:
    target = _owned_tree(path, root)
    if target is not None:
        shutil.rmtree(target)


def tree_pin(root: Path) -> list[dict[str, str]]:
    """Relative path and sha256 for every file under root. Missing roots pin nothing."""
    if not root.is_dir():
        return []
    pins: list[dict[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative_parts = path.relative_to(root).parts
        if any(part.startswith(".") for part in relative_parts):
            continue
        pins.append({"path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)})
    return pins


def parent_tree_pin(module: str, parent_number: int | None) -> list[dict[str, str]]:
    """Files on the parent sequence, including its KB1 sequence notes."""
    if parent_number is None:
        return []
    pins: list[dict[str, str]] = []
    prefix = f"sequences/{parent_number}"
    for item in tree_pin(sequence_dir(module, parent_number)):
        pins.append({"path": f"{prefix}/{item['path']}", "sha256": item["sha256"]})
    kb1_prefix = f"KB1/sequences/{parent_number}"
    for item in tree_pin(kb1_sequence_dir(module, parent_number)):
        pins.append({"path": f"{kb1_prefix}/{item['path']}", "sha256": item["sha256"]})
    return pins


def _snapshot(module: str) -> dict[str, Any]:
    numbers = sequence_numbers(module)
    return {
        "module": module,
        "sequences": [sequence_id(module, number) for number in numbers],
        "uploads": uploads_dir(module).is_dir(),
        "brief": any((essay_dir(module) / name).is_file() for name in ("brief.md", "brief.txt", "brief.docx")),
        "kb1": kb1_module_dir(module).is_dir(),
    }


def _delete_pin(module: str) -> dict[str, Any]:
    """Sequence ids plus the real files under uploads, the brief, and KB1.

    Paper notes live in the KB1 module folder and under Essay-writer/<module>/kb1.
    Both are part of the drafted list. Confirm removes that list, not a note
    that appeared after the draft.
    """
    brief_root = essay_dir(module)
    brief_pins: list[dict[str, str]] = []
    for name in ("brief.md", "brief.txt", "brief.docx"):
        path = brief_root / name
        if path.is_file():
            brief_pins.append({"path": name, "sha256": file_sha256(path)})
    kb1 = tree_pin(kb1_module_dir(module))
    for item in tree_pin(brief_root / "kb1"):
        kb1.append({"path": f"kb1/{item['path']}", "sha256": item["sha256"]})
    return {
        "module": module,
        "sequences": [sequence_id(module, number) for number in sequence_numbers(module)],
        "uploads": tree_pin(uploads_dir(module)),
        "brief": brief_pins,
        "kb1": kb1,
    }


def essay_project_archive(module: str, confirmPhase: str | None = None) -> dict[str, Any]:
    error = _module_error(module)
    if error:
        return refuse("essay-id", error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(essay_dir(module))
    if blocked:
        return blocked
    if module not in modules_on_disk():
        return refuse("archive", f"{module} is not on disk.")
    if is_archived(module):
        return refuse("archive", f"{module} is already archived.")
    snapshot = _snapshot(module)
    payload = {"module": module, "action": "archive"}
    fingerprint = snapshot
    body: dict[str, Any] = {
        "ok": True,
        "module": module,
        "confirmPhase": confirmPhase,
        "sequences": snapshot["sequences"],
        "wrote": False,
        "stored": False,
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(module, ARCHIVE, payload, fingerprint)
        body["next"] = say("Archiving this module hides every sequence. Say yes to continue.")
        return body
    ready = confirm_ready(module, ARCHIVE, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    marker = {
        "module": module,
        "archived_at": now(),
        "sequences": snapshot["sequences"],
    }
    path = archived_path(module)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    body["wrote"] = True
    body["stored"] = True
    body["archived"] = True
    return body


def essay_project_unarchive(module: str, confirmPhase: str | None = None) -> dict[str, Any]:
    error = _module_error(module)
    if error:
        return refuse("essay-id", error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(essay_dir(module))
    if blocked:
        return blocked
    if not is_archived(module):
        return refuse("unarchive", f"{module} is not archived.")
    snapshot = _snapshot(module)
    payload = {"module": module, "action": "unarchive"}
    fingerprint = snapshot
    body = {
        "ok": True,
        "module": module,
        "confirmPhase": confirmPhase,
        "sequences": snapshot["sequences"],
        "wrote": False,
        "stored": False,
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(module, UNARCHIVE, payload, fingerprint)
        body["next"] = say("Unarchive returns this module to the continue list. Say yes to continue.")
        return body
    ready = confirm_ready(module, UNARCHIVE, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    archived_path(module).unlink()
    body["wrote"] = True
    body["stored"] = True
    body["archived"] = False
    return body


def _delete_where(where: object) -> str | dict[str, Any]:
    if where is None:
        return WHERE_GROKBOT
    if isinstance(where, str):
        text = where.strip()
        if text == "":
            return WHERE_GROKBOT
        if text in WHERE_CHOICES:
            return text
    return refuse(
        "delete",
        "Choose where to delete: grokbot for this essay workspace only, "
        "local for Word and zip files on your computer only, or both. Nothing was removed.",
    )


def _coerce_local_paths(local_paths: object) -> tuple[list[str], dict[str, Any] | None]:
    if local_paths is None:
        return [], None
    if isinstance(local_paths, str):
        text = local_paths.strip()
        return ([text] if text else []), None
    if isinstance(local_paths, list):
        paths: list[str] = []
        for item in local_paths:
            if not isinstance(item, str) or not item.strip():
                return [], refuse(
                    "delete",
                    "Each path must be a Word file or a zip on your computer. Nothing was removed.",
                )
            paths.append(item.strip())
        return paths, None
    return [], refuse(
        "delete",
        "Name each Word file or zip on your computer as a path. Nothing was removed.",
    )


def _in_product_tree(path: Path) -> bool:
    resolved = path.resolve()
    for root in (workspace_root(), kb1_root()):
        base = root.resolve()
        if resolved == base or resolved.is_relative_to(base):
            return True
    return False


def _linked(path: Path) -> bool:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            return True
    return False


def _local_pin(raw: str) -> dict[str, Any]:
    """One regular Word file or zip this computer can already see, or a refusal."""
    if "\x00" in raw:
        return refuse("delete", "That path is not a file name. Nothing was removed.")
    expanded = Path(raw).expanduser()
    if not expanded.is_absolute():
        return refuse(
            "delete",
            "Name the full path of the Word file or zip, starting from the top of the computer. "
            "Nothing was removed.",
            path=raw,
        )
    if any(part.casefold() == "researchdrive" for part in expanded.parts):
        return refuse(
            "delete",
            "That path is not a named file on this computer. Nothing was removed.",
            path=str(expanded),
        )
    if _linked(expanded):
        return refuse(
            "delete",
            "That path is a link. Name the Word file or zip itself. Nothing was removed.",
            path=str(expanded),
        )
    if len(expanded.parts) < 3:
        return refuse(
            "delete",
            "Name the Word file or zip in its folder. Nothing was removed.",
            path=str(expanded),
        )
    if expanded.suffix.lower() not in LOCAL_SUFFIXES:
        return refuse(
            "delete",
            "That path is not a Word file or a zip. Name a .docx or a .zip on your computer. "
            "Nothing was removed.",
            path=str(expanded),
        )
    if _in_product_tree(expanded):
        return refuse(
            "delete",
            "That file is in this essay workspace. It is not a copy on your computer. Nothing was removed.",
            path=str(expanded),
        )
    if expanded.is_dir():
        return refuse(
            "delete",
            "This computer will not remove a folder. Name the Word file or zip. Nothing was removed.",
            path=str(expanded),
        )
    if not expanded.is_file():
        return refuse(
            "delete",
            "I can't see that file on this computer, so it was not removed. "
            "Name a Word file or zip this computer can already open. "
            "If that copy sits on a Mac folder that is not mounted here, it stays until this computer can see it.",
            path=str(expanded),
            leave_behind=True,
        )
    return {"path": str(expanded), "name": expanded.name, "sha256": file_sha256(expanded)}


def _local_pins(paths: list[str]) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    pins: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in paths:
        pin = _local_pin(raw)
        if pin.get("ok") is False:
            return [], pin
        path = str(pin["path"])
        if path in seen:
            continue
        seen.add(path)
        pins.append({"path": path, "name": str(pin["name"]), "sha256": str(pin["sha256"])})
    return pins, None


def _local_notice(pins: list[dict[str, str]]) -> str:
    lines = ["These files on your computer will be removed:"]
    lines.extend(item["path"] for item in pins)
    text = "\n".join(lines)
    if LOCAL_REMOVAL_SENTENCE not in text:
        return ""
    return text


def _recheck_local(pins: list[dict[str, str]]) -> dict[str, Any] | None:
    for pin in pins:
        fresh = _local_pin(pin["path"])
        if fresh.get("ok") is False or fresh.get("sha256") != pin["sha256"] or fresh.get("path") != pin["path"]:
            return refuse(
                "delete",
                "That file changed after the draft, or this computer can no longer see it. "
                "Nothing was removed. Show the list again in this chat.",
                path=pin["path"],
            )
    return None


def _local_draft_root(module: str) -> Path:
    """Drafts for a computer-only delete. This folder is not a module."""
    return workspace_root() / "Essay-writer" / ".delete-drafts" / module


def _clear_local_drafts(module: str) -> None:
    root = _local_draft_root(module)
    if root.exists():
        _remove_tree(root, root.parent)
    parent = root.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def _delete_targets(where: str, snapshot: dict[str, Any], pins: list[dict[str, str]]) -> list[str]:
    rows: list[str] = []
    if where in {WHERE_GROKBOT, WHERE_BOTH}:
        sequences = snapshot["sequences"]
        rows.append(
            "essay workspace sequences: " + (", ".join(sequences) if sequences else "none")
        )
        for item in snapshot["uploads"]:
            rows.append("essay workspace upload: " + item["path"])
        for item in snapshot["brief"]:
            rows.append("essay workspace brief: " + item["path"])
        for item in snapshot["kb1"]:
            rows.append("essay workspace paper note: " + item["path"])
    if where in {WHERE_LOCAL, WHERE_BOTH}:
        for item in pins:
            rows.append("your computer: " + item["path"])
    return rows


def _delete_next(where: str, pins: list[dict[str, str]]) -> str:
    if where == WHERE_LOCAL:
        prose = say(
            "This removes only the Word and zip files on your computer. "
            "This module stays. "
            "Open the Confirm card to remove this list, or choose Not yet to keep it. "
            "These files on your computer will be removed."
        )
    elif where == WHERE_BOTH:
        prose = say(
            "This removes this module from the chat, including its sequences, the brief, "
            "the uploads, and the paper notes, and the Word and zip files on your computer. "
            "Open the Confirm card to remove this list, or choose Not yet to keep it. "
            "These files on your computer will be removed."
        )
    else:
        prose = say(
            "This removes this module from the chat, including its sequences, the brief, "
            "the uploads, and the paper notes. Copies on your computer stay. "
            "Open the Confirm card to remove this list, or choose Not yet to keep it."
        )
    if not pins:
        return prose
    return prose + "\n" + "\n".join(item["path"] for item in pins)


def _sequence_delete_target(
    module: str,
    sequence: object,
    chosen: str,
) -> tuple[tuple[str, int] | None, dict[str, Any] | None]:
    """One sequence to remove, or a refusal. None means the whole module."""
    if sequence is None:
        return None, None
    if not isinstance(sequence, str) or not sequence.strip():
        return None, refuse("delete", "Name the sequence id, such as MOD1004AA-2. Nothing was removed.")
    parsed = parse_sequence_id(sequence.strip())
    named = sequence.strip()
    if parsed is None or parsed[0] != module:
        return None, refuse(
            "delete",
            "Name a sequence of this module, such as MOD1004AA-2. Nothing was removed.",
        )
    if chosen == WHERE_LOCAL:
        return None, refuse(
            "delete",
            "A sequence delete removes that sequence in this essay workspace. "
            "Choose the workspace, or both. Nothing was removed.",
            where=chosen,
        )
    if parsed[1] not in sequence_numbers(module):
        return None, refuse("delete", f"{named} is not on disk. Nothing was removed.")
    return parsed, None


def _known_mac_pins(essay_id: str) -> list[dict[str, str]]:
    """Saved and default Mac copies this computer can already see.

    A missing path is skipped. Documents and the Mac folder are not listed.
    """
    from essay_writer.first_run import sequence_mac_candidates

    pins: list[dict[str, str]] = []
    seen: set[Path] = set()
    for raw in sequence_mac_candidates(essay_id):
        pin = _local_pin(raw)
        if pin.get("ok") is False:
            continue
        path = str(pin["path"])
        try:
            resolved = Path(path).resolve()
        except OSError:
            resolved = Path(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        pins.append({"path": path, "name": str(pin["name"]), "sha256": str(pin["sha256"])})
    return pins


def _module_mac_pins(module: str) -> list[dict[str, str]]:
    """Saved and default Mac copies for every sequence in the module.

    A missing path is skipped. Documents and the Mac folder are not listed.
    The same file named by two sequences is kept once.
    """
    pins: list[dict[str, str]] = []
    seen: set[Path] = set()
    for number in sequence_numbers(module):
        for pin in _known_mac_pins(sequence_id(module, number)):
            path = str(pin["path"])
            try:
                resolved = Path(path).resolve()
            except OSError:
                resolved = Path(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            pins.append(pin)
    return pins


def essay_project_delete(
    module: str,
    confirmPhase: str | None = None,
    where: str | None = None,
    localPaths: list[str] | str | None = None,
    sequence: str | None = None,
    *,
    cardAction: str | None = None,
    cardDigest: str | None = None,
) -> dict[str, Any]:
    """Draft lists what will be removed. Confirm removes only that same list.

    where grokbot, or no where, clears this essay workspace and leaves copies
    on the student's computer. where local requires localPaths. where both
    reuses saved and default Mac copies when localPaths is omitted, for one
    sequence or across the sequences in the module, and asks for a path only
    when those files are not there. A path the caller names is the list.
    The draft returns a Confirm card. Confirm removes the list only when
    cardAction is confirm and cardDigest is that card. A typed yes does not.
    The computer list still has to say those files on the computer will be removed.
    sequence, such as MOD1004AA-2, removes only that sequence. The brief,
    uploads, and every other sequence stay.
    """
    error = _module_error(module)
    if error:
        return refuse("essay-id", error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase
    from essay_writer.fo_chat_locks import delete_where_gate

    gated = delete_where_gate(module, where, sequence=sequence)
    if isinstance(gated, dict):
        return gated
    chosen = _delete_where(gated)
    if isinstance(chosen, dict):
        return chosen
    paths, path_error = _coerce_local_paths(localPaths)
    if path_error:
        return path_error
    local_scope = chosen in {WHERE_LOCAL, WHERE_BOTH}
    workspace_scope = chosen in {WHERE_GROKBOT, WHERE_BOTH}
    if not local_scope and paths:
        return refuse(
            "delete",
            "A workspace-only delete does not remove files on your computer. "
            "Choose local or both to include those Word and zip files. Nothing was removed.",
        )
    one_sequence, sequence_error = _sequence_delete_target(module, sequence, chosen)
    if sequence_error:
        return sequence_error
    reused = False
    if chosen == WHERE_BOTH and not paths:
        if one_sequence is not None:
            known = _known_mac_pins(sequence_id(module, one_sequence[1]))
        else:
            known = _module_mac_pins(module)
        if known:
            paths = [item["path"] for item in known]
            reused = True
    if local_scope and not paths:
        if chosen == WHERE_BOTH and one_sequence is not None:
            return refuse(
                "delete",
                "The saved Word and zip copies for this sequence are not on this computer. "
                "Name the full path of each file. Nothing was removed.",
                where=chosen,
                needs_local_paths=True,
                computer_list=[],
                guessed=False,
                mac_paths_reused=False,
                scope="sequence",
                sequence=sequence_id(module, one_sequence[1]),
            )
        if chosen == WHERE_BOTH:
            return refuse(
                "delete",
                "The saved Word and zip copies for this module are not on this computer. "
                "Name the full path of each file. Nothing was removed.",
                where=chosen,
                needs_local_paths=True,
                computer_list=[],
                guessed=False,
                mac_paths_reused=False,
                scope="module",
            )
        return refuse(
            "delete",
            "Name each Word file or zip on your computer. "
            "Nothing is removed until those paths are listed and you say yes to that list.",
            where=chosen,
            needs_local_paths=True,
            computer_list=[],
            guessed=False,
        )
    pins: list[dict[str, str]] = []
    if local_scope:
        pins, pin_error = _local_pins(paths)
        if pin_error:
            return pin_error
        if not pins:
            return refuse(
                "delete",
                "Name each Word file or zip on your computer. "
                "Nothing is removed until those paths are listed and you say yes to that list.",
                where=chosen,
                needs_local_paths=True,
            )
    if workspace_scope and module not in modules_on_disk():
        if chosen == WHERE_BOTH:
            return refuse(
                "delete",
                f"{module} is not in this essay workspace. "
                "Choose local to remove only the Word and zip files on your computer. Nothing was removed.",
                where=chosen,
            )
        return refuse("delete", f"{module} is not on disk.")
    if one_sequence is not None:
        number = one_sequence[1]
        snapshot = {
            "module": module,
            "sequences": [sequence_id(module, number)],
            "uploads": [],
            "brief": [],
            "kb1": tree_pin(kb1_sequence_dir(module, number)),
        }
    elif workspace_scope:
        snapshot = _delete_pin(module)
    else:
        snapshot = {
            "module": module,
            "sequences": [],
            "uploads": [],
            "brief": [],
            "kb1": [],
        }
    payload: dict[str, Any] = {
        "module": module,
        "action": "delete-sequence" if one_sequence is not None else "delete",
        "where": chosen,
        "sequences": snapshot["sequences"],
        "local": [item["path"] for item in pins],
    }
    if one_sequence is not None:
        payload["sequence"] = snapshot["sequences"][0]
    fingerprint: dict[str, Any] = {"where": chosen}
    if workspace_scope:
        fingerprint["workspace"] = snapshot
    if local_scope:
        fingerprint["local"] = pins
    if one_sequence is not None:
        fingerprint["sequence"] = snapshot["sequences"][0]
    draft_root = _local_draft_root(module) if chosen == WHERE_LOCAL else None
    notice = _local_notice(pins) if local_scope else ""
    if local_scope and LOCAL_REMOVAL_SENTENCE not in notice:
        return refuse(
            "delete",
            "The confirm did not say the files on your computer will be removed. Nothing was removed.",
            where=chosen,
        )
    body: dict[str, Any] = {
        "ok": True,
        "module": module,
        "where": chosen,
        "where_label": WHERE_LABELS[chosen],
        "confirmPhase": confirmPhase,
        "sequences": snapshot["sequences"],
        "count": len(snapshot["sequences"]),
        "uploads": snapshot["uploads"],
        "brief": snapshot["brief"],
        "kb1": snapshot["kb1"],
        "local": pins,
        "targets": _delete_targets(chosen, snapshot, pins),
        "wrote": False,
        "stored": False,
        "deleted": False,
        "deleted_local": False,
    }
    if one_sequence is not None:
        from essay_writer.specialists.grok_bot import sequence_delete_speech

        body["scope"] = "sequence"
        body["sequence"] = snapshot["sequences"][0]
        body["next"] = sequence_delete_speech(body["sequence"], computer=chosen == WHERE_BOTH)
        if chosen == WHERE_BOTH and pins:
            body["next"] = body["next"] + "\n" + "\n".join(item["path"] for item in pins)
    elif local_scope:
        body["local_notice"] = notice
        body["local_discovery"] = (
            "This does not search your computer. "
            "Only the Word and zip files you named, which this computer can already see, can be removed."
        )
        body["next"] = _delete_next(chosen, pins)
    else:
        body["next"] = _delete_next(WHERE_GROKBOT, [])
    if local_scope:
        body["local_notice"] = notice
        body["local_discovery"] = (
            "This does not search your computer. "
            "Only the Word and zip files you named, which this computer can already see, can be removed."
        )
    if chosen == WHERE_BOTH:
        body["mac_paths_reused"] = reused
        if reused:
            whose = "this sequence" if one_sequence is not None else "the sequences in this module"
            body["local_discovery"] = (
                "This does not search your computer. "
                f"These Word and zip files are the copies already stored for {whose}. "
                "A file is removed only when this computer can already see it."
            )
    body["workspace_list"] = [
        row for row in body["targets"] if isinstance(row, str) and row.startswith("essay workspace")
    ]
    body["computer_list"] = [item["path"] for item in pins]
    body["guessed"] = False
    if not local_scope:
        body["leave_behind_notice"] = LEAVE_BEHIND_NOTICE
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(module, DELETE, payload, fingerprint, root=draft_root)
        from essay_writer.specialists.grok_bot import delete_confirm_card

        body["card"] = delete_confirm_card(
            module,
            body["digest"],
            body["next"],
            sequence=body.get("sequence") if isinstance(body.get("sequence"), str) else None,
        )
        return speak(body)
    ready = confirm_ready(module, DELETE, payload, fingerprint, root=draft_root)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    from essay_writer.specialists.grok_bot import accept_card_pick

    blocked_card = accept_card_pick(cardAction)
    if blocked_card:
        blocked_card["confirmPhase"] = CONFIRM
        blocked_card["deleted"] = False
        blocked_card["deleted_local"] = False
        return blocked_card
    if cardDigest != ready.get("digest"):
        return refuse(
            "confirm-card",
            "That card does not match this list. Show the list again in this chat.",
            deleted=False,
            deleted_local=False,
        )
    if local_scope:
        mismatch = _recheck_local(pins)
        if mismatch:
            if mismatch.get("confirmPhase") is None:
                mismatch["confirmPhase"] = CONFIRM
            return mismatch
        removed: list[str] = []
        try:
            for pin in pins:
                path = Path(pin["path"])
                if path.is_symlink() or not path.is_file() or file_sha256(path) != pin["sha256"]:
                    raise OSError(pin["path"])
                path.unlink()
                removed.append(pin["path"])
        except OSError:
            return refuse(
                "delete",
                "I could not remove every named file. The essay workspace was left in place.",
                where=chosen,
                confirmPhase=CONFIRM,
                removed_local=removed,
            )
        body["removed_local"] = removed
        body["deleted_local"] = True
    if one_sequence is not None and workspace_scope:
        number = one_sequence[1]
        prior = read_last_saved(module)
        _remove_tree(sequence_dir(module, number), essay_dir(module))
        _remove_tree(kb1_sequence_dir(module, number), kb1_module_dir(module))
        if prior == number:
            remaining = sequence_numbers(module)
            marker = last_saved_path(module)
            if remaining:
                write_last_saved(module, remaining[-1])
            elif marker.is_file():
                marker.unlink()
        body["deleted"] = True
        body["scope"] = "sequence"
    elif workspace_scope:
        _remove_tree(essay_dir(module), essay_dir(module).parent)
        _remove_tree(uploads_dir(module), uploads_root())
        _remove_tree(kb1_module_dir(module), kb1_root())
        body["deleted"] = True
    if chosen == WHERE_LOCAL:
        _clear_local_drafts(module)
    body["wrote"] = True
    body["stored"] = True
    return speak(body)


def _replace_token(text: str, old: str, new: str) -> str:
    """Replace old only when it is not the prefix of a longer number."""
    return re.sub(re.escape(old) + r"(?!\d)", new, text)


def _rewrite(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return _replace_token(value, old, new)
    if isinstance(value, list):
        return [_rewrite(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite(item, old, new) for key, item in value.items()}
    return value


_W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
_W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_CORE_FIELDS = (
    "title",
    "subject",
    "keywords",
    "category",
    "comments",
    "identifier",
    "content_status",
)


def _set_text(node: Any, text: str) -> None:
    node.text = text
    if text[:1].isspace() or text[-1:].isspace():
        node.set(_XML_SPACE, "preserve")


def _paragraph_text_nodes(paragraph: Any) -> list[Any]:
    """Text nodes of this paragraph, not text inside a nested paragraph (a text box)."""
    nodes: list[Any] = []
    for node in paragraph.iter(_W_T):
        ancestor = node.getparent()
        nested = False
        while ancestor is not None and ancestor is not paragraph:
            if ancestor.tag == _W_P:
                nested = True
                break
            ancestor = ancestor.getparent()
        if not nested:
            nodes.append(node)
    return nodes


def _rewrite_paragraph(paragraph: Any, old: str, new: str) -> bool:
    nodes = _paragraph_text_nodes(paragraph)
    if not nodes:
        return False
    joined = "".join(node.text or "" for node in nodes)
    updated = _replace_token(joined, old, new)
    if updated == joined:
        return False
    per_node = [_replace_token(node.text or "", old, new) for node in nodes]
    if "".join(per_node) == updated:
        changed = False
        for node, text in zip(nodes, per_node, strict=False):
            if (node.text or "") != text:
                _set_text(node, text)
                changed = True
        return changed
    # The id was split across runs. Keep the rewritten paragraph text.
    _set_text(nodes[0], updated)
    for node in nodes[1:]:
        _set_text(node, "")
    return True


def _rewrite_story(element: Any, old: str, new: str) -> bool:
    changed = False
    for paragraph in element.iter(_W_P):
        if _rewrite_paragraph(paragraph, old, new):
            changed = True
    return changed


def _rewrite_docx(path: Path, old: str, new: str) -> None:
    """Update a copied Word file so the sequence id is the child's, including the cover.

    Covers body paragraphs (including an id split across runs), tables, headers,
    footers, text boxes, and core properties. `-1` does not replace `-10`.
    """
    import zipfile

    from docx import Document

    try:
        document = Document(str(path))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile):
        return
    changed = _rewrite_story(document.element, old, new)
    for rel in document.part.rels.values():
        if rel.reltype.endswith("/header") or rel.reltype.endswith("/footer"):
            if _rewrite_story(rel.target_part.element, old, new):
                changed = True
    props = document.core_properties
    for name in _CORE_FIELDS:
        if not hasattr(props, name):
            continue
        current = getattr(props, name) or ""
        if not isinstance(current, str):
            continue
        updated = _replace_token(current, old, new)
        if updated != current:
            setattr(props, name, updated)
            changed = True
    if changed:
        document.save(str(path))


def _rewrite_tree(root: Path, old: str, new: str) -> None:
    if not root.is_dir():
        return
    text_suffixes = {".md", ".txt", ".csv", ".html", ".htm"}
    files = [path for path in root.rglob("*") if path.is_file()]
    for path in files:
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                text = _replace_token(path.read_text(encoding="utf-8"), old, new)
                path.write_text(text, encoding="utf-8")
            else:
                path.write_text(
                    json.dumps(_rewrite(data, old, new), indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        elif suffix in text_suffixes:
            text = path.read_text(encoding="utf-8")
            updated = _replace_token(text, old, new)
            if updated != text:
                path.write_text(updated, encoding="utf-8")
        elif suffix == ".docx":
            _rewrite_docx(path, old, new)
        renamed = _replace_token(path.name, old, new)
        if renamed != path.name:
            path.rename(path.with_name(renamed))


class SequenceCloneError(Exception):
    """The clone did not finish. No new sequence folder was kept."""


def _discard_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _write_cloned_state(folder: Path, module: str, child: int, old: str, new: str, reason: str) -> None:
    path = folder / "state.json"
    base = empty_sequence_state(module, child, parent=old, reason=reason)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            base.update(data)
    base["essay_id"] = new
    base["sequence"] = child
    base["sequence_id"] = new
    base["branched_from"] = old
    base["branch_reason"] = reason
    path.write_text(json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clone_sequence(module: str, parent: int, child: int, *, reason: str) -> None:
    """Copy a sequence, then publish it with one rename.

    A failure deletes the staging copy. The numbered folder is created only
    after the copy, the id rewrite, the state file, and pointer init are
    complete, so a partial clone cannot become the latest sequence.
    The parent copy takes the stage lock after any torn commit is finished,
    so the child does not publish a new note with an old pointer.
    The copied pointer is replaced before publish for an open parent and a
    closed parent. Stage notes are cleared with it. The child is stage 1.
    """
    source = sequence_dir(module, parent)
    target = sequence_dir(module, child)
    if target.exists():
        raise FileExistsError(sequence_id(module, child))
    staging = target.with_name(f".{child}.partial")
    kb1_source = kb1_sequence_dir(module, parent)
    kb1_target = kb1_sequence_dir(module, child)
    kb1_staging = kb1_target.with_name(f".{child}.partial")
    published = False
    kb1_published = False
    try:
        _discard_tree(staging)
        _discard_tree(kb1_staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        from essay_writer.stage_track import (
            init_cloned_sequence_pointer,
            rebind_cloned_confirms,
            stage_lock,
        )

        if source.is_dir():
            with stage_lock(sequence_id(module, parent)):
                shutil.copytree(source, staging)
        else:
            staging.mkdir(parents=True)
        old = sequence_id(module, parent)
        new = sequence_id(module, child)
        _rewrite_tree(staging, old, new)
        _rewrite_tree(staging, f"sequences/{parent}", f"sequences/{child}")
        copy_kb1 = kb1_source.is_dir() and not kb1_target.exists()
        if copy_kb1:
            kb1_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(kb1_source, kb1_staging)
            _rewrite_tree(kb1_staging, old, new)
        _write_cloned_state(staging, module, child, old, new, reason)
        from essay_writer.fo_chat_locks import snapshot_inherited_locks

        snapshot_inherited_locks(staging, old)
        init_cloned_sequence_pointer(staging)
        rebind_cloned_confirms(staging, new)
        from essay_writer.roll_forward import shape_cloned_child

        shape_cloned_child(staging, new)
        os.replace(staging, target)
        published = True
        if copy_kb1:
            os.replace(kb1_staging, kb1_target)
            kb1_published = True
        write_last_saved(module, child)
    except FileExistsError:
        _discard_tree(staging)
        _discard_tree(kb1_staging)
        if published:
            _discard_tree(target)
        if kb1_published:
            _discard_tree(kb1_target)
        raise
    except Exception as exc:
        _discard_tree(staging)
        _discard_tree(kb1_staging)
        if published:
            _discard_tree(target)
        if kb1_published:
            _discard_tree(kb1_target)
        raise SequenceCloneError(sequence_id(module, child)) from exc


def essay_sequence_new(
    module: str,
    confirmPhase: str | None = None,
    parent: str | None = None,
) -> dict[str, Any]:
    error = _module_error(module)
    if error:
        return refuse("essay-id", error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(essay_dir(module))
    if blocked:
        return blocked
    if is_archived(module):
        return refuse("sequence", f"{module} is archived. Unarchive it before a new sequence.")
    numbers = sequence_numbers(module)
    if parent is None:
        parent_number = read_last_saved(module)
        if numbers and parent_number is None:
            return refuse(
                "sequence",
                f"I don't know which sequence of {module} was saved last. "
                "Name the parent sequence id. I won't guess from the highest folder number.",
            )
        parent_id = sequence_id(module, parent_number) if parent_number else None
    else:
        parsed = parse_sequence_id(parent)
        if parsed is None or parsed[0] != module:
            return refuse("sequence", "parent must be a sequence id of this module, such as MOD1011AA-5.")
        parent_number = parsed[1]
        parent_id = sequence_id(module, parent_number)
        if parent_number not in numbers:
            return refuse("sequence", f"{parent_id} is not on disk.")
    child = 1 if not numbers else max(numbers) + 1
    child_id = sequence_id(module, child)
    payload = {"module": module, "parent": parent_id, "sequence_id": child_id, "action": "new-sequence"}
    fingerprint = {
        "parent": parent_id,
        "sequences": [sequence_id(module, n) for n in sequence_numbers(module)],
        "parent_tree": parent_tree_pin(module, parent_number),
    }
    body: dict[str, Any] = {
        "ok": True,
        "module": module,
        "essay_id": child_id,
        "sequence_id": child_id,
        "parent": parent_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
    }
    if confirmPhase == DRAFT:
        essay_dir(module).mkdir(parents=True, exist_ok=True)
        body["digest"] = save_draft(module, SEQUENCE_NEW, payload, fingerprint)
        if parent_id is None:
            body["next"] = say(
                f"This starts {child_id}. Say yes and I will create it. Nothing is written until then."
            )
        else:
            body["next"] = say(
                f"This copies {parent_id} and starts {child_id}. "
                "Say yes and I will copy it. Nothing is written until then."
            )
        return body
    ready = confirm_ready(module, SEQUENCE_NEW, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    if parent_number is None:
        save_sequence_state(module, child, empty_sequence_state(module, child, parent=None, reason="new"))
    else:
        try:
            clone_sequence(module, parent_number, child, reason="new-sequence")
        except FileExistsError:
            return refuse("sequence", f"{child_id} already exists. Draft again.")
        except SequenceCloneError:
            return refuse(
                "sequence",
                "I couldn't finish the new sequence, so I didn't keep a partial copy. "
                "Say if you want me to try again.",
            )
    body["wrote"] = True
    body["stored"] = True
    body["digest"] = digest(payload)
    from essay_writer.stage_track import door_card_reply

    opened = door_card_reply(child_id)
    card = opened.get("card") if isinstance(opened, dict) else None
    if isinstance(opened, dict) and isinstance(card, dict) and card.get("essay_id") == child_id:
        body["card"] = card
        if opened.get("cardAction"):
            body["cardAction"] = opened["cardAction"]
        if opened.get("cardDigest"):
            body["cardDigest"] = opened["cardDigest"]
        nxt = opened.get("next")
        if isinstance(nxt, str) and nxt.strip():
            body["next"] = nxt
    return body
