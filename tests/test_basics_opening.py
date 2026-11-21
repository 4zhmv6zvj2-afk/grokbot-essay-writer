"""One reader for the Basics opening. Each ask loads it once."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from helpers import ESSAY, open_sequence

from essay_writer import assignment_gate
from essay_writer.build_office import stage_launch
from essay_writer.build_status import basis_for
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.paths import essay_dir
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists import grok_bot
from essay_writer.specialists.eqr import build_findings
from essay_writer.specialists.grok_bot import (
    basics_pass_block,
    maybe_seed_basics_on_draft,
    read_basics_opening,
    remember_approved_look,
)
from essay_writer.stage_body import look_is_confirmable
from essay_writer.stage_hold import _opening_look
from essay_writer.stage_landing import _collect_stage_misses
from essay_writer.stage_state import _note_path
from essay_writer.stage_track import essay_stage

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"
QUESTION_A = "How should the firm manage the corridor?"
QUESTION_B = "Should the council publish the recycling figure?"
READER_CALLS = frozenset(
    {
        "read_basics_opening",
        "maybe_seed_basics_on_draft",
        "basics_pass_block",
        "seed_basics_look",
        "basics_pass_lines",
        "standard_opening",
        "attach_basics_pass",
        "_guidance_pieces",
        "look_is_confirmable",
        "_attach_stage_reports",
        "_opening_look",
        "build_findings",
        "basis_for",
    }
)
OUTSIDE = frozenset(
    {
        "maybe_seed_basics_on_draft",
        "seed_basics_look",
        "basics_pass_block",
    }
)


def _brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _report(question: str, *, sections: bool = False) -> str:
    lines = [f"Genre: report\nQuestion: {question}\n"]
    if sections:
        lines.append("\nSections:\n- Purpose\n- Evidence\n")
    return "".join(lines)


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def _calls_read_assignment(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Attribute) and func.attr == "read_assignment":
            return True
        if isinstance(func, ast.Name) and func.id == "read_assignment":
            return True
    return False


def _call_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _owner() -> str:
    for frame in inspect.stack():
        if frame.function in READER_CALLS and frame.function != "read_basics_opening":
            return frame.function
    return "other"


def _miss_codes(body: dict[str, object]) -> list[str]:
    if body.get("refused") == "misses":
        found = body.get("misses")
        if isinstance(found, list):
            return [str(item.get("code")) for item in found if isinstance(item, dict)]
    refused = body.get("refused")
    return [str(refused)] if isinstance(refused, str) else []


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-basics-1", id="AC-ew-basics-1")],
)
def test_one_reader_loads_once_per_ask(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-basics-1: one reader and the once-per-ask load rule hold."""
    assert case_id == "AC-ew-basics-1"
    del workspace
    bot = PACKAGE / "specialists" / "grok_bot.py"
    tree = ast.parse(bot.read_text(encoding="utf-8"))
    readers = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and _calls_read_assignment(node)
    }
    assert readers == {"read_basics_opening"}
    defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"maybe_seed_basics_on_draft", "seed_basics_look", "basics_pass_block"} <= defined
    reader = _function(bot, "read_basics_opening")
    assert reader.decorator_list == []

    _brief(ESSAY, _report(QUESTION_A))
    seq = open_sequence()
    loads: list[str] = []
    real_read = assignment_gate.read_assignment

    def spy_read(essay_id: str) -> dict[str, object]:
        record = real_read(essay_id)
        if "read_basics_opening" in {frame.function for frame in inspect.stack()}:
            question = record.get("question")
            loads.append(question if isinstance(question, str) else "")
        return record

    monkeypatch.setattr(assignment_gate, "read_assignment", spy_read)
    text, seeded, opening = maybe_seed_basics_on_draft(
        seq,
        "1",
        "draft",
        "The corridor is the case.",
        minting=False,
    )
    assert seeded is True
    assert opening is not None and opening.active is True
    assert opening.lines[2] == f"Question: {QUESTION_A}"
    assert loads == [QUESTION_A]
    assert "\n".join(opening.lines) in text

    _brief(ESSAY, _report(QUESTION_B))
    refused = basics_pass_block(seq, "The corridor is the case.")
    assert refused is not None
    assert loads == [QUESTION_A, QUESTION_B]
    passed = refused.get("basics_pass")
    assert isinstance(passed, list)
    assert passed[2] == f"Question: {QUESTION_B}"

    loads.clear()
    owners: list[str] = []
    real_open = read_basics_opening

    def spy_open(essay_id: str):
        owners.append(_owner())
        return real_open(essay_id)

    monkeypatch.setattr(grok_bot, "read_basics_opening", spy_open)
    draft = essay_stage(seq, "1", "draft", "The corridor is the case.")
    assert draft["ok"] is True, draft
    assert owners == ["maybe_seed_basics_on_draft", "basics_pass_block"]
    assert loads == [QUESTION_B, QUESTION_B]


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-basics-2", id="AC-ew-basics-2")],
)
def test_draft_body_reuses_the_one_brief_read(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-basics-2: draft body build has one brief read, reused by the reply field and in-build guidance."""
    assert case_id == "AC-ew-basics-2"
    del workspace
    _brief(ESSAY, _report(QUESTION_A))
    seq = open_sequence()
    expected = read_basics_opening(seq).lines
    owners: list[str] = []
    captured: dict[str, tuple[str, str, str]] = {}
    seen: list[tuple[str, str, str] | None] = []
    real_open = read_basics_opening
    real_look = look_is_confirmable

    def spy_open(essay_id: str):
        owner = _owner()
        owners.append(owner)
        opening = real_open(essay_id)
        if owner == "maybe_seed_basics_on_draft":
            captured["lines"] = opening.lines
        return opening

    def spy_look(
        essay_id: str,
        stage: str,
        genre: str | None,
        text: str,
        lines: tuple[str, str, str] | None = None,
    ) -> bool:
        seen.append(lines)
        return real_look(essay_id, stage, genre, text, lines)

    monkeypatch.setattr(grok_bot, "read_basics_opening", spy_open)
    monkeypatch.setattr("essay_writer.stage_body.look_is_confirmable", spy_look)

    quiet = essay_stage(seq, "1", "draft", "\n".join(expected))
    assert quiet["refused"] == "guidance-only"
    assert owners == ["maybe_seed_basics_on_draft"]
    assert seen == [captured["lines"]]
    assert seen[0] == expected

    owners.clear()
    captured.clear()
    seen.clear()
    draft = essay_stage(seq, "1", "draft", "The corridor is the case.")
    assert draft["ok"] is True, draft
    assert draft.get("basics_seeded") is True
    assert owners.count("maybe_seed_basics_on_draft") == 1
    assert owners.count("basics_pass_block") == 1
    assert "look_is_confirmable" not in owners
    assert "_guidance_pieces" not in owners
    assert "attach_basics_pass" not in owners
    assert "_attach_stage_reports" not in owners
    assert seen == [captured["lines"]]
    assert draft["basics_pass"] == list(captured["lines"])
    assert HANDLERS["essay.stage"] is essay_stage
    assert cursor_shell()["handlers"]["essay.stage"] is essay_stage
    assert front_office()["handlers"]["essay.stage"] is essay_stage
    assert "basics_pass" not in (PACKAGE / "build_office.py").read_text(encoding="utf-8")
    assert "basics_pass" not in (PACKAGE / "cursor_office.py").read_text(encoding="utf-8")
    assert stage_launch("1")["source"] == cursor_stage_launch("1")["source"]


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-basics-3", id="AC-ew-basics-3")],
)
def test_miss_collector_refuses_once_on_its_own_ask(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-basics-3: miss collector is a separate ask, refusal once, student note unchanged, slot order as locked, stage 5 skips the refusal."""
    assert case_id == "AC-ew-basics-3"
    del workspace
    _brief(ESSAY, _report(QUESTION_A, sections=True))
    seq = open_sequence()
    refused_notes: list[str] = []
    seed_calls: list[str] = []
    real_block = basics_pass_block
    real_seed = maybe_seed_basics_on_draft

    def spy_block(essay_id: str, text: str):
        refused_notes.append(text)
        return real_block(essay_id, text)

    def spy_seed(*args: object, **kwargs: object):
        seed_calls.append("seed")
        return real_seed(*args, **kwargs)

    monkeypatch.setattr(grok_bot, "basics_pass_block", spy_block)
    monkeypatch.setattr(grok_bot, "maybe_seed_basics_on_draft", spy_seed)
    pointer = {"current": "1"}

    file_only = "annotation.docx"
    file_body, _gate = _collect_stage_misses(seq, "1", "draft", file_only, pointer, minting=False)
    assert file_body is not None
    assert refused_notes == [file_only]
    assert refused_notes[0] is file_only
    assert seed_calls == []
    assert _miss_codes(file_body) == ["basics-pass", "assignment-gate"]

    refused_notes.clear()
    plain = "The corridor needs a longer plan."
    plain_body, _gate = _collect_stage_misses(seq, "1", "draft", plain, pointer, minting=False)
    assert plain_body is not None
    assert refused_notes == [plain]
    assert refused_notes[0] is plain
    assert _miss_codes(plain_body) == ["assignment-gate", "basics-pass"]

    refused_notes.clear()
    wording = "The smoke is not part of the plan."
    stage_three, _gate = _collect_stage_misses(
        seq, "3", "draft", wording, {"current": "3"}, minting=False
    )
    assert stage_three is not None
    assert refused_notes == [wording]
    misses = stage_three.get("misses")
    assert isinstance(misses, list)
    reasons = [str(item.get("reason")) for item in misses if isinstance(item, dict)]
    assert reasons[0].startswith("That note uses an internal label")
    assert reasons[1].startswith("The brief names these parts")
    codes = _miss_codes(stage_three)
    assert codes.index("assignment-gate") < codes.index("basics-pass")
    assert codes.index("basics-pass") > 1

    refused_notes.clear()
    named_file, _gate = _collect_stage_misses(
        seq, "3", "draft", file_only, {"current": "3"}, minting=False
    )
    assert named_file is not None
    assert refused_notes == [file_only]
    named_codes = _miss_codes(named_file)
    assert named_codes[0] != "basics-pass"
    assert "The brief names these parts" in str(named_file.get("reason"))
    assert named_codes.index("basics-pass") < named_codes.index("assignment-gate")

    refused_notes.clear()
    stage_five, _gate = _collect_stage_misses(
        seq, "5", "draft", file_only, {"current": "5"}, minting=False
    )
    assert refused_notes == []
    assert seed_calls == []
    if isinstance(stage_five, dict):
        assert "basics-pass" not in _miss_codes(stage_five)
        assert stage_five.get("refused") != "basics-pass"

    wrong = "\n".join(
        (
            "The mark scheme scores the wrong band.",
            "Format: report.",
            f"Question: {QUESTION_A}",
            "The corridor is the case.",
        )
    )
    refused_notes.clear()
    blocked = essay_stage(seq, "1", "draft", wrong)
    assert blocked["ok"] is False
    assert blocked.get("basics_seeded") is not True
    assert refused_notes == [wrong]
    assert not _note_path(seq, "1").exists()


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-basics-4", id="AC-ew-basics-4")],
)
def test_opener_findings_and_status_stay_outside(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-basics-4: next-card opener, findings note, and status line stay outside the seed and the refusal as locked."""
    assert case_id == "AC-ew-basics-4"
    del workspace
    opener = _function(PACKAGE / "stage_hold.py", "_opening_look")
    findings = _function(PACKAGE / "specialists" / "eqr.py", "build_findings")
    clears = _function(PACKAGE / "specialists" / "eqr.py", "findings_note_clears")
    status = _function(PACKAGE / "build_status.py", "basis_for")
    opener_calls = _call_names(opener)
    assert "cached_approved_look" in opener_calls
    assert "attach_basics_pass" in opener_calls
    assert opener_calls.isdisjoint(OUTSIDE)
    assert _call_names(findings).isdisjoint(OUTSIDE)
    assert "basics_pass_lines" in _call_names(findings)
    assert _call_names(clears).isdisjoint(OUTSIDE)
    assert "standard_opening" in _call_names(clears)
    assert _call_names(status).isdisjoint(OUTSIDE)
    assert "standard_opening" in _call_names(status)
    cached_at = attach_at = None
    for node in ast.walk(opener):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "cached_approved_look":
            cached_at = node.lineno
        if node.func.id == "attach_basics_pass":
            attach_at = node.lineno
    assert cached_at is not None and attach_at is not None
    assert cached_at < attach_at

    bare = open_sequence("RPT7001AA")
    _brief(ESSAY, _report(QUESTION_A))
    seq = open_sequence()
    module = "RPT7002AA"
    _brief(module, _report(QUESTION_A))
    scheme = essay_dir(module) / "mark-scheme.md"
    scheme.write_text(
        "High Distinction (80-100): the question is answered with evidence\n",
        encoding="utf-8",
    )
    marked = open_sequence(module)
    lines = read_basics_opening(seq).lines

    loads: list[str] = []
    outside: list[str] = []
    real_open = read_basics_opening
    real_seed = maybe_seed_basics_on_draft
    real_block = basics_pass_block

    def spy_open(essay_id: str):
        loads.append(_owner())
        return real_open(essay_id)

    def spy_seed(*args: object, **kwargs: object):
        outside.append("seed")
        return real_seed(*args, **kwargs)

    def spy_block(*args: object, **kwargs: object):
        outside.append("refusal")
        return real_block(*args, **kwargs)

    monkeypatch.setattr(grok_bot, "read_basics_opening", spy_open)
    monkeypatch.setattr(grok_bot, "maybe_seed_basics_on_draft", spy_seed)
    monkeypatch.setattr(grok_bot, "basics_pass_block", spy_block)

    assert _opening_look(bare) == ""
    assert _opening_look(seq) == "\n".join(lines)
    assert loads == ["attach_basics_pass", "attach_basics_pass"]
    assert outside == []

    remember_approved_look(seq, "Cached approved look with a student sentence.")
    assert _opening_look(seq) == "Cached approved look with a student sentence."
    assert loads == ["attach_basics_pass", "attach_basics_pass"]
    assert outside == []

    note = build_findings(marked, {"text": "A report about the corridor."}, {})
    from essay_writer.specialists.grok_bot import standard_opening

    scores = standard_opening(marked)
    assert scores in note
    assert basis_for(marked) == scores.strip()
    assert outside == []
