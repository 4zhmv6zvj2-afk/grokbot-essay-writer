"""One JSON record store: tolerant read, guarded writer-unique atomic write."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from essay_writer.known_paths import RepoSaveRefused
from essay_writer.records import read_json, write_json

REPO = Path(__file__).resolve().parents[1]


def _temporaries(folder: Path, name: str) -> list[Path]:
    return sorted(folder.glob(f".{name}.*.tmp"))


def test_read_json_tolerates_missing_corrupt_and_non_object_files(tmp_path):
    path = tmp_path / "record.json"
    assert read_json(path) is None
    assert read_json(path, default={}) == {}
    path.write_text("{", encoding="utf-8")
    assert read_json(path, default={"kept": True}) == {"kept": True}
    path.write_text("[1, 2]", encoding="utf-8")
    assert read_json(path, default=None) is None
    path.write_text('{"ok": true}', encoding="utf-8")
    assert read_json(path) == {"ok": True}


def test_read_json_treats_a_record_that_fails_validation_as_absent(tmp_path):
    path = tmp_path / "record.json"
    path.write_text('{"papers": "not a list"}', encoding="utf-8")
    assert read_json(path, default={}, validate=lambda data: isinstance(data.get("papers"), list)) == {}
    path.write_text('{"papers": []}', encoding="utf-8")
    assert read_json(path, default={}, validate=lambda data: isinstance(data.get("papers"), list)) == {
        "papers": []
    }


def test_write_json_writes_one_complete_record_and_no_fixed_temp(tmp_path):
    path = tmp_path / "nested" / "record.json"
    write_json(path, {"essay_id": "MOD1004AA-1", "ok": True}, mkdir=True)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "essay_id": "MOD1004AA-1",
        "ok": True,
    }
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert _temporaries(path.parent, path.name) == []
    assert not (tmp_path / "nested" / "record.json.tmp").exists()


def test_write_json_removes_its_temp_when_the_replace_fails(tmp_path):
    target = tmp_path / "record.json"
    target.mkdir()
    with pytest.raises(OSError):
        write_json(target, {"ok": True})
    assert _temporaries(tmp_path, target.name) == []


def test_write_json_refuses_the_code_checkout(tmp_path):
    target = REPO / "src" / "essay_writer" / "record-probe.json"
    with pytest.raises(RepoSaveRefused):
        write_json(target, {"ok": True}, mkdir=True)
    assert not target.exists()


def test_two_writers_to_one_record_leave_one_complete_file(tmp_path):
    """Writer-unique temps: concurrent writes never splice or corrupt the record."""
    path = tmp_path / "shared.json"
    sides = {
        "a": [{"writer": "a", "filler": "a" * 4000, "n": index} for index in range(40)],
        "b": [{"writer": "b", "filler": "b" * 4000, "n": index} for index in range(40)],
    }
    payloads = sides["a"] + sides["b"]
    start = threading.Event()

    def write_side(records: list[dict[str, object]]) -> None:
        start.wait()
        for record in records:
            write_json(path, record, mkdir=True)

    threads = [
        threading.Thread(target=write_side, args=(records,)) for records in sides.values()
    ]
    for thread in threads:
        thread.start()
    start.set()
    for thread in threads:
        thread.join()

    assert _temporaries(tmp_path, path.name) == []
    final = json.loads(path.read_text(encoding="utf-8"))
    assert final in payloads
    assert final["filler"] == final["writer"] * 4000
