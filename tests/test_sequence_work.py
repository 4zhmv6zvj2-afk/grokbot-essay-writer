import json

from helpers import ESSAY, TOPIC, pack, source, write_upload

from essay_writer.originals import essay_originals
from essay_writer.projects import essay_project_archive, essay_sequence_new
from essay_writer.research import essay_research_summary
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word


def test_work_follows_the_sequence_and_uploads_stay_shared(workspace):
    draft = essay_sequence_new(ESSAY, "draft")
    assert draft["wrote"] is False
    opened = essay_sequence_new(ESSAY, "confirm")
    sequence_id = opened["sequence_id"]
    write_upload(workspace)
    listed = essay_originals(sequence_id, "list")
    assert listed["uploads"][0]["locator"] == f"uploads/{ESSAY}/smith.md"
    missing = essay_research_summary(f"{ESSAY}-9", TOPIC, "draft", [source()])
    assert missing["ok"] is False

    assert essay_research_summary(sequence_id, TOPIC, "draft", [source()])["ok"] is True
    assert essay_research_summary(sequence_id, TOPIC, "confirm", [source()])["stored"] is True
    state_path = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["sequence_id"] == sequence_id
    assert state["research"]["summary"]["topic"] == TOPIC
    assert not (workspace / "Essay-writer" / ESSAY / "state.json").exists()

    assert essay_pack_validate(sequence_id, pack(), "draft")["passed"] is True
    assert essay_pack_validate(sequence_id, pack(), "confirm")["recorded_pass"] is True
    assert essay_pack_render_word(sequence_id, pack(), "draft")["wrote"] is False
    written = essay_pack_render_word(sequence_id, pack(), "confirm")
    assert written["wrote"] is True
    assert written["path"] == f"Essay-writer/{ESSAY}/sequences/1/output/{sequence_id}.docx"
    assert (workspace / written["path"]).is_file()
    assert not (workspace / "Essay-writer" / ESSAY / "output" / f"{ESSAY}.docx").exists()

    assert essay_sequence_new(ESSAY, "draft")["ok"] is True
    child_id = essay_sequence_new(ESSAY, "confirm")["sequence_id"]
    child_topic = TOPIC + " for the next sequence"
    assert essay_research_summary(child_id, child_topic, "draft", [source()])["ok"] is True
    assert essay_research_summary(child_id, child_topic, "confirm", [source()])["stored"] is True
    parent = json.loads(state_path.read_text(encoding="utf-8"))
    child = json.loads(
        (workspace / "Essay-writer" / ESSAY / "sequences" / "2" / "state.json").read_text(encoding="utf-8")
    )
    assert parent["research"]["summary"]["topic"] == TOPIC
    assert child["research"]["summary"]["topic"] == child_topic
    assert child["branched_from"] == sequence_id


def test_archived_sequence_refuses_further_work(workspace):
    draft = essay_sequence_new(ESSAY, "draft")
    sequence_id = essay_sequence_new(ESSAY, "confirm")["sequence_id"]
    assert draft["sequence_id"] == sequence_id
    essay_project_archive(ESSAY, "draft")
    essay_project_archive(ESSAY, "confirm")
    refused = essay_originals(sequence_id, "list")
    assert refused["ok"] is False
