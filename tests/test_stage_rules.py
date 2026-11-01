"""Stage guidance is applied as rules, and confirm saves the tracking note."""

import ast
import asyncio
import json
from pathlib import Path

from helpers import (
    ESSAY,
    OTHER,
    open_sequence,
    picked,
    plant_gathered_source,
    plant_renderable_pack,
)

from essay_writer.build_office import stage_launch
from essay_writer.doors import DOORS
from essay_writer.server import INSTRUCTIONS, build_review_server, build_server
from essay_writer.shells import front_office_call
from essay_writer.stage_llm import STAGE_ORDER, brief_genre, stage_settings, stage_title
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import student_surface_hits
from essay_writer.writing_basics import (
    CHECKLIST_WALK,
    CHECKLISTS,
    DOOR_WALK,
    REVISIT_DOOR,
    basics_lines,
)

REPO_DOCS = Path(__file__).resolve().parents[1]


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def _door(tool: str) -> str:
    return next(door["description"] for door in DOORS if door["tool"] == tool)


def test_every_stage_loads_its_guidance_as_rules():
    for stage, lines in CHECKLISTS.items():
        item = stage_settings(stage)
        bullets = "\n".join(f"- {line}" for line in lines)
        assert item["prompt_overlay"].startswith(CHECKLIST_WALK)
        assert bullets in item["prompt_overlay"]
        assert item["rules"].startswith(f"Rules for stage {stage} — ")
        assert "Apply every line." in item["rules"]
        assert item["prompt_overlay"] in item["rules"]
        assert CHECKLIST_WALK in item["rules"]
        assert item["tracking_file"] == f"tracking/{stage}.md"
        assert item["pointer_file"] == "tracking/stage.json"
        assert item["source"] == "essay_writer.stage_llm.stage_settings"
        assert student_surface_hits(item["prompt_overlay"]) == []
        assert student_surface_hits(item["rules"]) == []
    review = stage_settings("eqr")
    assert review["prompt_overlay"] in review["rules"]
    assert "Apply every line." in review["rules"]
    assert review["tracking_file"] is None
    assert review["next_stage"] is None
    assert stage_settings("10")["next_stage"] is None
    assert stage_settings("1")["next_stage"] == "2"
    assert stage_settings("4a")["next_stage"] == "4b"
    assert stage_settings("9")["next_stage"] == "10"


def test_cursor_briefing_and_tools_load_the_same_rules():
    assert (
        "Rules for stage 2 — Essay: Establish a thesis. "
        "Report: Establish purpose and scope. Apply every line."
    ) in INSTRUCTIONS
    assert "Rules for stage 7 — Ask for feedback. Apply every line." in INSTRUCTIONS
    assert CHECKLISTS["2"][0] in INSTRUCTIONS
    assert "central theme" in INSTRUCTIONS
    assert "A report has no thesis." in INSTRUCTIONS
    assert CHECKLIST_WALK in INSTRUCTIONS
    assert "Stage 1 limiting conditions" in INSTRUCTIONS
    originals = _door("essay.originals")
    assert "Apply stage 1 — Analyse the task guidance as rules" in originals
    assert "tracking/1.md" in originals
    assert "stage 2 — Essay: Establish a thesis. Report: Establish purpose and scope" in originals
    assert DOOR_WALK in originals
    assert "A report has no thesis." in originals
    summary = _door("essay.research.summary")
    assert "tracking/4a.md" in summary
    assert "stage 4b — Critical review" in summary
    assert "as rules" in summary
    stage = _door("essay.stage")
    assert "Stage 3 — Essay: Write an essay plan. Report: Write a report plan." in stage
    assert DOOR_WALK in stage
    assert "central theme" in stage
    assert "tracking/3.md" in stage
    assert "Stage 7 — Ask for feedback." in stage
    assert "tracking/7.md" in stage
    assert "Stage 10 — Submit the final draft." in stage
    assert "The tool does not submit." in stage
    assert "Apply stage 1" not in _door("essay.health")
    reviewer = build_review_server()
    tools = reviewer._tool_manager.list_tools()
    assert stage_settings("eqr")["rules"] in tools[0].description
    assert "Follow every line." in tools[0].description


def test_build_launch_puts_the_same_rules_and_path_on_the_command():
    for stage in ("2", "7", "4b", "10", "eqr"):
        item = stage_settings(stage)
        rules = _rules(stage_launch(stage)["command"])
        assert item["rules"] in rules
        assert item["prompt_overlay"] in rules
        assert "Apply the stage guidance as rules:" in rules
        if item["tracking_file"]:
            assert item["tracking_file"] in rules
            assert "tracking/stage.json" in rules
        else:
            assert "Tracking file: none" in rules
    assert "tracking/7.md" in _rules(stage_launch("7")["command"])
    assert "Next stage: 8" in _rules(stage_launch("7")["command"])
    assert "Next stage: none" in _rules(stage_launch("10")["command"])


def test_build_launch_carries_the_checklist_walk_and_the_plan_revisit():
    """Grok Build stage_launch and Cursor stage_settings share one rules text."""
    for stage in STAGE_ORDER:
        launch = stage_launch(stage)
        rules = _rules(launch["command"])
        item = stage_settings(stage)
        assert launch["source"] == "essay_writer.stage_llm.stage_settings"
        assert launch["settings"]["rules"] == item["rules"]
        assert item["rules"] in rules
        assert CHECKLIST_WALK in rules
        assert "Walk this Basics checklist internally before the save." in rules
    for stage in ("2", "3", "4a", "4b", "5"):
        rules = _rules(stage_launch(stage)["command"])
        assert "revisit the stage 3 plan" in rules or "reopen" in rules
        assert "Do not silently rewrite the plan into the draft." in rules
        assert "purpose and scope" in rules
        assert "central theme" in rules
        assert "A report has no thesis." in rules or "no thesis" in rules.casefold()
    stage_two = _rules(stage_launch("2")["command"])
    assert "An essay locks a thesis." in stage_two
    assert "A report locks purpose and scope." in stage_two
    assert CHECKLIST_WALK not in _rules(stage_launch("eqr")["command"])


def test_draft_writes_the_tracking_note_and_confirm_advances(workspace):
    seq = open_sequence()
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking"
    draft = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "draft",
            "look": "The task is a report on one named chain.",
        },
    )
    assert draft["ok"] is True
    assert draft["stored"] is False
    assert draft["advanced"] is False
    assert draft["current"] == "1"
    assert draft["rules"] == stage_settings("1")["rules"]
    assert draft["source"] == "essay_writer.stage_llm.stage_settings"
    assert draft["stage_title"] == "Analyse the task"
    assert draft["confirm_line"] == (
        "Confirm to save the final look and go to **Stage 2 — Establish purpose and scope**."
    )
    assert "Show this stage note" not in draft["next"]
    note = folder / "1.md"
    text = note.read_text(encoding="utf-8")
    assert f"Sequence id: {seq}" in text
    assert "Status: draft" in text
    assert "## Working look" in text
    assert "The task is a report on one named chain." in text
    for line in CHECKLISTS["1"]:
        assert line in text
    assert student_surface_hits(text) == []
    pointer = json.loads((folder / "stage.json").read_text(encoding="utf-8"))
    assert pointer["current"] == "1"
    assert pointer["saved"] == []

    saved = essay_stage(seq, "1", "confirm", "The task is a report on one named chain.", **picked(draft))
    assert saved["ok"] is True
    assert saved["stored"] is True
    assert saved["advanced"] is True
    assert saved["current"] == "2"
    assert saved["next_stage"] == "2"
    assert saved["submitted"] is False
    assert "markdown" not in saved["next"].casefold()
    final = note.read_text(encoding="utf-8")
    assert f"Sequence id: {seq}" in final
    assert "Status: final" in final
    assert "## Final look" in final
    assert "The task is a report on one named chain." in final
    for line in CHECKLISTS["1"]:
        assert line in final
    pointer = json.loads((folder / "stage.json").read_text(encoding="utf-8"))
    assert pointer["current"] == "2"
    assert pointer["saved"] == ["1"]
    assert pointer["files"]["1"].endswith("tracking/1.md")
    assert pointer["closed"] is False


def test_confirm_keeps_the_card_look_and_refuses_a_skipped_stage(workspace):
    seq = open_sequence()
    opened = essay_stage(seq, "1", "draft", "Thesis is still open.")
    changed = essay_stage(
        seq, "1", "confirm", "A different thesis.", cardAction="confirm", cardDigest=opened["digest"]
    )
    assert changed["ok"] is True, changed
    assert changed["stored"] is True
    final = (
        workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking" / "1.md"
    ).read_text(encoding="utf-8")
    assert "Thesis is still open." in final
    assert "A different thesis." not in final
    skipped = essay_stage(seq, "3", "draft")
    assert skipped["ok"] is False
    assert skipped["refused"] == "stage"
    assert "current stage is 2" in skipped["reason"]
    assert "Send that stage" not in skipped["reason"]
    assert "Finish that step in this chat" in skipped["reason"]
    bare = essay_stage(ESSAY, "1", "draft")
    assert bare["ok"] is False
    assert bare["wrote"] is False
    assert not (workspace / "Essay-writer" / ESSAY / "tracking").exists()


def test_a_house_label_in_the_look_is_refused_before_the_file(workspace):
    seq = open_sequence()
    refused = essay_stage(seq, "1", "draft", "Confirm the pack before EQR.")
    assert refused["ok"] is False
    assert refused["refused"] == "house-jargon"
    assert refused["wrote"] is False
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking"
    assert not folder.exists()
    assert "invent-forbid" not in refused["reason"].casefold()


def test_each_stage_confirm_saves_the_final_look_then_the_next_stage(workspace):
    seq = open_sequence()
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking"
    genre = brief_genre(seq)
    assert genre == "report"
    for stage in STAGE_ORDER:
        item = stage_settings(stage, genre)
        following = item["next_stage"]
        draft = essay_stage(seq, stage, "draft")
        assert draft["ok"] is True, draft
        assert draft["rules"] == item["rules"]
        assert draft["stage_title"] == stage_title(stage, genre)
        note = (folder / f"{stage}.md").read_text(encoding="utf-8")
        for line in basics_lines(stage, genre):
            assert line in note
        assert CHECKLIST_WALK in note
        assert student_surface_hits(note) == []
        if stage == "2":
            assert draft["stage_title"] == "Establish purpose and scope"
            assert "locked thesis" not in item["prompt_overlay"]
            assert "purpose and scope" in item["prompt_overlay"]
            assert "A report has no thesis." in item["prompt_overlay"]
            assert item["rules"].startswith(
                "Rules for stage 2 — Establish purpose and scope. Apply every line."
            )
        if stage == "3":
            assert draft["stage_title"] == "Write a report plan"
            assert "central theme" in item["prompt_overlay"]
            assert "holds the thesis" not in item["prompt_overlay"]
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            saved = draft
        else:
            if stage == "10":
                plant_renderable_pack(seq)
            saved = essay_stage(seq, stage, "confirm", **picked(draft))
        assert saved["stored"] is True
        assert saved["submitted"] is False
        final = (folder / f"{stage}.md").read_text(encoding="utf-8")
        assert "## Final look" in final
        assert item["prompt_overlay"] in final
        if following:
            assert saved["advanced"] is True
            assert saved["current"] == following
        else:
            assert saved["advanced"] is False
            assert saved["closed"] is True
            assert saved["current"] == "10"
            assert "does not submit" in saved["next"]
    pointer = json.loads((folder / "stage.json").read_text(encoding="utf-8"))
    assert pointer["saved"] == list(STAGE_ORDER)
    assert pointer["closed"] is True
    again = essay_stage(seq, "10", "confirm")
    assert again["ok"] is False
    assert again["refused"] == "stage"


def test_shared_overlay_walks_the_checklist_and_names_both_genres():
    shared_two = stage_settings("2")["prompt_overlay"]
    shared_three = stage_settings("3")["prompt_overlay"]
    assert shared_two.startswith(CHECKLIST_WALK)
    assert "Do not paste the rest of the Basics checklist into the chat." in shared_two
    assert "Stage 1 limiting conditions" in shared_two
    assert "An essay locks a thesis." in shared_two
    assert "A report locks purpose and scope." in shared_two
    assert "central theme" in shared_three
    report_two = stage_settings("2", "report")["prompt_overlay"]
    report_three = stage_settings("3", "report")["prompt_overlay"]
    assert "locked thesis" not in report_two
    assert "purpose and scope" in report_two
    assert "A report has no thesis." in report_two
    assert "central theme" in report_three
    assert "holds the thesis" not in report_three
    essay_two = stage_settings("2", "essay")["prompt_overlay"]
    essay_three = stage_settings("3", "essay")["prompt_overlay"]
    assert "locked thesis" in essay_two
    assert stage_title("2", "essay") == "Establish a thesis"
    assert "central theme" not in essay_three
    assert stage_title("3", "essay") == "Write an essay plan"
    assert student_surface_hits(report_two) == []
    assert student_surface_hits(essay_two) == []


def test_essay_sequence_keeps_the_thesis_label(workspace):
    seq = open_sequence(OTHER)
    assert brief_genre(seq) == "essay"
    draft = essay_stage(seq, "1", "draft", "The task is an essay.")
    assert draft["confirm_line"] == (
        "Confirm to save the final look and go to **Stage 2 — Establish a thesis**."
    )
    saved = essay_stage(seq, "1", "confirm", "The task is an essay.", **picked(draft))
    assert saved["card"]["stage"] == "2"
    assert saved["next"] == (
        "Open the Confirm card to save Stage 2 — Establish a thesis, "
        "or choose Not yet to keep working in this chat."
    )
    stage_two = essay_stage(
        seq,
        "2",
        "draft",
        "The thesis is that chokepoints constrain the corridor.",
    )
    assert stage_two["stage_title"] == "Establish a thesis"
    assert "locked thesis" in stage_two["rules"]
    assert "Establish purpose and scope" not in stage_two["stage_title"]
    essay_stage(seq, "2", "confirm", "The thesis is that chokepoints constrain the corridor.", **picked(stage_two))
    stage_three = essay_stage(seq, "3", "draft", "Three points support the thesis.")
    assert stage_three["stage_title"] == "Write an essay plan"
    assert "thesis" in stage_three["rules"]
    assert "central theme" not in stage_three["rules"]


def _save_through(seq: str, stop: str) -> None:
    look = "Saved from the brief."
    for stage in STAGE_ORDER:
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            if stage == stop:
                return
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
        if stage == stop:
            return


def test_post_research_revisit_is_on_the_overlay_and_the_door():
    for stage in ("4a", "4b", "5"):
        shared = stage_settings(stage)["prompt_overlay"]
        assert "revisit the stage 3 plan" in shared
        assert "Do not silently rewrite the plan into the draft." in shared
        assert "purpose and scope" in shared
        assert "central theme" in shared
        assert student_surface_hits(shared) == []
        report = stage_settings(stage, "report")["prompt_overlay"]
        assert "Revisit purpose and scope only if the research breaks them." in report
        assert "central theme" in report
        assert "A report has no thesis." in report
        assert "locked thesis" not in report
        essay = stage_settings(stage, "essay")["prompt_overlay"]
        assert "Revisit the thesis only if the research breaks it." in essay
        assert "central theme" not in essay
        assert student_surface_hits(essay) == []
    assert REVISIT_DOOR in _door("essay.research.summary")
    assert REVISIT_DOOR in _door("essay.research.full")
    assert REVISIT_DOOR in _door("essay.pack.validate")
    assert "Do not silently rewrite the plan into the draft." in _door("essay.stage")
    assert "After 4a and 4b Confirm" in INSTRUCTIONS
    router = (REPO_DOCS / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    essay_help = (REPO_DOCS / "docs" / "essay-writing-helpers.md").read_text(encoding="utf-8")
    report_help = (REPO_DOCS / "docs" / "report-writing-helpers.md").read_text(encoding="utf-8")
    assert "revisit the stage 3 plan" in router
    assert "central theme" in router
    assert "Do not silently rewrite the plan into the draft." in router
    assert student_surface_hits(router) == []
    assert "Revisit the thesis only if the research breaks it." in essay_help
    assert "Do not silently rewrite the plan into the draft." in essay_help
    assert "Revisit purpose and scope only if the research breaks them." in report_help
    assert "central theme" in report_help
    assert "A report has no thesis." in report_help


def test_plan_revisit_updates_tracking_and_blocks_a_silent_draft(workspace):
    seq = open_sequence()
    _save_through(seq, "4b")
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking"
    empty = essay_stage(seq, "3", "draft", "   ")
    assert empty["ok"] is False
    assert empty["refused"] == "stage"
    delta = "The analysis now follows Smith 2020. The central theme still holds."
    opened = essay_stage(seq, "3", "draft", delta)
    assert opened["revisit"] is True
    assert "Stage 5 —" in opened["confirm_line"]
    silent = essay_stage(seq, "5", "draft", "A draft that skips the plan save.")
    assert silent["ok"] is False
    assert silent["refused"] == "stage"
    saved = essay_stage(seq, "3", "confirm", delta, **picked(opened))
    assert saved["stored"] is True
    assert saved["advanced"] is False
    assert saved["current"] == "5"
    assert saved["next_stage"] == "5"
    note = (folder / "3.md").read_text(encoding="utf-8")
    assert delta in note
    assert "Status: final" in note
    draft = essay_stage(seq, "5", "draft", "The first draft can start.")
    assert draft["ok"] is True
    assert draft["stored"] is True
    assert draft["current"] == "6"
    assert draft["revisit"] is False
    assert "card" not in draft
    late = essay_stage(seq, "3", "draft", "Too late to reopen the plan.")
    assert late["ok"] is False
    assert "already saved" in late["reason"]


def test_a_broken_lock_confirms_stage_2_before_the_plan(workspace):
    seq = open_sequence()
    _save_through(seq, "4b")
    lock = "Purpose and scope now name one chain because Smith 2020 shows it."
    opened = essay_stage(seq, "2", "draft", lock)
    assert opened["revisit"] is True
    assert opened["stage_title"] == "Establish purpose and scope"
    assert "Stage 3 — Write a report plan" in opened["confirm_line"]
    early_plan = essay_stage(seq, "3", "draft", "The plan waits on the lock.")
    assert early_plan["ok"] is False
    assert "purpose and scope" in early_plan["reason"]
    early_draft = essay_stage(seq, "5", "draft", "Silent draft.")
    assert early_draft["ok"] is False
    saved_lock = essay_stage(seq, "2", "confirm", lock, **picked(opened))
    assert saved_lock["current"] == "5"
    assert saved_lock["advanced"] is False
    assert saved_lock["next_stage"] == "3"
    still = essay_stage(seq, "5", "draft", "Still too soon.")
    assert still["ok"] is False
    assert "plan again" in still["reason"]
    plan = "The plan names that chain because Smith 2020 shows it."
    planned = essay_stage(seq, "3", "draft", plan)
    saved_plan = essay_stage(seq, "3", "confirm", plan, **picked(planned))
    assert saved_plan["current"] == "5"
    assert saved_plan["next"] == "Start Stage 5 — Write your first draft in this chat."
    ready = essay_stage(seq, "5", "draft", "Now the draft.")
    assert ready["ok"] is True
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "tracking"
    assert lock in (folder / "2.md").read_text(encoding="utf-8")
    assert plan in (folder / "3.md").read_text(encoding="utf-8")


def test_workflow_records_stage_tracking_for_both_shells():
    workflow = (REPO_DOCS / "docs" / "workflow.md").read_text(encoding="utf-8")
    assert "Essay-writer/<module>/sequences/<n>/tracking/<stage>.md" in workflow
    bot = (REPO_DOCS / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "switched on" in bot.casefold()
    assert "not switched on" not in bot.casefold()
    assert "tracking/" not in bot
    dig = (REPO_DOCS / "src" / "essay_writer" / "dig.py").read_text(encoding="utf-8")
    assert "ESSAY_WRITER_CONSENSUS" in dig
    root = REPO_DOCS / "src" / "essay_writer"
    found: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {"stage_settings", "stage_rules", "essay_stage"}:
                found.setdefault(node.name, []).append(path.name)
    assert found["stage_settings"] == ["stage_llm.py"]
    assert found["stage_rules"] == ["stage_llm.py"]
    assert found["essay_stage"] == ["stage_track.py"]
    names = {tool.name for tool in asyncio.run(build_server().list_tools())}
    assert "essay.stage" in names
