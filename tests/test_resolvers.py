import json

from helpers import ESSAY, TOPIC, card_digest_for, open_sequence, source, write_upload

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


def test_openalex_lookup_sends_the_key_when_one_is_stored(monkeypatch):
    from essay_writer import resolvers

    seen: dict[str, str] = {}
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("OPENALEX_API_KEY", "oa-key-not-echoed")

    def fake(url):
        seen["url"] = url
        return None

    monkeypatch.setattr(resolvers, "_lookup_json", fake)
    resolvers.openalex_lookup("chokepoints")
    assert "api_key=oa-key-not-echoed" in seen["url"]


def test_openalex_lookup_sends_no_key_when_none_is_stored(monkeypatch):
    from essay_writer import resolvers

    seen: dict[str, str] = {}
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)

    def fake(url):
        seen["url"] = url
        return None

    monkeypatch.setattr(resolvers, "_lookup_json", fake)
    resolvers.openalex_lookup("chokepoints")
    assert "api_key" not in seen["url"]


def test_saved_crossref_sample_matches_title():
    record = crossref_lookup(FIXTURE_TITLE, fetch=fixture_crossref_fetch)
    assert record is not None
    assert record["doi"] == "10.5555/fixture-chokepoint"
    assert record["container"] == "Journal of Transport Geography"


def test_crossref_uses_year_and_author_to_pick_the_real_work():
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Highly accurate protein structure prediction with AlphaFold"],
                    "DOI": "10.1/wrong-year",
                    "issued": {"date-parts": [[2019]]},
                    "author": [{"family": "Jumper"}],
                },
                {
                    "title": ["Highly accurate protein structure prediction with AlphaFold"],
                    "DOI": "10.1038/s41586-021-03819-2",
                    "issued": {"date-parts": [[2021]]},
                    "author": [{"family": "Jumper"}],
                    "container-title": ["Nature"],
                },
            ]
        }
    }
    record = crossref_lookup(
        "Highly accurate protein structure prediction with AlphaFold",
        fetch=lambda query: payload,
        year="2021",
        author="Jumper, J.",
    )
    assert record is not None
    assert record["doi"] == "10.1038/s41586-021-03819-2"


def test_crossref_refuses_a_same_title_work_from_another_year():
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Deep learning"],
                    "DOI": "10.1/wrong",
                    "issued": {"date-parts": [[2019]]},
                    "author": [{"family": "LeCun"}],
                }
            ]
        }
    }
    assert crossref_lookup("Deep learning", fetch=lambda query: payload, year="2015") is None


def test_crossref_refuses_a_same_title_work_by_another_author():
    payload = {
        "message": {
            "items": [
                {
                    "title": ["Deep learning"],
                    "DOI": "10.1/wrong",
                    "issued": {"date-parts": [[2015]]},
                    "author": [{"family": "Someone"}],
                }
            ]
        }
    }
    assert crossref_lookup("Deep learning", fetch=lambda query: payload, author="LeCun, Y.") is None


def test_crossref_without_a_citation_still_reads_only_the_first_row():
    payload = {
        "message": {
            "items": [
                {"title": ["Deep learning"], "DOI": "10.1/first"},
                {"title": ["Deep learning"], "DOI": "10.1/second"},
            ]
        }
    }
    record = crossref_lookup("Deep learning", fetch=lambda query: payload)
    assert record is not None
    assert record["doi"] == "10.1/first"


def test_lookups_send_the_stored_email_as_the_polite_pool_contact(monkeypatch):
    from essay_writer import resolvers

    seen: list[str] = []
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    monkeypatch.setattr(resolvers, "_lookup_json", lambda url: seen.append(url) or {})
    assert resolvers.crossref_lookup("Deep learning") is None
    assert resolvers.openalex_lookup("Deep learning") is None
    assert len(seen) == 2
    assert all("mailto=reader%40example.com" in url for url in seen)


def test_crossref_sample_does_not_match_other_titles():
    record = crossref_lookup("Chokepoints and crude", fetch=fixture_crossref_fetch)
    assert record is None


def test_matched_lookup_stores_doi_and_lists_crossref(workspace, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    text = f"Smith, J. (2020) {FIXTURE_TITLE}.\nThe Strait handles a large share of flows.\n"
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
    confirmed = essay_research_summary(
        seq, TOPIC, "confirm", [payload], cardDigest=card_digest_for(seq, "essay.research.summary")
    )
    assert confirmed["stored"] is True
    state = json.loads(
        (workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "state.json").read_text(
            encoding="utf-8"
        )
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
    text = f"Smith, J. (2020) {FIXTURE_TITLE}.\nThe Strait handles a large share of flows.\n"
    write_upload(workspace, text=text)
    seq = open_sequence()
    payload = source()
    payload["title"] = FIXTURE_TITLE
    payload["quote"] = "The Strait handles a large share of flows."
    draft = essay_research_summary(seq, TOPIC, "draft", [payload])
    assert draft["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    confirmed = essay_research_summary(
        seq, TOPIC, "confirm", [payload], cardDigest=card_digest_for(seq, "essay.research.summary")
    )
    assert confirmed["stored"] is True
    assert confirmed.get("refused") is None
    assert "saved files changed" not in confirmed.get("reason", "")
    assert confirmed["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    state = json.loads(
        (workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["research"]["summary"]["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
