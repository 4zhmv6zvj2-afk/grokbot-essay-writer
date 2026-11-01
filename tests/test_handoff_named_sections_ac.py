"""Brief-named report sections are the report headings. Stable ids: AC1–AC3.

A report brief or mark scheme that lists its sections is read as those section
names, so the draft carries them. A diary keeps its entry names, an essay keeps
none, and a workshop list is not a section list. Nothing is invented.
"""

from pathlib import Path

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import named_heading_issues, stage_contract_refusal
from essay_writer.paths import essay_dir

REPORT = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Sections:\n"
    "- Purpose\n"
    "- Findings\n"
    "- Discussion\n"
    "- Conclusion\n"
)
SCHEME_ONLY = "Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"
SCHEME = "Sections:\n- Purpose\n- Findings\n- Discussion\n"
WORKSHOPS = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Workshop topics\n"
    "1. Quay watch\n"
    "2. Tide log\n"
)
DIARY = (
    "Genre: reflective diary\n"
    "Question: Reflect on the decisions in the watch.\n"
    "Entries:\n"
    "- Quay watch\n"
    "- Tide log\n"
)
ESSAY = (
    "Genre: essay\n"
    "Question: Should the council publish the figure?\n"
    "Sections:\n"
    "- Purpose\n"
    "- Findings\n"
)


def _plant(workspace: Path, module: str, brief: str, scheme: str = "") -> str:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    if scheme:
        (folder / "mark-scheme.md").write_text(scheme, encoding="utf-8")
    return f"{module}-1"


def test_ac1_a_report_carries_the_sections_the_brief_names(workspace):
    """AC1. Listed report sections are the headings; a different heading is refused."""
    seq = _plant(workspace, "REP9101AA", REPORT)
    names = ["Purpose", "Findings", "Discussion", "Conclusion"]
    record = read_assignment(seq)
    assert record["named_entries"] == names
    assert record["named_parts_source"] == "report"
    assert named_heading_issues(seq, names) == []
    issues = named_heading_issues(seq, ["Introduction", "Findings", "Discussion", "Conclusion"])
    assert issues and "Purpose" in issues[0]
    assert stage_contract_refusal(seq, "3", "A plan with no section names.")["refused"] == (
        "named-parts"
    )
    # The purpose-and-scope lock is not refused on section names.
    assert stage_contract_refusal(seq, "2", "Purpose and scope are fixed.") is None


def test_ac2_a_mark_scheme_list_counts_and_a_workshop_list_does_not(workspace):
    """AC2. The scheme lists sections; a workshop list is not a section list."""
    seq = _plant(workspace, "REP9102AA", SCHEME_ONLY, SCHEME)
    record = read_assignment(seq)
    assert record["named_entries"] == ["Purpose", "Findings", "Discussion"]
    assert named_heading_issues(seq, ["Purpose", "Findings", "Discussion"]) == []

    other = _plant(workspace, "REP9103AA", WORKSHOPS)
    assert read_assignment(other)["named_entries"] == []
    assert named_heading_issues(other, ["Purpose", "Findings", "Discussion"]) == []


def test_ac3_diary_entries_and_essay_lists_stay_where_they_are(workspace):
    """AC3. A diary keeps entry names; an essay keeps no named parts."""
    diary = _plant(workspace, "DIA9104AA", DIARY)
    record = read_assignment(diary)
    assert record["named_entries"] == ["Quay watch", "Tide log"]
    assert record["named_parts_source"] == "diary"

    essay = _plant(workspace, "ESY9105AA", ESSAY)
    assert read_assignment(essay)["named_entries"] == []
    assert named_heading_issues(essay, ["Purpose", "Findings"]) == []
