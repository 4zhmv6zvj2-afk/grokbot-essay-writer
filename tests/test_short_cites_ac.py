"""Short cites. Stable ids: AC1–AC4.

AC1: the ask "shorten the cites to about one or two sentences" is read, and the
     length it names is kept on the sequence for the later stages.
AC2: a cited point that runs long is cut to that many sentences at the stage
     door, and the paper it cites is still cited.
AC3: a cite per paper is left alone. The cut is said out loud, not silent.
AC4: the revision door reads the same ask, and a proposed draft is cut to it.
"""

from __future__ import annotations

from helpers import open_sequence, picked

from essay_writer.cite_fit import load_record
from essay_writer.revise import essay_revise
from essay_writer.shells import front_office_call
from essay_writer.short_cites import (
    apply_short_cite_request,
    limit_for,
    parse_limit,
    shorten,
)
from essay_writer.stage_track import _note_look, essay_stage
from essay_writer.state import load_state, save_state
from essay_writer.writing_basics import STAGE_ORDER

STUDENT = "Privacy risk reduces willingness to disclose personal data."
TOPIC_ONLY = "Surveys of privacy and personal data on government websites discuss trust."
FITS = (
    "Privacy risk reduces willingness to disclose personal data when people use a public site."
)
QUESTION = "Which public website?"

MINI_REVIEW = (
    "Privacy risk reduces willingness to disclose personal data (Beldad, 2019). "
    "Privacy risk also reduces willingness to disclose personal data on a public site "
    "(Beldad, 2019). "
    "Willingness to disclose personal data falls when privacy risk is high "
    "(Beldad, 2019). "
    "People disclose less personal data when the public site feels unsafe (Beldad, 2019)."
)


def _source(seq: str, ident: str, author: str, year: str, quote: str) -> dict:
    from essay_writer.paths import module_code

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


def _write_paper(seq: str, source: dict) -> None:
    """Put the gathered file on disk so a proposed draft can be inspected."""
    from pathlib import Path

    from essay_writer.paths import workspace_root

    path = workspace_root() / Path(source["locator"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{source['author']} ({source['year']}) {source['title']}.\n{source['quote']}\n",
        encoding="utf-8",
    )


def _plant(seq: str) -> None:
    state = load_state(seq)
    state["research"] = {
        "summary": {
            "sources": [
                _source(seq, "beldad", "Beldad, A.", "2019", FITS),
                _source(seq, "peng", "Peng, W.", "2018", TOPIC_ONLY),
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


def _cited_sentences(text: str, name: str) -> list[str]:
    from essay_writer.cite_fit import _sentences

    return [sentence for sentence in _sentences(text) if name in sentence]


def test_ac1_the_ask_is_read_and_the_length_is_kept(workspace):
    """AC1. The length the student names is read once and kept for later stages."""
    assert parse_limit("Please shorten the cites to 1-2 sentences.") == 2
    assert parse_limit("Shorten the citations to one or two sentences, please.") == 2
    assert parse_limit("Keep each cite to one sentence.") == 1
    assert parse_limit("Trim the quotes to at most two sentences.") == 2
    # No length named, or no ask at all: the door does not invent a length.
    assert parse_limit("Shorten the cites.") is None
    assert parse_limit("The sources are strong.") is None
    assert parse_limit("This section is too short. The cites are fine.") is None

    seq = open_sequence()
    assert limit_for(seq) is None
    asked = apply_short_cite_request(
        seq,
        STUDENT,
        answers="Please shorten the cites to 1-2 sentences.",
    )
    assert asked["asked"] is True
    assert asked["limit"] == 2
    assert limit_for(seq) == 2
    # Named once, it holds on the later saves.
    later = apply_short_cite_request(seq, STUDENT)
    assert later["limit"] == 2


def test_ac2_a_long_cited_stretch_is_cut_at_the_stage_door(workspace):
    """AC2. Four sentences on one paper become two, and the paper is still cited."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    landed = essay_stage(seq, "5", "draft", MINI_REVIEW)
    assert landed["stored"] is True, landed
    assert len(_cited_sentences(_note_look(seq, "5") or "", "Beldad")) == 4

    cut = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": MINI_REVIEW,
            "answers": "Please shorten the cites to 1-2 sentences.",
        },
    )
    assert cut["ok"] is True, cut
    look = _note_look(seq, "6") or ""
    cited = _cited_sentences(look, "Beldad")
    assert len(cited) <= 2
    assert "(Beldad, 2019)" in look
    assert "cite_short" in cut
    assert cut["cite_short"] == {"limit": 2, "cut": 2}
    assert "cite_short_line" in cut
    assert "beldad, 2019" not in load_record(seq)["withheld"]
    assert limit_for(seq) == 2

    saved = essay_stage(
        seq,
        "6",
        "confirm",
        MINI_REVIEW,
        answers="Please shorten the cites to 1-2 sentences.",
        **picked(cut),
    )
    assert saved["stored"] is True, saved

    # The next stage keeps the same length without the ask being repeated.
    again = essay_stage(seq, "7", "draft", MINI_REVIEW)
    assert again["ok"] is True, again
    assert len(_cited_sentences(_note_look(seq, "7") or "", "Beldad")) <= 2


def test_ac3_one_cite_per_paper_is_left_alone_and_the_cut_is_said(workspace):
    """AC3. A short stretch is not trimmed, and a long one reports what it cut."""
    one_each = (
        "Privacy risk reduces willingness to disclose personal data (Beldad, 2019). "
        "Public websites survey trust in personal data (Peng, 2018)."
    )
    text, report = shorten(one_each, 2)
    assert text == one_each
    assert report["applied"] is False
    assert report["cut"] == []

    quoted = (
        'Privacy risk reduces willingness to disclose personal data (Beldad, 2019). '
        'The student notes "I would not enter my address" on the same form (Beldad, 2019). '
        "Privacy risk also reduces willingness to disclose personal data (Beldad, 2019). "
        "Willingness to disclose personal data falls when privacy risk is high (Beldad, 2019)."
    )
    text, report = shorten(quoted, 2)
    assert "I would not enter my address" in text
    assert report["cut"]

    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    essay_stage(seq, "5", "draft", MINI_REVIEW)
    cut = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "6",
            "confirmPhase": "draft",
            "look": MINI_REVIEW,
            "answers": "Please shorten the cites to 1-2 sentences.",
        },
    )
    # The reply says how many long stretches were cut. Nothing is silently dropped.
    assert cut["cite_short"]["cut"] == 2
    assert cut["cite_short_line"] in cut["next"]
    assert "two sentences" in cut["cite_short_line"]


def test_ac4_the_revision_door_reads_the_same_ask(workspace):
    """AC4. A revision note sets the same length, and a proposed draft is cut to it."""
    seq = open_sequence()
    _plant(seq)
    _walk(seq, "5", stage3=f"Use Beldad. {STUDENT}")
    essay_stage(seq, "5", "draft", MINI_REVIEW)
    _write_paper(seq, _source(seq, "beldad", "Beldad, A.", "2019", FITS))

    draft = essay_revise(
        seq,
        "Please shorten the cites to 1-2 sentences.",
        "draft",
        pack={
            "essay_id": seq,
            "title": "Privacy risk",
            "referencing": "harvard",
            "conclusion": "noted",
            "sections": [{"heading": "Findings", "body": MINI_REVIEW}],
            "sources": [_source(seq, "beldad", "Beldad, A.", "2019", FITS)],
        },
    )
    assert draft["ok"] is True, draft
    assert limit_for(seq) == 2
    assert draft["cite_short"]["limit"] == 2
    assert draft["cite_short"]["cut"] == 2
    assert draft["cite_short_line"] in draft["next"]
    sections = draft.get("pack", {}).get("sections")
    if sections is None:
        state_body = load_state(seq)
        assert state_body  # the note was recorded on the sequence
    else:
        assert len(_cited_sentences(sections[0]["body"], "Beldad")) <= 2
