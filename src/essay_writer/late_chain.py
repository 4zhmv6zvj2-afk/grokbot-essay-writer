"""After stage 7 ask and edit, stages 8, 9, and 10 are separate runs.

One call does not run the later stages. A blocked independent review is
shown. Stage 10 writes the sequence Word file, refreshes that sequence's
-10 final from those bytes, and writes the Mac handoff folder when one is
configured. Documents/<project>-10/ is the fallback when Documents is mounted
and no handoff folder is configured.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer import textutil as essay_textutil
from essay_writer.diary import (
    _cover_stored_title,
    _real_title,
    _stated_cover_values,
    assignment_on_cover,
    cover_residue_line,
)
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import module_code, work_dir, workspace_root
from essay_writer.prompt_loader import text as prompt_text
from essay_writer.stage7 import comment_text, load_stage7
from essay_writer.state import load_state
from essay_writer.student_voice import say
from essay_writer.user_place import master_word

_LATE = frozenset({"7", "8", "9", "10"})


def documents_root(override: Path | None = None) -> Path | None:
    """Documents when this computer can see it. Tests pass the folder.

    ESSAY_WRITER_ROOT stays the isolation switch for a test ledger; this
    function does not key on the test runner itself.
    """
    import os
    import sys

    if override is not None:
        return override
    env = os.environ.get("ESSAY_WRITER_MAC_DIR")
    if env is not None:
        text = env.strip()
        if not text or text.casefold() == "open":
            return None
        return Path(text).expanduser()
    if os.environ.get("ESSAY_WRITER_ROOT"):
        return None
    if sys.platform != "darwin":
        return None
    folder = Path.home() / "Documents"
    if folder.is_dir():
        return folder
    return None


def final_place(essay_id: str) -> str:
    from essay_writer.first_run import (
        sequence_mac_deliverables_dir,
        sequence_mac_handoff_place,
    )

    project = module_code(essay_id)
    if sequence_mac_deliverables_dir(essay_id) is not None:
        return sequence_mac_handoff_place(essay_id, f"{project}-final.docx")
    return f"Documents/{project}-10/{project}-final.docx"


def comments_place(essay_id: str) -> str:
    from essay_writer.first_run import (
        sequence_mac_deliverables_dir,
        sequence_mac_handoff_place,
    )

    project = module_code(essay_id)
    if sequence_mac_deliverables_dir(essay_id) is not None:
        return sequence_mac_handoff_place(essay_id, f"{project}-comments.docx")
    return f"Documents/{project}-10/{project}-comments.docx"


def _chat_path_under_root(root: Path, tail: str) -> str:
    """Student path for a file under the mounted root. No invented Documents path."""
    parts = root.expanduser().parts
    folded = [part.casefold() for part in parts]
    if "documents" in folded:
        index = max(i for i, name in enumerate(folded) if name == "documents")
        head = "/".join(parts[index:])
        return f"{head}/{tail}"
    from essay_writer.paths import student_chat_path

    return student_chat_path((root / tail).as_posix())


def findings_place(essay_id: str, *, documents: Path | None = None) -> str:
    """Independent-review findings. The project folder, not the stage 10 folder.

    The chat names the folder the write uses. An unmounted root does not
    invent a Documents path.
    """
    project = module_code(essay_id)
    tail = f"{project}/{project}-findings.docx"
    root = documents_root(documents)
    if root is None:
        return ""
    return _chat_path_under_root(root, tail)


def next_run(essay_id: str, stage: str, *, armed: bool) -> dict[str, Any] | None:
    """The single following run. Never 8, 9, and 10 together."""
    if not armed or stage == "6":
        return None
    if stage == "7":
        return {"stage": "8", "run": "edit", "separate": True, "runs_in_this_step": 1}
    if stage == "8":
        return {"stage": "9", "run": "references", "separate": True, "runs_in_this_step": 1}
    if stage == "9":
        from essay_writer.spine import final_review

        text, verdict = final_review(essay_id)
        if text:
            return {
                "stage": "9",
                "run": "review",
                "separate": True,
                "runs_in_this_step": 1,
                "blocked": True,
                "eqr": verdict,
            }
        return {
            "stage": "10",
            "run": "final",
            "separate": True,
            "runs_in_this_step": 1,
            "eqr": verdict,
        }
    return None


MISSING_FINAL_WORD = "The final Word file is missing."
FINDINGS_UNMOUNTED = (
    "The review opened the saved Word file. "
    "The Mac folder is not on this computer, so the findings stay in this chat and on this sequence."
)
QUIET_STEP = "Wait while the first draft is written."
FIRST_DRAFT_READY = "Read the first draft in this chat."
STAGE6_OPEN = "Your draft is saved. Start the first read in this chat."
STAGE6_READ_LIST = prompt_text("front_office/chat.md", "stage6_read_list")
_LEAKS = (
    "Essay-writer/",
    "uploads/",
    "tracking/",
    "sequences/",
    "~/",
    "/Users/",
    "/Volumes/",
    "ResearchDrive",
    "BackupDrive",
    "Backup-Drive",
    "ArchiveDrive",
    "Archive-Drive",
    "Apply every line",
)


def quiet_next(stage: str, *, armed: bool, blocked: bool, place: str) -> str | None:
    from essay_writer.stage_next import quiet_stage_line

    return quiet_stage_line(stage, armed=armed, blocked=blocked, place=place)


def chat_leaks(text: str) -> bool:
    """Checklist dump or a file path in the line a person would hear."""
    return any(token in text for token in _LEAKS)


def completed_draft_chat(prose: str) -> str:
    """The finished first draft, or a short ready line when the prose would leak."""

    spoken = say(prose).strip() if prose else ""
    if not spoken or chat_leaks(spoken):
        return FIRST_DRAFT_READY
    return spoken


def draft_prose(pack: dict[str, Any] | None) -> str:
    if not isinstance(pack, dict):
        return ""
    sections = pack.get("sections")
    if not isinstance(sections, list):
        return ""
    parts: list[str] = []
    for section in sections:
        if isinstance(section, dict) and isinstance(section.get("body"), str):
            text = section["body"].strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def mark_quiet(
    body: dict[str, Any], chat: str, *, step: str, speak_next: bool = True
) -> dict[str, Any]:
    body["quiet"] = True
    body["step"] = step
    body["checklist_in_chat"] = False
    body["chat"] = chat
    if speak_next:
        body["next"] = chat
    body["confirm_line"] = chat
    body.pop("tracking_path", None)
    return body


def stage5_chat_line(text: str, fallback: str) -> str:
    """Stage 5 chat. A Basics checklist dump is not the line a person hears."""
    if not isinstance(text, str) or not text.strip():
        return fallback
    if chat_leaks(text) or "Basics checklist" in text or "Apply every line" in text:
        return fallback
    return text.strip()


def _stage5_shown_line(essay_id: str, line: str) -> tuple[str, int | None]:
    """Ready line for a draft inside the band. A short draft is not announced as finished."""
    from essay_writer.specialists.writer import draft_word_count, first_draft_below_minimum
    from essay_writer.stage_note import _note_look

    saved = _note_look(essay_id, "5")
    if not isinstance(saved, str) or not saved.strip():
        return line, None
    blocked = first_draft_below_minimum(essay_id, saved)
    if blocked is not None:
        reason = str(blocked.get("reason") or line)
        counted = blocked.get("counted")
        return reason, counted if isinstance(counted, int) else None
    counted = draft_word_count(essay_id, saved)
    if counted is None:
        return line, None
    return f"{line} Counted words: {counted}.", counted


def quiet_stage5(body: dict[str, Any], essay_id: str) -> dict[str, Any]:
    """Stage 5 speech. No save prompt. The finished draft is heard after Word exists."""

    word = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    if body.get("stored") and word.is_file():
        line = stage5_chat_line(FIRST_DRAFT_READY, FIRST_DRAFT_READY)
    else:
        line = stage5_chat_line(STAGE6_OPEN, STAGE6_OPEN)
    line, counted = _stage5_shown_line(essay_id, line)
    if isinstance(counted, int):
        body["counted_words"] = counted
    quiet = mark_quiet(body, line, step="5", speak_next=False)
    from essay_writer.stage_next import write_stage_next

    write_stage_next(quiet, line)
    quiet["checklist_in_chat"] = False
    from essay_writer.student_turns import STAGE6_LEAD_IN

    quiet["read_lead"] = say(STAGE6_LEAD_IN)
    quiet["read_list"] = say(STAGE6_READ_LIST)
    from essay_writer.cite_fit import speak_cite_ask

    return speak_cite_ask(quiet)


def quiet_word_step(body: dict[str, Any], pack: dict[str, Any] | None) -> dict[str, Any]:
    """Word preview is the quiet middle pass. Confirm shows the finished draft."""
    blocked = body.get("ok") is False or bool(body.get("blockers")) or bool(body.get("refused"))
    if blocked:
        body["quiet"] = False
        body["step"] = "5b"
        body["checklist_in_chat"] = False
        return body
    if body.get("wrote"):
        prose = draft_prose(pack)
        essay_id = body.get("essay_id")
        if isinstance(essay_id, str) and essay_id.strip():
            from essay_writer.specialists.writer import first_draft_below_minimum

            short = first_draft_below_minimum(essay_id, prose)
            if short is not None:
                reason = str(short.get("reason") or "")
                return mark_quiet(body, reason, step="5b")
        return mark_quiet(body, completed_draft_chat(prose), step="5b")
    kept = body.get("next")
    if isinstance(kept, str) and "Say yes to keep this step." in kept:
        return mark_quiet(body, kept, step="5b")
    return mark_quiet(body, QUIET_STEP, step="5b")


def log_word_manifest(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    *,
    pack_path: str,
    product_log: bool = True,
) -> None:
    if not product_log:
        return
    from essay_writer.debug_log import (
        log_word_step,
        pack_log_assessment,
        pack_log_title,
    )

    cover = report.get("cover") if isinstance(report.get("cover"), list) else []
    log_word_step(
        "word_manifest",
        essay_id,
        pack_path=pack_path,
        title=pack_log_title(pack),
        assessment=pack_log_assessment(pack),
        conclusion=str(pack.get("conclusion") or ""),
        cover=cover,
        sources_count=len(report.get("sources") or []),
        refs_count=len(report.get("references") or []),
    )


def log_word_docx_written(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    cover: list[str],
    path: Path,
    *,
    product_log: bool = True,
) -> None:
    if not product_log:
        return
    from essay_writer.debug_log import (
        log_word_step,
        pack_log_assessment,
        pack_log_title,
    )

    log_word_step(
        "write_docx",
        essay_id,
        title=pack_log_title(pack),
        assessment=pack_log_assessment(pack),
        conclusion=str(pack.get("conclusion") or ""),
        cover=cover,
        sources_count=len(report.get("sources") or []),
        refs_count=len(report.get("references") or []),
        output_path=path,
    )


def _saved_pack(essay_id: str) -> dict[str, Any] | None:

    pack = load_state(essay_id).get("saved_pack")
    if isinstance(pack, dict):
        return pack
    return None


def _infer_source_origin(locator: str) -> str:
    lowered = locator.strip().casefold()
    if lowered.startswith("uploads/"):
        return "upload"
    if lowered.startswith("essay-writer/") or lowered.startswith("kb1/"):
        return "kb1"
    return "brief"


def _pack_sources(essay_id: str, pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Sources for Word: pack list, then the stored pack, then confirmed research."""

    raw = pack.get("sources")
    if isinstance(raw, list) and raw:
        return [item for item in raw if isinstance(item, dict)]
    if pack.get("recovered_from_docx") is True and isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    saved = load_state(essay_id).get("saved_pack")
    if isinstance(saved, dict):
        stored = saved.get("sources")
        if isinstance(stored, list) and stored:
            return [item for item in stored if isinstance(item, dict)]
    from essay_writer.research_packs import bibliography_sources

    rows: list[dict[str, Any]] = []
    for item in bibliography_sources(essay_id):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        locator = row.get("locator")
        if isinstance(locator, str) and locator.strip() and not row.get("origin"):
            row["origin"] = _infer_source_origin(locator)
        rows.append(row)
    return rows


def _word_pack(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Pack fields Word and inspect_pack need after a body-only recovery from .docx."""
    filled = dict(pack)
    sources = _pack_sources(essay_id, filled)
    if sources:
        filled["sources"] = sources

    assessment = filled.get("assessment")
    if not _cover_stored_title(assessment):
        title = _cover_stored_title(filled.get("title"))
        if title:
            filled["assessment"] = title
    if not filled.get("referencing"):
        filled["referencing"] = "harvard"
    return filled


_STACK_MARK = re.compile(r"(?i)^(?:registration number|counted words|stated word count)\s*:")


def _wrapped_draft(lines: list[str], cover: list[str]) -> bool:
    """True when a Draft section is an earlier Word file, not the essay."""
    known = {line.strip().casefold() for line in cover if line and line.strip()}
    for line in lines:
        folded = line.strip().casefold()
        if folded in {"draft", "references"} or folded in known:
            return True
        if _STACK_MARK.match(line.strip()):
            return True
    return False


def _split_named(lines: list[str], names: list[str]) -> list[dict[str, Any]] | None:
    """Split flattened paragraphs on the brief's part names, in that order."""
    lookup = {name.casefold(): name for name in names}
    present = {line.casefold() for line in lines}
    if any(name.casefold() not in present for name in names):
        return None
    buckets: dict[str, list[str]] = {name.casefold(): [] for name in names}
    current: str | None = None
    for line in lines:
        key = line.casefold()
        if key in lookup:
            current = key
            continue
        if current is None:
            continue
        buckets[current].append(line)
    return [{"heading": name, "lines": buckets[name.casefold()]} for name in names]


def _unwrap_draft(essay_id: str, lines: list[str], cover: list[str]) -> list[dict[str, Any]]:
    """Drop stacked covers and recover the essay sections inside a Draft wrap."""

    compared = list(cover)
    compared.extend(_stated_cover_values(essay_textutil.module_brief_text(essay_id)))
    kept = [line for line in lines if not cover_residue_line(line, compared)]
    record = essay_assignment_gate.read_assignment(essay_id)
    names: list[str] = []
    if record.get("lock") not in {None, "thesis", "purpose_and_scope"}:
        stored = record.get("named_entries")
        if isinstance(stored, list):
            names = [name.strip() for name in stored if isinstance(name, str) and name.strip()]
    if names:
        split = _split_named(kept, names)
        if split:
            return split
    if not kept:
        return []
    return [{"heading": kept[0], "lines": kept[1:]}]


_COUNTED_COVER = re.compile(r"(?i)^counted words:\s*(\d+)\s*$")
_REGISTRATION_COVER = re.compile(r"(?i)^registration number:\s*(.+)\s*$")
_REFERENCE_AUTHOR_YEAR = re.compile(r"^(.+?)\s*\((\d{4})")


def _programme_cover_lines() -> set[str]:
    from essay_writer.programme import PROGRAMME

    return {str(value).casefold() for value in PROGRAMME.values()}


def _hydrate_pack_from_docx_cover(
    essay_id: str, cover: list[str], pack: dict[str, Any]
) -> dict[str, Any]:
    """Carry cover values already printed on disk into the recovered pack."""

    programme = _programme_cover_lines()
    brief = essay_textutil.module_brief_text(essay_id)
    brief_assignment = assignment_on_cover({}, {}, brief)
    out = dict(pack)
    # The pack field is the conclusion. A cover sentence fills it only when
    # that field is empty, for a file written before the sentence left the cover.
    held = out.get("conclusion") if out.get("conclusion") in {"noted", "open"} else None
    seen_on_cover: str | None = None
    assignment_lines: list[str] = []
    for line in cover:
        text = line.strip()
        if not text:
            continue
        if text.casefold() in programme or text == essay_id:
            continue
        if text == "Conclusion: noted":
            seen_on_cover = "noted"
            continue
        if text == "Conclusion: open — not a settled finding":
            seen_on_cover = "open"
            continue
        match = _REGISTRATION_COVER.match(text)
        if match:
            out["registration_number"] = match.group(1).strip()
            continue
        if _COUNTED_COVER.match(text):
            continue
        if text.endswith(":") and not _real_title(text.rstrip(":")):
            continue
        if _real_title(text) and not cover_residue_line(text):
            assignment_lines.append(text)
    if assignment_lines and not _real_title(out.get("assessment")):
        chosen = None
        if isinstance(brief_assignment, str) and brief_assignment.strip():
            wanted = brief_assignment.strip()
            for line in assignment_lines:
                if line.strip() == wanted:
                    chosen = wanted
                    break
        if chosen is None:
            for line in assignment_lines:
                if not cover_residue_line(line):
                    chosen = line.strip()
                    break
        if chosen is None:
            chosen = assignment_lines[0].strip()
        out["assessment"] = chosen
        if not _real_title(out.get("title")):
            out["title"] = chosen
    if held:
        out["conclusion"] = held
    elif seen_on_cover:
        out["conclusion"] = seen_on_cover
    return out


def _paragraph_text_style(paragraph) -> tuple[str, str]:
    text = paragraph.text.strip()
    style = ""
    if paragraph.style is not None and getattr(paragraph.style, "name", None):
        style = paragraph.style.name
    return text, style


def _reference_lines_from_docx(document) -> list[str]:
    """Reference lines under the References heading, including table cells."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    lines: list[str] = []
    current = False

    def add(text: str) -> None:
        if text and (not lines or lines[-1] != text):
            lines.append(text)

    def consume(paragraph) -> bool:
        nonlocal current
        text, style = _paragraph_text_style(paragraph)
        heading = style.startswith("Heading")
        if heading and text.casefold() == "references":
            current = True
            return False
        if not current:
            return False
        if heading and text:
            return True
        add(text)
        return False

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            if consume(Paragraph(child, document)):
                break
            continue
        if child.tag != qn("w:tbl") or not current:
            continue
        table = Table(child, document)
        stop = False
        for row in table.rows:
            seen: set[int] = set()
            for cell in row.cells:
                ident = id(cell._tc)
                if ident in seen:
                    continue
                seen.add(ident)
                for paragraph in cell.paragraphs:
                    if consume(paragraph):
                        stop = True
                        break
                if stop:
                    break
            if stop:
                break
        if stop:
            break
    return lines


def _source_for_reference_line(essay_id: str, line: str) -> dict[str, Any] | None:
    """Match a printed Harvard line to a gathered upload. Nothing is invented."""
    from essay_writer.invent import read_gathered_text

    match = _REFERENCE_AUTHOR_YEAR.match(line.strip())
    if match is None:
        return None
    author = match.group(1).strip().rstrip(",")
    year = match.group(2)
    surname = author.split(",", 1)[0].strip().split()[-1].casefold()
    if not surname:
        return None
    module = module_code(essay_id)
    upload_dir = workspace_root() / "uploads" / module
    if not upload_dir.is_dir():
        return None
    for path in sorted(upload_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            text = read_gathered_text(path, essay_id)
        except (OSError, ValueError):
            continue
        folded = text.casefold()
        if surname not in folded or year not in text:
            continue
        quote = ""
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            piece = sentence.strip()
            if surname in piece.casefold() and year in piece:
                quote = piece
                break
        if not quote:
            quote = text.strip()[:500]
        # The printed line is matched to the upload. Its title is not parsed
        # here, and the line itself is not a gathered title, so none is stored.
        return {
            "id": f"src-{path.stem}",
            "origin": "upload",
            "locator": f"uploads/{module}/{path.name}",
            "author": author,
            "year": year,
            "quote": quote[:500],
        }
    return None


def _finish_recovered_pack(
    essay_id: str,
    pack: dict[str, Any],
    reference_lines: list[str],
) -> dict[str, Any]:
    """Keep the reference lines printed in the Word file.

    When the file lists references, those lines are the reference list.
    Research that is not one of those lines is not added.
    """
    filled = dict(pack)
    filled["recovered_from_docx"] = True
    if reference_lines:
        filled["references_markdown"] = "\n".join(reference_lines)
    filled = _word_pack(essay_id, filled)
    if reference_lines:
        filled["references_markdown"] = "\n".join(reference_lines)
    if filled.get("sources") and not reference_lines:
        return filled
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in reference_lines:
        source = _source_for_reference_line(essay_id, line)
        if source is None:
            continue
        ident = str(source.get("id") or "")
        if not ident or ident in seen:
            continue
        seen.add(ident)
        matched.append(source)
    if reference_lines:
        filled["sources"] = matched
        return filled
    if matched:
        filled["sources"] = matched
    return filled


def _reference_lines_in_docx(path: Path) -> int:
    from docx import Document

    try:
        document = Document(str(path))
    except Exception:
        return 0
    return len(_reference_lines_from_docx(document))


def _pack_from_docx(essay_id: str, source: Path) -> dict[str, Any] | None:
    """Essay sections from an earlier Word file.

    The cover that write_docx prepends is not part of the essay. A previous
    rewrite that wrapped every paragraph under Draft is unwrapped, so the next
    write does not stack another cover or another Draft heading.
    """
    from docx import Document

    try:
        document = Document(str(source))
    except Exception:
        return None
    reference_lines = _reference_lines_from_docx(document)
    cover: list[str] = []
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading") and text:
            current = {"heading": text, "lines": []}
            sections.append(current)
            continue
        if current is None:
            if text:
                cover.append(text)
            continue
        if text:
            current["lines"].append(text)
    content = [item for item in sections if item["heading"].casefold() != "references"]
    if content and all(item["heading"].casefold() == "draft" for item in content):
        lines: list[str] = []
        for item in content:
            lines.extend(item["lines"])
        if len(content) > 1 or _wrapped_draft(lines, cover):
            content = _unwrap_draft(essay_id, lines, cover)
    elif not content:
        if _wrapped_draft(cover, []):
            content = _unwrap_draft(essay_id, cover, [])
        elif cover:
            content = [{"heading": cover[0], "lines": cover[1:]}]
    packed: list[dict[str, str]] = []
    for item in content:
        heading = str(item.get("heading") or "").strip()
        if not heading or heading.casefold() == "references":
            continue
        lines_raw = item.get("lines")
        body_lines: list[object] = lines_raw if isinstance(lines_raw, list) else []
        body = "\n".join(
            line.strip() for line in body_lines if isinstance(line, str) and line.strip()
        )
        packed.append({"heading": heading, "body": body})
    if not packed:
        return None
    pack = {
        "essay_id": essay_id,
        "title": "Draft",
        "sections": packed,
        "referencing": "harvard",
    }
    pack = _hydrate_pack_from_docx_cover(essay_id, cover, pack)
    if pack.get("conclusion") not in {"noted", "open"}:
        pack["conclusion"] = "noted"
    return _finish_recovered_pack(essay_id, pack, reference_lines)


def _copy_word_bytes(source: Path, dest: Path) -> None:
    """Copy one built Word file byte-for-byte. This does not build the document again."""
    import os

    refuse_repo_write(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pending = dest.with_name(f".{dest.name}.writing")
    pending.write_bytes(source.read_bytes())
    os.replace(pending, dest)


def _refresh_sequence_final(source: Path, project: str) -> Path:
    """Write output/<module>-10/<module>-final.docx from the one build just saved."""
    final = source.parent / f"{project}-10" / f"{project}-final.docx"
    _copy_word_bytes(source, final)
    return final


def _unmounted_documents(body: dict[str, Any]) -> None:
    body["reason"] = "mac-not-mounted"
    body["copied"] = False
    body["findings_place"] = ""
    body["findings_file"] = {
        "wrote": False,
        "place": "",
        "reason": "mac-not-mounted",
        "refused": "documents",
        "ok": False,
    }


def _footer_stop(body: dict[str, Any], *, refused: str, reason: str) -> dict[str, Any]:
    body["ok"] = False
    body["copied"] = False
    body["sequence_written"] = False
    body["refused"] = refused
    body["reason"] = reason
    return body


def _stage10_mark_path(source: Path) -> Path:
    return source.with_name(".stage10-copied.json")


def _mounted_final_docx(essay_id: str) -> Path | None:
    """The copied final Word file when Documents is mounted for this sequence."""
    project = module_code(essay_id)
    leaf = f"{project}-final.docx"
    from essay_writer.first_run import sequence_mac_deliverables_dir

    folder = sequence_mac_deliverables_dir(essay_id)
    if folder is not None:
        return folder / leaf
    root = documents_root()
    if root is not None and root.is_dir():
        return root / f"{project}-10" / leaf
    return None


def _recorded_copy_present(source: Path, record: dict[str, Any]) -> bool:
    """True when the copied final named by this stage 10 record is still on disk."""
    place = record.get("place")
    if isinstance(place, str) and place.strip() and Path(place).expanduser().is_file():
        return True
    mounted = _mounted_final_docx(source.stem)
    return mounted is not None and mounted.is_file()


def _missing_stored_final_word(essay_id: str) -> bool:
    """True when stage 10 recorded a copied final and that file is gone."""
    import json

    source = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    mark = _stage10_mark_path(source)
    if not mark.is_file():
        return False
    try:
        record = json.loads(mark.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(record, dict) or record.get("copied") is not True:
        return False
    return not _recorded_copy_present(source, record)


def _stop_missing_final_word(body: dict[str, Any]) -> None:
    """Say the final Word file is missing. This does not write it again."""
    body["ok"] = False
    body["refused"] = "word"
    body["reason"] = MISSING_FINAL_WORD
    body["place"] = ""
    body["final_word"] = {
        "ok": False,
        "copied": False,
        "place": "",
        "reason": MISSING_FINAL_WORD,
    }


def _stage10_pack_sha(pack: dict[str, Any]) -> str:
    import hashlib
    import json

    raw = json.dumps(pack, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _remember_stage10(source: Path, pack: dict[str, Any], body: dict[str, Any]) -> None:
    import json

    record = {
        "pack_sha256": _stage10_pack_sha(pack),
        "copied": body.get("copied") is True,
        "place": body.get("place") or "",
        "comments_place": body.get("comments_place") or "",
        "findings_place": body.get("findings_place") or "",
        "sequence_written": body.get("sequence_written") is True,
    }
    path = _stage10_mark_path(source)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def _reuse_stage10(
    source: Path, pack: dict[str, Any], body: dict[str, Any]
) -> dict[str, Any] | None:
    """Return the previous stage 10 result when this pack was already written.

    A recorded copy whose file is gone stops here. The Word file is not written again.
    """
    import json

    mark = _stage10_mark_path(source)
    if not source.is_file() or not mark.is_file():
        return None
    try:
        record = json.loads(mark.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("pack_sha256") != _stage10_pack_sha(pack):
        return None
    if record.get("sequence_written") is not True:
        return None
    if record.get("copied") is True and not _recorded_copy_present(source, record):
        body["ok"] = False
        body["copied"] = False
        body["sequence_written"] = False
        body["reused"] = False
        body["reason"] = MISSING_FINAL_WORD
        body["place"] = ""
        body["comments_place"] = ""
        body["findings_place"] = ""
        return body
    body["ok"] = True
    body["copied"] = record.get("copied") is True
    body["sequence_written"] = True
    body["reused"] = True
    body["reason"] = ""
    body["place"] = record.get("place") or body.get("place") or ""
    body["comments_place"] = record.get("comments_place") or ""
    body["findings_place"] = record.get("findings_place") or ""
    project = module_code(source.stem)
    sequence_final = source.parent / f"{project}-10" / f"{project}-final.docx"
    if sequence_final.is_file():
        from essay_writer.assignment_handoff import attach_word_chat

        attach_word_chat(body, sequence_final)
    return body


def _stage10_body(
    *,
    project: str,
    source: Path,
    place: str,
    notes: str,
) -> dict[str, Any]:
    """The reply body before any pack or Word work starts."""
    return {
        "ok": True,
        "copied": False,
        "place": place,
        "comments_place": notes,
        "findings_place": "",
        "final_name": f"{project}-final.docx",
        "first_draft_name": source.name,
        "sequence_written": False,
    }


def _load_stage10_pack(
    essay_id: str,
    source: Path,
    body: dict[str, Any],
) -> tuple[dict[str, Any] | None, str, str, int]:
    """Finish reads the saved draft when it is present, otherwise the working Word file.

    The saved draft is the stored pack. The working Word file is the sequence
    document. Both are input to the same one build.
    """
    saved_pack = _saved_pack(essay_id)
    pack_path = "saved_pack" if saved_pack is not None else "missing"
    pack = saved_pack
    existing_ref_lines = _reference_lines_in_docx(source) if source.is_file() else 0
    if pack is None and source.is_file():
        pack = _pack_from_docx(essay_id, source)
        if pack is not None:
            pack_path = "pack_from_docx"
    saved_pack_state = "present" if saved_pack is not None else "null"
    body["pack_path"] = pack_path
    body["saved_pack_state"] = saved_pack_state
    return pack, pack_path, saved_pack_state, existing_ref_lines


def _missing_stage10_pack(
    essay_id: str,
    body: dict[str, Any],
    *,
    root: Path | None,
    pack_path: str,
    saved_pack_state: str,
) -> dict[str, Any]:
    """The saved draft Word file and a usable pack are both absent."""
    body["ok"] = False
    body["reason"] = "The saved draft Word file is not there yet."
    from essay_writer.debug_log import log_word_step

    log_word_step(
        "write_stage10",
        essay_id,
        stage="10",
        pack_path=pack_path,
        saved_pack=saved_pack_state,
        refused="missing-pack",
        reason=body["reason"],
    )
    if root is None:
        _unmounted_documents(body)
        body["ok"] = False
    return body


def _log_stage10_word(
    essay_id: str,
    pack: dict[str, Any],
    *,
    pack_path: str,
    saved_pack_state: str,
    cover: list[Any] | None,
    sources_count: int,
    refs_count: int,
    **extra: Any,
) -> None:
    """One debug-line shape for every stage 10 Word stop and success."""
    from essay_writer.debug_log import (
        log_word_step,
        pack_log_assessment,
        pack_log_title,
    )

    log_word_step(
        "write_stage10",
        essay_id,
        stage="10",
        pack_path=pack_path,
        saved_pack=saved_pack_state,
        title=pack_log_title(pack),
        assessment=pack_log_assessment(pack),
        conclusion=str(pack.get("conclusion") or ""),
        cover=cover,
        sources_count=sources_count,
        refs_count=refs_count,
        **extra,
    )


def _stage10_manifest(
    essay_id: str,
    *,
    body: dict[str, Any],
    pack: dict[str, Any],
    pack_path: str,
    saved_pack_state: str,
    existing_ref_lines: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Manifest the pack and refuse a recovery that would drop references."""
    from essay_writer.word import word_manifest

    pack, report = word_manifest(essay_id, pack, pack_path=pack_path, product_log=False)
    refs_count = len(report.get("references") or [])
    sources_count = len(report.get("sources") or [])
    cover = report.get("cover") if isinstance(report.get("cover"), list) else []
    if pack_path == "pack_from_docx" and existing_ref_lines > 0 and refs_count == 0:
        reason = (
            "The sequence Word file already lists references, but recovery from that file "
            "would write an empty References section. Restore saved_pack or confirm research first."
        )
        _log_stage10_word(
            essay_id,
            pack,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
            cover=cover,
            sources_count=sources_count,
            refs_count=refs_count,
            refused="word-recovery",
            reason=reason,
        )
        body["ok"] = False
        body["copied"] = False
        body["sequence_written"] = False
        body["refused"] = "word-recovery"
        body["reason"] = reason
        body["references"] = report.get("references") or []
        body["cover"] = cover
        body["sources"] = report.get("sources") or []
        return None, body
    return (
        {
            "pack": pack,
            "report": report,
            "pack_path": pack_path,
            "saved_pack_state": saved_pack_state,
            "refs_count": refs_count,
            "sources_count": sources_count,
            "cover": cover,
        },
        None,
    )


def _stage10_gate(
    essay_id: str,
    *,
    source: Path,
    body: dict[str, Any],
    prepared: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The contract, word-count, reference, and repeat-run gates."""
    from essay_writer.brief_contract import word_contract_refusal

    pack = prepared["pack"]
    report = prepared["report"]
    pack_path = prepared["pack_path"]
    saved_pack_state = prepared["saved_pack_state"]
    refs_count = prepared["refs_count"]
    sources_count = prepared["sources_count"]
    cover = prepared["cover"]
    blocked = word_contract_refusal(essay_id, pack, report)
    if blocked:
        body["ok"] = False
        body["copied"] = False
        body["refused"] = blocked.get("refused")
        body["reason"] = blocked.get("reason") or ""
        body["missing_fields"] = blocked.get("missing_fields")
        _log_stage10_word(
            essay_id,
            pack,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
            cover=cover,
            sources_count=sources_count,
            refs_count=refs_count,
            refused=str(blocked.get("refused") or "refused"),
            reason=str(blocked.get("reason") or ""),
        )
        return None, body
    if pack.get("word_count_acknowledged") is not True:
        blockers = report.get("blockers")
        if isinstance(blockers, list):
            for item in blockers:
                if not isinstance(item, dict) or item.get("code") != "word-count":
                    continue
                reason = str(item.get("reason") or "")
                _log_stage10_word(
                    essay_id,
                    pack,
                    pack_path=pack_path,
                    saved_pack_state=saved_pack_state,
                    cover=cover,
                    sources_count=sources_count,
                    refs_count=refs_count,
                    refused="word-count",
                    reason=reason,
                )
                body["ok"] = False
                body["copied"] = False
                body["sequence_written"] = False
                body["refused"] = "word-count"
                body["reason"] = reason
                return None, body
    from essay_writer.word_references import stage10_reference_block

    blocked_refs = stage10_reference_block(
        report.get("sources") or [],
        pack,
        list(report.get("sections") or []),
    )
    if blocked_refs:
        body["ok"] = False
        body["copied"] = False
        body["sequence_written"] = False
        body["refused"] = blocked_refs.get("refused")
        body["reason"] = blocked_refs.get("reason") or ""
        _log_stage10_word(
            essay_id,
            pack,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
            cover=cover,
            sources_count=sources_count,
            refs_count=refs_count,
            refused=str(blocked_refs.get("refused") or "empty-references"),
            reason=str(blocked_refs.get("reason") or ""),
        )
        return None, body
    reused = _reuse_stage10(source, pack, body)
    if reused is not None:
        return None, reused
    return prepared, None


def build_finished_word(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    path: Path,
) -> Path:
    """Build the finished Word document once and return that file.

    Stage 10 save is the only caller. Page-number and reference checks run on
    this file before it is saved. The final-named file and the student's folder
    receive a byte-for-byte copy of this result. A later call with the same
    draft does not call this again.
    """
    from essay_writer.word import write_docx

    write_docx(essay_id, pack, report, path, product_log=False)
    return path


def _write_stage10_sequence(
    essay_id: str,
    *,
    source: Path,
    body: dict[str, Any],
    prepared: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Build once, check that file, then save it.

    A failed check deletes the pending build and leaves every previous file in
    place. A written file leaves the facts the delivery step needs in the first
    slot.
    """
    import os

    from essay_writer.word import (
        EmptyFooter,
        empty_footer_refusal,
    )

    pack = prepared["pack"]
    report = prepared["report"]
    pack_path = prepared["pack_path"]
    saved_pack_state = prepared["saved_pack_state"]
    refs_count = prepared["refs_count"]
    sources_count = prepared["sources_count"]
    cover = prepared["cover"]
    pending = source.with_name(f".{source.name}.writing")
    try:
        build_finished_word(essay_id, pack, report, pending)
    except EmptyFooter:
        pending.unlink(missing_ok=True)
        return None, _footer_stop(
            body,
            refused="footer",
            reason="The page number is missing. An empty footer is refused.",
        )
    empty = empty_footer_refusal(pending)
    if empty:
        pending.unlink(missing_ok=True)
        return None, _footer_stop(
            body,
            refused=str(empty.get("refused") or "footer"),
            reason=str(empty.get("reason") or ""),
        )
    if _reference_lines_in_docx(pending) == 0:
        pending.unlink(missing_ok=True)
        reason = (
            "The References section has no entries. Add reference lines before this step can close."
        )
        _log_stage10_word(
            essay_id,
            pack,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
            cover=cover,
            sources_count=sources_count,
            refs_count=0,
            refused="empty-references",
            reason=reason,
        )
        body["ok"] = False
        body["copied"] = False
        body["sequence_written"] = False
        body["refused"] = "empty-references"
        body["reason"] = reason
        return None, body
    from essay_writer.harvard_ref_check import writer_reference_block

    blocked_harvard = writer_reference_block(
        essay_id,
        pending,
        list(report.get("sources") or []),
    )
    if blocked_harvard:
        pending.unlink(missing_ok=True)
        reason = str(blocked_harvard.get("reason") or "")
        _log_stage10_word(
            essay_id,
            pack,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
            cover=cover,
            sources_count=sources_count,
            refs_count=refs_count,
            refused="harvard-references",
            reason=reason,
        )
        body["ok"] = False
        body["copied"] = False
        body["sequence_written"] = False
        body["refused"] = "harvard-references"
        body["reason"] = reason
        body["misses"] = blocked_harvard.get("misses") or []
        body["checked"] = True
        body["handbook"] = blocked_harvard.get("handbook") or ""
        return None, body
    body["harvard_references"] = {
        "checked": True,
        "ok": True,
        "handbook": "docs/referencing-harvard.md",
    }
    source.parent.mkdir(parents=True, exist_ok=True)
    os.replace(pending, source)
    return prepared, None


def _deliver_stage10(
    essay_id: str,
    *,
    project: str,
    root: Path | None,
    source: Path,
    written: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Copy the one build to the final-named file, then to the student's folder."""
    pack = written["pack"]
    report = written["report"]
    pack_path = written["pack_path"]
    saved_pack_state = written["saved_pack_state"]
    refs_count = written["refs_count"]
    sources_count = written["sources_count"]
    cover = written["cover"]
    sequence_final = _refresh_sequence_final(source, project)
    from essay_writer.assignment_handoff import attach_word_chat
    from essay_writer.word_references import reference_lines_origin

    attach_word_chat(body, sequence_final)
    body["sequence_written"] = True
    refs_from = reference_lines_origin(pack)
    _log_stage10_word(
        essay_id,
        pack,
        pack_path=pack_path,
        saved_pack_state=saved_pack_state,
        cover=cover,
        sources_count=sources_count,
        refs_count=refs_count,
        refs_from=refs_from,
        output_path=source,
    )
    body["references"] = report.get("references") or []
    body["cover"] = cover
    body["sources"] = report.get("sources") or []
    if root is None:
        _unmounted_documents(body)
        body["ok"] = True
        body["sequence_written"] = True
        return body
    from essay_writer.first_run import (
        ensure_sequence_mac_folder,
        sequence_mac_deliverables_dir,
    )

    seq_mac = sequence_mac_deliverables_dir(essay_id)
    if seq_mac is not None:
        ensure_sequence_mac_folder(essay_id)
        folder = seq_mac
    elif not root.is_dir():
        _unmounted_documents(body)
        body["ok"] = True
        body["sequence_written"] = True
        return body
    else:
        folder = root / f"{project}-10"
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{project}-final.docx"
    comments = folder / f"{project}-comments.docx"
    _copy_word_bytes(source, final)
    from essay_writer.review import place_findings_note

    note = place_findings_note(essay_id, documents=root)
    body["findings_file"] = note
    if note.get("wrote"):
        body["findings_place"] = note.get("place") or ""
    _write_comments(essay_id, comments)
    from essay_writer.quarantine import clear_mac_quarantine

    clear_mac_quarantine(final)
    clear_mac_quarantine(comments)
    if note.get("wrote"):
        clear_mac_quarantine(root / project / f"{project}-findings.docx")
    body["copied"] = True
    body["reason"] = ""
    body["sequence_written"] = True
    return body


def _remember_stage10_result(
    essay_id: str,
    source: Path,
    pack: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Record the delivered pack, then point the ML event log at the new file."""
    _remember_stage10(source, pack, body)
    from essay_writer.ml_events import note_stage10_rewrite_paths

    note_stage10_rewrite_paths(essay_id)
    return body


def write_stage10(essay_id: str, *, documents: Path | None = None) -> dict[str, Any]:
    """Build the finished Word file once, check it, then copy those bytes.

    The build runs on the stage 10 save, before that step is marked saved.
    Page-number and reference checks run on that one file. The same bytes are
    saved as the working sequence file, copied to output/<module>-10/<module>-final.docx,
    and copied to the student's folder when that folder is on this computer.
    A failed check leaves the previous files in place. A successful build is
    remembered whether or not that folder is here. The same draft later returns
    the remembered result and does not build again. A missing registration
    number or an empty footer does not record the file as final.
    """
    project = module_code(essay_id)
    place = final_place(essay_id)
    notes = comments_place(essay_id)
    root = documents_root(documents)
    source = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    body = _stage10_body(project=project, source=source, place=place, notes=notes)
    pack, pack_path, saved_pack_state, existing_ref_lines = _load_stage10_pack(
        essay_id,
        source,
        body,
    )
    if pack is None:
        return _missing_stage10_pack(
            essay_id,
            body,
            root=root,
            pack_path=pack_path,
            saved_pack_state=saved_pack_state,
        )
    prepared, stopped = _stage10_manifest(
        essay_id,
        body=body,
        pack=pack,
        pack_path=pack_path,
        saved_pack_state=saved_pack_state,
        existing_ref_lines=existing_ref_lines,
    )
    if prepared is None:
        if stopped is None:
            raise RuntimeError("stage 10 manifest stopped without a reply")
        return stopped
    prepared, stopped = _stage10_gate(
        essay_id,
        source=source,
        body=body,
        prepared=prepared,
    )
    if prepared is None:
        if stopped is None:
            raise RuntimeError("stage 10 gate stopped without a reply")
        return stopped
    written, stopped = _write_stage10_sequence(
        essay_id,
        source=source,
        body=body,
        prepared=prepared,
    )
    if written is None:
        if stopped is None:
            raise RuntimeError("stage 10 write stopped without a reply")
        return stopped
    body = _deliver_stage10(
        essay_id,
        project=project,
        root=root,
        source=source,
        written=written,
        body=body,
    )
    if body.get("ok") is True and body.get("sequence_written") is True:
        return _remember_stage10_result(essay_id, source, written["pack"], body)
    return body


def _write_comments(essay_id: str, path: Path) -> None:
    from docx import Document

    from essay_writer.specialists.eqr import eqr_record, eqr_verdict
    from essay_writer.word import _font, _style_document

    document = Document()
    _style_document(document)
    stored = eqr_record(essay_id, "9") or {}
    findings_raw = stored.get("findings")
    findings = findings_raw if isinstance(findings_raw, str) else ""
    if stored.get("word_opened") and findings.strip():
        review = findings.strip()
    else:
        verdict = eqr_verdict(essay_id, "9")
        if verdict == "PASS":
            review = "The independent review recorded a pass."
        elif verdict == "FAIL":
            review = "The independent review recorded a fail."
        else:
            review = "The independent review is not recorded."
    record = load_stage7(essay_id)
    notes = comment_text(record)
    for paragraph_text in (review, notes):
        if not paragraph_text.strip():
            continue
        paragraph = document.add_paragraph()
        run = paragraph.add_run(paragraph_text)
        _font(run, 12)
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(path))


def stage6_fields(essay_id: str, *, master: str | None, named_folder: str | None) -> dict[str, Any]:
    report = master_word(essay_id, master=master, named_folder=named_folder)
    return {
        "place": report["place"],
        "master_ask": report["master_ask"],
        "choices": report["choices"],
        "expected_draft": report["expected"],
        "block_confirm": report["block_confirm"],
        "chain_started": False,
    }


def stage7_fields(essay_id: str) -> dict[str, Any]:
    record = load_stage7(essay_id)
    return {
        "questions": record.get("questions") or [],
        "draft_read": bool(record.get("asked")),
        "file_work": "chat",
        "delta": record.get("delta") or [],
        "chain_started": False,
    }


def finish_stage_reply(
    body: dict[str, Any],
    essay_id: str,
    stage: str,
    *,
    armed: bool,
) -> dict[str, Any]:
    """One stage only. Quiet mid steps once the chain is armed. Stage 10 names the final Word.

    A stored stage 10 reply does not write that Word file again. A missing copy
    stops and says so. Documents left unmounted stay on the unmounted reply.
    """

    body["chain_started"] = False
    body["chain_armed"] = armed
    body["executed_runs"] = [stage] if body.get("stored") else []
    if stage == "9":
        from essay_writer.specialists.grok_bot import front_office_stage9

        stop = front_office_stage9(essay_id)
        body["remarked"] = False
        body["freeflow"] = False
        body["gap_fill"] = False
        body["fo_stop"] = stop["stopped"]
        body["submit_pass"] = stop.get("reason") or ""
    if stage == "7":
        for key, value in stage7_fields(essay_id).items():
            body.setdefault(key, value)
    if stage == "6":
        body["chain_started"] = False
        body.pop("next_run", None)
    if body.get("stored") and armed and stage in {"7", "8", "9"}:
        run = next_run(essay_id, stage, armed=True)
        if run:
            body["next_run"] = run
            blocked = bool(run.get("blocked"))
            if blocked:
                body["blocked"] = True
                body["eqr"] = run.get("eqr") or "missing"
    if stage == "10" and body.get("stored"):
        final = body.get("final_word")
        source = work_dir(essay_id) / "output" / f"{essay_id}.docx"
        missing_copy = (
            not isinstance(final, dict)
            or "copied" not in final
            or (isinstance(final, dict) and final.get("reason") == MISSING_FINAL_WORD)
            or (
                isinstance(final, dict)
                and final.get("copied") is True
                and not _recorded_copy_present(source, final)
            )
        )
        if missing_copy:
            _stop_missing_final_word(body)
        elif isinstance(final, dict) and final.get("reason") == "mac-not-mounted":
            final.pop("sequence_written", None)
            final = dict(final)
            final["place"] = ""
            final["comments_place"] = ""
            final["delivery"] = "chat"
            body["place"] = ""
            body["final_word"] = final
        elif isinstance(final, dict):
            final.pop("sequence_written", None)
            body["place"] = final["place"]
            body["final_word"] = final
        kept = body.get("final_word")
        delivery = kept.get("delivery") if isinstance(kept, dict) else None
        if isinstance(delivery, dict):
            body["delivery"] = delivery
    elif stage == "10" and armed and not body.get("stored"):
        from essay_writer.spine import final_review

        blocked_text, verdict = final_review(essay_id)
        if blocked_text:
            body["blocked"] = True
            body["eqr"] = verdict
    from essay_writer.stage_next import apply_finished_stage_next

    apply_finished_stage_next(
        body,
        essay_id,
        stage,
        armed=armed,
        place=final_place(essay_id),
    )
    from essay_writer.cite_fit import in_line, speak_cite_ask

    speak_cite_ask(body)
    in_line(body, "student_outline_line")
    if stage == "10" and body.get("stored"):
        final = body.get("final_word")
        missing = not isinstance(final, dict) or final.get("reason") == MISSING_FINAL_WORD
        if not missing:
            _say_written_conclusion(body, essay_id)
    return body


def _say_written_conclusion(body: dict[str, Any], essay_id: str) -> None:
    """One student sentence when Word is already written. It is not a cover line."""
    from essay_writer.diary import conclusion_chat_line
    from essay_writer.state import load_state
    from essay_writer.student_voice import say

    source = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    if not source.is_file():
        return
    saved = load_state(essay_id).get("saved_pack")
    if not isinstance(saved, dict):
        return
    line = say(conclusion_chat_line(saved))
    if not line:
        return
    body["conclusion_line"] = line
    from essay_writer.stage_next import append_conclusion_next

    append_conclusion_next(body, line)
    chat = body.get("chat")
    if isinstance(chat, str) and chat.strip():
        if line not in chat:
            body["chat"] = f"{chat.rstrip()} {line}"
    else:
        body["chat"] = line
