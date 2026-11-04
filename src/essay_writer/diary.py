"""Reflective diary as a third kind of writing.

The brief decides when the whole assignment is a diary of entries.
Workshop names, one module code, and one deadline are not rules here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from essay_writer import textutil as essay_textutil
from essay_writer.paths import essay_dir, module_code, sequence_number
from essay_writer.textutil import section_word_band, unmarked_labels, word_band_from_brief_text

_DIARY_NAME = re.compile(
    r"(?i)\b(?:reflective diary|learning diary|reflective journal)\b"
)
_TITLE_DIARY = re.compile(
    r"(?i)(?:assignment(?:\s+title)?(?:\s+\d+)?|title)\s*:\s*[^\n]{0,180}"
    r"\b(?:individual\s+)?(?:reflective diary|learning diary|reflective journal)\b"
)
_ENTRIES = re.compile(
    r"(?i)\b(?:entries|each entry|one entry|per entry|weekly entries|workshop entries)\b"
)
_OWN = re.compile(
    r"(?i)\b(?:decisions?|learning events?|own practice|first person)\b"
)
_ANALYSIS = re.compile(r"(?i)\b(?:analys\w*|theory|evidence)\b")
_SECTION_ONLY = re.compile(
    r"(?i)\b(?:reflective section|reflection section|section (?:on|of) reflection)\b"
)
_GENRE_LINE = re.compile(r"(?im)^\s*genre\s*:\s*(essay|report)\b")
_TITLE_OTHER = re.compile(
    r"(?im)^(?:assignment(?:\s+title)?(?:\s+\d+)?|title)\s*:\s*([^\n]+)$"
)

_MODULE_CODE = re.compile(
    r"(?i)\bmodule\s+code\b\s*[:\-]?\s*([A-Z]{2,6}\d{3,4}[A-Z]{2,8})\b"
)
_MODULE_TITLE = re.compile(r"(?im)^\s*module\s+title\s*:\s*(.+)$")
_TITLE_PAGE = re.compile(r"(?im)^\s*title\s+page\s*:\s*(.+)$")
_TITLE_PAGE_SAYS = re.compile(
    r"(?im)^\s*title\s+page\s+(?:should|must|needs to|needs)\s+(.+)$"
)
_MINT_STOP = frozenset(
    {"the", "a", "an", "of", "and", "for", "module", "assignment", "individual"}
)

_TABLE_HEADING = re.compile(
    r"(?i)^#{0,3}\s*(?:marking criteria(?:\s*/\s*feedback form)?|"
    r"assessment criteria|grade descriptors|marking table|feedback form)\b"
)
_KNOWN_SCHEME = re.compile(
    r"(?i)^#{0,3}\s*(?:mark scheme|marking guidelines?|rubric)\b"
)
_FORM_FIELD = re.compile(
    r"(?i)^(?:#{0,3}\s*)?(?:participant number|comments|strengths|"
    r"areas for improvement|marker(?:'s|s)? comments)\b"
)
_HAS_BAND = re.compile(
    r"(?i)(?:\d{1,3}\s*\+|\d{1,3}\s*[-–]\s*\d{1,3}|"
    r"\b(?:high distinction|distinction|merit|credit)\b)"
)

_OCCASION = re.compile(
    r"(?i)one entry for each [^:\n]{0,60}:\s*([^\n.]+)"
)
_ENTRY_COUNT = re.compile(
    r"(?i)\b(\d+|two|three|four|five|six|seven|eight)\s+entries\b"
)
_WORD_NUM = {
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
}
_LIST_HEAD = re.compile(
    r"(?i)^\s*#{0,3}\s*"
    r"(?:entries|sections|occasions|workshops?)"
    r"(?:\s+[A-Za-z][A-Za-z'-]*){0,4}"
    r"\s*:?\s*$"
)
_LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d{1,2}[.)])\s+(\S.*?)\s*$")

_AIM = "aim"
_TASK = "assignment task"
_BLOCK_END = re.compile(
    r"(?i)^(?:aim|assignment task|assignment question|question|task|"
    r"assignment ask|ask|title|format|genre|module code|module title|"
    r"title page|word count|submission|pages|referencing|harvard|"
    r"marking criteria|assessment criteria|mark scheme|marking guidelines?|"
    r"rubric|feedback form)\b"
)

# "your name" is the usual object of a ban. It is not a request for the name.
_NAME_OFF = re.compile(
    r"(?i)(?:"
    r"\bname (?:does not|must not|should not)\b|"
    r"\b(?:do not|don['\u2019]t|must not|should not)\s+"
    r"(?:include|print|show|put|write|add)\s+"
    r"(?:(?:the|a|your)\s+)?(?:student\s+)?name\b|"
    r"\bno (?:student )?name\b|"
    r"\bnot your name\b|"
    r"\bleave (?:(?:the|your)\s+)?name off\b|"
    r"\bwithout (?:(?:the|a|your)\s+)?(?:student\s+)?name\b|"
    r"\bthe name stays off\b|"
    r"\byour name (?:stays off|is not|must not|should not)\b"
    r")"
)
_NAME_ON = re.compile(
    r"(?i)(?:include|show|print|carries|with) (?:the |a |your )?student name|"
    r"title page[^\n]{0,80}\bstudent name\b"
)
# A positive ask. "student no" is not read as the word "no" after the phrase is removed.
_REG_ASK = re.compile(
    r"(?i)\b(?:registration numbers?|registration nos?\.?|"
    r"student numbers?|student nos?\.?|student ids?|"
    r"candidate numbers?|enrolment numbers?|enrollment numbers?|matriculation numbers?)\b"
)
_REG_NEG = re.compile(
    r"(?i)\b(?:do not|don't|must not|should not|without|no)\b"
)
_TITLE_HEADING = re.compile(r"(?i)^\s*#{0,3}\s*title\s+page\s*:?\s*$")
_TITLE_BULLET = re.compile(r"^\s*(?:[-*]|\d{1,2}[.)])\s+")
_TITLE_NEXT = re.compile(
    r"(?i)^\s*#{0,3}\s*(?:aim|assignment(?:\s+task|\s+question)?|question|task|"
    r"format|genre|module\s+code|module\s+title|word\s+count|submission|pages|"
    r"referencing|harvard|marking|assessment\s+criteria|"
    r"length|structure|presentation|margins?|layout|formatting|tutorials?|"
    r"guidance|rubric|academic\s+style)\b"
)
_TITLE_LABELS = (
    ("module title", "module_title"),
    ("module code", "module_code"),
    ("assignment title", "assignment_title"),
    ("registration numbers", "registration"),
    ("registration number", "registration"),
    ("registration nos", "registration"),
    ("registration no", "registration"),
    ("student numbers", "registration"),
    ("student number", "registration"),
    ("student nos", "registration"),
    ("student no", "registration"),
    ("student ids", "registration"),
    ("student id", "registration"),
    ("candidate numbers", "registration"),
    ("candidate number", "registration"),
    ("enrolment number", "registration"),
    ("enrollment number", "registration"),
    ("matriculation number", "registration"),
    ("word count", "word_count"),
    ("name", "name"),
)
_PROGRAMME_ASK = re.compile(
    r"(?i)\b(?:programme name|programme code|partner institution)\b"
)
_BANDISH = re.compile(
    r"(?i)\b(?:thin|partial|sound|clear|exact|consistent|coherent|competent|"
    r"satisfactory|appropriate|relevant|poor|good|excellent|adequate|"
    r"evidenced|missing|weak|strong|high|low|pass|fail|merit|distinction)\b"
)
# A thousands separator is part of a number. It is not a new field.
_ASK_SPLIT = re.compile(r"\s*(?:(?<!\d),(?!\d)|;|\band\b)\s*")
_ASK_LEAD = re.compile(
    r"(?i)^(?:please\s+)?(?:include|show|print|state|list|give|with)\s+"
)
# "It should specify the module title, ..." is a list of fields, not one field.
_FIELD_CUE = re.compile(
    r"(?i)^(?:please\s+)?"
    r"(?:(?:it|this|the|a)\s+)?"
    r"(?:(?:title|cover)\s+page\s+)?"
    r"(?:(?:should|must|needs to|needs)\s+)?"
    r"(?:also\s+)?"
    r"(?:specify|specifies|specified|include|includes|included|including|"
    r"show|shows|list|lists|state|states|give|gives)\s+"
)
_FIELD_CUE_WORTH = re.compile(
    r"(?i)\b(?:should|must|please)\b|\b(?:title|cover)\s+page\b|,|\band\b"
)
_INSTRUCTION_WORD = re.compile(
    r"(?i)\b(?:should|must|specify|specifies|include|includes|including|"
    r"use|using|follow|follows|followed|show|shows|shown|mark|marked|"
    r"state|stated|submit|keep|ensure|write|put|make|require|required|"
    r"repeat|repeats|clearly)\b"
)
_LAYOUT_WORD = re.compile(
    r"(?i)\b(?:margins?|fonts?|arial|harvard|spacing|justified|justify|"
    r"bold|italic|headings?|page numbers?|referenc\w*|appendices|appendix|"
    r"headers?|footers?|template|title case|line spacing|lower right|"
    r"upper right|word-processed|word processed)\b"
)
# Instruction and mark-scheme language. These are not identifiers the cover prints.
_CRUMB_LABEL = re.compile(
    r"(?i)(?:"
    r"\b(?:length|lengths|structure|structures|presentation|formatting|layout|"
    r"margins?|tutorials|guidance|fluent|marking|criteria|criterion|rubric|"
    r"fonts?|spacing)\b|"
    r"\bacademic\s+style\b|"
    r"\b(?:it\s+)?should\s+specify\b"
    r")"
)
_COVER_RESIDUE = re.compile(
    r"(?i)^(?:"
    r"registration number\s*:|"
    r"counted words\s*:|"
    r"stated word count\s*:|"
    r"conclusion\s*:|"
    r"module title\s*:|"
    r"module code\s*:|"
    r"assignment title\s*:|"
    r"name\s*:"
    r")"
)
_STATUS_LINE = re.compile(r"(?i)^(?:drafts?|final|final draft|first draft|the draft)$")
_NOT_A_FIELD = frozenset(
    {
        "draft",
        "drafts",
        "final",
        "complete",
        "completed",
        "missing",
        "correct",
        "structure",
        "presentation",
        "shown",
        "followed",
        "following",
        "harvard",
        "arial",
        "bold",
        "thin",
        "partial",
        "sound",
        "clear",
        "exact",
        "consistent",
        "coherent",
        "competent",
        "satisfactory",
        "appropriate",
        "relevant",
    }
)
_ASSIGNMENT_LINE = re.compile(
    r"(?im)^[ \t>*_-]*assignment(?:\s+title)?(?:\s+\d+)?\s*:\s*(.+?)\s*$"
)
_BRIEF_TITLE_LINE = re.compile(
    r"(?im)^[ \t>*_-]*(?!module\s)title\s*:\s*(.+?)\s*$"
)
_PLACEHOLDER_TITLE = re.compile(
    r"(?i)^(?:draft|final|final draft|first draft|the draft)$"
)
_GATE_TIP_TITLE = re.compile(
    r"(?i)^(?:"
    r"how to score(?:\s+high)?\b|"
    r"the mark scheme scores\b|"
    r"no mark scheme is on this module\b|"
    r"the mark scheme is on this module\b"
    r")"
)
_BAND_ONLY_TITLE = re.compile(
    r"^(?:\d{1,3}\s*\+|\d{1,3}\s*[-–]\s*\d{1,3})$"
)
_ASK_ARTICLE = re.compile(r"(?i)^(?:the|a|an|your)\s+")
_ASK_TRAIL = re.compile(
    r"(?i)\s+(?:are|is|must be|should be)\s+(?:present|shown|included|stated|given)\s*$"
)
_NEG_START = re.compile(r"(?i)^(?:do not|don['\u2019]t|must not|should not|without|no)\b")

_MARGIN = re.compile(r"(?i)(\d+(?:\.\d+)?)\s*cm\s+margins")
_PAGE_RIGHT = re.compile(
    r"(?i)(?:"
    r"page\s+numbers?.{0,80}?(?:lower|bottom)[\s-]*right"
    r"|(?:lower|bottom)[\s-]*right.{0,80}?page\s+numbers?"
    r")"
)
_SIZE = re.compile(r"(?i)\bsize\s+12\b")
_HEADING_LARGER = re.compile(r"(?i)heading[^\n]{0,40}\b(?:14|16|18|larger)\b")
_JUSTIFY = re.compile(r"(?i)fully justified|body text[^\n]{0,40}justif")

NAME_KEYS = frozenset({"student_name", "student"})
NUMBER_KEYS = frozenset(
    {"student_number", "student_id", "student_no", "registration_number"}
)


def diary_signals(text: str) -> bool:
    """True when the whole assignment is a reflective diary of entries.

    The name alone is not enough. An essay or a report that only contains
    a reflective section stays that kind of writing.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    labels = unmarked_labels(text)
    if not _DIARY_NAME.search(labels):
        return False
    if not (_ENTRIES.search(labels) or (_OWN.search(labels) and _ANALYSIS.search(labels))):
        return False
    if _title_is_diary(labels):
        return True
    if _GENRE_LINE.search(labels):
        return False
    if _title_is_other(labels):
        return False
    if _SECTION_ONLY.search(labels):
        return False
    return True


def _title_is_diary(labels: str) -> bool:
    return _TITLE_DIARY.search(labels) is not None


def _title_is_other(labels: str) -> bool:
    match = _TITLE_OTHER.search(labels)
    if match is None:
        return False
    line = match.group(1)
    if _DIARY_NAME.search(line):
        return False
    return re.search(r"(?i)\b(?:essay|report|case study|case analysis)\b", line) is not None


def mint_module_id(title: str) -> str:
    """A short id from the module title. It is not forced to end in HK."""
    words = [
        word
        for word in re.findall(r"[A-Za-z]+", title or "")
        if word.casefold() not in _MINT_STOP
    ]
    if not words:
        words = ["Module"]
    raw = "".join(word[:4] for word in words[:3]).upper()
    raw = re.sub(r"[^A-Z]", "", raw)
    if len(raw) < 4:
        raw = (raw + "MODU")[:4]
    raw = raw[:16]
    if raw.endswith("HK"):
        raw = raw[:-2] + "MD"
    return raw


def module_id_from_brief(text: str) -> str | None:
    """The code the brief prints, or a short id from the module title."""
    if not isinstance(text, str) or not text.strip():
        return None
    found = _MODULE_CODE.findall(text)
    if found:
        return max(found, key=len)
    title = _MODULE_TITLE.search(text)
    if title and title.group(1).strip():
        return mint_module_id(title.group(1).strip())
    return None


def marking_table_span(brief: str) -> str:
    """The mark table printed in the brief, without the marker's form fields."""
    if not isinstance(brief, str) or not brief.strip():
        return ""
    lines = brief.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if _KNOWN_SCHEME.match(stripped):
            continue
        if _TABLE_HEADING.match(stripped):
            start = index
            break
    if start is None:
        return ""
    taken: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if taken and _FORM_FIELD.match(stripped):
            break
        if taken and stripped.startswith("#") and not _TABLE_HEADING.match(stripped):
            break
        taken.append(line)
    while taken and not taken[-1].strip():
        taken.pop()
    text = "\n".join(taken).strip()
    if not text or not _HAS_BAND.search(text):
        return ""
    return text + "\n"


def extract_marking_table(essay_id: str) -> str:
    """Copy a brief-only mark table to marking-table.md. Return that copy."""

    span = marking_table_span(essay_textutil.module_brief_text(essay_id))
    if not span:
        return ""
    folder = essay_dir(module_code(essay_id))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "marking-table.md"
    if not path.is_file():
        path.write_text(span, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def top_column_quote(scheme: str, label: str) -> str:
    """The printed top-column label, plus the cells under it when a table has them."""
    if not label:
        return ""
    rows = [line for line in scheme.splitlines() if line.strip().startswith("|")]
    if len(rows) < 2:
        return label
    header = [cell.strip() for cell in rows[0].strip().strip("|").split("|")]
    index = None
    for place, cell in enumerate(header):
        if label.casefold() in re.sub(r"\s+", "", cell).casefold() or label.casefold() in cell.casefold():
            index = place
            break
    if index is None:
        return label
    cells: list[str] = []
    for row in rows[1:]:
        cols = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if index >= len(cols):
            continue
        cell = cols[index]
        if not cell or set(cell) <= set("-: "):
            continue
        cells.append(cell)
    printed = header[index]
    if not cells:
        return printed
    return f"{printed}. " + "; ".join(cells)


def _block_after(labels: str, heading: str) -> str | None:
    lines = labels.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        same = re.match(rf"(?i){re.escape(heading)}\s*:\s*(.*)$", stripped)
        if same:
            rest = same.group(1).strip()
            extra = _paragraph(lines, index + 1)
            joined = " ".join(part for part in (rest, extra) if part).strip()
            return joined or None
        if stripped.casefold() == heading:
            return _paragraph(lines, index + 1)
    return None


def _paragraph(lines: list[str], start: int) -> str:
    taken: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped:
            if taken:
                break
            continue
        if _BLOCK_END.match(stripped) and not taken:
            break
        if _BLOCK_END.match(stripped) and ":" in stripped[:40]:
            break
        taken.append(stripped)
    return " ".join(taken).strip()


def diary_ask(text: str) -> str | None:
    """Aim and assignment task, when the brief uses those headings."""
    if not isinstance(text, str) or not text.strip():
        return None

    labels = unmarked_labels(text)
    aim = _block_after(labels, _AIM)
    task = _block_after(labels, _TASK)
    parts = [part for part in (aim, task) if part]
    if not parts:
        return None
    return " ".join(parts)


def named_entries(text: str) -> list[str]:
    """Entry or section names the brief prints. Nothing is added."""
    if not isinstance(text, str) or not text.strip():
        return []
    match = _OCCASION.search(text)
    if match:
        return _split_list(match.group(1))
    names: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        if _LIST_HEAD.match(stripped):
            if capture and names:
                break
            capture = True
            continue
        if not capture:
            continue
        item = _LIST_ITEM.match(line)
        if item:
            names.append(item.group(1).strip())
            continue
        if not stripped:
            if names:
                break
            continue
        break
    return names


def entry_count(text: str) -> int | None:
    named = named_entries(text)
    if named:
        return len(named)
    if not isinstance(text, str):
        return None
    match = _ENTRY_COUNT.search(text)
    if match is None:
        return None
    raw = match.group(1).casefold()
    if raw.isdigit():
        return int(raw)
    return _WORD_NUM.get(raw)


def _split_list(blob: str) -> list[str]:
    parts = re.split(r",|\band\b|&", blob)
    names: list[str] = []
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip(" .;")
        if cleaned:
            names.append(cleaned)
    return names


def section_word_plan(
    text: str,
    *,
    names: list[str] | None = None,
    part_count: int | None = None,
) -> dict[str, Any]:
    """Total band plus a length for each entry the brief names.

    A length the brief does not state is a plan. It is not a brief rule
    and it is not a mark band. A clash is shown and neither figure is dropped.
    Names passed in are the assignment record. They are not parsed again.
    """

    total = word_band_from_brief_text(text)
    section = section_word_band(text)
    if names is None:
        names = named_entries(text)
    else:
        names = [name.strip() for name in names if isinstance(name, str) and name.strip()]
    if part_count is None:
        count = len(names) if names else (entry_count(text) or 0)
    else:
        count = max(0, part_count)
    clash = None
    plan_not_brief_rule = False
    sections: list[dict[str, Any]] = []
    if section and names:
        for name in names:
            sections.append(
                {**section, "name": name, "from_brief": True, "named_by_brief": True}
            )
    elif section and count:
        for index in range(count):
            sections.append(
                {**section, "name": f"Entry {index + 1}", "from_brief": True, "named_by_brief": False}
            )
    elif total and (names or count) and not section:
        plan_not_brief_rule = True
        labels = names or [f"Entry {index + 1}" for index in range(count)]
        named_by_brief = bool(names)
        limit = total.get("limit")
        tolerance = total.get("tolerance", 0.10)
        if isinstance(limit, int) and limit > 0 and labels:
            base = limit // len(labels)
            extra = limit - base * len(labels)
            for index, name in enumerate(labels):
                part = base + (extra if index == len(labels) - 1 else 0)
                low = round(part * (1 - float(tolerance)))
                high = round(part * (1 + float(tolerance)))
                sections.append(
                    {
                        "name": name,
                        "min": low,
                        "max": high,
                        "limit": part,
                        "tolerance": tolerance,
                        "from_brief": False,
                        "named_by_brief": named_by_brief,
                    }
                )
    if names and not sections:
        for name in names:
            sections.append({"name": name, "from_brief": True, "named_by_brief": True})
    if section and total and sections:
        per = section.get("limit")
        whole = total.get("limit")
        if isinstance(per, int) and isinstance(whole, int) and sections:
            product = per * len(sections)
            total_min = total.get("min")
            total_max = total.get("max")
            if isinstance(total_min, int) and isinstance(total_max, int) and not (
                total_min <= product <= total_max
            ):
                clash = (
                    "The per-entry lengths and the total do not add up. "
                    "The entry length stays on the entry and the total stays on the whole body."
                )
    unnamed_note = None
    if not names and count:
        unnamed_note = "The brief did not name these parts."
    return {
        "total": total,
        "sections": sections,
        "plan_not_brief_rule": plan_not_brief_rule,
        "clash": clash,
        "named_by_brief": bool(names),
        "unnamed_note": unnamed_note,
    }


def section_plan_for(essay_id: str) -> dict[str, Any]:
    """Section lengths from the assignment record, not a second parse."""
    from essay_writer.assignment_gate import assignment_requirements

    record = assignment_requirements(essay_id)
    if record.get("mapped") is False:
        return {
            "ok": False,
            "mapped": False,
            "reason": record.get("reason"),
            "sections": [],
            "total": None,
            "plan_not_brief_rule": False,
            "clash": None,
            "named_by_brief": False,
            "unnamed_note": None,
        }
    stored = record.get("named_entries")
    names = stored if isinstance(stored, list) else []
    if record.get("lock") in {"thesis", "purpose_and_scope"}:
        names = []
        count = 0
    elif isinstance(record.get("part_count"), int):
        count = record["part_count"]
    else:
        count = len(names)
    plan = section_word_plan(essay_textutil.module_brief_text(essay_id), names=names, part_count=count)
    plan["unnamed_note"] = record.get("unnamed_note")
    plan["named_by_brief"] = record.get("named_by_brief") is True
    plan["mapped"] = True
    return plan


def _plain_brief(text: str) -> str:
    """Brief text with emphasis and non-breaking spaces removed, for label reads."""

    plain = text.replace("\u00a0", " ").replace("\u202f", " ")
    return unmarked_labels(plain)


def _registration_asked(labels: str) -> bool:
    """True when a sentence asks for a registration number and does not cancel that ask."""
    for sentence in re.split(r"[\n.!?]+", labels):
        if _REG_ASK.search(sentence) is None:
            continue
        remainder = _REG_ASK.sub(" ", sentence)
        if _REG_NEG.search(remainder):
            continue
        return True
    return False


def _title_page_blob(labels: str) -> str:
    """The title-page line, plus a bare Title page heading and the lines under it."""
    parts: list[str] = []
    listed = _TITLE_PAGE.search(labels)
    if listed:
        parts.append(listed.group(1))
    says = _TITLE_PAGE_SAYS.search(labels)
    if says:
        parts.append(says.group(1))
    lines = labels.splitlines()
    index = 0
    while index < len(lines):
        if _TITLE_HEADING.match(lines[index]):
            index += 1
            chunk: list[str] = []
            while index < len(lines):
                row = lines[index]
                if not row.strip():
                    break
                if not _TITLE_BULLET.match(row) and _TITLE_NEXT.match(row):
                    break
                chunk.append(row)
                index += 1
            if chunk:
                parts.append("\n".join(chunk))
            continue
        index += 1
    return "\n".join(parts)


def _has_label(blob: str, label: str) -> bool:
    """True when label is its own words. A shorter label does not match inside a longer one."""
    return (
        re.search(r"(?i)(?<![a-z])" + re.escape(label) + r"(?![a-z])", blob) is not None
    )


def _marking_title_asks(labels: str) -> str:
    """Title-page asks written in the marking table. Other rows are not fields."""
    span = marking_table_span(labels)
    if not span:
        return ""
    found: list[str] = []
    for raw in span.splitlines():
        stripped = raw.strip()
        folded = stripped.casefold()
        if "title page" not in folded and "cover page" not in folded:
            continue
        if not stripped.startswith("|"):
            found.append(stripped)
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        for index, cell in enumerate(cells):
            if not cell or set(cell) <= set("-: "):
                continue
            cell_folded = cell.casefold()
            if cell_folded in {"title page", "cover page"}:
                continue
            if "title page" in cell_folded or "cover page" in cell_folded:
                tail = re.split(r"(?i)\b(?:title page|cover page)\b", cell, maxsplit=1)[-1]
                tail = tail.strip(" :.-")
                if tail:
                    found.append(tail)
                continue
            # The first cell is the criterion name. It is not a cover field.
            if index == 0:
                continue
            if len(cell.split()) <= 3 and _BANDISH.search(cell):
                continue
            found.append(cell)
    return "\n".join(found)


def _phrase_items(ask: str) -> list[str]:
    """Field phrases in a title-page ask. A do-not-include sentence is not a phrase."""
    items: list[str] = []
    for raw in ask.splitlines():
        line = _TITLE_BULLET.sub("", raw).strip()
        if not line or line.startswith("|"):
            continue
        for sentence in re.split(r"[.!?]+", line):
            sentence = sentence.strip(" -*")
            sentence = re.sub(r"\([^)]*\)", " ", sentence)
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if not sentence or _NAME_OFF.search(sentence) or _NEG_START.search(sentence):
                continue
            if _REG_ASK.search(sentence) and _REG_NEG.search(_REG_ASK.sub(" ", sentence)):
                continue
            if _FIELD_CUE.search(sentence) and _FIELD_CUE_WORTH.search(sentence):
                sentence = _FIELD_CUE.sub("", sentence, count=1).strip()
                if not sentence:
                    continue
            for part in _ASK_SPLIT.split(sentence):
                part = part.strip(" .:-*")
                part = _ASK_LEAD.sub("", part).strip()
                part = _ASK_ARTICLE.sub("", part).strip()
                part = _ASK_TRAIL.sub("", part).strip(" .:-")
                if part:
                    items.append(part)
    return items


def _known_phrase(phrase: str) -> bool:
    """True when the phrase is a known title-page field and nothing else."""
    folded = phrase.casefold().strip()
    folded = _ASK_ARTICLE.sub("", folded).strip()
    for label, _key in _TITLE_LABELS:
        if folded == label:
            return True
        if not _has_label(folded, label):
            continue
        remainder = re.sub(
            r"(?i)(?<![a-z])" + re.escape(label) + r"(?![a-z])",
            " ",
            folded,
        )
        remainder = re.sub(
            r"(?i)\b(?:the|a|an|your|and|of|on|for|is|are)\b",
            " ",
            remainder,
        )
        remainder = re.sub(r"\s+", " ", remainder).strip(" .:-")
        if not remainder:
            return True
    if _PROGRAMME_ASK.search(folded) and not re.sub(
        r"(?i)\b(?:programme name|programme code|partner institution)\b",
        " ",
        folded,
    ).strip():
        return True
    return False


def _plausible_field(phrase: str) -> bool:
    if not phrase or len(phrase) > 60:
        return False
    if set(phrase) <= set("-:| "):
        return False
    words = phrase.split()
    if not 1 <= len(words) <= 6:
        return False
    if not re.search(r"[A-Za-z]", phrase):
        return False
    if len(words) <= 3 and _BANDISH.search(phrase):
        return False
    folded = phrase.casefold()
    if folded in {"title page", "cover page", "front page", "criterion", "feedback"}:
        return False
    if _NAME_OFF.search(phrase) or _NEG_START.search(phrase):
        return False
    return True


def _display_label(phrase: str) -> str:
    shown = re.sub(r"\s+", " ", phrase).strip(" .:-")
    if shown and shown.casefold() == shown:
        shown = shown[0].upper() + shown[1:]
    return shown


def _norm_phrase(text: str) -> str:
    folded = text.casefold().replace("–", "-").replace("—", "-")
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def _stated_cover_values(text: str) -> list[str]:
    """Title, module, and code the brief already prints. They are values, not fields."""
    values: list[str] = []
    for pattern in (_MODULE_TITLE, _ASSIGNMENT_LINE, _BRIEF_TITLE_LINE):
        for match in pattern.finditer(text):
            value = match.group(1).strip()
            if value:
                values.append(value)
    values.extend(_MODULE_CODE.findall(text))
    return values


def _is_stated_value(phrase: str, values: list[str]) -> bool:
    folded = _norm_phrase(phrase)
    if len(folded) < 3:
        return False
    for value in values:
        norm = _norm_phrase(value)
        if norm and (folded == norm or folded in norm):
            return True
    return False


def _mentions_known_field(phrase: str) -> bool:
    """True when the phrase is about a field the known keys already record."""
    folded = phrase.casefold()
    return any(_has_label(folded, label) for label, _key in _TITLE_LABELS)


def _not_a_cover_field(phrase: str, values: list[str]) -> bool:
    """Instruction prose, a sample line, or a layout note is not a cover field."""
    folded = phrase.casefold().strip()
    if not folded or _STATUS_LINE.fullmatch(folded):
        return True
    if _mentions_known_field(phrase):
        return True
    if _is_stated_value(phrase, values):
        return True
    if re.search(r"\d", phrase):
        return True
    if _INSTRUCTION_WORD.search(phrase) or _LAYOUT_WORD.search(phrase):
        return True
    if _CRUMB_LABEL.search(phrase):
        return True
    words = [word.strip(" .:-") for word in folded.split()]
    words = [word for word in words if word]
    if len(words) == 1 and words[0] in _NOT_A_FIELD:
        return True
    fillers = _NOT_A_FIELD | {"and", "or", "the", "a", "of"}
    if words and all(word in fillers for word in words):
        return True
    return False


def _unknown_cover_labels(ask: str, brief: str = "") -> list[str]:
    """Labels the brief asks for that are not the known title-page keys.

    A sentence that tells the student what to do, a sample of the finished
    page, and a marking comment are not fields. A real asked field stays,
    even when its value is empty.
    """
    values = _stated_cover_values(brief)
    labels: list[str] = []
    seen: set[str] = set()
    for phrase in _phrase_items(ask):
        if _known_phrase(phrase) or not _plausible_field(phrase):
            continue
        if _not_a_cover_field(phrase, values):
            continue
        shown = _display_label(phrase)
        key = shown.casefold()
        if not shown or key in seen:
            continue
        seen.add(key)
        labels.append(shown)
    return labels


def _real_title(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or _PLACEHOLDER_TITLE.fullmatch(text):
        return ""
    return text


def gate_tip_cover_title(text: str) -> bool:
    """True when text is a gate or genre tip line, not a brief assessment title."""
    cleaned = text.strip()
    if not cleaned:
        return False
    folded = cleaned.casefold()
    if _GATE_TIP_TITLE.search(cleaned):
        return True
    if _BAND_ONLY_TITLE.match(cleaned):
        return True
    if "how to score" in folded and re.search(r"\d{1,3}\s*\+", cleaned):
        return True
    return False


def _cover_stored_title(value: object) -> str:
    """Pack or report title usable on the cover. Gate tips and Draft are rejected."""
    text = _real_title(value)
    if text and gate_tip_cover_title(text):
        return ""
    return text


def assignment_on_cover(
    pack: dict[str, Any],
    report: dict[str, Any],
    brief: str,
) -> str:
    """The assignment title the cover prints.

    A pack title of Draft is the working file, not the assignment title.
    The brief's own assignment-title line is used when the pack has none.
    Nothing is invented.
    """
    for key in ("assessment", "title"):
        if not isinstance(pack, dict):
            break
        found = _cover_stored_title(pack.get(key))
        if found:
            return found
    found = _cover_stored_title(report.get("title"))
    if found:
        return found
    if not isinstance(brief, str):
        return ""
    match = _ASSIGNMENT_LINE.search(brief)
    if match is not None:
        return match.group(1).strip()
    match = _BRIEF_TITLE_LINE.search(brief)
    if match is None:
        return ""
    return match.group(1).strip()


def _positive_name_ask(ask: str) -> bool:
    """True when a title-page sentence asks for the name and does not ban it."""
    for sentence in re.split(r"[\n.!?]+", ask):
        if not _has_label(sentence.casefold(), "name"):
            continue
        if _NAME_OFF.search(sentence) or _NEG_START.search(sentence):
            continue
        return True
    return False


def title_page_spec(text: str) -> dict[str, Any]:
    """Fields the brief or its marking table lists. Nothing else is assumed."""
    spec: dict[str, Any] = {
        "fields": [],
        "registration": False,
        "name": "silent",
        "programme": False,
        "labels": [],
    }
    if not isinstance(text, str) or not text.strip():
        return spec
    labels = _plain_brief(text)
    if _NAME_OFF.search(labels):
        spec["name"] = "forbidden"
    elif _NAME_ON.search(labels):
        spec["name"] = "required"
    spec["registration"] = _registration_asked(labels)
    spec["programme"] = _PROGRAMME_ASK.search(labels) is not None
    ask = "\n".join(
        part
        for part in (_title_page_blob(labels), _marking_title_asks(labels))
        if part
    )
    folded = ask.casefold()
    if folded:
        for label, key in _TITLE_LABELS:
            if key == "name" and spec["name"] == "forbidden":
                continue
            if key == "name" and not _positive_name_ask(ask):
                continue
            if _has_label(folded, label) and key not in spec["fields"]:
                spec["fields"].append(key)
        if "name" in spec["fields"] and spec["name"] == "silent":
            spec["name"] = "required"
    if spec["name"] == "forbidden":
        spec["fields"] = [key for key in spec["fields"] if key != "name"]
    if spec["registration"] and "registration" not in spec["fields"]:
        spec["fields"].append("registration")
    spec["labels"] = _unknown_cover_labels(ask, labels)
    return scrub_title_page_labels(spec, labels)


def scrub_title_page_labels(spec: dict[str, Any], brief: str = "") -> dict[str, Any]:
    """Drop mark-scheme crumbs from stored title-page labels. Real fields stay."""
    if not isinstance(spec, dict):
        return spec
    raw = spec.get("labels")
    if not isinstance(raw, list) or not raw:
        return spec
    values = _stated_cover_values(brief) if isinstance(brief, str) and brief.strip() else []
    cleaned: list[str] = []
    seen: set[str] = set()
    for label in raw:
        if not isinstance(label, str):
            continue
        text = label.strip().rstrip(":").strip()
        if not text or not cover_label_kept(text, values):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(_display_label(text))
    out = dict(spec)
    out["labels"] = cleaned
    return out


def cover_label_kept(phrase: str, values: list[str] | None = None) -> bool:
    """True when phrase is an asked cover field, not an instruction or mark-scheme crumb.

    A label already stored on the assignment record is judged again here.
    """
    text = phrase.strip().rstrip(":").strip()
    if not text or not _plausible_field(text) or _known_phrase(text):
        return False
    if _not_a_cover_field(text, values or []):
        return False
    return True


def cover_residue_line(line: str, cover_lines: list[str] | None = None) -> bool:
    """An earlier cover line or a Draft wrapper line. Essay prose is kept."""
    text = line.strip()
    if not text:
        return True
    if gate_tip_cover_title(text):
        return True
    folded = text.casefold()
    if folded in {"draft", "references"}:
        return True
    if cover_lines:
        known = {item.strip().casefold() for item in cover_lines if item and item.strip()}
        if folded in known:
            return True
    if _COVER_RESIDUE.match(text):
        return True
    if text.endswith(":") and len(text.split()) <= 8:
        return True
    if len(text.split()) <= 6 and _CRUMB_LABEL.search(text):
        return True
    if (
        len(text.split()) <= 24
        and _FIELD_CUE.search(text)
        and _FIELD_CUE_WORTH.search(text)
    ):
        return True
    return False


def title_page_extra_values(pack: dict[str, Any]) -> dict[str, str]:
    """Values the pack supplies for asked title-page labels outside the known keys."""
    raw = pack.get("title_page_fields")
    if not isinstance(raw, dict):
        return {}
    kept: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        text = value.strip()
        if text:
            kept[key.casefold()] = text
    return kept


def custom_cover_value(label: str, pack: dict[str, Any]) -> str | None:
    """Stored value for a brief-named cover label. Nothing is invented."""
    return title_page_extra_values(pack).get(label.casefold())


def blank_field_labels(spec: dict[str, Any], brief: str = "") -> list[str]:
    """Cover labels for asked fields that are not known keys. The value stays blank.

    Labels already stored on the assignment record are filtered again, so a
    mark-scheme crumb cached from an earlier read is not printed.
    """
    values = _stated_cover_values(brief) if isinstance(brief, str) and brief.strip() else []
    lines: list[str] = []
    for label in spec.get("labels") or []:
        if not isinstance(label, str):
            continue
        text = label.strip().rstrip(":").strip()
        if text and cover_label_kept(text, values):
            lines.append(f"{text}:")
    return lines


def _cover_line_present(lines: list[str], text: str) -> bool:
    """True when an exact cover line or the same assignment title is already printed."""
    wanted = text.strip()
    if not wanted:
        return False
    folded = wanted.casefold()
    for line in lines:
        if line.strip() == wanted:
            return True
        if line.strip().casefold() == folded:
            return True
    return False


@dataclass(frozen=True)
class CoverFieldRow:
    """One cover row from the brief and marking table. Values are never invented."""

    label: str
    value: str
    kind: Literal["asked", "house"]
    key: str = ""


def print_cover_row(row: CoverFieldRow) -> str:
    """Format one cover row. A filled custom field is a bare value; empty is Label:."""
    value = row.value
    label = row.label
    key = row.key
    if key == "registration":
        return f"Registration number: {value}" if value else "Registration number:"
    if key == "word_count":
        return f"Counted words: {value}" if value else "Counted words:"
    if key == "stated_word_count":
        return f"Stated word count: {value}"
    if key == "conclusion_noted":
        return "Conclusion: noted"
    if key == "conclusion_open":
        return "Conclusion: open — not a settled finding"
    if key == "module_title" and not value:
        return "Module title:"
    if key == "module_code" and not value:
        return "Module code:"
    if key == "assignment_title" and not value:
        return "Assignment title:"
    if key == "name" and not value:
        return "Name:"
    if key == "custom" and not value:
        return f"{label}:"
    if value:
        return value
    if label:
        return f"{label}:"
    return ""


def _row_present(rows: list[CoverFieldRow], text: str) -> bool:
    wanted = text.strip()
    if not wanted:
        return False
    folded = wanted.casefold()
    for row in rows:
        line = print_cover_row(row)
        if line.strip() == wanted or line.strip().casefold() == folded:
            return True
    return False


def cover_field_rows(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    *,
    essay: bool,
) -> list[CoverFieldRow]:
    """Brief plus marking table → ordered cover rows. Diary is asked only; essay adds house rows."""
    from essay_writer.assignment_gate import assignment_requirements, read_assignment
    from essay_writer.programme import PROGRAMME

    brief = essay_textutil.module_brief_text(essay_id)
    seen = assignment_requirements(essay_id)
    stored = seen.get("title_page")
    spec = stored if isinstance(stored, dict) and stored.get("fields") else title_page_spec(brief)
    fields = list(spec.get("fields") or [])
    rows: list[CoverFieldRow] = []

    if essay or spec.get("programme"):
        for programme_key in ("partner", "award", "title", "code"):
            rows.append(
                CoverFieldRow("", str(PROGRAMME[programme_key]), "house", "programme")
            )

    module_title = pack.get("module_title")
    if not isinstance(module_title, str) or not module_title.strip():
        found = _MODULE_TITLE.search(brief)
        module_title = found.group(1).strip() if found else ""
    assignment = assignment_on_cover(pack, report, brief)
    code = module_id_from_brief(brief) or module_code(essay_id)
    number_str = _present_text(pack.get("registration_number")) or _present_text(
        pack.get("student_number")
    )
    counted = report.get("word_count", {}).get("counted")
    counted_str = str(counted) if isinstance(counted, int) else ""

    for key in fields:
        if key == "module_title":
            value = (
                module_title.strip()
                if isinstance(module_title, str) and module_title.strip()
                else ""
            )
            rows.append(CoverFieldRow("Module title", value, "asked", "module_title"))
        elif key == "module_code":
            rows.append(
                CoverFieldRow(
                    "Module code",
                    str(code) if code else "",
                    "asked",
                    "module_code",
                )
            )
        elif key == "assignment_title":
            value = (
                assignment.strip()
                if isinstance(assignment, str) and assignment.strip()
                else ""
            )
            rows.append(CoverFieldRow("Assignment title", value, "asked", "assignment_title"))
        elif key == "registration" and spec.get("registration"):
            rows.append(
                CoverFieldRow("Registration number", number_str, "asked", "registration")
            )
        elif key == "word_count":
            rows.append(CoverFieldRow("Counted words", counted_str, "asked", "word_count"))
        elif key == "name" and spec.get("name") == "required":
            student = pack.get("student_name")
            value = student.strip() if isinstance(student, str) and student.strip() else ""
            rows.append(CoverFieldRow("Name", value, "asked", "name"))

    stated_values = _stated_cover_values(brief)
    for label in spec.get("labels") or []:
        if not isinstance(label, str):
            continue
        text = label.strip().rstrip(":").strip()
        if not text:
            continue
        stored_value = custom_cover_value(text, pack)
        if stored_value:
            rows.append(CoverFieldRow(text, stored_value, "asked", "custom"))
        elif cover_label_kept(text, stated_values):
            rows.append(CoverFieldRow(text, "", "asked", "custom"))

    if spec.get("name") != "required":
        rows = [
            row
            for row in rows
            if row.key != "name" and not _looks_like_name_line(print_cover_row(row), pack)
        ]

    if not essay:
        if seen.get("lock") == "entries" or seen.get("format") == "reflective diary":
            if sequence_number(essay_id) is not None:
                sequence_label = essay_id
            else:
                sequence_label = str(module_id_from_brief(brief) or module_code(essay_id) or "")
            if sequence_label and not _row_present(rows, sequence_label):
                rows.append(CoverFieldRow("", sequence_label, "house", "sequence_id"))
        return rows

    record = read_assignment(essay_id)
    if record.get("active") is True and record.get("mapped") is False:
        return rows
    lock = record.get("lock")

    if lock in {None, "thesis", "purpose_and_scope"}:
        if sequence_number(essay_id) is not None:
            sequence_label = essay_id
        else:
            sequence_label = str(module_id_from_brief(brief) or module_code(essay_id) or "")
        if sequence_label and not _row_present(rows, sequence_label):
            rows.append(CoverFieldRow("", sequence_label, "house", "sequence_id"))
        if (
            isinstance(assignment, str)
            and assignment.strip()
            and not _row_present(rows, assignment.strip())
        ):
            rows.append(CoverFieldRow("", assignment.strip(), "house", "assignment_title"))
        if lock in {None, "purpose_and_scope"} and not any(
            row.key == "word_count" for row in rows
        ):
            rows.append(CoverFieldRow("Counted words", counted_str, "house", "word_count"))

    stated = report.get("word_count", {}).get("stated")
    if isinstance(stated, int) and not any(row.key == "stated_word_count" for row in rows):
        rows.append(CoverFieldRow("Stated word count", str(stated), "house", "stated_word_count"))

    conclusion = pack.get("conclusion")
    if conclusion == "noted" and not any(row.key == "conclusion_noted" for row in rows):
        rows.append(CoverFieldRow("", "", "house", "conclusion_noted"))
    elif conclusion == "open" and not any(row.key == "conclusion_open" for row in rows):
        rows.append(CoverFieldRow("", "", "house", "conclusion_open"))

    return rows


def cover_lines_from_field_rows(
    essay_id: str,
    pack: dict[str, Any],
    rows: list[CoverFieldRow],
) -> list[str]:
    """Print cover rows. Registration is ordered before counted words when stored."""
    from essay_writer.assignment_gate import assignment_requirements

    seen = assignment_requirements(essay_id)
    stored = seen.get("title_page")

    brief = essay_textutil.module_brief_text(essay_id)
    spec = stored if isinstance(stored, dict) and stored.get("fields") else title_page_spec(brief)
    lines = [print_cover_row(row) for row in rows]
    lines = [line for line in lines if line]
    if spec.get("name") != "required":
        lines = [line for line in lines if not _looks_like_name_line(line, pack)]
    return with_registration_line(lines, spec, pack)


def ensure_house_cover_lines(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    lines: list[str],
) -> list[str]:
    """Module or sequence id, assignment title, and report word count when the brief stayed silent."""
    from essay_writer.assignment_gate import read_assignment

    record = read_assignment(essay_id)
    if record.get("active") is True and record.get("mapped") is False:
        return lines
    lock = record.get("lock")
    if lock not in {None, "thesis", "purpose_and_scope"}:
        return lines
    brief = essay_textutil.module_brief_text(essay_id)
    if sequence_number(essay_id) is not None:
        code = essay_id
    else:
        code = module_id_from_brief(brief) or module_code(essay_id)
    assignment = assignment_on_cover(pack, report, brief)
    counted = report.get("word_count", {}).get("counted")
    out = list(lines)
    if code and not _cover_line_present(out, str(code)):
        out.append(str(code))
    if isinstance(assignment, str) and assignment.strip() and not _cover_line_present(out, assignment):
        out.append(assignment.strip())
    if lock in {None, "purpose_and_scope"} and not any(item.startswith("Counted words:") for item in out):
        if isinstance(counted, int):
            out.append(f"Counted words: {counted}")
        else:
            out.append("Counted words:")
    return out


def registration_cover_line(spec: dict[str, Any], pack: dict[str, Any]) -> str | None:
    """The registration line when the brief asks and a number is already stored."""
    if not spec.get("registration"):
        return None
    number = pack.get("registration_number") or pack.get("student_number")
    if number in (None, "", False):
        return None
    return f"Registration number: {number}"


def with_registration_line(
    lines: list[str],
    spec: dict[str, Any],
    pack: dict[str, Any],
) -> list[str]:
    """Put the stored registration on the one cover, before the counted words."""
    line = registration_cover_line(spec, pack)
    if line is None:
        return lines
    if any(item.startswith("Registration number:") for item in lines):
        return lines
    for index, item in enumerate(lines):
        if item.startswith("Counted words:"):
            return lines[:index] + [line] + lines[index:]
    return lines + [line]


def layout_spec(text: str) -> dict[str, Any]:
    """Page layout the brief states, for every writing type. Silence leaves the app measurement."""
    spec: dict[str, Any] = {}
    if not isinstance(text, str) or not text.strip():
        return spec
    margin = _MARGIN.search(text)
    if margin:
        spec["margin_cm"] = float(margin.group(1))
    if _PAGE_RIGHT.search(text):
        spec["page_number"] = "right"
    if _SIZE.search(text) and not _HEADING_LARGER.search(text):
        spec["body_pt"] = 12
        spec["heading_pt"] = 12
    if _JUSTIFY.search(text):
        spec["justify"] = True
    return spec


def layout_for(essay_id: str) -> dict[str, Any]:
    """Page layout on the assignment record. The brief is read once into that record."""
    from essay_writer.assignment_gate import read_assignment

    stored = read_assignment(essay_id).get("page_layout")
    if isinstance(stored, dict):
        return dict(stored)
    return layout_spec(essay_textutil.module_brief_text(essay_id))


def title_page_cover_lines(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    *,
    always_programme: bool = False,
) -> list[str]:
    """Title-page lines the brief asks for. A missing value stays a blank label."""
    rows = cover_field_rows(essay_id, pack, report, essay=always_programme)
    return cover_lines_from_field_rows(essay_id, pack, rows)


def diary_cover_lines(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
) -> list[str]:
    """Diary cover: brief-asked fields, plus the sequence id. Programme prints when the brief asks."""
    rows = cover_field_rows(essay_id, pack, report, essay=False)
    return cover_lines_from_field_rows(essay_id, pack, rows)


def _present_text(value: object) -> str:
    """Stored cover text. Whitespace is empty and is not a registration number."""
    if value in (None, "", False):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def missing_cover_fields(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
) -> list[str]:
    """Required cover fields with no stored value. Custom labels use title_page_fields."""
    from essay_writer.assignment_gate import assignment_requirements

    record = assignment_requirements(essay_id)
    if record.get("mapped") is False:
        return []
    spec = record.get("title_page")
    if not isinstance(spec, dict):
        return []
    brief = essay_textutil.module_brief_text(essay_id)
    missing: list[str] = []
    number = _present_text(pack.get("registration_number")) or _present_text(
        pack.get("student_number")
    )
    if spec.get("registration") and not number:
        missing.append("registration number")
    student = pack.get("student_name")
    if spec.get("name") == "required" and not (isinstance(student, str) and student.strip()):
        missing.append("name")
    module_title = pack.get("module_title")
    if not isinstance(module_title, str) or not module_title.strip():
        found = _MODULE_TITLE.search(brief)
        module_title = found.group(1).strip() if found else ""
    assignment = assignment_on_cover(pack, report, brief)
    code = module_id_from_brief(brief) or module_code(essay_id)
    counted = report.get("word_count", {}).get("counted")
    fields = list(spec.get("fields") or [])
    if "module_title" in fields and not (isinstance(module_title, str) and module_title.strip()):
        missing.append("module title")
    if "module_code" in fields and not code:
        missing.append("module code")
    if "assignment_title" in fields and not (isinstance(assignment, str) and assignment.strip()):
        missing.append("assignment title")
    if "word_count" in fields and not isinstance(counted, int):
        missing.append("word count")
    for label in spec.get("labels") or []:
        if not isinstance(label, str):
            continue
        text = label.strip().rstrip(":").strip()
        if not text or not cover_label_kept(text, _stated_cover_values(brief)):
            continue
        if custom_cover_value(text, pack):
            continue
        missing.append(text.lower())
    return missing


def _looks_like_name_line(line: str, pack: dict[str, Any]) -> bool:
    student = pack.get("student_name")
    if isinstance(student, str) and student.strip() and student.strip() in line:
        return True
    return False


def blocked_identity_keys(essay_id: str, pack: dict[str, Any]) -> list[str]:
    """Student fields the file must not carry.

    The title page on the assignment record decides. A registration number
    is allowed when the brief asks, and a name only when the brief asks.
    An unmapped writing type blocks every student field.
    """
    from essay_writer.assignment_gate import read_assignment
    from essay_writer.programme import STUDENT_KEYS

    record = read_assignment(essay_id)
    stored = record.get("title_page")
    spec = stored if record.get("mapped") is not False and isinstance(stored, dict) else None
    blocked: list[str] = []
    keys = set(STUDENT_KEYS) | {"registration_number"}
    for key in keys:
        if key not in pack or pack.get(key) in (None, "", False):
            continue
        if spec is None:
            blocked.append(key)
            continue
        if key in NAME_KEYS:
            if spec.get("name") != "required":
                blocked.append(key)
            continue
        if key in NUMBER_KEYS:
            if not spec.get("registration"):
                blocked.append(key)
            continue
        blocked.append(key)
    return blocked
