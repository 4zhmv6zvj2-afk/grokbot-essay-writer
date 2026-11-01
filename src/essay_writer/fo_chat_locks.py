"""Front-office chat locks: inherited stage saves, revise vs keep, delete scope.

Roll-forward children re-run stages 1–3. A parent save on those stages is
named before the chat asks revise or keep. Confirm appears only on revise or
an explicit re-lock. Delete drafts need a where choice when Mac copies may exist.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from essay_writer.confirm import refuse
from essay_writer.paths import sequence_numbers, work_dir
from essay_writer.projects import (
    WHERE_CHOICES,
    WHERE_GROKBOT,
    WHERE_LABELS,
)
from essay_writer.stage_llm import stage_title
from essay_writer.student_voice import say

INHERITED_STAGES = frozenset({"2", "3"})
_FINAL_LOOK = re.compile(r"(?ms)^##\s+Final look\s*\n+(.*)\Z")
_LOCK_CHOICES = frozenset({"keep", "revise", "relock"})

FO_STAGES_ROLL_FORWARD = (
    "When a copied sequence opens on stage 1, stages 1–3 run again. "
    "If the parent already saved stage 2 or 3, name the prior lock: stage number, "
    "stage title, and the parent sequence id. Ask whether to revise it or keep it. "
    "Show the Confirm card only when they revise or explicitly re-lock. "
    "Keep continues with the saved lock and does not show Confirm again for that same save."
)

FO_DELETE_SCOPE = (
    "Before essay.project.delete draft, ask whether to remove the cloud workspace only, "
    "Mac-local copies only, or both. Pass that choice as where grokbot, local, or both. "
    "Do not draft delete with where grokbot when Word or zip copies on the Mac may still exist."
)


def _read_pointer(folder: Path) -> dict[str, Any] | None:
    path = folder / "tracking" / "stage.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def extract_final_look(note_text: str) -> str:
    """Body under ## Final look in a tracking note."""
    match = _FINAL_LOOK.search(note_text.strip())
    if match is None:
        return ""
    return match.group(1).strip()


def _load_roll_record(folder: Path) -> dict[str, Any]:
    from essay_writer.roll_forward import RECORD

    path = folder / RECORD
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_roll_record(folder: Path, record: dict[str, Any]) -> None:
    from essay_writer.roll_forward import _write_record

    _write_record(folder, record)


def snapshot_inherited_locks(folder: Path, parent_essay_id: str) -> None:
    """Remember parent saves on stages 1–3 before the child pointer is reset."""
    pointer = _read_pointer(folder)
    if pointer is None:
        return
    saved = [item for item in pointer.get("saved") or [] if item in INHERITED_STAGES]
    if not saved:
        return
    locks: list[dict[str, Any]] = []
    for stage in saved:
        note = folder / "tracking" / f"{stage}.md"
        if not note.is_file():
            continue
        look = extract_final_look(note.read_text(encoding="utf-8"))
        if not look:
            continue
        locks.append(
            {
                "stage": stage,
                "title": stage_title(stage),
                "essay_id": parent_essay_id,
                "look": look,
            }
        )
    if not locks:
        return
    record = _load_roll_record(folder)
    record["inherited_locks"] = locks
    record["parent_essay_id"] = parent_essay_id
    record.setdefault("papers", [])
    record["essay_id"] = parent_essay_id
    _write_roll_record(folder, record)


def inherited_locks(essay_id: str) -> list[dict[str, Any]]:
    from essay_writer.roll_forward import load_record

    record = load_record(essay_id)
    if not isinstance(record, dict):
        return []
    shown: list[dict[str, Any]] = []
    for row in record.get("inherited_locks") or []:
        if not isinstance(row, dict):
            continue
        stage = row.get("stage")
        look = row.get("look")
        if stage not in INHERITED_STAGES or not isinstance(look, str) or not look.strip():
            continue
        shown.append(
            {
                "stage": stage,
                "title": row.get("title") if isinstance(row.get("title"), str) else stage_title(stage),
                "essay_id": row.get("essay_id") if isinstance(row.get("essay_id"), str) else "",
                "look": look.strip(),
                "resolved": row.get("resolved") is True,
            }
        )
    return shown


def inherited_lock_pending(essay_id: str, stage: str) -> dict[str, Any] | None:
    for row in inherited_locks(essay_id):
        if row["stage"] == stage and row.get("resolved") is not True:
            return row
    return None


def _mark_lock_resolved(essay_id: str, stage: str) -> None:

    folder = work_dir(essay_id)
    record = _load_roll_record(folder)
    rows = record.get("inherited_locks")
    if not isinstance(rows, list):
        return
    for row in rows:
        if isinstance(row, dict) and row.get("stage") == stage:
            row["resolved"] = True
    _write_roll_record(folder, record)


def prior_saved_lock_line(row: dict[str, Any]) -> str:
    parent = row.get("essay_id") or "the parent sequence"
    return (
        f"Stage {row['stage']} — {row['title']} was already saved on {parent}."
    )


def prior_saved_lock_ask(essay_id: str, stage: str, row: dict[str, Any]) -> dict[str, Any]:
    """FO names the prior save and asks revise vs keep. No Confirm card."""
    lead = prior_saved_lock_line(row)
    body: dict[str, Any] = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "stage_title": row.get("title") or stage_title(stage),
        "confirmPhase": "draft",
        "prior_saved_lock": {
            "stage": row["stage"],
            "title": row["title"],
            "essay_id": row.get("essay_id"),
            "look": row["look"],
        },
        "inherited_lock_preview": row["look"],
        "lock_choices": ["revise", "keep", "relock"],
        "wrote": False,
        "stored": False,
        "advanced": False,
        "waiting_confirm": False,
        "next": say(
            f"{lead} Revise it, keep it and continue, or re-lock it with Confirm. "
            "Call essay.stage with lockChoice revise, keep, or relock. "
            "Confirm appears only on revise or relock."
        ),
    }
    body.pop("card", None)
    body.pop("cardAction", None)
    body.pop("cardDigest", None)
    return body


def lock_choice_refusal(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() not in _LOCK_CHOICES:
        return refuse(
            "lock-choice",
            "lockChoice must be revise, keep, or relock.",
        )
    return None


def seed_inherited_look(essay_id: str, stage: str, text: str) -> str:
    """Roll-forward look carries parent entry locks, not Basics alone."""
    row = inherited_lock_pending(essay_id, stage)
    if row is None:
        return text
    inherited = row["look"]
    if not text.strip():
        return inherited
    if inherited.casefold() in text.casefold():
        return text
    return f"{inherited}\n{text}".strip()


def module_mac_deliverables_may_exist(module: str) -> bool:
    """True when stored or default Mac handoff paths may exist for this module."""
    from essay_writer.first_run import mac_deliverables_record, sequence_mac_candidates
    from essay_writer.projects import sequence_id

    for number in sequence_numbers(module):
        essay_id = sequence_id(module, number)
        if mac_deliverables_record(essay_id).is_file():
            return True
        if sequence_mac_candidates(essay_id):
            return True
    return False


def delete_where_gate(
    module: str,
    where: object,
    *,
    sequence: str | None,
) -> str | dict[str, Any]:
    """Refuse a silent workspace-only delete when Mac copies may still exist."""
    if isinstance(where, str):
        text = where.strip()
        if text:
            return text  # caller still validates choices
    if sequence is not None:
        from essay_writer.projects import parse_sequence_id

        parsed = parse_sequence_id(sequence) if isinstance(sequence, str) else None
        if parsed is not None and parsed[0] == module:
            return WHERE_GROKBOT
    if module_mac_deliverables_may_exist(module):
        return refuse(
            "delete",
            "Ask whether to delete the cloud workspace only, Mac-local copies only, or both. "
            "Pass where grokbot, local, or both on essay.project.delete draft. Nothing was removed.",
            needs_where_choice=True,
            where_choices=sorted(WHERE_CHOICES),
            where_labels=WHERE_LABELS,
            guessed=False,
        )
    return WHERE_GROKBOT
