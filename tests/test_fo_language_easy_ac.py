"""FO chat language matches the student on this turn. Stable ids: AC1–AC3.

Build covered: Cursor and Grok Build shells share bot_share_document and LANGUAGE
from essay_writer.specialists.grok_bot (docs/templates/bot.md and essay-bot.share.json).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from essay_writer.first_run import repo_bot_share
from essay_writer.shells import bot_share_document, front_office
from essay_writer.specialists.grok_bot import LANGUAGE

REPO = Path(__file__).resolve().parents[1]
BOT = REPO / "docs" / "templates" / "bot.md"
SHARE = REPO / "docs" / "templates" / "essay-bot.share.json"


def test_ac1_language_default_english_match_this_turn_across_sources():
    """AC1. LANGUAGE, bot.md, and share tip default English and match this-turn student language."""
    assert "Default to English" in LANGUAGE
    assert "current message" in LANGUAGE.casefold()
    assert "reply in the same language family" in LANGUAGE
    assert "mirror that language" not in LANGUAGE

    sheet = BOT.read_text(encoding="utf-8")
    assert "Default to English" in sheet
    assert "this turn" in sheet.casefold()
    assert "reply in the same language family" in sheet

    on_disk = json.loads(SHARE.read_text(encoding="utf-8"))
    share = repo_bot_share()
    assert on_disk["chat_tone"]["language"] == LANGUAGE
    assert share["chat_tone"]["language"] is LANGUAGE
    built = bot_share_document(share["mcpServers"])
    assert built["chat_tone"]["language"] is LANGUAGE


def test_ac2_product_terms_stay_english():
    """AC2. Word, stages, Harvard, and the no-translate list stay English."""
    assert "Word files, stages, helpers, Harvard Referencing" in LANGUAGE
    assert "stay English" in LANGUAGE
    assert "Do not translate" in LANGUAGE

    sheet = BOT.read_text(encoding="utf-8")
    assert "Word files, stages, helpers, Harvard Referencing" in sheet
    assert "stay English" in sheet


def test_ac3_build_covered_fo_template_path_uses_one_language_source():
    """AC3. Build covered. FO share JSON and shells read grok_bot.LANGUAGE only."""
    shells_src = (REPO / "src" / "essay_writer" / "shells.py").read_text(encoding="utf-8")
    assert "from essay_writer.specialists.grok_bot import LANGUAGE" in shells_src
    assert '"language": LANGUAGE' in shells_src or '"language": LANGUAGE,' in shells_src
    assert front_office()["handlers"] is not None
    fo_src = inspect.getsource(front_office)
    assert "LANGUAGE" not in fo_src

    share = repo_bot_share()
    assert share["front_office"] == "essay_writer.shells.front_office"
    assert share["instructions"] == "docs/templates/bot.md"
    assert json.loads(SHARE.read_text(encoding="utf-8")) == share
