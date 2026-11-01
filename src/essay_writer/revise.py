"""Record feedback on the same essay. Does not write a new Word file."""

from __future__ import annotations

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import sequence_write_error, work_dir
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import say
from essay_writer.textutil import citation_tokens, in_text_forms, token_allowed
from essay_writer.validate import inspect_pack, research_index

TOOL = "essay.revise"


def _forms(state: dict[str, object]) -> set[str]:
    allowed, _digests = research_index(state)
    forms: set[str] = set()
    for source in allowed.values():
        if source.get("author") and source.get("year"):
            forms |= in_text_forms(str(source["author"]), str(source["year"]))
    return forms


def essay_revise(
    essay_id: str,
    message: str,
    confirmPhase: str | None = None,
    pack: dict[str, object] | None = None,
) -> dict[str, object]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if not isinstance(message, str) or not message.strip():
        return refuse("revise", "message says what to change. The door does not invent the revision.")
    state = load_state(essay_id)
    has_research = any((state.get("research") or {}).get(depth) for depth in ("summary", "full"))
    has_word = bool(state.get("word"))
    if not has_research and not has_word:
        return refuse(
            "revise",
            "Nothing is confirmed yet. Confirm research, or Word, before revise.",
        )
    forms = _forms(state)
    invented = [
        token for token in citation_tokens(message) if not token_allowed(token, forms)
    ]
    if invented:
        return refuse(
            "invent-forbid",
            f"The revision cites {invented[0]!r}, which was not gathered. Omit it.",
            invent_forbid="refuse",
        )
    note = message.strip()
    # A revision note can carry the ask for shorter citations. The limit is
    # kept on the sequence, and a proposed draft is cut to it here.
    from essay_writer.short_cites import apply_short_cite_request, shorten_sections

    short_report = apply_short_cite_request(essay_id, note, answers=note)
    note = short_report["text"]
    if isinstance(pack, dict) and isinstance(short_report.get("limit"), int):
        sections = pack.get("sections")
        if isinstance(sections, list):
            cut_sections, cut = shorten_sections(sections, short_report["limit"])
            if cut:
                pack = dict(pack)
                pack["sections"] = cut_sections
                short_report["cut"] = list(short_report.get("cut") or []) + cut
                short_report["applied"] = True
    cite_report = None
    if citation_tokens(note):
        from essay_writer.specialists.writer import land_body_cites

        cite_report = land_body_cites(essay_id, "revise", note)
        note = cite_report["text"]
        if not note.strip():
            reason = cite_report.get("ask") or "That paper was not added."
            return refuse(
                "citation",
                str(reason),
                cite_held=cite_report.get("held") or [],
                cite_ask=cite_report.get("ask"),
            )
    report = None
    if pack is not None:
        report = inspect_pack(essay_id, pack)
        hard = [item for item in report["blockers"] if item["code"] in {"invent-forbid", "cross-essay"}]
        if hard:
            return refuse(hard[0]["code"], hard[0]["reason"], blockers=report["blockers"])
    payload: dict[str, object] = {"essay_id": essay_id, "message": note}
    if pack is not None:
        payload["pack"] = pack
    fingerprint = {
        "files": {} if report is None else report["files"],
        "word": sorted((state.get("word") or {}).keys()),
    }
    body: dict[str, object] = {
        "ok": True,
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "message": note,
        "word_rewritten": False,
        "proposed_blockers": [] if report is None else report["blockers"],
        "proposed_notes": [] if report is None else report["notes"],
        "same_arguments_required": True,
        "next": say(
            "Show this revision to the human. Saying yes records the note and does not "
            "write a .docx. A changed draft still needs validate, then Word."
        ),
    }
    _quiet_revise(essay_id, body)
    _attach_short_report(body, short_report)
    _attach_cite_report(body, cite_report)
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        if body.get("quiet") is not True:
            from essay_writer.build_status import begin_mid_build

            body["status"] = begin_mid_build(essay_id, "work")
            body["mid_started"] = True
        return body
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["word_rewritten"] = False
        return ready
    state = load_state(essay_id)
    entry = {
        "digest": ready["digest"],
        "message": note,
        "confirmed_at": now(),
        "word_stale": bool(state.get("word")),
        "proposed_pack": pack is not None,
    }
    state.setdefault("revisions", []).append(entry)
    save_state(essay_id, state)
    body["stored"] = True
    body["digest"] = ready["digest"]
    body["word_stale"] = entry["word_stale"]
    body["confirmed_at"] = entry["confirmed_at"]
    _quiet_revise(essay_id, body)
    _attach_cite_report(body, cite_report)
    if body.get("quiet") is not True:
        from essay_writer.build_status import complete_job

        body["status"] = complete_job(essay_id)
    return body


def _attach_short_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    """Say the cite length the ask set, and how many long stretches were cut."""
    if not isinstance(report, dict):
        return
    limit = report.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return
    raw_cut = report.get("cut")
    cut = raw_cut if isinstance(raw_cut, list) else []
    if report.get("applied") is not True and not cut and report.get("asked") is not True:
        return
    from essay_writer.cite_fit import in_line
    from essay_writer.short_cites import short_line

    body["cite_short"] = {"limit": limit, "cut": len(cut)}
    body["cite_short_line"] = short_line(limit)
    in_line(body, "cite_short_line")


def _attach_cite_report(body: dict[str, object], report: dict[str, object] | None) -> None:
    if not isinstance(report, dict):
        return
    held = report.get("held")
    if isinstance(held, list) and held:
        body["cite_held"] = held
    ask = report.get("ask")
    if isinstance(ask, str) and ask.strip():
        body["cite_ask"] = ask
    gap = report.get("gap")
    if isinstance(gap, str) and gap.strip():
        body["cite_gap"] = gap
    from essay_writer.cite_fit import speak_cite_ask

    speak_cite_ask(body)


def _quiet_revise(essay_id: str, body: dict[str, object]) -> bool:
    """Middle revise during the first draft stays quiet unless the call was refused."""
    from essay_writer.late_chain import QUIET_STEP, mark_quiet
    from essay_writer.stage_track import in_first_draft

    if body.get("ok") is False or not in_first_draft(essay_id):
        return False
    mark_quiet(body, QUIET_STEP, step="revise")
    return True
