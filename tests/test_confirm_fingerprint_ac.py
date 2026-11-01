"""Confirm fingerprint is student arguments and local file hashes.

Live Unpaywall, OpenAlex, and resolver bodies are not fingerprint fields.
The draft stores the card that was shown. Confirm reuses it. Essay, diary,
and any later writing type use that same handler.
"""

import inspect
import json

from helpers import TOPIC, open_sequence, source, write_upload

from essay_writer.confirm import load_draft
from essay_writer.dig import TOOL as DIG_TOOL
from essay_writer.dig import essay_dig
from essay_writer.paths import work_dir
from essay_writer.research import SUMMARY, essay_research_summary
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists.researcher import essay_dig as researcher_dig
from essay_writer.state import load_state
from essay_writer.textutil import genre_from_brief_text

DRAFT_URL = "https://oa.example/draft-copy.pdf"
OTHER_URL = "https://oa.example/confirm-flip.pdf"
SECOND_URL = "https://oa.example/filled-on-confirm.pdf"
DRAFT_HIT = "Draft hit"
CONFIRM_HIT = "Confirm hit"
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
FILES_CHANGED = "saved files changed"

ESSAY_BRIEF = "Genre: essay\nQuestion: How does a harbour lock work?\n"
DIARY_BRIEF = (
    "Title: Individual reflective diary\n"
    "One entry for each occasion: North lock and South lock.\n"
    "Each entry names a decision and applies theory.\n"
)
TYPE_X_BRIEF = "Kind: fieldnote\nQuestion: How does a harbour lock work?\n"
WRITING_TYPES = (
    ("MOD1011AA", "essay", ESSAY_BRIEF),
    ("NOTEBOOK", "diary", DIARY_BRIEF),
    ("FIELDX", None, TYPE_X_BRIEF),
)


def _brief(workspace, module, text):
    path = workspace / "Essay-writer" / module / "brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _one_draft(seq, tool):
    folder = work_dir(seq) / ".drafts" / tool
    files = [path for path in folder.glob("*.json") if path.is_file()]
    assert len(files) == 1, [path.name for path in files]
    return json.loads(files[0].read_text(encoding="utf-8"))


def _stub_lookups(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")
    monkeypatch.delenv("CONSENSUS_API_KEY", raising=False)
    phase = {"live": "draft"}
    calls = {"openalex": 0, "unpaywall": 0}
    fetched: list[str] = []

    def fake_json(url, headers=None):
        if "api.openalex.org" in url:
            calls["openalex"] += 1
            title = DRAFT_HIT if phase["live"] == "draft" else CONFIRM_HIT
            return {
                "results": [
                    {
                        "title": title,
                        "publication_year": 2020,
                        "doi": "https://doi.org/10.1000/lock",
                        "authorships": [],
                    }
                ]
            }
        if "api.unpaywall.org" in url:
            calls["unpaywall"] += 1
            url_for_pdf = DRAFT_URL if phase["live"] == "draft" else OTHER_URL
            return {"best_oa_location": {"url_for_pdf": url_for_pdf}}
        return {"results": []}

    def fake_fetch(url):
        fetched.append(url)
        return 200, "application/pdf", PDF

    monkeypatch.setattr("essay_writer.dig._get_json", fake_json)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fake_fetch)
    return phase, calls, fetched


def _dig_flip(seq, query, phase, calls, fetched):
    phase["live"] = "draft"
    before = dict(calls)
    draft = essay_dig(seq, query, "draft")
    assert draft["ok"] is True, draft
    assert draft["wrote"] is False
    assert draft["card"]["unpaywall"][0]["oa_url"] == DRAFT_URL
    assert draft["card"]["openalex"]["hits"][0]["title"] == DRAFT_HIT
    record = load_draft(seq, DIG_TOOL, {"essay_id": seq, "query": query})
    assert record["fingerprint"] == {"query": query}
    assert "unpaywall" not in record["fingerprint"]
    assert "openalex" not in record["fingerprint"]
    assert "consensus" not in record["fingerprint"]
    assert record["shown"]["unpaywall"][0]["oa_url"] == DRAFT_URL
    phase["live"] = "confirm"
    confirmed = essay_dig(seq, query, "confirm")
    assert confirmed["ok"] is True, confirmed
    assert confirmed["stored"] is True
    assert confirmed.get("refused") is None
    assert FILES_CHANGED not in json.dumps(confirmed)
    assert calls["unpaywall"] == before["unpaywall"] + 1
    assert calls["openalex"] == before["openalex"] + 1
    card_path = work_dir(seq) / "dig-card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["unpaywall"][0]["oa_url"] == DRAFT_URL
    assert card["openalex"]["hits"][0]["title"] == DRAFT_HIT
    assert OTHER_URL not in card_path.read_text(encoding="utf-8")
    assert CONFIRM_HIT not in card_path.read_text(encoding="utf-8")
    assert fetched == [DRAFT_URL]
    return confirmed


def _query_change_refuses(seq, phase, calls):
    phase["live"] = "draft"
    draft = essay_dig(seq, "first lock", "draft")
    assert draft["ok"] is True, draft
    phase["live"] = "confirm"
    before = dict(calls)
    refused = essay_dig(seq, "second lock", "confirm")
    assert refused["ok"] is False
    assert refused["refused"] == "confirm"
    assert refused["stored"] is False
    assert refused["wrote"] is False
    assert FILES_CHANGED not in refused.get("reason", "")
    assert calls == before
    folder = work_dir(seq)
    assert not (folder / "dig-card.json").exists()
    assert not (folder / "dig-card.md").exists()
    return refused


def _file_hash_refuses(workspace, module, seq):
    path = write_upload(
        workspace,
        essay_id=module,
        text=(
            "Smith, J. (2020) Chokepoints and crude.\n"
            "The Strait handles a large share of flows.\n"
            "North lock is the harbour case.\n"
        ),
    )
    row = source(module)
    draft = essay_research_summary(seq, TOPIC, "draft", [row])
    assert draft["ok"] is True, draft
    record = _one_draft(seq, SUMMARY)
    assert set(record["fingerprint"]) == {"topic", "sources", "files"}
    assert "resolver_values" not in record["fingerprint"]
    assert "unpaywall" not in json.dumps(record["fingerprint"])
    path.write_text(path.read_text(encoding="utf-8") + "\nA later sentence.\n", encoding="utf-8")
    refused = essay_research_summary(seq, TOPIC, "confirm", [row])
    assert refused["ok"] is False, refused
    assert refused["refused"] == "confirm"
    assert refused["stored"] is False
    assert FILES_CHANGED in refused["reason"]
    assert load_state(seq)["research"]["summary"] is None


def test_ac1_unpaywall_flip_on_confirm_keeps_the_draft_url(workspace, monkeypatch):
    """Stub returns an open URL on draft and a different URL on confirm."""
    phase, calls, fetched = _stub_lookups(monkeypatch)
    seq = open_sequence()
    _dig_flip(seq, "harbour lock", phase, calls, fetched)


def test_ac2_query_change_refuses_and_does_not_write_the_card(workspace, monkeypatch):
    phase, calls, _fetched = _stub_lookups(monkeypatch)
    seq = open_sequence()
    _query_change_refuses(seq, phase, calls)
    phase["live"] = "draft"
    kept = essay_dig(seq, "first lock", "confirm")
    assert kept["stored"] is True
    card = json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))
    assert card["query"] == "first lock"


def test_ac3_gathered_file_hash_change_refuses_research_confirm(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    seq = open_sequence()
    _file_hash_refuses(workspace, "MOD1004AA", seq)


def test_ac4_essay_and_diary_use_the_same_essay_dig_handler(workspace, monkeypatch):
    """Prove on the handler. A stage number is not how dig is chosen."""
    assert list(inspect.signature(essay_dig).parameters) == ["essay_id", "query", "confirmPhase"]
    source = inspect.getsource(essay_dig)
    assert "genre" not in source
    assert "diary" not in source
    assert "stage" not in source
    assert HANDLERS["essay.dig"] is essay_dig
    assert researcher_dig is essay_dig
    assert cursor_shell()["handlers"] is HANDLERS
    assert front_office()["handlers"] is HANDLERS
    assert [name for name in HANDLERS if name.endswith("dig")] == ["essay.dig"]

    seen = []
    real = essay_dig

    def wrapped(essay_id, query, confirmPhase=None):
        assert "stage" not in inspect.signature(wrapped).parameters
        seen.append((essay_id, query, confirmPhase))
        return real(essay_id, query, confirmPhase)

    monkeypatch.setitem(HANDLERS, "essay.dig", wrapped)
    assert cursor_shell()["handlers"]["essay.dig"] is wrapped
    assert front_office()["handlers"]["essay.dig"] is wrapped
    monkeypatch.setattr("essay_writer.dig._get_json", lambda url, headers=None: {"results": []})
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")

    essay_seq = open_sequence("MOD1011AA")
    diary_seq = open_sequence("NOTEBOOK")
    _brief(workspace, "MOD1011AA", ESSAY_BRIEF)
    _brief(workspace, "NOTEBOOK", DIARY_BRIEF)
    assert genre_from_brief_text(ESSAY_BRIEF) == "essay"
    assert genre_from_brief_text(DIARY_BRIEF) == "diary"

    cursor_shell()["handlers"]["essay.dig"](essay_seq, "harbour lock", "draft")
    front_office()["handlers"]["essay.dig"](diary_seq, "harbour lock", "draft")
    assert seen == [
        (essay_seq, "harbour lock", "draft"),
        (diary_seq, "harbour lock", "draft"),
    ]
    assert all(len(call) == 3 for call in seen)


def test_research_second_unpaywall_keeps_draft_fields(workspace, monkeypatch):
    """The confirm pass would fill a URL the draft missed. The saved source does not take it."""
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    title = "Harbour lock notes"
    quote = "The Strait handles a large share of flows."
    write_upload(workspace, text=f"Smith, J. (2020) {title}.\n{quote}\n")
    seq = open_sequence()
    payload = source()
    payload["title"] = title
    payload["quote"] = quote
    calls = {"n": 0}

    def crossref_doi_only(query, fetch=None):
        return {"doi": "10.1000/kept"}

    def unpaywall(doi, email):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return {"url": SECOND_URL}

    monkeypatch.setattr("essay_writer.resolvers.crossref_lookup", crossref_doi_only)
    monkeypatch.setattr("essay_writer.resolvers.unpaywall_lookup", unpaywall)

    draft = essay_research_summary(seq, TOPIC, "draft", [payload])
    assert draft["ok"] is True, draft
    assert draft["sources"][0]["doi"] == "10.1000/kept"
    assert "url" not in draft["sources"][0]
    assert calls["n"] == 1
    record = _one_draft(seq, SUMMARY)
    assert set(record["fingerprint"]) == {"topic", "sources", "files"}
    assert "resolver_values" not in record["fingerprint"]
    assert SECOND_URL not in json.dumps(record["fingerprint"])
    assert "url" not in record["shown"]["sources"][0]

    confirmed = essay_research_summary(seq, TOPIC, "confirm", [payload])
    assert confirmed["stored"] is True, confirmed
    assert confirmed.get("refused") is None
    assert FILES_CHANGED not in json.dumps(confirmed)
    assert calls["n"] == 2
    assert confirmed["sources"][0]["doi"] == "10.1000/kept"
    assert "url" not in confirmed["sources"][0]
    assert SECOND_URL not in json.dumps(confirmed["sources"])
    saved = load_state(seq)["research"]["summary"]["sources"][0]
    assert saved["doi"] == "10.1000/kept"
    assert "url" not in saved
    assert SECOND_URL not in json.dumps(saved)


def test_ac_nt5_fingerprint_is_type_agnostic(workspace, monkeypatch):
    """AC-NT5. Same write gate for essay, diary, and a future writing type."""
    assert genre_from_brief_text(ESSAY_BRIEF) == "essay"
    assert genre_from_brief_text(DIARY_BRIEF) == "diary"
    assert genre_from_brief_text(TYPE_X_BRIEF) is None
    assert HANDLERS["essay.dig"] is essay_dig
    assert HANDLERS["essay.research.summary"] is essay_research_summary
    research_source = inspect.getsource(essay_research_summary)
    module_source = inspect.getsource(inspect.getmodule(essay_research_summary))
    assert "genre" not in research_source
    assert "diary" not in research_source
    assert "genre" not in module_source
    assert "diary" not in module_source
    phase, calls, fetched = _stub_lookups(monkeypatch)

    for module, genre, brief in WRITING_TYPES:
        _brief(workspace, module, brief)
        assert genre_from_brief_text(brief) == genre
        seq = open_sequence(module)
        _query_change_refuses(seq, phase, calls)
        fetched.clear()
        _dig_flip(seq, "harbour lock", phase, calls, fetched)
        monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
        _file_hash_refuses(workspace, module, seq)
        monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
