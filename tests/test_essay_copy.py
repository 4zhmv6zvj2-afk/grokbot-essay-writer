"""Copy infrastructure. Each hyphen id is bound once, in that test's docstring."""

import importlib.util
import json
import re
from pathlib import Path

from helpers import (
    CLARIFY_OPEN,
    ESSAY,
    OTHER,
    TOPIC,
    open_sequence,
    pack,
    plant_gathered_source,
    source,
    store_confirmed_question,
    write_upload,
)

from essay_writer.assignment_gate import assignment_gate
from essay_writer.build_status import (
    begin_mid_build,
    reset_status,
    spawn_exit_status,
    start_sentence,
)
from essay_writer.confirm import NO_MATCHING_DRAFT, phase_refusal
from essay_writer.cursor_office import start_stage_mid
from essay_writer.dig import essay_dig
from essay_writer.free_alt import essay_download_leftovers
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.projects import essay_project_delete, essay_sequence_new
from essay_writer.prompt_loader import text as prompt_text
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.revise import essay_revise
from essay_writer.server import INSTRUCTIONS
from essay_writer.shelf import essay_shelf_put
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state
from essay_writer.student_voice import for_word, say, strip_word_labels, student_surface_hits
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

REPO = Path(__file__).resolve().parents[1]
SHELL = REPO / "tools" / "doc_templates" / "bot.md"
BOT = REPO / "docs" / "templates" / "bot.md"
README = REPO / "README.md"
BRIEFING = REPO / "src" / "essay_writer" / "prompts" / "front_office" / "briefing.md"
CONFIRM = REPO / "src" / "essay_writer" / "prompts" / "front_office" / "confirm.md"
SNAPSHOT = REPO / "tests" / "snapshots" / "prompts.json"

TYPED_SAVE = (
    "A typed yes, ok, or Confirm saves the waiting stage only when the host "
    "cannot send the card fields; a supplied card field still has to be the "
    "Confirm action; it never saves a later stage."
)
FALSE_STAGE_SAVE = (
    "typed yes does not save",
    "typed ok, yes, or confirm does not save",
    "typed yes, ok, or confirm does not save",
    "typed confirm, yes, or ok does not save",
)
BANNED = (
    "the human",
    "show this",
    "card digest",
    "word_count_acknowledged",
    "dig-card",
    "do not invent an address",
    "say that before saving",
    "show it in the chat again",
)
KEEP = "Choose Confirm to keep this step."
SAY_YES = "Say yes to keep this step."
FORMAT_QUESTION = "Add the format and the assignment question in this chat, then save."
STUDENT = "Task: evaluate the corridor."
REPORT = "Genre: report\nQuestion: How should the firm manage the corridor?\n"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _clean(text: str) -> None:
    folded = text.casefold()
    for phrase in BANNED:
        assert phrase not in folded, (phrase, text)


def _open(module: str, parent: str | None = None) -> dict:
    draft = essay_sequence_new(module, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm", parent)
    assert opened["ok"] is True, opened
    return opened


def _no_card(body: dict) -> None:
    assert body.get("card") is None
    assert body.get("cardAction") is None
    assert body.get("cardDigest") is None


def _stub_lookups(monkeypatch) -> None:
    monkeypatch.setattr("essay_writer.dig._get_json", lambda url, headers=None: {"results": []})


def _research_draft(seq: str, *, confirm: bool) -> None:
    """The research draft has no card, so its student line asks the student to say yes."""
    missing = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert missing["ok"] is False, missing
    assert missing["reason"] == NO_MATCHING_DRAFT
    _clean(missing["reason"])
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True, draft
    assert draft.get("card") is None
    assert SAY_YES in draft["next"]
    assert KEEP not in draft["next"]
    _clean(draft["next"])
    if confirm:
        confirmed = essay_research_summary(
            seq,
            TOPIC,
            "confirm",
            [source()],
            cardDigest=draft["cardDigest"],
        )
        assert confirmed["ok"] is True, confirmed


def _dig_draft(seq: str) -> None:
    """The dig draft still has a card, so its student line names Choose Confirm."""
    store_confirmed_question(seq, "chokepoints")
    missing_dig = essay_dig(seq, "corridor", "confirm")
    assert missing_dig["ok"] is False, missing_dig
    assert missing_dig["reason"] == NO_MATCHING_DRAFT
    _clean(missing_dig["reason"])
    card = essay_dig(seq, "corridor", "draft")
    assert card["ok"] is True, card
    assert isinstance(card.get("card"), dict)
    assert KEEP in card["next"]
    assert SAY_YES not in card["next"]
    assert isinstance(card.get("cardDigest"), str) and card["cardDigest"]
    _clean(card["next"])


def test_essay_copy_a1_chat_keeps_ordinary_english(workspace):
    """essay-copy-a1. Chat leaves ordinary English, and the two refusals still have a verb."""
    assert say("Please confirm the save.") == "Please confirm the save."
    assert say("Confirm the plan first.") == "Confirm the plan first."
    assert say("invent-forbid") == "invent-forbid"
    assert say("The seat by the door is a pack on the shelf.") == (
        "The seat by the door is a pack on the shelf."
    )
    assert say("Please dig the archive and tip the scale.") == (
        "Please dig the archive and tip the scale."
    )
    assert "GO" not in say("The GO signal is a PASS.")
    assert say("A pass mark is a goal.") == "A pass mark is a goal."
    seq = open_sequence()
    empty = essay_revise(seq, " ", "draft")
    assert empty["ok"] is False, empty
    assert "does" in empty["reason"]
    assert empty["reason"] != "The does not invent the revision."
    leftovers = essay_download_leftovers(seq, "draft")
    assert leftovers["ok"] is False, leftovers
    assert "Confirm the annotated bibliography before fetching leftovers." in leftovers["reason"]
    assert leftovers["reason"] != "the annotated bibliography before fetching leftovers."


def test_essay_copy_a2_chat_drops_internal_labels_and_keeps_app_names():
    """essay-copy-a2. Chat drops internal labels and keeps Cursor, Grok Build, and Grok Bot."""
    spoken = say(
        "Save on the Grok Bot cloud computer with SuperGrok, Grok Build, or Cursor. "
        "The front office sent an EQR dig card from the mid office."
    )
    assert "Grok Bot" in spoken
    assert "Grok Build" in spoken
    assert "Cursor" in spoken
    assert "SuperGrok" not in spoken
    assert "front office" not in spoken.casefold()
    assert "mid office" not in spoken.casefold()
    assert "EQR" not in spoken
    assert "source card" in spoken
    assert "dig card" not in spoken.casefold()
    paths = say("Save copies under ~/Documents/zips and /Volumes/ResearchDrive/out.zip")
    assert "ResearchDrive" not in paths
    assert "~/" not in paths
    assert "Documents/" in paths
    assert "I am an AI" not in say("I am an AI. The essay is ready.").casefold()
    assert student_surface_hits("Use Grok Build for file work.") == ["Grok Build"]
    assert "Grok Build" in say("Use Grok Build for file work.")


def test_essay_copy_a3_word_is_strict_and_the_lenient_note_is_not():
    """essay-copy-a3. Word drops pack and the app names. The lenient note keeps pack and confirm."""
    assert "pack" not in for_word("the pack size")
    assert "draft" in for_word("the pack size")
    invented = for_word("The note says do not invent a source. Keep the rest.")
    assert "invent" not in invented.casefold()
    assert "Grok Build" not in for_word("Grok Build runs the file work.")
    assert "Grok Bot" not in for_word("Grok Bot runs a dig for SuperGrok.")
    assert strip_word_labels("the pack size") == "the pack size"
    assert strip_word_labels("Please confirm the save.") == "Please confirm the save."
    assert strip_word_labels("invent-forbid") == "do not invent sources"
    assert "Grok Build" not in strip_word_labels("Grok Build wrote this.")
    assert "Grok Bot" not in strip_word_labels("Grok Bot wrote this.")


def test_essay_copy_b1_student_lines_name_the_save(workspace, monkeypatch):
    """essay-copy-b1. The named drafts tell the student how to save, on a fresh sequence and a copied child."""
    _stub_lookups(monkeypatch)
    write_upload(workspace)
    write_upload(workspace, OTHER)
    fresh = _open(ESSAY)
    _no_card(fresh)
    child = _open(ESSAY, fresh["sequence_id"])
    _no_card(child)
    assert load_pointer(child["sequence_id"])["saved"] == []
    _research_draft(fresh["sequence_id"], confirm=True)
    _dig_draft(fresh["sequence_id"])
    _research_draft(child["sequence_id"], confirm=False)
    _dig_draft(child["sequence_id"])
    refused = phase_refusal(None)
    assert refused is not None
    assert "has not been shown yet" in refused["reason"]
    _clean(refused["reason"])
    seq = fresh["sequence_id"]
    revised = essay_revise(seq, "Shorten the opening.", "draft")
    assert revised["ok"] is True, revised
    assert SAY_YES in revised["next"]
    _clean(revised["next"])
    checked = essay_pack_validate(seq, pack(), "draft")
    assert checked["ok"] is True, checked
    assert SAY_YES in checked["next"]
    _clean(checked["next"])
    validated = essay_pack_validate(seq, pack(), "confirm")
    assert validated["ok"] is True, validated
    preview = essay_pack_render_word(seq, pack(), "draft")
    assert preview["ok"] is True, preview
    assert "No file has been written yet. Say yes to keep this step." in preview["next"]
    _clean(preview["next"])
    written = essay_pack_render_word(seq, pack(), "confirm")
    assert written["ok"] is True, written
    stored = essay_shelf_put(seq, pack(), "draft")
    assert stored["ok"] is True, stored
    assert SAY_YES in stored["next"]
    _clean(stored["next"])

    folder = essay_dir(OTHER)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
        "Word count: 800 words (720 to 880).\n",
        encoding="utf-8",
    )
    band_open = _open(OTHER)
    _no_card(band_open)
    band_child = _open(OTHER, band_open["sequence_id"])
    _no_card(band_child)
    assert load_pointer(band_child["sequence_id"])["saved"] == []
    for seq in (band_open["sequence_id"], band_child["sequence_id"]):
        gated = assignment_gate(seq, "A short note.", seat="writer")
        assert FORMAT_QUESTION in gated["reason"]
        assert gated["reason"].count(FORMAT_QUESTION) == 1
        _clean(gated["reason"])
    covered = pack(OTHER)
    covered["assessment"] = "Individual report"
    covered["sections"] = [dict(item) for item in covered["sections"]]
    covered["sections"][0]["body"] += " How do chokepoints constrain the corridor?"
    for seq in (band_open["sequence_id"], band_child["sequence_id"]):
        band = essay_pack_validate(seq, covered, "draft")
        reasons = [
            item["reason"]
            for item in band.get("blockers") or []
            if isinstance(item, dict) and item.get("code") == "word-count"
        ]
        assert reasons, band
        assert re.fullmatch(
            r"This draft is \d+ words\. The brief allows \d+\u2013\d+\. "
            r"Shorten it, or tell me you accept this length\.",
            reasons[0],
        )
        _clean(reasons[0])


def test_essay_copy_b3_guidance_next_stays_student_facing(workspace):
    """essay-copy-b3. A guidance-only next stays student-facing on a fresh sequence, a copied child, and an open with no card."""
    fresh = _open(ESSAY)
    _no_card(fresh)
    child = _open(ESSAY, fresh["sequence_id"])
    _no_card(child)
    assert load_pointer(child["sequence_id"])["saved"] == []
    for seq in (fresh["sequence_id"], child["sequence_id"]):
        drafted = essay_stage(seq, "1", "draft", "")
        assert drafted["ok"] is False, drafted
        assert drafted["next"] == (
            "One sentence of your own is the look. Add it in this chat, then save."
        )
        _clean(drafted["next"])
        _clean(str(drafted.get("reason") or ""))
        assert drafted.get("card") is None


def test_essay_copy_r2_a1_research_drafts_have_no_card(workspace, monkeypatch):
    """essay-copy-r2-a1. Summary and full research drafts return no card and ask the student to say yes."""
    _stub_lookups(monkeypatch)
    write_upload(workspace)
    seq = _open(ESSAY)["sequence_id"]
    summary = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert summary["ok"] is True, summary
    assert summary.get("card") is None
    assert summary.get("cardAction") is None
    assert isinstance(summary.get("cardDigest"), str) and summary["cardDigest"]
    assert SAY_YES in summary["next"]
    assert KEEP not in summary["next"]
    _clean(summary["next"])

    full = essay_research_full(
        seq,
        TOPIC,
        "draft",
        [source()],
        clarify_context=CLARIFY_OPEN,
    )
    assert full["ok"] is True, full
    assert full.get("card") is None
    assert full.get("cardAction") is None
    assert isinstance(full.get("cardDigest"), str) and full["cardDigest"]
    assert SAY_YES in full["next"]
    assert KEEP not in full["next"]
    _clean(full["next"])


def test_essay_copy_r2_a2_dig_keeps_its_card(workspace, monkeypatch):
    """essay-copy-r2-a2. The dig draft still returns a card and keeps the Choose Confirm line."""
    _stub_lookups(monkeypatch)
    seq = _open(ESSAY)["sequence_id"]
    store_confirmed_question(seq, "corridor")
    card = essay_dig(seq, "corridor", "draft")
    assert card["ok"] is True, card
    assert isinstance(card.get("card"), dict)
    assert KEEP in card["next"]
    assert SAY_YES not in card["next"]
    _clean(card["next"])


def test_essay_copy_r2_a3_research_and_dig_lines_are_split(workspace, monkeypatch):
    """essay-copy-r2-a3. Research asserts the say-yes line; dig asserts the Choose Confirm line."""
    _stub_lookups(monkeypatch)
    write_upload(workspace)
    seq = _open(ESSAY)["sequence_id"]
    research = essay_research_summary(seq, TOPIC, "draft", [source()])
    store_confirmed_question(seq, "corridor")
    dig = essay_dig(seq, "corridor", "draft")
    assert SAY_YES in research["next"]
    assert KEEP not in research["next"]
    assert KEEP in dig["next"]
    assert SAY_YES not in dig["next"]
    assert research["next"] != dig["next"]


def test_essay_copy_r2_a4_unsaved_research_is_not_kept(workspace, monkeypatch):
    """essay-copy-r2-a4. An unsaved research draft is not kept, and the typed fallback is the real path there."""
    _stub_lookups(monkeypatch)
    write_upload(workspace)
    seq = _open(ESSAY)["sequence_id"]
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True, draft
    assert load_state(seq).get("research", {}).get("summary") is None

    typed = essay_research_summary(seq, TOPIC, "confirm", [source()], cardDigest="yes")
    assert typed["ok"] is False, typed
    assert typed["refused"] == "confirm"
    assert typed.get("card") is None
    assert "pick the new card" not in typed["reason"]
    assert "say yes" in typed["reason"]
    assert load_state(seq).get("research", {}).get("summary") is None

    kept = essay_research_summary(
        seq,
        TOPIC,
        "confirm",
        [source()],
        cardDigest=draft["cardDigest"],
    )
    assert kept["ok"] is True, kept
    assert kept["stored"] is True
    stored = load_state(seq)["research"]["summary"]
    assert isinstance(stored, dict)
    assert stored["sources"]


def test_essay_copy_r2_a4_b_dig_keeps_the_card_path(workspace, monkeypatch):
    """Neighbouring case: dig still has a card, and a typed yes does not confirm it."""
    _stub_lookups(monkeypatch)
    seq = _open(ESSAY)["sequence_id"]
    store_confirmed_question(seq, "corridor")
    draft = essay_dig(seq, "corridor", "draft")
    assert draft["ok"] is True, draft
    assert isinstance(draft.get("card"), dict)
    typed = essay_dig(seq, "corridor", "confirm", cardDigest="yes")
    assert typed["ok"] is False, typed
    assert typed["refused"] == "confirm"
    assert not (work_dir(seq) / "dig-card.json").exists()
    kept = essay_dig(seq, "corridor", "confirm", cardDigest=draft["cardDigest"])
    assert kept["ok"] is True, kept
    assert (work_dir(seq) / "dig-card.json").is_file()


def test_essay_copy_r2_b1_word_band_line_stays(workspace):
    """essay-copy-r2-b1. The student word-band line stays in those words."""
    folder = essay_dir(OTHER)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
        "Word count: 800 words (720 to 880).\n",
        encoding="utf-8",
    )
    seq = _open(OTHER)["sequence_id"]
    covered = pack(OTHER)
    covered["assessment"] = "Individual report"
    covered["sections"] = [dict(item) for item in covered["sections"]]
    covered["sections"][0]["body"] += " How do chokepoints constrain the corridor?"
    band = essay_pack_validate(seq, covered, "draft")
    reasons = [
        item["reason"]
        for item in band.get("blockers") or []
        if isinstance(item, dict) and item.get("code") == "word-count"
    ]
    assert reasons, band
    assert re.fullmatch(
        r"This draft is \d+ words\. The brief allows \d+\u2013\d+\. "
        r"Shorten it, or tell me you accept this length\.",
        reasons[0],
    )
    _clean(reasons[0])


def test_essay_copy_r2_b2_host_sheet_names_the_flag(workspace):
    """essay-copy-r2-b2. The host sheet says the host sets word_count_acknowledged only after the student accepts."""
    shell = _flat(SHELL.read_text(encoding="utf-8"))
    assert "word_count_acknowledged" in shell
    assert "The host sets `word_count_acknowledged` only after the student accepts." in shell
    assert "Until then a later validate of the same pack still blocks." in shell
    bot = BOT.read_text(encoding="utf-8")
    assert "word_count_acknowledged" in bot

    seq = _open(ESSAY)["sequence_id"]
    write_upload(workspace)
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True, draft
    saved = essay_research_summary(
        seq,
        TOPIC,
        "confirm",
        [source()],
        cardDigest=draft["cardDigest"],
    )
    assert saved["ok"] is True, saved
    checked = essay_pack_validate(seq, pack(), "draft")
    assert checked["ok"] is True, checked
    text = _flat(str(checked.get("next") or "") + " " + str(checked.get("reason") or ""))
    assert "word_count_acknowledged" not in text.casefold()


def test_essay_copy_r2_b3_validate_description_names_the_host_path():
    """essay-copy-r2-b3. The essay.pack.validate tool description names the host path."""
    from essay_writer.doors import DOORS

    door = next(item for item in DOORS if item["tool"] == "essay.pack.validate")
    description = door["description"]
    assert "word_count_acknowledged" in description
    assert "only after the student accepts" in description
    assert "the door never sets that flag" in description


def test_essay_copy_r2_b4_a_test_asserts_the_host_path(workspace):
    """essay-copy-r2-b4. The host path is asserted here, on the sheet, the description, and the reply."""
    from essay_writer.doors import DOORS

    shell = _flat(SHELL.read_text(encoding="utf-8"))
    door = next(item for item in DOORS if item["tool"] == "essay.pack.validate")
    assert "word_count_acknowledged" in shell
    assert "word_count_acknowledged" in door["description"]

    folder = essay_dir(OTHER)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
        "Word count: 800 words (720 to 880).\n",
        encoding="utf-8",
    )
    seq = _open(OTHER)["sequence_id"]
    covered = pack(OTHER)
    covered["assessment"] = "Individual report"
    covered["sections"] = [dict(item) for item in covered["sections"]]
    covered["sections"][0]["body"] += " How do chokepoints constrain the corridor?"
    checked = essay_pack_validate(seq, covered, "draft")
    reasons = [
        item["reason"]
        for item in checked.get("blockers") or []
        if isinstance(item, dict) and item.get("code") == "word-count"
    ]
    assert reasons
    assert "word_count_acknowledged" not in reasons[0]


def test_essay_copy_r2_b5_the_flag_is_a_host_record(workspace):
    """essay-copy-r2-b5. A later validate still blocks until a real acceptance, then the host records the flag."""
    folder = essay_dir(OTHER)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
        "Word count: 800 words (720 to 880).\n",
        encoding="utf-8",
    )
    seq = _open(OTHER)["sequence_id"]
    covered = pack(OTHER)
    covered["assessment"] = "Individual report"
    covered["sections"] = [dict(item) for item in covered["sections"]]
    covered["sections"][0]["body"] += " How do chokepoints constrain the corridor?"
    first = essay_pack_validate(seq, covered, "draft")
    assert any(item.get("code") == "word-count" for item in first.get("blockers") or []), first
    again = essay_pack_validate(seq, covered, "draft")
    assert any(item.get("code") == "word-count" for item in again.get("blockers") or []), again

    accepted = dict(covered)
    accepted["word_count_acknowledged"] = True
    checked = essay_pack_validate(seq, accepted, "draft")
    notes = [
        item["reason"]
        for item in checked.get("notes") or []
        if isinstance(item, dict) and item.get("code") == "word-count"
    ]
    assert notes, checked
    assert "A person acknowledged that." in notes[0]
    assert not [item for item in checked.get("blockers") or [] if item.get("code") == "word-count"]


def test_essay_copy_r2_c1_free_alt_drops_the_invent_line(workspace, monkeypatch):
    """essay-copy-r2-c1. The free_alt next keeps Nothing was fetched and drops the invent-address line."""
    from essay_writer.free_alt import essay_download_leftovers

    seq = _open(ESSAY)["sequence_id"]
    plant_gathered_source(seq)
    folder = work_dir(seq) / "output"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "annotation.docx").write_bytes(b"PK annotated bibliography")
    draft = essay_download_leftovers(seq, "draft")
    assert draft["ok"] is True, draft
    assert "Nothing was fetched." in draft["next"]
    assert "Do not invent an address." not in draft["next"]
    folded = draft["next"].casefold()
    assert "do not invent an address" not in folded
    _clean(draft["next"])


def test_essay_copy_r2_d1_the_delete_sentence_starts_with_a_capital():
    """essay-copy-r2-d1. The sentence starts with a capital A in the generated docs, the template, and briefing.md."""
    sentence = "A typed yes does not remove anything."
    lower = "a typed yes does not remove anything."
    shell = SHELL.read_text(encoding="utf-8")
    bot = BOT.read_text(encoding="utf-8")
    briefing = BRIEFING.read_text(encoding="utf-8")
    for text in (shell, bot):
        assert sentence in text
        assert lower not in text
    delete_brief = next(
        line for line in briefing.splitlines() if line.startswith("Call essay.project.delete")
    )
    assert sentence in delete_brief
    assert lower not in delete_brief
    assert sentence in bot
    assert bot == _render_bot()


def test_essay_copy_c1_missing_host_names_the_app(workspace, monkeypatch):
    """essay-copy-c1. File work names Cursor or Grok Build, and the essay so far is safe."""
    fresh = _open(ESSAY)
    _no_card(fresh)
    child = _open(ESSAY, fresh["sequence_id"])
    _no_card(child)
    assert load_pointer(child["sequence_id"])["saved"] == []
    for seq in (fresh["sequence_id"], child["sequence_id"]):
        cursor_line = spawn_exit_status(seq, "agent-cli-missing")[0]
        grok_line = spawn_exit_status(seq, "grok-cli-missing")[0]
        assert "Cursor" in cursor_line
        assert "Grok Build" in grok_line
        assert "writing tool" not in cursor_line.casefold()
        assert "writing tool" not in grok_line.casefold()
        assert "safe" in cursor_line.casefold()
        assert "safe" in grok_line.casefold()
        assert say(cursor_line) == cursor_line
        assert say(grok_line) == grok_line
    monkeypatch.setattr(
        "essay_writer.cursor_office.spawn_agent",
        lambda command, launch=None: {
            "started": False,
            "reason": "agent-cli-missing",
            "command": list(command),
        },
    )
    cursor = start_stage_mid(fresh["sequence_id"], "4a", launch={"command": ["agent", "run"]})
    assert "Cursor" in cursor["status"][0]
    monkeypatch.setattr(
        "essay_writer.build_office.spawn_grok",
        lambda command, launch=None: {
            "started": False,
            "reason": "grok-cli-missing",
            "command": list(command),
        },
    )
    grok = start_stage_mid(fresh["sequence_id"], "4a", launch={"command": ["grok", "run"]})
    assert "Grok Build" in grok["status"][0]
    assert "writing tool" not in grok["status"][0].casefold()


def test_essay_copy_c2_a_full_sentence_question_is_not_repeated(workspace):
    """essay-copy-c2. A question that already ends in a full stop fills one full stop, on a fresh sequence and a copied child."""
    reset_status()
    question = "Evaluate the firm's actions."
    filled = start_sentence("work", question)
    assert filled.count(".") == 1
    assert filled.endswith(".")
    assert not filled.endswith("..")
    assert filled == start_sentence("work", "Evaluate the firm's actions")
    ellipsis = start_sentence("work", "Notes...")
    assert "Notes..." in ellipsis

    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        f"Format: report\nQuestion: {question}\n",
        encoding="utf-8",
    )
    fresh = _open(ESSAY)
    _no_card(fresh)
    child = _open(ESSAY, fresh["sequence_id"])
    _no_card(child)
    assert load_pointer(child["sequence_id"])["saved"] == []
    for seq in (fresh["sequence_id"], child["sequence_id"]):
        lines = begin_mid_build(seq, "work")
        assert lines
        assert lines[0].count(".") == 1
        assert question not in lines[0]
        assert "your report" in lines[0]

    (folder / "brief.md").write_text(
        f"Format: essay\nQuestion: {question}\n",
        encoding="utf-8",
    )
    essay_open = _open(OTHER)
    _no_card(essay_open)
    other = essay_dir(OTHER)
    other.mkdir(parents=True, exist_ok=True)
    (other / "brief.md").write_text(
        f"Format: essay\nQuestion: {question}\n",
        encoding="utf-8",
    )
    essay_child = _open(OTHER, essay_open["sequence_id"])
    _no_card(essay_child)
    for seq in (essay_open["sequence_id"], essay_child["sequence_id"]):
        lines = begin_mid_build(seq, "work")
        assert question not in lines[0]
        assert module_code(seq) in lines[0]
        assert lines[0].count(".") == 1


def _render_bot() -> str:
    path = REPO / "tools" / "generate_docs.py"
    spec = importlib.util.spec_from_file_location("generate_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_bot()


def _outside_injected(bot: str) -> str:
    block = prompt_text("front_office/confirm.md", "stage_confirm_each")
    assert bot.count(block) == 1
    return bot.replace(block, "", 1)


def test_essay_copy_d1_one_injected_confirm_rule():
    """essay-copy-d1. The typed-yes stage rule is injected once, and the group-room press paragraph stays."""
    bot = BOT.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    assert bot == _render_bot()
    assert _flat(bot).count(TYPED_SAVE) == 1
    assert TYPED_SAVE in _flat(CONFIRM.read_text(encoding="utf-8"))
    assert TYPED_SAVE in _flat(README.read_text(encoding="utf-8"))
    assert "unable to tap" in shell
    assert "Press Confirm for Stage N" in shell
    assert "second identical press is not required" in shell
    assert "A typed yes, ok, or Confirm does not save" not in shell
    assert "Each stage is saved only by a Confirm for that stage" not in shell
    assert "Each stage is saved only by a Confirm for that stage" in bot
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert snapshot["instructions"] == INSTRUCTIONS
    assert TYPED_SAVE in _flat(INSTRUCTIONS)


def test_essay_copy_d2_delete_still_needs_the_card(workspace):
    """essay-copy-d2. A typed yes does not remove a module, and the false stage-save sentence is gone."""
    shell = SHELL.read_text(encoding="utf-8")
    bot = BOT.read_text(encoding="utf-8")
    outside = _outside_injected(bot)
    for text in (shell, outside):
        folded = text.casefold()
        for phrase in FALSE_STAGE_SAVE:
            assert phrase not in folded, phrase
    briefing = BRIEFING.read_text(encoding="utf-8")
    delete_brief = next(
        line for line in briefing.splitlines() if line.startswith("Call essay.project.delete")
    )
    delete_shell = shell.split("## Delete a module", 1)[1].split("\n## ", 1)[0]
    for paragraph in (delete_brief, delete_shell, bot):
        assert "A typed yes does not remove anything." in paragraph
        folded = paragraph.casefold()
        assert "typed ok, yes, or confirm saves" not in folded
        assert "typed yes saves" not in folded
        assert "typed confirm saves" not in folded
    seq = open_sequence()
    draft = essay_project_delete(ESSAY, "draft", where="grokbot")
    assert draft["ok"] is True, draft
    refused = essay_project_delete(ESSAY, "confirm", where="grokbot")
    assert refused["ok"] is False, refused
    assert refused["refused"] == "confirm-card"
    assert essay_dir(ESSAY).is_dir()
    assert seq


def test_essay_copy_d3_typed_yes_saves_only_the_waiting_stage(workspace):
    """essay-copy-d3. A typed yes saves the waiting stage only, and it does not invent a card on a fresh open or a copied child."""
    folder = essay_dir(ESSAY)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(REPORT, encoding="utf-8")
    fresh = _open(ESSAY)
    _no_card(fresh)
    seq = fresh["sequence_id"]
    early = essay_stage(seq, "1", "confirm", "yes")
    assert early.get("stored") is not True
    assert early.get("card") is None
    pointer = load_pointer(seq)
    assert "1" not in pointer["saved"]
    assert pointer["waiting_stage"] is None
    assert pointer["waiting_digest"] is None
    look = "\n".join(basics_pass_lines(seq)) + "\n" + STUDENT
    draft = essay_stage(seq, "1", "draft", look)
    assert draft["ok"] is True, draft
    assert draft.get("cardDigest")
    saved = essay_stage(seq, "1", "confirm", "yes")
    assert saved["stored"] is True, saved
    pointer = load_pointer(seq)
    assert pointer["saved"] == ["1"]
    later = essay_stage(seq, "2", "confirm", "yes")
    assert later.get("stored") is not True
    assert "2" not in load_pointer(seq)["saved"]
    child = _open(ESSAY, seq)
    _no_card(child)
    child_id = child["sequence_id"]
    assert load_pointer(child_id)["saved"] == []
    pressed = essay_stage(child_id, "1", "confirm", "yes")
    assert pressed.get("stored") is not True
    assert pressed.get("card") is None
    child_pointer = load_pointer(child_id)
    assert "1" not in child_pointer["saved"]
    assert child_pointer["waiting_stage"] is None
    assert child_pointer["waiting_digest"] is None
