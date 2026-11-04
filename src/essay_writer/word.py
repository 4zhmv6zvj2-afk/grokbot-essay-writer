"""Confirm-gated Word export. Draft writes nothing. Confirm writes .docx only."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from essay_writer.assignment_gate import assignment_requirements
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.diary import cover_field_rows, cover_lines_from_field_rows, layout_for
from essay_writer.draft_from_review import CRITICAL_REVIEW
from essay_writer.known_paths import guard_write_door, refuse_repo_write
from essay_writer.paths import (
    module_code,
    relative,
    sequence_number,
    sequence_write_error,
    work_dir,
)
from essay_writer.programme import STYLE_ID
from essay_writer.review import PERSON_BLOCK, writer_clears_left
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import (
    for_word,
    prose_for_surface,
    say,
    strip_word_labels,
)
from essay_writer.textutil import prepare_word_citations, reference_parts
from essay_writer.validate import inspect_pack, pack_identity

if TYPE_CHECKING:
    from docx.document import Document as DocumentType

TOOL = "essay.pack.render_word"


def _font(run, size: int, *, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Arial"
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor(0, 0, 0)
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attribute in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(attribute), "Arial")


def _page_number(paragraph) -> None:
    run = paragraph.add_run()
    _font(run, 12)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instruction)
    run._r.append(end)


class EmptyFooter(Exception):
    """write_docx refuses to save a file whose footer has no page field."""


def empty_footer_refusal(path) -> dict[str, object] | None:
    """Refuse a Word file whose footer has no PAGE field."""
    import zipfile

    reason = "The page number is missing. An empty footer is refused."
    try:
        xml = zipfile.ZipFile(path).read("word/footer1.xml").decode("utf-8")
    except (KeyError, OSError, zipfile.BadZipFile):
        return refuse("footer", reason, wrote=False)
    if "PAGE" not in xml or "instrText" not in xml:
        return refuse("footer", reason, wrote=False)
    return None


def _footer_has_page(document: DocumentType) -> bool:
    xml = document.sections[0].footer._element.xml
    return "PAGE" in xml and "instrText" in xml


def cover_lines(essay_id: str, pack: dict[str, Any], report: dict[str, Any]) -> list[str]:
    """One cover for stages 6, 7, 9, and the stage 10 final. All of them call write_docx."""

    record = assignment_requirements(essay_id)
    if record.get("active") is True and record.get("mapped") is False:
        return []
    lock = record.get("lock")
    if isinstance(lock, str) and lock not in {"thesis", "purpose_and_scope"}:
        essay = False
    else:
        essay = True
    rows = cover_field_rows(essay_id, pack, report, essay=essay)
    return cover_lines_from_field_rows(essay_id, pack, rows)


def word_manifest(
    essay_id: str,
    pack: dict[str, Any],
    *,
    pack_path: str | None = None,
    product_log: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Shared cover and Reference List door for stages 6, 7, 9, and 10.

    A body-only pack picks up gathered sources here, then the same house cover
    lines every stage Word file prints. Stages do not keep a second pack builder.
    A short body is stretched from those gathered files into the document word
    band before inspect. The house cover is unchanged.

    When the student supplied an outline or base prose, that structure is the
    plan: its headings and order stay, no section is lifted from the brief, and
    the body is not stretched. Only the short cites are woven in.
    """
    from essay_writer.brief_contract import pack_with_registration
    from essay_writer.late_chain import _word_pack, log_word_manifest
    from essay_writer.outline_primary import apply_outline_primary
    from essay_writer.specialists.writer import lift_missing_sections, recover_short_word_band

    prepared = pack_with_registration(essay_id, _word_pack(essay_id, pack))
    pinned = apply_outline_primary(essay_id, prepared)
    prepared = pinned["pack"]
    if pinned.get("applied") is not True:
        prepared = lift_missing_sections(essay_id, prepared)["pack"]
        prepared = recover_short_word_band(essay_id, prepared)
    report = inspect_pack(essay_id, prepared)
    from essay_writer.cite_fit import withhold_body_cites

    kept_sources, kept_sections = withhold_body_cites(
        essay_id,
        list(report.get("sources") or []),
        list(report.get("sections") or []),
    )
    report = dict(report)
    report["sources"] = kept_sources
    report["sections"] = kept_sections
    stamped = dict(report)
    from essay_writer.word_references import (
        references_markdown_lines,
        usable_word_reference_lines,
        without_withheld_reference_lines,
    )

    reference_lines = without_withheld_reference_lines(
        essay_id,
        usable_word_reference_lines(list(report.get("sources") or []), prepared),
        list(report.get("sources") or []),
    )
    stamped["references"] = reference_lines
    if references_markdown_lines(prepared):
        prepared = dict(prepared)
        if reference_lines:
            prepared["references_markdown"] = "\n".join(reference_lines)
        else:
            prepared.pop("references_markdown", None)
    stamped["cover"] = cover_lines(essay_id, prepared, report)
    if pinned.get("applied") is True:
        outline: dict[str, Any] = {}
        raw_outline = pinned.get("outline")
        if isinstance(raw_outline, dict):
            outline = raw_outline
        stamped["student_outline"] = {
            "headings": list(outline.get("headings") or []),
            "used": list(pinned.get("used") or []),
            "off_outline": list(pinned.get("off_outline") or []),
            "sources": list(outline.get("files") or []),
            "invented_lift": False,
        }
    log_word_manifest(
        essay_id,
        prepared,
        stamped,
        pack_path=pack_path or "caller_pack",
        product_log=product_log,
    )
    return prepared, stamped


def _planned(essay_id: str) -> str:
    number = sequence_number(essay_id)
    module = module_code(essay_id)
    if number is None:
        return ""
    return f"Essay-writer/{module}/sequences/{number}/output/{essay_id}.docx"


def _validation_stamp(record: object) -> dict[str, object] | None:
    if not isinstance(record, dict):
        return None
    return {
        "ok": bool(record.get("ok")),
        "files": record.get("files") or {},
        "confirmed_at": record.get("confirmed_at"),
    }


def _style_document(document: DocumentType, essay_id: str | None = None) -> None:

    layout = layout_for(essay_id) if essay_id else {}
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(int(layout.get("body_pt") or 12))
    normal.font.color.rgb = RGBColor(0, 0, 0)
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    if layout.get("margin_cm"):
        margin: Cm | Inches = Cm(float(layout["margin_cm"]))
    else:
        margin = Inches(1)
    section.left_margin = margin
    section.right_margin = margin
    section.top_margin = margin
    section.bottom_margin = margin
    footer = section.footer.paragraphs[0]
    if layout.get("page_number") == "right":
        footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _page_number(footer)
    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    document.core_properties.comments = ""
    document.core_properties.category = ""


_HASH_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _heading_parts(text: str) -> tuple[int, str]:
    match = _HASH_HEADING.match(text.strip())
    if match is None:
        return 1, text.strip()
    return min(len(match.group(1)), 3), match.group(2).strip()


def _paragraph(
    document: DocumentType,
    text: str,
    *,
    center: bool = False,
    justify: bool = False,
    size: int = 12,
    bold: bool = False,
):
    cleaned = prose_for_surface(text, "word")
    if not cleaned:
        return None
    if center:
        alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif justify:
        alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    else:
        alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph = document.add_paragraph()
    paragraph.alignment = alignment
    paragraph.paragraph_format.line_spacing = 1.5
    run = paragraph.add_run(cleaned)
    _font(run, size, bold=bold)
    return paragraph


def _add_heading(document: DocumentType, text: str, *, level: int = 1, size: int = 14):
    level, title = _heading_parts(text) if level == 1 else (level, text.strip())
    heading = document.add_heading(for_word(title), level=level)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    heading.paragraph_format.line_spacing = 1.5
    for run in heading.runs:
        _font(run, size, bold=True)
    return heading


def _write_body(document: DocumentType, text: str, *, justify: bool, heading_size: int = 14) -> None:
    cleaned = prose_for_surface(text, "word")
    if not cleaned:
        return
    for line in cleaned.splitlines():
        if not line.strip():
            continue
        match = _HASH_HEADING.match(line.strip())
        if match:
            _add_heading(document, line, level=1, size=heading_size)
            continue
        _paragraph(document, line, justify=justify)


def write_critical_review_docx(path: Path, prose: str) -> None:
    """One critical-review note as Word for the student zip."""
    document = Document()
    _style_document(document)
    document.core_properties.title = "Critical review"
    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    if prose:
        for line in prose.splitlines():
            if not line.strip():
                continue
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.line_spacing = 1.5
            run = paragraph.add_run(line.rstrip())
            _font(run, 12)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".docx.tmp")
    document.save(str(temporary))
    os.replace(temporary, path)


def write_docx(
    essay_id: str,
    pack: dict[str, Any],
    report: dict[str, Any],
    path,
    *,
    product_log: bool = True,
) -> None:
    from essay_writer.brief_contract import pack_with_registration

    pack = pack_with_registration(essay_id, pack)
    printed_sources, printed_sections = prepare_word_citations(
        essay_id, list(report["sources"]), list(report["sections"])
    )
    refuse_repo_write(Path(path))
    from essay_writer.specialists.writer import body_is_justified

    justify = body_is_justified(essay_id)

    layout = layout_for(essay_id)
    heading_size = int(layout.get("heading_pt") or 14)
    document = Document()
    _style_document(document, essay_id)
    if not _footer_has_page(document):
        raise EmptyFooter()
    document.core_properties.title = strip_word_labels(str(report.get("title") or essay_id))
    stored_cover = report.get("cover")
    lines = stored_cover if isinstance(stored_cover, list) else cover_lines(essay_id, pack, report)
    for index, line in enumerate(lines):
        _paragraph(document, line, center=True, size=16 if index == 0 else 14, bold=True)
    document.add_page_break()
    for section in printed_sections:
        _add_heading(document, str(section["heading"]), size=heading_size)
        _write_body(document, section["body"], justify=justify, heading_size=heading_size)
    for visual in list(report["figures"]) + list(report["tables"]):
        _paragraph(document, visual["label"], bold=True)
        if visual.get("source_line"):
            _paragraph(document, visual["source_line"])
    reference_heading = document.add_heading("References", level=1)
    reference_heading.alignment = WD_ALIGN_PARAGRAPH.LEFT
    for run in reference_heading.runs:
        _font(run, heading_size, bold=True)
    from essay_writer.word_references import (
        references_markdown_lines,
        without_withheld_reference_lines,
    )

    markdown_lines = without_withheld_reference_lines(
        essay_id,
        references_markdown_lines(pack),
        printed_sources,
    )

    def _reference_paragraph():
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.line_spacing = 1.5
        paragraph.paragraph_format.left_indent = Inches(0.5)
        paragraph.paragraph_format.first_line_indent = Inches(-0.5)
        return paragraph

    if markdown_lines:
        from essay_writer.word_references import styled_reference_runs

        for line in markdown_lines:
            cleaned = strip_word_labels(line)
            if not cleaned.strip():
                continue
            paragraph = _reference_paragraph()
            for text, italic in styled_reference_runs(cleaned, printed_sources):
                piece = strip_word_labels(text)
                if not piece:
                    continue
                run = paragraph.add_run(piece)
                _font(run, 12, italic=italic)
    else:
        for source in printed_sources:
            if not isinstance(source, dict):
                continue
            parts = reference_parts(source)
            if not "".join(text for text, _italic in parts).strip():
                continue
            paragraph = _reference_paragraph()
            for text, italic in parts:
                run = paragraph.add_run(strip_word_labels(text))
                _font(run, 12, italic=italic)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".docx.tmp")
    document.save(str(temporary))
    os.replace(temporary, path)
    from essay_writer.late_chain import log_word_docx_written

    log_word_docx_written(essay_id, pack, report, lines, path, product_log=product_log)


def essay_pack_render_word(
    essay_id: str,
    pack: dict[str, Any],
    confirmPhase: str | None = None,
    stage: str | None = None,
) -> dict[str, object]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if not isinstance(pack, dict):
        return refuse("pack", "pack must be an object")
    from essay_writer.brief_contract import student_fields_label, word_contract_refusal
    from essay_writer.validate import _pack_assignment_text

    pack, report = word_manifest(essay_id, pack)
    blocked_contract = word_contract_refusal(essay_id, pack, report)
    if blocked_contract:
        blocked_contract["path"] = _planned(essay_id)
        return blocked_contract
    from essay_writer.specialists.writer import accept_draft

    blocked_gate = accept_draft(essay_id, _pack_assignment_text(pack))
    if blocked_gate:
        return blocked_gate
    if pack.get("format", "docx") != "docx":
        return refuse("word-only", "Word .docx is the only output. PDF is refused.", wrote=False)
    if stage is not None and stage not in {"6", "7", "9"}:
        return refuse(
            "stage",
            "Word stage is 6 for the first Word file, 7 after the questions and edits, or 9 for the final Word file.",
        )
    if stage == "7":
        from essay_writer.stage7 import stage7_edited

        if not stage7_edited(essay_id):
            return refuse("stage", "Ask, then edit from the answers, before this Word save.")
    hard = [
        item
        for item in report["blockers"]
        if item["code"]
        in {
            "invent-forbid",
            "cross-essay",
            "word-only",
            "measurement",
            "title-page",
            "named-parts",
            "brief-mapping",
            CRITICAL_REVIEW,
        }
    ]
    identity = pack_identity(essay_id, pack)
    state = load_state(essay_id)
    validation = (state.get("validations") or {}).get(identity)
    payload = {"essay_id": essay_id, "pack": pack, "format": "docx"}
    if stage is not None:
        payload["stage"] = stage
    fingerprint = {
        "files": report["files"],
        "research": report["research"],
        "validation": _validation_stamp(validation),
    }
    planned = _planned(essay_id)
    body: dict[str, Any] = {
        "ok": not hard,
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "format": "docx",
        "path": planned,
        "pack_digest": identity,
        "passed": report["passed"],
        "blockers": report["blockers"],
        "notes": report["notes"],
        "cover": (
            report["cover"]
            if isinstance(report.get("cover"), list)
            else cover_lines(essay_id, pack, report)
        ),
        "headings": [section["heading"] for section in report["sections"]],
        "references": report["references"],
        "figures": report["figures"],
        "tables": report["tables"],
        "word_count": report["word_count"],
        "section_budgets": report.get("section_budgets") or [],
        "brief_contradictions": report.get("brief_contradictions") or [],
        "safe_default": report.get("safe_default"),
        "simulation_events": report.get("simulation_events") or {"noticed": False},
        "validation_confirmed": bool(isinstance(validation, dict) and validation.get("ok")),
        "student_fields": student_fields_label(essay_id, pack),
        "referencing": STYLE_ID,
        "genre": report.get("genre"),
        "same_arguments_required": True,
    }
    if stage is not None:
        body["stage"] = stage
    if hard:
        body["refused"] = hard[0]["code"]
        reason = hard[0]["reason"]
        body["reason"] = say(reason) if isinstance(reason, str) else reason
        return body
    if stage in {"6", "9"}:
        from essay_writer.gates import evaluate_gates
        from essay_writer.specialists.eqr import eqr_verdict

        gate_report = evaluate_gates(essay_id, pack)
        body["gates"] = {"passed": gate_report["passed"], "gates": gate_report["gates"]}
        body["plagiarism"] = gate_report["plagiarism"]
        if stage == "9":
            from essay_writer.specialists.eqr import submit_pass_unlocked

            submit = submit_pass_unlocked(essay_id)
            body["eqr"] = submit.get("eqr") or "missing"
            body["submit_pass"] = submit.get("reason") or ""
        else:
            body["eqr"] = eqr_verdict(essay_id, stage) or "missing"
        if not gate_report["plagiarism"]["passed"]:
            body["ok"] = False
            body["refused"] = "unquoted-exact"
            reason = gate_report["plagiarism"]["reason"]
            body["reason"] = say(reason) if isinstance(reason, str) else reason
            return body
        if not gate_report["passed"]:
            body["ok"] = False
            body["refused"] = "gates"
            body["reason"] = say("Mechanical gates 1–11 did not pass. Word was not written.")
            return body
    if confirmPhase == DRAFT:
        body["ok"] = True
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        if stage in {"6", "9"} and body.get("eqr") != "PASS":
            which = "first" if stage == "6" else "final"
            body["writer_clears_left"] = writer_clears_left()
            body["next"] = say(
                f"The {which} Word file is not written yet. {PERSON_BLOCK}"
            )
            from essay_writer.specialists.grok_bot import attach_eqr_first_run_speech

            attach_eqr_first_run_speech(body)
        else:
            body["next"] = say(
                "Show this Word preview to the human. No file has been written. "
                "Say yes to write this same draft, and only once validation of this draft is recorded."
            )
        if stage is None:
            from essay_writer.late_chain import quiet_word_step

            return quiet_word_step(body, pack)
        return body
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["wrote"] = False
        ready["path"] = planned
        return ready
    if not report["passed"]:
        return refuse(
            "validate",
            "This pack did not pass validation. Word was not written.",
            blockers=report["blockers"],
            path=planned,
            pack_digest=identity,
        )
    if not isinstance(validation, dict) or not validation.get("ok"):
        return refuse(
            "validate",
            "Validate this pack with draft, then confirm, before Word confirm. "
            "A changed pack needs both steps again.",
            path=planned,
            pack_digest=identity,
        )
    if (validation.get("files") or {}) != report["files"]:
        return refuse(
            "confirm",
            "Gathered files changed after validation. Fresh validate draft required.",
            path=planned,
            pack_digest=identity,
        )
    if stage == "9":
        from essay_writer.specialists.eqr import submit_pass_unlocked

        submit = submit_pass_unlocked(essay_id)
        if submit.get("unlocked") is not True:
            from essay_writer.specialists.grok_bot import attach_eqr_first_run_speech

            return attach_eqr_first_run_speech(
                refuse(
                    "eqr",
                    f"The final Word file is waiting on the reviewer. {PERSON_BLOCK}",
                    writer_clears_left=writer_clears_left(),
                    submit_pass=submit.get("reason") or "",
                    path=planned,
                    pack_digest=identity,
                    stage=stage,
                    eqr=submit.get("eqr") or "missing",
                )
            )
    elif stage == "6":
        from essay_writer.specialists.eqr import eqr_verdict

        verdict = eqr_verdict(essay_id, stage)
        if verdict != "PASS":
            from essay_writer.specialists.grok_bot import attach_eqr_first_run_speech

            return attach_eqr_first_run_speech(
                refuse(
                    "eqr",
                    f"The first Word file is waiting on the reviewer. {PERSON_BLOCK}",
                    writer_clears_left=writer_clears_left(),
                    path=planned,
                    pack_digest=identity,
                    stage=stage,
                    eqr=verdict or "missing",
                )
            )
    if stage == "9":
        # Final Word only: one look-up for a specialist source class the brief
        # names and the gathered files do not. A hit is reported, never added.
        from essay_writer.mark_fit import final_specialist_lookup

        lookup_state = load_state(essay_id)
        attempt = final_specialist_lookup(
            essay_id, pack, identity=identity, state=lookup_state
        )
        if attempt.get("attempted"):
            if not attempt.get("reused"):
                save_state(essay_id, lookup_state)
            body["specialist_lookup"] = attempt
            body["notes"] = list(body.get("notes") or []) + [
                {"code": "mark-fit-source", "reason": str(attempt.get("note") or "")}
            ]
    target = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    try:
        write_docx(essay_id, pack, report, target)
    except EmptyFooter:
        if target.is_file():
            target.unlink()
        return refuse(
            "footer",
            "The page number is missing. An empty footer is refused.",
            path=planned,
            wrote=False,
        )
    if stage in {"7", "9"}:
        from essay_writer.stage7 import rewrite_first_draft_md

        rewrite_first_draft_md(essay_id, target)
        body["draft_note_rewritten"] = True
    if stage == "7":
        body["file_work"] = "cursor"
    state = load_state(essay_id)
    state["word"][identity] = {
        "path": relative(target),
        "pack_digest": identity,
        "confirmed_at": now(),
        "files": report["files"],
    }
    state["saved_pack"] = pack
    save_state(essay_id, state)
    body["ok"] = True
    body["wrote"] = True
    body["stored"] = True
    body["path"] = relative(target)
    body["digest"] = ready["digest"]
    from essay_writer.assignment_handoff import attach_word_chat

    attach_word_chat(body, target)
    body["next"] = say("Word is written. A later change goes through revise, then validation and Word again.")
    if stage is None:
        from essay_writer.late_chain import quiet_word_step

        return quiet_word_step(body, pack)
    return body
