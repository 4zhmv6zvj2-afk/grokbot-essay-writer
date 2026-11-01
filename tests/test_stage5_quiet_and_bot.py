"""Stage 5 quiet, context, handoff, and Essay Bot."""

import json
from pathlib import Path

from helpers import (
    CLARIFY_OPEN,
    ESSAY,
    TOPIC,
    open_sequence,
    pack,
    picked,
    plant_gathered_source,
    source,
    write_upload,
)

from essay_writer.build_office import RESIDUALS, build_deliverable_handoff, stage_launch
from essay_writer.context_fit import fit_critical_reviews
from essay_writer.first_run import attach_custom_mcp, repo_bot_share
from essay_writer.late_chain import FIRST_DRAFT_READY, QUIET_STEP, STAGE6_OPEN
from essay_writer.projects import essay_project_delete
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.revise import essay_revise
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word
from essay_writer.writing_basics import CHECKLISTS

REPO = Path(__file__).resolve().parents[1]
SHARE = REPO / "docs" / "templates" / "essay-bot.share.json"


def _save_through(seq: str, stop: str) -> None:
    from essay_writer.writing_basics import STAGE_ORDER

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


def _quiet(body: dict) -> None:
    assert body["quiet"] is True
    assert body["checklist_in_chat"] is False
    assert body["chat"] == body["next"]
    assert "Walk this Basics checklist" not in body["next"]
    assert "Apply every line" not in body["next"]
    assert "Essay-writer/" not in body["next"]
    assert "tracking/" not in body["next"]
    assert "tracking_path" not in body


def test_stage5_stays_quiet_until_the_word_file_exists(workspace):
    seq = open_sequence()
    _save_through(seq, "4b")
    draft = essay_stage(seq, "5", "draft", "The first draft can start.")
    _quiet(draft)
    assert draft["step"] == "5"
    assert draft["next"] == STAGE6_OPEN
    assert draft["stored"] is True
    assert draft["current"] == "6"
    assert "card" not in draft
    assert "Say yes" not in draft["next"]
    assert draft["rules"] == stage_settings("5", "report")["rules"]
    kept = essay_stage(seq, "5", "confirm", "The first draft can start.")
    assert kept["ok"] is False
    assert "sequences/" not in draft["next"]


def test_word_preview_is_quiet_and_confirm_shows_the_draft(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    preview = essay_pack_render_word(seq, pack(), "draft")
    _quiet(preview)
    assert preview["step"] == "5b"
    assert preview["wrote"] is False
    assert preview["next"] == QUIET_STEP
    assert preview.get("path") not in ("", None)
    assert preview["path"] not in preview["next"]

    written = essay_pack_render_word(seq, pack(), "confirm")
    _quiet(written)
    assert written["wrote"] is True
    assert "narrow strait" in written["next"]
    assert written["path"] not in written["next"]
    assert "Essay-writer/" not in written["next"]

    _save_through(seq, "4b")
    draft = essay_stage(seq, "5", "draft", "Kept.")
    assert draft["stored"] is True
    assert draft["current"] == "6"
    assert draft["next"] == FIRST_DRAFT_READY
    assert "card" not in draft
    assert "tracking/" not in draft["next"]


def test_revise_during_the_first_draft_is_quiet_unless_blocked(workspace):
    seq = open_sequence()
    _save_through(seq, "4b")
    note = essay_revise(seq, "Tighten the opening. Do not add sources.", "draft")
    _quiet(note)
    assert note["step"] == "revise"
    blocked = essay_revise(seq, "Cite (Patel, 2019) as well.", "draft")
    assert blocked["ok"] is False
    assert blocked["refused"] == "invent-forbid"
    assert blocked.get("quiet") is not True


def test_context_exhaust_trims_splits_and_reopens_without_a_silent_cut():
    short = [{"paper_id": "a", "markdown": "Smith (2020) says the strait is narrow.\n"}]
    fitted = fit_critical_reviews(short, budget=256_000)
    assert fitted["action"] == "fit"
    assert fitted["clear"] is True
    assert fitted["exhausted"] is False
    assert fitted["continue_revise"] is False
    assert fitted["silent_truncation"] is False
    assert fitted["tip"] is None

    body = "The gathered note says the corridor is narrow."
    padded = f"Critical note: grok-4.7\n{body}\n"
    trimmed = fit_critical_reviews(
        [{"paper_id": "a", "markdown": padded}],
        budget=len(body) + 1,
    )
    assert trimmed["action"] == "trim"
    assert trimmed["clear"] is True
    assert trimmed["continue_revise"] is True
    assert trimmed["silent_truncation"] is False
    assert trimmed["evidence"] == "full-markdown"
    working = trimmed["batches"][0]["working"]["a"]
    assert "Critical note: grok-4.7" not in working
    assert body in working
    assert working != padded[: len(body) + 1]

    one = "A" * 60
    two = "B" * 60
    split = fit_critical_reviews(
        [
            {"paper_id": "a", "markdown": one},
            {"paper_id": "b", "markdown": two},
        ],
        budget=80,
    )
    assert split["action"] == "split"
    assert split["clear"] is True
    assert split["continue_revise"] is True
    assert split["exhausted"] is False
    assert [batch["paper_ids"] for batch in split["batches"]] == [["a"], ["b"]]
    assert split["batches"][0]["working"]["a"] == one

    huge = "HEAD " + ("x" * 80) + " EXACT PASSAGE HERE " + ("y" * 80)
    opened = fit_critical_reviews(
        [{"paper_id": "a", "markdown": huge}],
        reopens=[{"paper_id": "a", "gap": "missing limit", "passage": "EXACT PASSAGE HERE"}],
        budget=len("EXACT PASSAGE HERE"),
    )
    assert opened["action"] == "reopen"
    assert opened["clear"] is True
    assert opened["continue_revise"] is True
    assert opened["batches"][0]["working"]["a"] == "EXACT PASSAGE HERE"
    assert opened["batches"][0]["working"]["a"] != huge[: len("EXACT PASSAGE HERE")]

    invented = fit_critical_reviews(
        [{"paper_id": "a", "markdown": huge}],
        reopens=[{"paper_id": "a", "gap": "missing limit", "passage": "A sentence that was not gathered."}],
        budget=40,
    )
    assert invented["exhausted"] is True
    assert invented["continue_revise"] is False
    assert invented["invent_forbid"] == "refuse"
    assert invented["silent_truncation"] is False
    assert invented["tip"]
    dumped = json.dumps(invented["batches"])
    assert "A sentence that was not gathered." not in dumped
    assert huge[:40] not in dumped

    stopped = fit_critical_reviews([{"paper_id": "a", "markdown": huge}], budget=40)
    assert stopped["exhausted"] is True
    assert stopped["continue_revise"] is False
    assert stopped["tip"]
    assert "cut off in silence" in stopped["tip"]
    assert huge[:40] not in json.dumps(stopped["batches"])

    pending = stage_launch("5")
    assert pending["context_fit"]["action"] == "pending"
    assert pending["context_fit"]["silent_truncation"] is False
    rules = pending["command"][pending["command"].index("--rules") + 1]
    assert "Chat for this step stays quiet." in rules
    assert "drop only a repeated model line" in rules
    assert CHECKLISTS["5"][-1] in stage_settings("5")["rules"]


def _confirm_stage_deliverables(workspace, seq: str) -> None:
    """4a and 4b files come from confirm. Handoff does not write them."""
    journal = (
        "Smith, J. (2020) Chokepoints and crude. Maritime Policy 12(3) pp. 4-9. doi:10.1000/strait\n"
        "The Strait handles a large share of flows.\n"
        "The authors confirm the limit in the gathered file.\n"
    )
    annotation = (
        "Smith (2020) measured chokepoint risk on one corridor. "
        "The paper found that the strait carries a large share of flows. "
        "That finding helps this assignment on how a firm should manage the corridor."
    )
    review = (
        "Smith (2020) argues the corridor is narrow. The authors confirm the limit. "
        'The paper says "The Strait handles a large share of flows."'
    )
    write_upload(workspace, text=journal)
    row = source()
    row["annotation"] = annotation
    draft = essay_research_summary(seq, TOPIC, "draft", [row])
    assert draft["ok"] is True, draft
    saved = essay_research_summary(seq, TOPIC, "confirm", [row])
    assert saved["stored"] is True, saved
    reviews = [{"paper_id": "src-1", "markdown": review}]
    full_draft = essay_research_full(
        seq, TOPIC, "draft", [source()], clarify_context=CLARIFY_OPEN, reviews=reviews
    )
    assert full_draft["ok"] is True, full_draft
    full = essay_research_full(
        seq, TOPIC, "confirm", [source()], clarify_context=CLARIFY_OPEN, reviews=reviews
    )
    assert full["stored"] is True, full


def test_handoff_wires_4a_and_4b_deliverables(workspace, tmp_path):
    seq = open_sequence()
    _confirm_stage_deliverables(workspace, seq)
    mac = tmp_path / "mac"
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    before = {name: (folder / name).read_bytes() for name in (
        "annotation.docx",
        "download-list.docx",
        "papers.zip",
        "critical-reviews.zip",
    )}
    copied = build_deliverable_handoff(folder, mac_dir=mac)
    assert copied["handoff"] == "stage-deliverables"
    assert copied["deliverables"] == [
        "annotation.docx",
        "download-list.docx",
        "papers.zip",
        "critical-reviews.zip",
    ]
    assert "40d-packing" not in copied["residual_ids"]
    for name in copied["deliverables"]:
        assert (folder / name).read_bytes() == before[name]
        assert (mac / name).read_bytes() == before[name]

    ad_hoc = tmp_path / "loose"
    ad_hoc.mkdir()
    (ad_hoc / "essay.docx").write_bytes(b"word-bytes")
    loose = build_deliverable_handoff(ad_hoc, mac_dir=mac)
    assert loose["handoff"] == "copy_deliverable_to_mac"
    assert "40d-packing" in loose["residual_ids"]
    assert RESIDUALS["40d-packing"] in loose["residual"]


def test_bot_share_json_and_delete_lists(workspace, tmp_path):
    share = repo_bot_share()
    assert "host_note" in share
    assert "CreateBotShareJson" not in json.dumps(share)
    assert share["switched_on"] is True
    assert share["mcpServers"]["essay-writer"]["command"] == "essay-writer"
    assert share["mcpServers"]["essay-writer"]["args"] == []
    assert share["delete"]["tool"] == "essay.project.delete"
    assert share["delete"]["skip_computer_list"] is False
    assert "consensus.app" not in json.dumps(share)
    assert "unpaywall.org" not in json.dumps(share)
    on_disk = json.loads(SHARE.read_text(encoding="utf-8"))
    assert on_disk == share

    project = tmp_path / "proj"
    project.mkdir()
    attached = attach_custom_mcp(project, include_user=False, enable=lambda name: {"identifier": name})
    written = json.loads(Path(attached["bot_share"]).read_text(encoding="utf-8"))
    assert "CreateBotShareJson" not in json.dumps(written)
    assert written["mcpServers"]["essay-writer"]["args"] == []
    assert (project / ".grok" / "essay-bot.share.json").is_file()

    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "switched on" in bot.casefold()
    assert "not switched on" not in bot.casefold()
    assert "computer_list" in bot
    assert "essay.project.delete" in bot

    from essay_writer.projects import essay_sequence_new

    essay_sequence_new(ESSAY, "draft")
    essay_sequence_new(ESSAY, "confirm")
    draft = essay_project_delete(ESSAY, "draft")
    assert draft["computer_list"] == []
    assert draft["guessed"] is False
    assert draft["workspace_list"]
    assert "Copies on your computer stay." in draft["next"]
    assert "Open the Confirm card" in draft["next"]
    assert "Computer list:" not in draft["next"]
    assert "will be removed" not in draft["next"]
    assert "Documents" not in draft["next"]

    missing = essay_project_delete(ESSAY, "draft", where="local")
    assert missing["computer_list"] == []
    assert missing["guessed"] is False
    assert missing["needs_local_paths"] is True
