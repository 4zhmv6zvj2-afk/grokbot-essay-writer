"""Stage-pack snapshots. One writer for Cursor and Grok Build.

A successful stage save and a successful pack validate each write
``Essay-writer/<module>/backups/<essay_id>/<snapshot_id>/``. The snapshot
holds pack.json, plus the annotation report and review markdown when those
files or notes are already on the sequence. ``essay.pack.restore`` puts one
snapshot back. A missing or damaged snapshot is refused. No review text is
created from nothing.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    load_draft_by_digest,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door, refuse_repo_write
from essay_writer.paths import essay_dir, sequence_write_error, work_dir
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import speak

TOOL = "essay.pack.restore"
REASON_STAGE = "stage-save"
REASON_VALIDATE = "pack-validate"
_REASONS = frozenset({REASON_STAGE, REASON_VALIDATE})
_PAPER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_SNAPSHOT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_ANNOTATION_NAMES = frozenset({"annotation-report.json", "annotation-report.md"})


def backups_dir(essay_id: str) -> Path:
    """``backups/<essay_id>/`` under the module folder."""
    return essay_dir(essay_id) / "backups" / essay_id


def snapshot_after_stage_save(essay_id: str, stage: str, look: str | None = None) -> dict[str, Any]:
    """Write one snapshot after a stage save that stored."""
    text = look if isinstance(look, str) else ""
    pack = _pack_for_stage(essay_id, stage, text)
    return _write_snapshot(essay_id, reason=REASON_STAGE, stage=stage, pack=pack)


def snapshot_after_pack_validate(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Write one snapshot after a pack validate that stored."""
    body = _embed_reviews(essay_id, copy.deepcopy(pack))
    return _write_snapshot(essay_id, reason=REASON_VALIDATE, stage=None, pack=body)


def essay_pack_restore(
    essay_id: str,
    snapshot: str | None = None,
    confirmPhase: str | None = None,
) -> dict[str, Any]:
    """Restore one snapshot. Draft writes nothing. Confirm writes that snapshot only."""
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id), backups_dir(essay_id))
    if blocked:
        return blocked
    if snapshot is None or (isinstance(snapshot, str) and not snapshot.strip()):
        if confirmPhase == CONFIRM:
            return refuse(
                "snapshot-missing",
                "Name the snapshot to restore. Nothing was written.",
            )
        return speak(
            {
                "ok": True,
                "essay_id": essay_id,
                "confirmPhase": confirmPhase,
                "wrote": False,
                "stored": False,
                "snapshots": _snapshot_ids(essay_id),
                "next": "Name the snapshot to restore.",
            }
        )
    if not isinstance(snapshot, str):
        return refuse("snapshot-missing", "Name the snapshot to restore. Nothing was written.")
    loaded = _read_snapshot(essay_id, snapshot.strip())
    if loaded.get("ok") is False:
        return loaded
    payload = {"essay_id": essay_id, "snapshot": snapshot.strip()}
    fingerprint = loaded["fingerprint"]
    if confirmPhase == DRAFT:
        body = {
            "ok": True,
            "essay_id": essay_id,
            "confirmPhase": DRAFT,
            "wrote": False,
            "stored": False,
            "snapshot_id": loaded["snapshot_id"],
            "reason": loaded["manifest"].get("reason"),
            "reviews": [item["paper_id"] for item in loaded["reviews"]],
            "annotation_report": loaded["annotation"] is not None,
            "digest": save_draft(essay_id, TOOL, payload, fingerprint),
            "next": "Show this restore. Save it only after an explicit yes, with the same snapshot.",
        }
        return speak(body)
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["wrote"] = False
        ready["stored"] = False
        return speak(ready)
    again = _read_snapshot(essay_id, snapshot.strip())
    if again.get("ok") is False:
        return again
    _apply_snapshot(essay_id, again)
    reviews = [item["paper_id"] for item in again["reviews"]]
    if reviews:
        nxt = "That snapshot is back. The critical reviews from it are on this sequence again."
    else:
        nxt = "That snapshot is back on this sequence."
    return speak(
        {
            "ok": True,
            "essay_id": essay_id,
            "confirmPhase": CONFIRM,
            "wrote": True,
            "stored": True,
            "snapshot_id": again["snapshot_id"],
            "reviews": reviews,
            "annotation_report": again["annotation"] is not None,
            "pack_restored": True,
            "digest": ready.get("digest"),
            "next": nxt,
        }
    )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _pack_for_stage(essay_id: str, stage: str, look: str) -> dict[str, Any]:
    durable = _durable_pack(essay_id)
    if durable is None:
        pack: dict[str, Any] = {"essay_id": essay_id, "stage": stage, "look": look}
    else:
        pack = durable
    return _embed_reviews(essay_id, pack)


def _durable_pack(essay_id: str) -> dict[str, Any] | None:

    state = load_state(essay_id)
    saved = state.get("saved_pack")
    if isinstance(saved, dict):
        return copy.deepcopy(saved)
    validations = state.get("validations")
    if not isinstance(validations, dict) or not validations:
        return None
    best_digest = ""
    best_at = ""
    for key, item in validations.items():
        if not isinstance(item, dict):
            continue
        stamp = item.get("confirmed_at")
        stamp_text = stamp if isinstance(stamp, str) else ""
        digest = item.get("pack_digest")
        if not isinstance(digest, str) or not digest:
            digest = key if isinstance(key, str) else ""
        if not digest:
            continue
        if best_digest == "" or stamp_text >= best_at:
            best_at = stamp_text
            best_digest = digest
    if not best_digest:
        return None
    from essay_writer.validate import TOOL as VALIDATE_TOOL

    record = load_draft_by_digest(essay_id, VALIDATE_TOOL, best_digest)
    if not isinstance(record, dict):
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    pack = payload.get("pack")
    if isinstance(pack, dict):
        return copy.deepcopy(pack)
    return None


def _embed_reviews(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Copy review markdown already on disk into the pack when the pack has none."""
    if "critical_reviews" in pack:
        return pack
    from essay_writer.draft_from_review import stored_critical_reviews

    rows = stored_critical_reviews(essay_id)
    if not rows:
        return pack
    body = copy.deepcopy(pack)
    body["critical_reviews"] = rows
    return body


def _review_files(essay_id: str) -> list[tuple[str, bytes]]:
    folder = work_dir(essay_id) / "output" / "reviews"
    if not folder.is_dir():
        return []
    found: list[tuple[str, bytes]] = []
    for path in sorted(folder.glob("*.md")):
        if not path.is_file() or not _PAPER_ID.fullmatch(path.stem):
            continue
        try:
            data = path.read_bytes()
            data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not data.strip():
            continue
        found.append((f"reviews/{path.name}", data))
    return found


def _annotation_bytes(essay_id: str) -> tuple[str, bytes] | None:
    output = work_dir(essay_id) / "output"
    for name in ("annotation-report.json", "annotation-report.md"):
        path = output / name
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if data:
            return name, data

    research = load_state(essay_id).get("research")
    if not isinstance(research, dict):
        return None
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for depth in ("summary", "full"):
        record = research.get(depth)
        if not isinstance(record, dict):
            continue
        sources = record.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            paper_id = source.get("id")
            note = source.get("annotation")
            if not isinstance(paper_id, str) or not paper_id.strip():
                continue
            if not isinstance(note, str) or not note.strip():
                continue
            if paper_id in seen:
                continue
            seen.add(paper_id)
            rows.append({"id": paper_id, "annotation": note})
    if not rows:
        return None
    payload = {"essay_id": essay_id, "sources": rows}
    data = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return "annotation-report.json", data


def _unique_id(root: Path, reason: str, stage: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    label = reason if not stage else f"{reason}-{stage}"
    base = f"{stamp}-{label}"
    candidate = base
    number = 2
    while (root / candidate).exists() or (root / f".{candidate}.tmp").exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def _write_tree(dest: Path, files: dict[str, bytes]) -> None:

    refuse_repo_write(dest)
    temporary = dest.parent / f".{dest.name}.tmp"
    if temporary.exists():
        shutil.rmtree(temporary)
    try:
        for rel, data in files.items():
            path = temporary / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.rename(temporary, dest)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _write_snapshot(
    essay_id: str,
    *,
    reason: str,
    stage: str | None,
    pack: dict[str, Any],
) -> dict[str, Any]:
    root = backups_dir(essay_id)
    snapshot_id = _unique_id(root, reason, stage)
    reviews = _review_files(essay_id)
    annotation = _annotation_bytes(essay_id)
    created = _now()
    manifest: dict[str, Any] = {
        "essay_id": essay_id,
        "snapshot_id": snapshot_id,
        "reason": reason,
        "stage": stage,
        "created_at": created,
        "pack": "pack.json",
        "annotation_report": None if annotation is None else annotation[0],
        "reviews": [rel for rel, _data in reviews],
    }
    files: dict[str, bytes] = {
        "pack.json": (json.dumps(pack, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        "manifest.json": (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
    }
    for rel, data in reviews:
        files[rel] = data
    if annotation is not None:
        files[annotation[0]] = annotation[1]
    dest = root / snapshot_id
    _write_tree(dest, files)
    return {"ok": True, "snapshot_id": snapshot_id, "reason": reason}


def _snapshot_ids(essay_id: str) -> list[str]:
    root = backups_dir(essay_id)
    if not root.is_dir():
        return []
    names: list[str] = []
    for path in sorted(root.iterdir()):
        if path.is_dir() and _snapshot_child(root, path.name) is not None and (path / "pack.json").is_file():
            names.append(path.name)
    return names


def _snapshot_child(root: Path, snapshot_id: str) -> Path | None:
    if not isinstance(snapshot_id, str) or _SNAPSHOT_ID.fullmatch(snapshot_id) is None:
        return None
    if snapshot_id.endswith(".tmp"):
        return None
    try:
        base = root.resolve()
        path = (root / snapshot_id).resolve()
        path.relative_to(base)
    except (OSError, ValueError):
        return None
    if path.parent != base:
        return None
    return path


def _corrupt(reason: str) -> dict[str, Any]:
    return refuse("snapshot-corrupt", reason, wrote=False, stored=False)


def _missing(reason: str) -> dict[str, Any]:
    return refuse("snapshot-missing", reason, wrote=False, stored=False)


def _stored_file(path: Path) -> bool:
    """A regular file stored in the snapshot. A link is not the snapshot's bytes."""
    return path.is_file() and not path.is_symlink()


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not _stored_file(path):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _review_rel_ok(name: object) -> bool:
    if not isinstance(name, str) or "\\" in name or name.startswith("/") or ".." in name.split("/"):
        return False
    parts = name.split("/")
    if len(parts) != 2 or parts[0] != "reviews" or not parts[1].endswith(".md"):
        return False
    return _PAPER_ID.fullmatch(parts[1][:-3]) is not None


def _reviews_from_pack(pack: dict[str, Any]) -> list[dict[str, str]] | None:
    """Review rows copied from pack JSON. None means the list is damaged."""
    raw = pack.get("critical_reviews", None)
    if raw is None:
        return []
    if not isinstance(raw, list):
        return None
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            return None
        paper_id = item.get("paper_id")
        markdown = item.get("markdown")
        if not isinstance(paper_id, str) or _PAPER_ID.fullmatch(paper_id) is None:
            return None
        if paper_id in seen:
            return None
        if not isinstance(markdown, str) or not markdown.strip():
            return None
        seen.add(paper_id)
        rows.append({"paper_id": paper_id, "markdown": markdown})
    return rows


def _read_snapshot(essay_id: str, snapshot_id: str) -> dict[str, Any]:
    root = backups_dir(essay_id)
    path = _snapshot_child(root, snapshot_id)
    if path is None or not path.is_dir():
        return _missing("That snapshot is not on disk. Nothing was written.")
    manifest = _read_json_object(path / "manifest.json")
    if manifest is None:
        return _corrupt("That snapshot is damaged. Nothing was written.")
    if manifest.get("essay_id") != essay_id or manifest.get("snapshot_id") != snapshot_id:
        return _corrupt("That snapshot is damaged. Nothing was written.")
    if manifest.get("reason") not in _REASONS or manifest.get("pack") != "pack.json":
        return _corrupt("That snapshot is damaged. Nothing was written.")
    pack_path = path / "pack.json"
    pack = _read_json_object(pack_path)
    if pack is None:
        return _corrupt("That snapshot is damaged. Nothing was written.")
    try:
        pack_bytes = pack_path.read_bytes()
    except OSError:
        return _corrupt("That snapshot is damaged. Nothing was written.")
    listed = manifest.get("reviews")
    if not isinstance(listed, list) or not all(_review_rel_ok(item) for item in listed):
        return _corrupt("That snapshot is damaged. Nothing was written.")
    review_dir = path / "reviews"
    on_disk: list[str] = []
    if review_dir.exists():
        if review_dir.is_symlink() or not review_dir.is_dir():
            return _corrupt("That snapshot is damaged. Nothing was written.")
        for child in sorted(review_dir.iterdir()):
            rel = f"reviews/{child.name}"
            if child.is_symlink() or not child.is_file():
                return _corrupt("That snapshot is damaged. Nothing was written.")
            on_disk.append(rel)
    if sorted(listed) != on_disk:
        return _corrupt("That snapshot is damaged. Nothing was written.")
    reviews: list[dict[str, Any]] = []
    review_bytes: list[bytes] = []
    for rel in listed:
        file_path = path / rel
        if not _stored_file(file_path):
            return _corrupt("That snapshot is damaged. Nothing was written.")
        try:
            data = file_path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return _corrupt("That snapshot is damaged. Nothing was written.")
        if not text.strip():
            return _corrupt("That snapshot is damaged. Nothing was written.")
        reviews.append({"paper_id": Path(rel).stem, "markdown": text, "bytes": data})
        review_bytes.append(data)
    if not reviews:
        from_pack = _reviews_from_pack(pack)
        if from_pack is None:
            return _corrupt("That snapshot is damaged. Nothing was written.")
        for item in from_pack:
            data = item["markdown"].encode("utf-8")
            reviews.append({"paper_id": item["paper_id"], "markdown": item["markdown"], "bytes": data})
            review_bytes.append(data)
    ann_name = manifest.get("annotation_report")
    annotation: tuple[str, bytes] | None = None
    ann_bytes = b""
    if ann_name is not None:
        if not isinstance(ann_name, str) or ann_name not in _ANNOTATION_NAMES:
            return _corrupt("That snapshot is damaged. Nothing was written.")
        ann_path = path / ann_name
        if not _stored_file(ann_path):
            return _corrupt("That snapshot is damaged. Nothing was written.")
        try:
            ann_path.resolve().relative_to(path.resolve())
            ann_bytes = ann_path.read_bytes()
        except (OSError, ValueError):
            return _corrupt("That snapshot is damaged. Nothing was written.")
        if not ann_bytes or ann_path.parent.resolve() != path.resolve():
            return _corrupt("That snapshot is damaged. Nothing was written.")
        annotation = (ann_name, ann_bytes)
    fingerprint = {
        "snapshot_id": snapshot_id,
        "pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
        "reviews_sha256": hashlib.sha256(b"".join(review_bytes)).hexdigest(),
        "annotation_sha256": hashlib.sha256(ann_bytes).hexdigest(),
    }
    return {
        "ok": True,
        "snapshot_id": snapshot_id,
        "manifest": manifest,
        "pack": pack,
        "reviews": reviews,
        "annotation": annotation,
        "fingerprint": fingerprint,
    }


def _apply_snapshot(essay_id: str, loaded: dict[str, Any]) -> None:

    output = work_dir(essay_id) / "output"
    refuse_repo_write(output)
    annotation = loaded.get("annotation")
    if isinstance(annotation, tuple):
        name, data = annotation
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        _replace_bytes(dest, data)
    for item in loaded["reviews"]:
        dest = output / "reviews" / f"{item['paper_id']}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _replace_bytes(dest, item["bytes"])
    state = load_state(essay_id)
    state["saved_pack"] = loaded["pack"]
    save_state(essay_id, state)


def _replace_bytes(path: Path, data: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)
