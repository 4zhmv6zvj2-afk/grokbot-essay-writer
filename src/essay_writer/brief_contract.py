"""Brief to assignment record.

One read fills the parts, the title page, and the findings-opening label.
Stage 2, stage 3, stage 5, and Word read that record. A writing type with
no mapping does not use the essay or report contract.

The findings-opening label selects the shared standard sentence.
findings_note_clears and the mid-status basis both read that sentence.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer.assignment_gate import mark_scheme_text
from essay_writer.confirm import refuse
from essay_writer.diary import (
    entry_count,
    layout_spec,
    missing_cover_fields,
    named_entries,
    title_page_spec,
)
from essay_writer.state import load_state, save_state

FINDINGS_HOW_TO_SCORE_HIGH = "how_to_score_high"
FINDINGS_MARK_SCHEME = "mark_scheme"
FINDINGS_NONE = "none"

UNMAPPED_REASON = (
    "This writing type has no brief-to-assignment mapping. "
    "It does not use the essay or report contract."
)
MAPPED_TYPE_OVERLAY = (
    "The assignment record holds the parts, the title page, the page layout, and the lock. "
    "Follow that record. Print a registration number when that record requires it. "
    "Put the page number where that record says."
)
UNNAMED_NOTE = "The brief did not name these parts."

REQUIRED_MAPPING_KEYS = (
    "named_entries",
    "title_page",
    "findings_opening",
    "lock",
)

CONTRACT_STAGES = frozenset({"2", "3", "5"})

_GENERIC_ENTRY = re.compile(r"(?i)\bentry\s+\d+\b")
_GENERIC_HEADING = re.compile(r"(?i)^entry\s+\d+$")

Mapper = Callable[..., dict[str, Any]]
_MAPPERS: dict[str, Mapper] = {}


def writing_type_of(prescribed: str | None) -> str | None:
    """Genre key for the mapping. The reflective-diary format uses diary."""
    if not isinstance(prescribed, str) or not prescribed.strip():
        return None
    if prescribed.strip().casefold() == "reflective diary":
        return "diary"
    return prescribed.strip().casefold()


def has_mapping(writing_type: str | None) -> bool:
    return isinstance(writing_type, str) and writing_type in _MAPPERS


def register_mapping(writing_type: str, mapper: Mapper) -> None:
    """Add a writing type. Essay, report, and diary stay registered here."""
    key = writing_type.strip().casefold()
    if not key or key in {"essay", "report", "diary"}:
        raise ValueError("essay, report, and diary already have mappings")
    _MAPPERS[key] = mapper


def unregister_mapping(writing_type: str) -> None:
    key = writing_type.strip().casefold()
    if key in {"essay", "report", "diary"}:
        return
    _MAPPERS.pop(key, None)


def _title_page(text: str) -> dict[str, Any]:

    return title_page_spec(text)


def _parts(text: str, *, use_list: bool) -> dict[str, Any]:

    names = named_entries(text) if use_list else []
    count = entry_count(text) if use_list else None
    if use_list and not names and count:
        note = UNNAMED_NOTE
    else:
        note = None
    return {
        "named_entries": names,
        "named_by_brief": bool(names),
        "part_count": count,
        "unnamed_note": note,
    }


def _opening(kind: str, *, has_scheme: bool) -> str:
    if not has_scheme:
        return FINDINGS_NONE
    return kind


def _map_essay(text: str, *, has_scheme: bool) -> dict[str, Any]:
    return {
        **_parts(text, use_list=False),
        "lock": "thesis",
        "title_page": _title_page(text),
        "findings_opening": _opening(FINDINGS_MARK_SCHEME, has_scheme=has_scheme),
    }


_REPORT_LIST_HEAD = re.compile(
    r"(?i)^\s*#{0,3}\s*(?:(?:required|report|main)\s+){0,2}"
    r"sections?(?:\s+headings?)?(?:\s+[A-Za-z][A-Za-z'\-]*){0,2}\s*:?\s*$"
)
_REPORT_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d{1,2}[.)])\s+(\S.*?)\s*$")


def report_section_names(text: str) -> list[str]:
    """Section names a report brief or mark scheme lists under a sections heading.

    A workshop list, an entry list, or prose is not this list. Nothing is added.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    names: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if _REPORT_LIST_HEAD.match(stripped):
            if capture and names:
                break
            capture = True
            continue
        if not capture:
            continue
        item = _REPORT_LIST_ITEM.match(line)
        if item:
            names.append(item.group(1).strip())
            continue
        if not stripped:
            if names:
                break
            continue
        break
    return names


def _map_report(text: str, *, has_scheme: bool, scheme: str = "") -> dict[str, Any]:
    """A report keeps the sections the brief or the mark scheme names.

    The list is read, never widened: a brief that names no section adds none.
    """
    names = report_section_names(text) or report_section_names(scheme)
    parts = {
        "named_entries": names,
        "named_by_brief": bool(names),
        "part_count": len(names) or None,
        "unnamed_note": None,
        "named_parts_source": "report" if names else None,
    }
    return {
        **parts,
        "lock": "purpose_and_scope",
        "title_page": _title_page(text),
        "findings_opening": _opening(FINDINGS_MARK_SCHEME, has_scheme=has_scheme),
    }


def _map_diary(text: str, *, has_scheme: bool) -> dict[str, Any]:
    return {
        **_parts(text, use_list=True),
        "named_parts_source": "diary",
        "lock": "entries",
        "title_page": _title_page(text),
        "findings_opening": _opening(FINDINGS_HOW_TO_SCORE_HIGH, has_scheme=has_scheme),
    }


_MAPPERS["essay"] = _map_essay
_MAPPERS["report"] = _map_report
_MAPPERS["diary"] = _map_diary


def _unmapped(writing_type: str) -> dict[str, Any]:
    return {
        "mapped": False,
        "writing_type": writing_type,
        "named_entries": [],
        "named_by_brief": False,
        "part_count": None,
        "unnamed_note": None,
        "lock": None,
        "title_page": None,
        "findings_opening": None,
        "reason": UNMAPPED_REASON,
    }


def _unlabeled(text: str, *, has_scheme: bool) -> dict[str, Any]:
    return {
        "mapped": True,
        "writing_type": None,
        "named_entries": [],
        "named_by_brief": False,
        "part_count": None,
        "unnamed_note": None,
        "lock": None,
        "title_page": _title_page(text),
        "findings_opening": _opening(FINDINGS_MARK_SCHEME, has_scheme=has_scheme),
    }


def contract_for(
    writing_type: str | None,
    text: str,
    *,
    has_scheme: bool,
    scheme: str = "",
) -> dict[str, Any]:
    """The brief fields for this writing type. An unknown type fails closed."""

    if not writing_type:
        filled = _unlabeled(text, has_scheme=has_scheme)
        filled["page_layout"] = layout_spec(text)
        return filled
    mapper = _MAPPERS.get(writing_type)
    if mapper is None:
        row = _unmapped(writing_type)
        row["page_layout"] = {}
        return row
    row = mapper(text, has_scheme=has_scheme, scheme=scheme) if writing_type == "report" else mapper(text, has_scheme=has_scheme)
    if not isinstance(row, dict) or any(key not in row for key in REQUIRED_MAPPING_KEYS):
        missed = _unmapped(writing_type)
        missed["page_layout"] = {}
        return missed
    filled = dict(row)
    filled["page_layout"] = layout_spec(text)
    filled["mapped"] = True
    filled["writing_type"] = writing_type
    return filled


def _record(essay_id: str) -> dict[str, Any]:

    return essay_assignment_gate.read_assignment(essay_id)


def assignment_silence_gaps(essay_id: str) -> list[str]:
    """Gap sentences when a brief or scheme is on the module but silent on a requirement.

    Stage 1 and stage 3 doors attach these beside the Basics pass so the chat names
    what is missing without filling samples-study defaults.
    """
    record = _record(essay_id)
    if record.get("active") is not True:
        return []
    gaps: list[str] = []
    if not record.get("format"):
        gaps.append("Format: the brief does not name one.")
    if not record.get("question"):
        gaps.append("Question: the brief does not name one.")
    from essay_writer.specialists.writer import document_word_band

    if not document_word_band(essay_id):
        gaps.append("Word band: the brief does not name one.")
    return gaps


def opening_card_lines(essay_id: str, stage: str) -> list[str]:
    """Part names and the top band a next-stage Confirm note has to carry."""
    record = _record(essay_id)
    lines: list[str] = []
    if stage in CONTRACT_STAGES:
        for name in record.get("named_entries") or []:
            if isinstance(name, str) and name.strip():
                lines.append(name.strip())
    band = record.get("highest_band")
    if isinstance(band, str) and band.strip():
        lines.append(band.strip())
    return lines


def stage_contract_refusal(essay_id: str, stage: str, text: str) -> dict[str, Any] | None:
    """Refuse an unmapped type, and Entry N when the brief named the parts."""

    record = _record(essay_id)
    if record.get("active") is not True:
        return None
    if record.get("mapped") is False:
        return refuse("brief-mapping", str(record.get("reason") or UNMAPPED_REASON))
    if stage not in CONTRACT_STAGES:
        return None
    if stage == "2" and record.get("named_parts_source") == "report":
        # A report's named sections belong to the draft headings, not the
        # purpose-and-scope lock, so stage 2 is not refused on them.
        return None
    names = [name for name in (record.get("named_entries") or []) if isinstance(name, str) and name.strip()]
    if not names:
        return None
    body = text or ""
    missing = [name for name in names if name.casefold() not in body.casefold()]
    generic = _GENERIC_ENTRY.search(body) is not None
    if not missing and not generic:
        return None
    shown = "; ".join(names)
    return refuse(
        "named-parts",
        f"The brief names these parts: {shown}. Entry numbers are not those names.",
        named_entries=names,
    )


def missing_title_fields(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any] | None = None,
) -> list[str]:
    """Required title-page fields the pack does not carry. Nothing is invented.

    A forbidden or silent name is not missing. An asked label with no stored
    value is left blank on the cover and blocks Word until it is supplied.
    """

    if report is None:
        report = {
            "title": pack.get("title") or pack.get("assessment"),
            "word_count": {},
        }
    return missing_cover_fields(essay_id, pack, report)


def named_heading_issues(essay_id: str, headings: list[str]) -> list[str]:
    """Word headings against the names on the assignment record."""
    from essay_writer.draft_from_review import scheme_section_titles

    if scheme_section_titles(mark_scheme_text(essay_id)):
        # Mark-scheme section titles are already the heading check. They win.
        return []
    record = _record(essay_id)
    if record.get("mapped") is False:
        return []
    names = [name.strip() for name in (record.get("named_entries") or []) if isinstance(name, str) and name.strip()]
    if not names:
        return []
    clean = [heading.strip() for heading in headings if isinstance(heading, str) and heading.strip()]
    shown = "; ".join(names)
    if any(_GENERIC_HEADING.fullmatch(heading) for heading in clean):
        return [f"The brief names these parts: {shown}. Entry numbers are not those names."]
    if [heading.casefold() for heading in clean] != [name.casefold() for name in names]:
        return [f"The headings are the parts the brief names, in that order: {shown}."]
    return []


def word_contract_refusal(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Word refuses a missing required field, generic headings, or an unmapped type."""

    record = _record(essay_id)
    if record.get("active") is True and record.get("mapped") is False:
        return refuse("brief-mapping", str(record.get("reason") or UNMAPPED_REASON), wrote=False)
    if report is None:
        from essay_writer.validate import inspect_pack

        report = inspect_pack(essay_id, pack)
    missing = missing_title_fields(essay_id, pack, report)
    if missing:
        if len(missing) == 1:
            reason = (
                f"The title page is missing the {missing[0]}. Supply it. "
                "It is not invented and it is not taken from a sample."
            )
        else:
            shown = ", ".join(missing)
            reason = (
                f"The title page is missing the {shown}. Supply them. "
                "They are not invented and they are not taken from a sample."
            )
        return refuse(
            "title-page",
            reason,
            missing_fields=missing,
            wrote=False,
        )
    headings: list[str] = []
    sections = pack.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, dict) and isinstance(section.get("heading"), str):
                headings.append(section["heading"])
    issues = named_heading_issues(essay_id, headings)
    if issues:
        return refuse("named-parts", issues[0], wrote=False)
    return None


def sequence_registration(essay_id: str) -> str | None:
    """The registration number stored once on this sequence. Nothing is invented."""

    number = load_state(essay_id).get("registration_number")
    if isinstance(number, str) and number.strip():
        return number.strip()
    return None


def remember_registration(essay_id: str, number: object) -> str | None:
    """Store the first non-empty number. A later call reuses that value."""

    stored = sequence_registration(essay_id)
    if stored:
        return stored
    if not isinstance(number, str) or not number.strip():
        return None
    state = load_state(essay_id)
    state["registration_number"] = number.strip()
    save_state(essay_id, state)
    return number.strip()


def pack_with_registration(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Copy the stored number onto a pack when the assignment record requires it."""
    record = _record(essay_id)
    spec = record.get("title_page")
    if not isinstance(spec, dict) or not spec.get("registration"):
        return pack
    filled = dict(pack)
    stored = sequence_registration(essay_id)
    supplied = filled.get("registration_number")
    if supplied in (None, "", False):
        supplied = filled.get("student_number")
    if stored:
        filled["registration_number"] = stored
        return filled
    kept = remember_registration(essay_id, supplied)
    if kept:
        filled["registration_number"] = kept
    return filled


def student_fields_label(essay_id: str, pack: dict[str, Any]) -> str:
    """Present title-page fields the brief required. Omitted when none are present."""
    record = _record(essay_id)
    spec = record.get("title_page")
    if not isinstance(spec, dict):
        return "omitted"
    present: list[str] = []
    number = pack.get("registration_number")
    if number in (None, "", False):
        number = pack.get("student_number")
    if spec.get("registration") and number not in (None, "", False):
        present.append("registration")
    student = pack.get("student_name")
    if spec.get("name") == "required" and isinstance(student, str) and student.strip():
        present.append("name")
    if not present:
        return "omitted"
    return ",".join(present)
