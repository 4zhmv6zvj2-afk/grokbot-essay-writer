"""Stage 4b context is 256000. EQR stays 256000. Stable ids: AC10a–AC10e."""

from __future__ import annotations

import inspect
from pathlib import Path

from essay_writer import build_office, cursor_office, stage_llm
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.stage_llm import (
    STAGE_KEYS,
    all_stage_settings,
    eqr_llm_note,
    stage_settings,
)

REPO = Path(__file__).resolve().parents[1]


def test_ac10a_stage_4b_context_window_is_256000():
    """AC10a. Stage 4b context is 256000. Model, reasoning, and fast stay."""
    item = stage_settings("4b")
    assert item["context_window"] == 256_000
    assert item["model"] == "grok-4.7"
    assert item["reasoning"] == "xhigh"
    assert item["fast"] is False


def test_ac10b_no_stage_uses_500000_context():
    """AC10b. No stage, including EQR, keeps a 500000 context window."""
    settings = all_stage_settings()
    assert "eqr" in settings
    assert set(settings) == set(STAGE_KEYS)
    for stage, item in settings.items():
        assert item["context_window"] == 256_000, stage
        assert item["context_window"] != 500_000
    source = Path(stage_llm.__file__).read_text(encoding="utf-8")
    assert "500000" not in source
    assert "500_000" not in source


def test_ac10c_docs_say_every_stage_context_is_256000():
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = workflow.split("## Stage LLM", 1)[1].split("\n## ", 1)[0]
    assert "256000 on every stage" in section
    assert "stage 4b" in section
    assert "EQR" in section
    for text in (workflow, section):
        assert "256000" in text
        assert "500000" not in text
        assert "500k" not in text.casefold()
    assert "500000" not in readme
    assert "500k" not in readme.casefold()


def test_ac10d_build_covered_cursor_and_grok_show_256000_for_4b():
    """AC10d. Build covered. Cursor and Grok Build read the same 4b row."""
    item = stage_settings("4b")
    cursor = cursor_stage_launch("4b")
    built = stage_launch("4b")
    assert cursor["settings"] == item
    assert built["settings"] == item
    assert cursor["source"] == built["source"] == "essay_writer.stage_llm.stage_settings"
    assert cursor["settings"]["context_window"] == 256_000
    rules = built["command"][built["command"].index("--rules") + 1]
    assert "Context window 256000" in rules
    assert "500000" not in rules
    assert "256000" not in cursor["command"]
    assert "500000" not in cursor["command"]
    assert "stage_settings(" in inspect.getsource(cursor_stage_launch)
    assert "stage_settings(" in inspect.getsource(stage_launch)
    assert "def stage_settings" not in Path(build_office.__file__).read_text(encoding="utf-8")
    assert "def stage_settings" not in Path(cursor_office.__file__).read_text(encoding="utf-8")


def test_ac10e_eqr_context_window_stays_256000():
    """AC10e. EQR context stays 256000. Model, reasoning, and fast stay."""
    item = stage_settings("eqr")
    assert item["context_window"] == 256_000
    assert item["model"] == "grok-4.7"
    assert item["reasoning"] == "xhigh"
    assert item["fast"] is False
    rules = stage_launch("eqr")["command"]
    text = rules[rules.index("--rules") + 1]
    assert "Context window 256000" in text
    assert "500000" not in text
    note = eqr_llm_note()
    assert "context 256000" in note
    assert "500000" not in note
