"""A rejected cite stays out when a later save puts the body back.

AC1: a failed swap leaves a gap and asks the student; the rejected cite is not
     put back by a pack snapshot restore.
AC2: a body that still carries a withheld cite (an earlier note, or a restored
     snapshot) does not clear the withhold, so the next stage does not re-land it.
AC3: the Word door drops a rejected paper from the body and the reference list
     even when the exact token was never recorded as withheld.

These extend ``tests/test_cite_fit_ac.py`` AC1–AC5, which stay green.
"""

from __future__ import annotations

from helpers import open_sequence, picked

from essay_writer.cite_fit import apply_body_cites, load_record
from essay_writer.pack_backup import backups_dir, essay_pack_restore
from essay_writer.paths import module_code
from essay_writer.shells import front_office_call
from essay_writer.stage_track import _note_look, essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.textutil import prepare_word_citations, reference_line
from essay_writer.writing_basics import STAGE_ORDER

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
                _source(seq, "beldad", "Beldad, A.", "2019", FITS),
                _source(seq, "yamoah", "Yamoah, F.", "2020", TOPIC_ONLY),
            ]
        },
        "full": None,
    }
    save_state(seq, state)


def _walk(seq: str, stop: str, *, stage3: str) -> None:
    for stage in STAGE_ORDER:
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


def _beldad_pack(seq: str) -> dict:
    return {
        "essay_id": seq,
        "title": "Privacy risk",
        "assessment": "Individual report",
        "referencing": "harvard",
        "conclusion": "noted",
        "sections": [
            {"heading": "Findings", "body": _cited("Beldad", "2019")},
            {"heading": "Conclusion", "body": "Reading a public site as unsafe is the point."},
        ],
        "sources": [_source(seq, "beldad", "Beldad, A.", "2019", FITS)],
    }


def _newest_snapshot(seq: str) -> str:
    root = backups_dir(seq)
    names = sorted(path.name for path in root.iterdir() if path.is_dir())
    assert names, "the stage save wrote no snapshot"
    return names[-1]


def _refs(sources: list) -> str:
    return "\n".join(reference_line(source) for source in sources if isinstance(source, dict))


def test_ac1_failed_swap_leaves_a_gap_and_snapshot_restore_does_not_put_it_back(workspace):
    """AC1. Beldad is rejected, the swap does not fit, the point is left open."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    state = load_state(seq)
    state["saved_pack"] = _beldad_pack(seq)
    save_state(seq, state)
    landed = essay_stage(seq, "5", "draft", _cited("Beldad", "2019"))
    assert landed["stored"] is True, landed
    snapshot = _newest_snapshot(seq)

    swapped = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": _cited("Beldad", "2019").replace(
                "(Beldad, 2019)", "(Beldad, 2019; Yamoah, 2020)"
            ),
            "answers": "swap Beldad for Yamoah",
        },
    )
    assert swapped["ok"] is True, swapped
    assert "Beldad" not in (_note_look(seq, "6") or "")
    assert "Yamoah" not in (_note_look(seq, "6") or "")
    reasons = {item["token"]: item["reason"] for item in swapped["cite_held"]}
    assert reasons["beldad, 2019"] == "rejected"
    assert reasons["yamoah, 2020"] == "claim-fit"
    # The student is offered the gap. Nothing is put back and nothing is invented.
    gap = swapped["cite_gap"]
    assert "stays out because you rejected it" in gap
    assert "left open" in gap
    assert gap in swapped["next"]
    assert "cite_ask" not in swapped
    assert "beldad" in load_record(seq)["rejected"]

    # A snapshot from before the swap still carries the rejected body.
    state = load_state(seq)
    state["saved_pack"] = None
    save_state(seq, state)
    preview = essay_pack_restore(seq, snapshot, "draft")
    assert preview["ok"] is True, preview
    assert preview["wrote"] is False
    restored = essay_pack_restore(seq, snapshot, "confirm")
    assert restored["ok"] is True, restored
    assert restored["stored"] is True
    assert "Beldad" in repr(load_state(seq).get("saved_pack"))

    # The restored copy does not print that paper. The reject outlives the restore.
    from essay_writer.word import word_manifest

    _pack, report = word_manifest(seq, load_state(seq)["saved_pack"])
    bodies = " ".join(section["body"] for section in report["sections"])
    assert "Beldad" not in bodies
    assert "Beldad" not in " ".join(report["references"])
    assert "Beldad" not in _refs(report["sources"])


def test_ac2_a_still_carried_cite_does_not_clear_the_withhold(workspace):
    """AC2. Stage 5 still holds Beldad. That copy does not re-land it at stage 6."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    landed = essay_stage(seq, "5", "draft", _cited("Beldad", "2019"))
    assert landed["stored"] is True, landed
    assert "Beldad" in (_note_look(seq, "5") or "")

    rejected = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": _cited("Beldad", "2019"),
            "answers": "Do not use Beldad.",
        },
    )
    assert rejected["ok"] is True, rejected
    assert "Beldad" not in (_note_look(seq, "6") or "")
    record = load_record(seq)
    assert "beldad" in record["rejected"]
    assert "beldad, 2019" in record["withheld"]

    # Stage 6 now sends the same sentence again. The earlier note still has the
    # paper, and that earlier copy is not a student yes.
    again = apply_body_cites(seq, "6", _cited("Beldad", "2019"))
    assert "Beldad" not in again["text"]
    assert "beldad, 2019" in load_record(seq)["withheld"]

    # A negated ask is a drop, not a yes. "Do not add" carries the same verb as "add".
    from essay_writer.cite_fit import _added_names

    assert _added_names("Do not add Beldad.") == set()
    assert _added_names("Do not include Beldad.") == set()
    assert _added_names("Do not use Beldad.") == set()
    assert _added_names("Yes, add Beldad.") == {"beldad"}

    # A student yes still lands it: the reject is read, it is not a permanent ban.
    allowed = apply_body_cites(
        seq,
        "6",
        _cited("Beldad", "2019"),
        answers="Yes, add Beldad.",
    )
    assert "(Beldad, 2019)" in allowed["text"]
    assert "beldad, 2019" not in load_record(seq)["withheld"]
    assert "beldad" not in load_record(seq)["rejected"]


def test_ac3_word_door_drops_a_rejected_paper_whose_token_was_never_recorded(workspace):
    """AC3. A reject is by paper, so the exact author-year token is not the only key."""
    from essay_writer.cite_fit import _write_record

    seq = open_sequence()
    _plant(seq)
    # The student dropped Beldad before any body carried the year. Only the
    # surname is on the record, which is what a restore-then-reland hits.
    _write_record(seq, {"ok": [], "rejected": ["beldad"], "withheld": []})
    sources, sections = prepare_word_citations(
        seq,
        [_source(seq, "beldad", "Beldad, A.", "2019", FITS)],
        [{"heading": "Findings", "body": _cited("Beldad", "2019")}],
    )
    assert "Beldad" not in sections[0]["body"]
    assert "privacy risk reduces willingness" in sections[0]["body"].casefold()
    assert sources == []

    # A year the student never rejected does not slip past the same record.
    other_year = _source(seq, "beldad", "Beldad, A.", "2021", FITS)
    sources, sections = prepare_word_citations(
        seq,
        [other_year],
        [{"heading": "Findings", "body": _cited("Beldad", "2021")}],
    )
    assert "Beldad" not in sections[0]["body"]
    assert sources == []
    assert "Beldad" not in _refs(sources)

    # A saved reference list is dropped for the same paper, and a kept paper stays.
    from essay_writer.word_references import without_withheld_reference_lines

    beldad_line = reference_line(_source(seq, "beldad", "Beldad, A.", "2019", FITS))
    kept_line = reference_line(_source(seq, "yamoah", "Yamoah, F.", "2020", TOPIC_ONLY))
    assert beldad_line and kept_line
    kept = without_withheld_reference_lines(
        seq,
        [beldad_line, kept_line],
        [_source(seq, "yamoah", "Yamoah, F.", "2020", TOPIC_ONLY)],
    )
    assert kept == [kept_line]


def test_ac4_restore_preview_writes_nothing_and_keeps_the_reject(workspace):
    """AC4. A draft-phase restore preview does not write, and the record is untouched."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    state = load_state(seq)
    state["saved_pack"] = _beldad_pack(seq)
    save_state(seq, state)
    essay_stage(seq, "5", "draft", _cited("Beldad", "2019"))
    snapshot = _newest_snapshot(seq)
    front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": _cited("Beldad", "2019"),
            "answers": "drop Beldad",
        },
    )
    before = load_record(seq)
    preview = essay_pack_restore(seq, snapshot, "draft")
    assert preview["ok"] is True, preview
    assert preview["wrote"] is False
    assert preview["stored"] is False
    assert load_record(seq) == before

    # Nothing on this sequence wrote a Word file from that preview.
    from essay_writer.paths import work_dir

    output = work_dir(seq) / "output"
    assert not (output / f"{seq}.docx").exists()
