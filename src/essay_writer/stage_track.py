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
or the current stage's card gets an injected card runner (``_run_card_only``);
the state side never sets a contextvar to re-enter the door. The typed stage
values (StageArgs and StageContext) live in essay_writer/stage_context.py.
"""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    NO_MATCHING_DRAFT,
    confirm_ready,
    latest_draft,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import relative, sequence_write_error, work_dir
from essay_writer.stage_confirm import _confirm_path, _stage7_skip_request
from essay_writer.stage_context import ConfirmState, StageArgs, StageContext
from essay_writer.stage_hold import (
    CardRun,
    _cache_approved_look,
    _card_record,
    _commit_with_next_card,
    _confirm_blocked,
    _confirm_line,
    _mark_explicit_end,
    _mint_stage_allowed,
    _older_card,
    _pointer_lost,
    _reoffer_confirm,
    _replay_confirm_card,
    _snapshot_stage_save,
    _stage_refusal,
    _stale_confirm_body,
    _with_plan_encourage,
)
from essay_writer.stage_landing import (
    _attach_cite_report,
    _attach_mid_run,
    _attach_outline_report,
    _attach_short_report,
    _collect_stage_misses,
    _inherited_lock_keep,
    _late_armed,
    _store_stage,
)
from essay_writer.stage_llm import (
    RULES_SOURCE,
    STAGE_ORDER,
    brief_genre,
    next_stage,
    stage_settings,
    stage_title,
)
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    Pointer,
    StageResult,
    _commit_pointer,
    _note_path,
    _payload,
    _revisit_window,
    _room_after_card_save,
    _saved_after_confirm,
    _waiting_digest,
    load_pointer,
)


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
    from essay_writer.textutil import begin_brief_ask, end_brief_ask

    token = begin_brief_ask()
    try:
        return _stage_call(
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
        )
    finally:
        end_brief_ask(token)


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
    )


def _inherited_keep_confirm(
    essay_id: str,
    stage: str,
    look: str,
    digest: str | None,
) -> dict[str, Any]:
    """Save a kept inherited lock through the public door.

    The landing layer sets the keep flag around this call; it never imports
    this module to re-enter the door.
    """
    from essay_writer.specialists.grok_bot import CARD_CONFIRM

    return essay_stage(
        essay_id,
        stage,
        CONFIRM,
        look,
        cardAction=CARD_CONFIRM,
        cardDigest=digest,
    )


def _stage_call(args: StageArgs, *, minting: bool) -> dict[str, Any]:
    """Run one stage call. A damaged confirm record or state file stops it."""
    from essay_writer.stage_state import DAMAGED_COMMIT, DamagedStageCommit
    from essay_writer.state import DamagedState, state_file_refusal

    try:
        result = _run_stage(args, minting=minting)
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


def _run_stage(args: StageArgs, *, minting: bool) -> dict[str, Any]:
    """Resolve one stage call, then draft it or save it.

    The tool call arrives as StageArgs. The runner validates it, resolves the
    waiting card, and builds a StageContext for the reply writers. A refusal
    stops at the step that raised it and is returned unchanged.

    ``minting`` is true only inside the injected card runner. The state and
    reply layers receive the same runner and never import this module.
    """
    card_run = None if minting else _run_card_only
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
            return _confirm_blocked(essay_id, pointer, stage, genre, blocked, card_run=card_run)
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
        and not _INHERITED_KEEP.get()
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
    state = _confirm_path(resolved, pointer, genre, card_run=card_run)
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
    body = _build_stage_body(filled, pointer, genre, minting, auto_next)
    if not isinstance(body, StageContext):
        return body
    if body.confirmPhase == DRAFT:
        result = _draft_reply(body, card_run=card_run)
    else:
        # A minted call is always a draft, so a save always has the runner.
        result = _save_confirm(body, cardDigest, card_run=cast(CardRun, card_run))
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


def _draft_reply(context: StageContext, *, card_run: CardRun | None = None) -> dict[str, Any]:
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
                return _pointer_lost(essay_id, stage, genre, card_run=card_run)
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
                card_run=card_run,
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
    card_run: CardRun,
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
    if not _INHERITED_KEEP.get() and _stale_confirm_body(
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
        stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
        if stored is None:
            return _pointer_lost(essay_id, stage, genre, card_run=card_run)
        updated = stored
        _cache_approved_look(essay_id, stage, text)
        body["wrote"] = True
        body["stored"] = True
        body["advanced"] = False
        body["closed"] = False
        body["revisit"] = True
        body["digest"] = ready["digest"]
        body["tracking_path"] = rel
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
        card_run=card_run,
    )
