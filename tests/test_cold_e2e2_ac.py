"""Cold E2E #2. Stable ids: AC1, AC2, AC3, AC4.

Typed Confirm re-shows the card and does not write. The Stage 1 question
gate reads Title and assignment ask. Plan revisit cites the opened year only.
"""

from helpers import ESSAY, OTHER, open_sequence, picked, plant_gathered_source

from essay_writer.assignment_gate import _question_of, assignment_gate, read_assignment
from essay_writer.cite_open import cite_look
from essay_writer.paths import essay_dir, work_dir
from essay_writer.shells import front_office_call
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

TITLE_QUESTION = "How should the firm manage the corridor?"
ASK_QUESTION = "Should the council publish the recycling figure?"


def _pointer_bytes(seq: str) -> bytes:
    path = work_dir(seq) / "tracking" / "stage.json"
    assert path.is_file()
    return path.read_bytes()


def _look_body(seq: str, stage: str) -> str:
    note = (work_dir(seq) / "tracking" / f"{stage}.md").read_text(encoding="utf-8")
    _rules, heading, body = note.partition("## Working look")
    if heading != "## Working look":
        _rules, heading, body = note.partition("## Final look")
    assert heading in {"## Working look", "## Final look"}
    return body


def test_ac1_typed_confirm_represents_the_card_and_does_not_write(workspace):
    """A typed Confirm, yes, or ok shows the waiting card again. It does not save."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": look},
    )
    assert draft["card"]["kind"] == "confirm"
    assert draft["card"]["digest"] == draft["digest"]
    assert draft["stored"] is False
    before = _pointer_bytes(seq)
    assert load_pointer(seq)["saved"] == []
    assert load_pointer(seq)["current"] == "1"

    for typed in ("Confirm", "yes", "ok", "Yes", "OK"):
        spoken = front_office_call(
            "essay.stage",
            {"essay_id": seq, "stage": "1", "confirmPhase": "confirm", "look": typed},
        )
        assert spoken["ok"] is False
        assert spoken["refused"] == "confirm-card"
        assert spoken["stored"] is not True
        assert spoken.get("advanced") is not True
        assert spoken["wrote"] is False
        card = spoken["card"]
        assert card["kind"] == "confirm"
        assert card["digest"] == draft["digest"]
        assert spoken["digest"] == draft["digest"]
        assert card["actions"][0] == {"id": "confirm", "label": "Confirm"}
        assert "Confirm card" in spoken["next"]
        assert load_pointer(seq)["saved"] == []
        assert load_pointer(seq)["current"] == "1"
        assert _pointer_bytes(seq) == before

        spoken = front_office_call(
            "essay.stage",
            {
                "essay_id": seq,
                "stage": "1",
                "confirmPhase": "confirm",
                "look": look,
                "cardAction": typed,
                "cardDigest": draft["digest"],
            },
        )
        assert spoken["ok"] is False
        assert spoken["refused"] == "confirm-card"
        assert spoken["card"]["digest"] == draft["digest"]
        assert spoken["stored"] is not True
        assert load_pointer(seq)["saved"] == []
        assert _pointer_bytes(seq) == before


def test_ac2_card_confirm_still_writes_and_advances(workspace):
    """confirmPhase confirm plus the card action and digest still saves."""
    seq = open_sequence()
    look = "The task is a short report."
    draft = essay_stage(seq, "1", "draft", look)
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "cardAction": "confirm",
            "cardDigest": draft["digest"],
        },
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["current"] == "2"
    assert "1" in load_pointer(seq)["saved"]
    pointer = (work_dir(seq) / "tracking" / "stage.json").read_text(encoding="utf-8")
    assert '"current": "2"' in pointer
    assert "1" in pointer


def test_ac3_stage1_gate_accepts_title_and_assignment_ask(workspace):
    """Title or assignment ask is the question. The brief file is not rewritten."""
    assert _question_of("The corridor is the topic of this unlabeled brief.\n") is None
    assert (
        _question_of(
            "Title: Weekly notes\nQuestion: How do chokepoints constrain the corridor?\n"
        )
        == "How do chokepoints constrain the corridor?"
    )

    title_only = f"Title: {TITLE_QUESTION}\n"
    ask_only = f"Genre: report\nAssignment ask: {ASK_QUESTION}\n"
    heading = "Title\nHow do chokepoints constrain the corridor?\n"
    _assert_stage1_pass(ESSAY, title_only, TITLE_QUESTION)
    _assert_stage1_pass(OTHER, ask_only, ASK_QUESTION)
    _assert_stage1_pass("RPT6001AA", heading, "How do chokepoints constrain the corridor?")


def _assert_stage1_pass(module: str, brief: str, question: str) -> None:
    from essay_writer.specialists.grok_bot import basics_pass_lines

    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "brief.md"
    path.write_text(brief, encoding="utf-8")
    before = path.read_bytes()
    assert not any(line.strip().casefold().startswith("question:") for line in brief.splitlines())
    seq = open_sequence(module)
    seen = read_assignment(seq)
    assert seen["question"] == question
    missed = assignment_gate(seq, "Saved.", seat="grok_bot")
    assert missed["ok"] is False
    assert "question" in missed["missing"]
    look = "\n".join(basics_pass_lines(seq))
    assert question in look
    passed = assignment_gate(seq, look, seat="grok_bot")
    assert passed["ok"] is True, passed
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["ok"] is True, draft
    saved = essay_stage(seq, "1", "confirm", **picked(draft))
    assert saved["stored"] is True, saved
    assert path.read_bytes() == before
    assert "Question:" not in path.read_text(encoding="utf-8")


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


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Length "
        + str(len(stream)).encode()
        + b">>stream\n"
        + stream
        + b"\nendstream\nendobj\ntrailer<<>>\n%%EOF\n"
    )


def test_ac4_plan_revisit_cites_the_opened_year_only(workspace):
    """The plan look uses the opened PDF year. It does not invent a second year."""
    seq = open_sequence()
    _save_through(seq, "4b")
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "hasan-sarker.pdf").write_bytes(_pdf("Hasan and Sarker (2023) Corridor risk"))
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    research = state.setdefault("research", {})
    summary = research.setdefault("summary", {"sources": []})
    summary["sources"].append(
        {
            "id": "hasan",
            "author": "Hasan, M. and Sarker, S.",
            "year": "2025",
            "title": "Corridor risk",
            "locator": f"uploads/{ESSAY}/hasan-sarker.pdf",
        }
    )
    save_state(seq, state)

    gloss = "Hasan and Sarker (2025\u2026 treated as 2023)"
    assert cite_look(seq, f"The plan still holds. {gloss} shows the risk.") == (
        "The plan still holds. Hasan and Sarker (2023) shows the risk."
    )
    assert cite_look(seq, "(Hasan and Sarker, 2025... treated as 2023)") == "(Hasan and Sarker, 2023)"
    assert "treated as" not in cite_look(seq, gloss).casefold()

    look = f"The plan still holds. {gloss} shows the corridor risk."
    opened = essay_stage(seq, "3", "draft", look)
    assert opened["ok"] is True, opened
    body = _look_body(seq, "3")
    assert "Hasan and Sarker (2023)" in body
    assert "treated as" not in body.casefold()
    assert "2025" not in body
    saved = essay_stage(seq, "3", "confirm", **picked(opened))
    assert saved["stored"] is True, saved
    final = _look_body(seq, "3")
    assert "Hasan and Sarker (2023)" in final
    assert "treated as" not in final.casefold()
    assert "2025" not in final
