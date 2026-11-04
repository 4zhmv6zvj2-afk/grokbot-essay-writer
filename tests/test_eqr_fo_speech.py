"""First-run EQR FO speech on the writer Word path. Stable ids: AC1–AC3.

Build covered: Cursor and Grok Build share essay_writer.shells.front_office_call,
essay_writer.word.essay_pack_render_word, and essay_writer.specialists.grok_bot.attach_eqr_first_run_speech.
"""

from __future__ import annotations

import re
from pathlib import Path

from helpers import ESSAY, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.research import essay_research_summary
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import (
    EQR_FIRST_RUN_SPEECH,
    eqr_first_run_tip_sha,
)
from essay_writer.validate import essay_pack_validate

REPO = Path(__file__).resolve().parents[1]
_CONFIRM = re.compile(r"\bconfirm\b|\bbutton above\b|carddigest|cardaction|not yet to keep", re.IGNORECASE)
_PHANTOM = re.compile(r"don't click|do not click", re.IGNORECASE)


def _assert_no_confirm_speech(text: str) -> None:
    assert not _CONFIRM.search(text or "")
    assert not _PHANTOM.search(text or "")
    lowered = (text or "").casefold()
    assert "open the confirm card" not in lowered
    assert "press confirm for stage" not in lowered


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


def test_ac1_first_eqr_fo_speech_names_separate_specialist_review(workspace):
    """AC1. First writer hit on the EQR path names a separate specialist review."""
    assert "separate specialist review" in EQR_FIRST_RUN_SPEECH.casefold()
    seq = _ready(workspace)
    spoken = front_office_call(
        "essay.pack.render_word",
        {
            "essay_id": seq,
            "pack": pack(),
            "confirmPhase": "draft",
            "stage": "6",
        },
    )
    line = spoken.get("next") or ""
    assert "separate" in line.casefold()
    assert "specialist" in line.casefold()
    assert "independent review" in line.casefold()
    assert spoken.get("eqr") == "missing"


def test_ac2_first_eqr_fo_speech_has_no_phantom_stage_confirm(workspace):
    """AC2. First-run EQR FO speech does not invent Stage N Confirm."""
    seq = _ready(workspace)
    spoken = front_office_call(
        "essay.pack.render_word",
        {
            "essay_id": seq,
            "pack": pack(),
            "confirmPhase": "draft",
            "stage": "6",
        },
    )
    joined = " ".join(
        part
        for part in (
            spoken.get("next"),
            spoken.get("reason"),
            " ".join(spoken.get("status") or []),
        )
        if isinstance(part, str)
    )
    _assert_no_confirm_speech(joined)
    assert "stage 6 confirm" not in joined.casefold()


def test_ac3_build_covered_shared_fo_word_path():
    """AC3. Build covered. One grok_bot helper; word and FO shells share it."""
    word_src = (REPO / "src" / "essay_writer" / "word.py").read_text(encoding="utf-8")
    assert "attach_eqr_first_run_speech" in word_src
    assert "from essay_writer.specialists.grok_bot import attach_eqr_first_run_speech" in word_src
    grok_bot_src = (REPO / "src" / "essay_writer" / "specialists" / "grok_bot.py").read_text(
        encoding="utf-8"
    )
    assert "EQR_FIRST_RUN_SPEECH" in grok_bot_src
    assert "def attach_eqr_first_run_speech" in grok_bot_src
    shells_src = (REPO / "src" / "essay_writer" / "shells.py").read_text(encoding="utf-8")
    assert "front_office_call" in shells_src
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "separate specialist review" in bot.casefold()
    assert eqr_first_run_tip_sha() == eqr_first_run_tip_sha()


def test_first_eqr_intro_is_spoken_only_once_per_workspace(workspace):
    seq = _ready(workspace)
    args = {
        "essay_id": seq,
        "pack": pack(),
        "confirmPhase": "draft",
        "stage": "6",
    }
    first = front_office_call("essay.pack.render_word", args)
    second = front_office_call("essay.pack.render_word", args)
    needle = "separate specialist"
    assert needle in (first.get("next") or "").casefold()
    assert (second.get("next") or "").casefold().count(needle) == 0
