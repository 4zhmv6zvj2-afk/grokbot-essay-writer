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
stage lock. A confirm that expects a next card stores that card's waiting
digest in the same write as the advance. If that card cannot be minted,
the write does not happen and the waiting card stays. Stage 5 and the
last stage name an advance with no card. A newer current or saved list
is left in place.

The state layer — the pointer and its commit journal, the stage lock, the
tracking-note renderer, and the reply bodies a held save returns — lives in
essay_writer/stage_state.py. The landing and report helpers live in
essay_writer/stage_landing.py and the draft and save reply writers in
essay_writer/stage_replies.py. This module is the orchestrator: it imports the
three layers at module load and keeps the public entry point.

Those layers do not import this module, at module load or at call time. A save
that needs the next stage's card or the current stage's card gets an injected
card runner (``_run_card_only``); the state layer never sets a contextvar to
re-enter the door. The typed stage values (StageArgs and StageContext) live in
essay_writer/stage_context.py.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    latest_draft,
    phase_refusal,
    refuse,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import sequence_write_error, work_dir
from essay_writer.stage_context import ConfirmState, StageArgs, StageContext
from essay_writer.stage_landing import (
    _attach_cite_report,
    _attach_outline_report,
    _attach_short_report,
    _collect_stage_misses,
    _inherited_lock_keep,
)
from essay_writer.stage_llm import (
    RULES_SOURCE,
    STAGE_ORDER,
    brief_genre,
    stage_settings,
    stage_title,
)
from essay_writer.stage_replies import _draft_reply, _noop_result, _save_confirm
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    CardRun,
    Pointer,
    _card_record,
    _confirm_blocked,
    _grant_room,
    _hydrate_card,
    _mint_stage_allowed,
    _note_path,
    _older_card,
    _payload,
    _pointer_lost,
    _reoffer_confirm,
    _revisit_window,
    _room_blocks,
    _stage7_skip_reply,
    _stage_refusal,
    _superseded_card,
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
) -> dict[str, Any]:
    """A card saves the final look. Stage 5 starts stage 6."""
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
        ),
        minting=False,
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
    """Run one stage call with the shared damage and quarantine handling."""
    from essay_writer.stage_state import _QUARANTINE_NOTICE, DamagedStageCommit

    try:
        result = _run_stage(args, minting=minting)
    except DamagedStageCommit as exc:
        _QUARANTINE_NOTICE.set(None)
        reason = str(exc).strip() or "The last confirm record was damaged and was not applied."
        return refuse(
            "stage",
            reason,
            wrote=False,
            stored=False,
        )
    except Exception:
        _QUARANTINE_NOTICE.set(None)
        raise
    notice = _QUARANTINE_NOTICE.get()
    if notice and isinstance(result, dict):
        _QUARANTINE_NOTICE.set(None)
        result["notice"] = notice
        following = result.get("next")
        if isinstance(following, str) and notice not in following:
            result["next"] = f"{notice} {following}"
        elif not isinstance(following, str):
            result["next"] = notice
    return result


def _turn_redirect(
    stage: str, confirm_phase: str | None, *messages: object
) -> dict[str, Any] | None:
    """Approved reply for a short ask. A stage note is not one of these."""
    from essay_writer.student_turns import redirect_for

    for message in messages:
        reply = redirect_for(message)
        if reply is not None:
            return refuse(
                "turn",
                reply,
                next=reply,
                stage=stage,
                confirmPhase=confirm_phase,
            )
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
            "stage must be 1, 2, 3, 4a, 4b, 5, 6, 7, 8, 9, or 10.",
        )
    if look is None:
        text = ""
    elif isinstance(look, str):
        text = look.strip()
    else:
        return refuse("stage", "look must be plain text.")
    redirected = _turn_redirect(stage, confirmPhase, text, args.answers)
    if redirected is not None:
        return redirected
    pointer = load_pointer(essay_id)
    genre = brief_genre(essay_id)
    pending_lock = inherited_lock_pending(essay_id, stage)
    blocked = _stage_refusal(cast(Pointer, pointer), stage, genre)
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
    from essay_writer.spine import advances_without_confirm

    auto_next = advances_without_confirm(stage)
    if confirmPhase == CONFIRM and auto_next:
        return refuse(
            "confirm-card",
            "This step moves on when the draft is stored. There is no save-card between this step and the next.",
            advanced=False,
            current=pointer["current"],
            next=(
                "This step moves on when the draft is stored. "
                "There is no Confirm card between this step and the next."
            ),
            waiting_confirm=False,
        )
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
        return _noop_result(essay_id, stage, confirmPhase, pointer["current"])
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


def _confirm_path(
    args: StageArgs,
    pointer: dict[str, Any],
    genre: str | None,
    *,
    card_run: CardRun | None,
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
            if not _INHERITED_KEEP.get() and _superseded_card(essay_id, stage, pointer, cardDigest):
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
                    return _pointer_lost(essay_id, stage, genre, card_run=card_run)
                pointer = stored_room
                look = None
                text = ""
                granted_here = True
            elif press_target == stage:
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre, card_run=card_run)
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
