"""The shared sentence splitter: one segmentation for every gate and check.

Golden: gates, brief_checks, cite_fit, and stage7 all call the same
textutil.sentences. The paragraph below has quoted full stops, abbreviations,
a decimal, and short sentences; every module must segment it the same way.
"""

from __future__ import annotations

from essay_writer import brief_checks, cite_fit, gates, stage7, textutil

TRICKY = (
    'Dr. Chen writes, "The port is narrow." That claim is short. '
    "It relies on Smith et al. (2020), e.g. county records. "
    "The port handles 3.5 million tonnes a year. "
    'He said, "stop." Then he left.'
)
GOLDEN = [
    'Dr. Chen writes, "The port is narrow."',
    "That claim is short.",
    "It relies on Smith et al. (2020), e.g. county records.",
    "The port handles 3.5 million tonnes a year.",
    'He said, "stop."',
    "Then he left.",
]


def test_all_four_modules_segment_the_tricky_paragraph_identically():
    for module in (gates, brief_checks, cite_fit, stage7):
        assert module.sentences is textutil.sentences, module.__name__
        assert module.sentences(TRICKY) == GOLDEN, module.__name__


def test_short_sentences_are_kept():
    assert textutil.sentences("One line. Two words. Three.") == [
        "One line.",
        "Two words.",
        "Three.",
    ]


def test_a_quoted_full_stop_stays_with_the_quotation():
    text = 'She wrote, "The port is narrow." The next sentence follows.'
    assert textutil.sentences(text) == [
        'She wrote, "The port is narrow."',
        "The next sentence follows.",
    ]


def test_a_quoted_full_stop_with_a_continuation_does_not_cut_the_sentence():
    text = 'He said "hello." quietly and then left.'
    assert textutil.sentences(text) == [text]


def test_a_full_stop_inside_a_quotation_is_not_a_boundary():
    text = 'A line says "stop. now" and continues to the end.'
    assert textutil.sentences(text) == [text]


def test_abbreviations_do_not_split_a_sentence():
    text = "The study by Smith et al. (2020), e.g. the county report, used a 3.5 percent band."
    assert textutil.sentences(text) == [text]


def test_unbalanced_quotes_still_split_on_outside_full_stops():
    text = 'uncited "unbalanced quote. The next sentence is here.'
    assert textutil.sentences(text) == [
        'uncited "unbalanced quote.',
        "The next sentence is here.",
    ]


def test_blank_and_non_string_input_is_no_sentences():
    assert textutil.sentences("") == []
    assert textutil.sentences("   ") == []
    assert textutil.sentences(None) == []  # type: ignore[arg-type]


def test_the_gates_now_see_a_short_sentence():
    """Regression: the old gates splitter silently dropped sentences under eight words."""
    short = "The port is narrow."
    assert len(short.split()) < 8
    assert gates.unquoted_exact(short, [short]) == [short]
    quoted = 'A gathered line says "The port is narrow." and stops.'
    assert gates.unquoted_exact(quoted, [short]) == []


def test_stage7_keeps_its_claim_filter_over_the_shared_splitter():
    before = "GHG means greenhouse gases. The port is narrow."
    after = "GHG means greenhouse gas. The port is wide."
    changed = stage7.claim_delta(before, after)
    assert changed == ["The port is narrow.", "The port is wide."]
