"""Mac module + per-sequence Essay Bot folder. Stable ids: AC1–AC5.

Build covered: Cursor and Grok Build share ensure_sequence_mac_folder,
copy_deliverable_to_mac, and essay.stage Stage 1 Confirm.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from helpers import (
    ESSAY,
    mac_handoff_sequence_dir,
    open_sequence,
    picked,
    plant_gathered_source,
    write_upload,
)

from essay_writer.build_office import build_deliverable_handoff, stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.first_run import (
    copy_deliverable_to_mac,
    ensure_sequence_mac_folder,
    module_shared_mac_deliverables_dir,
    sequence_mac_deliverables_dir,
)
from essay_writer.stage_track import essay_stage

REPO = Path(__file__).resolve().parents[1]


def _essay_bot(tmp_path) -> Path:
    return tmp_path / "Documents" / "Essay Bot"


def test_ac1_stage_1_confirm_creates_module_essay_id_folder_when_mac_remembered(
    workspace, tmp_path, monkeypatch
):
    """AC1. Stage 1 Confirm creates Documents/Essay Bot/<module>/<essay_id>/."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The task is a report.")
    saved = essay_stage(seq, "1", "confirm", "The task is a report.", **picked(draft))
    assert saved["stored"] is True
    folder = mac_handoff_sequence_dir(bot, seq)
    assert folder.is_dir()
    record = saved.get("sequence_mac_folder")
    assert isinstance(record, dict)
    assert record.get("ok") is True
    assert record.get("remembered") is True
    assert record.get("path") == str(folder.resolve())
    assert sequence_mac_deliverables_dir(seq) == folder


def test_ac2_stage_1_confirm_creates_module_shared_folder(workspace, tmp_path, monkeypatch):
    """AC2. Stage 1 Confirm creates Documents/Essay Bot/<module>/shared/."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", "The task is a report.")
    saved = essay_stage(seq, "1", "confirm", "The task is a report.", **picked(draft))
    assert saved["stored"] is True
    shared = bot / ESSAY / "shared"
    assert shared.is_dir()
    record = saved.get("sequence_mac_folder")
    assert isinstance(record, dict)
    assert record.get("shared_path") == str(shared.resolve())
    assert module_shared_mac_deliverables_dir(seq) == shared
    assert (bot / ESSAY).is_dir()


def test_ac3_handoff_copies_into_sequence_folder_not_flat_bot(
    workspace, tmp_path, monkeypatch
):
    """AC3. Student Word and zip handoff copies into <module>/<essay_id>, not flat Essay Bot."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    seq = open_sequence()
    plant_gathered_source(seq)
    out = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "annotation.docx").write_bytes(b"ann")
    (out / "papers.zip").write_bytes(b"zip")
    copied = copy_deliverable_to_mac(out / "annotation.docx")
    assert copied["copied"] is True
    seq_folder = mac_handoff_sequence_dir(bot, seq)
    assert copied["path"] == str((seq_folder / "annotation.docx").resolve())
    assert not (bot / "annotation.docx").exists()
    assert not (bot / seq / "annotation.docx").exists()
    handoff = build_deliverable_handoff(out)
    assert handoff["copied"] is True
    assert (seq_folder / "papers.zip").is_file()


def test_ac4_two_sequences_do_not_overwrite_fixed_deliverable_names(
    workspace, tmp_path, monkeypatch
):
    """AC4. Two sequences keep separate annotation.docx copies under their essay_id folders."""
    bot = _essay_bot(tmp_path)
    bot.mkdir(parents=True)
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(bot))
    write_upload(workspace)
    seq1 = open_sequence()
    from essay_writer.projects import essay_sequence_new

    draft2 = essay_sequence_new(ESSAY, "draft")
    assert draft2["ok"] is True
    opened2 = essay_sequence_new(ESSAY, "confirm")
    seq2 = opened2["sequence_id"]
    assert seq2 != seq1
    from essay_writer.paths import sequence_number

    for seq, tag in ((seq1, b"one"), (seq2, b"two")):
        number = sequence_number(seq)
        out = workspace / "Essay-writer" / ESSAY / "sequences" / str(number) / "output"
        out.mkdir(parents=True, exist_ok=True)
        (out / "annotation.docx").write_bytes(tag)
        copy_deliverable_to_mac(out / "annotation.docx")
    first = (mac_handoff_sequence_dir(bot, seq1) / "annotation.docx").read_bytes()
    second = (mac_handoff_sequence_dir(bot, seq2) / "annotation.docx").read_bytes()
    assert first == b"one"
    assert second == b"two"


def test_ac5_build_covered_mac_copy_and_stage_1_confirm_path():
    """AC5. Mac copy and Stage 1 Confirm share one implementation slice."""
    from essay_writer import first_run
    from essay_writer.stage_track import essay_stage

    copy_src = inspect.getsource(copy_deliverable_to_mac)
    ensure_src = inspect.getsource(ensure_sequence_mac_folder)
    stage_src = inspect.getsource(essay_stage)
    assert "_mac_copy_folder" in copy_src or "sequence_mac_deliverables_dir" in copy_src
    assert "module_shared_mac_deliverables_dir" in ensure_src
    assert "ensure_sequence_mac_folder" in stage_src
    for fn in (stage_launch, cursor_stage_launch):
        source = inspect.getsource(fn)
        assert "ensure_sequence_mac_folder" not in source
        assert "choose_mac_handoff" not in source
    assert "module_mac_deliverables_dir" in inspect.getsource(first_run.sequence_mac_deliverables_dir)
