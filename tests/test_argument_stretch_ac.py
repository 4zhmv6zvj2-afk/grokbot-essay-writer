"""Claim force in the short-draft stretch. Stable ids: AC1–AC3.

Word calls recover_short_word_band before it inspects the draft, so a reworded
gathered sentence lands in the essay body. A reword keeps what that sentence
claims: the same modal, the same negation, and no added proof or need. Prompt
text is not involved, and no pass/fail gate is added.
"""

import re
from pathlib import Path

from essay_writer.specialists.writer import _REWRITE, _rewrite_supported

REPO = Path(__file__).resolve().parents[1]
MODALS = ("can", "cannot", "could", "may", "might", "must", "ought", "should", "would")
STRENGTH = (
    "prove",
    "proves",
    "proved",
    "definitely",
    "certainly",
    "undoubtedly",
    "always",
    "never",
)
PROBES = (
    "The intervention can be pernicious in its effects.",
    "The practice cannot be limited to one module.",
    "The programme should involve serious engagement.",
    "A second reading might explain the gap.",
    "It may prove difficult to separate the two claims.",
    "The report does not support a single cause.",
)


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z'-]+", text.casefold())


def _modals(text: str) -> list[str]:
    return [word for word in _words(text) if word in MODALS]


def _strength(text: str) -> list[str]:
    return [word for word in _words(text) if word in STRENGTH]


def test_ac1_a_reword_keeps_the_same_modal():
    """AC1. Every variant keeps the modal words of the sentence it rewords."""
    for sentence in PROBES:
        before = _modals(sentence)
        for variant in range(12):
            line = _rewrite_supported(sentence, variant)
            assert _modals(line) == before, (sentence, variant, line)


def test_ac2_a_reword_adds_no_proof_and_drops_no_negation():
    """AC2. No variant adds a strength word, and a negation survives."""
    for sentence in PROBES:
        before_strength = _strength(sentence)
        before_not = _words(sentence).count("not")
        for variant in range(12):
            line = _rewrite_supported(sentence, variant)
            added = [word for word in _strength(line) if word not in before_strength]
            assert added == [], (sentence, variant, line)
            assert _words(line).count("not") >= before_not, (sentence, variant, line)


def test_ac3_the_table_holds_no_modal_or_strength_swap():
    """AC3. The rewrite table never targets a modal, a negation, or a strength word."""
    drift = {"may prove", "is not", "needs"}
    swap = re.compile(
        r"\b(?:" + "|".join(MODALS + STRENGTH) + r"|not|needs)\b",
        re.IGNORECASE,
    )
    for pattern, replacement in _REWRITE:
        assert replacement not in drift, pattern.pattern
        assert swap.search(pattern.pattern) is None, pattern.pattern
        assert swap.search(replacement) is None, replacement
    source = (REPO / "src" / "essay_writer" / "specialists" / "writer.py").read_text(
        encoding="utf-8"
    )
    for gone in ('"may prove"', '"is not"', '"needs"'):
        assert gone not in source
