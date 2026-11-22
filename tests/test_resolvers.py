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


def test_live_lookup_sends_the_gathered_year_and_author(monkeypatch):
    from essay_writer import resolvers

    seen: list[str] = []
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.delenv("ESSAY_WRITER_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)

    def fake(url: str):
        seen.append(url)
        return {"message": {"items": []}, "results": []}

    monkeypatch.setattr(resolvers, "_lookup_json", fake)
    record, calls = resolvers._lookup_chain(
        "Deep learning",
        None,
        year="2015",
        author="LeCun, Y.",
    )
    assert record is None
    crossref = next(url for url in seen if "api.crossref.org" in url)
    assert "LeCun" in crossref
    assert "2015" in crossref
    assert "type%3Ajournal-article" in crossref or "type:journal-article" in crossref
    assert any(item["name"] == "crossref" and item["result"] == "missed" for item in calls)


def test_openalex_skips_a_same_title_work_from_another_year(monkeypatch):
    from essay_writer import resolvers

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setattr(
        resolvers,
        "_lookup_json",
        lambda url: {
            "results": [
                {
                    "title": "Deep learning",
                    "publication_year": 2019,
                    "doi": "https://doi.org/10.1/wrong",
                    "authorships": [{"author": {"display_name": "Yann LeCun"}}],
                },
                {
                    "title": "Deep learning",
                    "publication_year": 2015,
                    "doi": "https://doi.org/10.1/right",
                    "authorships": [{"author": {"display_name": "Yann LeCun"}}],
                },
            ]
        },
    )
    record = resolvers.openalex_lookup("Deep learning", year="2015", author="LeCun, Y.")
    assert record is not None
    assert record["doi"] == "10.1/right"
    assert resolvers.openalex_lookup("Deep learning", year="2014", author="LeCun, Y.") is None


def test_lookup_chain_does_not_keep_an_openalex_doi_crossref_rejected(monkeypatch):
    from essay_writer import resolvers

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.delenv("ESSAY_WRITER_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)

    def fake(url: str):
        if "api.crossref.org" in url:
            return {
                "message": {
                    "items": [
                        {
                            "title": ["Deep learning"],
                            "DOI": "10.1/wrong-year",
                            "issued": {"date-parts": [[2019]]},
                            "author": [{"family": "LeCun"}],
                        }
                    ]
                }
            }
        if "api.openalex.org" in url:
            return {
                "results": [
                    {
                        "title": "Deep learning",
                        "publication_year": 2019,
                        "doi": "https://doi.org/10.1/also-wrong",
                        "authorships": [{"author": {"display_name": "Yann LeCun"}}],
                    }
                ]
            }
        return None

    monkeypatch.setattr(resolvers, "_lookup_json", fake)
    record, calls = resolvers._lookup_chain(
        "Deep learning",
        None,
        year="2015",
        author="LeCun, Y.",
    )
    assert record is None
    assert [item["result"] for item in calls] == ["missed", "missed"]


def test_crossref_http_error_is_a_miss_not_an_exception(monkeypatch):
    from essay_writer import resolvers, safe_url

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")

    def refused(url, **kwargs):
        return safe_url.Response(429, {}, b'{"message": "Too many requests"}')

    monkeypatch.setattr(resolvers.safe_url, "open_url", refused)
    assert resolvers.crossref_lookup("Deep learning", year="2015", author="LeCun, Y.") is None
    assert resolvers.openalex_lookup("Deep learning", year="2015", author="LeCun, Y.") is None

    def strange(url, **kwargs):
        return safe_url.Response(200, {}, b'{"message": "not-an-object"}')

    monkeypatch.setattr(resolvers.safe_url, "open_url", strange)
    assert resolvers.crossref_lookup("Deep learning", year="2015") is None


def test_crossref_without_a_citation_accepts_only_one_exact_title():
    two = {
        "message": {
            "items": [
                {"title": ["Deep learning"], "DOI": "10.1/first"},
                {"title": ["Deep learning"], "DOI": "10.1/second"},
            ]
        }
    }
    assert crossref_lookup("Deep learning", fetch=lambda query: two) is None
    one = {
        "message": {
            "items": [
                {"title": ["A different paper"], "DOI": "10.1/other"},
                {"title": ["  Deep   Learning "], "DOI": "10.1/only"},
            ]
        }
    }
    record = crossref_lookup("Deep learning", fetch=lambda query: one)
    assert record is not None
    assert record["doi"] == "10.1/only"
    none = {"message": {"items": [{"title": ["Something else"], "DOI": "10.1/no"}]}}
    assert crossref_lookup("Deep learning", fetch=lambda query: none) is None


def test_crossref_sends_the_contact_email_and_openalex_does_not(monkeypatch):
    from essay_writer import resolvers

    seen: list[str] = []
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    monkeypatch.setattr(resolvers, "_lookup_json", lambda url: seen.append(url) or {})
    assert resolvers.crossref_lookup("Deep learning") is None
    assert resolvers.openalex_lookup("Deep learning") is None
    assert len(seen) == 2
    assert "mailto=reader%40example.com" in seen[0]
    assert "article-number" in seen[0]
    assert "mailto" not in seen[1]
    assert "per_page=" in seen[1]
    assert "per-page" not in seen[1]


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
