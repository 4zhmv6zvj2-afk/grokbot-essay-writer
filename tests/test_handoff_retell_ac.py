"""A stage 5 section that lightly rewrites a 4b note stays refused. Stable ids: AC1–AC3.

The retell check reads the section and the note as content words. An exact copy,
a long run of the note, and a light rewrite that keeps most of the note's
five-word runs are all a retell. A short quotation inside an argument, and a
developed argument, are not.
"""

from essay_writer.draft_from_review import (
    _copy_overlap,
    _retells_one_paper,
    argument_blockers,
)

NOTE = (
    "This paper examines how the Strait of Hormuz carries a large share of world "
    "crude flows. The authors judge the aim, the method, and the single-corridor "
    "limit of the model. The study finds that a short closure would raise freight "
    "costs, but the authors do not measure fuel prices or insurance spreads. The "
    "review notes that the evidence is drawn from one year of tanker movements and "
    "that the conclusions are stated more widely than that sample supports."
)
# A light rewrite: same order, same claims, a few words swapped for plainer ones.
LIGHT = (
    "This paper looks at how the Strait of Hormuz carries a large share of world "
    "crude flows. The authors judge the aim, the method, and the single-corridor "
    "limit of the model. The study finds that a short closure would raise freight "
    "costs, but the authors do not measure fuel prices or insurance spreads. The "
    "review notes that the evidence comes from one year of tanker movements and "
    "that the conclusions are stated more widely than that sample supports."
)
SHORT_QUOTE = "The Strait of Hormuz carries a large share of world crude flows."
ARGUMENT = (
    "The corridor matters because closure risk is priced through freight and "
    "insurance rather than through the barrel itself. Smith's account of the "
    f"single-corridor model is useful here: \"{SHORT_QUOTE}\" That estimate is "
    "narrow, and it says nothing about how importers would re-route. A second "
    "reading is needed before the essay can claim a fuel-price effect, because "
    "the model holds routes fixed and samples one year of movements. The essay "
    "therefore treats the finding as a bound on disruption, not as a forecast."
)


def test_ac1_a_light_rewrite_is_still_a_retell():
    """AC1. Swapping a few words does not turn a note copy into an argument."""
    by_paper = {"src-1": NOTE}
    assert _retells_one_paper(NOTE, by_paper) == "src-1"
    assert _retells_one_paper(LIGHT, by_paper) == "src-1"
    assert _copy_overlap(LIGHT, NOTE) >= 0.5


def test_ac2_a_short_quote_inside_an_argument_is_not_a_retell():
    """AC2. A quotation used as evidence stays evidence."""
    by_paper = {"src-1": NOTE}
    assert _retells_one_paper(ARGUMENT, by_paper) is None
    assert _copy_overlap(ARGUMENT, NOTE) < 0.5


def test_ac3_the_stage_five_refusal_names_the_paper():
    """AC3. The refusal still comes from the stage 5 argument check."""
    sections = [{"heading": "Analysis", "body": LIGHT}]
    reviews = [{"paper_id": "src-1", "markdown": NOTE}]
    issues = argument_blockers("MOD1004AA-1", sections, reviews)
    assert issues
    assert issues[0]["code"] == "argument"
    assert "src-1" in issues[0]["reason"]
    clean = argument_blockers("MOD1004AA-1", [{"heading": "Analysis", "body": ARGUMENT}], reviews)
    assert clean == []
