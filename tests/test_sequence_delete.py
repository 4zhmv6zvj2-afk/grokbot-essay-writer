"""One sequence can be deleted. The rest of the module stays."""

import json
from pathlib import Path

from helpers import picked

from essay_writer.first_run import MAC_DELIVERABLES_NAME, copy_deliverable_to_mac
from essay_writer.paths import (
    essay_dir,
    kb1_module_dir,
    kb1_sequence_dir,
    read_last_saved,
    sequence_dir,
    uploads_dir,
)
from essay_writer.projects import essay_project_delete, essay_sequence_new
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import sequence_delete_speech
from essay_writer.student_voice import student_surface_hits

MODULE = "MOD1011AA"


def _two_sequences() -> None:
    essay_sequence_new(MODULE, "draft")
    essay_sequence_new(MODULE, "confirm")
    essay_sequence_new(MODULE, "draft")
    essay_sequence_new(MODULE, "confirm")
    (sequence_dir(MODULE, 1) / "keep.txt").write_text("one\n", encoding="utf-8")
    (sequence_dir(MODULE, 2) / "drop.txt").write_text("two\n", encoding="utf-8")
    upload = uploads_dir(MODULE) / "paper.md"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_text("shared\n", encoding="utf-8")
    brief = essay_dir(MODULE) / "brief.md"
    brief.write_text("brief\n", encoding="utf-8")
    note = kb1_module_dir(MODULE) / "module.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("module note\n", encoding="utf-8")
    seq_note = kb1_sequence_dir(MODULE, 2) / "note.md"
    seq_note.parent.mkdir(parents=True, exist_ok=True)
    seq_note.write_text("sequence note\n", encoding="utf-8")
    kept = kb1_sequence_dir(MODULE, 1) / "note.md"
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.write_text("kept note\n", encoding="utf-8")


def test_sequence_delete_refuses_confirm_without_a_draft(workspace):
    _two_sequences()
    silent = essay_project_delete(MODULE, "confirm", sequence=f"{MODULE}-2")
    assert silent["ok"] is False
    assert sequence_dir(MODULE, 2).is_dir()


def test_sequence_delete_waits_for_confirm_and_leaves_the_module(workspace):
    _two_sequences()
    target = f"{MODULE}-2"
    draft = essay_project_delete(MODULE, "draft", sequence=target)
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert draft["deleted"] is False
    assert draft["scope"] == "sequence"
    assert draft["sequence"] == target
    assert draft["sequences"] == [target]
    assert draft["uploads"] == []
    assert draft["brief"] == []
    assert "only MOD1011AA-2" in draft["next"]
    assert "Other sequences" in draft["next"]
    assert student_surface_hits(draft["next"].replace("Confirm card", "")) == []
    assert sequence_dir(MODULE, 2).is_dir()

    deleted = essay_project_delete(MODULE, "confirm", sequence=target, **picked(draft))
    assert deleted["deleted"] is True
    assert deleted["scope"] == "sequence"
    assert not sequence_dir(MODULE, 2).exists()
    assert not kb1_sequence_dir(MODULE, 2).exists()
    assert sequence_dir(MODULE, 1).is_dir()
    assert (sequence_dir(MODULE, 1) / "keep.txt").read_text(encoding="utf-8") == "one\n"
    assert (kb1_sequence_dir(MODULE, 1) / "note.md").is_file()
    assert (uploads_dir(MODULE) / "paper.md").is_file()
    assert (essay_dir(MODULE) / "brief.md").is_file()
    assert (kb1_module_dir(MODULE) / "module.md").is_file()
    assert read_last_saved(MODULE) == 1


def test_deleting_an_older_sequence_leaves_the_last_saved_pointer(workspace):
    _two_sequences()
    assert read_last_saved(MODULE) == 2
    draft = essay_project_delete(MODULE, "draft", sequence=f"{MODULE}-1")
    deleted = essay_project_delete(MODULE, "confirm", sequence=f"{MODULE}-1", **picked(draft))
    assert deleted["deleted"] is True
    assert not sequence_dir(MODULE, 1).exists()
    assert sequence_dir(MODULE, 2).is_dir()
    assert read_last_saved(MODULE) == 2


def test_module_delete_still_removes_every_sequence(workspace):
    _two_sequences()
    draft = essay_project_delete(MODULE, "draft")
    deleted = essay_project_delete(MODULE, "confirm", **picked(draft))
    assert deleted.get("scope") != "sequence"
    assert deleted["deleted"] is True
    assert deleted["sequences"] == [f"{MODULE}-1", f"{MODULE}-2"]
    assert not essay_dir(MODULE).exists()
    assert not uploads_dir(MODULE).exists()
    assert not kb1_module_dir(MODULE).exists()


def test_sequence_delete_refuses_the_wrong_id_and_a_local_only_where(workspace):
    _two_sequences()
    foreign = essay_project_delete(MODULE, "draft", sequence="MOD1004AA-2")
    assert foreign["ok"] is False
    missing = essay_project_delete(MODULE, "draft", sequence=f"{MODULE}-9")
    assert missing["ok"] is False
    local = essay_project_delete(MODULE, "draft", where="local", sequence=f"{MODULE}-2")
    assert local["ok"] is False
    assert sequence_dir(MODULE, 2).is_dir()
    assert sequence_dir(MODULE, 1).is_dir()


def test_sequence_delete_is_the_same_delete_door(workspace):
    assert HANDLERS["essay.project.delete"] is essay_project_delete
    assert front_office()["handlers"]["essay.project.delete"] is essay_project_delete
    assert cursor_shell()["handlers"]["essay.project.delete"] is essay_project_delete
    _two_sequences()
    spoken = front_office_call(
        "essay.project.delete",
        {"module": MODULE, "confirmPhase": "draft", "sequence": f"{MODULE}-2"},
    )
    assert spoken["wrote"] is False
    assert spoken["next"] == sequence_delete_speech(f"{MODULE}-2", computer=False)
    assert sequence_dir(MODULE, 2).is_dir()


def _paths(body: dict) -> set[Path]:
    return {Path(item).resolve() for item in body["computer_list"]}


def _store_mac_copy(sequence: int, folder: Path, name: str, payload: bytes) -> Path:
    source = sequence_dir(MODULE, sequence) / "output" / name
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(payload)
    essay_id = f"{MODULE}-{sequence}"
    copied = copy_deliverable_to_mac(source, mac_dir=folder / essay_id)
    assert copied["copied"] is True
    return folder / essay_id / name


def _forbid_listing(monkeypatch, roots: list[Path]) -> None:
    banned = [root.resolve() for root in roots]
    real_iterdir = Path.iterdir
    real_rglob = Path.rglob
    real_glob = Path.glob

    def blocked(self: Path) -> bool:
        try:
            resolved = self.resolve()
        except OSError:
            resolved = self
        return any(resolved == root or root in resolved.parents for root in banned)

    def iterdir(self: Path):
        if blocked(self):
            raise AssertionError(f"listed {self}")
        return real_iterdir(self)

    def rglob(self: Path, pattern: str):
        if blocked(self):
            raise AssertionError(f"crawled {self}")
        return real_rglob(self, pattern)

    def glob(self: Path, pattern: str):
        if blocked(self):
            raise AssertionError(f"crawled {self}")
        return real_glob(self, pattern)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    monkeypatch.setattr(Path, "rglob", rglob)
    monkeypatch.setattr(Path, "glob", glob)


def test_sequence_both_reuses_a_saved_mac_path(workspace):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-mac"
    mac.mkdir()
    saved = _store_mac_copy(2, mac, f"{MODULE}-2.docx", b"saved-copy")
    stray = mac / "notes.docx"
    stray.write_bytes(b"stray")
    record = json.loads((sequence_dir(MODULE, 2) / MAC_DELIVERABLES_NAME).read_text(encoding="utf-8"))
    assert saved.resolve().as_posix() in record["paths"]
    target = f"{MODULE}-2"

    draft = essay_project_delete(MODULE, "draft", where="both", sequence=target)
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert draft["mac_paths_reused"] is True
    assert draft["guessed"] is False
    assert draft.get("needs_local_paths") is not True
    assert saved.resolve() in _paths(draft)
    assert stray.resolve() not in _paths(draft)
    assert student_surface_hits(draft["next"].replace("Confirm card", "")) == []
    assert saved.is_file()
    assert sequence_dir(MODULE, 2).is_dir()

    deleted = essay_project_delete(MODULE, "confirm", where="both", sequence=target, **picked(draft))
    assert deleted["deleted"] is True
    assert deleted["deleted_local"] is True
    assert deleted["mac_paths_reused"] is True
    assert not saved.exists()
    assert stray.is_file()
    assert not sequence_dir(MODULE, 2).exists()
    assert sequence_dir(MODULE, 1).is_dir()
    assert (kb1_sequence_dir(MODULE, 1) / "note.md").is_file()


def test_sequence_both_reuses_default_mac_names_without_a_record(workspace, monkeypatch):
    _two_sequences()
    mac = workspace.parent / "handoff"
    documents = workspace.parent / "Documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _forbid_listing(monkeypatch, [mac, documents])
    seq_id = f"{MODULE}-2"
    seq_folder = mac / MODULE / seq_id
    seq_folder.mkdir(parents=True)
    essay = seq_folder / f"{MODULE}-2.docx"
    essay.write_bytes(b"default-essay")
    annotation = seq_folder / "annotation.docx"
    annotation.write_bytes(b"default-notes")
    stray = mac / "notes.docx"
    stray.write_bytes(b"stray")
    decoy = documents / "annotation.docx"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_bytes(b"decoy")
    assert not (sequence_dir(MODULE, 2) / MAC_DELIVERABLES_NAME).exists()

    draft = essay_project_delete(MODULE, "draft", where="both", sequence=f"{MODULE}-2")
    assert draft["mac_paths_reused"] is True
    assert draft["guessed"] is False
    listed = _paths(draft)
    assert essay.resolve() in listed
    assert annotation.resolve() in listed
    assert stray.resolve() not in listed
    assert decoy.resolve() not in listed

    deleted = essay_project_delete(MODULE, "confirm", where="both", sequence=f"{MODULE}-2", **picked(draft))
    assert deleted["deleted_local"] is True
    assert not essay.exists()
    assert not annotation.exists()
    assert stray.is_file()
    assert decoy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()


def test_sequence_both_asks_when_saved_paths_are_missing(workspace, monkeypatch):
    _two_sequences()
    documents = workspace.parent / "Documents"
    mac = workspace.parent / "empty-handoff"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _forbid_listing(monkeypatch, [mac, documents])
    missing = mac / f"{MODULE}-2.docx"
    record = sequence_dir(MODULE, 2) / MAC_DELIVERABLES_NAME
    record.write_text(json.dumps({"paths": [str(missing)]}) + "\n", encoding="utf-8")
    decoy = documents / f"{MODULE}-2.docx"
    decoy.parent.mkdir(parents=True, exist_ok=True)
    decoy.write_bytes(b"do-not-take")
    nested = documents / MODULE / "nested" / "annotation.docx"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"nested")

    asked = essay_project_delete(MODULE, "draft", where="both", sequence=f"{MODULE}-2")
    assert asked["ok"] is False
    assert asked["needs_local_paths"] is True
    assert asked["mac_paths_reused"] is False
    assert asked["guessed"] is False
    assert asked["computer_list"] == []
    assert asked["scope"] == "sequence"
    assert "path" in asked["reason"].casefold()
    assert student_surface_hits(asked["reason"]) == []
    assert decoy.is_file()
    assert nested.is_file()
    assert sequence_dir(MODULE, 2).is_dir()
    assert str(decoy) not in json.dumps(asked)
    assert str(nested) not in json.dumps(asked)


def test_sequence_both_does_not_reuse_paths_the_caller_left_out(workspace):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-mac"
    mac.mkdir()
    saved = _store_mac_copy(2, mac, f"{MODULE}-2.docx", b"saved-copy")
    named = mac / "named.docx"
    named.write_bytes(b"named")
    target = f"{MODULE}-2"

    draft = essay_project_delete(MODULE, "draft", where="both", sequence=target, localPaths=[str(named)])
    assert draft["mac_paths_reused"] is False
    assert _paths(draft) == {named.resolve()}

    deleted = essay_project_delete(
        MODULE, "confirm", where="both", sequence=target, localPaths=[str(named)], **picked(draft)
    )
    assert deleted["deleted_local"] is True
    assert not named.exists()
    assert saved.is_file()
    assert not sequence_dir(MODULE, 2).exists()


def test_module_both_reuses_saved_paths_across_sequences(workspace):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-mac"
    mac.mkdir()
    first = _store_mac_copy(1, mac, f"{MODULE}-1.docx", b"one")
    second = _store_mac_copy(2, mac, f"{MODULE}-2.docx", b"two")
    stray = mac / "notes.docx"
    stray.write_bytes(b"stray")

    draft = essay_project_delete(MODULE, "draft", where="both")
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    assert draft["mac_paths_reused"] is True
    assert draft["guessed"] is False
    assert draft.get("needs_local_paths") is not True
    listed = _paths(draft)
    assert first.resolve() in listed
    assert second.resolve() in listed
    assert stray.resolve() not in listed
    assert student_surface_hits(draft["next"].replace("Confirm card", "")) == []
    assert first.is_file()
    assert essay_dir(MODULE).is_dir()

    deleted = essay_project_delete(MODULE, "confirm", where="both", **picked(draft))
    assert deleted["deleted"] is True
    assert deleted["deleted_local"] is True
    assert deleted["mac_paths_reused"] is True
    assert not first.exists()
    assert not second.exists()
    assert stray.is_file()
    assert not essay_dir(MODULE).exists()


def test_module_both_uses_default_names_without_a_crawl(workspace, monkeypatch):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-module-handoff"
    documents = workspace.parent / f"{workspace.name}-documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _forbid_listing(monkeypatch, [mac, documents])
    mac.mkdir()
    (mac / MODULE / f"{MODULE}-1").mkdir(parents=True)
    (mac / MODULE / f"{MODULE}-2").mkdir(parents=True)
    one = mac / MODULE / f"{MODULE}-1" / f"{MODULE}-1.docx"
    two = mac / MODULE / f"{MODULE}-2" / f"{MODULE}-2.docx"
    one.write_bytes(b"one")
    two.write_bytes(b"two")
    notes = mac / MODULE / f"{MODULE}-1" / "annotation.docx"
    notes.write_bytes(b"notes")
    stray = mac / "notes.docx"
    stray.write_bytes(b"stray")
    decoy = documents / f"{MODULE}-1.docx"
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(b"decoy")
    assert not (sequence_dir(MODULE, 1) / MAC_DELIVERABLES_NAME).exists()
    assert not (sequence_dir(MODULE, 2) / MAC_DELIVERABLES_NAME).exists()

    draft = essay_project_delete(MODULE, "draft", where="both")
    assert draft["mac_paths_reused"] is True
    assert draft["guessed"] is False
    listed = _paths(draft)
    assert one.resolve() in listed
    assert two.resolve() in listed
    assert notes.resolve() in listed
    assert stray.resolve() not in listed
    assert decoy.resolve() not in listed
    assert str(decoy) not in json.dumps(draft)

    deleted = essay_project_delete(MODULE, "confirm", where="both", **picked(draft))
    assert deleted["deleted_local"] is True
    assert not one.exists()
    assert not two.exists()
    assert not notes.exists()
    assert stray.is_file()
    assert decoy.is_file()


def test_module_both_asks_when_none_are_visible(workspace, monkeypatch):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-empty-handoff"
    documents = workspace.parent / f"{workspace.name}-documents"
    mac.mkdir()
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _forbid_listing(monkeypatch, [mac, documents])
    decoy = documents / f"{MODULE}-1.docx"
    decoy.parent.mkdir(parents=True)
    decoy.write_bytes(b"no")

    asked = essay_project_delete(MODULE, "draft", where="both")
    assert asked["ok"] is False
    assert asked["needs_local_paths"] is True
    assert asked["mac_paths_reused"] is False
    assert asked["guessed"] is False
    assert asked["computer_list"] == []
    assert asked["scope"] == "module"
    assert "path" in asked["reason"].casefold()
    assert student_surface_hits(asked["reason"]) == []
    assert decoy.is_file()
    assert str(decoy) not in json.dumps(asked)
    assert essay_dir(MODULE).is_dir()


def test_module_both_uses_a_path_when_only_one_sequence_has_one(workspace, monkeypatch):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-one-handoff"
    documents = workspace.parent / f"{workspace.name}-documents"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _forbid_listing(monkeypatch, [mac, documents])
    mac.mkdir()
    (mac / MODULE / f"{MODULE}-1").mkdir(parents=True)
    one = mac / MODULE / f"{MODULE}-1" / f"{MODULE}-1.docx"
    one.write_bytes(b"one")
    hidden = documents / f"{MODULE}-2.docx"
    hidden.parent.mkdir(parents=True, exist_ok=True)
    hidden.write_bytes(b"hidden")

    draft = essay_project_delete(MODULE, "draft", where="both")
    assert draft["ok"] is True, draft
    assert draft.get("needs_local_paths") is not True
    assert draft["mac_paths_reused"] is True
    assert _paths(draft) == {one.resolve()}
    assert str(hidden) not in json.dumps(draft)

    deleted = essay_project_delete(MODULE, "confirm", where="both", **picked(draft))
    assert deleted["deleted"] is True
    assert not one.exists()
    assert hidden.is_file()
    assert not essay_dir(MODULE).exists()


def test_module_both_caller_paths_win(workspace):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-mac"
    mac.mkdir()
    saved = _store_mac_copy(1, mac, f"{MODULE}-1.docx", b"saved")
    named = mac / "named.docx"
    named.write_bytes(b"named")

    draft = essay_project_delete(MODULE, "draft", where="both", localPaths=[str(named)])
    assert draft["mac_paths_reused"] is False
    assert _paths(draft) == {named.resolve()}

    deleted = essay_project_delete(MODULE, "confirm", where="both", localPaths=[str(named)], **picked(draft))
    assert deleted["deleted_local"] is True
    assert not named.exists()
    assert saved.is_file()
    assert not essay_dir(MODULE).exists()


def test_module_local_still_asks_and_sequence_local_stays_refused(workspace):
    _two_sequences()
    mac = workspace.parent / f"{workspace.name}-mac"
    mac.mkdir()
    saved = _store_mac_copy(2, mac, f"{MODULE}-2.docx", b"saved-copy")

    asked = essay_project_delete(MODULE, "draft", where="local")
    assert asked["ok"] is False
    assert asked["needs_local_paths"] is True
    assert saved.is_file()
    assert essay_dir(MODULE).is_dir()

    local = essay_project_delete(MODULE, "draft", where="local", sequence=f"{MODULE}-2")
    assert local["ok"] is False
    assert local.get("needs_local_paths") is not True
    assert saved.is_file()
    assert sequence_dir(MODULE, 2).is_dir()

    workspace_only = essay_project_delete(MODULE, "draft", sequence=f"{MODULE}-2")
    assert workspace_only["ok"] is True
    assert workspace_only["computer_list"] == []
    deleted = essay_project_delete(MODULE, "confirm", sequence=f"{MODULE}-2", **picked(workspace_only))
    assert deleted["deleted"] is True
    assert deleted["deleted_local"] is False
    assert saved.is_file()
