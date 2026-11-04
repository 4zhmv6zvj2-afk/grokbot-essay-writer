"""A stretch append carries the source's author and year, or does not append.

Stable ids: AC1–AC3. The stretch adds a gathered claim to the essay body. When
the source has a stored author and year, the appended sentence carries that
in-text citation. When it does not, the sentence is not appended at all and the
draft is marked short. Nothing is invented.
"""

from helpers import open_sequence, plant_gathered_source, write_upload

from essay_writer.gates import unquoted_exact
from essay_writer.paths import essay_dir
from essay_writer.specialists.writer import recover_short_word_band

MODULE = "MOD1013AA"
OTHER = "MOD1014AA"
S1 = (
    "This article presents the corridor as a single point of failure, and it "
    "argues that a short closure raises freight costs."
)
S2 = (
    "It argues that the study measures one year of tanker movements, as well as "
    "insurance spreads, and that the sample is narrow."
)
BODY = (
    "The corridor report treats the strait as a single point of failure and "
    "weighs a short closure against freight costs."
)
GATHERED = f"Smith, J. (2020). Chokepoints and crude.\n{S1} {S2}\n"


def _brief(module: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: essay\n"
        "Question: How do chokepoints constrain the corridor?\n"
        "Word count: 600 words (540 to 660).\n",
        encoding="utf-8",
    )


def _pack(seq: str, module: str, *, authored: bool) -> dict:
    source = {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{module}/smith.md",
        "quote": S1,
    }
    if authored:
        source["author"] = "Smith, J."
        source["year"] = "2020"
    return {
        "essay_id": seq,
        "title": "Corridor risk",
        "referencing": "harvard",
        "assessment": "Individual essay",
        "genre": "essay",
        "conclusion": "open",
        "sections": [
            {"heading": "Introduction", "body": "This essay asks how far the corridor constrains trade."},
            {"heading": "Analysis", "body": " ".join([BODY] * 20)},
            {"heading": "Conclusion", "body": "The essay treats the corridor as a constraint on trade."},
        ],
        "sources": [source],
    }


def test_ac1_an_appended_claim_carries_the_author_and_year(workspace):
    """AC1. Every appended sentence ends with the stored in-text citation."""
    _brief(MODULE)
    seq = open_sequence(MODULE)
    plant_gathered_source(seq)
    write_upload(workspace, essay_id=MODULE, name="smith.md", text=GATHERED)
    pack = _pack(seq, MODULE, authored=True)
    recovered = recover_short_word_band(seq, pack)
    body = recovered["sections"][1]["body"]
    assert body != pack["sections"][1]["body"]
    added = body[len(pack["sections"][1]["body"]) :].strip()
    assert added
    for sentence in added.split("."):
        text = sentence.strip()
        if text:
            assert text.endswith("(Smith, 2020)"), text
    assert "(Smith, 2020)" in added
    assert unquoted_exact(body, [GATHERED]) == []


def test_ac2_no_author_year_means_no_append(workspace):
    """AC2. Without a stored author and year the sentence is not appended."""
    _brief(OTHER)
    write_upload(workspace, essay_id=OTHER, name="smith.md", text=GATHERED)
    seq = open_sequence(OTHER)
    pack = _pack(seq, OTHER, authored=False)
    recovered = recover_short_word_band(seq, pack)
    assert recovered["sections"][1]["body"] == pack["sections"][1]["body"]
    assert recovered["word_band_shortfall"]["low"] == 540


def test_ac3_no_citation_is_invented(workspace):
    """AC3. A missing author or year leaves no empty or partial citation."""
    _brief(OTHER)
    write_upload(workspace, essay_id=OTHER, name="smith.md", text=GATHERED)
    seq = open_sequence(OTHER)
    pack = _pack(seq, OTHER, authored=False)
    recovered = recover_short_word_band(seq, pack)
    text = "\n".join(section["body"] for section in recovered["sections"])
    for invented in ("()", "(, )", "(, 2020)", "(Smith, )", "(Smith, 2020)"):
        assert invented not in text
