"""A student outline or base prose is the structure for stages 3 to 6.

When the student puts an outline or their own prose on the sequence, that is
the plan. Stages 3 to 6 keep its headings and their order, weave a short
claim-fit cite where a gathered paper supports a line, and do not build new
sections around whatever was gathered. A draft with no student outline keeps
the earlier path.

The outline is read, never written. A heading the student did not name is not
invented, and a section that the outline does not name is reported rather than
dropped in silence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer.paths import work_dir

FOLDER = "student-outline"
SUFFIXES = frozenset({".md", ".txt"})
_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+")
_ATX = re.compile(r"^\s{0,3}#{1,6}\s+(?P<name>.+?)\s*#*\s*$")
_NUMBERED = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+(?P<name>[A-Z][^.!?]{0,59})$")
_HEADING_MAX_WORDS = 10
SHORT_CITE_LIMIT = 2


def outline_dir(essay_id: str) -> Path:

    return work_dir(essay_id) / FOLDER


def outline_paths(essay_id: str) -> list[Path]:
    """Files the student put there, in name order. A link is not a student file."""

    found: list[Path] = []
    folder = outline_dir(essay_id)
    if folder.is_dir():
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.is_symlink() and path.suffix.casefold() in SUFFIXES:
                found.append(path)
    for name in ("student-outline.md", "student-outline.txt"):
        path = work_dir(essay_id) / name
        if path.is_file() and not path.is_symlink():
            found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _heading_name(line: str) -> str | None:
    atx = _ATX.match(line)
    if atx is not None:
        name = atx.group("name").strip()
        return name or None
    numbered = _NUMBERED.match(line)
    if numbered is None:
        return None
    name = numbered.group("name").strip().rstrip(":").strip()
    if not name or len(name.split()) > _HEADING_MAX_WORDS:
        return None
    return name


def read_outline(essay_id: str) -> dict[str, Any] | None:
    """Headings and prose the student supplied, or None when there is none."""
    paths = outline_paths(essay_id)
    if not paths:
        return None
    headings: list[str] = []
    prose: list[str] = []
    seen: set[str] = set()
    used: list[str] = []
    for path in paths:
        text = _read(path)
        if not text.strip():
            continue
        used.append(path.name)
        for line in text.split("\n"):
            name = _heading_name(line)
            if name is not None:
                key = _fold(name)
                if key and key not in seen:
                    seen.add(key)
                    headings.append(name)
                continue
            if line.strip():
                prose.append(line.strip())
    if not headings and not prose:
        return None
    return {
        "files": used,
        "headings": headings,
        "prose": " ".join(prose),
        "words": len(" ".join(prose).split()),
    }


def _fold(name: str) -> str:
    text = _NUMBER.sub("", str(name or "").strip()).casefold()
    return " ".join(text.split()).strip(" .:—-")


def outline_primary(essay_id: str) -> bool:
    """True when the student supplied an outline or base prose on this sequence."""
    outline = read_outline(essay_id)
    return bool(outline and (outline["headings"] or outline["words"] >= 1))


def outline_names_sections(essay_id: str) -> bool:
    """True when the student's outline names headings.

    Base prose alone is the student's own writing, so the pipeline does not
    shorten a cited stretch inside it. Named headings mean the writer builds
    the prose, and those woven cites stay short.
    """
    outline = read_outline(essay_id)
    return bool(outline and outline["headings"])


def pin_structure(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Put the student's headings first, in the student's order.

    A section the outline does not name keeps its place after them and is
    reported. Nothing is dropped and no heading is invented.
    """
    outline = read_outline(essay_id)
    if not isinstance(pack, dict) or outline is None or not outline["headings"]:
        return {
            "pack": pack,
            "applied": False,
            "outline": outline,
            "off_outline": [],
            "used": [],
        }
    sections: list[Any] = list(pack.get("sections") or [])
    rows = [section for section in sections if isinstance(section, dict)]
    by_heading: dict[str, dict[str, Any]] = {}
    for section in rows:
        key = _fold(str(section.get("heading") or ""))
        if key and key not in by_heading:
            by_heading[key] = section
    ordered: list[Any] = []
    used: list[str] = []
    taken: set[int] = set()
    for name in outline["headings"]:
        key = _fold(name)
        found = by_heading.get(key)
        if found is None:
            continue
        ordered.append(found)
        used.append(str(found.get("heading") or name))
        taken.add(id(found))
    off_outline: list[str] = []
    for section in sections:
        if isinstance(section, dict) and id(section) in taken:
            continue
        ordered.append(section)
        if isinstance(section, dict):
            off_outline.append(str(section.get("heading") or ""))
    pinned = dict(pack)
    pinned["sections"] = ordered
    return {
        "pack": pinned,
        "applied": True,
        "outline": outline,
        "off_outline": off_outline,
        "used": used,
    }


def apply_outline_primary(
    essay_id: str, pack: dict[str, Any], *, limit: int = SHORT_CITE_LIMIT
) -> dict[str, Any]:
    """Keep the student's structure and keep every woven cite short.

    ``applied`` is true when a student outline or base prose is on the
    sequence, which is what stops the writer lifting sections and stretching
    the body from gathered files.
    """
    pinned = pin_structure(essay_id, pack)
    outline = pinned["outline"]
    if not isinstance(pinned["pack"], dict) or not isinstance(outline, dict):
        return {**pinned, "applied": False, "woven": 0, "shortened": []}
    from essay_writer.short_cites import shorten_sections

    sections = pinned["pack"].get("sections")
    shortened: list[str] = []
    if isinstance(sections, list) and outline.get("headings"):
        cleaned, shortened = shorten_sections(sections, limit)
        if shortened:
            body = dict(pinned["pack"])
            body["sections"] = cleaned
            pinned = {**pinned, "pack": body}
    return {
        **pinned,
        "applied": True,
        "woven": len(shortened),
        "shortened": shortened,
    }


def weave_short_cites(
    essay_id: str, text: str, limit: int = SHORT_CITE_LIMIT
) -> tuple[str, list[str]]:
    """Cut long cited stretches in a stage draft, on a student outline.

    Only an outline that names headings reaches here: base prose alone is the
    student's own writing and is not cut. The returned list is what was cut.
    """
    if not outline_primary(essay_id) or not outline_names_sections(essay_id):
        return text, []
    from essay_writer.short_cites import shorten

    short, report = shorten(text, limit)
    return short, list(report["cut"])


def outline_speech(essay_id: str) -> str | None:
    """One line for the stage reply. Empty when the student supplied no outline."""
    outline = read_outline(essay_id)
    if outline is None:
        return None
    headings = outline.get("headings") or []
    if headings:
        names = ", ".join(str(name) for name in headings[:6])
        tail = "" if len(headings) <= 6 else f", and {len(headings) - 6} more"
        return (
            f"Your outline is the plan: {names}{tail}. "
            "These headings and this order stay, and each cited point stays short."
        )
    return (
        "Your own prose is the base for these stages. Its order stays, "
        "and each cited point stays short."
    )
