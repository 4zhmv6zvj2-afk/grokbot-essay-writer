"""Confirm pins the parent tree, latest.docx, and delete contents."""

from helpers import picked
from test_projects import MODULE, _confirm_new, _docx

from essay_writer.intake import essay_intake
from essay_writer.paths import kb1_sequence_dir, sequence_dir, uploads_dir
from essay_writer.projects import (
    essay_project_delete,
    essay_sequence_new,
    save_sequence_state,
)


def test_sequence_new_refuses_when_the_parent_tree_drifts(workspace):
    assert _confirm_new()["sequence_id"] == f"{MODULE}-1"
    note = kb1_sequence_dir(MODULE, 1) / "essay.md"
    note.parent.mkdir(parents=True)
    note.write_text("before\n", encoding="utf-8")
    draft = essay_sequence_new(MODULE, "draft")
    assert draft["wrote"] is False
    assert draft["sequence_id"] == f"{MODULE}-2"
    note.write_text("after\n", encoding="utf-8")
    refused = essay_sequence_new(MODULE, "confirm")
    assert refused["ok"] is False
    assert refused["refused"] == "confirm"
    assert not sequence_dir(MODULE, 2).exists()
    assert note.read_text(encoding="utf-8") == "after\n"


def test_delete_pin_covers_a_file_added_under_uploads(workspace):
    _confirm_new()
    upload = uploads_dir(MODULE) / "paper.md"
    upload.parent.mkdir(parents=True)
    upload.write_text("first\n", encoding="utf-8")
    draft = essay_project_delete(MODULE, "draft")
    assert draft["wrote"] is False
    assert any(item["path"] == "paper.md" for item in draft["uploads"])
    extra = uploads_dir(MODULE) / "added.md"
    extra.write_text("later\n", encoding="utf-8")
    refused = essay_project_delete(MODULE, "confirm")
    assert refused["ok"] is False
    assert extra.is_file()
    assert upload.is_file()
    fresh = essay_project_delete(MODULE, "draft")
    deleted = essay_project_delete(MODULE, "confirm", **picked(fresh))
    assert deleted["deleted"] is True
    assert not uploads_dir(MODULE).exists()


def test_intake_locks_the_latest_docx_used_for_comparison(workspace):
    _confirm_new()
    output = sequence_dir(MODULE, 1) / "output" / f"{MODULE}-1.docx"
    original = [
        "The port handles containers.",
        "Reference List",
        "Smith, A. (2020) Port pricing. Journal of Ports.",
    ]
    _docx(output, original, headings=["Findings"])
    save_sequence_state(
        MODULE,
        1,
        {
            "essay_id": MODULE,
            "sequence": 1,
            "sequence_id": f"{MODULE}-1",
            "research": {"summary": {"sources": [{"id": "src-1", "title": "Port pricing"}]}, "full": None},
            "validations": {},
            "word": {},
            "revisions": [],
            "shelf": {},
        },
    )
    incoming = workspace / "unassigned" / "draft.docx"
    _docx(
        incoming,
        [
            "The port handles containers and barges.",
            "Reference List",
            "Smith, A. (2020) Port pricing. Journal of Ports.",
        ],
        headings=["Findings", "Barges"],
    )
    draft = essay_intake("draft.docx", "draft", MODULE)
    assert draft["kind"] == "output"
    assert draft["wrote"] is False
    _docx(output, ["A different latest file."], headings=["Other"])
    refused = essay_intake("draft.docx", "confirm", MODULE)
    assert refused["ok"] is False
    assert refused["refused"] == "confirm"
    assert not sequence_dir(MODULE, 2).exists()
    assert incoming.is_file()
