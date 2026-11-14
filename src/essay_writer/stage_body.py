"""Body builder for one resolved stage call.

stage_body prepares the note, fills the reply fields, attaches the reports
and the database view, and builds the stage-7 draft body. ``_build_stage_body``
returns a StageContext or a refusal. This module load-imports the shared
stage-7 skip probe from stage_confirm. It never imports the orchestrator.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from essay_writer.confirm import CONFIRM, DRAFT, refuse
from essay_writer.stage_confirm import _stage7_skip_request
from essay_writer.stage_context import StageArgs, StageContext
from essay_writer.stage_landing import (
    _attach_cite_report,
    _attach_outline_report,
    _attach_short_report,
    _collect_stage_misses,
)
from essay_writer.stage_llm import RULES_SOURCE, stage_settings, stage_title
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    _note_path,
    _payload,
    _revisit_window,
)

GUIDANCE_REASON = "Add your own sentence for this stage; the checklist alone is not a save"
GUIDANCE_NEXT = "One sentence of your own is the look. Add it in this chat, then save."


def guidance_only_refusal() -> dict[str, Any]:
    """Spoken refusal. Nothing is written and no Confirm card is returned."""
    return refuse("guidance-only", GUIDANCE_REASON, next=GUIDANCE_NEXT)


def _normalize_look(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _guidance_pieces(essay_id: str, stage: str, genre: str | None) -> list[str]:
    """Normalized guidance blocks and their lines, longest first."""
    from essay_writer.brief_contract import opening_card_lines
    from essay_writer.specialists.grok_bot import (
        CHECKLIST_WALK,
        basics_pass_lines,
        cached_approved_look,
    )
    from essay_writer.stage_llm import prompt_overlay, stage_rules

    scores, format_line, question_line = basics_pass_lines(essay_id)
    blocks = [
        "\n".join((scores, format_line, question_line)),
        scores,
        format_line,
        question_line,
        CHECKLIST_WALK,
        prompt_overlay(stage, genre),
        stage_rules(stage, genre),
    ]
    from essay_writer.stage_state import load_pointer

    saved = load_pointer(essay_id).get("saved") or []
    # A copied sequence keeps the parent's look until this sequence saves a stage.
    cached = cached_approved_look(essay_id) if saved else None
    if isinstance(cached, str) and cached.strip():
        blocks.append(cached)
    opening = [line.strip() for line in opening_card_lines(essay_id, stage) if line.strip()]
    if opening:
        blocks.append("\n".join(opening))
        blocks.extend(opening)
    pieces: list[str] = []
    for block in blocks:
        if not isinstance(block, str) or not block.strip():
            continue
        pieces.append(block)
        pieces.extend(line for line in block.splitlines() if line.strip())
    norms = {_normalize_look(piece) for piece in pieces}
    norms.discard("")
    return sorted(norms, key=len, reverse=True)


def look_is_confirmable(essay_id: str, stage: str, genre: str | None, text: str) -> bool:
    """True when the text that would be stored has a sentence of the student's own.

    Missing or blank text is not confirmable. Text that is only the Basics
    lines, the checklist walk, the stage overlay, the stage rules, the cached
    approved look, or the opening lines — joined in either order — is not
    confirmable. A remaining line that is not one of those blocks is enough.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    remaining = _normalize_look(text)
    for piece in _guidance_pieces(essay_id, stage, genre):
        if not remaining:
            break
        while piece and piece in remaining:
            start = 0
            removed = False
            while True:
                index = remaining.find(piece, start)
                if index < 0:
                    break
                end = index + len(piece)
                before = index == 0 or remaining[index - 1] == " "
                after = end == len(remaining) or remaining[end] == " "
                if before and after:
                    remaining = (remaining[:index] + " " + remaining[end:]).strip()
                    remaining = re.sub(r"\s+", " ", remaining).strip()
                    removed = True
                    break
                start = index + 1
            if not removed:
                break
    return bool(remaining)


def _prepare_stage_text(
    args: StageArgs,
    text: str,
    *,
    minting: bool,
) -> tuple[str, bool, str | None, dict[str, Any], dict[str, Any] | None]:
    """Seed the draft, then run the shared citation report before the gates."""
    from essay_writer.specialists.grok_bot import maybe_seed_basics_on_draft

    essay_id = args.essay_id
    stage = args.stage
    answers = args.answers
    edited = args.edited
    text, basics_seeded = maybe_seed_basics_on_draft(
        essay_id,
        stage,
        args.confirmPhase,
        text,
        minting=minting,
    )
    from essay_writer.cite_open import cite_look
    from essay_writer.short_cites import apply_short_cite_request
    from essay_writer.specialists.writer import BODY_CITE_STAGES, land_body_cites

    text = cite_look(essay_id, text)
    # A student ask for one or two sentences per cited point is read before the
    # gate, so a shortened stretch still has to pass claim-fit on the way out.
    short_report = apply_short_cite_request(
        essay_id,
        text,
        answers=answers if isinstance(answers, str) else None,
        edited=edited if isinstance(edited, str) else None,
        rewrite=stage in BODY_CITE_STAGES,
    )
    text = short_report["text"]
    if isinstance(edited, str):
        edited = short_report["edited"]
    cite_report = None
    if stage in BODY_CITE_STAGES:
        cite_report = land_body_cites(
            essay_id,
            stage,
            text,
            answers=answers if isinstance(answers, str) else None,
            edited=edited if isinstance(edited, str) else None,
        )
        text = cite_report["text"]
        if isinstance(edited, str):
            edited = cite_report["edited"]
        from essay_writer.outline_primary import SHORT_CITE_LIMIT, weave_short_cites

        # The student's outline is the structure, so each woven cite stays
        # short here too: no mini review is built around a gathered paper.
        text, woven = weave_short_cites(essay_id, text, SHORT_CITE_LIMIT)
        if woven:
            short_report = {
                **short_report,
                "limit": SHORT_CITE_LIMIT,
                "applied": True,
                "cut": list(short_report.get("cut") or []) + woven,
            }
    return text, basics_seeded, edited, short_report, cite_report


def _stage_body_fields(
    args: StageArgs,
    text: str,
    pointer: dict[str, Any],
    genre: str | None,
    *,
    revisit: bool,
    basics_seeded: bool,
) -> tuple[dict[str, Any], dict[str, object], dict[str, object], Path]:
    """Build the payload, fingerprint, note path, and base reply body."""
    essay_id = args.essay_id
    stage = args.stage
    item = stage_settings(stage, genre)
    payload = _payload(essay_id, stage, text)
    for key, value in (
        ("master", args.master),
        ("namedFolder", args.namedFolder),
        ("answers", args.answers),
        ("edited", args.edited),
        ("webCheck", args.webCheck),
        ("heldFile", args.heldFile),
    ):
        if value is not None:
            payload[key] = value
    fingerprint: dict[str, object] = (
        {"stage": stage, "inherited_keep": True} if _INHERITED_KEEP.get() else {"stage": stage}
    )
    note = _note_path(essay_id, stage)
    body: dict[str, Any] = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "stage_title": stage_title(stage, genre),
        "confirmPhase": args.confirmPhase,
        "rules": item["rules"],
        "source": RULES_SOURCE,
        "tracking_file": item["tracking_file"],
        "pointer_file": item["pointer_file"],
        "next_stage": item["next_stage"],
        "next_stage_title": item["next_stage_title"],
        "current": pointer["current"],
        "stored": False,
        "advanced": False,
        "closed": False,
        "submitted": False,
        "revisit": revisit,
    }
    if basics_seeded:
        body["basics_seeded"] = True
    return body, payload, fingerprint, note


def _attach_stage_reports(
    args: StageArgs,
    body: dict[str, Any],
    short_report: dict[str, Any],
    cite_report: dict[str, Any] | None,
    *,
    stage5_gate: dict[str, Any] | None,
) -> None:
    """Attach the outline, cite, basics, and host-launch report fields."""
    essay_id = args.essay_id
    stage = args.stage
    _attach_outline_report(body, essay_id, stage)
    _attach_short_report(body, short_report)
    _attach_cite_report(body, cite_report)
    if stage in {"5", "6", "7", "8"}:
        from essay_writer.encourage import student_facts

        body["student_detail"] = student_facts(essay_id)
    if stage5_gate is not None:
        body["north_star"] = stage5_gate
        body["checklist_in_chat"] = False
    if stage != "5":
        from essay_writer.specialists.grok_bot import attach_basics_pass

        shown = attach_basics_pass(essay_id)
        if shown:
            body["basics_pass"] = shown
    if stage in {"1", "3"}:
        from essay_writer.brief_contract import assignment_silence_gaps

        gaps = assignment_silence_gaps(essay_id)
        if gaps:
            body["assignment_gaps"] = gaps
    from essay_writer.cursor_office import stage_host_launch

    body["mid_office_launch"] = stage_host_launch(stage)


def _attach_stage_databases(args: StageArgs, body: dict[str, Any]) -> None:
    """Attach the database view for the stages that hold a file."""
    if args.stage not in {"1", "4a"} and args.heldFile is None:
        return
    from essay_writer.databases import database_view, remember_databases

    remember_databases(args.essay_id, args.heldFile)
    body["databases"] = database_view(args.essay_id)


def _stage7_draft_body(
    args: StageArgs,
    text: str,
    pointer: dict[str, Any],
    genre: str | None,
    body: dict[str, Any],
    payload: dict[str, object],
    short_report: dict[str, Any],
    cite_report: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None, str | None, dict[str, Any] | None]:
    """Fill the stage-7 draft reply, or return the skip or edit refusal.

    A skip asks the questions again and does not save. Answers are read into
    the note before the body is built.
    """
    essay_id = args.essay_id
    stage = args.stage
    confirm_phase = args.confirmPhase
    answers = args.answers
    edited = args.edited
    web_check = args.webCheck
    if stage == "7" and confirm_phase == DRAFT and args.card_only:
        from essay_writer.stage7 import note_questions

        body.update(note_questions(essay_id))
        return None, answers, edited, web_check
    if stage != "7" or confirm_phase != DRAFT:
        return None, answers, edited, web_check
    from essay_writer.short_cites import apply_short_cite_request
    from essay_writer.specialists.writer import BODY_CITE_STAGES, land_body_cites
    from essay_writer.stage7 import (
        answers_mean_no_change,
        load_stage7,
        note_edits,
        note_questions,
    )

    skipped = _stage7_skip_request(
        essay_id,
        stage,
        genre,
        pointer,
        confirm_phase,
        text,
        answers,
    )
    if skipped is not None:
        return skipped, answers, edited, web_check
    # A later draft whose whole note is "no changes" is the answer.
    # The door keeps the text already saved and does not invent sentences.
    if (
        answers is None
        and edited is None
        and web_check is None
        and load_stage7(essay_id).get("asked") is True
        and answers_mean_no_change(text)
    ):
        answers = text
    if answers is not None or edited is not None or web_check is not None:
        edited_note = note_edits(essay_id, answers=answers, edited=edited, web_check=web_check)
        if edited_note.get("ok") is False:
            return (
                refuse(
                    "stage",
                    str(edited_note.get("reason") or "Ask, then edit from the answers."),
                    next=edited_note.get("next"),
                    stage=stage,
                    current=pointer["current"],
                ),
                answers,
                edited,
                web_check,
            )
        answers = edited_note.get("answers", answers)
        edited = edited_note.get("edited", edited)
        web_check = edited_note.get("webCheck", web_check)
        if stage in BODY_CITE_STAGES:
            short_report = apply_short_cite_request(
                essay_id,
                text,
                answers=answers if isinstance(answers, str) else None,
                edited=edited if isinstance(edited, str) else None,
            )
            text = short_report["text"]
            if isinstance(edited, str):
                edited = short_report["edited"]
            cite_report = land_body_cites(
                essay_id,
                stage,
                text,
                answers=answers if isinstance(answers, str) else None,
                edited=edited if isinstance(edited, str) else None,
            )
            text = cite_report["text"]
            if isinstance(edited, str):
                edited = cite_report["edited"]
        payload["look"] = text
        for key, value in (
            ("answers", answers),
            ("edited", edited),
            ("webCheck", web_check),
        ):
            if value is not None:
                payload[key] = value
        body.update(edited_note)
        if isinstance(edited, str):
            body["edited"] = edited
        _attach_short_report(body, short_report)
        _attach_cite_report(body, cite_report)
    else:
        body.update(note_questions(essay_id))
    return None, answers, edited, web_check


def _build_stage_body(
    args: StageArgs,
    pointer: dict[str, Any],
    genre: str | None,
    minting: bool,
    auto_next: str | None,
) -> StageContext | dict[str, Any]:
    """Apply the gates and build the reply body for one resolved stage call.

    ``args`` is the resolved call: its look is already the normalised note.
    A refusal is returned unchanged as a dict; a buildable reply is returned
    as a StageContext for the draft or save writer.
    """
    essay_id = args.essay_id
    stage = args.stage
    confirmPhase = args.confirmPhase
    look = args.look
    text = look.strip() if isinstance(look, str) else ""
    answers = args.answers
    edited = args.edited
    webCheck = args.webCheck
    master = args.master
    namedFolder = args.namedFolder
    heldFile = args.heldFile
    card_only = args.card_only
    text, basics_seeded, edited, short_report, cite_report = _prepare_stage_text(
        args,
        text,
        minting=minting,
    )
    from essay_writer.spine import stage_uses_confirm_card

    # Card-bearing stages only. Stage 5 stores on the draft, including an empty look.
    # formatAnswer and questionAnswer are not part of this change. The predicate
    # runs only when those arguments are absent.
    answer_call = getattr(args, "formatAnswer", None) is not None or getattr(
        args, "questionAnswer", None
    ) is not None
    if (
        stage_uses_confirm_card(stage)
        and not answer_call
        and not look_is_confirmable(essay_id, stage, genre, text)
    ):
        return guidance_only_refusal()
    # A waiting-card mint is not the student's answer. Part names, Entry N,
    # and house words are checked when the student later writes that stage.
    blocked_save, stage5_gate = _collect_stage_misses(
        essay_id,
        stage,
        confirmPhase,
        text,
        pointer,
        minting=minting,
    )
    if blocked_save is not None:
        if basics_seeded:
            blocked_save["basics_seeded"] = True
        return blocked_save
    revisit = _revisit_window(pointer) and stage in {"2", "3"}
    if revisit and not text:
        return refuse(
            "stage",
            "Write what changed, or that the plan still holds, and which gathered source shows it.",
        )
    body, payload, fingerprint, note = _stage_body_fields(
        args,
        text,
        pointer,
        genre,
        revisit=revisit,
        basics_seeded=basics_seeded,
    )
    _attach_stage_reports(args, body, short_report, cite_report, stage5_gate=stage5_gate)
    _attach_stage_databases(args, body)
    if stage == "6":
        from essay_writer.late_chain import stage6_fields

        body.update(stage6_fields(essay_id, master=master, named_folder=namedFolder))
        block_master = body.pop("block_confirm", False)
        if confirmPhase == CONFIRM and block_master:
            return refuse(
                "master",
                f"Which Word file is the master copy? The place is {body['place']}. Do not guess.",
                place=body["place"],
                choices=body["choices"],
                master_ask=True,
                chain_started=False,
            )
    stage7_refusal, answers, edited, webCheck = _stage7_draft_body(
        args,
        text,
        pointer,
        genre,
        body,
        payload,
        short_report,
        cite_report,
    )
    if stage7_refusal is not None:
        return stage7_refusal
    if stage == "10" and confirmPhase == CONFIRM and pointer.get("chain_armed") is True:
        from essay_writer.spine import final_review

        eqr_blocked, verdict = final_review(essay_id)
        if eqr_blocked:
            return refuse(
                "eqr",
                eqr_blocked,
                eqr=verdict,
                blocked=True,
                chain_started=False,
            )
    real_bib = True
    if stage == "4b":
        from essay_writer.spine import stage_reconcile

        real_bib, check = stage_reconcile(essay_id)
        body["download_check"] = check
    return StageContext(
        args=args,
        essay_id=essay_id,
        stage=stage,
        genre=genre,
        pointer=pointer,
        confirmPhase=confirmPhase,
        text=text,
        look=look,
        master=master,
        namedFolder=namedFolder,
        answers=answers,
        edited=edited,
        webCheck=webCheck,
        heldFile=heldFile,
        card_only=card_only,
        minting=minting,
        auto_next=auto_next,
        revisit=revisit,
        real_bib=real_bib,
        payload=payload,
        fingerprint=fingerprint,
        body=body,
        note=note,
    )
