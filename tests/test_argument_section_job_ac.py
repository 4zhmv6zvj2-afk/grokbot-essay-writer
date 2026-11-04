"""Section job when the short-draft stretch appends. Stable ids: AC1–AC3.

The stretch adds a gathered claim sentence to one body section. It must not
land in Methodology or Recommendations, whose job is not to carry an added
claim. Leaving the draft short is the honest outcome. Intro and conclusion
are skipped as before.
"""

from pathlib import Path

from essay_writer.specialists.writer import _append_target

ESSAY = [
    {"heading": "Introduction", "body": "One."},
    {"heading": "Africa in Roman writing", "body": "Two."},
    {"heading": "Conclusion", "body": "Three."},
]
REPORT_WITH_FINDINGS = [
    {"heading": "1. Introduction", "body": "One."},
    {"heading": "2. Methodology", "body": "Two."},
    {"heading": "3. Findings", "body": "Three."},
    {"heading": "4. Recommendations", "body": "Four."},
    {"heading": "5. Conclusion", "body": "Five."},
]
FIXED_ONLY = [
    {"heading": "Introduction", "body": "One."},
    {"heading": "Method", "body": "Two."},
    {"heading": "Recommendations", "body": "Three."},
    {"heading": "Conclusion", "body": "Four."},
]
INTRO_ONLY = [
    {"heading": "Introduction", "body": "One."},
    {"heading": "Conclusion", "body": "Two."},
]


def test_ac1_an_essay_body_section_still_takes_the_sentence():
    """AC1. The ordinary essay body target is unchanged."""
    assert _append_target(ESSAY) == 1


def test_ac2_a_report_appends_to_the_findings_not_the_method():
    """AC2. Numbered headings are read by job, so findings win over methodology."""
    assert _append_target(REPORT_WITH_FINDINGS) == 2


def test_ac3_a_pack_with_only_fixed_job_sections_is_left_alone():
    """AC3. No eligible section means no append, and the intro is not a back door."""
    assert _append_target(FIXED_ONLY) is None
    assert _append_target(INTRO_ONLY) == 0
    assert _append_target([]) is None
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "essay_writer"
        / "specialists"
        / "writer.py"
    ).read_text(encoding="utf-8")
    for heading in ("methodology", "methods", "recommendations", "executive summary"):
        assert f'"{heading}"' in source


METHODOLOGICAL = [
    {"heading": "Introduction", "body": "One."},
    {"heading": "Methodological analysis of trade", "body": "Two."},
    {"heading": "Conclusion", "body": "Three."},
]
METHODS_AND_DATA = [
    {"heading": "Introduction", "body": "One."},
    {"heading": "Methods and data", "body": "Two."},
    {"heading": "Executive summary", "body": "Three."},
    {"heading": "Conclusion", "body": "Four."},
]


def test_ac4_a_methodological_analysis_takes_the_claim():
    """AC4. An analysis heading is not a methods section, and real fixed jobs still skip."""
    assert _append_target(METHODOLOGICAL) == 1
    assert _append_target(METHODS_AND_DATA) is None
    assert _append_target([{"heading": "Methodology", "body": "x"}]) is None
    assert _append_target([{"heading": "Recommendations", "body": "x"}]) is None
