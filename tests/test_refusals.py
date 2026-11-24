"""Every spoken refusal names a next step, and a fallback leaves a metadata line."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from helpers import open_sequence

from essay_writer.cite_open import _record_blank_pages
from essay_writer.incident import incident_path, note
from essay_writer.paths import work_dir
from essay_writer.stage_state import load_pointer
from essay_writer.word import WORD_TITLE_SPARE, document_title

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "essay_writer"
DOC = ROOT / "docs" / "refusals.md"
CUES = (
    "ask",
    "add",
    "say",
    "open",
    "save",
    "try",
    "show",
    "name",
    "pick",
    "choose",
    "write",
    "send",
    "upload",
    "confirm",
    "give",
    "omit",
    "revise",
)


def _refuse_calls():
    found = []
    for path in SRC.rglob("*.py"):
        if "_vendor" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "refuse" or not node.args:
                continue
            code = node.args[0]
            if not isinstance(code, ast.Constant) or not isinstance(code.value, str):
                continue
            found.append((path, node))
    return found


def test_every_refusal_code_is_in_the_table() -> None:
    text = DOC.read_text(encoding="utf-8")
    missing = sorted(
        {
            node.args[0].value
            for _path, node in _refuse_calls()
            if f"| {node.args[0].value} |" not in text
        }
    )
    assert missing == []


def test_a_literal_refusal_names_a_next_step() -> None:
    bare = []
    for path, node in _refuse_calls():
        reason = node.args[1] if len(node.args) > 1 else None
        if not isinstance(reason, ast.Constant) or not isinstance(reason.value, str):
            continue
        keys = {kw.arg for kw in node.keywords}
        words = re.compile(r"\b(" + "|".join(CUES) + r")\b")
        if "next" in keys or words.search(reason.value.casefold()):
            continue
        bare.append(f"{path.name}:{node.lineno}")
    assert bare == []


def test_model_contract_constants_have_a_test() -> None:
    tests = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py")
    )
    assert "MISSING_QUESTION" in tests
    assert "VERDICT_SHAPE" in tests


def test_a_fallback_is_recorded_with_debug_off(workspace, monkeypatch) -> None:
    monkeypatch.delenv("ESSAY_WRITER_DEBUG", raising=False)
    title = document_title("x" * 300)
    assert title == WORD_TITLE_SPARE
    lines = incident_path().read_text(encoding="utf-8").splitlines()
    recorded = [json.loads(line) for line in lines]
    match = [row for row in recorded if row.get("code") == "word-title-spare"]
    assert match
    assert match[0]["disposition"] == "fallback"
    assert match[0]["severity"] == "info"
    assert match[0]["stage"] == "title"
    assert match[0]["tool"] == "word"
    assert match[0]["message"] == ""
    assert "essay" not in incident_path().read_text(encoding="utf-8").casefold()


def test_a_non_utf8_pointer_is_not_rewritten(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\n")
    loaded = load_pointer(seq)
    assert loaded["current"] == "1"
    assert path.read_bytes() == b"\xff\n"
    codes = [
        json.loads(line)["code"]
        for line in incident_path().read_text(encoding="utf-8").splitlines()
    ]
    assert "pointer-damaged" in codes


def test_a_damaged_pointer_is_not_rewritten(workspace) -> None:
    seq = open_sequence()
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    loaded = load_pointer(seq)
    assert loaded["current"] == "1"
    assert path.read_text(encoding="utf-8") == "{not json"
    codes = [
        json.loads(line)["code"]
        for line in incident_path().read_text(encoding="utf-8").splitlines()
    ]
    assert "pointer-damaged" in codes


def test_an_unwritten_gap_keeps_the_pages(workspace, monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise OSError("gap file")

    monkeypatch.setattr("essay_writer.cite_open.record_read_gaps", fail)
    paper = workspace / "paper.pdf"
    fresh = _record_blank_pages(paper, ["", "kept"], [])
    assert fresh and fresh[0]["part"] == 1
    codes = [
        json.loads(line)["code"]
        for line in incident_path().read_text(encoding="utf-8").splitlines()
    ]
    assert "pdf-gap-unwritten" in codes


def test_a_bad_incident_line_does_not_stop_the_student(workspace) -> None:
    path = incident_path()
    path.write_bytes(b"\xff\n")
    note("word-title-spare", severity="info", disposition="fallback", tool="word", step="title")
    assert b"word-title-spare" in path.read_bytes()


def test_the_same_code_is_not_written_twice(workspace) -> None:
    note("word-title-spare", severity="info", disposition="fallback", tool="word", step="title")
    note("word-title-spare", severity="info", disposition="fallback", tool="word", step="title")
    lines = incident_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_a_bare_exception_pass_names_its_reason() -> None:
    bare = []
    for path in SRC.rglob("*.py"):
        if "_vendor" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if line.strip() != "except Exception:":
                continue
            body = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if body != "pass":
                continue
            window = "\n".join(lines[max(0, index - 2) : index + 2])
            if "#" not in window:
                bare.append(f"{path.name}:{index + 1}")
    assert bare == []
