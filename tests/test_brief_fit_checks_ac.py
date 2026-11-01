"""Brief-fit checks before Word. Stable ids: AC1–AC3.

A section budget is a section length the brief prints. The match between that
listed section and the draft heading tolerates a section number and closing
punctuation, and nothing else. A section that is really absent still reports
as missing.
"""

from pathlib import Path

from helpers import ESSAY

from essay_writer.brief_checks import (
    before_word,
    section_budgets,
    stated_word_totals,
    word_total_clash,
)

BRIEF = (
    "Genre: report\n"
    "Section budgets: Introduction 400, Analysis 400, Conclusion 200\n"
)


def _plant(workspace: Path, text: str = BRIEF) -> None:
    folder = workspace / "Essay-writer" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _section(heading: str, words: int) -> dict[str, str]:
    return {"heading": heading, "body": "word " * words}


def _view(sections: list[dict[str, str]]) -> dict:
    return before_word(
        ESSAY,
        sections,
        acknowledged_sections=False,
        acknowledged_contradiction=False,
        acknowledged_simulation=False,
        exclude_citations=False,
    )


def _codes(items: list[dict]) -> list[str]:
    return [str(item.get("code")) for item in items]


def test_ac1_a_numbered_heading_matches_its_listed_budget(workspace):
    """AC1. '1. Introduction' is the Introduction the brief budgets."""
    _plant(workspace)
    sections = [
        _section("1. Introduction", 400),
        _section("2. Analysis", 400),
        _section("3. Conclusion", 200),
    ]
    view = _view(sections)
    assert [row["missing"] for row in view["section_budgets"]] == [False, False, False]
    assert [row["inside"] for row in view["section_budgets"]] == [True, True, True]
    assert "section-budget" not in _codes(view["blockers"])


def test_ac2_closing_punctuation_does_not_hide_a_section(workspace):
    """AC2. A trailing colon or full stop on the heading is still that section."""
    _plant(workspace)
    sections = [
        _section("Introduction:", 400),
        _section("Analysis.", 400),
        _section("Conclusion", 200),
    ]
    view = _view(sections)
    assert [row["missing"] for row in view["section_budgets"]] == [False, False, False]
    assert "section-budget" not in _codes(view["blockers"])


def test_ac3_a_section_that_is_really_absent_still_reports(workspace):
    """AC3. Tolerance does not invent a section the draft does not have."""
    _plant(workspace)
    view = _view([_section("1. Introduction", 400), _section("2. Analysis", 400)])
    assert "section-budget" in _codes(view["blockers"])
    missing = [row["heading"] for row in view["section_budgets"] if row["missing"]]
    assert missing == ["Conclusion"]


def test_ac4_a_section_name_with_and_is_one_listed_name(workspace):
    """AC4. 'Analysis and findings 400' is one section, not a budget for 'findings'."""
    _plant(
        workspace,
        "Genre: report\n"
        "Section budgets: Introduction 400, Analysis and findings 400, Conclusion 200\n",
    )
    sections = [
        _section("1. Introduction", 400),
        _section("2. Analysis and findings", 400),
        _section("3. Conclusion", 200),
    ]
    view = _view(sections)
    assert [row["heading"] for row in view["section_budgets"]] == [
        "Introduction",
        "Analysis and findings",
        "Conclusion",
    ]
    assert [row["missing"] for row in view["section_budgets"]] == [False, False, False]
    assert "section-budget" not in _codes(view["blockers"])


def test_ac5_two_counts_in_one_phrase_are_two_sections():
    """AC5. A phrase without commas still lists two sections and two budgets."""
    rows = section_budgets("Section budgets: Introduction 300 words and Conclusion 200 words")
    assert [row["heading"] for row in rows] == ["Introduction", "Conclusion"]
    assert [row["words"] for row in rows] == [300, 200]


def test_ac6_a_thousands_separator_and_a_range_are_read_honestly():
    """AC6. A comma inside a number stays inside it, and a range is not one budget."""
    many = section_budgets(
        "Word budgets: Introduction 400; Analysis and findings 1,200; Conclusion 200"
    )
    assert [row["words"] for row in many] == [400, 1200, 200]
    ranged = section_budgets("Section budgets: Introduction 400-500 words, Conclusion 200 words")
    assert [row["heading"] for row in ranged] == ["Conclusion"]


CLASH_BRIEF = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Word count: 2,000 words.\n"
    "The rubric expects 1,800 words.\n"
)
ONE_TOTAL = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Word count: 2,000 words, excluding references.\n"
)


def test_ac7_two_stated_totals_are_named_and_not_chosen(workspace):
    """AC7. Two whole-piece totals are a notice, not a silent pick and not a block."""
    _plant(workspace, CLASH_BRIEF)
    view = _view([_section("1. Introduction", 400)])
    notes = [item for item in view["notes"] if item.get("code") == "brief-word-clash"]
    assert len(notes) == 1
    assert "2,000 and 1,800" in str(notes[0]["reason"])
    assert "brief-word-clash" not in _codes(view["blockers"])


def test_ac8_one_total_and_a_per_entry_length_are_not_a_clash(workspace):
    """AC8. A per-entry or per-section length is not a second total."""
    _plant(workspace, ONE_TOTAL + "Each entry is about 500 words.\n")
    view = _view([_section("1. Introduction", 400)])
    assert "brief-word-clash" not in _codes(view["notes"])
    assert stated_word_totals(ONE_TOTAL + "Each entry is about 500 words.\n") == [2000]


def test_ac9_a_printed_range_is_not_a_clash(workspace):
    """AC9. A range next to the total is the band, not a second total."""
    brief = "Genre: report\nThe essay is 2,000 words (1,800 to 2,200).\n"
    _plant(workspace, brief)
    view = _view([_section("1. Introduction", 400)])
    assert "brief-word-clash" not in _codes(view["notes"])
    assert stated_word_totals(brief) == [2000]


SCHEME_BUDGETS = "Section budgets: Introduction 400, Analysis 400, Conclusion 200\n"
BARE_BRIEF = "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"


def test_ac10_a_budget_in_the_mark_scheme_file_is_read(workspace):
    """AC10. A section budget printed on the mark scheme counts like one in the brief."""
    _plant(workspace, BARE_BRIEF)
    folder = workspace / "Essay-writer" / ESSAY
    (folder / "mark-scheme.md").write_text(SCHEME_BUDGETS, encoding="utf-8")
    view = _view([_section("1. Introduction", 400), _section("2. Analysis", 400)])
    assert [row["heading"] for row in view["section_budgets"]] == [
        "Introduction",
        "Analysis",
        "Conclusion",
    ]
    assert "section-budget" in _codes(view["blockers"])


PARTS_BRIEF = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Word count: 2,000 words.\n"
    "Abstract: 150 words.\n"
    "References: 500 words.\n"
    "Bibliography 300 words.\n"
)


def test_ac11_a_part_word_count_is_not_a_whole_piece_total(workspace):
    """AC11. Abstract, references, and bibliography lengths do not make a clash."""
    _plant(workspace, PARTS_BRIEF)
    view = _view([_section("1. Introduction", 400)])
    assert "brief-word-clash" not in _codes(view["notes"])
    assert stated_word_totals(PARTS_BRIEF) == [2000]


def test_ac12_a_real_second_total_is_still_caught_beside_part_lines(workspace):
    """AC12. The polish does not hide a second whole-piece total."""
    brief = PARTS_BRIEF + "The rubric expects 1,800 words.\n"
    _plant(workspace, brief)
    view = _view([_section("1. Introduction", 400)])
    notes = [item for item in view["notes"] if item.get("code") == "brief-word-clash"]
    assert len(notes) == 1
    assert "2,000 and 1,800" in str(notes[0]["reason"])
    assert "brief-word-clash" not in _codes(view["blockers"])
    assert stated_word_totals(brief) == [2000, 1800]


PROSE_PARTS = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Word count: 2,000 words.\n"
    "The abstract is limited to 150 words.\n"
    "References should be about 500 words.\n"
    "The bibliography is capped at 300 words.\n"
    "Executive summary is limited to 200 words.\n"
)


def test_ac13_a_sentence_part_limit_is_not_a_whole_piece_total(workspace):
    """AC13. "The abstract is limited to 150 words" is the part, not the total."""
    _plant(workspace, PROSE_PARTS)
    view = _view([_section("1. Introduction", 400)])
    assert "brief-word-clash" not in _codes(view["notes"])
    assert stated_word_totals(PROSE_PARTS) == [2000]


def test_ac14_a_real_second_total_still_notices_beside_prose_limits(workspace):
    """AC14. The prose polish does not hide a second whole-piece total."""
    brief = PROSE_PARTS + "The rubric expects 1,800 words.\n"
    _plant(workspace, brief)
    view = _view([_section("1. Introduction", 400)])
    notes = [item for item in view["notes"] if item.get("code") == "brief-word-clash"]
    assert len(notes) == 1
    assert "2,000 and 1,800" in str(notes[0]["reason"])
    assert "brief-word-clash" not in _codes(view["blockers"])
    assert stated_word_totals(brief) == [2000, 1800]


def test_ac15_a_total_that_counts_the_part_still_counts():
    """AC15. A sentence about the whole piece, mentioning a part, keeps its total."""
    for sentence in (
        "Word count: 2,000 words, including references.",
        "The total, including references, is 2,000 words.",
        "The references are not counted in the 2,000 words.",
    ):
        assert stated_word_totals(sentence) == [2000], sentence
        assert word_total_clash(sentence + "\nThe tutor may allow 2,200 words.\n")


REF_LIST = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Word count: 2,000 words.\n"
    "Reference list should be about 500 words.\n"
    "The reference list is limited to 600 words.\n"
)


def test_ac16_reference_list_is_the_two_word_subject(workspace):
    """AC16. "Reference list" is read before bare "references", so its count is the part's."""
    _plant(workspace, REF_LIST)
    view = _view([_section("1. Introduction", 400)])
    assert "brief-word-clash" not in _codes(view["notes"])
    assert stated_word_totals(REF_LIST) == [2000]
    labeled = "Word count: 2,000 words.\nReference list: 500 words.\n"
    assert stated_word_totals(labeled) == [2000]
    inclusive = "The total, including references, is 2,000 words.\n"
    assert stated_word_totals(inclusive) == [2000]


def test_ac17_a_real_second_total_still_notices_beside_the_reference_list(workspace):
    """AC17. The two-word subject does not hide a second whole-piece total."""
    brief = REF_LIST + "The rubric expects 1,800 words.\n"
    _plant(workspace, brief)
    view = _view([_section("1. Introduction", 400)])
    notes = [item for item in view["notes"] if item.get("code") == "brief-word-clash"]
    assert len(notes) == 1
    assert "2,000 and 1,800" in str(notes[0]["reason"])
    assert "brief-word-clash" not in _codes(view["blockers"])
    assert stated_word_totals(brief) == [2000, 1800]


LEFT_EXPRESSIONS = (
    "A list of references should be about 500 words.",
    "List of references is limited to 500 words.",
    "Lists of references should be about 500 words.",
    "Reference lists should be about 500 words.",
    "References list is limited to 500 words.",
)
LEFT_LABELS = ("Reference lists: 500 words.", "List of references: 500 words.")


def test_ac18_reference_list_leftovers_are_the_part(workspace):
    """AC18. "list of references" and plural or reversed lists are the part's own length."""
    for sentence in LEFT_EXPRESSIONS:
        brief = f"Genre: report\nWord count: 2,000 words.\n{sentence}\n"
        _plant(workspace, brief)
        view = _view([_section("1. Introduction", 400)])
        assert "brief-word-clash" not in _codes(view["notes"]), sentence
        assert stated_word_totals(brief) == [2000], sentence
    for sentence in LEFT_LABELS:
        brief = f"Genre: report\nWord count: 2,000 words.\n{sentence}\n"
        assert stated_word_totals(brief) == [2000], sentence


def test_ac19_inclusive_totals_and_a_real_second_total_still_work(workspace):
    """AC19. Inclusive and exclusion totals still count, and a second total still notices."""
    for sentence in (
        "The total, including references, is 2,000 words.",
        "Including the reference list, the total is 2,000 words.",
        "The paper is 3,000 words excluding references.",
    ):
        assert stated_word_totals(sentence) != [], sentence
    assert stated_word_totals("The paper is 3,000 words excluding references.") == [3000]
    # Parked on purpose: this one still counts, as it did before the polish.
    assert stated_word_totals(
        "The references including footnotes are 500 words.\nWord count: 2,000 words.\n"
    ) == [500, 2000]

    brief = (
        "Genre: report\nWord count: 2,000 words.\n"
        "Reference lists should be about 500 words.\n"
        "The rubric expects 1,800 words.\n"
    )
    _plant(workspace, brief)
    view = _view([_section("1. Introduction", 400)])
    notes = [item for item in view["notes"] if item.get("code") == "brief-word-clash"]
    assert len(notes) == 1
    assert "2,000 and 1,800" in str(notes[0]["reason"])
    assert "brief-word-clash" not in _codes(view["blockers"])
