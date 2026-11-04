"""The draft and save reply writers for the stage tracking note.

These writers turn a built stage context into the tool reply: the quiet no-op,
the draft card, and the held save. The state layer lives in
essay_writer/stage_state.py and the landing helpers in
essay_writer/stage_landing.py. The orchestrator in essay_writer.stage_track
keeps the public entry points and re-exports every name here.
"""

from __future__ import annotations

from typing import Any

from essay_writer.confirm import DRAFT, confirm_ready, save_draft
from essay_writer.paths import relative
from essay_writer.stage_context import StageContext
from essay_writer.stage_landing import _attach_mid_run, _late_armed, _store_stage
from essay_writer.stage_llm import next_stage, stage_title
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    StageResult,
    _cache_approved_look,
    _commit_pointer,
    _commit_with_next_card,
    _confirm_line,
    _mark_explicit_end,
    _note_path,
    _older_card,
    _pointer_lost,
    _reoffer_confirm,
    _replay_confirm_card,
    _room_after_card_save,
    _saved_after_confirm,
    _snapshot_stage_save,
    _stale_confirm_body,
    _waiting_digest,
    _with_plan_encourage,
    render_tracking,
)


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
            note_text = render_tracking(stage, status="draft", look=text, genre=genre, essay_id=essay_id)
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
                return _pointer_lost(essay_id, stage, genre)
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
            )
        from essay_writer.specialists.grok_bot import (
            card_next,
            confirm_reply_fields,
            stage7_lead,
        )
        from essay_writer.stage7 import stage7_edited
        from essay_writer.student_progress import (
            mid_run_wait_next,
            upload_reconcile_next,
        )

        upload_next = upload_reconcile_next(body.get("download_check"))
        if upload_next:
            body["next"] = upload_next
        elif body.get("mid_started") is True:
            body["next"] = mid_run_wait_next(stage, body["stage_title"])
        elif stage == "7" and not stage7_edited(essay_id):
            body["next"] = stage7_lead(list(body.get("questions") or []), body["stage_title"])
        else:
            body["next"] = card_next(stage, body["stage_title"])
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


def _save_confirm(context: StageContext, cardDigest: str | None) -> dict[str, Any]:
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
            reason=str(ready.get("reason") or "Show this step in the chat again before it can be saved."),
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
            )
        body["delivery"] = delivery
        body["delivery_speech"] = "4b"
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
            return _pointer_lost(essay_id, stage, genre)
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
        from essay_writer.specialists.grok_bot import revisit_plan_next, saved_next

        if stage == "2":
            body["next_stage"] = "3"
            body["next_stage_title"] = stage_title("3", genre)
            body["next"] = revisit_plan_next(stage_title("3", genre))
        else:
            body["next_stage"] = "5"
            body["next_stage_title"] = stage_title("5", genre)
            body["next"] = saved_next("5", stage_title("5", genre))
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
    )
