from helpers import ESSAY, TOPIC, open_sequence, source, write_upload

from essay_writer.research import essay_research_summary


def test_fabricated_source_is_refused(workspace):
    seq = open_sequence()
    fake = {
        "author": "Nobody, N.",
        "title": "A paper that was not gathered",
        "year": "1999",
        "doi": "10.0000/not-real",
    }
    result = essay_research_summary(seq, TOPIC, "draft", [fake])
    assert result["ok"] is False
    assert result["refused"] == "invent-forbid"
    assert result["stored"] is False
    research = (
        workspace / "Essay-writer" / ESSAY / "sequences" / "1" / ".drafts" / "essay.research.summary"
    )
    assert not research.exists()


def test_sample_study_is_not_a_source(workspace):
    sample = {
        "origin": "sample",
        "locator": "docs/samples-study.md",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
    }
    seq = open_sequence()
    result = essay_research_summary(seq, TOPIC, "draft", [sample])
    assert result["refused"] == "invent-forbid"
    assert result["stored"] is False


def test_lookup_volume_pages_url_and_publisher_are_not_retyped(workspace):
    """Fields already marked lookup stay lookup. A new publisher is still invented."""
    from essay_writer.invent import gather_source
    from essay_writer.state import load_state, save_state

    write_upload(
        workspace,
        text="Smith, J. (2020) Chokepoints and crude.\nThe Strait handles a large share of flows.\n",
    )
    seq = open_sequence()
    locator = f"uploads/{ESSAY}/smith.md"
    state = load_state(seq)
    state["research"] = {
        "summary": {
            "sources": [
                {
                    "id": "src-1",
                    "origin": "upload",
                    "locator": locator,
                    "author": "Smith, J.",
                    "year": "2020",
                    "title": "Chokepoints and crude",
                    "volume": "42",
                    "pages": "101-112",
                    "url": "https://doi.org/10.5555/fixture-chokepoint",
                    "publisher": "Elsevier",
                    "field_sources": {
                        "volume": "lookup",
                        "pages": "lookup",
                        "url": "lookup",
                        "publisher": "lookup",
                    },
                }
            ]
        },
        "full": None,
    }
    save_state(seq, state)
    raw = {
        "id": "src-1",
        "origin": "upload",
        "locator": locator,
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "volume": "42",
        "pages": "101-112",
        "url": "https://doi.org/10.5555/fixture-chokepoint",
        "publisher": "Elsevier",
        "field_sources": {"publisher": "file"},
    }
    kept, issues = gather_source(seq, raw, 0)
    assert issues == []
    assert kept is not None
    assert kept["volume"] == "42"
    assert kept["pages"] == "101-112"
    assert kept["url"] == "https://doi.org/10.5555/fixture-chokepoint"
    assert kept["publisher"] == "Elsevier"
    assert kept["field_sources"]["volume"] == "lookup"
    assert kept["field_sources"]["pages"] == "lookup"
    assert kept["field_sources"]["url"] == "lookup"
    assert kept["field_sources"]["publisher"] == "lookup"

    invented = dict(raw)
    invented["publisher"] = "Invented Press"
    rejected, bad = gather_source(seq, invented, 0)
    assert rejected is None
    assert bad[0]["code"] == "invent-forbid"
    assert "publisher" in bad[0]["reason"]


def test_lookup_container_issue_place_and_accessed_are_not_retyped(workspace):
    """A look-up fills a blank field. A different value is still invented."""
    from essay_writer.invent import gather_source
    from essay_writer.state import load_state, save_state
    from essay_writer.textutil import reference_line

    write_upload(
        workspace,
        text="Smith, J. (2020) Chokepoints and crude.\nThe Strait handles a large share of flows.\n",
    )
    seq = open_sequence()
    locator = f"uploads/{ESSAY}/smith.md"
    state = load_state(seq)
    state["research"] = {
        "summary": {
            "sources": [
                {
                    "id": "src-1",
                    "origin": "upload",
                    "locator": locator,
                    "author": "Smith, J.",
                    "year": "2020",
                    "title": "Chokepoints and crude",
                    "container": "Journal of Looked Up study",
                    "issue": "2",
                    "place": "Cardiff",
                    "accessed": "17 May 2022",
                    "field_sources": {
                        "container": "lookup",
                        "issue": "lookup",
                        "place": "lookup",
                        "accessed": "lookup",
                    },
                }
            ]
        },
        "full": None,
    }
    save_state(seq, state)
    raw = {
        "id": "src-1",
        "origin": "upload",
        "locator": locator,
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "container": "Journal of Looked Up study",
        "issue": "2",
        "place": "Cardiff",
        "accessed": "17 May 2022",
    }
    kept, issues = gather_source(seq, raw, 0)
    assert issues == []
    assert kept is not None
    assert kept["container"] == "Journal of Looked Up study"
    assert kept["issue"] == "2"
    assert kept["place"] == "Cardiff"
    assert kept["accessed"] == "17 May 2022"
    for field in ("container", "issue", "place", "accessed"):
        assert kept["field_sources"][field] == "lookup"
    assert "Journal of Looked Up study" in reference_line(kept)

    invented = dict(raw)
    invented["place"] = "Bristol"
    rejected, bad = gather_source(seq, invented, 0)
    assert rejected is None
    assert bad[0]["code"] == "invent-forbid"
    assert "place" in bad[0]["reason"]


def test_quote_must_be_in_the_file(workspace):
    write_upload(workspace)
    seq = open_sequence()
    bad = source()
    bad["quote"] = "This sentence was not in the upload."
    result = essay_research_summary(seq, TOPIC, "draft", [bad])
    assert result["refused"] == "invent-forbid"


def test_cross_essay_source_is_refused(workspace):
    write_upload(workspace, "MOD1011AA")
    seq = open_sequence()
    result = essay_research_summary(seq, TOPIC, "draft", [source("MOD1011AA")])
    assert result["ok"] is False
    assert result["refused"] == "cross-essay"


def test_matched_crossref_sample_adds_doi(workspace, monkeypatch):
    from essay_writer.resolvers import FIXTURE_TITLE

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    text = (
        f"Patel, A. (2019) {FIXTURE_TITLE}.\n"
        "Evidence line for the corridor.\n"
    )
    write_upload(workspace, text=text)
    seq = open_sequence()
    item = {
        "id": "src-fixture",
        "origin": "upload",
        "locator": f"uploads/{ESSAY}/smith.md",
        "author": "Patel, A.",
        "year": "2019",
        "title": FIXTURE_TITLE,
        "quote": "Evidence line for the corridor.",
    }
    draft = essay_research_summary(seq, TOPIC, "draft", [item])
    assert draft["ok"] is True
    assert draft["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    assert draft["resolvers_called"]
