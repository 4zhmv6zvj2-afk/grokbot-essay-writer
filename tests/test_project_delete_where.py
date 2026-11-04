"""Delete asks where, then confirms the exact list.

Workspace-only stays the draft-then-confirm delete. Copies on the student's
computer are removed only when where is local or both and the confirm names them.
"""

from pathlib import Path

from helpers import picked
from test_projects import MODULE, _confirm_new

from essay_writer.doors import DOORS
from essay_writer.paths import (
    essay_dir,
    kb1_module_dir,
    sequence_dir,
    uploads_dir,
    workspace_root,
)
from essay_writer.projects import (
    LOCAL_REMOVAL_SENTENCE,
    essay_project_delete,
    essay_projects,
)
from essay_writer.server import HANDLERS, INSTRUCTIONS, call_local
from essay_writer.shells import cursor_shell, front_office
from essay_writer.student_voice import student_surface_hits

REPO = Path(__file__).resolve().parents[1]


def _outside(workspace: Path) -> Path:
    folder = workspace.parent / f"{workspace.name}-mac"
    folder.mkdir(exist_ok=True)
    return folder


def _file(folder: Path, name: str, payload: bytes = b"handed-copy") -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _seed() -> None:
    assert _confirm_new()["sequence_id"] == f"{MODULE}-1"
    upload = uploads_dir(MODULE) / "paper.md"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_text("keep until confirm\n", encoding="utf-8")
    brief = essay_dir(MODULE) / "brief.md"
    brief.write_text("brief\n", encoding="utf-8")
    note = kb1_module_dir(MODULE) / "paper.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("vault\n", encoding="utf-8")


def test_workspace_only_still_waits_and_leaves_computer_copies(workspace):
    _seed()
    copy = _file(_outside(workspace), f"{MODULE}.docx")
    draft = essay_project_delete(MODULE, "draft")
    assert draft["wrote"] is False
    assert draft["deleted"] is False
    assert draft["deleted_local"] is False
    assert draft["where"] == "grokbot"
    assert draft["where_label"] == "Essay workspace only"
    assert draft["sequences"] == [f"{MODULE}-1"]
    assert any(item["path"] == "paper.md" for item in draft["uploads"])
    assert any(item["path"] == "brief.md" for item in draft["brief"])
    assert any(item["path"] == "paper.md" for item in draft["kb1"])
    assert "your computer:" not in " ".join(draft["targets"])
    assert "will be removed" not in draft["next"]
    assert copy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()

    (uploads_dir(MODULE) / "added.md").write_text("later\n", encoding="utf-8")
    named = essay_project_delete(MODULE, "confirm")
    assert named["ok"] is False
    assert copy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()

    fresh = essay_project_delete(MODULE, "draft")
    deleted = essay_project_delete(MODULE, "confirm", **picked(fresh))
    assert deleted["wrote"] is True
    assert deleted["deleted"] is True
    assert deleted["deleted_local"] is False
    assert not sequence_dir(MODULE, 1).exists()
    assert not uploads_dir(MODULE).exists()
    assert not kb1_module_dir(MODULE).exists()
    assert copy.is_file()


def test_where_must_be_a_known_choice(workspace):
    _seed()
    refused = essay_project_delete(MODULE, "draft", where="workspace")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert sequence_dir(MODULE, 1).is_dir()
    assert "grokbot" in refused["reason"]
    assert "local" in refused["reason"]
    assert "both" in refused["reason"]


def test_workspace_only_refuses_computer_paths(workspace):
    _seed()
    copy = _file(_outside(workspace), f"{MODULE}.docx")
    refused = essay_project_delete(MODULE, "draft", where="grokbot", localPaths=[str(copy)])
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert copy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()
    confirm = essay_project_delete(MODULE, "confirm", localPaths=[str(copy)])
    assert confirm["ok"] is False
    assert copy.is_file()
    assert uploads_dir(MODULE).is_dir()


def test_local_and_both_need_named_paths(workspace):
    _seed()
    for phase in ("draft", "confirm"):
        for choice in ("local", "both"):
            refused = essay_project_delete(MODULE, phase, where=choice)
            assert refused["ok"] is False
            assert refused["needs_local_paths"] is True
            assert refused["wrote"] is False
    assert sequence_dir(MODULE, 1).is_dir()
    assert uploads_dir(MODULE).is_dir()
    assert essay_projects("continue")["rows"][0]["essay_id"].startswith("MOD1011AA")


def test_local_draft_lists_paths_and_confirm_removes_only_those_files(workspace):
    _seed()
    mac = _outside(workspace)
    copy = _file(mac, f"{MODULE}.docx", b"word-bytes")
    zipped = _file(mac, f"{MODULE}-papers.zip", b"zip-bytes")
    other = _file(mac, "other-module.docx", b"leave-me")
    draft = essay_project_delete(
        MODULE,
        "draft",
        where="local",
        localPaths=[str(copy), str(zipped), str(copy)],
    )
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert draft["stored"] is False
    assert draft["where"] == "local"
    assert draft["where_label"] == "Copies on your computer only"
    assert draft["sequences"] == []
    assert [item["path"] for item in draft["local"]] == [str(copy), str(zipped)]
    assert draft["targets"] == [f"your computer: {copy}", f"your computer: {zipped}"]
    assert LOCAL_REMOVAL_SENTENCE in draft["next"]
    assert LOCAL_REMOVAL_SENTENCE in draft["local_notice"]
    assert str(copy) in draft["local_notice"]
    assert str(zipped) in draft["local_notice"]
    assert student_surface_hits(draft["next"].replace("Confirm card", "")) == []
    assert copy.is_file() and zipped.is_file() and other.is_file()
    assert sequence_dir(MODULE, 1).is_dir()
    assert not (essay_dir(MODULE) / ".drafts" / "essay.project.delete").exists()
    assert (workspace_root() / "Essay-writer" / ".delete-drafts" / MODULE).is_dir()

    skipped = essay_project_delete(MODULE, "confirm", where="local", localPaths=[str(copy)])
    assert skipped["ok"] is False
    assert copy.is_file()

    deleted = essay_project_delete(
        MODULE,
        "confirm",
        where="local",
        localPaths=[str(copy), str(zipped)],
        **picked(draft),
    )
    assert deleted["wrote"] is True
    assert deleted["deleted"] is False
    assert deleted["deleted_local"] is True
    assert deleted["removed_local"] == [str(copy), str(zipped)]
    assert LOCAL_REMOVAL_SENTENCE in deleted["local_notice"]
    assert not copy.exists()
    assert not zipped.exists()
    assert other.is_file()
    assert sequence_dir(MODULE, 1).is_dir()
    assert uploads_dir(MODULE).is_dir()
    assert (essay_dir(MODULE) / "brief.md").is_file()


def test_local_string_path_and_a_changed_file_is_refused(workspace):
    _seed()
    copy = _file(_outside(workspace), f"{MODULE}.docx", b"before")
    draft = essay_project_delete(MODULE, "draft", where="local", localPaths=str(copy))
    assert draft["wrote"] is False
    assert draft["local"][0]["path"] == str(copy)
    copy.write_bytes(b"after")
    refused = essay_project_delete(MODULE, "confirm", where="local", localPaths=str(copy))
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert copy.read_bytes() == b"after"
    assert sequence_dir(MODULE, 1).is_dir()


def test_both_removes_the_workspace_and_the_named_copies(workspace):
    _seed()
    copy = _file(_outside(workspace), f"{MODULE}.docx")
    draft = essay_project_delete(MODULE, "draft", where="both", localPaths=[str(copy)])
    assert draft["wrote"] is False
    assert f"{MODULE}-1" in " ".join(draft["targets"])
    assert f"your computer: {copy}" in draft["targets"]
    assert "essay workspace upload: paper.md" in draft["targets"]
    assert "essay workspace brief: brief.md" in draft["targets"]
    assert "essay workspace paper note: paper.md" in draft["targets"]
    assert LOCAL_REMOVAL_SENTENCE in draft["next"]
    assert copy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()

    deleted = essay_project_delete(MODULE, "confirm", where="both", localPaths=[str(copy)], **picked(draft))
    assert deleted["wrote"] is True
    assert deleted["deleted"] is True
    assert deleted["deleted_local"] is True
    assert LOCAL_REMOVAL_SENTENCE in deleted["local_notice"]
    assert not copy.exists()
    assert not sequence_dir(MODULE, 1).exists()
    assert not uploads_dir(MODULE).exists()
    assert not kb1_module_dir(MODULE).exists()


def test_a_different_where_does_not_reuse_the_draft(workspace):
    _seed()
    copy = _file(_outside(workspace), f"{MODULE}.docx")
    essay_project_delete(MODULE, "draft", where="grokbot")
    refused = essay_project_delete(MODULE, "confirm", where="local", localPaths=[str(copy)])
    assert refused["ok"] is False
    essay_project_delete(MODULE, "draft", where="local", localPaths=[str(copy)])
    refused = essay_project_delete(MODULE, "confirm", where="both", localPaths=[str(copy)])
    assert refused["ok"] is False
    assert copy.is_file()
    assert sequence_dir(MODULE, 1).is_dir()
    assert uploads_dir(MODULE).is_dir()


def test_local_paths_that_are_not_safe_copies_are_refused(workspace):
    _seed()
    mac = _outside(workspace)
    copy = _file(mac, f"{MODULE}.docx")
    linked = mac / f"{MODULE}-link.docx"
    linked.symlink_to(copy)
    folder = mac / "packet.docx"
    folder.mkdir()
    inside = _file(workspace / "Documents", f"{MODULE}.docx")
    volume = _file(workspace.parent / f"{workspace.name}-outside" / "ResearchDrive", f"{MODULE}.docx")
    pdf = _file(mac, f"{MODULE}.pdf")
    real = mac / "real"
    held = _file(real, f"{MODULE}-held.docx")
    alias = mac / "alias"
    alias.symlink_to(real, target_is_directory=True)
    cases = [
        "MOD1011AA.docx",
        str(linked),
        str(folder),
        str(inside),
        str(volume),
        str(pdf),
        str(mac / "missing.docx"),
        str(alias / held.name),
    ]
    for path in cases:
        refused = essay_project_delete(MODULE, "confirm", where="local", localPaths=[path])
        assert refused["ok"] is False, path
        assert refused["wrote"] is False
    assert copy.is_file()
    assert linked.is_symlink()
    assert folder.is_dir()
    assert inside.is_file()
    assert volume.is_file()
    assert pdf.is_file()
    assert held.is_file()
    assert sequence_dir(MODULE, 1).is_dir()
    shown = essay_project_delete(MODULE, "draft", where="local", localPaths=[str(copy)])
    assert student_surface_hits(shown["next"].replace("Confirm card", "")) == []


def test_local_delete_works_after_the_workspace_module_is_gone(workspace):
    mac = _outside(workspace)
    copy = _file(mac, f"{MODULE}.docx", b"left-behind")
    assert MODULE not in essay_projects("delete")["modules"]
    draft = call_local(
        "essay.project.delete",
        {"module": MODULE, "confirmPhase": "draft", "where": "local", "localPaths": [str(copy)]},
    )
    assert draft["wrote"] is False
    assert draft["where"] == "local"
    assert str(copy) in draft["targets"][0]
    assert not essay_dir(MODULE).exists()
    assert all(
        not row.get("essay_id", "").startswith(f"{MODULE}-")
        for row in essay_projects("continue")["rows"]
    )
    deleted = essay_project_delete(MODULE, "confirm", where="local", localPaths=[str(copy)], **picked(draft))
    assert deleted["deleted_local"] is True
    assert deleted["deleted"] is False
    assert not copy.exists()
    assert not essay_dir(MODULE).exists()
    assert not (workspace_root() / "Essay-writer" / ".delete-drafts").exists()


def test_both_refuses_when_the_workspace_module_is_gone(workspace):
    copy = _file(_outside(workspace), f"{MODULE}.docx")
    refused = essay_project_delete(MODULE, "confirm", where="both", localPaths=[str(copy)])
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert copy.is_file()
    assert "local" in refused["reason"]


def test_plain_english_and_shared_handler(workspace):
    door = next(item for item in DOORS if item["tool"] == "essay.project.delete")
    assert door["requires"] == ["module", "confirmPhase"]
    assert "grokbot" in door["description"]
    assert "local" in door["description"]
    assert "both" in door["description"]
    for banned in ("Grok Bot", "Grok Build", "Cursor", "SuperGrok", "mid office", "mid-office"):
        assert banned not in door["description"]
    assert "localPaths" in INSTRUCTIONS
    assert "where grokbot" in INSTRUCTIONS
    assert "files on the student's computer will be removed" in INSTRUCTIONS
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "switched on" in bot.casefold()
    assert "not switched on" not in bot.casefold()
    assert "computer_list" in bot
    assert "do not guess" in bot.casefold()
    assert "essay.project.delete" in bot
    assert "where" in bot and "grokbot" in bot
    assert HANDLERS["essay.project.delete"] is essay_project_delete
    assert front_office()["handlers"]["essay.project.delete"] is essay_project_delete
    assert cursor_shell()["handlers"]["essay.project.delete"] is essay_project_delete
