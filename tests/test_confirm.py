import json

from helpers import (
    CLARIFY_OPEN,
    ESSAY,
    TOPIC,
    open_sequence,
    pack,
    source,
    write_upload,
)

from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.revise import essay_revise
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word


def _research(seq):
    essay_research_summary(seq, TOPIC, "draft", [source()])
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert confirmed["stored"] is True
    return confirmed


def test_render_without_confirm_writes_nothing(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    target = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / f"{seq}.docx"
    missing = essay_pack_render_word(seq, pack(), None)
    assert missing["refused"] == "confirm"
    assert missing["wrote"] is False
    draft = essay_pack_render_word(seq, pack(), "draft")
    assert draft["wrote"] is False
    silent = essay_pack_render_word(seq, pack(), "confirm")
    # draft then confirm of a pack that was not validate-confirmed must not write
    assert silent["wrote"] is False
    assert not target.exists()


def test_confirm_without_draft_is_refused(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    result = essay_pack_render_word(seq, pack(), "confirm")
    assert result["refused"] == "confirm"
    assert result["wrote"] is False


def test_changed_pack_needs_a_fresh_draft(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    original = pack()
    changed = pack(title="A different title")
    essay_pack_validate(seq, original, "draft")
    moved = essay_pack_validate(seq, changed, "confirm")
    assert moved["refused"] == "confirm"
    essay_pack_validate(seq, original, "confirm")
    essay_pack_render_word(seq, original, "draft")
    rendered = essay_pack_render_word(seq, changed, "confirm")
    assert rendered["refused"] == "confirm"
    assert rendered["wrote"] is False
    assert not (workspace / "Essay-writer" / ESSAY / "output").exists()


def test_full_research_does_not_assume_leave_open(workspace):
    seq = open_sequence()
    refused = essay_research_full(seq, TOPIC, "draft", clarify_context=None)
    assert refused["refused"] == "clarify"
    assert "not assumed" in refused["reason"] or "not filled" in refused["reason"]
    partial = essay_research_full(
        seq,
        TOPIC,
        "draft",
        clarify_context={"objective": "Frame the corridor"},
    )
    assert partial["refused"] == "clarify"
    assert any("background" in item["reason"] for item in partial["issues"])
    opened = essay_research_full(seq, TOPIC, "draft", clarify_context=CLARIFY_OPEN)
    assert opened["ok"] is True
    assert opened["stored"] is False
    assert opened["clarify_is_not_evidence"] is True
    assert opened["clarify_context"]["objective"] == {"leave_open": True}


def test_file_change_after_draft_blocks_confirm(workspace):
    path = write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    path.write_text(path.read_text(encoding="utf-8") + "\nA later sentence.\n", encoding="utf-8")
    result = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert result["ok"] is False
    assert result["refused"] == "confirm"
    assert result["stored"] is False


def test_noted_conclusion_without_evidence_is_refused(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    bare = pack(sections=[{"heading": "Introduction", "body": "The corridor is exposed."}])
    result = essay_pack_validate(seq, bare, "draft")
    assert result["passed"] is False
    assert any(item["code"] == "invent-forbid" for item in result["blockers"])


def test_open_conclusion_can_stand_without_a_citation(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    # Research confirmed the source, but the pack does not cite it and stays open.
    open_pack = pack(
        conclusion="open",
        sections=[{"heading": "Introduction", "body": "The corridor is exposed."}],
        sources=[],
    )
    draft = essay_pack_validate(seq, open_pack, "draft")
    assert draft["passed"] is True
    assert any(item["code"] == "conclusion" for item in draft["notes"])


def test_missing_conclusion_is_not_chosen_by_the_door(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    body = pack()
    del body["conclusion"]
    result = essay_pack_validate(seq, body, "draft")
    assert result["passed"] is False
    assert any(item["code"] == "conclusion" for item in result["blockers"])


def test_revise_does_not_write_word(workspace):
    write_upload(workspace)
    seq = open_sequence()
    _research(seq)
    note = essay_revise(seq, "Tighten the opening. Do not add sources.", "draft")
    assert note["wrote"] is False
    assert note["word_rewritten"] is False
    done = essay_revise(seq, "Tighten the opening. Do not add sources.", "confirm")
    assert done["stored"] is True
    assert done["wrote"] is False
    invented = essay_revise(seq, "Cite (Patel, 2019) as well.", "draft")
    assert invented["refused"] == "invent-forbid"
    assert not list((workspace / "Essay-writer" / ESSAY).glob("output/*.docx"))


def test_originals_do_not_cross(workspace):
    from essay_writer.originals import essay_originals

    write_upload(workspace, ESSAY)
    write_upload(workspace, "MOD1011AA", name="secret.md", text="other essay")
    listed = essay_originals(ESSAY, "list")
    assert [item["name"] for item in listed["uploads"]] == ["smith.md"]
    escaped = essay_originals(ESSAY, "read", "../MOD1011AA/secret.md")
    assert escaped["ok"] is False
    assert "secret" not in json.dumps(escaped)
