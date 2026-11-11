"""One content-word extractor for the assignment gate and the body-cite gate.

The shared function is explicit about order, length, and the caller's stop
words. The title/particle helper in textutil keeps its own meaning.
"""

from __future__ import annotations

from essay_writer import assignment_gate, cite_fit, textutil

SENTENCE = "Privacy risk reduces willingness to disclose personal data."
STOP = frozenset({"privacy", "data"})


def test_ordered_keeps_first_seen_order_and_drops_repeats():
    words = textutil.content_words("Risk risk Risk data privacy", stopwords=STOP, ordered=True)
    assert words == ["risk"]


def test_unordered_keeps_repeats():
    words = textutil.content_words("risk risk risk", stopwords=STOP)
    assert words == ["risk", "risk", "risk"]


def test_short_words_and_numeral_tokens_are_not_content_words():
    assert textutil.content_words("A 2020 risk of data flow") == ["risk", "data", "flow"]


def test_a_hyphenated_compound_is_one_word():
    assert textutil.content_words("cross-border trade") == ["cross-border", "trade"]


def test_the_assignment_gate_reads_its_ask_ordered_and_unique():
    assert assignment_gate.ask_content_words("Privacy risk, risk and data") == [
        "privacy",
        "risk",
        "data",
    ]
    asked = assignment_gate.ask_content_words("What does the privacy risk question ask?")
    assert asked == ["does", "privacy", "risk", "question"]


def test_the_body_cite_gate_uses_the_same_extractor():
    assert cite_fit.content_words is textutil.content_words
    assert assignment_gate.content_words is textutil.content_words
    claim = cite_fit._claim_words(SENTENCE, "")
    assert claim == ["privacy", "risk", "reduces", "willingness", "disclose", "personal", "data"]


def test_the_cite_gate_ignores_the_assignment_topic_words():
    claim = cite_fit._claim_words(SENTENCE, "privacy risk and personal data")
    assert claim == ["reduces", "willingness", "disclose"]


def test_the_name_helper_in_textutil_is_left_alone():
    assert textutil._content_words(["Dr.", "Smith"]) == ["Smith"]
    assert textutil._content_words(["van", "Dijk"]) == ["Dijk"]


def test_the_two_gates_no_longer_own_a_tokenizer():
    assert "_WORD" not in assignment_gate.__dict__
    assert "_WORD" not in cite_fit.__dict__
    assert "_content_words" not in cite_fit.__dict__
