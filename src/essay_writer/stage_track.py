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

from dataclasses import replace
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
from essay_writer.stage_body import _build_stage_body
from essay_writer.stage_confirm import _confirm_path, _stage7_skip_request
from essay_writer.stage_context import ConfirmState, StageArgs, StageContext
from essay_writer.stage_hold import (
    CardRun,
    _card_record,
    _confirm_blocked,
    _mint_stage_allowed,
    _stage_refusal,
)
from essay_writer.stage_landing import _inherited_lock_keep
from essay_writer.stage_llm import STAGE_ORDER, brief_genre
from essay_writer.stage_replies import _draft_reply, _noop_result, _save_confirm
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    Pointer,
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
    """Run one stage call. A damaged confirm record or state file stops it."""
    from essay_writer.stage_state import DAMAGED_COMMIT, DamagedStageCommit
    from essay_writer.state import DamagedState, state_file_refusal

    try:
        return _run_stage(args, minting=minting)
    except DamagedStageCommit as exc:
        reason = str(exc).strip() or DAMAGED_COMMIT
        return refuse(
            "stage",
            reason,
            wrote=False,
            stored=False,
        )
    except DamagedState:
        return state_file_refusal()


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
        from essay_writer.specialists.grok_bot import typed_save_word
        from essay_writer.stage_body import guidance_only_refusal, look_is_confirmable

        answer_call = (
            getattr(args, "formatAnswer", None) is not None
            or getattr(args, "questionAnswer", None) is not None
        )
        if (
            text
            and stage_uses_confirm_card(stage)
            and not answer_call
            and not typed_save_word(look)
            and not look_is_confirmable(essay_id, stage, genre, text)
        ):
            return guidance_only_refusal()
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
