"""Plagiarism scan, source gathering, and one citation word-count rule.

A gathered text file is read as itself. UTF-8, UTF-8 with a byte-order mark,
and UTF-16 with a byte-order mark stay in the scan and in source gathering.
A file that is not valid text is refused on both paths, and the scan does not
continue on a replaced copy. The word band and the section budgets drop
citation words under the same rule. A tighter pack maximum stays.
"""

from pathlib import Path

import pytest
from helpers import open_sequence

from essay_writer.gates import essay_gates
from essay_writer.invent import gather_sources, read_gathered_text
from essay_writer.paths import essay_dir, module_code

SENTENCE = "The café keeps a written record of every winter closure."
NOTE = f"Smith, J. (2020) Harbour notes.\n{SENTENCE}\n"
TEN = "one two three four five six seven eight nine ten"
CITED = f"{TEN} (Smith, 2020)"
ELEVEN = f"{TEN} eleven"

EXCLUDE_BRIEF = (
    "Write 800 words. In-text citations do not count.\nSection budgets: Harbour 10 words\n"
)
COUNT_BRIEF = "Write 800 words. In-text citations count.\nSection budgets: Harbour 10 words\n"


def _plant(workspace: Path, seq: str, name: str, raw: bytes) -> Path:
    folder = workspace / "uploads" / module_code(seq)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(raw)
    return path


def _source(seq: str, name: str) -> dict[str, str]:
    return {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{module_code(seq)}/{name}",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Harbour notes",
        "quote": SENTENCE,
    }


def _scan(seq: str, name: str, body: str) -> dict:
    return essay_gates(
        seq,
        {
            "essay_id": seq,
            "genre": "essay",
            "conclusion": "open",
            "sources": [{"locator": f"uploads/{module_code(seq)}/{name}"}],
        },
        body=body,
    )


def _as_note(text: str, encoding: str) -> bytes:
    if encoding == "utf-8":
        return text.encode("utf-8")
    if encoding == "utf-8-bom":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if encoding == "utf-16":
        return text.encode("utf-16")
    if encoding == "utf-16-be":
        return b"\xfe\xff" + text.encode("utf-16-be")
    raise AssertionError(encoding)


def _write_brief(seq: str, text: str) -> None:
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _word_report(seq: str, rules: dict, body: str, *, acknowledge: bool = False) -> dict:
    pack: dict = {
        "essay_id": seq,
        "genre": "report" if module_code(seq) == "MOD1004AA" else "essay",
        "conclusion": "open",
        "word_rules": rules,
        "sections": [{"heading": "Harbour", "body": body}],
        "sources": [{"author": "Smith, J.", "year": "2020"}],
    }
    if acknowledge:
        pack["section_words_acknowledged"] = True
    return essay_gates(seq, pack, body=body)


def _band(report: dict) -> dict:
    for item in report["gates"]:
        if item["name"] == "word-band":
            return item
    raise AssertionError("word-band")


def _budget(report: dict) -> dict:
    rows = report["section_budgets"]
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac1"])
def test_ew_hunt_s2_ac1(case_id, workspace: Path):
    """Valid UTF-8, a BOM, and UTF-16 with a BOM are scanned as the file text."""
    assert case_id == "ew-hunt-s2-ac1"
    seq = open_sequence()
    encodings = {
        "harbour-utf8.txt": "utf-8",
        "harbour-bom.txt": "utf-8-bom",
        "harbour-utf16.txt": "utf-16",
        "harbour-utf16be.txt": "utf-16-be",
    }
    for name, encoding in encodings.items():
        path = _plant(workspace, seq, name, _as_note(NOTE, encoding))
        assert read_gathered_text(path, seq) == NOTE
        kept, issues = gather_sources(seq, [_source(seq, name)])
        assert issues == []
        assert kept[0]["quote"] == SENTENCE
        assert "\ufffd" not in kept[0]["quote"]
        assert "\ufeff" not in kept[0]["quote"]

        clean = _scan(seq, name, "A clean sentence stays here.")
        assert clean["plagiarism"]["passed"] is True
        assert clean["plagiarism"]["code"] != "gathered-encoding"
        assert clean["plagiarism"]["matches"] == []

        copied = _scan(seq, name, SENTENCE)
        assert copied["plagiarism"]["code"] == "unquoted-exact"
        assert copied["plagiarism"]["code"] != "gathered-encoding"
        assert SENTENCE in copied["plagiarism"]["matches"]
        assert all("\ufffd" not in match for match in copied["plagiarism"]["matches"])
        assert all("\ufeff" not in match for match in copied["plagiarism"]["matches"])


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac2"])
def test_ew_hunt_s2_ac2(case_id, workspace: Path):
    """Invalid UTF-8 is refused. The copied sentence is not taken from a replaced copy."""
    assert case_id == "ew-hunt-s2-ac2"
    seq = open_sequence()
    name = "broken.txt"
    _plant(workspace, seq, name, NOTE.encode("utf-8") + b"\xff")
    report = _scan(seq, name, SENTENCE)
    assert report["plagiarism"]["passed"] is False
    assert report["passed"] is False
    assert report["plagiarism"]["code"] == "gathered-encoding"
    assert name in report["plagiarism"]["reason"]
    assert SENTENCE not in report["plagiarism"]["matches"]
    assert all("\ufffd" not in match for match in report["plagiarism"]["matches"])


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac3"])
def test_ew_hunt_s2_ac3(case_id, workspace: Path):
    """The same invalid file is refused by source gathering and by the scan."""
    assert case_id == "ew-hunt-s2-ac3"
    seq = open_sequence()
    name = "broken.txt"
    path = _plant(workspace, seq, name, NOTE.encode("utf-8") + b"\xff")
    with pytest.raises(ValueError, match="UTF-8"):
        read_gathered_text(path, seq)
    kept, issues = gather_sources(seq, [_source(seq, name)])
    assert kept == []
    assert issues
    assert all(item["code"] == "invent-forbid" for item in issues)
    assert any(name in item["reason"] and "UTF-8" in item["reason"] for item in issues)
    report = _scan(seq, name, SENTENCE)
    assert report["plagiarism"]["passed"] is False
    assert report["plagiarism"]["code"] == "gathered-encoding"
    assert SENTENCE not in report["plagiarism"]["matches"]


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac4"])
def test_ew_hunt_s2_ac4(case_id, workspace: Path):
    """A missing citation flag follows the brief on the band and the section budget."""
    assert case_id == "ew-hunt-s2-ac4"
    seq = open_sequence()
    _write_brief(seq, EXCLUDE_BRIEF)
    report = _word_report(seq, {"min": 10, "max": 10}, CITED)
    band = _band(report)
    budget = _budget(report)
    assert band["passed"] is True
    assert "10–10" in band["reason"]
    assert "720" not in band["reason"]
    assert budget["counted"] == 10
    assert budget["inside"] is True
    assert budget["missing"] is False


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac5"])
def test_ew_hunt_s2_ac5(case_id, workspace: Path):
    """A tighter pack maximum stays when the citation default is filled in."""
    assert case_id == "ew-hunt-s2-ac5"
    seq = open_sequence("MOD1011AA")
    rules = {"min": 10, "max": 10}
    cited = _word_report(seq, rules, CITED)
    cited_band = _band(cited)
    assert cited_band["passed"] is True
    assert "10–10" in cited_band["reason"]
    assert "2700" not in cited_band["reason"]
    assert "3300" not in cited_band["reason"]

    over = _word_report(seq, rules, ELEVEN)
    over_band = _band(over)
    assert over_band["passed"] is False
    assert "11 counted, 10–10" in over_band["reason"]
    assert "2700" not in over_band["reason"]


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac6"])
def test_ew_hunt_s2_ac6(case_id, workspace: Path):
    """An explicit pack citation flag is the one both paths use."""
    assert case_id == "ew-hunt-s2-ac6"
    seq = open_sequence()
    _write_brief(seq, COUNT_BRIEF)
    excluded = _word_report(
        seq,
        {"min": 10, "max": 10, "exclude_in_text_citations": True},
        CITED,
    )
    excluded_band = _band(excluded)
    excluded_budget = _budget(excluded)
    assert excluded_band["passed"] is True
    assert "10–10" in excluded_band["reason"]
    assert excluded_budget["counted"] == 10
    assert excluded_budget["inside"] is True

    _write_brief(seq, EXCLUDE_BRIEF)
    counted = _word_report(
        seq,
        {"min": 10, "max": 10, "exclude_in_text_citations": False},
        CITED,
        acknowledge=True,
    )
    counted_band = _band(counted)
    counted_budget = _budget(counted)
    assert counted_band["passed"] is False
    assert "12 counted, 10–10" in counted_band["reason"]
    assert counted_budget["counted"] == 12
    assert counted_budget["inside"] is False


@pytest.mark.parametrize("case_id", ["ew-hunt-s2-ac7"])
def test_ew_hunt_s2_ac7(case_id, workspace: Path):
    """Text with no citation counts the same on both paths and stays inside the band."""
    assert case_id == "ew-hunt-s2-ac7"
    seq = open_sequence()
    _write_brief(seq, EXCLUDE_BRIEF)
    report = _word_report(seq, {"min": 10, "max": 10}, TEN)
    band = _band(report)
    budget = _budget(report)
    assert band["passed"] is True
    assert "10–10" in band["reason"]
    assert budget["counted"] == 10
    assert budget["inside"] is True
