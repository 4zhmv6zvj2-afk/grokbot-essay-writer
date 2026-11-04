"""One final-Word look-up for a specialist source class. Stable ids: AC1–AC5.

The synth-mark brief names a specialist industry source class. When the gathered
files do not name one, the final Word does exactly one live look-up and reports
what it found. Nothing is added to the sources or the reference list, so no
source, reference line, or claim is invented. Fixture-only, soft only.
"""

import re
from pathlib import Path

from helpers import open_sequence

from essay_writer.mark_fit import final_specialist_lookup, specialist_lookup_query
from essay_writer.paths import essay_dir

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
MODULE = "SYN6004AA"
BRIEF = (FIXTURES / "synth-mark-brief-v1.md").read_text(encoding="utf-8")
GENERIC = [
    {
        "id": "src-1",
        "author": "Web Desk",
        "year": "2025",
        "title": "Sustainable supply chains explained",
        "url": "https://example.org/supply-chains",
        "locator": f"uploads/{MODULE}/web.md",
    }
]
SPECIALIST = [
    {
        "id": "src-1",
        "author": "Lloyd's List",
        "year": "2025",
        "title": "Carrier fuel rules and container rates",
        "locator": f"uploads/{MODULE}/lloyds.md",
    }
]


class Search:
    """A stand-in for the one live call. It records each query."""

    def __init__(self, hits):
        self.hits = hits
        self.calls: list[str] = []

    def __call__(self, query: str) -> dict:
        self.calls.append(query)
        return {"called": True, "tier": "free", "hits": self.hits}


def _plant(workspace: Path, text: str = BRIEF) -> str:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")
    return open_sequence(MODULE)


def _sections(name: str) -> list[dict[str, str]]:
    text = (FIXTURES / f"synth-mark-{name}-v1.md").read_text(encoding="utf-8")
    parts = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    return [
        {"heading": part.partition("\n")[0].strip(), "body": part.partition("\n")[2].strip()}
        for part in parts
    ]


def _pack(seq: str, sections, sources) -> dict:
    return {
        "essay_id": seq,
        "title": "Sustainability and the chain",
        "referencing": "harvard",
        "assessment": "Individual report",
        "genre": "report",
        "conclusion": "open",
        "sections": sections,
        "sources": sources,
    }


def test_ac1_a_named_class_costs_no_look_up(workspace):
    """AC1. When the pack already names a class, no search is made."""
    seq = _plant(workspace)
    search = Search([{"title": "Anything"}])
    attempt = final_specialist_lookup(
        seq, _pack(seq, _sections("strong"), SPECIALIST), search=search
    )
    assert attempt["attempted"] is False
    assert attempt["reason"] == "present"
    assert search.calls == []


def test_ac2_one_hit_is_reported_and_never_added(workspace):
    """AC2. A hit is named in the note and stays out of the sources."""
    seq = _plant(workspace)
    search = Search([{"title": "Container freight and fuel", "year": "2025", "doi": "10.1/x"}])
    pack = _pack(seq, _sections("weak"), GENERIC)
    attempt = final_specialist_lookup(seq, pack, search=search)
    assert attempt["attempted"] is True
    assert attempt["called"] is True
    assert attempt["found"] is True
    assert len(search.calls) == 1
    assert search.calls[0].startswith("Statista")
    assert "Container freight and fuel" in attempt["note"]
    assert "no reference line was invented" in attempt["note"]
    assert pack["sources"] == GENERIC
    assert attempt["candidate"] == {
        "title": "Container freight and fuel",
        "year": "2025",
        "doi": "10.1/x",
    }


def test_ac3_no_hit_says_so_and_invents_nothing(workspace):
    """AC3. A miss leaves one attempt and a clear note, with no invented source."""
    seq = _plant(workspace)
    search = Search([])
    pack = _pack(seq, _sections("weak"), GENERIC)
    before = [dict(source) for source in pack["sources"]]
    attempt = final_specialist_lookup(seq, pack, search=search)
    assert attempt["attempted"] is True
    assert attempt["found"] is False
    assert len(search.calls) == 1
    assert "one live look-up found none" in attempt["note"]
    assert "No source was invented" in attempt["note"]
    assert pack["sources"] == before


def test_ac4_one_attempt_is_kept_per_pack(workspace):
    """AC4. Showing the same pack again does not search twice."""
    seq = _plant(workspace)
    search = Search([])
    pack = _pack(seq, _sections("weak"), GENERIC)
    state: dict = {}
    first = final_specialist_lookup(seq, pack, identity="digest-1", state=state, search=search)
    second = final_specialist_lookup(seq, pack, identity="digest-1", state=state, search=search)
    assert first["attempted"] is True and second["attempted"] is True
    assert second["reused"] is True
    assert len(search.calls) == 1
    assert second["note"] == first["note"]
    # A different pack digest is a new attempt.
    final_specialist_lookup(seq, pack, identity="digest-2", state=state, search=search)
    assert len(search.calls) == 2


def test_ac5_the_look_up_runs_only_at_the_final_write(workspace):
    """AC5. The look-up sits at the final Word write, after the reviewer gate."""
    source = (REPO / "src" / "essay_writer" / "word.py").read_text(encoding="utf-8")
    assert "final_specialist_lookup" in source
    final_block = source.index('if stage == "9":\n        # Final Word only')
    write_block = source.index("write_docx(essay_id, pack, report, target)")
    assert final_block < write_block
    assert specialist_lookup_query(MODULE + "-1", ["Statista"]).startswith("Statista")
