"""FO chat locks, per-sequence logs, land SHA, and gates ml-events.

Stable ids: AC1–AC17. Build covered: Cursor and Grok Build share HANDLERS.
"""

import inspect
import json
import subprocess
from pathlib import Path

from helpers import picked

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.debug_log import debug_log_path, land_sha, ml_events_path
from essay_writer.first_run import mac_deliverables_record
from essay_writer.fo_chat_locks import (
    FO_STAGES_ROLL_FORWARD,
    inherited_locks,
    prior_saved_lock_line,
)
from essay_writer.paths import essay_dir, sequence_dir, work_dir
from essay_writer.projects import essay_project_delete, essay_sequence_new
from essay_writer.roll_forward import load_record
from essay_writer.server import HANDLERS, INSTRUCTIONS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import stage_tool_description
from essay_writer.stage_track import essay_stage, load_pointer

MODULE = "RPT5001AA"
DIARY_BRIEF = """
Assignment title: Individual reflective diary
Module title: Practice module
Module code: RPT5001AA
Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.
One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.
Title page: module title, module code, assignment title, registration number, and the word count.
# Marking criteria/feedback form
| Criterion | 70+ |
| Clarity | exact |
"""
ENTRY_LOCK = (
    "North occasion: the firm chose the corridor route.\n"
    "South occasion: the team delayed the launch.\n"
    "East occasion: the budget was re-cut.\n"
    "West occasion: the client asked for proof."
)
REPO = Path(__file__).resolve().parents[1]


def _brief() -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(DIARY_BRIEF, encoding="utf-8")


def _look(seq: str, *extra: str) -> str:
    lines = list(basics_pass_lines(seq))
    lines.extend(extra)
    return "\n".join(lines)


def _save_stage(seq: str, stage: str, look: str) -> None:
    draft = essay_stage(seq, stage, "draft", look)
    assert draft["ok"] is True, draft
    essay_stage(seq, stage, "confirm", look, **picked(draft))


def _parent_with_stage2_lock() -> str:
    _brief()
    draft = essay_sequence_new(MODULE, "draft")
    assert draft["ok"] is True, draft
    parent = essay_sequence_new(MODULE, "confirm")["sequence_id"]
    _save_stage(parent, "1", _look(parent, "Task noted for the diary."))
    _save_stage(parent, "2", _look(parent, ENTRY_LOCK))
    return parent


def _child_from(parent: str) -> str:
    draft = essay_sequence_new(MODULE, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(MODULE, "confirm", parent)
    assert opened["ok"] is True, opened
    child = opened["sequence_id"]
    record = load_record(child)
    assert record is not None
    locks = record.get("inherited_locks") or []
    assert any(row.get("stage") == "2" and ENTRY_LOCK.splitlines()[0] in row.get("look", "") for row in locks)
    _save_stage(child, "1", _look(child, "Child opens on stage 1."))
    return child


def test_ac1_prior_saved_lock_named_before_revise_keep(workspace):
    """AC1. FO names prior save (stage, title, essay_id) before revise/keep."""
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    landed = essay_stage(child, "2", "draft")
    assert landed["ok"] is True, landed
    assert "card" not in landed
    prior = landed["prior_saved_lock"]
    assert prior["stage"] == "2"
    assert prior["essay_id"] == parent
    assert "Establish" in prior["title"] or "entries" in prior["title"].casefold()
    assert parent in prior_saved_lock_line(prior)
    assert "revise" in landed["next"].casefold()
    assert "keep" in landed["next"].casefold()


def test_ac2_keep_skips_confirm_revise_shows_card(workspace):
    """AC2. Confirm only on revise/re-lock; keep does not re-Confirm."""
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    assert "card" not in essay_stage(child, "2", "draft")
    kept = essay_stage(child, "2", "draft", lockChoice="keep")
    assert kept["stored"] is True, kept
    assert kept.get("inherited_keep") is True
    assert "card" not in kept
    assert load_pointer(child)["current"] == "3"

    child2 = _child_from(parent)
    essay_stage(child2, "2", "draft", lockChoice="revise")
    revised = essay_stage(child2, "2", "draft", _look(child2, ENTRY_LOCK))
    assert revised.get("card", {}).get("stage") == "2"


def test_ac3_delete_scope_refuses_without_where(workspace):
    """AC3. Delete draft refuses until workspace|local|both is chosen."""
    parent = _parent_with_stage2_lock()
    mac_deliverables_record(parent).write_text('{"paths": ["/tmp/example.docx"]}\n', encoding="utf-8")
    refused = essay_project_delete(MODULE, "draft")
    assert refused["ok"] is False
    assert refused.get("needs_where_choice") is True
    assert refused.get("wrote") is False
    allowed = essay_project_delete(MODULE, "draft", where="grokbot")
    assert allowed["ok"] is True
    assert allowed["where"] == "grokbot"


def test_ac4_no_silent_grokbot_when_mac_may_exist(workspace):
    """AC4. Omitted where does not silently become grokbot when Mac copies may exist."""
    parent = _parent_with_stage2_lock()
    mac_deliverables_record(parent).write_text('{"paths": ["/tmp/example.docx"]}\n', encoding="utf-8")
    refused = essay_project_delete(MODULE, "draft")
    assert refused["ok"] is False
    assert refused.get("needs_where_choice") is True
    assert refused.get("guessed") is not True


def test_ac5_suite_hooks_and_build_covered(workspace):
    """AC5. Shared handlers and FO copy are wired. Build covered."""
    text = (REPO / "src" / "essay_writer" / "stage_track.py").read_text(encoding="utf-8")
    assert "prior_saved_lock_ask" in text
    assert "delete_where_gate" in (REPO / "src" / "essay_writer" / "projects.py").read_text(encoding="utf-8")
    assert FO_STAGES_ROLL_FORWARD in stage_tool_description()
    assert "Mac-local" in INSTRUCTIONS or "Mac-local copies" in INSTRUCTIONS
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert cursor_shell()["handlers"]["essay.project.delete"] is HANDLERS["essay.project.delete"]
    assert "stage_launch" in inspect.getsource(stage_launch)
    assert "stage_launch" in inspect.getsource(cursor_stage_launch)


def test_ac6_child_inherits_parent_stage2_entry_locks(workspace):
    """AC6. sequence.new child inherits parent Stage 2 entry locks, not Basics-only."""
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    essay_stage(child, "2", "draft", lockChoice="revise")
    essay_stage(child, "2", "draft")
    note = (work_dir(child) / "tracking" / "2.md").read_text(encoding="utf-8")
    assert "North occasion" in note
    basics = "\n".join(basics_pass_lines(child))
    assert note.strip() != basics.strip()


def test_ac7_inherited_locks_visible_on_revise_keep_path(workspace):
    """AC7. Inherited entry locks visible on roll-forward revise/keep path."""
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    landed = essay_stage(child, "2", "draft")
    assert "North occasion" in landed.get("inherited_lock_preview", "")
    assert "North occasion" in landed["prior_saved_lock"]["look"]


def test_ac8_stage_events_write_sequence_debug_and_ml_paths(workspace, monkeypatch):
    """AC8. essay_id events append under that sequence debug.log and ml-events.jsonl."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    traced = front_office_call(
        "essay.stage",
        {"essay_id": child, "stage": "2", "confirmPhase": "draft", "look": "AC8 trace line."},
    )
    assert traced["ok"] is True, traced
    assert debug_log_path(child).is_file()
    assert ml_events_path(child).is_file()
    log_text = debug_log_path(child).read_text(encoding="utf-8")
    ml_text = ml_events_path(child).read_text(encoding="utf-8")
    assert child in log_text
    assert f'"essay_id":"{child}"' in ml_text.replace(" ", "")


def test_ac9_two_sequences_do_not_share_one_long_debug_ml_trail(workspace, monkeypatch):
    """AC9. Two sequences keep separate long debug and ml trails."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    parent = _parent_with_stage2_lock()
    child_a = _child_from(parent)
    child_b = _child_from(parent)
    front_office_call(
        "essay.stage",
        {"essay_id": child_a, "stage": "2", "confirmPhase": "draft", "look": "Trail A only."},
    )
    front_office_call(
        "essay.stage",
        {"essay_id": child_b, "stage": "2", "confirmPhase": "draft", "look": "Trail B only."},
    )
    log_a = debug_log_path(child_a).read_text(encoding="utf-8")
    log_b = debug_log_path(child_b).read_text(encoding="utf-8")
    ml_a = ml_events_path(child_a).read_text(encoding="utf-8")
    ml_b = ml_events_path(child_b).read_text(encoding="utf-8")
    assert child_a in log_a and child_b not in log_a
    assert child_b in log_b and child_a not in log_b
    assert child_a in ml_a and child_b not in ml_a
    assert child_b in ml_b and child_a not in ml_b
    assert log_a != log_b
    assert ml_a != ml_b


def test_ac10_health_reports_real_land_sha_when_available(workspace):
    """AC10. essay.health includes land when install or git provides a SHA."""
    report = front_office_call("essay.health", {})
    assert report["alive"] is True
    expected = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    assert report.get("land") == expected
    assert report["land"] == land_sha()
    assert report["land"] != "unknown"


def test_ac11_new_sequence_debug_trail_opens_with_land_sha(workspace, monkeypatch):
    """AC11. A new sequence debug.log opens with the land SHA on its first line."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    front_office_call(
        "essay.stage",
        {"essay_id": child, "stage": "2", "confirmPhase": "draft", "look": "AC11 land header."},
    )
    first = debug_log_path(child).read_text(encoding="utf-8").splitlines()[0]
    land = land_sha()
    assert land != "unknown"
    assert f"land={land}" in first
    assert f"essay_id={child}" in first
    assert "essay-writer.land" in first
    ml_first = json.loads(ml_events_path(child).read_text(encoding="utf-8").splitlines()[0])
    assert ml_first["tool"] == "essay-writer.land"
    assert ml_first.get("land") == land


def test_ac12_failed_essay_gates_outcome_names_refused_or_gate(workspace, monkeypatch):
    """AC12. Failed essay.gates ml-events outcome always carries refused and/or gate."""
    monkeypatch.setenv("ESSAY_WRITER_DEBUG", "1")
    parent = _parent_with_stage2_lock()
    child = _child_from(parent)
    body = front_office_call("essay.gates", {"essay_id": child})
    assert body["ok"] is False, body
    rows = [
        json.loads(line)
        for line in ml_events_path(child).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    outcomes = [row for row in rows if row.get("kind") == "outcome" and row.get("tool") == "essay.gates"]
    assert outcomes
    last = outcomes[-1]
    assert last["ok"] is False
    assert last.get("refused") or last.get("gate")
    if last.get("gate"):
        assert last["gate"] in {"brief", "module", "genre", "body", "citations", "word-band", "references", "identity", "conclusion", "unquoted-exact"} or last["gate"].isdigit()


def _parent_stage1_only() -> str:
    _brief()
    essay_sequence_new(MODULE, "draft")
    parent = essay_sequence_new(MODULE, "confirm")["sequence_id"]
    _save_stage(parent, "1", _look(parent, "Task noted for the diary."))
    return parent


def _open_child(parent: str) -> str:
    draft = essay_sequence_new(MODULE, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(MODULE, "confirm", parent)
    assert opened["ok"] is True, opened
    return opened["sequence_id"]


def test_ac13_local_delete_refuses_without_reachable_mac_paths(workspace):
    """AC13. local with no named paths refuses; nothing removed."""
    parent = _parent_with_stage2_lock()
    refused = essay_project_delete(MODULE, "draft", where="local")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert refused.get("needs_local_paths") is True
    reason = refused.get("reason", "").casefold()
    assert "nothing" in reason and "removed" in reason
    assert sequence_dir(MODULE, int(parent.split("-")[-1])).is_dir()


def test_ac14_both_delete_refuses_without_reachable_mac_paths(workspace):
    """AC14. both with no named paths refuses; workspace not wiped."""
    parent = _parent_with_stage2_lock()
    refused = essay_project_delete(MODULE, "confirm", where="both")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert refused.get("needs_local_paths") is True
    reason = refused.get("reason", "").casefold()
    assert "nothing" in reason and "removed" in reason
    assert sequence_dir(MODULE, int(parent.split("-")[-1])).is_dir()
    assert essay_dir(MODULE).is_dir()


def test_ac15_stage1_only_parent_child_does_not_invent_stage2_entry_lock(workspace):
    """AC15. Parent Stage 1 Confirmed only: child has no invented Stage 2 entry lock."""
    parent = _parent_stage1_only()
    child = _open_child(parent)
    record = load_record(child) or {}
    locks = record.get("inherited_locks") or []
    assert not any(row.get("stage") == "2" for row in locks)
    assert not any(ENTRY_LOCK.splitlines()[0] in str(row.get("look", "")) for row in locks)
    assert inherited_locks(child) == []
    assert load_pointer(child)["current"] == "1"


def test_ac16_parent_stage2_entry_confirmed_child_still_inherits(workspace):
    """AC16. Parent Stage 2 entry Confirmed: child still inherits (regression)."""
    parent = _parent_with_stage2_lock()
    child = _open_child(parent)
    locks = inherited_locks(child)
    assert any(row.get("stage") == "2" and ENTRY_LOCK.splitlines()[0] in row.get("look", "") for row in locks)
    _save_stage(child, "1", _look(child, "Child opens on stage 1."))
    landed = essay_stage(child, "2", "draft")
    assert landed["ok"] is True, landed
    assert "North occasion" in landed.get("prior_saved_lock", {}).get("look", "")


def test_ac17_build_covered_delete_and_sequence_new_handlers(workspace):
    """AC17. FO and Cursor/Grok Build share essay.project.delete and essay.sequence.new."""
    assert HANDLERS["essay.project.delete"] is essay_project_delete
    assert HANDLERS["essay.sequence.new"] is essay_sequence_new
    fo = front_office()["handlers"]
    cur = cursor_shell()["handlers"]
    assert fo["essay.project.delete"] is HANDLERS["essay.project.delete"]
    assert fo["essay.sequence.new"] is HANDLERS["essay.sequence.new"]
    assert cur["essay.project.delete"] is HANDLERS["essay.project.delete"]
    assert cur["essay.sequence.new"] is HANDLERS["essay.sequence.new"]
