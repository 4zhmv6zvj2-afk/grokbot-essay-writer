"""Body-cite gate. Stable ids: AC1–AC5.

AC1: an FO-added gathered cite that fails claim-fit does not land in the body
or the reference list.
AC2: an FO-added cite the student did not ask for waits for an explicit yes.
AC3: after the student rejects a cite, a failed swap does not put it back.
AC4: the gate is the writer path for stages 5, 6, 7, and 8, not a stage-6 branch.
AC5: Build covered. Cursor and Grok Build share the stage row and this gate.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from helpers import open_sequence, picked

from essay_writer.build_office import stage_launch
from essay_writer.cite_fit import apply_body_cites, load_record
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.paths import module_code
from essay_writer.revise import essay_revise
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, front_office_call
from essay_writer.specialists.writer import BODY_CITE_STAGES, land_body_cites
from essay_writer.stage_track import _build_stage_body, _note_look, essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.textutil import prepare_word_citations, reference_line
from essay_writer.word import word_manifest
from essay_writer.writing_basics import STAGE_ORDER

REPO = Path(__file__).resolve().parents[1]
STUDENT = "Privacy risk reduces willingness to disclose personal data."
TOPIC_ONLY = "Surveys of privacy and personal data on government websites discuss trust."
FITS = (
    "Privacy risk reduces willingness to disclose personal data when people use a public site."
)


def _source(seq: str, ident: str, author: str, year: str, quote: str) -> dict:
    module = module_code(seq)
    return {
        "id": ident,
        "author": author,
        "year": year,
        "title": author.split(",")[0],
        "locator": f"uploads/{module}/{ident}.md",
        "quote": quote,
        "origin": "upload",
    }


def _plant(seq: str) -> None:
    state = load_state(seq)
    state["research"] = {
        "summary": {
            "sources": [
                _source(seq, "peng", "Peng, W.", "2018", TOPIC_ONLY),
                _source(seq, "oconnor", "O'Connor, C.", "2021", FITS),
                _source(seq, "beldad", "Beldad, A.", "2019", FITS),
                _source(seq, "yamoah", "Yamoah, F.", "2020", TOPIC_ONLY),
            ]
        },
        "full": None,
    }
    save_state(seq, state)


def _walk(seq: str, stop: str, *, stage3: str, start: str | None = None) -> None:
    begun = start is None
    for stage in STAGE_ORDER:
        if not begun:
            if stage == start:
                begun = True
            else:
                continue
        if stage == stop:
            return
        look = stage3 if stage == "3" else "Saved from the brief."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, (stage, draft)
        if stage == "5":
            assert draft["stored"] is True, draft
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, (stage, saved)


def _cited(name: str, year: str) -> str:
    return f"{STUDENT.rstrip('.')} ({name}, {year})."


def _write_paper(source: dict) -> None:
    from essay_writer.paths import workspace_root

    locator = Path(source["locator"])
    path = workspace_root() / locator
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{source['author']} ({source['year']}) {source['title']}.\n{source['quote']}\n",
        encoding="utf-8",
    )


def _refs(sources: list) -> str:
    return "\n".join(reference_line(source) for source in sources if isinstance(source, dict))


def test_ac1_fo_added_cite_that_fails_claim_fit_does_not_land(workspace):
    """AC1. Peng is gathered and on the same topic. The claim does not match, so it stays out."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=STUDENT)
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "5", "confirmPhase": "draft", "look": _cited("Peng", "2018")},
    )
    assert draft["ok"] is True, draft
    assert draft["stored"] is True
    look = _note_look(seq, "5") or ""
    assert "Peng" not in look
    assert "privacy risk reduces willingness" in look.casefold()
    held = {item["token"]: item["reason"] for item in draft["cite_held"]}
    assert held["peng, 2018"] == "claim-fit"
    assert "cite_ask" not in draft
    assert load_record(seq)["withheld"] == ["peng, 2018"]

    peng = _source(seq, "peng", "Peng, W.", "2018", TOPIC_ONLY)
    _write_paper(peng)
    from essay_writer.invent import gather_sources

    gathered, issues = gather_sources(seq, [peng])
    assert issues == []
    assert gathered[0]["author"] == "Peng, W."
    sources, sections = prepare_word_citations(
        seq,
        [peng],
        [{"heading": "Findings", "body": _cited("Peng", "2018")}],
    )
    assert "Peng" not in _refs(sources)
    _pack, report = word_manifest(
        seq,
        {
            "essay_id": seq,
            "title": "Privacy risk",
            "referencing": "harvard",
            "conclusion": "open",
            "sections": [{"heading": "Findings", "body": _cited("Peng", "2018")}],
            "sources": [peng],
        },
    )
    assert "Peng" not in " ".join(report["references"])
    assert "Peng" not in " ".join(section["body"] for section in report["sections"])
    assert "withhold_body_cites" in inspect.getsource(prepare_word_citations)


def test_ac2_fo_added_cite_needs_student_ok_before_it_lands(workspace):
    """AC2. O'Connor supports the sentence. It still waits until the student says yes."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=STUDENT)
    asked = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "5",
            "confirmPhase": "draft",
            "look": _cited("O'Connor", "2021"),
        },
    )
    assert asked["stored"] is True, asked
    assert "O'Connor" not in (_note_look(seq, "5") or "")
    assert asked["cite_ask"] == "Do you want O'Connor (2021) added? You did not ask for this paper."
    assert asked["cite_ask"] in asked["next"]
    assert "o'connor, 2021" in load_record(seq)["withheld"]

    again = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": _cited("O'Connor", "2021"),
        },
    )
    assert again["ok"] is True, again
    assert "O'Connor" not in (_note_look(seq, "6") or "")
    assert "cite_ask" in again

    allowed = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": _cited("O'Connor", "2021"),
            "answers": "Yes, add O'Connor.",
        },
    )
    assert allowed["ok"] is True, allowed
    landed = _note_look(seq, "6") or ""
    assert "(O'Connor, 2021)" in landed
    assert "cite_ask" not in allowed
    assert "o'connor, 2021" not in load_record(seq)["withheld"]
    sources, sections = prepare_word_citations(
        seq,
        [_source(seq, "oconnor", "O'Connor, C.", "2021", FITS)],
        [{"heading": "Findings", "body": _cited("O'Connor", "2021")}],
    )
    assert "O'Connor" in _refs(sources)


def test_ac3_failed_swap_does_not_restore_rejected_cite(workspace):
    """AC3. Beldad was rejected. Yamoah does not fit. Beldad is not put back."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    landed = essay_stage(seq, "5", "draft", _cited("Beldad", "2019"))
    assert landed["stored"] is True, landed
    assert "(Beldad, 2019)" in (_note_look(seq, "5") or "")
    assert "cite_held" not in landed

    swapped = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": (
                "Privacy risk reduces willingness to disclose personal data "
                "(Beldad, 2019; Yamoah, 2020)."
            ),
            "answers": "swap Beldad for Yamoah",
        },
    )
    assert swapped["ok"] is True, swapped
    look = _note_look(seq, "6") or ""
    assert "Beldad" not in look
    assert "Yamoah" not in look
    assert "privacy risk reduces willingness" in look.casefold()
    held = {item["token"]: item["reason"] for item in swapped["cite_held"]}
    assert held["beldad, 2019"] == "rejected"
    assert held["yamoah, 2020"] == "claim-fit"
    withheld = set(load_record(seq)["withheld"])
    assert "beldad, 2019" in withheld
    assert "yamoah, 2020" in withheld
    sources, sections = prepare_word_citations(
        seq,
        [
            _source(seq, "beldad", "Beldad, A.", "2019", FITS),
            _source(seq, "yamoah", "Yamoah, F.", "2020", TOPIC_ONLY),
        ],
        [
            {
                "heading": "Findings",
                "body": (
                    "Privacy risk reduces willingness to disclose personal data "
                    "(Beldad, 2019; Yamoah, 2020)."
                ),
            }
        ],
    )
    body = sections[0]["body"]
    refs = _refs(sources)
    assert "Beldad" not in body and "Beldad" not in refs
    assert "Yamoah" not in body and "Yamoah" not in refs


def test_ac4_gate_is_shared_writer_path_not_stage6_only(workspace):
    """AC4. Stages 5, 6, 7, and 8 use one writer function. Stage 6 is not a private branch."""
    assert BODY_CITE_STAGES == frozenset({"5", "6", "7", "8"})
    assert "4a" not in BODY_CITE_STAGES
    assert "4b" not in BODY_CITE_STAGES
    assert "9" not in BODY_CITE_STAGES
    gate_source = inspect.getsource(apply_body_cites)
    role_source = inspect.getsource(land_body_cites)
    stage_source = inspect.getsource(_build_stage_body)
    assert '== "6"' not in gate_source
    assert '== "6"' not in role_source
    assert "stage in BODY_CITE_STAGES" in stage_source
    assert "land_body_cites" in stage_source
    assert "land_body_cites" in inspect.getsource(essay_revise)
    assert "withhold_body_cites" in inspect.getsource(prepare_word_citations)
    assert "withhold_body_cites" in inspect.getsource(word_manifest)
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert front_office()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]

    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=STUDENT)
    proposal = _cited("Peng", "2018")
    reasons = []
    for stage in ("5", "6", "7", "8"):
        result = land_body_cites(seq, stage, proposal)
        assert "Peng" not in result["text"]
        assert result["applied"] is True
        reasons.append(result["held"][0]["reason"])
    assert reasons == ["claim-fit", "claim-fit", "claim-fit", "claim-fit"]

    untouched = _cited("Peng", "2018")
    for stage in ("4a", "4b", "9"):
        skipped = land_body_cites(seq, stage, untouched)
        assert skipped["applied"] is False
        assert skipped["text"] == untouched

    _walk(seq, "8", stage3=STUDENT, start="5")
    stage8 = essay_stage(seq, "8", "draft", proposal)
    assert stage8["ok"] is True, stage8
    assert "Peng" not in (_note_look(seq, "8") or "")
    assert stage8["cite_held"][0]["reason"] == "claim-fit"


def test_excerpt_supports_a_sentence_that_does_not_repeat_it():
    """A locked excerpt can support a sentence that adds its own words."""
    from essay_writer.cite_fit import same_idea

    paraphrase = (
        "Privacy risk reduces willingness to disclose personal data "
        "on a public website that feels unsafe."
    )
    assert same_idea(paraphrase, FITS) is True
    assert same_idea(STUDENT, TOPIC_ONLY) is False


def test_ac5_build_covered_cursor_and_grok_build(workspace):
    """AC5. Build covered. The stage row is shared, and fast stays off."""
    for stage in ("5", "6", "7", "8"):
        cursor = cursor_stage_launch(stage)
        build = stage_launch(stage)
        assert cursor["settings"] is build["settings"] or (
            cursor["settings"]["model"] == build["settings"]["model"]
            and cursor["settings"]["fast"] == build["settings"]["fast"]
            and cursor["settings"]["reasoning"] == build["settings"]["reasoning"]
        )
        assert cursor["settings"]["model"] == "grok-4.7"
        assert build["settings"]["model"] == "grok-4.7"
        assert cursor["settings"]["fast"] is False
        assert build["settings"]["fast"] is False
        assert "fast" not in " ".join(cursor["command"]).casefold()
