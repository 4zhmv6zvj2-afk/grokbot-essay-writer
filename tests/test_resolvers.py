import json

from helpers import ESSAY, TOPIC, open_sequence, source, write_upload

from essay_writer.programme import FREE_RESOLVERS, PAID_RESOLVERS
from essay_writer.research import essay_research_summary
from essay_writer.resolvers import (
    FIXTURE_TITLE,
    crossref_lookup,
    fixture_crossref_fetch,
)


def test_free_and_paid_allow_lists():
    assert "crossref" in FREE_RESOLVERS
    assert "scopus" in PAID_RESOLVERS


def test_saved_crossref_sample_matches_title():
    record = crossref_lookup(FIXTURE_TITLE, fetch=fixture_crossref_fetch)
    assert record is not None
    assert record["doi"] == "10.5555/fixture-chokepoint"
    assert record["container"] == "Journal of Transport Geography"


def test_crossref_sample_does_not_match_other_titles():
    record = crossref_lookup("Chokepoints and crude", fetch=fixture_crossref_fetch)
    assert record is None


def test_matched_lookup_stores_doi_and_lists_crossref(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    text = (
        f"Smith, J. (2020) {FIXTURE_TITLE}.\n"
        "The Strait handles a large share of flows.\n"
    )
    write_upload(workspace, text=text)
    seq = open_sequence()
    payload = source()
    payload["title"] = FIXTURE_TITLE
    payload["quote"] = "The Strait handles a large share of flows."
    draft = essay_research_summary(seq, TOPIC, "draft", [payload])
    assert draft["ok"] is True
    assert draft["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    assert any(
        item["name"] == "crossref" and item["result"] == "matched"
        for item in draft["resolvers_called"]
    )
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [payload])
    assert confirmed["stored"] is True
    state = json.loads(
        (workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "state.json").read_text(encoding="utf-8")
    )
    pack = state["research"]["summary"]["research_pack"]
    assert pack["topic"] == TOPIC
    assert pack["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    assert pack["field_provenance"]["src-1"]["doi"] == "lookup"
    assert pack["opposing_point"]["found"] is False


def test_non_matching_title_leaves_doi_blank(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    write_upload(workspace)
    seq = open_sequence()
    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True
    assert "doi" not in draft["sources"][0]
    assert any(item["name"] == "crossref" for item in draft["resolvers_called"])


def test_typed_doi_without_gathered_locator_still_refused(workspace):
    seq = open_sequence()
    fake = {"doi": "10.5555/fixture-chokepoint", "title": "Anything"}
    result = essay_research_summary(seq, TOPIC, "draft", [fake])
    assert result["refused"] == "invent-forbid"


def test_typed_doi_not_in_file_still_refused(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    write_upload(workspace)
    seq = open_sequence()
    bad = source()
    bad["doi"] = "10.5555/not-in-upload"
    result = essay_research_summary(seq, TOPIC, "draft", [bad])
    assert result["refused"] == "invent-forbid"


def test_scopus_name_still_refused(workspace):
    write_upload(workspace)
    seq = open_sequence()
    bad = source()
    bad["resolver"] = "Scopus"
    result = essay_research_summary(seq, TOPIC, "draft", [bad])
    assert result["refused"] == "invent-forbid"


def test_resolver_flip_keeps_the_draft_fields(workspace, monkeypatch):
    """A second enrich that misses is not a confirm failure. The draft fields stay."""
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    text = (
        f"Smith, J. (2020) {FIXTURE_TITLE}.\n"
        "The Strait handles a large share of flows.\n"
    )
    write_upload(workspace, text=text)
    seq = open_sequence()
    payload = source()
    payload["title"] = FIXTURE_TITLE
    payload["quote"] = "The Strait handles a large share of flows."
    draft = essay_research_summary(seq, TOPIC, "draft", [payload])
    assert draft["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [payload])
    assert confirmed["stored"] is True
    assert confirmed.get("refused") is None
    assert "saved files changed" not in confirmed.get("reason", "")
    assert confirmed["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    state = json.loads(
        (workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "state.json").read_text(encoding="utf-8")
    )
    assert state["research"]["summary"]["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
