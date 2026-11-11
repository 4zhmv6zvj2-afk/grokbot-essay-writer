"""Policy B: hard-fail only an unambiguous citation. A lone name is flagged."""

from helpers import (
    ESSAY,
    TOPIC,
    card_digest_for,
    open_sequence,
    pack,
    source,
    write_upload,
)

from essay_writer.gates import essay_gates
from essay_writer.research import essay_research_summary
from essay_writer.review import essay_review
from essay_writer.textutil import citation_records, citation_tokens, count_words
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word

QUESTION = "How do chokepoints constrain the corridor?"


def _pack(seq: str, authors: list[tuple[str, str]]) -> dict:
    return {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [{"author": author, "year": year} for author, year in authors],
    }


def _citations(seq: str, body: str, authors: list[tuple[str, str]] | None = None) -> dict:
    return essay_gates(seq, _pack(seq, authors or [("Smith, J.", "2020")]), body=body)


def _gate(report: dict, name: str) -> dict:
    return next(item for item in report["gates"] if item["name"] == name)


def test_hard_cues_and_parentheticals_fail_when_ungathered(workspace):
    seq = open_sequence()
    cases = (
        "Patel et al. (2019) names one corridor.",
        "Smith and Jones (2020) name one corridor.",
        "Dr Patel (2019) names one corridor.",
        "J. Patel (2019) names one corridor.",
        "John Smith (2019) names one corridor.",
        "SMITH (2019) names one corridor.",
        "One corridor moved (Patel, 2019).",
        "One corridor moved (Page, 2020).",
    )
    for body in cases:
        report = _citations(seq, body)
        gate = _gate(report, "citations")
        assert gate["passed"] is False, body
        assert gate["questionable"] == []


def test_lone_names_are_possible_citations(workspace):
    seq = open_sequence()
    expected = {
        "Patel (2019) names one corridor.": "patel, 2019",
        "Marshall (1947) names one corridor.": "marshall, 1947",
        "Woods (2020) names one corridor.": "woods, 2020",
        "Google (2020) names one corridor.": "google, 2020",
        "France (2020) names one corridor.": "france, 2020",
    }
    for body, token in expected.items():
        report = _citations(seq, body)
        gate = _gate(report, "citations")
        assert gate["passed"] is True, body
        assert gate["questionable"] == [token]
        assert report["questionable_citations"] == [token]
        assert token in gate["reason"]


def test_gathered_narrative_citations_are_not_flagged(workspace):
    seq = open_sequence()
    smith = _citations(seq, "Smith et al. (2020) names one corridor.")
    assert _gate(smith, "citations")["passed"] is True
    assert _gate(smith, "citations")["questionable"] == []
    parenthetical = _citations(seq, "One corridor moved (Smith et al., 2020).")
    assert _gate(parenthetical, "citations")["passed"] is True
    assert parenthetical["questionable_citations"] == []
    joint = _citations(
        seq,
        "Smith, Jones, and Brown (2020) name one corridor.",
        [("Smith, J.", "2020"), ("Jones, A.", "2020"), ("Brown, R.", "2020")],
    )
    assert _gate(joint, "citations")["passed"] is True
    assert _gate(joint, "citations")["questionable"] == []


def test_label_spans_are_not_citations(workspace):
    seq = open_sequence()
    bodies = (
        "The Marshall Plan (1948) rebuilt trade.",
        "The Black Death (1347) changed labour.",
        "Bretton Woods (1944) set the rate.",
        "The Spanish Flu (1918) closed ports.",
        "The United Nations (1945) met.",
        "The European Union (1993) widened the market.",
        "ASEAN (1967) met.",
        "June (2020) stayed open.",
        "Monday (2020) stayed open.",
        "Manchester (2020) stayed open.",
        "The Smith Report (2020) stayed on the shelf.",
    )
    for body in bodies:
        assert citation_tokens(body) == [], body
        report = _citations(seq, body)
        assert _gate(report, "citations")["passed"] is True
        assert report["questionable_citations"] == []


def test_multi_word_labels_outside_the_list_stay_hard_failures(workspace):
    """Known shape limit. Changing the label list later has to do this on purpose."""
    seq = open_sequence()
    cases = {
        "New York (2020) set one rate.": "new york, 2020",
        "Supreme Court (2020) set one rate.": "supreme court, 2020",
        "United States (2020) set one rate.": "united states, 2020",
    }
    for body, token in cases.items():
        report = _citations(seq, body)
        gate = _gate(report, "citations")
        assert gate["passed"] is False, body
        assert token in gate["reason"]
        assert gate["questionable"] == []


def test_page_and_theresa_may_stay_silent_label_collisions():
    """page and May are already label words, so these narrative spans are not citations."""
    assert citation_records("Page (2020) names a leaf.") == []
    assert citation_records("Theresa May (2019) names a corridor.") == []


def test_a_gathered_lone_name_is_not_flagged(workspace):
    seq = open_sequence()
    report = _citations(seq, "Smith (2020) names one corridor.")
    assert _gate(report, "citations")["passed"] is True
    assert report["questionable_citations"] == []


def test_word_writes_a_possible_citation_and_refuses_a_hard_miss(workspace):
    write_upload(workspace)
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(f"Genre: report\nQuestion: {QUESTION}\n", encoding="utf-8")
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(
        seq, TOPIC, "confirm", [source()], cardDigest=card_digest_for(seq, "essay.research.summary")
    )
    constitution = f"This is a report. {QUESTION}"
    essay_review(seq, "6", "PASS", "draft", constitution=constitution)
    essay_review(seq, "6", "PASS", "confirm", constitution=constitution)

    possible = pack()
    possible["sections"][1] = {
        "heading": possible["sections"][1]["heading"],
        "body": possible["sections"][1]["body"]
        + " Patel (2019) names one corridor beside the strait.",
    }
    essay_pack_validate(seq, possible, "draft")
    essay_pack_validate(seq, possible, "confirm")
    preview = essay_pack_render_word(seq, possible, "draft", stage="6")
    assert preview["wrote"] is False
    written = essay_pack_render_word(seq, possible, "confirm", stage="6")
    assert written.get("refused") != "gates", written
    assert written["wrote"] is True
    assert written["questionable_citations"] == ["patel, 2019"]

    hard = pack()
    hard["sections"][1] = {
        "heading": hard["sections"][1]["heading"],
        "body": hard["sections"][1]["body"]
        + " Dr Patel (2019) names one corridor beside the strait.",
    }
    essay_pack_validate(seq, hard, "draft")
    essay_pack_validate(seq, hard, "confirm")
    essay_pack_render_word(seq, hard, "draft", stage="6")
    refused = essay_pack_render_word(seq, hard, "confirm", stage="6")
    assert refused["ok"] is False
    assert refused["refused"] == "invent-forbid"
    assert refused["wrote"] is False
    assert "dr patel, 2019" in refused["reason"]


def test_word_count_does_not_depend_on_citation_shape():
    base = "one two three four five six seven eight nine"
    pairs = (
        (f"{base} Smith (2020)", f"{base} (Smith, 2020)"),
        (f"{base} Smith et al. (2020)", f"{base} (Smith et al., 2020)"),
        (f"{base} SMITH (2020)", f"{base} (SMITH, 2020)"),
        (f"{base} Pérez (2019)", f"{base} (Pérez, 2019)"),
    )
    for narrative, parenthetical in pairs:
        assert count_words(narrative, exclude_citations=True) == count_words(
            parenthetical, exclude_citations=True
        )
        assert citation_tokens(narrative)
        assert citation_tokens(parenthetical)
