"""A short draft says it is short. Stable ids: AC1–AC3.

When the gathered files cannot fill the word band without repeating a claim,
the stretch stops and the pack is marked short. The Word path then says the
draft is short and asks for another source. Nothing is invented, and no claim
is repeated to reach the band.
"""

from pathlib import Path

from helpers import open_sequence, write_upload

from essay_writer.paths import essay_dir
from essay_writer.specialists.writer import recover_short_word_band
from essay_writer.word import essay_pack_render_word

MODULE = "MOD1012AA"
SENTENCE = (
    "The corridor carries a large share of crude flows, and the study measures "
    "one year of tanker movements."
)
GATHERED = f"{SENTENCE}\n"


def _brief(words: str) -> None:
    folder = essay_dir(MODULE)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(
        "Genre: essay\n"
        "Question: How do chokepoints constrain the corridor?\n"
        f"Word count: {words}.\n",
        encoding="utf-8",
    )


def _pack(seq: str, body: str) -> dict:
    return {
        "essay_id": seq,
        "title": "Corridor risk",
        "referencing": "harvard",
        "assessment": "Individual essay",
        "genre": "essay",
        "conclusion": "open",
        "sections": [
            {"heading": "Introduction", "body": "This essay asks how far the corridor constrains trade."},
            {"heading": "Analysis", "body": body},
            {"heading": "Conclusion", "body": "The essay treats the corridor as a constraint on trade."},
        ],
        "sources": [
            {
                "id": "src-1",
                "origin": "upload",
                "locator": f"uploads/{MODULE}/abstract.md",
                "quote": SENTENCE,
            }
        ],
    }


def _ready(workspace: Path, words: str) -> tuple[str, str]:
    _brief(words)
    write_upload(workspace, essay_id=MODULE, name="abstract.md", text=GATHERED)
    return open_sequence(MODULE), "\n".join([SENTENCE] * 12)


def test_ac1_a_band_that_cannot_be_filled_is_marked_short(workspace):
    """AC1. The stretch marks the pack short instead of inventing filler."""
    seq, body = _ready(workspace, "2,000 words (1,800 to 2,200)")
    recovered = recover_short_word_band(seq, _pack(seq, body))
    assert recovered["word_band_shortfall"]["low"] == 1800
    assert recovered["word_band_shortfall"]["counted"] < 1800
    text = "\n".join(section["body"] for section in recovered["sections"])
    assert text.count(SENTENCE) == 12


def test_ac2_the_word_path_says_short_and_asks_for_a_source(workspace):
    """AC2. The blocker names the gap and the next step, and asks for no filler."""
    seq, body = _ready(workspace, "2,000 words (1,800 to 2,200)")
    preview = essay_pack_render_word(seq, _pack(seq, body), "draft")
    assert preview["ok"] is True, preview
    reasons = [item["reason"] for item in preview["blockers"] if item["code"] == "word-count"]
    assert reasons
    reason = reasons[0]
    assert reason.startswith("The draft is short:")
    assert "Ask the student for another source." in reason
    assert "word_count_acknowledged" not in reason


def test_ac3_a_draft_inside_the_band_is_not_marked_short(workspace):
    """AC3. A draft already inside the band is left alone and carries no marker."""
    seq, body = _ready(workspace, "240 words (216 to 264)")
    recovered = recover_short_word_band(seq, _pack(seq, body))
    assert "word_band_shortfall" not in recovered
    assert recovered["sections"][1]["body"] == _pack(seq, body)["sections"][1]["body"]
