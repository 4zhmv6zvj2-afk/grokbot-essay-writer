"""The always-on incident record, its rotation, and the support bundle."""

from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from pathlib import Path

import pytest

from essay_writer.confirm import refuse
from essay_writer.debug_log import essay_debug_wipe, support_bundle, traced
from essay_writer.incident import (
    ALLOWED_MESSAGES,
    FILENAME,
    incident_path,
    note,
    rotated_path,
)
from essay_writer.paths import workspace_root
from essay_writer.server import main

ROOT = Path(__file__).resolve().parents[1]
ESSAY = "The fisheries opening stayed on the page."
SECRET = "consensus-value-aaa"
EMAIL = "reader@example.com"


def _rows() -> list[dict]:
    path = incident_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _plant(code: str, *, step: str = "title") -> None:
    note(code, severity="info", disposition="fallback", tool="word", step=step)


def test_the_record_lives_in_the_app_folder_at_mode_0600(workspace) -> None:
    _plant("word-title-spare")
    path = incident_path()
    assert path == workspace_root() / FILENAME
    assert path.parent == workspace
    assert path.stat().st_mode & 0o777 == 0o600


def test_an_existing_record_is_tightened_to_0600(workspace) -> None:
    path = incident_path()
    path.write_text("", encoding="utf-8")
    path.chmod(0o644)
    _plant("word-title-spare")
    assert path.stat().st_mode & 0o777 == 0o600


def test_a_refusal_is_recorded_with_debug_off(workspace, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    reason = "Say what you want cleared, such as delete the logs or clear debug log."
    body = refuse("debug-wipe", reason, next="Ask again with delete the logs, or clear debug log.")
    assert body["ok"] is False
    assert body["reason"] == reason
    row = _rows()[-1]
    assert row["code"] == "debug-wipe"
    assert row["severity"] == "error"
    assert row["disposition"] == "refuse"
    assert row["message"] == ""
    assert reason not in incident_path().read_text(encoding="utf-8")


def test_an_exception_keeps_the_class_and_drops_the_message(workspace, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    monkeypatch.setenv("ESSAY_WRITER_BUILD", "build-p910")
    from essay_writer import incident

    incident._CACHE.pop("build", None)

    def handler(essay_id: str, stage: str) -> None:
        raise RuntimeError(f"{ESSAY} {EMAIL} {SECRET}")

    with pytest.raises(RuntimeError, match="fisheries"):
        traced("essay.health", handler)("MOD1004AA-1", "3")
    row = _rows()[-1]
    text = incident_path().read_text(encoding="utf-8")
    assert row["code"] == "unhandled"
    assert row["exc"] == "RuntimeError"
    assert row["message"] == ""
    assert row["tool"] == "essay.health"
    assert row["stage"] == "3"
    assert row["sequence"] == "MOD1004AA-1"
    assert row["build"] == "build-p910"
    assert ESSAY not in text
    assert EMAIL not in text
    assert SECRET not in text


def test_an_allowlisted_exception_message_is_kept(workspace) -> None:
    message = next(iter(ALLOWED_MESSAGES))

    def handler() -> None:
        raise RuntimeError(message)

    with pytest.raises(RuntimeError, match="Windows"):
        traced("essay.health", handler)()
    row = _rows()[-1]
    assert row["exc"] == "RuntimeError"
    assert row["code"] == "unhandled"
    assert row["message"] == message


def test_the_same_code_is_one_line_per_call(workspace) -> None:
    def handler() -> dict:
        note(
            "page-cursor-repeat",
            severity="warn",
            disposition="fallback",
            tool="read",
            step="page",
        )
        note(
            "page-cursor-repeat",
            severity="warn",
            disposition="fallback",
            tool="read",
            step="page",
        )
        return {"ok": True, "kept": "answer"}

    assert traced("essay.dig", handler)()["kept"] == "answer"
    assert len(_rows()) == 1
    traced("essay.dig", handler)()
    assert len(_rows()) == 2


def test_the_two_hundredth_line_rotates(workspace) -> None:
    for index in range(200):
        _plant(f"row-{index}")
    assert rotated_path().is_file() is False
    _plant("row-200")
    assert len(rotated_path().read_text(encoding="utf-8").splitlines()) == 200
    assert [row["code"] for row in _rows()] == ["row-200"]
    assert rotated_path().stat().st_mode & 0o777 == 0o600


def test_a_byte_cap_rotates(workspace, monkeypatch) -> None:
    from essay_writer import incident

    monkeypatch.setattr(incident, "MAX_BYTES", 80)
    monkeypatch.setattr(incident, "MAX_LINES", 1000)
    _plant("byte-one")
    _plant("byte-two")
    assert "byte-one" in rotated_path().read_text(encoding="utf-8")
    assert [row["code"] for row in _rows()] == ["byte-two"]


def test_concurrent_appends_do_not_drop_a_line(workspace, monkeypatch) -> None:
    from essay_writer import incident

    monkeypatch.setattr(incident, "MAX_LINES", 15)
    for index in range(15):
        _plant(f"old-{index}")
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            note(
                f"new-{index}",
                severity="warn",
                disposition="retry",
                tool="read",
                step="fetch",
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    kept = {
        json.loads(line)["code"]
        for path in (incident_path(), rotated_path())
        if path.is_file()
        for line in path.read_text(encoding="utf-8").splitlines()
    }
    assert kept == {f"old-{index}" for index in range(15)} | {f"new-{index}" for index in range(8)}


def test_wipe_removes_the_record_and_the_rotated_file(workspace, monkeypatch) -> None:
    from essay_writer import incident

    monkeypatch.setattr(incident, "MAX_LINES", 1)
    _plant("row-0")
    _plant("row-1")
    assert incident_path().is_file()
    assert rotated_path().is_file()
    wiped = essay_debug_wipe("delete the logs")
    assert wiped["ok"] is True
    assert wiped["cleared_incident"] is True
    assert incident_path().is_file() is False
    assert rotated_path().is_file() is False


def test_a_logging_failure_does_not_stop_the_student(workspace, monkeypatch) -> None:
    from essay_writer import incident
    from essay_writer.word import WORD_TITLE_SPARE, document_title

    def boom(_path, _data):
        raise OSError("full")

    monkeypatch.setattr(incident, "_append_bytes", boom)
    assert document_title("x" * 300) == WORD_TITLE_SPARE


def test_the_bundle_names_the_failure_and_hides_the_essay(workspace, monkeypatch) -> None:
    monkeypatch.setenv("ESSAY_WRITER_BUILD", "build-p910")
    from essay_writer import incident

    incident._CACHE.pop("build", None)
    note(
        "read-bad-json",
        severity="warn",
        disposition="fallback",
        tool="read",
        step="json",
    )

    def handler(essay_id: str, stage: str) -> None:
        raise RuntimeError(f"{ESSAY} {EMAIL} token={SECRET} /Users/student/essay.txt")

    with pytest.raises(RuntimeError):
        traced("essay.pack.render_word", handler)("MOD1004AA-1", "4")
    state = workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "state.json"
    state.parent.mkdir(parents=True)
    body = f'{{"look": "{ESSAY}"}}\n'.encode()
    state.write_bytes(body)
    pointer = state.parent / "tracking" / "stage.json"
    pointer.parent.mkdir()
    pointer.write_text("{}\n", encoding="utf-8")
    exported = support_bundle()
    assert exported["ok"] is True
    assert exported["name"] == "support.zip"
    archive = workspace / "support.zip"
    with zipfile.ZipFile(archive) as zip_file:
        names = set(zip_file.namelist())
        blob = b"\n".join(zip_file.read(name) for name in zip_file.namelist())
        manifest = json.loads(zip_file.read("manifest.json"))
        files = json.loads(zip_file.read("files.json"))
        health = json.loads(zip_file.read("health.json"))
        record = zip_file.read("incident.jsonl").decode("utf-8")
    assert {"incident.jsonl", "health.json", "files.json", "manifest.json"} <= names
    assert "debug.log" not in names
    assert manifest["soft"]["read-bad-json"] == 1
    assert health["build"] == "build-p910"
    assert "essay.health" in health["doors"]
    assert ESSAY not in blob.decode("utf-8")
    assert EMAIL not in blob.decode("utf-8")
    assert SECRET not in blob.decode("utf-8")
    assert "/Users/" not in blob.decode("utf-8")
    assert str(workspace) not in blob.decode("utf-8")
    assert body.decode() not in blob.decode("utf-8")
    assert any(row["sequence"] == "MOD1004AA-1" for row in files)
    assert files[0]["state_sha256"] == hashlib.sha256(body).hexdigest()
    assert "pointer_sha256" in files[0]
    assert '"tool": "essay.pack.render_word"' in record
    assert '"stage": "4"' in record
    assert '"code": "unhandled"' in record
    assert '"build": "build-p910"' in record


def test_the_cli_writes_the_bundle(workspace, capsys) -> None:
    _plant("word-title-spare")
    main(["--support-bundle"])
    captured = capsys.readouterr()
    assert "support.zip" in captured.out
    assert (workspace / "support.zip").is_file()


def test_the_build_and_the_prompt_hash_are_read_once(workspace, monkeypatch) -> None:
    from essay_writer import incident

    incident._CACHE.clear()
    calls = {"build": 0, "prompt": 0}

    def build() -> str:
        calls["build"] += 1
        return "build-once"

    def prompt() -> str:
        calls["prompt"] += 1
        return "abc123def456"

    monkeypatch.setattr(incident, "_read_build", build)
    monkeypatch.setattr(incident, "_prompt_digest", prompt)
    try:
        _plant("cache-one")
        note("cache-two", severity="warn", disposition="fallback", tool="read", step="fetch")
        assert calls == {"build": 1, "prompt": 1}
        assert _rows()[0]["build"] == "build-once"
        assert _rows()[1]["prompt"] == "abc123def456"
    finally:
        incident._CACHE.clear()


def test_the_operator_doc_names_the_mode_and_the_dev_fallback() -> None:
    text = (ROOT / "docs" / "operator-log.md").read_text(encoding="utf-8")
    assert "mode 0600" in text
    assert "dev-only degradation" in text
    assert "incident.jsonl" in text
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "incident.jsonl" in ignored
    assert "incident.jsonl.1" in ignored
    assert "support.zip" in ignored
