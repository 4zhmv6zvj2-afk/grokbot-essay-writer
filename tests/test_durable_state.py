"""A crash before replace leaves the previous state file, and a retry converges.

The public seams are replace_bytes, save_sequence_state, and load_pointer
after a stage confirm. A failed fsync or replace is injected. The expected
bytes are literals, not a second copy of the writer.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence

from essay_writer.durable import replace_bytes
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import load_sequence_state, save_sequence_state
from essay_writer.shells import mount_handler
from essay_writer.stage_state import load_pointer

OLD = b'{"kept": 1}\n'
NEW = b'{"kept": 2}\n'
LOOK = "The task is a short report on the corridor."


def _live(**kwargs):
    return mount_handler("essay.stage")(**kwargs)


def test_a_failed_replace_keeps_the_previous_bytes(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_bytes(OLD)

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="replace failed"):
        replace_bytes(path, NEW)
    assert path.read_bytes() == OLD
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_a_failed_fsync_keeps_the_previous_bytes(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_bytes(OLD)
    real = os.fsync
    calls = {"n": 0}

    def flaky(fd):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("fsync failed")
        return real(fd)

    monkeypatch.setattr(os, "fsync", flaky)
    with pytest.raises(OSError, match="fsync failed"):
        replace_bytes(path, NEW)
    assert path.read_bytes() == OLD


def test_a_second_write_of_the_same_bytes_leaves_one_file(tmp_path):
    path = tmp_path / "state.json"
    replace_bytes(path, NEW)
    replace_bytes(path, NEW)
    assert path.read_bytes() == NEW
    names = sorted(item.name for item in tmp_path.iterdir())
    assert names == ["state.json"]


def test_killing_the_writer_before_replace_keeps_the_previous_bytes(tmp_path):
    path = tmp_path / "state.json"
    path.write_bytes(OLD)
    ready = tmp_path / "ready"
    script = """
import os, sys, time
from pathlib import Path
path = Path(sys.argv[1])
ready = Path(sys.argv[2])
real = os.replace
def pause(src, dst):
    ready.write_text("ready", encoding="utf-8")
    time.sleep(30)
    real(src, dst)
os.replace = pause
from essay_writer.durable import replace_bytes
replace_bytes(path, b'{"kept": 2}\\n')
"""
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src = str(root / "src")
    previous = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src if not previous else src + os.pathsep + previous
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(path), str(ready)],
        cwd=root,
        env=env,
    )
    deadline = time.monotonic() + 10
    while not ready.exists():
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            raise AssertionError(f"writer exited {proc.returncode} before replace")
        time.sleep(0.05)
    proc.kill()
    proc.wait(timeout=5)
    assert path.read_bytes() == OLD


def test_a_failed_replace_keeps_the_saved_sequence_state(workspace, monkeypatch):
    seq = open_sequence(ESSAY)
    module, _, number_text = seq.rpartition("-")
    number = int(number_text)
    state_path = work_dir(seq) / "state.json"
    before = state_path.read_text(encoding="utf-8")
    assert "p91-sentinel" not in before

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    state = load_sequence_state(module, number)
    state["p91"] = "sentinel"
    with pytest.raises(OSError, match="replace failed"):
        save_sequence_state(module, number, state)
    assert state_path.read_text(encoding="utf-8") == before
    loaded = load_sequence_state(module, number)
    assert loaded.get("p91") != "sentinel"


def test_a_crash_between_the_note_and_the_pointer_loads_one_pair(workspace, monkeypatch):
    """The next load finishes the journal, so the note and the pointer match."""
    seq = open_sequence(ESSAY)
    folder = work_dir(seq)
    brief = essay_dir(seq) / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("Assignment task: Name the corridor.\n", encoding="utf-8")
    draft = _live(essay_id=seq, stage="1", confirmPhase="draft", look=LOOK)
    assert draft["ok"] is True, draft
    real = os.replace

    def boom(src, dst):
        if str(dst).endswith(f"{os.sep}stage.json"):
            raise OSError("pointer replace failed")
        real(src, dst)

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="pointer replace failed"):
        _live(
            essay_id=seq,
            stage="1",
            confirmPhase="confirm",
            cardAction="confirm",
            cardDigest=draft["cardDigest"],
        )
    monkeypatch.setattr(os, "replace", real)
    pointer = load_pointer(seq)
    note = (folder / "tracking" / "1.md").read_text(encoding="utf-8")
    assert pointer["current"] == "2"
    assert LOOK in note
    assert not (folder / "tracking" / ".stage.commit").exists()


def test_a_failed_mac_copy_keeps_the_previous_deliverable(tmp_path, monkeypatch):
    from essay_writer.first_run_mac import copy_deliverable_to_mac

    mac = tmp_path / "mac"
    mac.mkdir()
    source = tmp_path / "essay.docx"
    source.write_bytes(b"NEW-DELIVERABLE")
    previous = mac / "essay.docx"
    previous.write_bytes(b"PREVIOUS-DELIVERABLE")

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    reply = copy_deliverable_to_mac(source, mac_dir=mac)
    assert reply["ok"] is False
    assert previous.read_bytes() == b"PREVIOUS-DELIVERABLE"
    assert list(mac.glob(".essay.docx.*.tmp")) == []


def test_a_failed_brief_rollback_does_not_leave_a_partial_file(tmp_path, monkeypatch):
    from essay_writer.assignment_gate import _rollback_brief_meta

    path = tmp_path / "answer.json"
    path.write_bytes(b'{"brief_sha256": "bad"}\n')
    kept = b'{"brief_sha256": "kept"}\n'

    def boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", boom)
    _rollback_brief_meta(path, kept)
    assert not path.exists()
    assert list(tmp_path.glob(".answer.json.*.tmp")) == []
