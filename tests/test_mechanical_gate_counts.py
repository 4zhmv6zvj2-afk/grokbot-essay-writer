"""Mechanical gates use the same cite list and word counter as pack validation.

Parenthetical and narrative citations both have to match a gathered author
and year. A word band that excludes in-text citations does not count those
parentheses as extra words. The Word write log counts reference lines apart
from gathered sources.
"""

from pathlib import Path

from helpers import open_sequence

from essay_writer.gates import essay_gates
from essay_writer.late_chain import log_word_docx_written, log_word_manifest


def _gate(report: dict, name: str) -> dict:
    for item in report["gates"]:
        if item["name"] == name:
            return item
    raise AssertionError(name)


def test_word_band_ignores_citations_when_the_rule_says_so(workspace):
    """Ten body words plus one parenthetical cite stay inside a 10-word band."""
    seq = open_sequence()
    body = "one two three four five six seven eight nine ten (Smith, 2020)"
    pack = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "word_rules": {"min": 10, "max": 10, "exclude_in_text_citations": True},
        "sources": [{"author": "Smith, J.", "year": "2020"}],
    }
    report = essay_gates(seq, pack, body=body)
    band = _gate(report, "word-band")
    assert band["passed"] is True
    assert "(10 counted" not in band["reason"]
    assert "10–10" in band["reason"] or "inside the word band" in band["reason"]


def test_narrative_and_parenthetical_cites_use_the_gathered_source(workspace):
    """Smith (2020) is a citation. A name the pack did not gather still fails."""
    seq = open_sequence()
    pack = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [{"author": "Smith, J.", "year": "2020"}],
    }
    matched = essay_gates(seq, pack, body="Smith (2020) reports one corridor.")
    assert _gate(matched, "citations")["passed"] is True
    assert _gate(matched, "references")["passed"] is True
    parenthetical = essay_gates(seq, pack, body="One corridor is named (Smith, 2020).")
    assert _gate(parenthetical, "citations")["passed"] is True
    missing = essay_gates(seq, pack, body="Patel (2019) reports one corridor.")
    assert _gate(missing, "citations")["passed"] is False
    assert "patel, 2019" in _gate(missing, "citations")["reason"]
    bare = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [{"author": "Smith, J."}],
    }
    unnamed_year = essay_gates(seq, bare, body="Smith (2020) reports one corridor.")
    assert _gate(unnamed_year, "references")["passed"] is False


def test_docx_log_counts_references_apart_from_sources(monkeypatch):
    """write_docx logs refs_n from the reference list, as the manifest does."""
    seen: dict[str, dict] = {}

    def capture(step, essay_id, **kwargs):
        seen[step] = {"essay_id": essay_id, **kwargs}

    monkeypatch.setattr("essay_writer.debug_log.log_word_step", capture)
    report = {"sources": [{}, {}], "references": [{}]}
    pack = {"title": "Corridor", "conclusion": "open"}
    log_word_manifest("MOD1004AA-1", pack, report, pack_path="pack.json")
    log_word_docx_written("MOD1004AA-1", pack, report, [], Path("out.docx"))
    assert seen["word_manifest"]["sources_count"] == 2
    assert seen["word_manifest"]["refs_count"] == 1
    assert seen["write_docx"]["sources_count"] == 2
    assert seen["write_docx"]["refs_count"] == 1
