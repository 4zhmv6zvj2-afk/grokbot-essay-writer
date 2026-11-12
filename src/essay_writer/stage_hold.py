"""Held and refused replies for one stage save.

stage_hold builds the reply a save returns when it is held or refused,
replays a Confirm card, and commits the next card through the injected
CardRun. The pointer write stays in stage_state: this module calls
_commit_pointer and does not write the journal itself. It never imports
the orchestrator, the confirm path, or the body builder.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from essay_writer.confirm import (
    CONFIRM,
    latest_draft,
    load_draft_by_digest,
    refuse,
)
from essay_writer.paths import relative
from essay_writer.stage_llm import STAGE_ORDER, brief_genre, next_stage, stage_title
from essay_writer.stage_note import _note_look
from essay_writer.stage_state import (
    TOOL,
    Pointer,
    _commit_pointer,
    _revisit_window,
    _waiting_digest,
    load_pointer,
)


class CardRun(Protocol):
    """Run one card-only stage. The orchestrator injects this into the state layer.

    ``minting=True`` is the next-card mint; the student-answer gates stay off
    that draft. Reopening an already-saved stage's card keeps the normal gates.
    """

    def __call__(
        self,
        essay_id: str,
        stage: str,
        look: str | None = None,
        *,
        minting: bool = False,
    ) -> dict[str, object]: ...


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


def door_card_reply(
    essay_id: str,
    *,
    card_run: CardRun | None = None,
) -> dict[str, object] | None:
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
    if current == "1" and not saved and card_run is not None:
        return _own_door_card(_draft_next_card(essay_id, "1", card_run), essay_id, "1")
    return None


def _pointer_lost(
    essay_id: str,
    stage: str,
    genre: str | None,
    *,
    card_run: CardRun | None = None,
) -> dict[str, object]:
    """The pointer moved after this call read it. The newer pointer stays."""
    fresh = load_pointer(essay_id)
    blocked = _stage_refusal(cast(Pointer, fresh), stage, genre, essay_id)
    if blocked is not None:
        return _confirm_blocked(essay_id, fresh, stage, genre, blocked, card_run=card_run)
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
    card_run: CardRun | None = None,
) -> dict[str, object]:
    """An already-saved stage does not replay its card. The draft card is for current."""
    from essay_writer.specialists.grok_bot import missing_confirm_next
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
        blocked["next"] = str(
            blocked.get("reason") or "The last stage is already saved. This tool does not submit."
        )
        return blocked
    opened = None
    if stage_uses_confirm_card(current) and current != stage:
        opened = _replay_confirm_card(essay_id, current, genre, pointer, None)
        if opened is None and card_run is not None:
            opened = card_run(essay_id, current, None, minting=False)
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
        nxt = opened_reply.get("next")
        blocked["next"] = (
            nxt
            if isinstance(nxt, str) and nxt.strip()
            else missing_confirm_next(current, stage_title(current, genre))
        )
    else:
        blocked["next"] = missing_confirm_next(current, stage_title(current, genre))
    return blocked


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


def _draft_next_card(
    essay_id: str,
    following: str,
    card_run: CardRun,
) -> dict[str, object]:
    """One card-only draft of the next stage. It does not move the pointer.

    Student-answer rules (part names, Entry N, house words) stay off this mint.
    They run when the student later writes that stage. The injected runner
    carries the mint flag; this module never imports the orchestrator.
    """
    return card_run(
        essay_id,
        following,
        _next_card_look(essay_id, following),
        minting=True,
    )


def _next_card_fields(
    opened: dict[str, object], essay_id: str, following: str
) -> dict[str, object] | None:
    """card, cardAction, and cardDigest for this sequence's next stage, or nothing."""
    card = opened.get("card")
    if not isinstance(card, dict):
        return None
    if card.get("essay_id") != essay_id or card.get("stage") != following:
        return None
    if card.get("kind") != "confirm":
        return None
    action = opened.get("cardAction") or card.get("cardAction")
    digest = opened.get("cardDigest") or card.get("cardDigest") or card.get("digest")
    if action != "confirm" or not isinstance(digest, str) or len(digest) != 64:
        return None
    if card.get("digest") not in (None, digest):
        return None
    return {"card": card, "cardAction": action, "cardDigest": digest}


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
    body["next"] = ask["next"]
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
        body["next"] = nxt
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
    card_run: CardRun,
) -> dict[str, object]:
    """One write advances the pointer and stores the next waiting card.

    A stage that expects a card and cannot mint one does not write. Stage 5
    and the last stage write the advance with no card, and say so. The next
    card is minted through the injected ``card_run``; this module never
    imports the orchestrator.
    """
    if isinstance(approved_look, str) and approved_look.strip():
        _cache_approved_look(essay_id, stage, approved_look)
    if stage == "10":
        held = _render_stage10_before_close(body, essay_id, stage, genre, pointer, card_digest)
        if held is not None:
            return held
    opened: dict[str, object] | None = None
    fields: dict[str, object] | None = None
    pending_next = _pending_inherited(essay_id, following)
    # A copied stage 2 or 3 names the parent save. Confirm waits for revise or re-lock.
    expects_card = _expects_next_card(following) and pending_next is None
    if expects_card:
        opened = _draft_next_card(essay_id, following or "", card_run)
        if isinstance(opened, dict):
            fields = _next_card_fields(opened, essay_id, following or "")
        if fields is None or opened is None:
            return _hold_confirm(
                essay_id,
                stage,
                genre,
                pointer,
                card_digest,
                opened if isinstance(opened, dict) else None,
                following or "",
            )
        updated["waiting_stage"] = following
        updated["waiting_digest"] = fields["cardDigest"]
    else:
        updated["waiting_stage"] = None
        updated["waiting_digest"] = None
    stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
    if stored is None:
        return _pointer_lost(essay_id, stage, genre, card_run=card_run)
    updated = stored
    body["wrote"] = True
    body["stored"] = True
    body["advanced"] = following is not None
    body["closed"] = following is None
    body["digest"] = card_digest
    body["tracking_path"] = relative(note)
    body["current"] = updated["current"]
    from essay_writer.specialists.grok_bot import saved_next

    if following:
        body["next"] = saved_next(following, stage_title(following, genre))
    else:
        body["next"] = "Keep a copy. This tool does not submit."
    from essay_writer.late_chain import finish_stage_reply

    finished = finish_stage_reply(
        body,
        essay_id,
        stage,
        armed=updated.get("chain_armed") is True,
    )
    if finished.get("delivery_speech") == "4b" and isinstance(finished.get("next"), str):
        from essay_writer.specialists.grok_bot import critical_reviews_delivery_next

        finished["next"] = critical_reviews_delivery_next(finished["next"])
        finished.pop("delivery_speech", None)
    if fields is not None and opened is not None:
        finished = _attach_minted_card(finished, opened, fields)
    elif pending_next is not None and following:
        finished = _name_inherited_lock(finished, essay_id, following, pending_next)
    else:
        finished = _mark_explicit_end(finished)
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
    return {
        "card": card,
        "digest": digest,
        **confirm_reply_fields(digest),
        "next": card_next(stage, title),
        "confirm_line": line,
        "stored": False,
        "advanced": False,
        "wrote": False,
    }


def _stage7_skip_reply(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    confirm_phase: str,
) -> dict[str, object]:
    """A skip does not save. The same reply asks the questions again."""
    from essay_writer.specialists.grok_bot import stage7_lead
    from essay_writer.stage7 import load_stage7, note_questions, questions_for

    record = load_stage7(essay_id)
    if not record.get("asked"):
        note_questions(essay_id)
        record = load_stage7(essay_id)
    questions = list(record.get("questions") or questions_for(essay_id))
    title = stage_title(stage, genre)
    reason = "Skipping the questions does not save this step. Answer them in this chat."
    lead = stage7_lead(questions, title)
    return refuse(
        "stage",
        reason,
        next=f"{reason} {lead}",
        questions=questions,
        stored=False,
        wrote=False,
        advanced=False,
        waiting_confirm=True,
        current=pointer["current"],
        stage=stage,
        confirmPhase=confirm_phase,
    )


def _reoffer_confirm(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    card_digest: str | None,
    *,
    reason: str,
    code: str = "confirm-card",
) -> dict[str, object]:
    """A confirm that does not save still leaves the Confirm card, or a next ask."""
    from essay_writer.specialists.grok_bot import missing_confirm_next

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
    else:
        extra["next"] = missing_confirm_next(stage, stage_title(stage, genre))
    return refuse(code, reason, **extra)


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
                return refuse("word", MISSING_FINAL_WORD, next=MISSING_FINAL_WORD)
        return refuse("stage", "The last stage is already saved. This tool does not submit.")
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
    return refuse(
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
        next=line,
        confirm_line=line,
    )


def _confirm_line(stage: str, genre: str | None, *, revisit: bool = False) -> str:
    from essay_writer.spine import save_line

    return save_line(stage, genre, revisit=revisit)
