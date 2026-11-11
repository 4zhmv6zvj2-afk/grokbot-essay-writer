"""Confirm path for one stage call.

stage_confirm owns the confirm path and the shared stage-7 skip probe.
stage_body may import this module for the skip probe. stage_confirm must
never import stage_body.
"""

from __future__ import annotations

from typing import Any

from essay_writer.confirm import CONFIRM, DRAFT, latest_draft
from essay_writer.stage_context import ConfirmState, StageArgs
from essay_writer.stage_hold import (
    CardRun,
    _card_record,
    _hydrate_card,
    _older_card,
    _pointer_lost,
    _reoffer_confirm,
    _stage7_skip_reply,
    _superseded_card,
)
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    _grant_room,
    _room_blocks,
)


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
