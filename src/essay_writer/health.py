"""Read-only health. Alive, doors, and the packs on disk."""

from __future__ import annotations

import json
from typing import Any

from essay_writer import __version__, build_commit
from essay_writer.doors import DOORS
from essay_writer.originals import material_locators
from essay_writer.paths import (
    ESSAY_ID,
    essay_dir,
    local_pack_index,
    read_last_saved,
    uploads_dir,
    work_dir,
    workspace_root,
)
from essay_writer.programme import (
    MODULE_EXAMPLES,
    PROGRAMME,
    STYLE_ID,
    referencing_record,
)
from essay_writer.projects import (
    is_archived,
    load_sequence_state,
    module_sequence_label,
    sequence_id,
    sequence_numbers,
    stage_name,
    strip_duplicate_card_ids,
)
from essay_writer.specialists.researcher import consensus_status
from essay_writer.stage_track import load_pointer
from essay_writer.state import load_state


def _discover() -> list[str]:
    found: set[str] = set()
    root = workspace_root()
    for folder in (root / "Essay-writer", root / "uploads"):
        if not folder.is_dir():
            continue
        for child in folder.iterdir():
            if child.is_dir() and ESSAY_ID.fullmatch(child.name):
                found.add(child.name)
    return sorted(found)


def _pack(essay_id: str, state: dict[str, Any], sequence: str | None) -> dict[str, Any]:
    research = state.get("research") or {}
    label = module_sequence_label(essay_id, sequence=sequence)
    body: dict[str, Any] = {
        "essay_id": label,
        "stage": stage_name(state),
        "uploads": len(material_locators(essay_id)),
        "research_summary": bool(research.get("summary")),
        "research_full": bool(research.get("full")),
        "validated": sorted(
            key
            for key, item in (state.get("validations") or {}).items()
            if isinstance(item, dict) and item.get("ok")
        ),
        "word": sorted((state.get("word") or {}).keys()),
        "revisions": len(state.get("revisions") or []),
        "shelf": sorted((state.get("shelf") or {}).keys()),
        "brief": (essay_dir(essay_id) / "brief.md").is_file()
        or (essay_dir(essay_id) / "brief.txt").is_file()
        or (essay_dir(essay_id) / "brief.docx").is_file(),
        "upload_dir": uploads_dir(essay_id).is_dir(),
    }
    if sequence:
        body["sequence_id"] = sequence
        pointer_path = work_dir(sequence) / "tracking" / "stage.json"
        if pointer_path.is_file():
            pointer = load_pointer(sequence)
            body["writing_stage"] = pointer["current"]
            body["writing_saved"] = list(pointer["saved"])
            if body["stage"] == "open":
                body["stage"] = pointer["current"]
    return strip_duplicate_card_ids(body)


def _app_folder() -> str:
    """Folder later tools load. The word open is not a folder."""
    root = workspace_root()
    if root.name.casefold() == "open":
        return ""
    return str(root)


def essay_health() -> dict[str, Any]:
    packs: list[dict[str, Any]] = []
    for essay_id in _discover():
        if is_archived(essay_id):
            continue
        numbers = sequence_numbers(essay_id)
        sequential = numbers[-1] if numbers else None
        saved = read_last_saved(essay_id)
        if saved is None and sequential is not None:
            sequential_id = sequence_id(essay_id, sequential)
            packs.append(
                strip_duplicate_card_ids(
                    {
                        "essay_id": sequential_id,
                        "state": "no-last-saved",
                        "last_sequential_id": sequential_id,
                        "next": (
                            f"I don't have a last-saved sequence for {essay_id}. "
                            f"The last sequential id is {sequential_id}. "
                            "Name the sequence, or start a new one?"
                        ),
                    }
                )
            )
            continue
        sequence = sequence_id(essay_id, saved) if saved else None
        try:
            state = load_sequence_state(essay_id, saved) if saved else load_state(essay_id)
        except json.JSONDecodeError:
            packs.append({"essay_id": essay_id, "state": "unreadable"})
            continue
        if state.get("unreadable"):
            item: dict[str, Any] = {
                "essay_id": module_sequence_label(essay_id, sequence=sequence),
                "state": "unreadable",
            }
            if sequence:
                item["sequence_id"] = sequence
                item["next"] = (
                    f"I can't read the saved state for {sequence}, "
                    "so I won't treat it as ready to continue."
                )
            packs.append(strip_duplicate_card_ids(item))
            continue
        packs.append(_pack(essay_id, state, sequence))
    from essay_writer.debug_log import FERRY_ZIP_TIP, _known_land, ferry_tip_sha

    body: dict[str, Any] = {
        "ok": True,
        "alive": True,
        "name": "essay-writer",
        "app_path": _app_folder(),
        "version": __version__,
        "build_commit": build_commit(),
        "read_only": True,
        "confirm": "draft-then-confirm",
        "doors": [
            {
                "id": door["id"],
                "tool": door["tool"],
                "confirm": door["confirm"],
                "read_only": door["read_only"],
                "requires": door["requires"],
                "writes": door["writes"],
            }
            for door in DOORS
        ],
        "packs": packs,
        "local_packs": local_pack_index(),
        "essay_ids": [pack["essay_id"] for pack in packs if "essay_id" in pack],
        "module_examples": list(MODULE_EXAMPLES),
        "programme": PROGRAMME,
        "referencing": referencing_record(),
        "style": STYLE_ID,
        "word": "docx-only",
        "slack": "out",
        "resolvers": "free-only",
        "consensus": consensus_status(),
        "invent_forbid": True,
        "opening": ["new", "continue", "roll-forward", "archive", "unarchive", "delete"],
        "sequence": [
            "essay.health",
            "essay.originals",
            "essay.dig",
            "essay.download.leftovers",
            "essay.research.summary or essay.research.full",
            "essay.gates",
            "essay.pack.validate",
            "essay.pack.render_word",
            "essay.revise",
            "essay.shelf.put",
        ],
    }
    land = _known_land()
    if land:
        body["land"] = land
    body["ferry_tip"] = FERRY_ZIP_TIP
    body["ferry_tip_sha"] = ferry_tip_sha()
    return body
