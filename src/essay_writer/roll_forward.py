"""Parent to child roll-forward.

A copied sequence starts open on stage 1. The writing pointer and the
stage notes are not inherited, open parent or closed. Research and the
papers already on disk stay. The previous final Word file is parked
under reference/. Stage 4a researches first, then each saved paper is
kept, dropped, or replaced. A drop removes the list row only. The PDF
stays in uploads and on the Mac. Stage 4b is skipped only when every
keeper already has a critical note. A keeper is not dug again and is
not put back on the leftovers list. Cursor and Grok Build both use
these functions through essay.sequence.new and essay.stage.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from essay_writer.confirm import refuse
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import sequence_write_error, work_dir, workspace_root

RECORD = "roll-forward.json"
REFERENCE = "reference"
_CHOICES = frozenset({"keep", "drop", "replace"})
_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return _SLUG.sub("-", value.casefold()).strip("-")


def _record_path(folder: Path) -> Path:
    return folder / RECORD


def _read_record(folder: Path) -> dict[str, Any] | None:
    path = _record_path(folder)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    papers = data.get("papers")
    if papers is not None and not isinstance(papers, list):
        return None
    if papers is None and not data.get("inherited_locks"):
        return None
    return data


def load_record(essay_id: str) -> dict[str, Any] | None:

    return _read_record(work_dir(essay_id))


def _write_record(folder: Path, record: dict[str, Any]) -> None:

    path = _record_path(folder)
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def save_record(essay_id: str, record: dict[str, Any]) -> None:

    _write_record(work_dir(essay_id), record)


def _paper_id(row: dict[str, Any]) -> str:
    for key in ("doi", "url", "path", "title"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _clean_paper(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    paper: dict[str, Any] = {}
    for key in ("doi", "title", "url", "path"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            paper[key] = value.strip()
    ident = _paper_id(paper)
    if not ident:
        return None
    paper["id"] = ident
    paper["choice"] = None
    return paper


def _papers_on_folder(folder: Path) -> list[dict[str, Any]]:
    path = folder / "download-run.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in data.get("papers") or []:
        paper = _clean_paper(raw if isinstance(raw, dict) else {})
        if paper is None or paper["id"] in seen:
            continue
        seen.add(paper["id"])
        found.append(paper)
    return found


def _park_finals(folder: Path) -> list[str]:
    """Move the copied stage-10 final under reference/. The sequence Word file stays.

    annotation.docx and the working sequence file are not the old final.
    Research files stay in output/.
    """
    output = folder / "output"
    if not output.is_dir():
        return []

    reference = folder / REFERENCE
    parked: list[str] = []
    for path in sorted(output.glob("*-10/*-final.docx")):
        if not path.is_file():
            continue
        reference.mkdir(parents=True, exist_ok=True)
        dest = reference / path.name
        refuse_repo_write(dest)
        if dest.exists():
            dest = reference / f"{path.stem}-earlier{path.suffix}"
        os.replace(path, dest)
        parked.append(dest.name)
    return parked


def _drop_parent_mac_record(folder: Path) -> None:
    """The parent's computer paths name that sequence's copies, not the child's."""
    from essay_writer.first_run import MAC_DELIVERABLES_NAME

    path = folder / MAC_DELIVERABLES_NAME
    if path.is_symlink() or path.is_file():
        path.unlink()


def shape_cloned_child(folder: Path, essay_id: str) -> None:
    """Park the old final and remember papers already on the copied sequence.

    Research in state.json is left as copied. PDFs are not moved. The
    marking table and the brief are outside this folder and are not written.
    The parent's record of Word and zip paths on the computer is not kept.
    """
    _park_finals(folder)
    _drop_parent_mac_record(folder)
    papers = _papers_on_folder(folder)
    if not papers:
        return
    record = _read_record(folder) or {}
    record["essay_id"] = essay_id
    record["papers"] = papers
    _write_record(folder, record)


def _same(left: dict[str, Any], right: dict[str, Any]) -> bool:
    from essay_writer.research_packs import same_source

    return same_source(_as_source(left), _as_source(right))


def _as_source(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    if not isinstance(item.get("url"), str):
        oa = item.get("oa_url")
        if isinstance(oa, str) and oa.strip():
            item["url"] = oa.strip()
    return item


def _match_paper(papers: list[dict[str, Any]], which: object) -> dict[str, Any] | None:
    if not isinstance(which, str) or not which.strip():
        return None
    probe = {"id": which.strip(), "doi": which.strip(), "url": which.strip(), "title": which.strip(), "path": which.strip()}
    for paper in papers:
        if paper.get("id") == which.strip() or _same(paper, probe):
            return paper
    return None


def public_papers(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(record, dict):
        return []
    shown: list[dict[str, Any]] = []
    for paper in record.get("papers") or []:
        if not isinstance(paper, dict):
            continue
        row = {
            "id": paper.get("id"),
            "choice": paper.get("choice"),
            "reuse_ok": True,
        }
        for key in ("doi", "title", "url", "path"):
            if isinstance(paper.get(key), str):
                row[key] = paper[key]
        shown.append(row)
    return shown


def pending_choice_reason(essay_id: str) -> str | None:
    """Stage 4a cannot be saved until each inherited paper has a choice."""
    record = load_record(essay_id)
    if record is None:
        return None
    papers = [item for item in record.get("papers") or [] if isinstance(item, dict)]
    if not papers:
        return None
    if any(item.get("choice") not in _CHOICES for item in papers):
        return (
            "Choose keep, drop, or replace for each saved paper before this step is saved. "
            "Research runs first. A kept paper can be reused."
        )
    return None


def attach_stage_roll(body: dict[str, Any], essay_id: str, stage: str) -> None:
    """Name the 4a order on a sequence that inherited papers."""
    record = load_record(essay_id)
    if record is None or stage != "4a":
        return
    papers = public_papers(record)
    if not papers:
        return
    body["roll_forward"] = {
        "research_first": True,
        "order": ["research", "keep-drop-replace"],
        "reuse_ok": True,
        "papers": papers,
    }


def _unlist(essay_id: str, paper: dict[str, Any]) -> None:
    """Take the paper off the download list. Do not delete the file."""
    from essay_writer.downloads import _load_state, _save_state

    state = _load_state(essay_id)
    state["papers"] = [
        item
        for item in state.get("papers") or []
        if isinstance(item, dict) and not _same(item, paper)
    ]
    _save_state(essay_id, state)


def _file_still_there(paper: dict[str, Any]) -> bool:
    raw = paper.get("path")
    if not isinstance(raw, str) or not raw.strip():
        return False

    path = workspace_root() / raw.strip()
    return path.is_file()


def choose_paper(essay_id: str, choice: object) -> dict[str, Any]:
    """Record keep, drop, or replace. Drop unlists. The PDF stays."""

    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    if not isinstance(choice, dict):
        return refuse("papers", "Name the paper and whether to keep, drop, or replace it.")
    decision = choice.get("choice")
    if decision not in _CHOICES:
        return refuse("papers", "choice must be keep, drop, or replace.")
    which = choice.get("paper") or choice.get("id") or choice.get("doi") or choice.get("url")
    record = load_record(essay_id)
    if record is None:
        return refuse("papers", "This sequence has no saved papers to keep, drop, or replace.")
    papers = [item for item in record.get("papers") or [] if isinstance(item, dict)]
    paper = _match_paper(papers, which)
    if paper is None:
        return refuse("papers", "That paper is not on this sequence.")
    before = {key: paper.get(key) for key in ("doi", "title", "url", "path")}
    paper["choice"] = decision
    if decision in {"drop", "replace"}:
        _unlist(essay_id, paper)
    for key, value in before.items():
        if value is None:
            paper.pop(key, None)
        else:
            paper[key] = value
    record["papers"] = papers
    save_record(essay_id, record)
    return {
        "ok": True,
        "essay_id": essay_id,
        "choice": decision,
        "unlisted": decision != "keep",
        "file_kept": _file_still_there(paper) or decision == "keep",
        "paper": {
            "id": paper.get("id"),
            "doi": paper.get("doi"),
            "title": paper.get("title"),
            "url": paper.get("url"),
            "path": paper.get("path"),
            "choice": decision,
        },
        "papers": public_papers(record),
    }


def keepers(essay_id: str) -> list[dict[str, Any]]:
    record = load_record(essay_id)
    if record is None:
        return []
    return [
        item
        for item in record.get("papers") or []
        if isinstance(item, dict) and item.get("choice") == "keep"
    ]


def has_critical_note(essay_id: str, paper: dict[str, Any]) -> bool:
    """True when a review markdown already names this paper and is a critical note."""

    folder = work_dir(essay_id) / "output" / "reviews"
    if not folder.is_dir():
        return False
    tokens: list[str] = []
    for key in ("id", "doi", "title", "url"):
        value = paper.get(key)
        if isinstance(value, str) and value.strip():
            tokens.append(value.strip())
    slugs = [_slug(token) for token in tokens if len(_slug(token)) >= 6]
    for path in folder.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "Critical note" not in text:
            continue
        hay = text.casefold()
        name = _slug(path.stem)
        if any(token.casefold() in hay for token in tokens if len(token) >= 6):
            return True
        if any(slug and (slug == name or slug in name) for slug in slugs):
            return True
    return False


def four_b_action(essay_id: str) -> str | None:
    """skip only when every keeper already has a critical note.

    A keeper or a replacement without a note still runs 4b research.
    A sequence with no inherited papers is unchanged.
    """
    record = load_record(essay_id)
    if record is None:
        return None
    papers = [item for item in record.get("papers") or [] if isinstance(item, dict)]
    if not papers:
        return None
    if any(item.get("choice") not in _CHOICES for item in papers):
        return "research"
    kept = [item for item in papers if item.get("choice") == "keep"]
    replaced = [item for item in papers if item.get("choice") == "replace"]
    if not kept or replaced:
        return "research"
    if all(has_critical_note(essay_id, item) for item in kept):
        return "skip"
    return "research"


def without_keepers(essay_id: str, rows: list[Any] | None) -> list[Any]:
    """Drop leftover rows that name a kept paper. Other rows stay."""
    if not isinstance(rows, list):
        return []
    kept = keepers(essay_id)
    if not kept:
        return list(rows)
    found: list[Any] = []
    for row in rows:
        if isinstance(row, dict) and any(_same(row, paper) for paper in kept):
            continue
        found.append(row)
    return found


def omit_keepers_from_card(essay_id: str, card: dict[str, Any]) -> dict[str, Any]:
    """A kept paper is not dug again. Its recorded doi, title, and url stay."""
    kept = keepers(essay_id)
    if not kept:
        return card

    def held(row: dict[str, Any]) -> bool:
        return any(_same(row, paper) for paper in kept)

    for bucket in ("openalex", "consensus"):
        block = card.get(bucket)
        if isinstance(block, dict) and isinstance(block.get("hits"), list):
            block["hits"] = [hit for hit in block["hits"] if not (isinstance(hit, dict) and held(hit))]
    unpaywall = card.get("unpaywall")
    if isinstance(unpaywall, list):
        card["unpaywall"] = [
            row for row in unpaywall if not (isinstance(row, dict) and held(row))
        ]
    return card
