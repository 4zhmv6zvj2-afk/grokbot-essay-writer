"""Source identity in the short-draft stretch. Stable ids: AC1–AC3.

A reworded gathered sentence keeps the noun its source used for itself
(article, paper, study) or a neutral text. The stretch does not promote a
brief into a study, and it does not carry process words into the essay.
Per-source author and year attribution stays a separate product call.
"""

from pathlib import Path

from essay_writer.specialists.writer import _rewrite_supported

CASES = (
    ("This article presents the author's development of a module.", "The article"),
    ("This paper argues that the policy failed.", "The paper"),
    ("This study compares two cohorts.", "The study"),
    ("It argues that the effect is small.", "The text"),
)
IDENTITY = ("article", "paper", "study", "account", "author", "journal", "report")
SOURCE_NOUNS = ("article", "paper", "study", "account", "text")


def test_ac1_a_source_keeps_the_noun_it_used_for_itself():
    """AC1. Each reword keeps the source's own noun and adds no process word."""
    for sentence, noun in CASES:
        word = noun.split()[-1].casefold()
        for variant in range(12):
            line = _rewrite_supported(sentence, variant)
            folded = line.casefold()
            assert word in folded, (sentence, variant, line)
            for other in SOURCE_NOUNS:
                if other != word:
                    assert other not in folded, (sentence, variant, line)
            assert "gathered" not in folded, (sentence, variant, line)


def test_ac2_the_fallback_lead_in_names_no_source_type():
    """AC2. A sentence with no self-reference gets a neutral lead-in, not a study."""
    line = _rewrite_supported("Demand rose sharply in 2019.", 0)
    assert line == "The text notes that demand rose sharply in 2019."
    lead_in = line.split("demand")[0].casefold()
    for noun in IDENTITY:
        assert noun not in lead_in, (noun, lead_in)
    for word in ("gathered", "source", "file", "record"):
        assert word not in lead_in, (word, lead_in)


def test_ac3_the_stretch_names_no_source_type_it_cannot_see():
    """AC3. The module's rewrite table holds no identity claim of its own."""
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "essay_writer"
        / "specialists"
        / "writer.py"
    ).read_text(encoding="utf-8")
    assert "gathered study" not in source.casefold()
    assert "gathered account" not in source.casefold()
    assert "The gathered record" not in source
