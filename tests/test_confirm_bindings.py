"""Confirm binds the side effects of stage 2, not just the arguments.

Setup binds the Consensus key and the Unpaywall email by SHA-256, so a draft
made with one value cannot be confirmed with another. Dig and research bind
the card that was shown with cardDigest, so a local edit to the draft
record's `shown` field cannot change what confirm writes. Stage 5 is the one
stage that stores on its draft and advances with no card; that exception is
pinned here.
"""

import hashlib
import json

from helpers import (
    CLARIFY_OPEN,
    ESSAY,
    TOPIC,
    open_sequence,
    source,
    write_upload,
)

from essay_writer import spine
from essay_writer.canon import digest
from essay_writer.confirm import card_digest
from essay_writer.dig import essay_dig
from essay_writer.paths import work_dir
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.setup import essay_setup
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.writing_basics import STAGE_ORDER

SETUP_TOOL_DIR = "essay.setup"
DIG_TOOL_DIR = "essay.dig"
SUMMARY_TOOL_DIR = "essay.research.summary"
FULL_TOOL_DIR = "essay.research.full"

SETUP_KEY = "consensus-key-alpha"
SETUP_EMAIL = "reader@example.com"
OTHER_KEY = "consensus-key-beta"


def _draft_path(essay_id: str, tool: str, payload_digest: str):
    return work_dir(essay_id) / ".drafts" / tool / f"{payload_digest}.json"


def _read_draft(essay_id: str, tool: str, payload_digest: str) -> dict:
    return json.loads(_draft_path(essay_id, tool, payload_digest).read_text(encoding="utf-8"))


def _write_draft(essay_id: str, tool: str, record: dict) -> None:
    """Rewrite a draft record after a simulated local edit."""
    for path in (work_dir(essay_id) / ".drafts" / tool).glob("*.json"):
        path.unlink()
    record = dict(record)
    record["digest"] = digest(record["payload"])
    path = _draft_path(essay_id, tool, record["digest"])
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- setup


def _setup_args(tmp_path):
    return {
        "app_path": str(tmp_path / "app"),
        "kb1_path": str(tmp_path / "KB1"),
        "consensus_api_key": SETUP_KEY,
        "unpaywall_email": SETUP_EMAIL,
        "consensus_plan": "pro",
    }


def _setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")


def test_setup_draft_binds_key_and_email_by_hash(tmp_path, monkeypatch):
    """The draft record carries SHA-256 of the normalised values, not the values."""
    _setup_env(tmp_path, monkeypatch)
    draft = essay_setup(**{**_setup_args(tmp_path), "confirmPhase": "draft"})
    assert draft["ok"] is True, draft
    assert draft["consensus_key"] is True
    assert draft["unpaywall_email"] is True
    dumped = json.dumps(draft)
    assert SETUP_KEY not in dumped
    assert SETUP_EMAIL not in dumped

    record = _read_draft("setup", SETUP_TOOL_DIR, draft["digest"])
    payload = record["payload"]
    assert payload["consensus_key"] is True
    assert payload["unpaywall_email"] is True
    assert payload["consensus_key_sha256"] == hashlib.sha256(SETUP_KEY.encode()).hexdigest()
    assert payload["unpaywall_email_sha256"] == hashlib.sha256(SETUP_EMAIL.encode()).hexdigest()
    record_text = json.dumps(record)
    assert SETUP_KEY not in record_text
    assert SETUP_EMAIL not in record_text


def test_setup_same_values_confirm_and_a_changed_key_is_refused(tmp_path, monkeypatch):
    """A draft with key A cannot be confirmed with key B. Same values can."""
    _setup_env(tmp_path, monkeypatch)
    draft = essay_setup(**{**_setup_args(tmp_path), "confirmPhase": "draft"})
    assert draft["ok"] is True, draft

    changed = essay_setup(
        **{**_setup_args(tmp_path), "consensus_api_key": OTHER_KEY, "confirmPhase": "confirm"}
    )
    assert changed["ok"] is False, changed
    assert changed["refused"] == "confirm"
    assert changed["wrote"] is False
    assert "show this step" in changed["reason"].casefold()
    assert not (tmp_path / "app").exists()
    assert not (tmp_path / "setup.json").exists()

    kept = essay_setup(**{**_setup_args(tmp_path), "confirmPhase": "confirm"})
    assert kept["ok"] is True, kept
    assert kept["wrote"] is True
    assert SETUP_KEY not in json.dumps(kept)
    assert SETUP_EMAIL not in json.dumps(kept)


def test_setup_old_draft_without_hashes_cannot_be_confirmed(tmp_path, monkeypatch):
    """A pre-binding draft is a different digest, so confirm shows the step again."""
    _setup_env(tmp_path, monkeypatch)
    draft = essay_setup(**{**_setup_args(tmp_path), "confirmPhase": "draft"})
    assert draft["ok"] is True, draft
    record = _read_draft("setup", SETUP_TOOL_DIR, draft["digest"])
    del record["payload"]["consensus_key_sha256"]
    del record["payload"]["unpaywall_email_sha256"]
    _write_draft("setup", SETUP_TOOL_DIR, record)

    refused = essay_setup(**{**_setup_args(tmp_path), "confirmPhase": "confirm"})
    assert refused["ok"] is False, refused
    assert refused["refused"] == "confirm"
    assert "show this step" in refused["reason"].casefold()
    assert not (tmp_path / "app").exists()


# ---------------------------------------------------------------- dig


def _stub_empty_lookups(monkeypatch):
    monkeypatch.setattr("essay_writer.dig._get_json", lambda url, headers=None: {"results": []})


def test_dig_card_digest_is_returned_and_a_confirm_without_it_is_refused(workspace, monkeypatch):
    _stub_empty_lookups(monkeypatch)
    seq = open_sequence()
    draft = essay_dig(seq, "corridor", "draft")
    assert draft["ok"] is True, draft
    assert draft["cardDigest"] == card_digest(
        {"essay_id": seq, "query": "corridor"}, draft["card"]
    )
    record = _read_draft(seq, DIG_TOOL_DIR, draft["digest"])
    assert record["cardDigest"] == draft["cardDigest"]
    assert "card digest" in draft["next"].casefold()

    refused = essay_dig(seq, "corridor", "confirm")
    assert refused["ok"] is False, refused
    assert refused["refused"] == "confirm"
    assert "show this step again" in refused["reason"].casefold()
    assert not (work_dir(seq) / "dig-card.json").exists()


def test_dig_legit_card_digest_confirms_and_a_local_shown_edit_is_refused(workspace, monkeypatch):
    _stub_empty_lookups(monkeypatch)
    seq = open_sequence()
    draft = essay_dig(seq, "corridor", "draft")
    record = _read_draft(seq, DIG_TOOL_DIR, draft["digest"])

    edited = json.loads(json.dumps(record))
    edited["shown"]["consensus"]["remind"] = "A locally edited card"
    _write_draft(seq, DIG_TOOL_DIR, edited)

    tampered = essay_dig(seq, "corridor", "confirm", cardDigest=draft["cardDigest"])
    assert tampered["ok"] is False, tampered
    assert tampered["refused"] == "confirm"
    assert "changed" in tampered["reason"].casefold()
    assert "show this step again" in tampered["reason"].casefold()
    assert not (work_dir(seq) / "dig-card.json").exists()

    # Remove the edited copy so a *new* draft can be confirmed normally.
    (work_dir(seq) / ".drafts" / DIG_TOOL_DIR / f"{edited['digest']}.json").unlink()
    (work_dir(seq) / ".drafts" / DIG_TOOL_DIR / f"{draft['digest']}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    wrong = essay_dig(seq, "corridor", "confirm", cardDigest="0" * 64)
    assert wrong["ok"] is False, wrong
    assert "not the card this step showed" in wrong["reason"].casefold()

    confirmed = essay_dig(seq, "corridor", "confirm", cardDigest=draft["cardDigest"])
    assert confirmed["ok"] is True, confirmed
    assert confirmed["stored"] is True
    assert (work_dir(seq) / "dig-card.json").is_file()


def test_dig_old_draft_without_a_card_digest_cannot_be_confirmed(workspace, monkeypatch):
    _stub_empty_lookups(monkeypatch)
    seq = open_sequence()
    draft = essay_dig(seq, "corridor", "draft")
    record = _read_draft(seq, DIG_TOOL_DIR, draft["digest"])
    del record["cardDigest"]
    _write_draft(seq, DIG_TOOL_DIR, record)

    refused = essay_dig(seq, "corridor", "confirm", cardDigest=draft["cardDigest"])
    assert refused["ok"] is False, refused
    assert refused["refused"] == "confirm"
    assert "before the card was bound" in refused["reason"].casefold()
    assert not (work_dir(seq) / "dig-card.json").exists()


# ---------------------------------------------------------------- research


def test_research_summary_card_is_bound(workspace):
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True, draft
    payload = {
        "essay_id": seq,
        "topic": TOPIC,
        "sources": [source()],
        "claims": [],
        "depth": "summary",
        "packs": [],
        "exclude_section_ids": [],
        "industry": None,
        "host_voice": None,
    }
    record = _read_draft(seq, SUMMARY_TOOL_DIR, draft["digest"])
    assert draft["cardDigest"] == card_digest(payload, record["shown"])
    assert record["cardDigest"] == draft["cardDigest"]
    assert "card digest" in draft["next"].casefold()

    missing = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert missing["ok"] is False, missing
    assert "show this step again" in missing["reason"].casefold()

    edited = json.loads(json.dumps(record))
    edited["shown"]["preview"]["topic"] = "A locally edited card"
    _write_draft(seq, SUMMARY_TOOL_DIR, edited)
    tampered = essay_research_summary(
        seq, TOPIC, "confirm", [source()], cardDigest=draft["cardDigest"]
    )
    assert tampered["ok"] is False, tampered
    assert tampered["refused"] == "confirm"
    assert "changed" in tampered["reason"].casefold()

    _write_draft(seq, SUMMARY_TOOL_DIR, record)
    confirmed = essay_research_summary(
        seq, TOPIC, "confirm", [source()], cardDigest=draft["cardDigest"]
    )
    assert confirmed["ok"] is True, confirmed
    assert confirmed["stored"] is True


def test_research_full_card_is_bound(workspace):
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_research_full(seq, TOPIC, "draft", [source()], clarify_context=CLARIFY_OPEN)
    assert draft["ok"] is True, draft
    assert isinstance(draft["cardDigest"], str) and len(draft["cardDigest"]) == 64
    record = _read_draft(seq, FULL_TOOL_DIR, draft["digest"])
    assert record["cardDigest"] == draft["cardDigest"]

    missing = essay_research_full(
        seq, TOPIC, "confirm", [source()], clarify_context=CLARIFY_OPEN
    )
    assert missing["ok"] is False, missing
    assert "show this step again" in missing["reason"].casefold()

    confirmed = essay_research_full(
        seq,
        TOPIC,
        "confirm",
        [source()],
        clarify_context=CLARIFY_OPEN,
        cardDigest=draft["cardDigest"],
    )
    assert confirmed["ok"] is True, confirmed
    assert confirmed["stored"] is True


# ---------------------------------------------------------------- stage 5


def _plant(seq: str, current: str, saved: list[str]) -> None:
    pointer = {
        "current": current,
        "saved": saved,
        "files": {},
        "closed": False,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": False,
        "room_grant": None,
        "room_lock": False,
        "waiting_stage": None,
        "waiting_digest": None,
        "revision": 4,
    }
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer), encoding="utf-8")


def test_stage5_stores_on_its_draft_and_advances_with_no_card(workspace):
    """The one exception: stage 5 stores, advances, and has no Confirm card.

    The binding added in this module covers dig, research, and setup. It is
    not a stage-save card: the stage path is proved in
    tests/test_confirm_atomic.py::test_ac3_stage5_and_last_stage_advance_without_card.
    """
    assert spine.AUTO_START == {"5": "6"}
    assert spine.advances_without_confirm("5") == "6"
    assert spine.stage_uses_confirm_card("5") is False
    assert {stage for stage in STAGE_ORDER if not spine.stage_uses_confirm_card(stage)} == {"5"}

    seq = open_sequence(ESSAY)
    _plant(seq, "5", ["1", "2", "3", "4a", "4b"])
    done = essay_stage(seq, "5", "draft", "The task is a short report on the corridor.")
    assert done["ok"] is True, done
    assert done["stored"] is True
    assert done["advanced"] is True
    assert done["current"] == "6"
    assert done.get("card") is None
    assert done.get("cardDigest") is None
    pointer = load_pointer(seq)
    assert pointer["current"] == "6"
    assert "5" in pointer["saved"]
    assert pointer["waiting_stage"] is None
