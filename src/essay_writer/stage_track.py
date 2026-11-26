"""Tracking note for each writing stage.

The note lives at Essay-writer/<module>/sequences/<n>/tracking/<stage>.md.
It is that stage's guidance. Draft writes the working note and does not
advance. A card pick saves the final look in the same file, then
tracking/stage.json moves to the next stage. Stage 5 stores on the
draft and starts stage 6 when the north-star gate passes and the look
is the report or essay argument. A failed gate does not store. Stage 10
does not submit.

After stage 4b is saved and before stage 5 is saved, stages 2 and 3
may be saved again. Stage 2 is only for a broken lock. A plan change
stays on stage 3. The first draft waits until that save. A broken
lock is saved on stage 2, then the plan is saved again on stage 3.

Cursor and Grok Build both read the path and the rules from
essay_writer.stage_llm.stage_settings. Only the stage state layer writes it.
The note and the pointer fields that name it are one commit under the
stage lock. A confirm clears waiting_stage and waiting_digest. It does not
mint the next stage's card, and a missing card does not roll the save back.
Stage 5 and the last stage name an advance with no card. A newer current
or saved list is left in place.

The pointer, the commit journal, and the stage lock live in
essay_writer/stage_state.py. The tracking-note renderer and look reader live
in essay_writer/stage_note.py. The held and refused reply bodies live in
essay_writer/stage_hold.py. The landing and report helpers live in
essay_writer/stage_landing.py and the draft and save reply writers in
essay_writer/stage_replies.py. The confirm path and the shared stage-7 skip
probe live in essay_writer/stage_confirm.py. The body builder lives in
essay_writer/stage_body.py. This module is the orchestrator: it imports the
state, hold, landing, reply, confirm, and body modules at module load and
keeps the public entry point.

Those modules do not import this module, at module load or at call time. The
note module does not import it either. A save that needs the next stage's card
or the current stage's card calls ``_run_card_only`` directly. The inherited-lock
keep re-enters through the private stage entry with ``inherited_keep``. The typed
stage values (StageArgs and StageContext) live in essay_writer/stage_context.py.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple, cast

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    NO_MATCHING_DRAFT,
    confirm_ready,
    latest_draft,
    load_draft_by_digest,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import relative, sequence_write_error, work_dir
from essay_writer.stage_context import ConfirmState, StageArgs, StageContext
from essay_writer.stage_llm import (
    RULES_SOURCE,
    STAGE_ORDER,
    brief_genre,
    next_stage,
    stage_settings,
    stage_title,
)
from essay_writer.stage_note import _note_look, render_tracking
from essay_writer.stage_state import (
    TOOL,
    Pointer,
    StageResult,
    _commit_pointer,
    _grant_room,
    _note_path,
    _payload,
    _revisit_window,
    _room_after_card_save,
    _room_blocks,
    _room_state,
    _saved_after_confirm,
    _waiting_digest,
    load_pointer,
)
from essay_writer.student_voice import student_surface_hits


def _continues_inherited_lock(
    essay_id: str,
    stage: str,
    inherited: str,
    text: str,
    card_digest: str | None,
) -> bool:
    """True when this call continues a revise card that already has the parent look.

    A bare later draft, with no look and no card, does not continue it.
    """
    if not inherited:
        return False
    waiting = latest_draft(essay_id, TOOL, stage=stage)
    if not isinstance(waiting, dict):
        return False
    payload = waiting.get("payload")
    look = payload.get("look") if isinstance(payload, dict) else None
    if not isinstance(look, str) or inherited.casefold() not in look.casefold():
        return False
    digest = waiting.get("digest")
    if isinstance(card_digest, str) and card_digest.strip() and card_digest.strip() == digest:
        return True
    return bool(text.strip()) and inherited.casefold() in text.casefold()


def _stage_entry(args: StageArgs, *, minting: bool, inherited_keep: bool) -> dict[str, Any]:
    """One brief-ask around a stage call. The public door and the keep re-entry share it."""
    from essay_writer.textutil import begin_brief_ask, end_brief_ask

    token = begin_brief_ask()
    try:
        return _stage_call(args, minting=minting, inherited_keep=inherited_keep)
    finally:
        end_brief_ask(token)


def essay_stage(
    essay_id: str,
    stage: str,
    confirmPhase: str | None = None,
    look: str | None = None,
    *,
    master: str | None = None,
    namedFolder: str | None = None,
    answers: str | None = None,
    edited: str | None = None,
    webCheck: dict[str, Any] | None = None,
    heldFile: str | None = None,
    cardAction: str | None = None,
    cardDigest: str | None = None,
    card_only: bool = False,
    encourageChoice: str | None = None,
    paperChoice: dict[str, Any] | None = None,
    lockChoice: str | None = None,
    formatAnswer: str | None = None,
    questionAnswer: str | None = None,
) -> dict[str, Any]:
    """A card saves the final look. Stage 5 starts stage 6."""
    return _stage_entry(
        StageArgs(
            essay_id=essay_id,
            stage=stage,
            confirmPhase=confirmPhase,
            look=look,
            master=master,
            namedFolder=namedFolder,
            answers=answers,
            edited=edited,
            webCheck=webCheck,
            heldFile=heldFile,
            cardAction=cardAction,
            cardDigest=cardDigest,
            card_only=card_only,
            encourageChoice=encourageChoice,
            paperChoice=paperChoice,
            lockChoice=lockChoice,
            formatAnswer=formatAnswer,
            questionAnswer=questionAnswer,
        ),
        minting=False,
        inherited_keep=False,
    )


def _run_card_only(
    essay_id: str,
    stage: str,
    look: str | None = None,
    *,
    minting: bool = False,
) -> dict[str, Any]:
    """The card-only stage run the state layer calls through injection.

    The next-card mint passes ``minting=True`` so the student-answer gates stay
    off that draft. Reopening an already-saved stage's card keeps the normal
    gates. The state layer never imports this module to reach it.
    """
    return _stage_call(
        StageArgs(
            essay_id=essay_id,
            stage=stage,
            confirmPhase=DRAFT,
            look=look,
            card_only=True,
        ),
        minting=minting,
        inherited_keep=False,
    )


def _inherited_keep_confirm(
    essay_id: str,
    stage: str,
    look: str,
    digest: str | None,
) -> dict[str, Any]:
    """Save a kept inherited lock through the same entry as the public door."""
    from essay_writer.specialists.grok_bot import CARD_CONFIRM

    return _stage_entry(
        StageArgs(
            essay_id=essay_id,
            stage=stage,
            confirmPhase=CONFIRM,
            look=look,
            cardAction=CARD_CONFIRM,
            cardDigest=digest,
        ),
        minting=False,
        inherited_keep=True,
    )


def _stage_call(args: StageArgs, *, minting: bool, inherited_keep: bool) -> dict[str, Any]:
    """Run one stage call. A damaged confirm record or state file stops it."""
    from essay_writer.stage_state import DAMAGED_COMMIT, DamagedStageCommit
    from essay_writer.state import DamagedState, state_file_refusal

    try:
        result = _run_stage(args, minting=minting, inherited_keep=inherited_keep)
    except DamagedStageCommit as exc:
        reason = str(exc).strip() or DAMAGED_COMMIT
        result = refuse(
            "stage",
            reason,
            wrote=False,
            stored=False,
        )
    except DamagedState:
        result = state_file_refusal()
    return result


def _turn_redirect(
    stage: str, confirm_phase: str | None, *messages: object
) -> dict[str, Any] | None:
    """Approved reply for a short ask. A stage note is not one of these."""
    from essay_writer.student_turns import redirect_for

    for message in messages:
        reply = redirect_for(message)
        if reply is not None:
            from essay_writer.stage_next import write_stage_next
            from essay_writer.student_voice import say

            refused = refuse(
                "turn",
                reply,
                stage=stage,
                confirmPhase=confirm_phase,
            )
            return write_stage_next(refused, say(reply if isinstance(reply, str) else ""))
    return None


def _run_stage(args: StageArgs, *, minting: bool, inherited_keep: bool) -> dict[str, Any]:
    """Resolve one stage call, then draft it or save it.

    The tool call arrives as StageArgs. The runner validates it, resolves the
    waiting card, and builds a StageContext for the reply writers. A refusal
    stops at the step that raised it and is returned unchanged.

    ``minting`` is true only for a card minted by ``_run_card_only``. A mint
    does not open another card.
    """
    open_card = not minting
    essay_id = args.essay_id
    stage = args.stage
    confirmPhase = args.confirmPhase
    look = args.look
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    if args.encourageChoice is not None:
        redirected = _turn_redirect(stage, confirmPhase, args.encourageChoice)
        if redirected is not None:
            return redirected
        from essay_writer.encourage import answer_encourage

        return answer_encourage(essay_id, args.encourageChoice)
    if args.paperChoice is not None:
        from essay_writer.roll_forward import choose_paper

        return choose_paper(essay_id, args.paperChoice)
    from essay_writer.fo_chat_locks import (
        inherited_lock_pending,
        lock_choice_refusal,
        prior_saved_lock_ask,
    )

    refused_choice = lock_choice_refusal(args.lockChoice)
    if refused_choice is not None:
        return refused_choice
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if stage not in STAGE_ORDER:
        return refuse(
            "stage",
            "Send a stage from 1 to 10, including 4a and 4b.",
        )
    if look is None:
        text = ""
    elif isinstance(look, str):
        text = look.strip()
    else:
        return refuse("stage", "Send the look as plain text.")
    redirected = _turn_redirect(stage, confirmPhase, text, args.answers)
    if redirected is not None:
        return redirected
    from essay_writer.state import record_damage_refusal

    damaged = record_damage_refusal(essay_id)
    if damaged:
        return damaged
    pointer = load_pointer(essay_id)
    genre = brief_genre(essay_id)
    pending_lock = inherited_lock_pending(essay_id, stage)
    blocked = _stage_refusal(cast(Pointer, pointer), stage, genre, essay_id)
    if blocked and not (minting and _mint_stage_allowed(pointer, stage)):
        if confirmPhase == CONFIRM:
            return _confirm_blocked(essay_id, pointer, stage, genre, blocked, open_card=open_card)
        return blocked
    cardAction = args.cardAction
    cardDigest = args.cardDigest
    if args.lockChoice == "keep" and pending_lock is not None:
        return _inherited_lock_keep(
            essay_id,
            stage,
            genre,
            pointer,
            pending_lock,
            run_confirm=_inherited_keep_confirm,
        )
    if args.lockChoice in {"revise", "relock"} and pending_lock is not None:
        inherited = str(pending_lock.get("look") or "").strip()
        if inherited:
            if not text.strip():
                text = inherited
            elif inherited.casefold() not in text.casefold():
                text = f"{inherited}\n{text}".strip()
        # The card minted before this choice does not carry the parent look.
        # Revise and re-lock open Confirm. They do not save that older card.
        if confirmPhase == CONFIRM and inherited:
            record = _card_record(essay_id, stage, cardDigest)
            payload = record.get("payload") if isinstance(record, dict) else None
            card_look = payload.get("look") if isinstance(payload, dict) else None
            if not isinstance(card_look, str) or inherited.casefold() not in card_look.casefold():
                confirmPhase = DRAFT
                cardAction = None
                cardDigest = None
        # The resolved note is the look from here on. The raw look no longer
        # carries anything the save needs once the inherited lock is kept.
        # The lock stays pending until a later save of this stage stores.
        look = text
    elif (
        pending_lock is not None
        and confirmPhase in {DRAFT, CONFIRM}
        and not minting
        and args.lockChoice is None
        and not args.card_only
        and not inherited_keep
        and not _continues_inherited_lock(
            essay_id,
            stage,
            str(pending_lock.get("look") or "").strip(),
            text,
            args.cardDigest,
        )
    ):
        return prior_saved_lock_ask(essay_id, stage, pending_lock)
    from essay_writer.spine import advances_without_confirm, stage_uses_confirm_card

    auto_next = advances_without_confirm(stage)
    if confirmPhase == CONFIRM and auto_next:
        from essay_writer.stage_next import write_no_card_between_next

        refused = refuse(
            "confirm-card",
            "This step moves on when the draft is stored. There is no save-card between this step and the next.",
            advanced=False,
            current=pointer["current"],
            waiting_confirm=False,
        )
        return write_no_card_between_next(refused)
    if (
        confirmPhase == CONFIRM
        and not auto_next
        and not minting
        and not cardAction
        and not cardDigest
    ):
        # Fallback for a host that cannot pass the card fields: a typed yes,
        # ok, or Confirm on a waiting card saves that card's draft. The card
        # path stays preferred, and a later stage is still its own card.
        from essay_writer.specialists.grok_bot import CARD_CONFIRM, typed_save_word

        if typed_save_word(look):
            waiting_digest = _waiting_digest(pointer, stage)
            if not waiting_digest:
                waiting = latest_draft(essay_id, TOOL, stage=stage)
                waiting_digest = waiting.get("digest") if isinstance(waiting, dict) else None
            if isinstance(waiting_digest, str) and waiting_digest:
                cardAction = CARD_CONFIRM
                cardDigest = waiting_digest
    if (
        confirmPhase == CONFIRM
        and not auto_next
        and not minting
        and _waiting_digest(pointer, stage) is None
        and latest_draft(essay_id, TOOL, stage=stage) is None
    ):
        from essay_writer.specialists.grok_bot import typed_save_word

        if (
            text
            and stage_uses_confirm_card(stage)
            and not typed_save_word(look)
            and not look_is_confirmable(essay_id, stage, genre, text)
        ):
            return guidance_only_refusal()
        return _noop_result(essay_id, stage, confirmPhase, pointer["current"])
    if (
        confirmPhase == CONFIRM
        and not minting
        and (args.formatAnswer is not None or args.questionAnswer is not None)
        and text
        and stage_uses_confirm_card(stage)
    ):
        # A waiting card saves its own draft. An answer field does not let a
        # guidance-only look through that save.
        from essay_writer.specialists.grok_bot import typed_save_word

        if not typed_save_word(look) and not look_is_confirmable(essay_id, stage, genre, text):
            return guidance_only_refusal()
    if (
        confirmPhase == DRAFT
        and not minting
        and (args.formatAnswer is not None or args.questionAnswer is not None)
    ):
        from essay_writer.assignment_gate import store_brief_answer

        outcome = store_brief_answer(essay_id, args.formatAnswer, args.questionAnswer)
        if isinstance(outcome, dict):
            return outcome
        if not look_is_confirmable(essay_id, stage, genre, text):
            from essay_writer.stage_next import answer_next, write_stage_next

            return write_stage_next(
                {
                    "ok": True,
                    "essay_id": essay_id,
                    "stage": stage,
                    "confirmPhase": DRAFT,
                    "stored": False,
                    "advanced": False,
                    "wrote": False,
                },
                answer_next(outcome[0], outcome[1]),
            )
    resolved = replace(
        args,
        confirmPhase=confirmPhase,
        look=look,
        cardAction=cardAction,
        cardDigest=cardDigest,
    )
    state = _confirm_path(
        resolved, pointer, genre, open_card=open_card, inherited_keep=inherited_keep
    )
    if not isinstance(state, ConfirmState):
        return state
    confirmPhase = state.confirmPhase
    text = state.text
    pointer = state.pointer
    answers = state.answers
    edited = state.edited
    webCheck = state.webCheck
    master = state.master
    namedFolder = state.namedFolder
    heldFile = state.heldFile
    if stage == "7" and confirmPhase == DRAFT:
        skipped = _stage7_skip_request(
            essay_id,
            stage,
            genre,
            pointer,
            confirmPhase,
            text,
            answers,
        )
        if skipped is not None:
            return skipped
    filled = replace(
        resolved,
        confirmPhase=confirmPhase,
        look=text,
        master=master,
        namedFolder=namedFolder,
        answers=answers,
        edited=edited,
        webCheck=webCheck,
        heldFile=heldFile,
    )
    body = _build_stage_body(
        filled, pointer, genre, minting, auto_next, inherited_keep=inherited_keep
    )
    if not isinstance(body, StageContext):
        return body
    if body.confirmPhase == DRAFT:
        result = _draft_reply(body)
    else:
        # A minted call is always a draft, so a save always opens a card.
        result = _save_confirm(body, cardDigest, inherited_keep=inherited_keep)
    if (
        isinstance(result, dict)
        and result.get("stored") is True
        and result.get("ok") is not False
        and pending_lock is not None
    ):
        from essay_writer.fo_chat_locks import _mark_lock_resolved

        try:
            _mark_lock_resolved(essay_id, stage)
        except OSError:
            result["notice"] = (
                "This stage was saved. The inherited lock could not be marked resolved."
            )
    return result


GUIDANCE_REASON = "Add your own sentence for this stage; the checklist alone is not a save"
GUIDANCE_NEXT = "One sentence of your own is the look. Add it in this chat, then save."


def guidance_only_refusal() -> dict[str, Any]:
    """Spoken refusal. Nothing is written and no Confirm card is returned."""
    from essay_writer.stage_next import write_stage_next

    return write_stage_next(refuse("guidance-only", GUIDANCE_REASON), GUIDANCE_NEXT)


def _normalize_look(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


def _guidance_pieces(
    essay_id: str,
    stage: str,
    genre: str | None,
    lines: tuple[str, str, str] | None = None,
) -> list[str]:
    """Normalized guidance blocks and their lines, longest first.

    ``lines`` is the opening this build already loaded. A call without them
    loads once for that ask.
    """
    from essay_writer.brief_contract import opening_card_lines
    from essay_writer.specialists.grok_bot import (
        CHECKLIST_WALK,
        cached_approved_look,
        read_basics_opening,
    )
    from essay_writer.stage_llm import prompt_overlay, stage_rules

    if lines is None:
        lines = read_basics_opening(essay_id).lines
    scores, format_line, question_line = lines
    blocks = [
        "\n".join((scores, format_line, question_line)),
        scores,
        format_line,
        question_line,
        CHECKLIST_WALK,
        prompt_overlay(stage, genre),
        stage_rules(stage, genre),
    ]
    # The cached approved look is guidance whenever it is non-empty.
    # A fresh sequence has none. A copied child keeps the parent's look
    # until it saves a stage, and that parent look is not a student sentence.
    cached = cached_approved_look(essay_id)
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


def look_is_confirmable(
    essay_id: str,
    stage: str,
    genre: str | None,
    text: str,
    lines: tuple[str, str, str] | None = None,
) -> bool:
    """True when the text that would be stored has a sentence of the student's own.

    Missing or blank text is not confirmable. Text that is only the Basics
    lines, the checklist walk, the stage overlay, the stage rules, the cached
    approved look, or the opening lines — joined in either order — is not
    confirmable. A remaining line that is not one of those blocks is enough.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    remaining = _normalize_look(text)
    for piece in _guidance_pieces(essay_id, stage, genre, lines):
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
) -> tuple[Any, bool, str | None, dict[str, Any], dict[str, Any] | None, object | None]:
    """Seed the draft, then run the shared citation report before the gates.

    The returned opening is the one brief read for this build. Stage 5 returns
    none because that stage does not read the brief here.
    """
    from essay_writer.specialists.grok_bot import maybe_seed_basics_on_draft

    essay_id = args.essay_id
    stage = args.stage
    answers = args.answers
    edited = args.edited
    text, basics_seeded, opening = maybe_seed_basics_on_draft(
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
        from essay_writer.cite_fit import carry_subject_gap
        from essay_writer.model_contract import StripReport

        carried: Any = carry_subject_gap(text, bool(cite_report.get("subject_gap")))
        text = carried.text if isinstance(carried, StripReport) and stage != "5" else carried
        if woven:
            short_report = {
                **short_report,
                "limit": SHORT_CITE_LIMIT,
                "applied": True,
                "cut": list(short_report.get("cut") or []) + woven,
            }
    return text, basics_seeded, edited, short_report, cite_report, opening


def _stage_body_fields(
    args: StageArgs,
    text: str,
    pointer: dict[str, Any],
    genre: str | None,
    *,
    revisit: bool,
    basics_seeded: bool,
    inherited_keep: bool,
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
    fingerprint: dict[str, object] = {"stage": stage}
    if inherited_keep:
        fingerprint["inherited_keep"] = True
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
    basics: object | None = None,
) -> None:
    """Attach the outline, cite, basics, and host-launch report fields.

    ``basics`` is the opening draft preparation already loaded. This does not
    read the brief again.
    """
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
    from essay_writer.specialists.grok_bot import BasicsOpening

    if stage != "5" and isinstance(basics, BasicsOpening) and basics.active:
        body["basics_pass"] = list(basics.lines)
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
            from essay_writer.stage_next import write_stage_next

            blocked = refuse(
                "stage",
                str(edited_note.get("reason") or "Ask, then edit from the answers."),
                stage=stage,
                current=pointer["current"],
            )
            chosen = edited_note.get("next")
            if isinstance(chosen, str):
                write_stage_next(blocked, chosen)
            return blocked, answers, edited, web_check
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
    *,
    inherited_keep: bool,
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
    from essay_writer.specialists.grok_bot import BasicsOpening

    if stage == "5" and not minting:
        from essay_writer.citation_list import first_write_block

        blocked = first_write_block(essay_id)
        if blocked is not None:
            blocked["stage"] = stage
            blocked["current"] = pointer.get("current")
            blocked["advanced"] = False
            from essay_writer.stage_next import write_stage_next

            reason = blocked.get("reason")
            return write_stage_next(blocked, reason if isinstance(reason, str) else "")
    text, basics_seeded, edited, short_report, cite_report, opening = _prepare_stage_text(
        args,
        text,
        minting=minting,
    )
    if stage == "5":
        from essay_writer.specialists.writer import finish_first_draft

        if not minting:
            from essay_writer.brief_contract import stage_contract_refusal
            from essay_writer.model_contract import ContractRefusal, parse_stage_draft, prose_of

            shown = prose_of(text)
            if shown.strip():
                parsed_draft = parse_stage_draft(shown)
                if isinstance(parsed_draft, ContractRefusal):
                    return refuse("draft", parsed_draft.reason)
            blocked_contract = stage_contract_refusal(essay_id, stage, shown)
            if blocked_contract:
                blocked_contract["stage"] = stage
                blocked_contract["confirmPhase"] = confirmPhase
                return blocked_contract
        finished_draft = finish_first_draft(essay_id, text)
        if finished_draft.get("ready") is True:
            written = finished_draft.get("text")
            if isinstance(written, str):
                text = written
        else:
            from essay_writer.assignment_gate import read_assignment

            named = [
                name
                for name in (read_assignment(essay_id).get("named_entries") or [])
                if isinstance(name, str) and name.strip()
            ]
            block = finished_draft.get("block")
            unreadable = isinstance(block, dict) and block.get("readable") is False
            # The named-parts check already passed. That note stays. A brief
            # with no named parts is still refused when it is short of the band.
            # A draft a citation removal left unreadable is refused either way.
            if unreadable or not named:
                if not isinstance(block, dict):
                    block = refuse(
                        "word-band",
                        "This first draft is not inside the brief's word band. "
                        "Change the draft so it fits the brief, then save again.",
                    )
                block["stage"] = stage
                block["current"] = pointer.get("current")
                block["advanced"] = False
                from essay_writer.stage_next import write_stage_next

                reason = block.get("reason")
                return write_stage_next(block, reason if isinstance(reason, str) else "")
    prepared_lines = opening.lines if isinstance(opening, BasicsOpening) else None
    from essay_writer.spine import stage_uses_confirm_card

    # Card-bearing stages only. Stage 5 stores on the draft, including an empty look.
    # An answer is stored on a draft, before this builder. A confirm does not take
    # that path, so an answer field on a confirm does not skip this gate.
    answer_call = confirmPhase == DRAFT and (
        args.formatAnswer is not None or args.questionAnswer is not None
    )
    if (
        stage_uses_confirm_card(stage)
        and not answer_call
        and not look_is_confirmable(essay_id, stage, genre, text, prepared_lines)
    ):
        # A mint is not a student save, and its card is not shown.
        if minting:
            return {"ok": False, "wrote": False, "stored": False}
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
        inherited_keep=inherited_keep,
    )
    _attach_stage_reports(
        args,
        body,
        short_report,
        cite_report,
        stage5_gate=stage5_gate,
        basics=opening,
    )
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


# A real draft was refused. Name the gap, then Confirm. The card stays.
_MISSING_SOURCE_NEXT = "Add a gathered source, then press Confirm."
_MISSING_BIBLIOGRAPHY_NEXT = "Add a bibliography, then press Confirm."


def _noop_result(
    essay_id: str,
    stage: str,
    confirmPhase: str | None,
    current: str,
) -> dict[str, Any]:
    """A confirm with no waiting card is a quiet no-op."""
    body: StageResult = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "confirmPhase": confirmPhase,
        "noop": True,
        "wrote": False,
        "stored": False,
        "advanced": False,
        "current": current,
        "closed": False,
        "submitted": False,
    }
    return dict(body)


def _draft_reply(context: StageContext) -> dict[str, Any]:
    from essay_writer.spine import stage_confirm_card

    essay_id = context.essay_id
    stage = context.stage
    genre = context.genre
    pointer = context.pointer
    body = context.body
    payload = context.payload
    fingerprint = context.fingerprint
    text = context.text
    note = context.note
    revisit = context.revisit
    real_bib = context.real_bib
    auto_next = context.auto_next
    minting = context.minting
    master = context.master
    namedFolder = context.namedFolder
    card_only = context.card_only
    if context.confirmPhase == DRAFT:
        from essay_writer.canon import digest as payload_digest

        waiting_same = None if minting or auto_next else _waiting_digest(pointer, stage)
        if (
            waiting_same is not None
            and waiting_same == payload_digest(payload)
            and _note_path(essay_id, stage).is_file()
        ):
            replay = _replay_confirm_card(essay_id, stage, genre, pointer, waiting_same)
            if replay is not None:
                body["digest"] = waiting_same
                body.update(replay)
                body["wrote"] = False
                body.pop("mid_office_launch", None)
                body.pop("status", None)
                body.pop("mid_started", None)
                from essay_writer.late_chain import finish_stage_reply

                return finish_stage_reply(
                    body,
                    essay_id,
                    stage,
                    armed=pointer.get("chain_armed") is True,
                )
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        if not auto_next and not minting:
            note_text = render_tracking(
                stage, status="draft", look=text, genre=genre, essay_id=essay_id
            )
            proposed = dict(pointer)
            proposed["waiting_stage"] = stage
            proposed["waiting_digest"] = body["digest"]
            if revisit:
                proposed["revisit_open"] = stage
                if stage == "2":
                    proposed["revisit_after_lock"] = True
            stored = _commit_pointer(
                essay_id,
                pointer,
                proposed,
                note=note,
                note_text=note_text,
            )
            if stored is None:
                return _pointer_lost(essay_id, stage, genre, open_card=not context.minting)
            pointer = stored
        body["wrote"] = not minting
        if not minting:
            body["tracking_path"] = relative(note)
        if stage == "4b" and not real_bib:
            line = (
                "Stage 4a has no bibliography yet. "
                "Stay on the annotated list. Do not go on to the next stage."
            )
        else:
            line = _confirm_line(stage, genre, revisit=revisit)
            if stage == "4b":
                line += " Option C: Download leftovers first."
        body["confirm_line"] = line
        if not card_only:
            _attach_mid_run(body, essay_id, stage)
            from essay_writer.roll_forward import attach_stage_roll

            attach_stage_roll(body, essay_id, stage)
        if auto_next:
            return _store_stage(
                body,
                essay_id,
                stage,
                text,
                genre,
                pointer,
                note,
                digest=body["digest"],
                master=master,
                named_folder=namedFolder,
                open_card=not context.minting,
            )
        from essay_writer.specialists.grok_bot import confirm_reply_fields
        from essay_writer.stage_next import write_draft_stage_next

        # A stage 7 draft that has not been edited asks the questions, and that
        # ask is the student's next action whether or not a mid step started.
        # The wait line never replaces it: the ask names the all-fine answer and
        # the card the door already returned, so the ask comes first.
        write_draft_stage_next(body, stage=stage, essay_id=essay_id)
        body["card"] = stage_confirm_card(
            essay_id,
            stage,
            body["digest"],
            line,
            stage_title=body["stage_title"],
        )
        body.update(confirm_reply_fields(body["digest"]))
        from essay_writer.late_chain import finish_stage_reply

        return finish_stage_reply(
            body,
            essay_id,
            stage,
            armed=pointer.get("chain_armed") is True,
        )
    raise AssertionError("draft path returned nothing")


def _save_confirm(
    context: StageContext,
    cardDigest: str | None,
    *,
    inherited_keep: bool,
) -> dict[str, Any]:
    essay_id = context.essay_id
    stage = context.stage
    genre = context.genre
    pointer = context.pointer
    body = context.body
    payload = context.payload
    fingerprint = context.fingerprint
    text = context.text
    note = context.note
    revisit = context.revisit
    real_bib = context.real_bib
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            cardDigest,
            code="confirm",
            reason=str(ready.get("reason") or NO_MATCHING_DRAFT),
        )
    if cardDigest != ready.get("digest"):
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            None,
            reason="That card does not match this draft. Show the draft card again.",
        )
    if not inherited_keep and _stale_confirm_body(
        essay_id, stage, pointer, ready.get("digest"), text
    ):
        return _older_card(essay_id, stage, genre, pointer)
    if stage == "4a":
        from essay_writer.roll_forward import pending_choice_reason

        pending = pending_choice_reason(essay_id)
        if pending:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="papers",
                reason=pending,
            )
        from essay_writer.spine import stage_bibliography

        delivery = stage_bibliography(essay_id)
        if delivery is None:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="stage",
                reason=(
                    "Stage 4a stays here until a gathered source is on the list. "
                    "Nothing was saved and the stage did not advance."
                ),
                lead=_MISSING_SOURCE_NEXT,
            )
        if isinstance(delivery, dict) and delivery.get("ok") is False:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code=str(delivery.get("refused") or "annotation-prose"),
                reason=str(delivery.get("reason") or "The annotation needs full sentences."),
            )
        body["delivery"] = delivery
    if stage == "4b" and not real_bib:
        return _reoffer_confirm(
            essay_id,
            stage,
            genre,
            pointer,
            cardDigest,
            code="stage",
            reason=(
                "Stage 4b stays here until stage 4a has a bibliography. "
                "Nothing was saved and the stage did not advance."
            ),
            lead=_MISSING_BIBLIOGRAPHY_NEXT,
        )
    if stage == "4b":
        from essay_writer.spine import stage_critical_reviews

        delivery = stage_critical_reviews(essay_id)
        if delivery is None:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="stage",
                reason=(
                    "Stage 4b stays here until stage 4a has a bibliography. "
                    "Nothing was saved and the stage did not advance."
                ),
                lead=_MISSING_BIBLIOGRAPHY_NEXT,
            )
        body["delivery"] = delivery
        body["delivery_speech"] = "4b"
        from essay_writer.citation_list import unfinished_stage_reason

        pending = unfinished_stage_reason(essay_id)
        if pending:
            return _reoffer_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                cardDigest,
                code="citation-list",
                reason=pending,
            )
    note_text = render_tracking(stage, status="final", look=text, genre=genre, essay_id=essay_id)
    rel = relative(note)
    saved = _saved_after_confirm(pointer, stage)
    room = _room_after_card_save(pointer, stage)
    files = dict(pointer["files"])
    files[stage] = rel
    following = next_stage(stage)
    if revisit:
        updated = {
            "current": "5",
            "saved": saved,
            "files": files,
            "closed": False,
            "revisit_open": None,
            "revisit_after_lock": stage == "2",
            "chain_armed": pointer.get("chain_armed") is True,
            "waiting_stage": None,
            "waiting_digest": None,
            **room,
        }
        committed = _commit_saved_stage(
            body,
            essay_id,
            stage,
            genre,
            pointer,
            updated,
            note,
            note_text,
            digest=ready["digest"],
            open_card=True,
            cache_look=text,
        )
        if committed.pointer is None:
            return committed.body
        updated = committed.pointer
        body["advanced"] = False
        body["closed"] = False
        body["revisit"] = True
        body["current"] = "5"
        from essay_writer.stage_next import write_revisit_stage_next

        if stage == "2":
            body["next_stage"] = "3"
            body["next_stage_title"] = stage_title("3", genre)
        else:
            body["next_stage"] = "5"
            body["next_stage_title"] = stage_title("5", genre)
        write_revisit_stage_next(body, stage=stage, genre=genre)
        finished = _mark_explicit_end(_with_plan_encourage(body, essay_id, stage, text))
        _snapshot_stage_save(essay_id, stage, text, finished)
        return finished
    updated = {
        "current": following if following else stage,
        "saved": saved,
        "files": files,
        "closed": following is None,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": _late_armed(pointer, stage, essay_id),
        **room,
    }
    if stage == "1":
        from essay_writer.first_run import ensure_sequence_mac_folder

        body["sequence_mac_folder"] = ensure_sequence_mac_folder(essay_id)
    return _commit_with_next_card(
        body,
        essay_id,
        stage,
        genre,
        pointer,
        updated,
        note,
        note_text,
        following,
        ready.get("digest") if isinstance(ready.get("digest"), str) else None,
        text if stage == "3" else None,
        approved_look=text,
        open_card=True,
    )


InheritedConfirm = Callable[[str, str, str, str | None], dict[str, object]]


def _late_armed(pointer: dict[str, Any], stage: str, essay_id: str) -> bool:
    from essay_writer.stage7 import stage7_edited

    armed = pointer.get("chain_armed") is True
    if stage == "7" and stage7_edited(essay_id):
        armed = True
    return armed


def _open_stage6(
    body: dict[str, object],
    essay_id: str,
    *,
    master: str | None,
    named_folder: str | None,
) -> dict[str, object]:
    """Stage 6 fields for the reply. This does not write stage 6's note."""
    from essay_writer.late_chain import stage6_fields

    fields = stage6_fields(essay_id, master=master, named_folder=named_folder)
    body["started"] = {
        "stage": "6",
        "stage_title": stage_title("6", brief_genre(essay_id)),
        "place": fields["place"],
        "master_ask": fields["master_ask"],
        "choices": fields["choices"],
        "expected_draft": fields["expected_draft"],
        "chain_started": False,
    }
    body.pop("card", None)
    return body


def _attach_outline_report(body: dict[str, object], essay_id: str, stage: str) -> None:
    """Name the student outline the draft follows. Stages 3 to 6 only."""
    if stage not in {"3", "4a", "4b", "5", "6"}:
        return
    from essay_writer.outline_primary import outline_speech, read_outline

    outline = read_outline(essay_id)
    if outline is None:
        return
    body["student_outline"] = {
        "headings": list(outline.get("headings") or []),
        "files": list(outline.get("files") or []),
    }
    line = outline_speech(essay_id)
    if line:
        body["student_outline_line"] = line


def _attach_short_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    """Say the cite length the student asked for. An untouched body stays quiet."""
    if not isinstance(report, dict):
        return
    limit = report.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        body.pop("cite_short", None)
        return
    raw_cut = report.get("cut")
    cut = raw_cut if isinstance(raw_cut, list) else []
    if report.get("applied") is not True and not cut and report.get("asked") is not True:
        body.pop("cite_short", None)
        return
    body["cite_short"] = {"limit": limit, "cut": len(cut)}
    from essay_writer.cite_fit import in_line
    from essay_writer.short_cites import short_line

    body["cite_short_line"] = short_line(limit)
    in_line(body, "cite_short_line")


def _attach_cite_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    """Ask and held cites from the shared writer gate. Empty stays off the reply."""
    if not isinstance(report, dict):
        return
    held = report.get("held")
    if isinstance(held, list) and held:
        body["cite_held"] = held
    else:
        body.pop("cite_held", None)
    ask = report.get("ask")
    if isinstance(ask, str) and ask.strip():
        body["cite_ask"] = ask
    else:
        body.pop("cite_ask", None)
    gap = report.get("gap")
    if isinstance(gap, str) and gap.strip():
        body["cite_gap"] = gap
    else:
        body.pop("cite_gap", None)


class _SavedStage(NamedTuple):
    pointer: dict[str, Any] | None
    body: dict[str, Any]


def _commit_saved_stage(
    body: dict[str, Any],
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    updated: dict[str, Any],
    note,
    note_text: str,
    *,
    digest: Any,
    open_card: bool,
    cache_look: str | None = None,
) -> _SavedStage:
    """Commit the note and pointer. A lost pointer returns the refusal."""
    stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
    if stored is None:
        lost = _pointer_lost(essay_id, stage, genre, open_card=open_card)
        return _SavedStage(None, lost)
    if cache_look is not None:
        _cache_approved_look(essay_id, stage, cache_look)
    body["wrote"] = True
    body["stored"] = True
    body["digest"] = digest
    body["tracking_path"] = relative(note)
    body["current"] = stored["current"]
    return _SavedStage(stored, body)


def _store_stage(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    text: str,
    genre: str | None,
    pointer: dict[str, Any],
    note,
    *,
    digest: str,
    master: str | None,
    named_folder: str | None,
    open_card: bool,
) -> dict[str, object]:
    """Store one stage that has no card between it and the next."""
    note_text = render_tracking(stage, status="final", look=text, genre=genre, essay_id=essay_id)
    rel = relative(note)
    saved = _saved_after_confirm(pointer, stage)
    files = dict(pointer["files"])
    files[stage] = rel
    following = next_stage(stage)
    updated = {
        "current": following if following else stage,
        "saved": saved,
        "files": files,
        "closed": following is None,
        "revisit_open": None,
        "revisit_after_lock": False,
        "chain_armed": _late_armed(pointer, stage, essay_id),
        "waiting_stage": None,
        "waiting_digest": None,
        **_room_state(pointer),
    }
    committed = _commit_saved_stage(
        body,
        essay_id,
        stage,
        genre,
        pointer,
        updated,
        note,
        note_text,
        digest=digest,
        open_card=open_card,
    )
    if committed.pointer is None:
        return committed.body
    updated = committed.pointer
    body["advanced"] = following is not None
    body["closed"] = following is None
    body.pop("card", None)
    from essay_writer.stage_next import write_following_stage_next

    following_title = stage_title(following, genre) if following else ""
    write_following_stage_next(body, following, following_title)
    from essay_writer.late_chain import finish_stage_reply, quiet_stage5

    finished = finish_stage_reply(
        body,
        essay_id,
        stage,
        armed=updated.get("chain_armed") is True,
    )
    if stage == "5":
        finished = quiet_stage5(finished, essay_id)
    finished = _mark_explicit_end(finished)
    _snapshot_stage_save(essay_id, stage, text, finished)
    if following == "6":
        return _open_stage6(finished, essay_id, master=master, named_folder=named_folder)
    return finished


_MID_RUN_STAGES = frozenset({"4a", "4b", "5", "6", "7", "8", "9", "10"})


def _attach_mid_run(body: dict[str, Any], essay_id: str, stage: str) -> None:
    """Arm a mid session only when Cursor CLI or Grok Build actually starts.

    Stage 4b research is skipped only when every kept paper already has a
    critical note. Cursor and Grok Build share this decision.
    """
    if stage not in _MID_RUN_STAGES:
        return
    from essay_writer.cursor_office import start_4a_research, start_stage_mid
    from essay_writer.roll_forward import four_b_action

    if stage == "4b":
        action = four_b_action(essay_id)
        if action == "skip":
            body["roll_forward_4b"] = "skip"
            return
        if action == "research":
            body["roll_forward_4b"] = "research"
    if stage == "4a":
        started = start_4a_research(essay_id, launch=body.get("mid_office_launch"))
    else:
        started = start_stage_mid(essay_id, stage, launch=body.get("mid_office_launch"))
    if stage == "4a":
        host = body.get("mid_office_launch")
        if isinstance(host, dict):
            host["research"] = {
                "runner": started.get("runner", ""),
                "command": started.get("command", []),
                "started": started.get("started", False),
                "reason": started.get("reason", ""),
                "heartbeat_seconds": started.get("heartbeat_seconds"),
            }
    if started.get("status"):
        body["status"] = started["status"]
    if started.get("started"):
        body["mid_started"] = True


def _miss_record(body: dict[str, object]) -> dict[str, Any]:
    item: dict[str, object] = {"code": body.get("refused"), "reason": body.get("reason")}
    words = body.get("words")
    if isinstance(words, list) and words:
        item["words"] = list(words)
    return item


def _join_stage_misses(found: list[dict[str, Any]]) -> dict[str, Any]:
    """One refuse that names every current miss. A single miss keeps its own reply."""
    misses = [_miss_record(body) for body in found]
    reasons = [
        str(item["reason"])
        for item in misses
        if isinstance(item.get("reason"), str) and item["reason"]
    ]
    words: list[str] = []
    for item in misses:
        for word in item.get("words") or []:
            if word not in words:
                words.append(word)
    extra: dict[str, Any] = {"misses": misses, "advanced": False}
    if words:
        extra["words"] = words
    return refuse("misses", " ".join(reasons), **extra)


def _collect_stage_misses(
    essay_id: str,
    stage: str,
    confirmPhase: str | None,
    text: str,
    pointer: dict[str, Any],
    *,
    minting: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Every current save block. One code returns that reply unchanged."""
    found: list[dict[str, Any]] = []

    def add(body: dict[str, Any] | None) -> None:
        if not isinstance(body, dict):
            return
        code = body.get("refused")
        if not isinstance(code, str) or any(item.get("refused") == code for item in found):
            return
        found.append(body)

    if not minting and student_surface_hits(text):
        add(
            refuse(
                "house-jargon",
                "That note uses an internal label. Say it in plain words.",
                words=student_surface_hits(text),
            )
        )
    if not minting:
        from essay_writer.brief_contract import stage_contract_refusal

        blocked_contract = stage_contract_refusal(essay_id, stage, text)
        if blocked_contract:
            blocked_contract["stage"] = stage
            blocked_contract["confirmPhase"] = confirmPhase
            add(blocked_contract)
    from essay_writer.specialists.grok_bot import basics_pass_block, delivery_file_only
    from essay_writer.spine import gate_save, north_star

    def take_basics_refusal() -> None:
        blocked_pass = basics_pass_block(essay_id, text)
        if not blocked_pass:
            return
        blocked_pass["stage"] = stage
        blocked_pass["confirmPhase"] = confirmPhase
        add(blocked_pass)

    # Wording and contract misses are already recorded. A file-name-only note
    # takes this refusal before the assignment gate. Every other note takes it
    # after that gate. Stage 5 does not take it. The note is not rewritten.
    file_only = stage != "5" and delivery_file_only(text)
    if file_only:
        take_basics_refusal()
    stage5_gate = None
    if stage == "5":
        from essay_writer.draft_from_review import stage5_draft_blockers

        stage5_gate = north_star(essay_id, text)
        stage5_blockers = stage5_draft_blockers(essay_id, text)
        if stage5_gate.get("passed") is not True or stage5_blockers:
            add(_stage5_held(pointer, stage5_gate, stage5_blockers))
    else:
        add(gate_save(essay_id, text))
    if stage != "5" and not file_only:
        take_basics_refusal()
    if not found:
        return None, stage5_gate
    if len(found) == 1:
        return found[0], stage5_gate
    return _join_stage_misses(found), stage5_gate


def _inherited_lock_keep(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    row: dict[str, Any],
    *,
    run_confirm: InheritedConfirm,
) -> dict[str, Any]:
    """Keep continues the parent save without showing Confirm again.

    ``run_confirm`` is the public stage runner injected by the orchestrator.
    This module does not import it, so the landing layer never depends on the
    orchestrator.
    """
    text = str(row.get("look") or "").strip()
    if not text:
        return refuse("lock-choice", "The inherited lock is empty. Revise instead.")
    if pointer.get("waiting_stage") == stage:
        cleared = dict(pointer)
        cleared["waiting_stage"] = None
        cleared["waiting_digest"] = None
        refreshed = _commit_pointer(essay_id, pointer, cleared, note=None, note_text=None)
        if refreshed is not None:
            pointer = refreshed
    blocked_save, _stage5_gate = _collect_stage_misses(
        essay_id,
        stage,
        CONFIRM,
        text,
        pointer,
        minting=False,
    )
    if blocked_save is not None:
        return blocked_save
    payload = _payload(essay_id, stage, text)
    fingerprint = {"stage": stage, "inherited_keep": True}
    digest = save_draft(essay_id, TOOL, payload, fingerprint)
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        return ready
    saved = run_confirm(
        essay_id,
        stage,
        text,
        digest if isinstance(digest, str) else ready.get("digest"),
    )
    if isinstance(saved, dict):
        saved["inherited_keep"] = True
        saved["prior_saved_lock"] = {
            "stage": row.get("stage"),
            "title": row.get("title"),
            "essay_id": row.get("essay_id"),
        }
        if saved.get("stored") is True:
            saved.pop("card", None)
            saved.pop("cardAction", None)
            saved.pop("cardDigest", None)
            saved["waiting_confirm"] = False
    return saved


def _confirm_path(
    args: StageArgs,
    pointer: dict[str, Any],
    genre: str | None,
    *,
    open_card: bool,
    inherited_keep: bool,
) -> ConfirmState | dict[str, Any]:
    """Resolve the confirm phase against the waiting card.

    A refusal is returned unchanged as a dict. The resolved fields come back
    as a ConfirmState and are fed to the body builder.
    """
    from essay_writer.spine import accept_stage_card

    essay_id = args.essay_id
    stage = args.stage
    confirmPhase = args.confirmPhase
    look = args.look
    text = look.strip() if isinstance(look, str) else ""
    cardAction = args.cardAction
    cardDigest = args.cardDigest
    master = args.master
    namedFolder = args.namedFolder
    answers = args.answers
    edited = args.edited
    webCheck = args.webCheck
    heldFile = args.heldFile
    if confirmPhase == CONFIRM:
        from essay_writer.specialists.grok_bot import (
            CARD_CONFIRM,
            press_confirm_stage,
            typed_save_word,
        )
        from essay_writer.stage7 import answers_mean_no_change

        named = press_confirm_stage(cardAction)
        if named is None:
            named = press_confirm_stage(look)
        press_target = None
        if named is not None:
            press_target = stage if named == "" else named
        card_record = _card_record(essay_id, stage, cardDigest)
        card_matches = cardAction == CARD_CONFIRM and card_record is not None
        probe = look if isinstance(look, str) else ""
        answer_text = answers if isinstance(answers, str) else ""
        if stage == "7":
            skipped = _stage7_skip_request(
                essay_id,
                stage,
                genre,
                pointer,
                confirmPhase,
                probe,
                answer_text,
            )
            if skipped is not None:
                return skipped
        # "All fine" is the answer. A waiting card copied into that same call does not save.
        stage7_no_change = stage == "7" and (
            answers_mean_no_change(probe) or answers_mean_no_change(answer_text)
        )
        no_card_no_change = (not card_matches) and (
            answers_mean_no_change(probe) or answers_mean_no_change(answer_text)
        )
        if stage7_no_change or no_card_no_change:
            # "All fine" opens the Confirm card. It does not save on this call.
            confirmPhase = DRAFT
            if answers is None and answers_mean_no_change(probe):
                answers = probe
            waiting = latest_draft(essay_id, TOOL, stage=stage)
            saved_look = None
            if isinstance(waiting, dict):
                payload = waiting.get("payload")
                if isinstance(payload, dict) and isinstance(payload.get("look"), str):
                    saved_look = payload["look"]
            if (
                isinstance(saved_look, str)
                and saved_look.strip()
                and not answers_mean_no_change(saved_look)
            ):
                text = saved_look.strip()
                look = text
        else:
            if not inherited_keep and _superseded_card(essay_id, stage, pointer, cardDigest):
                return _older_card(essay_id, stage, genre, pointer)
            if press_target is not None and press_target != stage:
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason=(
                        f"That press is for Stage {press_target} only. "
                        f"It does not save Stage {stage}. "
                        f"Open the Confirm card for Stage {stage}."
                    ),
                )
            granted_here = False
            if press_target == stage and card_matches:
                # One press plus the waiting card saves this stage only.
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre, open_card=open_card)
                pointer = stored_room
                look = None
                text = ""
                granted_here = True
            elif press_target == stage:
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre, open_card=open_card)
                pointer = stored_room
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason="Open the Confirm card in this reply to save this step.",
                )
            if not card_matches or (_room_blocks(pointer, stage) and not granted_here):
                if not card_matches:
                    picked_card = accept_stage_card(cardAction)
                    if picked_card:
                        return _reoffer_confirm(
                            essay_id,
                            stage,
                            genre,
                            pointer,
                            cardDigest,
                            reason=str(
                                picked_card.get("reason")
                                or "Open the Confirm card in this reply to save this step."
                            ),
                        )
                if _room_blocks(pointer, stage):
                    return _reoffer_confirm(
                        essay_id,
                        stage,
                        genre,
                        pointer,
                        cardDigest,
                        reason=(
                            f"Stage {stage} needs its own Confirm card. "
                            "The earlier card does not save this stage."
                        ),
                    )
            if typed_save_word(look):
                look = None
                text = ""
            omitted_look = look is None or (isinstance(look, str) and not look.strip())
            if card_record is None and omitted_look:
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason="That card does not match this draft. Show the draft card again.",
                )
        if confirmPhase == CONFIRM:
            if card_matches:
                answers = None
                edited = None
                webCheck = None
                look = None
                text = ""
            text, filled = _hydrate_card(
                text,
                look,
                card_record,
                {
                    "master": master,
                    "namedFolder": namedFolder,
                    "answers": answers,
                    "edited": edited,
                    "webCheck": webCheck,
                    "heldFile": heldFile,
                },
            )
            master = filled["master"]
            namedFolder = filled["namedFolder"]
            answers = filled["answers"]
            edited = filled["edited"]
            webCheck = filled["webCheck"]
            heldFile = filled["heldFile"]
    return ConfirmState(
        confirmPhase=confirmPhase,
        text=text,
        pointer=pointer,
        master=master,
        namedFolder=namedFolder,
        answers=answers,
        edited=edited,
        webCheck=webCheck,
        heldFile=heldFile,
    )


def _stage7_skip_request(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    confirm_phase: str,
    text: str | None,
    answers: str | None,
) -> dict[str, Any] | None:
    """The stage-7 skip reply when the look or answers only ask to skip.

    A skip does not save. The reply asks the questions again. The draft,
    confirm, and body paths all read this one probe.
    """
    if stage != "7":
        return None
    from essay_writer.stage7 import answers_mean_skip

    if not (answers_mean_skip(text) or answers_mean_skip(answers)):
        return None
    return _stage7_skip_reply(essay_id, stage, genre, pointer, confirm_phase)


def _own_door_card(
    opened: dict[str, object] | None, essay_id: str, stage: str
) -> dict[str, object] | None:
    """The door card when it names this sequence and this stage."""
    if not isinstance(opened, dict) or opened.get("ok") is False:
        return None
    card = opened.get("card")
    if not isinstance(card, dict) or card.get("kind") != "confirm":
        return None
    if card.get("essay_id") != essay_id or card.get("stage") != stage:
        return None
    digest = opened.get("cardDigest") or card.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        return None
    if card.get("digest") not in (None, digest):
        return None
    return opened


def door_card_reply(essay_id: str) -> dict[str, object] | None:
    """Confirm card for this sequence's open stage.

    A fresh stage 1, with nothing saved, gets that stage's door card.
    Roll-forward starts the child on stage 1 and returns that card.
    A card from another sequence is not returned.
    """
    from essay_writer.spine import stage_uses_confirm_card

    pointer = load_pointer(essay_id)
    if pointer.get("closed") is True:
        return None
    current = pointer.get("current")
    if not isinstance(current, str) or not stage_uses_confirm_card(current):
        return None
    saved = pointer.get("saved") or []
    if current in saved:
        return None
    replay = _replay_confirm_card(essay_id, current, brief_genre(essay_id), pointer, None)
    own = _own_door_card(replay, essay_id, current)
    if own is not None:
        return own
    if current == "1" and not saved:
        return _own_door_card(_draft_next_card(essay_id, "1"), essay_id, "1")
    return None


def _pointer_lost(
    essay_id: str,
    stage: str,
    genre: str | None,
    *,
    open_card: bool,
) -> dict[str, object]:
    """The pointer moved after this call read it. The newer pointer stays."""
    fresh = load_pointer(essay_id)
    blocked = _stage_refusal(cast(Pointer, fresh), stage, genre, essay_id)
    if blocked is not None:
        return _confirm_blocked(essay_id, fresh, stage, genre, blocked, open_card=open_card)
    return refuse(
        "pointer",
        f"This step was saved in another chat. The current stage is {fresh['current']}.",
        current=fresh["current"],
        stage=stage,
        waiting_confirm=True,
        stored=False,
        advanced=False,
        wrote=False,
    )


def _confirm_blocked(
    essay_id: str,
    pointer: dict[str, Any],
    stage: str,
    genre: str | None,
    blocked: dict[str, object],
    *,
    open_card: bool,
) -> dict[str, object]:
    """An already-saved stage does not replay its card. The draft card is for current."""
    from essay_writer.spine import stage_uses_confirm_card

    current = pointer["current"]
    blocked["waiting_confirm"] = False
    blocked["stored"] = False
    blocked["advanced"] = False
    blocked["repost"] = False
    blocked.pop("card", None)
    blocked.pop("cardAction", None)
    blocked.pop("cardDigest", None)
    saved = pointer.get("saved") or []
    if pointer.get("closed") is True or current in saved:
        from essay_writer.stage_next import write_closed_stage_next

        return write_closed_stage_next(blocked)
    opened = None
    if stage_uses_confirm_card(current) and current != stage:
        opened = _replay_confirm_card(essay_id, current, genre, pointer, None)
        if opened is None and open_card:
            opened = _run_card_only(essay_id, current, None, minting=False)
    opened_reply = opened if isinstance(opened, dict) else None
    card = opened_reply.get("card") if isinstance(opened_reply, dict) else None
    digest = opened_reply.get("cardDigest") if isinstance(opened_reply, dict) else None
    if (
        isinstance(opened_reply, dict)
        and isinstance(card, dict)
        and card.get("essay_id") == essay_id
        and card.get("stage") == current
        and card.get("stage") != stage
        and opened_reply.get("cardAction") == "confirm"
        and isinstance(digest, str)
        and len(digest) == 64
    ):
        blocked["card"] = card
        if opened_reply.get("cardAction"):
            blocked["cardAction"] = opened_reply["cardAction"]
        if opened_reply.get("cardDigest"):
            blocked["cardDigest"] = opened_reply["cardDigest"]
        from essay_writer.stage_next import write_blocked_card_next

        return write_blocked_card_next(
            blocked,
            opened_reply.get("next"),
            stage=current,
            title=stage_title(current, genre),
        )
    from essay_writer.specialists.grok_bot import missing_confirm_next
    from essay_writer.stage_next import write_stage_next

    return write_stage_next(blocked, missing_confirm_next(current, stage_title(current, genre)))


def _opening_look(essay_id: str) -> str:
    """A next-stage draft the assignment check can hold. Daily use stays empty."""
    from essay_writer.specialists.grok_bot import (
        attach_basics_pass,
        cached_approved_look,
    )

    cached = cached_approved_look(essay_id)
    if cached:
        return cached
    lines = attach_basics_pass(essay_id)
    if not lines:
        return ""
    return "\n".join(lines)


def _next_card_look(essay_id: str, stage: str) -> str:
    """Opening note the next Confirm card can save. The brief's own names stay in it."""
    from essay_writer.brief_contract import opening_card_lines

    lines: list[str] = []
    opening = _opening_look(essay_id)
    if opening:
        lines.extend(line for line in opening.splitlines() if line)
    text = "\n".join(lines)
    for extra in opening_card_lines(essay_id, stage):
        if extra.casefold() not in text.casefold():
            lines.append(extra)
            text = "\n".join(lines)
    return "\n".join(lines)


def _draft_next_card(essay_id: str, following: str) -> dict[str, object]:
    """One card-only draft of the next stage. It does not move the pointer.

    Student-answer rules (part names, Entry N, house words) stay off this mint.
    They run when the student later writes that stage.
    """
    return _run_card_only(
        essay_id,
        following,
        _next_card_look(essay_id, following),
        minting=True,
    )


def _pending_inherited(essay_id: str, stage: str | None) -> dict[str, object] | None:
    """Parent save still waiting on a copied stage 2 or 3."""
    if not stage:
        return None
    from essay_writer.fo_chat_locks import inherited_lock_pending

    return inherited_lock_pending(essay_id, stage)


def _name_inherited_lock(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    row: dict[str, object],
) -> dict[str, object]:
    """Name the parent save. This reply does not carry a Confirm card."""
    from essay_writer.fo_chat_locks import prior_saved_lock_ask

    ask = prior_saved_lock_ask(essay_id, stage, row)
    body.pop("card", None)
    body.pop("cardAction", None)
    body.pop("cardDigest", None)
    body.pop("explicit_end", None)
    from essay_writer.stage_next import write_stage_next

    inherited = ask.get("next")
    write_stage_next(body, inherited if isinstance(inherited, str) else "")
    body["prior_saved_lock"] = ask["prior_saved_lock"]
    body["inherited_lock_preview"] = ask["inherited_lock_preview"]
    body["lock_choices"] = ask["lock_choices"]
    body["waiting_confirm"] = False
    return body


def _expects_next_card(following: str | None) -> bool:
    """True when this advance must carry the next stage's Confirm card."""
    from essay_writer.spine import stage_uses_confirm_card

    return bool(following) and stage_uses_confirm_card(following or "")


def _mint_stage_allowed(pointer: dict[str, Any], stage: str) -> bool:
    """The next card may be minted while the pointer is still on the stage being confirmed."""
    if pointer.get("closed") is True or stage in (pointer.get("saved") or []):
        return False
    current = pointer.get("current")
    if current not in STAGE_ORDER:
        return False
    return next_stage(current) == stage


def _hold_confirm(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
    opened: dict[str, Any] | None,
    following: str,
) -> dict[str, object]:
    """The next card was not minted. The pointer and the waiting card stay."""
    reason = "The next Confirm card was not returned. This step was not saved."
    code = "card"
    if isinstance(opened, dict):
        if isinstance(opened.get("reason"), str) and opened["reason"].strip():
            reason = f"{opened['reason'].strip()} This step was not saved."
        if isinstance(opened.get("refused"), str) and opened["refused"].strip():
            code = opened["refused"].strip()
    held = _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        card_digest,
        code=code,
        reason=reason,
    )
    held["next_card_stage"] = following
    held["advanced"] = False
    held["stored"] = False
    return held


def _attach_minted_card(
    body: dict[str, object],
    opened: dict[str, object],
    fields: dict[str, object],
) -> dict[str, object]:
    """Put the already-minted next card on a confirm that has been stored."""
    body["repost"] = False
    body["card"] = fields["card"]
    body["cardAction"] = fields["cardAction"]
    body["cardDigest"] = fields["cardDigest"]
    chain = body.get("next_run") or body.get("blocked") or body.get("final_word")
    nxt = opened.get("next")
    if not chain and isinstance(nxt, str) and nxt.strip():
        from essay_writer.stage_next import write_stage_next

        write_stage_next(body, nxt)
    if "status" not in body:
        status = opened.get("status")
        if isinstance(status, list) and any(isinstance(line, str) and line for line in status):
            body["status"] = [line for line in status if isinstance(line, str) and line]
    questions = opened.get("questions")
    if isinstance(questions, list) and questions:
        body["questions"] = questions
    return body


def _mark_explicit_end(body: dict[str, object]) -> dict[str, object]:
    """Stage 5 and the last stage advance with no Confirm card. That end is named."""
    body["repost"] = False
    body.pop("card", None)
    body.pop("cardAction", None)
    body.pop("cardDigest", None)
    body["explicit_end"] = True
    return body


def _render_stage10_before_close(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> dict[str, object] | None:
    """Write the graded sequence file before the pointer can close.

    A missing registration number or an empty footer keeps the Confirm card
    and leaves the sequence closed flag false. The tracking note is not
    recorded as final.
    """
    from essay_writer.late_chain import write_stage10

    rendered = write_stage10(essay_id)
    written = rendered.pop("sequence_written", False) is True and rendered.get("ok") is True
    if written:
        body["final_word"] = rendered
        delivery = rendered.get("delivery")
        if isinstance(delivery, dict):
            body["delivery"] = delivery
        return None
    reason_raw = rendered.get("reason")
    reason = reason_raw if isinstance(reason_raw, str) else ""
    if not reason.strip():
        reason = "The final Word file was not written. This step was not saved."
    code_raw = rendered.get("refused")
    code = code_raw if isinstance(code_raw, str) else ""
    if not code.strip():
        code = "stage"
    held = _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        card_digest,
        code=code.strip(),
        reason=reason.strip(),
    )
    held["closed"] = False
    held["ok"] = False
    return held


def _with_plan_encourage(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    plan_text: str | None,
) -> dict[str, object]:
    """One plan question after Stage 3 is stored. Silence still leaves the save in place."""
    if stage != "3" or body.get("stored") is not True or not isinstance(plan_text, str):
        return body
    from essay_writer.encourage import attach_plan_encourage

    return attach_plan_encourage(body, essay_id, plan_text)


def _cache_approved_look(essay_id: str, stage: str, look: str) -> None:
    if stage == "5":
        return
    from essay_writer.specialists.grok_bot import remember_approved_look

    remember_approved_look(essay_id, look)


def _snapshot_stage_save(
    essay_id: str, stage: str, look: str | None, body: dict[str, object]
) -> None:
    """Auto-snapshot after a stage save that stored. A refusal writes no snapshot."""
    if body.get("stored") is not True:
        return
    from essay_writer.pack_backup import snapshot_after_stage_save

    snapshot_after_stage_save(essay_id, stage, look if isinstance(look, str) else "")


def _commit_with_next_card(
    body: dict[str, object],
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    updated: dict[str, object],
    note,
    note_text: str,
    following: str | None,
    card_digest: str | None,
    plan_text: str | None = None,
    *,
    approved_look: str | None = None,
    open_card: bool,
) -> dict[str, object]:
    """One write advances the pointer and stores the tracking note.

    The next stage's Confirm card is not minted on this path. A missing card
    does not roll the save back. Both waiting fields are cleared. Stage 10
    still writes the sequence file before the pointer can close. Stage 5 and
    the last stage name an advance with no card. This module never imports
    the orchestrator.
    """
    if stage == "10":
        held = _render_stage10_before_close(body, essay_id, stage, genre, pointer, card_digest)
        if held is not None:
            return held
    pending_next = _pending_inherited(essay_id, following)
    # A copied stage 2 or 3 names the parent save. Confirm waits for revise or re-lock.
    updated["waiting_stage"] = None
    updated["waiting_digest"] = None
    cache_look = approved_look if isinstance(approved_look, str) and approved_look.strip() else None
    committed = _commit_saved_stage(
        body,
        essay_id,
        stage,
        genre,
        pointer,
        updated,
        note,
        note_text,
        digest=card_digest,
        open_card=open_card,
        cache_look=cache_look,
    )
    if committed.pointer is None:
        return committed.body
    updated = committed.pointer
    body["advanced"] = following is not None
    body["closed"] = following is None
    from essay_writer.stage_next import write_critical_reviews_next, write_following_stage_next

    following_title = stage_title(following, genre) if following else ""
    write_following_stage_next(body, following, following_title)
    from essay_writer.late_chain import finish_stage_reply

    finished = finish_stage_reply(
        body,
        essay_id,
        stage,
        armed=updated.get("chain_armed") is True,
    )
    if finished.get("delivery_speech") == "4b" and isinstance(finished.get("next"), str):
        write_critical_reviews_next(finished)
    if pending_next is not None and following:
        finished = _name_inherited_lock(finished, essay_id, following, pending_next)
    elif not _expects_next_card(following):
        finished = _mark_explicit_end(finished)
    else:
        finished["repost"] = False
        finished.pop("card", None)
        finished.pop("cardAction", None)
        finished.pop("cardDigest", None)
    finished = _with_plan_encourage(finished, essay_id, stage, plan_text)
    _snapshot_stage_save(
        essay_id,
        stage,
        approved_look if isinstance(approved_look, str) else "",
        finished,
    )
    return finished


_CARD_FIELDS = ("master", "namedFolder", "answers", "edited", "webCheck", "heldFile")


def _replay_confirm_card(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> dict[str, object] | None:
    """The waiting Confirm card. Typed Confirm, yes, or ok shows it again."""
    record = _card_record(essay_id, stage, card_digest)
    if record is None:
        record = _card_record(essay_id, stage, _waiting_digest(pointer, stage))
    if record is None:
        record = latest_draft(essay_id, TOOL, stage=stage)
    if record is None:
        return None
    digest = record.get("digest")
    if not isinstance(digest, str) or not digest:
        return None
    from essay_writer.specialists.grok_bot import card_next, confirm_reply_fields
    from essay_writer.spine import stage_confirm_card
    from essay_writer.stage_next import write_stage_next

    revisit = _revisit_window(pointer) and stage in {"2", "3"}
    line = _confirm_line(stage, genre, revisit=revisit)
    title = stage_title(stage, genre)
    card = stage_confirm_card(
        essay_id,
        stage,
        digest,
        line,
        stage_title=title,
    )
    replayed: dict[str, Any] = {
        "card": card,
        "digest": digest,
        **confirm_reply_fields(digest),
        "confirm_line": line,
        "stored": False,
        "advanced": False,
        "wrote": False,
    }
    return write_stage_next(replayed, card_next(stage, title))


def _stage7_skip_reply(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    confirm_phase: str,
) -> dict[str, object]:
    """A skip does not save. The same reply asks the questions again."""
    from essay_writer.stage7 import load_stage7, note_questions, questions_for
    from essay_writer.stage_next import write_stage7_skip_next

    record = load_stage7(essay_id)
    if not record.get("asked"):
        note_questions(essay_id)
        record = load_stage7(essay_id)
    questions = list(record.get("questions") or questions_for(essay_id))
    title = stage_title(stage, genre)
    reason = "Skipping the questions does not save this step. Answer them in this chat."
    refused = refuse(
        "stage",
        reason,
        questions=questions,
        stored=False,
        wrote=False,
        advanced=False,
        waiting_confirm=True,
        current=pointer["current"],
        stage=stage,
        confirmPhase=confirm_phase,
    )
    spoken = [item for item in questions if isinstance(item, str)]
    return write_stage7_skip_next(refused, reason=reason, questions=spoken, title=title)


def _reoffer_confirm(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
    *,
    reason: str,
    code: str = "confirm-card",
    lead: str | None = None,
) -> dict[str, object]:
    """A confirm that does not save still leaves the Confirm card, or a next ask.

    ``lead`` is the spoken next when this draft was refused for a missing
    source or bibliography. It replaces the card ask and keeps the card.
    Other refusals still name the card. When no card can be replayed, the
    typed-yes fallback stays.
    """
    from essay_writer.stage_next import write_reoffer_next

    replay = _replay_confirm_card(essay_id, stage, genre, pointer, card_digest)
    extra: dict[str, object] = {
        "stage": stage,
        "confirmPhase": CONFIRM,
        "current": pointer["current"],
        "waiting_confirm": True,
        "stored": False,
        "advanced": False,
        "wrote": False,
    }
    if replay:
        extra.update(replay)
    refused = refuse(code, reason, **extra)
    return write_reoffer_next(
        refused,
        lead=lead,
        replayed=replay is not None,
        stage=stage,
        title=stage_title(stage, genre),
    )


def _card_record(essay_id: str, stage: str, card_digest: str | None):
    """Draft named by the Confirm card, when it is this stage's draft."""
    if not isinstance(card_digest, str) or not card_digest.strip():
        return None
    record = load_draft_by_digest(essay_id, TOOL, card_digest.strip())
    if record is None:
        return None
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    if payload.get("essay_id") != essay_id or payload.get("stage") != stage:
        return None
    return record


def _hydrate_card(
    text: str,
    look: str | None,
    record: dict[str, Any] | None,
    fields: dict[str, object],
) -> tuple[str, dict[str, Any]]:
    """Fill omitted Confirm fields from the card draft. A different look stays a new payload."""
    if record is None:
        return text, fields
    payload = record["payload"]
    omitted = look is None or (isinstance(look, str) and not look.strip())
    saved_look = payload.get("look")
    if omitted and isinstance(saved_look, str):
        text = saved_look.strip()
    filled = dict(fields)
    for key in _CARD_FIELDS:
        if filled.get(key) is None and key in payload:
            filled[key] = payload[key]
    return text, filled


def _superseded_card(
    essay_id: str,
    stage: str,
    pointer: dict[str, Any],
    card_digest: str | None,
) -> bool:
    """True when this card is an older draft of the same stage than the one waiting."""
    record = _card_record(essay_id, stage, card_digest)
    if record is None:
        return False
    card = record.get("digest")
    waiting = _waiting_digest(pointer, stage)
    if waiting is not None:
        return card != waiting
    payload = record.get("payload")
    look = payload.get("look") if isinstance(payload, dict) else None
    note_look = _note_look(essay_id, stage)
    if isinstance(note_look, str) and isinstance(look, str) and look != note_look:
        return True
    latest = latest_draft(essay_id, TOOL, stage=stage)
    if isinstance(latest, dict) and latest.get("digest") != card:
        return True
    return False


def _older_card(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
) -> dict[str, object]:
    return _reoffer_confirm(
        essay_id,
        stage,
        genre,
        pointer,
        None,
        code="confirm",
        reason=(
            "That card is an older draft of this step. "
            "Show the latest draft again before it can be saved."
        ),
    )


def _stale_confirm_body(
    essay_id: str,
    stage: str,
    pointer: dict[str, Any],
    digest: object,
    look_text: str,
) -> bool:
    """True unless this confirm is the waiting draft and that draft's look."""
    waiting = _waiting_digest(pointer, stage)
    if waiting is not None:
        if digest != waiting:
            return True
        record = load_draft_by_digest(essay_id, TOOL, waiting)
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict):
            return True
        return payload.get("look") != look_text
    note_look = _note_look(essay_id, stage)
    if isinstance(note_look, str) and note_look != look_text:
        return True
    latest = latest_draft(essay_id, TOOL, stage=stage)
    if not isinstance(latest, dict) or latest.get("digest") != digest:
        return True
    payload = latest.get("payload")
    if not isinstance(payload, dict):
        return True
    return payload.get("look") != look_text


def _stage_refusal(
    pointer: Pointer,
    stage: str,
    genre: str | None,
    essay_id: str | None = None,
) -> dict[str, object] | None:
    current = pointer["current"]
    if pointer.get("closed"):
        if isinstance(essay_id, str) and essay_id.strip():
            from essay_writer.late_chain import MISSING_FINAL_WORD, _missing_stored_final_word

            if _missing_stored_final_word(essay_id):
                from essay_writer.stage_next import write_stage_next
                from essay_writer.student_voice import say

                stopped = refuse("word", MISSING_FINAL_WORD)
                reason = stopped.get("reason")
                return write_stage_next(stopped, say(reason if isinstance(reason, str) else ""))
        return refuse(
            "stage",
            "The last stage is already saved. Ask me to show the finished step. "
            "This tool does not submit.",
        )
    window = _revisit_window(cast(dict[str, Any], pointer))
    if window and stage in {"2", "3"}:
        if stage == "3" and pointer.get("revisit_open") == "2":
            if genre == "report":
                reason = "Save purpose and scope first. Then save the plan before the first draft."
            elif genre == "essay":
                reason = "Save the thesis first. Then save the plan before the first draft."
            elif genre == "diary":
                reason = "Save the entries first. Then save the plan before the first draft."
            else:
                reason = "Save the earlier lock first. Then save the plan before the first draft."
            return refuse("stage", reason)
        return None
    if stage == "5" and window and pointer.get("revisit_open"):
        return refuse(
            "stage",
            "Save the plan note first. The first draft waits until that save.",
        )
    if stage == "5" and window and pointer.get("revisit_after_lock"):
        return refuse(
            "stage",
            "Save the plan again before the first draft. The earlier lock changed.",
        )
    if stage in pointer["saved"]:
        return refuse(
            "stage",
            f"Stage {stage} is already saved. The current stage is {current}.",
        )
    if stage != current:
        return refuse(
            "stage",
            f"The current stage is {current}. Finish that step in this chat before stage {stage}.",
        )
    return None


def _stage5_held(
    pointer: dict[str, Any],
    gate: dict[str, Any],
    blockers: list[dict[str, str]],
) -> dict[str, object]:
    """A failed north-star or a notes-shaped draft does not store and does not advance."""
    from essay_writer.late_chain import stage5_chat_line

    if blockers:
        code = blockers[0].get("code") or "argument"
        reason = blockers[0].get("reason") or "Stage 5 is the report or essay argument."
    else:
        code = "north-star"
        reason = gate.get("reason") or "The first draft does not pass the assignment check yet."
    line = stage5_chat_line(reason, "The first draft is not ready yet.")
    refused = refuse(
        code,
        reason,
        advanced=False,
        current=pointer["current"],
        north_star=gate,
        blockers=blockers,
        quiet=True,
        step="5",
        checklist_in_chat=False,
        chat=line,
        confirm_line=line,
    )
    from essay_writer.stage_next import write_stage_next
    from essay_writer.student_voice import say

    return write_stage_next(refused, say(line))


def _confirm_line(stage: str, genre: str | None, *, revisit: bool = False) -> str:
    from essay_writer.spine import save_line

    return save_line(stage, genre, revisit=revisit)
