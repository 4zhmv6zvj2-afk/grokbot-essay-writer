"""Lineage regressions: delete lists, roll-forward, Word intake, pack restore."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from helpers import picked

from essay_writer.intake import essay_intake
from essay_writer.pack_backup import backups_dir, essay_pack_restore
from essay_writer.paths import (
    essay_dir,
    kb1_module_dir,
    sequence_dir,
    uploads_dir,
    work_dir,
)
from essay_writer.projects import (
    essay_project_delete,
    essay_sequence_new,
    save_sequence_state,
)
from essay_writer.stage_track import load_pointer

MODULE = "MOD1004AA"


def _docx(path: Path, paragraphs: list[str]) -> None:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))


def _outside(workspace: Path) -> Path:
    folder = workspace.parent / f"{workspace.name}-mac"
    folder.mkdir(exist_ok=True)
    return folder


def _open(module: str, parent: str | None = None) -> dict:
    draft = essay_sequence_new(module, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm", parent)
    assert opened["ok"] is True, opened
    return opened


def _seed_module() -> None:
    assert _open(MODULE)["sequence_id"] == f"{MODULE}-1"
    upload = uploads_dir(MODULE) / "paper.md"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_text("shared\n", encoding="utf-8")
    (essay_dir(MODULE) / "brief.md").write_text("brief\n", encoding="utf-8")
    note = kb1_module_dir(MODULE) / "paper.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("vault\n", encoding="utf-8")


def test_draft_lists_a_module_folder_kb1_note_before_it_can_be_removed(workspace):
    """A paper note under the module folder is part of the drafted list."""
    del workspace
    _seed_module()
    note = essay_dir(MODULE) / "kb1" / "extra.md"
    note.parent.mkdir(parents=True)
    note.write_text("paper note\n", encoding="utf-8")
    draft = essay_project_delete(MODULE, "draft")
    assert draft["wrote"] is False
    assert note.is_file()
    paths = [item["path"] for item in draft["kb1"]]
    assert "kb1/extra.md" in paths
    assert any("kb1/extra.md" in row for row in draft["targets"])
    deleted = essay_project_delete(MODULE, "confirm", **picked(draft))
    assert deleted["deleted"] is True
    assert not note.exists()


def test_confirm_does_not_remove_a_kb1_note_absent_from_the_draft(workspace):
    """A note created after the draft is not on that list, so it stays."""
    del workspace
    _seed_module()
    draft = essay_project_delete(MODULE, "draft")
    assert draft["wrote"] is False
    listed = [item["path"] for item in draft["kb1"]]
    note = essay_dir(MODULE) / "kb1" / "sneak.md"
    note.parent.mkdir(parents=True)
    note.write_text("not on the draft\n", encoding="utf-8")
    assert "kb1/sneak.md" not in listed
    deleted = essay_project_delete(MODULE, "confirm", **picked(draft))
    assert deleted["ok"] is False
    assert note.read_text(encoding="utf-8") == "not on the draft\n"
    assert sequence_dir(MODULE, 1).is_dir()
    assert (uploads_dir(MODULE) / "paper.md").is_file()
    assert (essay_dir(MODULE) / "brief.md").is_file()


def test_new_sequence_restarts_at_stage_1_and_does_not_keep_parent_mac_paths(workspace):
    """Research stays. The parent's computer-path record does not."""
    parent = _open(MODULE)["sequence_id"]
    state_path = sequence_dir(MODULE, 1) / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["research"] = {"summary": {"topic": "ports", "sources": []}, "full": None}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    pointer = sequence_dir(MODULE, 1) / "tracking" / "stage.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(
        json.dumps({"current": "10", "saved": ["1", "2", "3"], "files": {}, "closed": True}) + "\n",
        encoding="utf-8",
    )
    for stage in ("1", "2", "3"):
        note = sequence_dir(MODULE, 1) / "tracking" / f"{stage}.md"
        note.write_text(f"# Stage {stage}\n\nSaved on the parent.\n", encoding="utf-8")
    mac = _outside(workspace) / f"{MODULE}-1.docx"
    mac.write_bytes(b"parent-computer-copy")
    record = sequence_dir(MODULE, 1) / "mac-deliverables.json"
    record.write_text(json.dumps({"paths": [str(mac)]}) + "\n", encoding="utf-8")
    parent_record = record.read_bytes()
    final = sequence_dir(MODULE, 1) / "output" / f"{MODULE}-10" / f"{MODULE}-final.docx"
    _docx(final, ["parent final"])
    parent_final = final.read_bytes()

    opened = _open(MODULE, parent)
    child = opened["sequence_id"]
    assert child == f"{MODULE}-2"
    child_record = sequence_dir(MODULE, 2) / "mac-deliverables.json"
    assert not child_record.exists()
    assert record.read_bytes() == parent_record
    assert mac.is_file()
    fresh = load_pointer(child)
    assert fresh["current"] == "1"
    assert fresh["saved"] == []
    child_state = json.loads((sequence_dir(MODULE, 2) / "state.json").read_text(encoding="utf-8"))
    assert child_state["research"]["summary"]["topic"] == "ports"
    assert child_state["essay_id"] == child
    for stage in ("1", "2", "3"):
        assert not (work_dir(child) / "tracking" / f"{stage}.md").exists()
    parked = work_dir(child) / "reference" / f"{MODULE}-final.docx"
    assert parked.is_file()
    assert parked.read_bytes() == parent_final
    assert final.is_file()
    assert load_pointer(parent)["current"] == "10"


def test_changed_word_rolls_forward_and_unchanged_word_stays_unassigned(workspace):
    """Deliverable Word files in output/ are not the essay being compared."""
    _open(MODULE)
    essay = [
        "The port handles containers and schedules.",
        "Ships wait outside the channel.",
        "Reference List",
        "Smith, A. (2020) Port pricing. Journal of Ports.",
    ]
    output = sequence_dir(MODULE, 1) / "output" / f"{MODULE}-1.docx"
    _docx(output, essay)
    _docx(
        sequence_dir(MODULE, 1) / "output" / "download-list.docx",
        ["Leftover bibliography only.", "Still needs a PDF."],
    )
    _docx(
        sequence_dir(MODULE, 1) / "output" / "annotation.docx",
        ["Citation line for a saved PDF."],
    )
    parent_bytes = output.read_bytes()
    save_sequence_state(
        MODULE,
        1,
        {
            "essay_id": f"{MODULE}-1",
            "sequence": 1,
            "sequence_id": f"{MODULE}-1",
            "research": {"summary": {"topic": "ports", "sources": []}, "full": None},
            "validations": {},
            "word": {},
            "revisions": [],
            "shelf": {},
        },
    )
    same = workspace / "unassigned" / "same.docx"
    same.parent.mkdir(parents=True, exist_ok=True)
    same.write_bytes(parent_bytes)
    draft = essay_intake("same.docx", "draft", MODULE)
    assert draft["wrote"] is False
    assert draft["unchanged"] is True
    assert draft.get("stays") == "unassigned"
    filed = essay_intake("same.docx", "confirm", MODULE)
    assert filed["wrote"] is False
    assert same.is_file()
    assert not sequence_dir(MODULE, 2).exists()
    assert output.read_bytes() == parent_bytes

    changed = workspace / "unassigned" / "changed.docx"
    _docx(
        changed,
        [
            "The port handles containers and barges.",
            "Ships wait outside the channel.",
            "Reference List",
            "Smith, A. (2020) Port pricing. Journal of Ports.",
        ],
    )
    word_draft = essay_intake("changed.docx", "draft", MODULE)
    assert word_draft["wrote"] is False
    assert word_draft["kind"] == "output"
    assert word_draft["essay_id"] == f"{MODULE}-2"
    word_filed = essay_intake("changed.docx", "confirm", MODULE)
    assert word_filed["ok"] is True, word_filed
    assert word_filed["essay_id"] == f"{MODULE}-2"
    assert word_filed["research_started"] is False
    assert output.read_bytes() == parent_bytes
    assert (sequence_dir(MODULE, 2) / "output" / f"{MODULE}-2.docx").is_file()
    assert not (uploads_dir(MODULE) / "changed.docx").exists()
    assert not changed.exists()


def test_pack_restore_draft_writes_nothing_and_a_linked_review_is_refused(workspace):
    """Review text has to be bytes stored in the snapshot, not a link elsewhere."""
    seq = _open(MODULE)["sequence_id"]
    outside = workspace / "outside-review.md"
    outside.write_text("Invented outside the snapshot.\n", encoding="utf-8")
    snap = backups_dir(seq) / "linked-review"
    (snap / "reviews").mkdir(parents=True)
    (snap / "reviews" / "paper-a.md").symlink_to(outside)
    manifest = {
        "essay_id": seq,
        "snapshot_id": "linked-review",
        "reason": "stage-save",
        "stage": "4b",
        "created_at": "2026-01-01T00:00:00+00:00",
        "pack": "pack.json",
        "annotation_report": None,
        "reviews": ["reviews/paper-a.md"],
    }
    (snap / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (snap / "pack.json").write_text(
        json.dumps({"essay_id": seq, "title": "Snapshot pack"}) + "\n",
        encoding="utf-8",
    )
    live = work_dir(seq) / "output" / "reviews" / "keep.md"
    live.parent.mkdir(parents=True)
    live.write_text("Already on the sequence.\n", encoding="utf-8")
    before = live.read_bytes()
    draft = essay_pack_restore(seq, "linked-review", "draft")
    assert draft["ok"] is False
    assert draft["wrote"] is False
    assert draft["stored"] is False
    assert live.read_bytes() == before
    assert not (live.parent / "paper-a.md").exists()
    restored = essay_pack_restore(seq, "linked-review", "confirm")
    assert restored["ok"] is False
    assert restored["wrote"] is False
    assert restored.get("refused") == "snapshot-corrupt"
    assert live.read_bytes() == before
    assert not (live.parent / "paper-a.md").exists()
    assert outside.read_text(encoding="utf-8") == "Invented outside the snapshot.\n"
