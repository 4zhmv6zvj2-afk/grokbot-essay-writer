"""Per-essay Confirm state. One file, one essay id, no cross-read."""

from __future__ import annotations

import json
import os
from typing import Any

from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import module_code, sequence_number, work_dir, write_last_saved


def empty_state(essay_id: str) -> dict[str, Any]:
    return {
        "essay_id": essay_id,
        "research": {"summary": None, "full": None},
        "validations": {},
        "word": {},
        "revisions": [],
        "shelf": {},
    }


def state_path(essay_id: str):
    return work_dir(essay_id) / "state.json"


def load_state(essay_id: str) -> dict[str, Any]:
    path = state_path(essay_id)
    base = empty_state(essay_id)
    if not path.is_file():
        return base
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in base:
            if key in data:
                base[key] = data[key]
        for key, value in data.items():
            if key not in base:
                base[key] = value
    base["essay_id"] = essay_id
    return base


def save_state(essay_id: str, state: dict[str, Any]) -> None:

    path = state_path(essay_id)
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
    number = sequence_number(essay_id)
    if number is not None:
        write_last_saved(module_code(essay_id), number)
