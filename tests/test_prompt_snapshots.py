"""Composed prompt snapshots: extraction must not drift the runtime text."""

from __future__ import annotations

import json
from pathlib import Path

from essay_writer.seats import seat_reading
from essay_writer.server import INSTRUCTIONS
from essay_writer.setup import CURSOR_SETUP_PROMPT, SETUP_PROMPT
from essay_writer.stage_llm import stage_settings
from essay_writer.writing_basics import STAGE_ORDER

SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "prompts.json"


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_instructions_match_snapshot():
    assert INSTRUCTIONS == _snapshot()["instructions"]


def test_stage_rules_match_snapshot():
    data = _snapshot()["stage_rules"]
    for stage in STAGE_ORDER:
        for genre in (None, "essay", "report", "diary"):
            key = f"{stage}:{genre or 'none'}"
            assert stage_settings(stage, genre)["rules"] == data[key], key
    assert stage_settings("eqr")["rules"] == data["eqr:none"]


def test_install_prompts_match_snapshot():
    data = _snapshot()["setup"]
    assert SETUP_PROMPT == data["setup_prompt"]
    assert CURSOR_SETUP_PROMPT == data["cursor_setup_prompt"]


def test_seat_reading_matches_snapshot():
    data = _snapshot()["seats"]
    assert seat_reading("research") == data["research"]
    assert seat_reading("write") == data["write"]
