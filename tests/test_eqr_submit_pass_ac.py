"""Submit-file review pass. A false or stale pass does not unlock that Word file.

AC1. A pass with no submit hash, or a pass whose file changed, does not unlock
the final Word file or the final step.
AC2. A pass unlocks only after citations are on that submit file.
AC3. Stage 6 answers the assignment question only. It does not check format,
rewrite the draft, or fill gaps.
AC4. The writer seat cannot clear the review.
AC5. Front office stage 9 stops without marking again.
Build covered: Cursor and Grok Build call submit_pass_unlocked.
"""

import inspect
import json

from docx import Document
from helpers import ESSAY, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.build_office import eqr_pass_unlock as build_unlock
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.cursor_office import eqr_pass_unlock as cursor_unlock
from essay_writer.late_chain import finish_stage_reply
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_summary
from essay_writer.review import (
    PERSON_BLOCK,
    eqr_verdict,
    essay_review,
    writer_clears_left,
)
from essay_writer.specialists.eqr import (
    HIGHEST_BAND,
    REVIEW_PROMPT,
    answers_assignment_question,
    stage6_scope,
    submit_pass_unlocked,
)
from essay_writer.specialists.grok_bot import front_office_stage9
from essay_writer.spine import final_review
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import student_surface_hits
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

CONSTITUTION = "This is a report. How do chokepoints constrain the corridor?"
QUESTION = "Chokepoints constrain the corridor."


def _ready(workspace) -> str:
    write_upload(workspace)
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    return seq


def _docx(path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    for line in lines:
        document.add_paragraph(line)
    document.save(str(path))


def _submit(seq: str):
    return work_dir(seq) / "output" / f"{seq}.docx"


def _review(seq: str, stage: str, verdict: str = "PASS") -> dict:
    drafted = essay_review(seq, stage, verdict, "draft", constitution=CONSTITUTION)
    assert drafted["ok"] is True, drafted
    stored = essay_review(seq, stage, verdict, "confirm", constitution=CONSTITUTION)
    assert stored["stored"] is True, stored
    return stored


def _word(seq: str, phase: str) -> dict:
    return essay_pack_render_word(seq, pack(), phase, stage="9")


def test_false_and_stale_pass_cannot_unlock_the_submit_file(workspace):
    """AC1 and AC2. No citations refuses the pass. A changed file, then a pass with no hash, stays locked."""
    seq = _ready(workspace)
    path = _submit(seq)
    _docx(path, ["This is a report. How do chokepoints constrain the corridor?"])
    refused_review = essay_review(seq, "9", "PASS", "draft", constitution=CONSTITUTION)
    assert refused_review["ok"] is False
    assert refused_review["reason"] == "The opened Word file has no citations. Nothing was recorded."
    assert refused_review.get("stored") is not True
    bare = submit_pass_unlocked(seq)
    assert bare["unlocked"] is False
    assert bare["reason"] == "missing"
    assert eqr_verdict(seq, "9") is None
    preview = _word(seq, "draft")
    assert preview["wrote"] is False
    assert preview["eqr"] != "PASS"
    blocked = _word(seq, "confirm")
    assert blocked["ok"] is False
    assert blocked["wrote"] is False
    assert blocked["refused"] == "eqr"
    assert not blocked.get("stored")
    text, verdict = final_review(seq)
    assert text == "The Word file has no citations. That block is shown before the final Word."
    assert verdict == "citations"

    _docx(
        path,
        ["This is a report. How do chokepoints constrain the corridor? (Smith, 2020)."],
    )
    _review(seq, "9")
    fresh = submit_pass_unlocked(seq)
    assert fresh["unlocked"] is True
    assert fresh["reason"] == "pass"
    assert eqr_verdict(seq, "9") == "PASS"
    assert final_review(seq) == (None, "PASS")
    written = _word(seq, "confirm")
    assert written["wrote"] is True, written
    after_write = submit_pass_unlocked(seq)
    assert after_write["unlocked"] is False
    assert after_write["reason"] == "stale"
    assert _word(seq, "confirm")["wrote"] is False

    state = load_state(seq)
    state["eqr"]["9"]["submit_sha256"] = ""
    state["eqr"]["9"]["word_opened"] = False
    save_state(seq, state)
    false_pass = submit_pass_unlocked(seq)
    assert false_pass["unlocked"] is False
    assert false_pass["reason"] == "false"
    assert eqr_verdict(seq, "9") is None
    assert _word(seq, "confirm")["submit_pass"] == "false"
    assert final_review(seq)[1] != "PASS"


def test_stage6_answers_the_question_only(workspace):
    """AC3. Format is not the stage 6 check. The draft file is not rewritten."""
    seq = _ready(workspace)
    assert stage6_scope() == {
        "judges": "answers-the-question",
        "format": False,
        "freeflow": False,
        "gap_fill": False,
    }
    assert "format" not in inspect.getsource(answers_assignment_question).casefold()
    assert answers_assignment_question(seq, "Format: report. The margins are wide.") is False
    assert answers_assignment_question(seq, QUESTION) is True
    sentence = "Stage 6 answers only whether the draft answers the assignment question."
    assert sentence in REVIEW_PROMPT
    assert "It does not check format." in REVIEW_PROMPT
    assert "It does not rewrite the draft." in REVIEW_PROMPT
    assert "It does not fill gaps." in REVIEW_PROMPT
    assert "Format and citations stay with the writer." in REVIEW_PROMPT
    assert student_surface_hits(REVIEW_PROMPT) == []
    for row in ("argument", "evidence", "critical thinking"):
        assert row not in HIGHEST_BAND.casefold()

    path = _submit(seq)
    _docx(path, ["Format: report. The margins are wide."])
    before = path.read_bytes()
    refused = essay_review(seq, "6", "PASS", "draft", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused["stored"] is not True
    assert "answers the assignment question" in refused["reason"]
    assert "format" not in refused["reason"].casefold()
    assert path.read_bytes() == before
    assert "eqr" not in load_state(seq)

    _docx(path, [QUESTION])
    _review(seq, "6")
    assert eqr_verdict(seq, "6") == "PASS"
    assert submit_pass_unlocked(seq)["unlocked"] is False


def test_writer_cannot_self_clear(workspace):
    """AC4. The writer seat does not record a pass, and it does not unlock one."""
    assert writer_clears_left() == 0
    seq = _ready(workspace)
    before = json.dumps(load_state(seq).get("eqr"))
    refused = essay_review(seq, "9", "PASS", "confirm", seat="writer", constitution=CONSTITUTION)
    assert refused["ok"] is False
    assert refused["refused"] == "seat"
    assert refused["writer_clears_left"] == 0
    assert PERSON_BLOCK in refused["reason"]
    assert json.dumps(load_state(seq).get("eqr")) == before
    assert submit_pass_unlocked(seq)["unlocked"] is False
    assert writer_clears_left() == 0


def test_front_office_stage9_does_not_remark(workspace, monkeypatch):
    """AC5. Stage 9 stops. It does not mark, rewrite, or fill gaps."""
    seq = _ready(workspace)
    path = _submit(seq)
    _docx(path, [f"This is a report. {QUESTION} (Smith, 2020)."])
    _review(seq, "9")
    state = load_state(seq)
    state["eqr"]["9"]["submit_sha256"] = "0" * 64
    save_state(seq, state)
    seen = json.dumps(load_state(seq).get("eqr"), sort_keys=True)

    def _boom(*_args, **_kwargs):
        raise AssertionError("stage 9 marked again")

    monkeypatch.setattr("essay_writer.review.essay_review", _boom)
    stop = front_office_stage9(seq)
    assert stop["stopped"] is True
    assert stop["remarked"] is False
    assert stop["freeflow"] is False
    assert stop["gap_fill"] is False
    assert stop["reason"] == "stale"
    body = finish_stage_reply({"ok": True, "stored": True, "next": "Kept."}, seq, "9", armed=True)
    assert body["fo_stop"] is True
    assert body["remarked"] is False
    assert body["freeflow"] is False
    assert body["gap_fill"] is False
    assert body["submit_pass"] == "stale"
    assert json.dumps(load_state(seq).get("eqr"), sort_keys=True) == seen
    source = inspect.getsource(front_office_stage9)
    assert "essay_review" not in source
    assert "build_findings" not in source
    for office in (cursor_unlock, build_unlock):
        assert office(seq)["reason"] == "stale"
        assert "submit_pass_unlocked" in office.__code__.co_names


def test_cursor_and_grok_build_share_the_unlock(workspace):
    """Build covered. One unlock function, and the same stage 6 review sentence."""
    seq = _ready(workspace)
    cursor = cursor_stage_launch("eqr")
    build = stage_launch("eqr")
    assert cursor["settings"]["prompt_overlay"] == build["settings"]["prompt_overlay"]
    assert "Stage 6 answers only whether the draft answers the assignment question." in cursor["settings"]["rules"]
    assert cursor["settings"]["rules"] == build["settings"]["rules"]
    assert cursor_unlock(seq) == build_unlock(seq) == submit_pass_unlocked(seq)
    assert "submit_pass_unlocked" in cursor_unlock.__code__.co_names
    assert "submit_pass_unlocked" in build_unlock.__code__.co_names
