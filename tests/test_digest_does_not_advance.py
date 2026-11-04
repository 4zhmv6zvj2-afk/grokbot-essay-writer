"""Digest does not advance the stage. Stable ids: AC1, AC2, AC3, AC4, AC5.

Stage 5 is the report or essay argument. A paper-note digest does not
auto-advance. Stage 6 starts only after the north-star gate passes, with
no Confirm card and no Basics checklist in the quiet chat.
"""

from pathlib import Path

from helpers import ESSAY, open_sequence, picked, plant_gathered_source

from essay_writer.assignment_gate import north_star_gate
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch, stage_host_launch
from essay_writer.draft_from_review import argument_blockers, notes_shaped
from essay_writer.late_chain import STAGE6_OPEN
from essay_writer.paths import essay_dir, work_dir
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists.grok_bot import basics_pass_lines, front_office_call
from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage, load_pointer

QUESTION = "How should Inditex manage its supply chain?"
SCHEME = (
    "High Distinction (80-100): the answer is an argument about the decision, "
    "not a stack of paper notes.\n"
)
NOTE = (
    "Smith, J. (2020) wrote about Zara and Inditex.\n"
    "The review says proximity sourcing keeps Zara's lead time short for Inditex.\n"
    "It judges the aim, the method, and a single-firm limit.\n"
    "Inditex should manage its supply chain. Format: report. High Distinction.\n"
)
NOTES = (
    "Tokatli (2008)\n"
    "Zara proximity is described as a case, not as a decision.\n"
    "\n"
    "Ferdows (2004)\n"
    "Inditex factories are described. The note does not decide the chain.\n"
    "\n"
    "Aim: describe Zara.\n"
    "Method: one case.\n"
    "Scope: Inditex stores.\n"
    "Limitations: the note does not say how Inditex should manage its supply chain.\n"
    "\n"
    "Format: report.\n"
    f"Question: {QUESTION}\n"
    "High Distinction.\n"
)
ARGUMENT = (
    "Inditex should manage its supply chain by keeping Zara's proximity sourcing "
    "and dropping suppliers that miss the lead time. This report argues that the "
    "decision is speed. Format: report. High Distinction. "
    f"{QUESTION}"
)
MISSES = (
    "The firm should shorten lead times and drop the suppliers that miss them. "
    "The decision is speed, and the reason is the customer wait."
)


def _brief() -> None:
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Genre: report\nQuestion: {QUESTION}\n",
        encoding="utf-8",
    )
    (folder / "mark-scheme.md").write_text(SCHEME, encoding="utf-8")


def _opening(seq: str) -> str:
    return "\n".join(basics_pass_lines(seq))


def _through(seq: str) -> None:
    look = _opening(seq)
    for stage in ("1", "2", "3", "4a", "4b"):
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved


def _ready(seq: str) -> str:
    return _opening(seq) + "\n" + ARGUMENT


def _quiet_chat(body: dict) -> None:
    for key in ("chat", "next", "confirm_line"):
        text = body.get(key) or ""
        assert "Walk this Basics checklist" not in text
        assert "Apply every line" not in text
        assert "Basics checklist" not in text
    assert body.get("checklist_in_chat") is False


def test_ac1_digest_does_not_auto_advance(workspace):
    """Inditex/Zara bar: paper notes are not the stage 5 argument."""
    assert notes_shaped(NOTES) is True
    assert notes_shaped(ARGUMENT) is False
    _brief()
    seq = open_sequence()
    _through(seq)
    note = work_dir(seq) / "output" / "reviews" / "src-zara.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(NOTE, encoding="utf-8")
    pasted = NOTE
    soft = argument_blockers(
        seq,
        [{"heading": "Purpose", "body": pasted}],
        [{"paper_id": "src-zara", "markdown": NOTE}],
    )
    assert soft
    assert soft[0]["code"] == "argument"
    assert "pastes the note" in soft[0]["reason"]
    assert "source material" in soft[0]["reason"]

    digest = essay_stage(seq, "5", "draft", _opening(seq) + "\n" + NOTES)
    assert digest["ok"] is False, digest
    assert digest["refused"] == "argument"
    assert digest["stored"] is False
    assert digest["advanced"] is False
    assert digest["wrote"] is False
    assert "started" not in digest
    assert "card" not in digest
    assert load_pointer(seq)["current"] == "5"
    assert "5" not in load_pointer(seq)["saved"]
    assert not (work_dir(seq) / "tracking" / "5.md").is_file()
    _quiet_chat(digest)

    pasted_look = essay_stage(seq, "5", "draft", _opening(seq) + "\n" + pasted)
    assert pasted_look["ok"] is False, pasted_look
    assert pasted_look["refused"] == "argument"
    assert pasted_look["stored"] is False
    assert pasted_look["advanced"] is False
    assert load_pointer(seq)["current"] == "5"
    assert "pastes the note" in pasted_look["reason"] or "source material" in pasted_look["reason"]
    assert pasted_look["north_star"]["passed"] is True


def test_ac2_failed_north_star_does_not_store_or_advance(workspace):
    _brief()
    seq = open_sequence()
    _through(seq)
    gate = north_star_gate(seq, MISSES)
    assert gate["passed"] is False
    assert gate["format_met"] is False
    assert gate["does_assignment"] is False
    assert gate["mark_scheme_met"] is False
    held = essay_stage(seq, "5", "draft", MISSES)
    assert held["ok"] is False, held
    assert held["refused"] == "north-star"
    assert held["stored"] is False
    assert held["advanced"] is False
    assert held["wrote"] is False
    assert held["north_star"]["passed"] is False
    assert "started" not in held
    assert "card" not in held
    pointer = load_pointer(seq)
    assert pointer["current"] == "5"
    assert "5" not in pointer["saved"]
    assert pointer["current"] != "6"
    assert not (work_dir(seq) / "tracking" / "5.md").is_file()
    _quiet_chat(held)


def test_ac3_quiet_chat_still_records_the_gate(workspace):
    _brief()
    seq = open_sequence()
    _through(seq)
    spoken = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "5", "confirmPhase": "draft", "look": _ready(seq)},
    )
    assert spoken["ok"] is True, spoken
    assert spoken["stored"] is True
    assert spoken["quiet"] is True
    _quiet_chat(spoken)
    assert spoken["chat"] == STAGE6_OPEN
    assert spoken["next"] == STAGE6_OPEN
    assert spoken["north_star"]["passed"] is True
    assert spoken["north_star"]["mark_scheme_met"] is True
    assert spoken["north_star"]["format_met"] is True
    assert spoken["north_star"]["does_assignment"] is True
    assert "Walk this Basics checklist" in spoken["rules"]
    assert "Walk this Basics checklist" not in spoken["chat"]
    for line in spoken.get("status") or []:
        assert "Basics checklist" not in line
        assert "Apply every line" not in line


def test_ac4_pass_starts_stage6_with_no_confirm_card(workspace):
    _brief()
    seq = open_sequence()
    _through(seq)
    assert advances_without_confirm("5") == "6"
    assert stage_uses_confirm_card("5") is False
    early = essay_stage(seq, "5", "confirm", _ready(seq), cardAction="confirm")
    assert early["ok"] is False
    assert early["refused"] == "confirm-card"
    assert early.get("advanced") is not True
    assert load_pointer(seq)["current"] == "5"
    assert "card" not in early
    done = essay_stage(seq, "5", "draft", _ready(seq))
    assert done["stored"] is True, done
    assert done["advanced"] is True
    assert done["current"] == "6"
    assert done["started"]["stage"] == "6"
    assert "card" not in done
    assert done["north_star"]["passed"] is True
    final = (work_dir(seq) / "tracking" / "5.md").read_text(encoding="utf-8")
    assert "Status: final" in final
    assert "5" in load_pointer(seq)["saved"]
    again = essay_stage(seq, "5", "confirm", _ready(seq), cardAction="confirm")
    assert again["ok"] is False
    assert load_pointer(seq)["current"] == "6"


def test_ac5_build_covered_shares_handlers_and_stage_path():
    assert HANDLERS["essay.stage"] is essay_stage
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    item = stage_settings("5")
    build = stage_launch("5")
    cursor = cursor_stage_launch("5")
    host = stage_host_launch("5")
    assert build["source"] == "essay_writer.stage_llm.stage_settings"
    assert cursor["source"] == build["source"]
    assert build["settings"]["rules"] == item["rules"]
    assert cursor["settings"]["rules"] == item["rules"]
    assert host["settings"]["rules"] == item["rules"]
    assert build["settings"]["prompt_overlay"] == item["prompt_overlay"]
    assert cursor["settings"]["prompt_overlay"] == item["prompt_overlay"]
    office = Path(stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    cursor_src = Path(cursor_stage_launch.__code__.co_filename).read_text(encoding="utf-8")
    assert "def essay_stage" not in office
    assert "def north_star_gate" not in office
    assert "def argument_blockers" not in office
    assert "def essay_stage" not in cursor_src
    assert "def north_star_gate" not in cursor_src
    assert "stage_settings" in office
    assert "stage_settings" in cursor_src
