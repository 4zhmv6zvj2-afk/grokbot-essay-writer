"""Layer 2. The constitution is conditional, and the top band is not invented."""

from helpers import ESSAY, pack, picked

from essay_writer.assignment_gate import assignment_gate, read_assignment
from essay_writer.gates import essay_gates
from essay_writer.paths import essay_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.review import essay_review
from essay_writer.stage_track import essay_stage
from essay_writer.validate import essay_pack_validate


def _open(module: str = ESSAY) -> str:
    essay_sequence_new(module, "draft")
    opened = essay_sequence_new(module, "confirm")
    assert opened["ok"] is True
    return opened["sequence_id"]


def test_daily_use_does_not_block_and_does_not_invent_a_band(workspace):
    seq = _open()
    report = read_assignment(seq)
    assert report["active"] is False
    assert report["mode"] == "daily"
    assert report["format"] is None
    assert report["question"] is None
    assert report["highest_band"] is None
    drafted = essay_stage(seq, "1", "draft", "")
    assert drafted["ok"] is True
    assert essay_stage(seq, "1", "confirm", "", **picked(drafted))["stored"] is True
    draft = essay_review(seq, "6", "PASS", "draft")
    assert draft["ok"] is True
    assert essay_review(seq, "6", "PASS", "confirm")["stored"] is True
    mechanical = essay_gates(seq, pack())
    assert mechanical["gates"][0]["name"] == "brief"
    assert mechanical["gates"][0]["passed"] is False


def test_brief_without_a_mark_scheme_asks_format_and_question(workspace):
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    seq = _open()
    seen = read_assignment(seq)
    assert seen["mode"] == "brief"
    assert seen["mark_scheme"] is False
    assert seen["format"] == "report"
    assert seen["highest_band"] is None
    empty = essay_stage(seq, "1", "draft", "")
    assert empty["ok"] is True, empty
    assert empty.get("basics_seeded") is True
    assert "band" not in str(empty.get("reason", "")).casefold()
    bare = essay_review(seq, "6", "PASS", "draft")
    assert bare["ok"] is False
    assert bare["refused"] == "review"
    assert "answers the assignment question" in bare["reason"]
    from essay_writer.specialists.grok_bot import basics_pass_lines

    note = "\n".join(basics_pass_lines(seq))
    drafted = essay_stage(seq, "1", "draft", note)
    assert drafted["ok"] is True
    assert essay_stage(seq, "1", "confirm", note, **picked(drafted))["stored"] is True
    assert essay_review(seq, "6", "PASS", "draft", constitution=note)["ok"] is True
    assert essay_review(seq, "6", "PASS", "confirm", constitution=note)["stored"] is True


def test_mark_scheme_aims_at_the_highest_band_and_prevails(workspace):
    folder = essay_dir("RPT6001AA")
    folder.mkdir(parents=True)
    (folder / "brief.md").write_text(
        "Genre: essay\nQuestion: Should the council publish the recycling figure?\n",
        encoding="utf-8",
    )
    (folder / "mark-scheme.md").write_text(
        "\n".join(
            [
                "Format: report",
                "High Distinction (80-100): the question is answered with evidence",
                "Merit (60-69): sound",
                "Pass (50-59): adequate",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    seq = _open("RPT6001AA")
    seen = read_assignment(seq)
    assert seen["mode"] == "both"
    assert seen["format"] == "report"
    assert seen["highest_band"] == "High Distinction"
    merely = "This is a report. Should the council publish the recycling figure? Pass."
    blocked = assignment_gate(seq, merely, seat="writer")
    assert blocked["ok"] is False
    assert "highest_band" in blocked["missing"]
    assert "highest band" in blocked["reason"].casefold()
    assert "High Distinction" in blocked["reason"]
    aimed = (
        "This is a report. Should the council publish the recycling figure? "
        "High Distinction."
    )
    assert assignment_gate(seq, aimed, seat="eqr")["ok"] is True
    plain = essay_pack_validate(seq, pack("RPT6001AA"), "draft")
    assert plain["refused"] == "assignment-gate"
    body = pack("RPT6001AA")
    body["sections"][0]["body"] = aimed
    checked = essay_pack_validate(seq, body, "draft")
    assert checked.get("refused") != "assignment-gate"


def test_mark_scheme_alone_does_not_invent_a_question(workspace):
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True)
    (folder / "rubric.md").write_text(
        "Distinction (70-100): evidence\nPass (50-59): adequate\n",
        encoding="utf-8",
    )
    seq = _open()
    seen = read_assignment(seq)
    assert seen["mode"] == "mark_scheme"
    assert seen["brief"] is False
    assert seen["highest_band"] == "Distinction"
    from essay_writer.specialists.grok_bot import basics_pass_lines

    seeded = essay_stage(seq, "1", "draft", "Pass.")
    assert seeded["ok"] is True
    assert seeded.get("basics_seeded") is True
    assert essay_stage(seq, "1", "draft", "\n".join(basics_pass_lines(seq)))["ok"] is True
