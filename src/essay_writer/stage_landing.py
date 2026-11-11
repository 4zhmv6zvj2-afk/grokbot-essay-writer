"""The landing and report helpers for the stage tracking note.

These helpers build the reply pieces a stage draft and save return: the late
chain flag, the stage 6 opening fields, the outline and cite reports, the
no-card store, the mid-run launch, the save misses, and the inherited lock
keep. The orchestrator in essay_writer.stage_track imports this module and
keeps the public entry points.

This module never imports essay_writer.stage_track. The inherited-lock keep
gets the public confirm runner as an injected callable, and the pointer-lost
path gets the same card runner the state layer uses.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from essay_writer.confirm import CONFIRM, confirm_ready, refuse, save_draft
from essay_writer.paths import relative
from essay_writer.stage_llm import brief_genre, next_stage, stage_title
from essay_writer.stage_state import (
    _INHERITED_KEEP,
    TOOL,
    CardRun,
    _commit_pointer,
    _mark_explicit_end,
    _payload,
    _pointer_lost,
    _room_state,
    _saved_after_confirm,
    _snapshot_stage_save,
    _stage5_held,
    render_tracking,
)
from essay_writer.student_voice import student_surface_hits

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
    card_run: CardRun | None = None,
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
        return _pointer_lost(essay_id, stage, genre, card_run=card_run)
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
    token = _INHERITED_KEEP.set(True)
    try:
        saved = run_confirm(
            essay_id,
            stage,
            text,
            digest if isinstance(digest, str) else ready.get("digest"),
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
