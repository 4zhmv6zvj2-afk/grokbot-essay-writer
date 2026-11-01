"""Stage-pack backup and restore. Stable ids: AC1–AC6."""

from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

from helpers import ESSAY, TOPIC, open_sequence, pack, picked, source, write_upload

from essay_writer import build_office, cursor_office
from essay_writer.build_office import _STAGE_DELIVERABLES
from essay_writer.debug_log import essay_debug_wipe, wipe_operator_log_files
from essay_writer.doors import DOORS
from essay_writer.draft_from_review import stored_critical_reviews
from essay_writer.first_run import main as first_run_main
from essay_writer.pack_backup import (
    backups_dir,
    essay_pack_restore,
    snapshot_after_pack_validate,
    snapshot_after_stage_save,
)
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_summary
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office
from essay_writer.stage_track import (
    _commit_with_next_card,
    _snapshot_stage_save,
    _store_stage,
    essay_stage,
)
from essay_writer.state import load_state, save_state
from essay_writer.validate import essay_pack_validate

REVIEW_A = "Alpha critical note stays on the sequence.\n"
REVIEW_B = "Beta critical note stays on the sequence.\n"
ANNOTATION = (
    json.dumps(
        {"sources": [{"id": "src-1", "annotation": "Kept annotation note."}]},
        indent=2,
    )
    + "\n"
)
LOOK = "Saved from the brief."
PACK_ONLY_A = "Alpha note stays in the pack.\n"
PACK_ONLY_B = "Beta note stays in the pack.\n"


def _output(seq: str) -> Path:
    return work_dir(seq) / "output"


def _snapshots(seq: str) -> list[Path]:
    root = backups_dir(seq)
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith("."))


def _plant_reports(seq: str) -> None:
    output = _output(seq)
    reviews = output / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "paper-a.md").write_text(REVIEW_A, encoding="utf-8")
    (reviews / "paper-b.md").write_text(REVIEW_B, encoding="utf-8")
    (output / "annotation-report.json").write_text(ANNOTATION, encoding="utf-8")


def _save_stage(seq: str, stage: str) -> dict:
    draft = essay_stage(seq, stage, "draft", LOOK)
    assert draft["ok"] is True, draft
    if stage == "5":
        assert draft["stored"] is True, draft
        return draft
    saved = essay_stage(seq, stage, "confirm", LOOK, **picked(draft))
    assert saved["stored"] is True, saved
    return saved


def _review_map(seq: str) -> dict[str, str]:
    return {row["paper_id"]: row["markdown"] for row in stored_critical_reviews(seq)}


def test_ac1_stage_save_snapshots_pack_annotation_and_reviews(workspace):
    """AC1. A successful stage save writes pack JSON, and the report and reviews when they exist."""
    seq = open_sequence()
    assert _snapshots(seq) == []
    draft = essay_stage(seq, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    assert draft.get("stored") is not True
    assert _snapshots(seq) == []
    _plant_reports(seq)
    saved = essay_stage(seq, "1", "confirm", LOOK, **picked(draft))
    assert saved["stored"] is True, saved
    snaps = _snapshots(seq)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.parent.name == seq
    assert snap.parent.parent.name == "backups"
    pack_body = json.loads((snap / "pack.json").read_text(encoding="utf-8"))
    assert pack_body["essay_id"] == seq
    assert pack_body["stage"] == "1"
    assert {row["paper_id"]: row["markdown"] for row in pack_body["critical_reviews"]} == {
        "paper-a": REVIEW_A,
        "paper-b": REVIEW_B,
    }
    assert (snap / "annotation-report.json").read_text(encoding="utf-8") == ANNOTATION
    assert (snap / "reviews" / "paper-a.md").read_text(encoding="utf-8") == REVIEW_A
    assert (snap / "reviews" / "paper-b.md").read_text(encoding="utf-8") == REVIEW_B
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "stage-save"
    assert manifest["reviews"] == ["reviews/paper-a.md", "reviews/paper-b.md"]
    assert manifest["annotation_report"] == "annotation-report.json"
    refused = essay_stage(seq, "9", "draft", LOOK)
    assert refused.get("stored") is not True
    assert _snapshots(seq) == snaps


def test_ac2_pack_validate_snapshots_same_shape(workspace):
    """AC2. A successful pack validate writes the same snapshot shape."""
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    _plant_reports(seq)
    refused = essay_pack_validate(seq, "nope", "draft")
    assert refused["ok"] is False
    assert refused.get("stored") is not True
    assert _snapshots(seq) == []
    body = pack()
    draft = essay_pack_validate(seq, body, "draft")
    assert draft["ok"] is True, draft
    assert draft.get("stored") is not True
    assert _snapshots(seq) == []
    saved = essay_pack_validate(seq, body, "confirm")
    assert saved["stored"] is True, saved
    snaps = _snapshots(seq)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.parent.name == seq
    assert snap.parent.parent.name == "backups"
    pack_body = json.loads((snap / "pack.json").read_text(encoding="utf-8"))
    assert pack_body["essay_id"] == ESSAY
    assert pack_body["title"] == body["title"]
    assert {row["paper_id"]: row["markdown"] for row in pack_body["critical_reviews"]} == {
        "paper-a": REVIEW_A,
        "paper-b": REVIEW_B,
    }
    assert (snap / "annotation-report.json").read_text(encoding="utf-8") == ANNOTATION
    assert (snap / "reviews" / "paper-a.md").read_bytes() == REVIEW_A.encode("utf-8")
    assert (snap / "reviews" / "paper-b.md").read_bytes() == REVIEW_B.encode("utf-8")
    manifest = json.loads((snap / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reason"] == "pack-validate"
    assert manifest["annotation_report"] == "annotation-report.json"
    assert manifest["reviews"] == ["reviews/paper-a.md", "reviews/paper-b.md"]


def test_ac3_pack_restore_puts_reviews_and_pack_back(workspace):
    """AC3. essay.pack.restore puts a chosen snapshot back, including reviews held only in pack JSON."""
    seq = open_sequence()
    _plant_reports(seq)
    _save_stage(seq, "1")
    snap = _snapshots(seq)[0]
    shutil.rmtree(_output(seq) / "reviews")
    (_output(seq) / "annotation-report.json").unlink()
    state = load_state(seq)
    state["saved_pack"] = None
    save_state(seq, state)
    assert stored_critical_reviews(seq) == []
    preview = essay_pack_restore(seq, snap.name, "draft")
    assert preview["ok"] is True, preview
    assert preview["wrote"] is False
    assert preview["stored"] is False
    assert stored_critical_reviews(seq) == []
    restored = essay_pack_restore(seq, snap.name, "confirm")
    assert restored["ok"] is True, restored
    assert restored["stored"] is True
    assert restored["pack_restored"] is True
    assert restored["reviews"] == ["paper-a", "paper-b"]
    assert _review_map(seq) == {"paper-a": REVIEW_A, "paper-b": REVIEW_B}
    assert (_output(seq) / "annotation-report.json").read_text(encoding="utf-8") == ANNOTATION
    saved_pack = load_state(seq)["saved_pack"]
    assert saved_pack["essay_id"] == seq
    assert {row["paper_id"]: row["markdown"] for row in saved_pack["critical_reviews"]} == {
        "paper-a": REVIEW_A,
        "paper-b": REVIEW_B,
    }

    shutil.rmtree(_output(seq) / "reviews")
    state = load_state(seq)
    state["saved_pack"] = {
        "essay_id": seq,
        "title": "Pack holds the reviews",
        "critical_reviews": [
            {"paper_id": "alpha", "markdown": PACK_ONLY_A},
            {"paper_id": "beta", "markdown": PACK_ONLY_B},
        ],
    }
    save_state(seq, state)
    _save_stage(seq, "2")
    pack_snap = _snapshots(seq)[-1]
    manifest = json.loads((pack_snap / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reviews"] == []
    assert not (pack_snap / "reviews").exists()
    held = json.loads((pack_snap / "pack.json").read_text(encoding="utf-8"))
    assert [row["paper_id"] for row in held["critical_reviews"]] == ["alpha", "beta"]
    state = load_state(seq)
    state["saved_pack"] = None
    save_state(seq, state)
    again = essay_pack_restore(seq, pack_snap.name, "draft")
    assert again["wrote"] is False
    put_back = essay_pack_restore(seq, pack_snap.name, "confirm")
    assert put_back["stored"] is True, put_back
    assert put_back["reviews"] == ["alpha", "beta"]
    assert _review_map(seq) == {"alpha": PACK_ONLY_A, "beta": PACK_ONLY_B}
    assert load_state(seq)["saved_pack"]["title"] == "Pack holds the reviews"
    names = sorted(path.name for path in (_output(seq) / "reviews").glob("*.md"))
    assert names == ["alpha.md", "beta.md"]


def test_ac4_restore_refuses_missing_and_corrupt_without_inventing(workspace):
    """AC4. A missing or damaged snapshot is refused and no review file is created."""
    seq = open_sequence()
    missing = essay_pack_restore(seq, "no-such-snapshot", "draft")
    assert missing["ok"] is False
    assert missing["refused"] == "snapshot-missing"
    assert missing["wrote"] is False
    assert missing["stored"] is False
    assert not (_output(seq) / "reviews").exists()
    escaped = essay_pack_restore(seq, "../secrets", "draft")
    assert escaped["refused"] == "snapshot-missing"
    assert escaped["wrote"] is False
    assert not (_output(seq) / "reviews").exists()

    sentinel = _output(seq) / "reviews" / "keep-me.md"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("Keep this review.\n", encoding="utf-8")
    root = backups_dir(seq)
    damaged = root / "damaged-pack"
    damaged.mkdir(parents=True)
    manifest = {
        "essay_id": seq,
        "snapshot_id": "damaged-pack",
        "reason": "stage-save",
        "stage": "1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "pack": "pack.json",
        "annotation_report": None,
        "reviews": [],
    }
    (damaged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (damaged / "pack.json").write_text("{not json", encoding="utf-8")
    broken = essay_pack_restore(seq, "damaged-pack", "draft")
    assert broken["ok"] is False
    assert broken["refused"] == "snapshot-corrupt"
    assert broken["wrote"] is False
    assert broken["stored"] is False
    assert sentinel.read_text(encoding="utf-8") == "Keep this review.\n"
    assert sorted(path.name for path in sentinel.parent.glob("*.md")) == ["keep-me.md"]

    partial = root / "partial-reviews"
    partial.mkdir()
    partial_manifest = dict(manifest)
    partial_manifest["snapshot_id"] = "partial-reviews"
    (partial / "manifest.json").write_text(json.dumps(partial_manifest), encoding="utf-8")
    (partial / "pack.json").write_text(
        json.dumps(
            {
                "essay_id": seq,
                "critical_reviews": [{"paper_id": "alpha"}],
            }
        ),
        encoding="utf-8",
    )
    invented = essay_pack_restore(seq, "partial-reviews", "confirm")
    assert invented["ok"] is False
    assert invented["refused"] == "snapshot-corrupt"
    assert invented["wrote"] is False
    assert not (sentinel.parent / "alpha.md").exists()
    assert sentinel.read_text(encoding="utf-8") == "Keep this review.\n"
    assert load_state(seq).get("saved_pack") in (None, {})


def test_ac5_wipe_and_copy_to_mac_leave_backups_additive(workspace, tmp_path, monkeypatch):
    """AC5. Wipe and --copy-to-mac stay on their existing paths. The snapshot remains."""
    seq = open_sequence()
    _plant_reports(seq)
    _save_stage(seq, "1")
    snap = _snapshots(seq)[0]
    pack_bytes = (snap / "pack.json").read_bytes()
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    log = workspace / "debug.log"
    log.write_text("operator line\n", encoding="utf-8")
    wiped = essay_debug_wipe("delete the logs")
    assert wiped["ok"] is True
    assert not log.exists()
    assert (snap / "pack.json").read_bytes() == pack_bytes
    assert "backup" not in inspect.getsource(wipe_operator_log_files).casefold()
    assert "snapshot_after" not in inspect.getsource(wipe_operator_log_files)

    mac = tmp_path / "mac"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    output = _output(seq)
    (output / "annotation.docx").write_bytes(b"ann-bytes")
    code = first_run_main(["--copy-to-mac", str(output)])
    assert code == 0
    copied = list(mac.rglob("*"))
    assert any(path.name == "annotation.docx" for path in copied)
    assert all(path.name != "backups" for path in copied)
    assert all("pack.json" not in path.name for path in copied)
    assert (snap / "pack.json").read_bytes() == pack_bytes
    assert _STAGE_DELIVERABLES == (
        "annotation.docx",
        "download-list.docx",
        "papers.zip",
        "critical-reviews.zip",
    )
    handoff = inspect.getsource(build_office.build_deliverable_handoff)
    assert "snapshot_after_stage_save" not in handoff
    assert "essay_pack_restore" not in handoff
    assert "backups" not in handoff


def test_ac6_build_covered_one_restore_door():
    """AC6. Cursor and Grok Build share essay.pack.restore. There is not a second snapshot writer."""
    assert HANDLERS["essay.pack.restore"] is essay_pack_restore
    assert cursor_office.restore_pack is essay_pack_restore
    assert build_office.restore_pack is essay_pack_restore
    assert cursor_shell()["handlers"]["essay.pack.restore"] is essay_pack_restore
    assert front_office()["handlers"]["essay.pack.restore"] is essay_pack_restore
    door = next(item for item in DOORS if item["tool"] == "essay.pack.restore")
    assert door["confirm"] == "draft-then-confirm"
    cursor_src = Path(cursor_office.__file__).read_text(encoding="utf-8")
    build_src = Path(build_office.__file__).read_text(encoding="utf-8")
    assert "def snapshot_after_stage_save" not in cursor_src
    assert "def snapshot_after_pack_validate" not in cursor_src
    assert "def snapshot_after_stage_save" not in build_src
    assert "def snapshot_after_pack_validate" not in build_src
    assert "def essay_pack_restore" not in cursor_src
    assert "def essay_pack_restore" not in build_src
    assert "_snapshot_stage_save" in inspect.getsource(_store_stage)
    assert "_snapshot_stage_save" in inspect.getsource(_commit_with_next_card)
    assert "_snapshot_stage_save" in inspect.getsource(essay_stage)
    assert "snapshot_after_stage_save" in inspect.getsource(_snapshot_stage_save)
    assert "snapshot_after_pack_validate" in inspect.getsource(essay_pack_validate)
    assert snapshot_after_stage_save.__module__ == "essay_writer.pack_backup"
    assert snapshot_after_pack_validate.__module__ == "essay_writer.pack_backup"
