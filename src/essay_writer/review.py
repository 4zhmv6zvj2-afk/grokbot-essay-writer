"""Reviewer seat. The writer door does not record EQR.

Stage 6 is the first Word path. Stage 9 is the references confirm.
Only seat=reviewer can store PASS or FAIL.
"""

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
from essay_writer.paths import module_code, sequence_write_error
from essay_writer.review_block import PERSON_BLOCK, writer_clears_left
from essay_writer.review_block import WRITER_CLEARS_LEFT as WRITER_CLEARS_LEFT
from essay_writer.specialists.eqr import REVIEW_PROMPT
from essay_writer.state import guard_damaged_records, load_state, save_state
from essay_writer.student_voice import say

TOOL = "essay.review"
STAGES = frozenset({"6", "9"})
FIRST_DRAFT_WORD_LINE = "The first-draft Word file is saved from the draft that was reviewed."
_WORD_NOT_SAVED = "The finished Word file is not saved yet."


def eqr_record(essay_id: str, stage: str) -> dict[str, object] | None:
    state = load_state(essay_id)
    record = (state.get("eqr") or {}).get(stage)
    if not isinstance(record, dict) or record.get("seat") != "reviewer":
        return None
    return record


def eqr_verdict(essay_id: str, stage: str) -> str | None:
    record = eqr_record(essay_id, stage)
    if record is None:
        return None
    verdict = record.get("verdict")
    if verdict not in {"PASS", "FAIL"}:
        return None
    if verdict == "PASS":
        from essay_writer.model_contract import ContractRefusal, parse_draft_tie, parse_findings
        from essay_writer.specialists.eqr import submit_pass_unlocked

        if isinstance(parse_findings(record.get("findings"), essay_id), ContractRefusal):
            return None
        if stage == "9" and submit_pass_unlocked(essay_id).get("unlocked") is not True:
            return None
        if stage == "6" and "draft_text" in record:
            from essay_writer.word import saved_first_draft_text

            tied = parse_draft_tie(saved_first_draft_text(essay_id), record.get("draft_text"))
            if isinstance(tied, ContractRefusal):
                return None
    return verdict


@guard_damaged_records
def essay_review(
    essay_id: str,
    stage: str,
    verdict: str,
    confirmPhase: str | None = None,
    seat: str = "reviewer",
    constitution: str | None = None,
) -> dict[str, object]:
    """Draft an EQR verdict. Confirm stores it. The writer seat is refused."""
    if seat != "reviewer":
        return refuse(
            "seat",
            PERSON_BLOCK,
            wrote=False,
            writer_clears_left=writer_clears_left(),
        )
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    if stage not in STAGES:
        return refuse(
            "review",
            "The independent review stage is 6 (first Word) or 9 (final Word).",
            next="Send stage 6 or stage 9.",
        )
    from essay_writer.model_contract import ContractRefusal, parse_verdict

    parsed_verdict = parse_verdict(verdict)
    if isinstance(parsed_verdict, ContractRefusal):
        return refuse("review", parsed_verdict.reason)
    verdict = parsed_verdict.verdict
    from essay_writer.specialists.eqr import (
        build_findings,
        claim_check_opened,
        open_finished_word,
        opened_word_gate,
        write_findings_note,
    )

    opened = open_finished_word(essay_id)
    if opened.get("unreadable"):
        return refuse(
            "review",
            "The saved Word file could not be opened. Nothing was recorded.",
            next="Ask me to open the saved Word file again.",
        )
    if opened.get("exists") and not opened.get("opened"):
        return refuse(
            "review",
            "The finished Word file is saved and was not opened. Nothing was recorded.",
            next="Ask me to open the finished Word file.",
        )
    saved_look = None
    if stage == "6" and not opened.get("opened"):
        from essay_writer.word import saved_first_draft_text

        saved_look = saved_first_draft_text(essay_id)
    claim_text = opened.get("text") or ""
    if isinstance(saved_look, str) and not opened.get("opened"):
        claim_text = saved_look
    claim = claim_check_opened(essay_id, claim_text)
    if verdict == "PASS" and claim.get("matches"):
        where = "saved Word file" if opened.get("opened") else "saved draft"
        return refuse(
            "review",
            f"A gathered sentence appears in the {where} without quotation marks. Nothing was recorded.",
            matches=claim["matches"],
        )
    judged_word = (
        opened.get("text") if opened.get("opened") and isinstance(opened.get("text"), str) else ""
    )
    if verdict == "PASS" and stage == "9":
        if opened.get("opened") is not True:
            return refuse(
                "review",
                "Stage 9 checks the opened Word file. Nothing was recorded.",
                next="Open the Word file, then ask for this check again.",
            )
        blocked_gate = opened_word_gate(
            essay_id, judged_word if isinstance(judged_word, str) else ""
        )
        if blocked_gate:
            return blocked_gate
    if verdict == "PASS" and stage == "6":
        from essay_writer.specialists.eqr import answers_assignment_question
        from essay_writer.word import intact_saved_first_draft

        if opened.get("opened"):
            judged = judged_word if isinstance(judged_word, str) else ""
        elif isinstance(saved_look, str):
            if intact_saved_first_draft(essay_id) is None:
                return refuse(
                    "review",
                    "The saved draft is not intact. Ask me to show this step again.",
                )
            judged = saved_look
        else:
            judged = constitution if isinstance(constitution, str) else ""
        if not answers_assignment_question(essay_id, judged):
            return refuse(
                "review",
                "Stage 6 only checks whether the draft answers the assignment question. Nothing was recorded.",
                next="Ask the question check again. Nothing was recorded.",
            )
    top_band = None
    if verdict == "PASS" and stage == "9":
        from essay_writer.specialists.eqr import mark_top_band_rows

        opened_text = opened.get("text") if opened.get("opened") else ""
        if not isinstance(opened_text, str):
            opened_text = ""
        top_band = mark_top_band_rows(essay_id, opened_text)
        if top_band.get("marked") and top_band.get("top_band") is not True:
            missed = ", ".join(str(item) for item in top_band.get("missed") or [])
            return refuse(
                "review",
                f"The review marks the top band for {missed}. Nothing was recorded.",
                top_band=top_band,
            )
        from essay_writer.textutil import citation_tokens

        if not citation_tokens(opened_text):
            return refuse(
                "review",
                "The opened Word file has no citations. Nothing was recorded.",
                top_band=top_band,
                next="Add the citations, then ask for this check again.",
            )
    if verdict == "PASS" and opened.get("opened") is True:
        from essay_writer.harvard_ref_check import clear_reference_findings
        from essay_writer.specialists.eqr import finished_word_path

        reviewed = clear_reference_findings(
            essay_id,
            finished_word_path(essay_id),
            seat="reviewer",
        )
        if reviewed.get("cleared") is not True:
            return reviewed
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase
    findings_opened = opened
    if isinstance(saved_look, str) and not opened.get("opened"):
        findings_opened = dict(opened)
        findings_opened["text"] = saved_look
    findings = build_findings(essay_id, findings_opened, claim)
    if top_band is not None:
        from essay_writer.specialists.eqr import with_top_band_marks

        findings = with_top_band_marks(findings, top_band)
    payload = {"essay_id": essay_id, "stage": stage, "verdict": verdict, "seat": "reviewer"}
    fingerprint = {
        "stage": stage,
        "verdict": verdict,
        "seat": "reviewer",
        "word": opened.get("sha256") or "absent",
        "places": list(opened.get("places") or []),
    }
    if constitution is not None:
        payload["constitution"] = constitution
        fingerprint["constitution"] = constitution
    body: dict[str, object] = {
        "ok": True,
        "essay_id": essay_id,
        "stage": stage,
        "verdict": verdict,
        "seat": "reviewer",
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "word_opened": bool(opened.get("opened")),
        "findings": findings,
    }
    if top_band is not None:
        body["top_band"] = top_band
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        from essay_writer.build_status import begin_mid_build

        body["status"] = begin_mid_build(essay_id, "work")
        body["mid_started"] = True
        if opened.get("opened"):
            body["next"] = say(
                "The review opened the saved Word file. "
                f"Say yes to record {verdict} for stage {stage}."
            )
        else:
            body["next"] = say(
                "Reviewer only. The finished Word file is not saved yet. "
                f"Say yes to record {verdict} for stage {stage}."
            )
        return body
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    draft_text = None
    first_draft_word = None
    if verdict == "PASS" and stage == "6" and not opened.get("opened"):
        from essay_writer.word import intact_saved_first_draft, write_first_draft_word

        saved_draft = intact_saved_first_draft(essay_id)
        if not isinstance(saved_draft, str) or not saved_draft.strip():
            return refuse(
                "review",
                "The saved draft is not intact. Ask me to show this step again.",
            )
        written = write_first_draft_word(essay_id)
        if written.get("wrote") is not True:
            reason = written.get("reason")
            if reason == "already-saved":
                reason = (
                    "The first-draft Word file is already saved. Ask me to show the review again."
                )
            elif not isinstance(reason, str) or not reason or reason == "not-intact":
                reason = "The saved draft is not intact. Ask me to show this step again."
            return refuse("review", reason, first_draft_word=written)
        draft_text = saved_draft
        first_draft_word = written
        updated = findings.replace(_WORD_NOT_SAVED, FIRST_DRAFT_WORD_LINE, 1)
        if updated != findings:
            findings = updated
            body["findings"] = findings
    findings_file = {"wrote": False, "place": "", "reason": ""}
    if opened.get("opened"):
        findings_file = write_findings_note(essay_id, findings)
    state = load_state(essay_id)
    eqr = state.get("eqr")
    if not isinstance(eqr, dict):
        eqr = {}
    eqr[stage] = {
        "verdict": verdict,
        "seat": "reviewer",
        "stage": stage,
        "at": now(),
        "word_opened": bool(opened.get("opened")),
        "submit_sha256": opened.get("sha256") if opened.get("opened") else "",
        "findings": findings,
        "findings_place": findings_file.get("place") or "",
        "opened_places": list(opened.get("places") or []),
    }
    if isinstance(draft_text, str):
        eqr[stage]["draft_text"] = draft_text
    if top_band is not None:
        eqr[stage]["top_band"] = top_band
    state["eqr"] = eqr
    save_state(essay_id, state)
    body["wrote"] = True
    body["stored"] = True
    body["findings_file"] = findings_file
    chat_docx = findings_file.get("chat_docx")
    if isinstance(chat_docx, dict):
        body["delivery"] = {"findings": chat_docx}
    body["digest"] = ready["digest"]
    from essay_writer.build_status import complete_job
    from essay_writer.specialists.grok_bot import findings_delivery_next

    body["status"] = complete_job(essay_id)
    filename = f"{module_code(essay_id)}-findings.docx"
    if opened.get("opened") and isinstance(chat_docx, dict):
        unmounted = findings_file.get("reason") == "mac-not-mounted"
        tail = None
        if not unmounted:
            places = [place for place in (opened.get("places") or []) if isinstance(place, str)]
            if len(places) >= 2:
                tail = f"Opened from both places at {places[-1]}."
        body["next"] = say(findings_delivery_next(filename, unmounted=unmounted, next_line=tail))
    elif opened.get("opened") and findings_file.get("reason") == "mac-not-mounted":
        from essay_writer.late_chain import FINDINGS_UNMOUNTED

        body["next"] = say(FINDINGS_UNMOUNTED)
    elif opened.get("opened"):
        places = [place for place in (opened.get("places") or []) if isinstance(place, str)]
        if len(places) >= 2:
            body["next"] = say(
                f"The review opened the saved Word file and {places[-1]}. Opened from both places."
            )
        else:
            body["next"] = say("The review opened the saved Word file.")
    elif isinstance(first_draft_word, dict):
        body["first_draft_word"] = {
            "wrote": True,
            "path": first_draft_word.get("path") or "",
            "counted_words": first_draft_word.get("counted_words"),
        }
        body["next"] = say(FIRST_DRAFT_WORD_LINE)
    return body


def place_findings_note(essay_id: str, *, documents=None) -> dict[str, object]:
    """Write the stored full findings note into Documents/<project>/.

    This does not record a new verdict. A one-line pass is not a findings file.
    """
    from essay_writer.specialists.eqr import (
        findings_note_clears,
        open_finished_word,
        with_opened_places,
        write_findings_note,
    )

    record = eqr_record(essay_id, "9")
    findings = record.get("findings") if isinstance(record, dict) else ""
    if not isinstance(findings, str) or not findings_note_clears(findings, essay_id):
        return {
            "ok": False,
            "wrote": False,
            "place": "",
            "reason": "no-findings-note",
            "refused": "findings",
        }
    opened = open_finished_word(essay_id, documents=documents)
    text = with_opened_places(findings, opened)
    written = write_findings_note(essay_id, text, documents=documents)
    if written.get("wrote") and isinstance(record, dict) and text != findings:
        state = load_state(essay_id)
        eqr = state.get("eqr")
        if isinstance(eqr, dict) and isinstance(eqr.get("9"), dict):
            eqr["9"]["findings"] = text
            eqr["9"]["findings_place"] = written.get("place") or ""
            eqr["9"]["opened_places"] = list(opened.get("places") or [])
            state["eqr"] = eqr
            save_state(essay_id, state)
    return written


# Operator briefing. The stage prompt is REVIEW_PROMPT. This tail is not that prompt.
REVIEW_INSTRUCTIONS = (
    REVIEW_PROMPT
    + "\nGrok Bot may relay your verdict to the user. Grok Build does not own this chat."
)
