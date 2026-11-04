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
essay_writer/stage_state.py. This module keeps the orchestrator and public
entry points, and re-exports every moved name below so existing imports of
essay_writer.stage_track keep working.
"""

# The state layer moved to stage_state.py. Every moved name is re-exported here
# with the PEP 484 redundant-alias form, which marks it as an explicit
# re-export instead of an unused import. The block is grouped by origin, not
# alphabetically, so isort is disabled for this file in pyproject.toml.
from __future__ import annotations

from typing import Any, cast

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    latest_draft,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import relative, sequence_write_error, work_dir
from essay_writer.stage_llm import (
    RULES_SOURCE,
    STAGE_ORDER,
    brief_genre,
    next_stage,
    stage_settings,
    stage_title,
)
from essay_writer.student_voice import student_surface_hits

from essay_writer.stage_state import (
    Pointer as Pointer,
    STAGE_COMMIT as STAGE_COMMIT,
    StageResult as StageResult,
    _CARD_FIELDS as _CARD_FIELDS,
    _INHERITED_KEEP as _INHERITED_KEEP,
    _LOCKS as _LOCKS,
    _MINTING as _MINTING,
    _STAGE_NOTE_RELS as _STAGE_NOTE_RELS,
    _apply_commit as _apply_commit,
    _atomic as _atomic,
    _attach_minted_card as _attach_minted_card,
    _cache_approved_look as _cache_approved_look,
    _card_record as _card_record,
    _card_records_no_change as _card_records_no_change,
    _clear_copied_writing as _clear_copied_writing,
    _commit_path as _commit_path,
    _commit_pointer as _commit_pointer,
    _commit_with_next_card as _commit_with_next_card,
    _confirm_blocked as _confirm_blocked,
    _confirm_line as _confirm_line,
    _draft_next_card as _draft_next_card,
    _expects_next_card as _expects_next_card,
    _grant_room as _grant_room,
    _held_locks as _held_locks,
    _hold_confirm as _hold_confirm,
    _hydrate_card as _hydrate_card,
    _mark_explicit_end as _mark_explicit_end,
    _mint_stage_allowed as _mint_stage_allowed,
    _name_inherited_lock as _name_inherited_lock,
    _next_card_fields as _next_card_fields,
    _next_card_look as _next_card_look,
    _normalize_pointer as _normalize_pointer,
    _note_look as _note_look,
    _note_path as _note_path,
    _note_rel as _note_rel,
    _older_card as _older_card,
    _opening_look as _opening_look,
    _own_door_card as _own_door_card,
    _payload as _payload,
    _pending_inherited as _pending_inherited,
    _pointer_lock as _pointer_lock,
    _pointer_lost as _pointer_lost,
    _pointer_path as _pointer_path,
    _pointer_text as _pointer_text,
    _read_commit as _read_commit,
    _read_pointer_data as _read_pointer_data,
    _render_stage10_before_close as _render_stage10_before_close,
    _reoffer_confirm as _reoffer_confirm,
    _replay_commit as _replay_commit,
    _replay_confirm_card as _replay_confirm_card,
    _revision as _revision,
    _revisit_window as _revisit_window,
    _rolls_backward as _rolls_backward,
    _room_after_card_save as _room_after_card_save,
    _room_blocks as _room_blocks,
    _room_state as _room_state,
    _saved_after_confirm as _saved_after_confirm,
    _snapshot_stage_save as _snapshot_stage_save,
    _stage5_held as _stage5_held,
    _stage7_skip_reply as _stage7_skip_reply,
    _stage_refusal as _stage_refusal,
    _stale_confirm_body as _stale_confirm_body,
    _superseded_card as _superseded_card,
    _waiting_digest as _waiting_digest,
    _waiting_pair as _waiting_pair,
    _with_plan_encourage as _with_plan_encourage,
    blank_pointer as blank_pointer,
    door_card_reply as door_card_reply,
    in_first_draft as in_first_draft,
    init_cloned_sequence_pointer as init_cloned_sequence_pointer,
    load_pointer as load_pointer,
    rebind_cloned_confirms as rebind_cloned_confirms,
    render_tracking as render_tracking,
    stage_lock as stage_lock,
    TOOL as TOOL,
)


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


def _attach_outline_report(
    body: dict[str, object], essay_id: str, stage: str
) -> None:
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
    stored = _commit_pointer(essay_id, pointer, updated, note=note, note_text=note_text)
    if stored is None:
        return _pointer_lost(essay_id, stage, genre)
    updated = stored
    body["wrote"] = True
    body["stored"] = True
    body["advanced"] = following is not None
    body["closed"] = following is None
    body["digest"] = digest
    body["tracking_path"] = rel
    body["current"] = updated["current"]
    body.pop("card", None)
    from essay_writer.specialists.grok_bot import saved_next

    if following:
        body["next"] = saved_next(following, stage_title(following, genre))
    else:
        body["next"] = "Keep a copy. This tool does not submit."
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
                "That note uses a label that stays off the stage file. Use plain words.",
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

    if stage != "5" and delivery_file_only(text):
        blocked_pass = basics_pass_block(essay_id, text)
        if blocked_pass:
            blocked_pass["stage"] = stage
            blocked_pass["confirmPhase"] = confirmPhase
            add(blocked_pass)
    stage5_gate = None
    if stage == "5":
        from essay_writer.draft_from_review import stage5_draft_blockers

        stage5_gate = north_star(essay_id, text)
        stage5_blockers = stage5_draft_blockers(essay_id, text)
        if stage5_gate.get("passed") is not True or stage5_blockers:
            add(_stage5_held(pointer, stage5_gate, stage5_blockers))
    else:
        add(gate_save(essay_id, text))
    if stage != "5":
        blocked_pass = basics_pass_block(essay_id, text)
        if blocked_pass:
            blocked_pass["stage"] = stage
            blocked_pass["confirmPhase"] = confirmPhase
            add(blocked_pass)
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
) -> dict[str, Any]:
    """Keep continues the parent save without showing Confirm again."""
    from essay_writer.fo_chat_locks import _mark_lock_resolved
    from essay_writer.specialists.grok_bot import CARD_CONFIRM

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
    _mark_lock_resolved(essay_id, stage)
    token = _INHERITED_KEEP.set(True)
    try:
        saved = essay_stage(
            essay_id,
            stage,
            CONFIRM,
            text,
            cardAction=CARD_CONFIRM,
            cardDigest=digest if isinstance(digest, str) else ready.get("digest"),
        )
    finally:
        _INHERITED_KEEP.reset(token)
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
    minting = _MINTING.get()
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    if encourageChoice is not None:
        from essay_writer.encourage import answer_encourage

        return answer_encourage(essay_id, encourageChoice)
    if paperChoice is not None:
        from essay_writer.roll_forward import choose_paper

        return choose_paper(essay_id, paperChoice)
    from essay_writer.fo_chat_locks import (
        inherited_lock_pending,
        lock_choice_refusal,
        prior_saved_lock_ask,
    )

    refused_choice = lock_choice_refusal(lockChoice)
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
    pointer = load_pointer(essay_id)
    genre = brief_genre(essay_id)
    pending_lock = inherited_lock_pending(essay_id, stage)
    blocked = _stage_refusal(cast(Pointer, pointer), stage, genre)
    if blocked and not (minting and _mint_stage_allowed(pointer, stage)):
        if confirmPhase == CONFIRM:
            return _confirm_blocked(essay_id, pointer, stage, genre, blocked)
        return blocked
    if lockChoice == "keep" and pending_lock is not None:
        return _inherited_lock_keep(essay_id, stage, genre, pointer, pending_lock)
    if lockChoice in {"revise", "relock"} and pending_lock is not None:
        from essay_writer.fo_chat_locks import _mark_lock_resolved

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
                look = text
        _mark_lock_resolved(essay_id, stage)
    elif (
        pending_lock is not None
        and confirmPhase in {DRAFT, CONFIRM}
        and not minting
        and lockChoice is None
        and not card_only
        and not _INHERITED_KEEP.get()
    ):
        return prior_saved_lock_ask(essay_id, stage, pending_lock)
    return _run_stage(
        essay_id,
        stage,
        confirmPhase,
        text,
        look,
        master=master,
        namedFolder=namedFolder,
        answers=answers,
        edited=edited,
        webCheck=webCheck,
        heldFile=heldFile,
        cardAction=cardAction,
        cardDigest=cardDigest,
        card_only=card_only,
        pointer=pointer,
        genre=genre,
        minting=minting,
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


def _run_stage(
    essay_id: str,
    stage: str,
    confirmPhase: str | None,
    text: str,
    look: str | None,
    *,
    master: str | None,
    namedFolder: str | None,
    answers: str | None,
    edited: str | None,
    webCheck: dict[str, Any] | None,
    heldFile: str | None,
    cardAction: str | None,
    cardDigest: str | None,
    card_only: bool,
    pointer: dict[str, Any],
    genre: str | None,
    minting: bool,
) -> dict[str, Any]:
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
        and _waiting_digest(pointer, stage) is None
        and latest_draft(essay_id, TOOL, stage=stage) is None
    ):
        return _noop_result(essay_id, stage, confirmPhase, pointer["current"])
    result = _confirm_path(
        essay_id,
        stage,
        genre,
        pointer,
        confirmPhase,
        text,
        look,
        master,
        namedFolder,
        answers,
        edited,
        webCheck,
        heldFile,
        cardAction,
        cardDigest,
        card_only,
        minting,
    )
    if not result.get("_state"):
        return result
    confirmPhase = result["confirmPhase"]
    text = result["text"]
    look = result["look"]
    pointer = result["pointer"]
    master = result["master"]
    namedFolder = result["namedFolder"]
    answers = result["answers"]
    edited = result["edited"]
    webCheck = result["webCheck"]
    heldFile = result["heldFile"]
    if stage == "7" and confirmPhase == DRAFT:
        from essay_writer.stage7 import answers_mean_skip as _skip_probe

        if _skip_probe(text) or _skip_probe(answers if isinstance(answers, str) else None):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
    result = _build_stage_body(
        essay_id,
        stage,
        confirmPhase,
        text,
        pointer,
        genre,
        minting,
        answers,
        edited,
        webCheck,
        master,
        namedFolder,
        heldFile,
        card_only,
        auto_next,
    )
    if not result.get("_state"):
        return result
    if result["confirmPhase"] == DRAFT:
        return _draft_reply(result)
    return _save_confirm(result, cardDigest)


def _confirm_path(
    essay_id: str,
    stage: str,
    genre: str | None,
    pointer: dict[str, Any],
    confirmPhase: str | None,
    text: str,
    look: str | None,
    master: str | None,
    namedFolder: str | None,
    answers: str | None,
    edited: str | None,
    webCheck: dict[str, Any] | None,
    heldFile: str | None,
    cardAction: str | None,
    cardDigest: str | None,
    card_only: bool,
    minting: bool,
) -> dict[str, Any]:
    from essay_writer.spine import accept_stage_card

    if confirmPhase == CONFIRM:
        from essay_writer.specialists.grok_bot import (
            CARD_CONFIRM,
            press_confirm_stage,
            typed_save_word,
        )
        from essay_writer.stage7 import answers_mean_no_change, answers_mean_skip

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
        if stage == "7" and (answers_mean_skip(probe) or answers_mean_skip(answer_text)):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
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
            if isinstance(saved_look, str) and saved_look.strip() and not answers_mean_no_change(saved_look):
                text = saved_look.strip()
                look = text
        else:
            if not _INHERITED_KEEP.get() and _superseded_card(
                essay_id, stage, pointer, cardDigest
            ):
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
                    return _pointer_lost(essay_id, stage, genre)
                pointer = stored_room
                look = None
                text = ""
                granted_here = True
            elif press_target == stage:
                stored_room = _grant_room(essay_id, pointer, stage)
                if stored_room is None:
                    return _pointer_lost(essay_id, stage, genre)
                pointer = stored_room
                return _reoffer_confirm(
                    essay_id,
                    stage,
                    genre,
                    pointer,
                    cardDigest,
                    reason="A typed reply does not save this step. Open the Confirm card in this reply.",
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
                                or "A typed reply does not save this step. Open the Confirm card in this reply."
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
    return {
        "_state": True,
        "confirmPhase": confirmPhase,
        "text": text,
        "look": look,
        "pointer": pointer,
        "master": master,
        "namedFolder": namedFolder,
        "answers": answers,
        "edited": edited,
        "webCheck": webCheck,
        "heldFile": heldFile,
    }


def _build_stage_body(
    essay_id: str,
    stage: str,
    confirmPhase: str | None,
    text: str,
    pointer: dict[str, Any],
    genre: str | None,
    minting: bool,
    answers: str | None,
    edited: str | None,
    webCheck: dict[str, Any] | None,
    master: str | None,
    namedFolder: str | None,
    heldFile: str | None,
    card_only: bool,
    auto_next: str | None,
) -> dict[str, Any]:
    from essay_writer.specialists.grok_bot import maybe_seed_basics_on_draft

    text, basics_seeded = maybe_seed_basics_on_draft(
        essay_id,
        stage,
        confirmPhase,
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
    item = stage_settings(stage, genre)
    payload = _payload(essay_id, stage, text)
    for key, value in (
        ("master", master),
        ("namedFolder", namedFolder),
        ("answers", answers),
        ("edited", edited),
        ("webCheck", webCheck),
        ("heldFile", heldFile),
    ):
        if value is not None:
            payload[key] = value
    fingerprint = (
        {"stage": stage, "inherited_keep": True}
        if _INHERITED_KEEP.get()
        else {"stage": stage}
    )
    note = _note_path(essay_id, stage)
    body: dict[str, Any] = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "stage_title": stage_title(stage, genre),
        "confirmPhase": confirmPhase,
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
    if stage in {"1", "4a"} or heldFile is not None:
        from essay_writer.databases import database_view, remember_databases

        remember_databases(essay_id, heldFile)
        body["databases"] = database_view(essay_id)
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
    if stage == "7" and confirmPhase == DRAFT and card_only:
        from essay_writer.stage7 import note_questions

        body.update(note_questions(essay_id))
    elif stage == "7" and confirmPhase == DRAFT:
        from essay_writer.stage7 import (
            answers_mean_no_change,
            answers_mean_skip,
            load_stage7,
            note_edits,
            note_questions,
        )

        if answers_mean_skip(text) or answers_mean_skip(answers if isinstance(answers, str) else None):
            return _stage7_skip_reply(essay_id, stage, genre, pointer, confirmPhase)
        # A later draft whose whole note is "no changes" is the answer.
        # The door keeps the text already saved and does not invent sentences.
        if (
            answers is None
            and edited is None
            and webCheck is None
            and load_stage7(essay_id).get("asked") is True
            and answers_mean_no_change(text)
        ):
            answers = text
        if answers is not None or edited is not None or webCheck is not None:
            edited_note = note_edits(essay_id, answers=answers, edited=edited, web_check=webCheck)
            if edited_note.get("ok") is False:
                return refuse(
                    "stage",
                    str(edited_note.get("reason") or "Ask, then edit from the answers."),
                    next=edited_note.get("next"),
                    stage=stage,
                    current=pointer["current"],
                )
            answers = edited_note.get("answers", answers)
            edited = edited_note.get("edited", edited)
            webCheck = edited_note.get("webCheck", webCheck)
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
                ("webCheck", webCheck),
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
    return {
        "_state": True,
        "confirmPhase": confirmPhase,
        "text": text,
        "answers": answers,
        "edited": edited,
        "webCheck": webCheck,
        "payload": payload,
        "fingerprint": fingerprint,
        "body": body,
        "item": item,
        "note": note,
        "revisit": revisit,
        "real_bib": real_bib,
        "short_report": short_report,
        "cite_report": cite_report,
        "pointer": pointer,
        "auto_next": auto_next,
        "minting": minting,
        "card_only": card_only,
        "master": master,
        "namedFolder": namedFolder,
        "heldFile": heldFile,
        "essay_id": essay_id,
        "stage": stage,
        "genre": genre,
    }


def _draft_reply(state: dict[str, Any]) -> dict[str, Any]:
    from essay_writer.spine import stage_confirm_card

    confirmPhase = state["confirmPhase"]
    essay_id = state["essay_id"]
    stage = state["stage"]
    genre = state["genre"]
    pointer = state["pointer"]
    body = state["body"]
    payload = state["payload"]
    fingerprint = state["fingerprint"]
    text = state["text"]
    note = state["note"]
    revisit = state["revisit"]
    real_bib = state["real_bib"]
    auto_next = state["auto_next"]
    minting = state["minting"]
    master = state["master"]
    namedFolder = state["namedFolder"]
    card_only = state["card_only"]
    if confirmPhase == DRAFT:
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


def _save_confirm(state: dict[str, Any], cardDigest: str | None) -> dict[str, Any]:
    essay_id = state["essay_id"]
    stage = state["stage"]
    genre = state["genre"]
    pointer = state["pointer"]
    body = state["body"]
    payload = state["payload"]
    fingerprint = state["fingerprint"]
    text = state["text"]
    note = state["note"]
    revisit = state["revisit"]
    real_bib = state["real_bib"]
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
