"""FO standing heading is the sequence id alone. Stable ids: AC1–AC4.

Path: standing heading line on the shared front-office reply. The doors have
no host call that sets a chat or agent display name.
Build covered: Cursor and Grok Build share essay_writer.shells.front_office_call
and essay_writer.specialists.grok_bot.attach_standing_heading.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from helpers import picked

from essay_writer.server import INSTRUCTIONS, call_local
from essay_writer.shells import front_office_call
from essay_writer.specialists.grok_bot import (
    STANDING_HEADING,
    attach_standing_heading,
    standing_heading_label,
)
from essay_writer.specialists.grok_bot import (
    front_office_call as grok_speak,
)

REPO = Path(__file__).resolve().parents[1]
MODULE = "MOD1004AA"
OTHER = "MOD1011AA"
SEQ3 = "MOD1004AA-3"
FORBIDDEN = "MOD1004AA · MOD1004AA-3"


def _confirm_new(module: str) -> dict:
    draft = front_office_call(
        "essay.sequence.new",
        {"module": module, "confirmPhase": "draft"},
    )
    assert draft["ok"] is True, draft
    assert "heading" not in draft
    opened = front_office_call(
        "essay.sequence.new",
        {"module": module, "confirmPhase": "confirm"},
    )
    assert opened["ok"] is True, opened
    return opened


def _open_number(module: str, number: int) -> dict:
    opened = None
    for _ in range(number):
        opened = _confirm_new(module)
    assert opened is not None
    return opened


def test_ac1_open_essay_heading_is_sequence_id_alone(workspace):
    """AC1. An open essay's FO heading is the sequence id alone, e.g. MOD1004AA-3."""
    opened = _open_number(MODULE, 3)
    assert opened["sequence_id"] == SEQ3
    assert opened["heading"] == SEQ3
    assert opened["heading"] != FORBIDDEN
    assert " · " not in opened["heading"]


def test_ac2_heading_never_prefixes_module_when_id_starts_with_it(workspace):
    """AC2. The heading does not repeat the module in front of an id that already starts with it."""
    assert standing_heading_label(SEQ3, module=MODULE) == SEQ3
    assert standing_heading_label(FORBIDDEN, module=MODULE) == SEQ3
    assert standing_heading_label(f"{MODULE}·{SEQ3}", module=MODULE) == SEQ3
    assert " · " not in standing_heading_label(SEQ3, module=MODULE)
    opened = _open_number(MODULE, 3)
    assert opened["heading"] == SEQ3
    assert opened["heading"].count(MODULE) == 1
    spoken = json.dumps(
        {
            "heading": opened["heading"],
            "essay_id": opened.get("essay_id"),
            "sequence_id": opened.get("sequence_id"),
            "next": opened.get("next"),
        }
    )
    assert FORBIDDEN not in spoken


def test_ac3_heading_updates_on_open_confirm_and_switch(workspace):
    """AC3. Heading appears at open, again after stage Confirm, and when the essay changes."""
    opened = _confirm_new(MODULE)
    seq = opened["sequence_id"]
    assert opened["heading"] == seq == f"{MODULE}-1"
    quiet = front_office_call("essay.originals", {"essay_id": seq})
    assert quiet["ok"] is True, quiet
    assert "heading" not in quiet
    look = "The task is a short report."
    draft = front_office_call(
        "essay.stage",
        {"essay_id": seq, "stage": "1", "confirmPhase": "draft", "look": look},
    )
    assert draft["ok"] is True, draft
    assert "heading" not in draft
    saved = front_office_call(
        "essay.stage",
        {
            "essay_id": seq,
            "stage": "1",
            "confirmPhase": "confirm",
            "look": look,
            **picked(draft),
        },
    )
    assert saved["ok"] is True, saved
    assert saved.get("stored") is True
    assert saved["heading"] == seq
    other = _confirm_new(OTHER)
    assert other["heading"] == f"{OTHER}-1"
    assert other["heading"] != seq
    switched = front_office_call("essay.originals", {"essay_id": seq})
    assert switched["heading"] == seq
    same = front_office_call("essay.originals", {"essay_id": seq})
    assert "heading" not in same


def test_ac4_build_covered_shared_fo_heading_path(workspace):
    """AC4. Build covered. Cursor and Grok Build share one FO heading attach."""
    assert "attach_standing_heading" in inspect.getsource(front_office_call)
    assert "attach_standing_heading" in inspect.getsource(grok_speak)
    assert front_office_call is grok_speak
    assert "front_office_call" in inspect.getsource(call_local)
    shells = (REPO / "src" / "essay_writer" / "shells.py").read_text(encoding="utf-8")
    assert "def mount_handler" in shells
    assert "return front_office_call(tool, arguments)" in shells
    build = (REPO / "src" / "essay_writer" / "build_office.py").read_text(encoding="utf-8")
    cursor = (REPO / "src" / "essay_writer" / "cursor_office.py").read_text(encoding="utf-8")
    assert "def attach_standing_heading" not in build
    assert "def attach_standing_heading" not in cursor
    assert "standing_heading_label" not in build
    assert "standing_heading_label" not in cursor
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert STANDING_HEADING in bot
    assert STANDING_HEADING in INSTRUCTIONS
    sample = attach_standing_heading(
        {"ok": True, "stored": True, "confirmPhase": "confirm", "essay_id": SEQ3, "module": MODULE},
        tool="essay.sequence.new",
        arguments={"module": MODULE, "confirmPhase": "confirm"},
    )
    assert sample["heading"] == SEQ3
