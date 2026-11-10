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


def test_narrative_citations_ignore_events_and_accept_joint_authors(workspace):
    """Events and acronyms are not citations. Joint authors and et al. are."""
    from essay_writer.textutil import citation_tokens, count_words, token_allowed

    seq = open_sequence()
    pack = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [
            {"author": "Smith, J.", "year": "2020"},
            {"author": "Jones, A.", "year": "2020"},
        ],
    }
    prose = (
        "World War II (1939) and The Great Depression (1929) sit beside GDP (2020), "
        "OECD (2021), and Chapter Four (2020). Smith and Jones (2020) name the corridor. "
        "Smith & Jones (2020) agree. Smith et al. (2020) add a line. Patel et al. (2019) does not."
    )
    assert citation_tokens("World War II (1939) changed the route.") == []
    assert citation_tokens("GDP (2020) fell.") == []
    assert citation_tokens("Smith & Jones (2020) agree.") == ["smith & jones, 2020"]
    assert citation_tokens("Patel et al. (2019) does not.") == ["patel et al., 2019"]
    report = essay_gates(seq, pack, body=prose)
    reason = _gate(report, "citations")["reason"]
    assert "world war" not in reason
    assert "gdp" not in reason
    assert "oecd" not in reason
    assert "chapter four" not in reason
    assert "smith and jones" not in reason
    assert "smith & jones" not in reason
    assert "patel et al., 2019" in reason
    forms = {"smith, 2020", "jones, 2020"}
    assert token_allowed("smith and jones, 2020", forms)
    assert token_allowed("smith & jones, 2020", forms)
    assert token_allowed("(smith & jones, 2020)".strip("()"), forms) or token_allowed("smith & jones, 2020", forms)
    parenthetical = essay_gates(seq, pack, body="The corridor stays narrow (Smith & Jones, 2020).")
    assert _gate(parenthetical, "citations")["passed"] is True
    narrative = "one two three four five six seven eight nine Smith (2020)"
    paren = "one two three four five six seven eight nine (Smith, 2020)"
    assert count_words(narrative, exclude_citations=True) == count_words(paren, exclude_citations=True)
    shouted = "one two three four five six seven eight nine SMITH (2020)"
    accented = "one two three four five six seven eight nine Pérez (2019)"
    accented_paren = "one two three four five six seven eight nine (Pérez, 2019)"
    assert count_words(shouted, exclude_citations=True) == count_words(paren, exclude_citations=True)
    assert count_words(accented, exclude_citations=True) == count_words(accented_paren, exclude_citations=True)


def test_narrative_citations_cover_names_and_skip_periods(workspace):
    """A period label is not a citation. A real name, in any of these shapes, is."""
    from essay_writer.textutil import citation_tokens

    seq = open_sequence()
    pack = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [
            {"author": "Smith, J.", "year": "2020"},
            {"author": "Jones, A.", "year": "2020"},
            {"author": "Brown, C.", "year": "2020"},
        ],
    }
    periods = "Renaissance (1400), Enlightenment (1700), Brexit (2016), and Holocaust (1945) are events."
    assert citation_tokens(periods) == []
    clear = essay_gates(seq, pack, body=periods)
    reason = _gate(clear, "citations")["reason"]
    assert _gate(clear, "citations")["passed"] is True
    for label in ("renaissance", "enlightenment", "brexit", "holocaust"):
        assert label not in reason
    assert citation_tokens("SMITH (2020) names the corridor.") == ["smith, 2020"]
    assert citation_tokens("Pérez (2019) names the corridor.") == ["pérez, 2019"]
    assert citation_tokens("Castañeda (2020) names the corridor.") == ["castañeda, 2020"]
    assert citation_tokens("John Smith (2019) names the corridor.") == ["john smith, 2019"]
    assert citation_tokens("Dr Smith (2020) names the corridor.") == ["dr smith, 2020"]
    assert citation_tokens("Smith et al., (2020) name the corridor.") == ["smith et al., 2020"]
    assert citation_tokens("Smith, Jones, and Brown (2020) name the corridor.") == [
        "smith, jones, and brown, 2020"
    ]
    shouted = essay_gates(seq, pack, body="SMITH (2020) names the corridor in one sentence.")
    assert _gate(shouted, "citations")["passed"] is True
    titled = essay_gates(seq, pack, body="Dr Smith (2020) names the corridor in one sentence.")
    assert _gate(titled, "citations")["passed"] is True
    oxford = essay_gates(seq, pack, body="Smith, Jones, and Brown (2020) name the corridor.")
    assert _gate(oxford, "citations")["passed"] is True
    partial = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "sources": [{"author": "Brown, C.", "year": "2020"}],
    }
    invented_joint = essay_gates(
        seq,
        partial,
        body="Smith, Jones, and Brown (2020) name the corridor.",
    )
    joint_reason = _gate(invented_joint, "citations")["reason"]
    assert _gate(invented_joint, "citations")["passed"] is False
    assert "smith, jones, and brown, 2020" in joint_reason
    for body in (
        "PATEL (2019) names a corridor that was not gathered.",
        "Pérez (2019) names a corridor that was not gathered.",
        "John Smith (2019) names a corridor that was not gathered.",
    ):
        report = essay_gates(seq, pack, body=body)
        assert _gate(report, "citations")["passed"] is False, body


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


def test_pack_band_keeps_its_max_and_copies_only_the_citation_flag(workspace):
    """A tighter pack maximum stays. The missing citation flag is copied onto it."""
    from essay_writer.paths import essay_dir

    body = "one two three four five six seven eight nine ten (Smith, 2020)"
    pack = {
        "genre": "essay",
        "conclusion": "open",
        "word_rules": {"min": 10, "max": 10},
        "sources": [{"author": "Smith, J.", "year": "2020"}],
    }
    studied = open_sequence("MOD1011AA")
    pack["essay_id"] = studied
    studied_report = essay_gates(studied, pack, body=body)
    studied_band = _gate(studied_report, "word-band")
    assert studied_band["passed"] is True
    assert "10–10" in studied_band["reason"]

    briefed = open_sequence()
    brief = essay_dir("MOD1004AA") / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        "Write 800 words. In-text citations do not count.\n",
        encoding="utf-8",
    )
    pack["essay_id"] = briefed
    brief_report = essay_gates(briefed, pack, body=body)
    brief_band = _gate(brief_report, "word-band")
    assert brief_band["passed"] is True
    assert "10–10" in brief_band["reason"]
    assert "720" not in brief_band["reason"]

    counted = dict(pack)
    counted["word_rules"] = {"min": 10, "max": 10, "exclude_in_text_citations": False}
    forced = essay_gates(studied, counted, body=body)
    forced_band = _gate(forced, "word-band")
    assert forced_band["passed"] is False
    assert "10–10" in forced_band["reason"]


def test_plagiarism_scan_refuses_a_non_utf8_text_file(workspace):
    """A text upload that is not UTF-8 fails closed. A valid file is still scanned."""
    seq = open_sequence()
    folder = workspace / "uploads" / "MOD1004AA"
    folder.mkdir(parents=True)
    (folder / "broken.txt").write_bytes(
        b"The strait handles a large share of seaborne crude flows.\n\xff"
    )
    (folder / "clean.txt").write_text(
        "The harbour keeps a written record of every winter closure.\n",
        encoding="utf-8",
    )
    broken = essay_gates(
        seq,
        {
            "essay_id": seq,
            "genre": "essay",
            "conclusion": "open",
            "sources": [{"locator": "uploads/MOD1004AA/broken.txt"}],
        },
        body="A clean sentence stays here.",
    )
    assert broken["plagiarism"]["passed"] is False
    assert broken["passed"] is False
    assert "broken.txt" in broken["plagiarism"]["reason"]
    assert broken["plagiarism"]["code"] == "gathered-encoding"
    assert "not valid UTF-8" in broken["plagiarism"]["reason"]
    assert "Re-save" in broken["plagiarism"]["reason"]
    wide = "The harbour keeps a written record of every winter closure."
    (folder / "wide.txt").write_bytes(wide.encode("utf-16"))
    encoded = essay_gates(
        seq,
        {
            "essay_id": seq,
            "genre": "essay",
            "conclusion": "open",
            "sources": [{"locator": "uploads/MOD1004AA/wide.txt"}],
        },
        body="A clean sentence stays here.",
    )
    assert encoded["plagiarism"]["code"] != "gathered-encoding"
    from essay_writer.invent import read_gathered_text
    from essay_writer.textutil import module_brief_text

    assert "harbour" in read_gathered_text(folder / "wide.txt", seq).casefold()
    brief = workspace / "Essay-writer" / "MOD1004AA" / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_bytes("Write 800 words in the brief.\n".encode("utf-16"))
    assert "800" in module_brief_text(seq)
    copied = "The harbour keeps a written record of every winter closure."
    scanned = essay_gates(
        seq,
        {
            "essay_id": seq,
            "genre": "essay",
            "conclusion": "open",
            "sources": [{"locator": "uploads/MOD1004AA/clean.txt"}],
        },
        body=copied,
    )
    assert scanned["plagiarism"]["passed"] is False
    assert copied in scanned["plagiarism"]["matches"]


def test_an_unreadable_gathered_file_is_not_labelled_as_bad_utf8(workspace, monkeypatch):
    """A permission error is a read failure, not an encoding failure."""
    seq = open_sequence()
    folder = workspace / "uploads" / "MOD1004AA"
    folder.mkdir(parents=True)
    locked = folder / "locked.txt"
    locked.write_text("A sentence that cannot be opened.\n", encoding="utf-8")
    real = Path.read_bytes

    def blocked(self, *args, **kwargs):
        if self.name == "locked.txt":
            raise OSError("permission denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", blocked)
    report = essay_gates(
        seq,
        {
            "essay_id": seq,
            "genre": "essay",
            "conclusion": "open",
            "sources": [{"locator": "uploads/MOD1004AA/locked.txt"}],
        },
        body="A clean sentence stays here.",
    )
    assert report["plagiarism"]["code"] == "gathered-unreadable"
    assert "could not be read" in report["plagiarism"]["reason"]
    assert "locked.txt" in report["plagiarism"]["reason"]
    assert "not valid UTF-8" not in report["plagiarism"]["reason"]


def test_mark_scheme_citation_flag_is_the_band_and_the_section_budget(workspace, monkeypatch):
    """The mark scheme flag is used once. A pack maximum stays."""
    from essay_writer.brief_checks import before_word
    from essay_writer.paths import essay_dir

    seq = open_sequence()
    scheme = essay_dir("MOD1004AA") / "mark-scheme.md"
    scheme.parent.mkdir(parents=True, exist_ok=True)
    scheme.write_text(
        "Write 800 words. In-text citations are not counted.\n",
        encoding="utf-8",
    )
    seen: dict[str, bool] = {}
    real = before_word

    def capture(*args, **kwargs):
        seen["exclude"] = kwargs.get("exclude_citations")
        return real(*args, **kwargs)

    monkeypatch.setattr("essay_writer.brief_checks.before_word", capture)
    body = "one two three four five six seven eight nine ten (Smith, 2020)"
    pack = {
        "essay_id": seq,
        "genre": "essay",
        "conclusion": "open",
        "word_rules": {"min": 10, "max": 10},
        "sections": [{"heading": "Body", "body": body}],
        "sources": [{"author": "Smith, J.", "year": "2020"}],
    }
    report = essay_gates(seq, pack, body=body)
    assert seen["exclude"] is True
    assert _gate(report, "word-band")["passed"] is True
    assert "10–10" in _gate(report, "word-band")["reason"]
    forced = dict(pack)
    forced["word_rules"] = {"min": 10, "max": 10, "exclude_in_text_citations": False}
    essay_gates(seq, forced, body=body)
    assert seen["exclude"] is False


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
