"""Dig card, mechanical gates, plagiarism, and the reviewer seat."""

import ast
import json
import logging
from pathlib import Path

import pytest
from helpers import ESSAY, TOPIC, card_digest_for, open_sequence, pack, source, write_upload

from essay_writer import build_office
from essay_writer.dig import (
    LookupRefused,
    _card_markdown,
    _dig_reply,
    consensus_search,
    consensus_status,
    essay_dig,
    openalex_search,
)
from essay_writer.doors import DOORS
from essay_writer.gates import essay_gates
from essay_writer.health import essay_health
from essay_writer.research import essay_research_summary
from essay_writer.review import essay_review
from essay_writer.server import HANDLERS, INSTRUCTIONS, build_review_server, tool_names
from essay_writer.setup import CURSOR_SETUP_PROMPT, SETUP_PROMPT, essay_setup
from essay_writer.shells import cursor_shell, front_office
from essay_writer.state import load_state
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

REPO = Path(__file__).resolve().parents[1]
CONSENSUS_RULE = (
    "A Consensus key turns Consensus on for the search. "
    "No key leaves Consensus off and the search stays on OpenAlex."
)


LONG = "The corridor depends on a narrow strait that carries crude."


def _ready(workspace):
    # The shared splitter now keeps short bibliography lines in the upload.
    # The exact bibliography line would match its Word reference-list copy and
    # count as an unquoted copy, so this fixture gathers the same author,
    # title, and quote in prose instead.
    write_upload(
        workspace,
        text="Smith, J. (2020) 'Chokepoints and crude'. The Strait handles a large share of flows.\n",
    )
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n",
        encoding="utf-8",
    )
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(
        seq, TOPIC, "confirm", [source()], cardDigest=card_digest_for(seq, "essay.research.summary")
    )
    essay_pack_validate(seq, pack(), "draft")
    essay_pack_validate(seq, pack(), "confirm")
    return seq


def _lookup(monkeypatch, calls):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")

    def fake(url, headers=None):
        if "api.consensus.app" in url:
            calls["consensus"] += 1
            assert headers and "x-api-key" in headers
            return {
                "plan": "pro",
                "results": [
                    {
                        "title": "Returned by Consensus",
                        "publish_year": 2021,
                        "doi": "10.1/cs",
                        "authors": ["Ada"],
                    }
                ],
            }
        if "api.openalex.org" in url:
            assert not headers or "x-api-key" not in headers
            return {
                "results": [
                    {
                        "title": "Returned by OpenAlex",
                        "publication_year": 2019,
                        "doi": "https://doi.org/10.1/oa",
                        "authorships": [],
                    }
                ]
            }
        return None

    monkeypatch.setattr("essay_writer.dig._get_json", fake)


def test_dig_card_is_local_and_does_not_invent(workspace, monkeypatch):
    seq = open_sequence()
    calls = {"consensus": 0}
    _lookup(monkeypatch, calls)
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "key-not-echoed")
    draft = essay_dig(seq, "chokepoints", "draft")
    assert draft["wrote"] is False
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    assert not (folder / "dig-card.json").exists()
    assert "key-not-echoed" not in json.dumps(draft)
    titles = [hit["title"] for hit in draft["card"]["openalex"]["hits"]]
    titles += [hit["title"] for hit in draft["card"]["consensus"]["hits"]]
    assert titles == ["Returned by OpenAlex", "Returned by Consensus"]
    assert "Invented Journal" not in json.dumps(draft)
    assert draft["card"]["consensus"]["tier"] == "pro"
    assert draft["card"]["unpaywall"][0]["skipped"] == "no-email"
    confirmed = essay_dig(
        seq, "chokepoints", "confirm", cardDigest=card_digest_for(seq, "essay.dig")
    )
    assert confirmed["wrote"] is True
    card = json.loads((folder / "dig-card.json").read_text(encoding="utf-8"))
    text = (folder / "dig-card.md").read_text(encoding="utf-8")
    assert card["openalex"]["hits"][0]["title"] == "Returned by OpenAlex"
    assert "Returned by Consensus" in text
    assert "Invented Journal" not in text
    # Confirm reuses the stored card and does not call Consensus again.
    assert calls["consensus"] == 1


def test_openalex_abstract_is_saved_when_there_is_no_pdf(workspace, monkeypatch):
    """An OpenAlex abstract with no PDF is the gathered file, and nothing else."""
    from essay_writer.dig import _save_openalex_abstracts

    seq = open_sequence()
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")

    def fake(url, headers=None):
        if "api.openalex.org" in url:
            return {
                "results": [
                    {
                        "title": "Returned by OpenAlex",
                        "publication_year": 2019,
                        "doi": "https://doi.org/10.1/oa",
                        "authorships": [],
                        "abstract_inverted_index": {
                            "Supply": [0],
                            "chains": [1],
                            "collaborate.": [2],
                        },
                    }
                ]
            }
        return None

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    draft = essay_dig(seq, "chokepoints", "draft")
    hit = draft["card"]["openalex"]["hits"][0]
    assert hit["abstract"] == "Supply chains collaborate."
    assert _save_openalex_abstracts(seq, draft["card"], {"10.1/oa"}) == []
    confirmed = essay_dig(
        seq, "chokepoints", "confirm", cardDigest=card_digest_for(seq, "essay.dig")
    )
    assert confirmed["wrote"] is True
    saved = confirmed["abstract_files"]
    assert len(saved) == 1
    path = workspace / saved[0]["locator"]
    assert path.read_text(encoding="utf-8") == "Supply chains collaborate.\n"
    assert "Returned by OpenAlex" not in path.read_text(encoding="utf-8")


def test_consensus_free_tier_is_recorded_without_echoing_the_key(workspace, monkeypatch):
    seq = open_sequence()
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "free-key")

    def fake(url, headers=None):
        if "api.consensus.app" in url:
            return {"plan": "free", "results": [{"title": "Free hit", "publish_year": 2018}]}
        return {"results": []}

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    draft = essay_dig(seq, "ports", "draft")
    assert draft["wrote"] is False
    assert draft["card"]["consensus"]["tier"] == "free"
    assert draft["card"]["consensus"]["hits"][0]["title"] == "Free hit"
    assert "free-key" not in json.dumps(draft)


def test_key_present_turns_consensus_on_for_dig(workspace, monkeypatch):
    seq = open_sequence()
    calls = {"consensus": 0}
    _lookup(monkeypatch, calls)
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    monkeypatch.setenv("CONSENSUS_API_KEY", "key-not-echoed")
    draft = essay_dig(seq, "chokepoints", "draft")
    via_cursor = cursor_shell()["handlers"]["essay.dig"](seq, "chokepoints", "draft")
    via_bot = front_office()["handlers"]["essay.dig"](seq, "chokepoints", "draft")
    assert HANDLERS["essay.dig"] is essay_dig
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert front_office()["handlers"]["essay.dig"] is essay_dig
    assert draft["wrote"] is False
    assert via_cursor["wrote"] is False
    assert via_bot["wrote"] is False
    assert draft["consensus"]["enabled"] is True
    assert draft["consensus"]["key_present"] is True
    assert draft["consensus"]["switch"] == "unset"
    assert "Consensus is on for dig" in draft["consensus"]["remind"]
    assert draft["card"]["consensus"]["hits"] == via_cursor["card"]["consensus"]["hits"]
    assert draft["card"]["openalex"]["hits"] == via_bot["card"]["openalex"]["hits"]
    assert draft["card"]["consensus"]["hits"][0]["title"] == "Returned by Consensus"
    assert draft["invent_forbid"] is True
    assert "Invented Journal" not in json.dumps(draft)
    assert "key-not-echoed" not in json.dumps(draft)
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    assert not (folder / "dig-card.json").exists()
    confirmed = essay_dig(
        seq, "chokepoints", "confirm", cardDigest=card_digest_for(seq, "essay.dig")
    )
    assert confirmed["wrote"] is True
    assert confirmed["stored"] is True
    card = json.loads((folder / "dig-card.json").read_text(encoding="utf-8"))
    text = (folder / "dig-card.md").read_text(encoding="utf-8")
    assert card["consensus"]["hits"][0]["title"] == "Returned by Consensus"
    assert card["invent_forbid"] is True
    assert "invent-forbid: a line appears only when that look-up returned it." in text
    assert "Returned by Consensus" in text
    assert "Invented Journal" not in text
    assert "key-not-echoed" not in text
    health = essay_health()
    assert health["consensus"]["enabled"] is True
    assert "Consensus is on for dig" in health["consensus"]["remind"]
    assert "key-not-echoed" not in json.dumps(health)
    # Three drafts call Consensus. Confirm reuses the stored card.
    assert calls["consensus"] == 3


def test_missing_key_leaves_consensus_off_for_dig(workspace, monkeypatch):
    seq = open_sequence()
    calls = {"consensus": 0}
    _lookup(monkeypatch, calls)
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    monkeypatch.setattr("essay_writer.dig.read_setup_secret", lambda name: None)
    draft = essay_dig(seq, "ports", "draft")
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert calls["consensus"] == 0
    assert draft["consensus"]["enabled"] is False
    assert draft["consensus"]["key_present"] is False
    assert draft["consensus"]["switch"] == "unset"
    assert "Consensus is off" in draft["consensus"]["remind"]
    assert draft["card"]["consensus"]["hits"] == []
    assert draft["card"]["consensus"]["called"] is False
    assert draft["card"]["openalex"]["hits"][0]["title"] == "Returned by OpenAlex"
    assert "Returned by Consensus" not in json.dumps(draft)
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    confirmed = essay_dig(seq, "ports", "confirm", cardDigest=card_digest_for(seq, "essay.dig"))
    assert confirmed["wrote"] is True
    text = (folder / "dig-card.md").read_text(encoding="utf-8")
    assert "Consensus was not called." in text
    assert "Returned by OpenAlex" in text
    assert "Returned by Consensus" not in text
    assert "invent-forbid: a line appears only when that look-up returned it." in text
    assert calls["consensus"] == 0
    health = essay_health()
    assert health["consensus"]["enabled"] is False
    assert health["ok"] is True


def test_health_reports_whether_an_openalex_key_is_stored(monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)
    assert essay_health()["openalex"] == {"key_present": False}
    monkeypatch.setenv("OPENALEX_API_KEY", "oa-key-not-echoed")
    health = essay_health()
    assert health["openalex"] == {"key_present": True}
    assert "oa-key-not-echoed" not in json.dumps(health)


def test_an_openalex_key_is_sent_only_when_one_is_stored(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("OPENALEX_API_KEY", "oa-key-not-echoed")
    seen: dict[str, str] = {}

    def fake(url, headers=None):
        seen["url"] = url
        return {"results": []}

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    openalex_search("chokepoints")
    assert "api_key=oa-key-not-echoed" in seen["url"]
    monkeypatch.delenv("OPENALEX_API_KEY")
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)
    openalex_search("chokepoints")
    assert "api_key" not in seen["url"]
    assert "oa-key-not-echoed" not in json.dumps(seen)


def test_a_refused_lookup_is_not_reported_as_no_hits(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "key-not-echoed")

    def refused(url, headers=None):
        raise LookupRefused(429, "daily budget used up")

    monkeypatch.setattr("essay_writer.dig._get_json", refused)
    openalex = openalex_search("chokepoints")
    consensus = consensus_search("chokepoints")
    assert openalex["refused"] == {"status": 429, "detail": "daily budget used up"}
    assert openalex["hits"] == []
    assert consensus["refused"]["status"] == 429
    assert "key-not-echoed" not in json.dumps({"openalex": openalex, "consensus": consensus})


@pytest.mark.parametrize(
    "address",
    ["10.1.2.3", "192.168.4.5", "169.254.169.254", "198.18.0.1"],
)
def test_a_refusal_card_hides_the_resolved_address(monkeypatch, caplog, address):
    """The student card names a non-public address. The operator log keeps the address."""
    from essay_writer import dig

    monkeypatch.setattr(dig.safe_url, "_resolve_addresses", lambda host, port: [address])
    with caplog.at_level(logging.WARNING, logger="essay_writer.dig"):
        with pytest.raises(LookupRefused) as caught:
            dig._get_json("https://api.openalex.org/works?search=x")
    detail = caught.value.detail
    card = {
        "openalex": {"called": True, "hits": [], "refused": caught.value.record()},
        "consensus": {
            "called": False,
            "hits": [],
            "switch": "unset",
            "enabled": False,
            "key_present": False,
            "tier": None,
            "remind": "Consensus is off.",
        },
        "unpaywall": [],
    }
    text = _card_markdown("chokepoints", "MOD1004AA-1", card)
    reply = _dig_reply("MOD1004AA-1", "chokepoints", "draft", card)
    for shown in (detail, text, reply.get("lookup_note", ""), json.dumps(card)):
        assert address not in shown
        assert "non-public address" in shown
    assert address in caplog.text
    if address == "198.18.0.1":
        assert "198.18.0.0/15" in text
        assert "198.18.0.0/15" in caplog.text


def test_the_dig_card_and_reply_name_a_refusal():
    card = {
        "openalex": {
            "called": True,
            "hits": [],
            "refused": {"status": 429, "detail": "daily budget used up"},
        },
        "consensus": {
            "called": True,
            "tier": None,
            "hits": [],
            "refused": {"status": 401, "detail": "Invalid authentication credentials."},
            "switch": "1",
            "enabled": True,
            "key_present": True,
            "remind": "Consensus is on.",
        },
        "unpaywall": [],
    }
    text = _card_markdown("chokepoints", "MOD1004AA-1", card)
    assert "OpenAlex refused the look-up. HTTP 429: daily budget used up" in text
    assert "Consensus refused the look-up. HTTP 401: Invalid authentication credentials." in text
    reply = _dig_reply("MOD1004AA-1", "chokepoints", "draft", card)
    assert "OpenAlex refused the look-up" in reply["lookup_note"]
    assert "Consensus refused the look-up" in reply["lookup_note"]


def test_confirm_without_draft_writes_nothing_when_consensus_is_on(workspace, monkeypatch):
    seq = open_sequence()
    calls = {"consensus": 0}
    _lookup(monkeypatch, calls)
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    monkeypatch.setenv("CONSENSUS_API_KEY", "key-not-echoed")
    blocked = essay_dig(seq, "chokepoints", "confirm", cardDigest=card_digest_for(seq, "essay.dig"))
    assert blocked["ok"] is False
    assert blocked["wrote"] is False
    assert blocked["stored"] is False
    assert blocked["refused"] == "confirm"
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    assert not (folder / "dig-card.json").exists()
    assert not (folder / "dig-card.md").exists()
    assert "key-not-echoed" not in json.dumps(blocked)
    assert "Invented Journal" not in json.dumps(blocked)


def test_a_stored_setup_key_turns_consensus_on_without_echoing_it(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing-cloud")
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_CONSENSUS", raising=False)
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    key = "stored-consensus-key"
    skipped = essay_setup(app_path=str(app), kb1_path=str(kb1), confirmPhase="draft")
    assert skipped["consensus"]["enabled"] is False
    assert skipped["consensus"]["key_present"] is False
    assert "Consensus stays off for essay.dig." in skipped["next"]
    draft = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert draft["wrote"] is False
    assert draft["consensus_key"] is True
    assert draft["consensus"]["enabled"] is True
    assert draft["consensus"]["key_present"] is True
    assert "Consensus is on for essay.dig." in draft["next"]
    assert key not in json.dumps(draft)
    saved = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        consensus_plan="pro",
        acknowledge_skipped_searches=True,
    )
    assert saved["wrote"] is True
    assert saved["consensus"]["enabled"] is True
    assert key not in json.dumps(saved)
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    monkeypatch.setattr("essay_writer.paths.saved_setup_path", lambda: tmp_path / "setup.json")
    status = consensus_status()
    assert status["enabled"] is True
    assert status["key_present"] is True
    assert status["switch"] == "unset"
    assert "Consensus is on for dig" in status["remind"]
    assert key not in json.dumps(status)


def test_consensus_rule_is_shared_by_settings_briefings_and_both_shells():
    assert CONSENSUS_RULE in SETUP_PROMPT
    assert CONSENSUS_RULE in CURSOR_SETUP_PROMPT
    assert CONSENSUS_RULE in INSTRUCTIONS
    assert CONSENSUS_RULE in (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    descriptions = {door["tool"]: door["description"] for door in DOORS}
    assert CONSENSUS_RULE in descriptions["essay.dig"]
    assert CONSENSUS_RULE in descriptions["essay.setup"]
    bot = (REPO / "docs" / "templates" / "bot.md").read_text(encoding="utf-8")
    assert "switched on" in bot.casefold()
    assert "not switched on" not in bot.casefold()
    assert CONSENSUS_RULE not in bot
    office = Path(build_office.__file__).read_text(encoding="utf-8")
    assert "def essay_dig" not in office
    assert "def consensus_search" not in office
    root = REPO / "src" / "essay_writer"
    found: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                "essay_dig",
                "consensus_search",
                "consensus_status_for",
            }:
                found.setdefault(node.name, []).append(path.name)
    assert found["essay_dig"] == ["dig.py"]
    assert found["consensus_search"] == ["dig.py"]
    assert found["consensus_status_for"] == ["dig.py"]


def test_consensus_kill_switch_skips_the_call_and_reminds(workspace, monkeypatch):
    seq = open_sequence()
    calls = {"consensus": 0}
    _lookup(monkeypatch, calls)
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")
    monkeypatch.setenv("CONSENSUS_API_KEY", "secret-key")
    result = essay_dig(seq, "ports", "draft")
    assert calls["consensus"] == 0
    assert result["consensus"]["enabled"] is False
    assert "ESSAY_WRITER_CONSENSUS=0" in result["consensus"]["remind"]
    assert "secret-key" not in json.dumps(result)
    assert result["card"]["consensus"]["hits"] == []
    health = essay_health()
    assert health["consensus"]["switch"] == "0"
    assert "ESSAY_WRITER_CONSENSUS=0" in health["consensus"]["remind"]


def test_gates_block_an_unquoted_exact_sentence(workspace):
    write_upload(workspace, text=LONG + "\n")
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("Discuss the corridor.\n", encoding="utf-8")
    seq = open_sequence()
    copied = pack()
    copied["sections"] = [
        {"heading": "Introduction", "body": LONG},
        {
            "heading": "Supply chain context",
            "body": "One named supply chain on the corridor is in scope (Smith, 2020).",
        },
        {
            "heading": "Analysis and findings",
            "body": "The evidence is the gathered line (Smith, 2020).",
        },
        {"heading": "Conclusion", "body": "The corridor stays narrow (Smith, 2020)."},
    ]
    report = essay_gates(seq, copied)
    assert report["read_only"] is True
    assert report["wrote"] is False
    assert [item["gate"] for item in report["gates"]] == list(range(1, 12))
    assert report["plagiarism"]["code"] == "unquoted-exact"
    assert report["plagiarism"]["passed"] is False
    assert LONG in report["plagiarism"]["matches"]
    quoted = pack()
    quoted["sections"] = [
        {"heading": "Introduction", "body": f'A gathered line says "{LONG}" (Smith, 2020).'},
        {
            "heading": "Supply chain context",
            "body": "One named supply chain on the corridor is in scope (Smith, 2020).",
        },
        {
            "heading": "Analysis and findings",
            "body": "The evidence is tied to that line (Smith, 2020).",
        },
        {"heading": "Conclusion", "body": "The corridor stays narrow (Smith, 2020)."},
    ]
    clean = essay_gates(seq, quoted)
    assert clean["plagiarism"]["passed"] is True
    assert clean["passed"] is True


def test_writer_server_has_no_review_tool_and_stage_word_needs_eqr(workspace):
    assert "essay.review" not in tool_names()
    assert "essay.review" not in HANDLERS
    assert "essay.dig" in tool_names()
    assert "essay.gates" in tool_names()
    reviewer = build_review_server()
    names = [tool.name for tool in reviewer._tool_manager.list_tools()]
    assert reviewer.name == "essay-reviewer"
    assert names == ["essay.review"]

    seq = _ready(workspace)
    blocked = essay_review(seq, "6", "PASS", "draft", seat="writer")
    assert blocked["ok"] is False
    assert blocked["refused"] == "seat"
    assert "eqr" not in load_state(seq)

    preview = essay_pack_render_word(seq, pack(), "draft", stage="6")
    assert preview["wrote"] is False
    assert preview["eqr"] == "missing"
    silent = essay_pack_render_word(seq, pack(), "confirm", stage="6")
    assert silent["ok"] is False
    assert silent["refused"] == "eqr"
    target = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / f"{seq}.docx"
    assert not target.exists()

    constitution = "This is a report. How do chokepoints constrain the corridor?"
    draft = essay_review(seq, "6", "PASS", "draft", constitution=constitution)
    assert draft["wrote"] is False
    assert draft["seat"] == "reviewer"
    stored = essay_review(seq, "6", "PASS", "confirm", constitution=constitution)
    assert stored["stored"] is True
    assert load_state(seq)["eqr"]["6"]["verdict"] == "PASS"
    written = essay_pack_render_word(seq, pack(), "confirm", stage="6")
    assert written["wrote"] is True
    assert target.is_file()

    final_draft = essay_pack_render_word(seq, pack(), "draft", stage="9")
    assert final_draft["eqr"] == "missing"
    final_block = essay_pack_render_word(seq, pack(), "confirm", stage="9")
    assert final_block["refused"] == "eqr"
    essay_review(seq, "9", "PASS", "draft", constitution=constitution)
    essay_review(seq, "9", "PASS", "confirm", constitution=constitution)
    final = essay_pack_render_word(seq, pack(), "confirm", stage="9")
    assert final["wrote"] is True
