"""Grok Bot. Private banking Relationship Manager.

One client-facing personality, whichever stage is calling. The confirm
ledger stays in essay_writer.confirm. confirm_gate runs before a stage save.
Sequence-delete speech stays here. Mid-build progress sentences are said from
here. A stage save is a clickable Confirm card from this layer.
Research, writing, and independent review stay behind the curtain.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer.assignment_gate import assignment_gate, mark_scheme_text
from essay_writer.confirm import DRAFT, refuse
from essay_writer.paths import workspace_root
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import say, speak

ROLE = "grok_bot"

# Opening contract. The continue list still names every module. A new student does not inherit one.
OPENING_CHOICE = (
    "When a run starts, offer three choices before any leftover module. "
    "A is a new essay: start it with essay.sequence.new. "
    "B is continue, and only for a sequence this student names. "
    "C is roll forward: ask first, then the user names the parent sequence to copy. "
    "Call essay.sequence.new with that parent. "
    "The new id is always the module last sequence number plus one, not parent plus one. "
    "Do not continue a leftover module for a new student. "
    "A leftover sequence such as MOD1004AA-2 stays on disk. "
    "Do not delete it, and do not offer it unless this student names it. "
    "essay.projects lists those choices. "
    "Continue lists every active module with the last-saved sequence id on essay_id, such as MOD1011AA-5. "
    "If the last sequential id is different, name both. If they are the same, say it once. "
    "If you cannot find a sequence, ask whether to start a new one. "
    "essay.projects view roll-forward with the module lists sequences with sequence_pick true."
)

# Canonical client-language rule. Shells and the bot sheet use this text.
LANGUAGE = (
    "Default to English in student chat. Match the language of the student's current "
    "message: reply in the same language family they used. Word files, stages, "
    "helpers, Harvard Referencing, invent-forbid, and door/tool names stay English "
    "unless the brief requires otherwise. Do not translate authors, journals, paper "
    "titles, DOIs/URLs, Harvard cites, module ids, tool names, or file names."
)

# Stage prompt and tracking note. The save label "Confirm" stays off this text.
# The short Basics pass is the chat opening. The rest of the checklist stays out.
BASICS_FIRST_LINES = (
    "Before the save, the chat opens with a short Basics pass. "
    "The first three lines are what the mark scheme scores, "
    "the format the brief names, "
    "and the assignment question in the student's words. "
    "Later bullets stay short. "
    "Delivering annotation.docx alone is not this pass. "
    "Do not paste the rest of the Basics checklist into the chat. "
    "Stage 5 stays quiet and does not paste the whole checklist. "
)

CHECKLIST_WALK = BASICS_FIRST_LINES + (
    "Walk this Basics checklist internally before the save. "
    "Record the answers in the tracking note. "
    "Student chat is warm, helpful, encouraging, and concise: only what the person must know. "
    "A bullet list or a table is fine when the content is long. "
    "Limits the person must know, such as Stage 1 limiting conditions, always appear in that prose. "
    "Student chat never shows ~/… or a drive path the student did not name. "
    "Name Documents/… only when that folder is already on this computer. "
    "When it is not, the file stays in this chat and on this sequence. Do not invent a Documents path. "
    "Setup notes stay with the operator. Do not recite install steps in student chat, "
    "and do not offer a leftover module unless the student names that sequence. "
    "In the chat, the place is Grok Bot chat delivery, or a folder the student already named. "
    "On first use in student-facing prose, gloss jargon and acronyms in plain English (for example GHG Scope 1, 2, and 3). The example is not a closed list. "
    "Plain-English gloss only. Do not invent a company's methods or data practices. Name a method only when an opened gathered file states it in a sentence you can point to. "
    "The chat is natural helper prose, then a clean line to approve the save."
)

MCP_DOWN_SPEECH = (
    "If essay-writer MCP tools are unavailable, stop. "
    "Do not hand-write annotation.docx, download-list.docx, or papers.zip."
)

# Private banking Relationship Manager. Not sales. Not thin customer service.
# Not a generic bank script. Client chat never hears the desk behind this note.
ROLE_NOTE = (
    "Grok Bot is a private banking Relationship Manager. "
    "The service is bespoke for this client: know the assignment, the brief, and the mark scheme, "
    "and use excellent client-serving skills. It is not one generic script. "
    "The Relationship Manager is client-facing, stays professional, and owns the relationship "
    "and the client's satisfaction. "
    "Not sales. Not thin customer service. Not a generic bank role without the private-banking bar. "
    "Front-desk work may think through and draft the first three steps with the client. "
    "Deeper research, the writing, and the independent review stay behind the curtain. "
    "Propose options and one next step. Do not describe how that work runs. "
    "The client hears what happened for them and what to do next. "
    "Never name a worker, a command line, a model flag, a status file, or an internal path. "
    "If the client has to chase, decode jargon, or wait without a next step, the service failed."
)

# Delete uses the same Confirm card as a stage save. A typed yes does not remove.

# MCP door text. Confirm is the save label on the door, not in the stage file.
DOOR_WALK = BASICS_FIRST_LINES + (
    "Record the answers in the tracking note. "
    "The rest of the Basics checklist stays in the stage prompt and in the tracking note. "
    "Student chat is warm, helpful, encouraging, and concise: only what the person must know. "
    "A bullet list or a table is fine when the content is long. "
    "Always surface limits the person must know, such as Stage 1 limiting conditions. "
    "The chat outcome is the short Basics pass, then a clean Confirm."
)

_FILE_ONLY = frozenset({"annotation.docx", "download-list.docx", "papers.zip"})
CRITICAL_REVIEWS_ZIP = "critical-reviews.zip"


CARD_CONFIRM = "confirm"
CARD_NOT_YET = "not_yet"
_TYPED_SAVE = frozenset({"confirm", "yes", "ok"})

# Operator text. A group-room agent that cannot tap the card copies these fields.
# A typed yes, ok, or Confirm still does not save.
ROOM_CONFIRM_PATH = (
    "In a group room, a student or another agent may be unable to tap the Confirm card. "
    "The draft reply returns cardAction confirm and cardDigest from that waiting draft. "
    "Send confirmPhase confirm with those two fields copied from the reply. "
    "Do not invent a digest. "
    "A typed yes, ok, or Confirm does not save. "
    "A line such as Press Confirm for Stage N does not save by itself. "
    "It shows the waiting card again, including cardAction and cardDigest. "
    "Sending that press together with cardAction and cardDigest from the waiting draft "
    "saves that stage in one call. A second identical press is not required."
)

# Operator text. A finished answer returns a card and does not save. Not stage 7 only.
STAGE7_AFTER_ANSWERS = (
    "A student answer that finishes the ask, including a clear no changes, all fine, or none, "
    "is one tool call whose result is spoken in that same turn. "
    "That answer keeps the draft already saved and does not invent sentences. "
    "It returns the Confirm card and does not save. "
    "Do not leave tracking on Status draft with no next ask. "
    "A skip does not save and does not end the turn. Refuse the skip and ask the questions again in that same reply. "
    "Confirm with cardAction and cardDigest from that card saves the stage. "
    "Stray answers, edited text, a web check, or a look on that confirm do not change the card and do not change the phase."
)

# One press names one stage. A later stage is a different press. Operator only.
STAGE_CONFIRM_EACH = (
    "Operator only. Never read this block to the student. "
    "Each stage is saved only by a Confirm for that stage. "
    "Press Confirm for Stage N copies the waiting draft fields for stage N only. "
    "It does not save stage N+1 or stage N+2. "
    "Stage 4a needs its own Confirm before it is saved and before stage 4b. "
    "A typed Confirm, yes, or ok does not save. "
    "A typed reply does not save. "
    "The card shown is the one in the latest tool result for the current stage. "
    "Essay Bot may only show the Confirm card the door returned. "
    "It does not pick the next stage itself. "
    "Before any card is shown, follow the pointer. "
    "If this stage is already saved, or the current stage is later, do not show that card. "
    "Say the tool's next and the card the tool returned for the current stage. "
    "Do not leave the stage with no next ask. "
    "Stage 5 stores on the draft and starts stage 6. "
    "There is no Confirm card between stage 5 and stage 6. "
    "Stages 8, 9, and 10 keep their own Confirm cards. "
    "Do not save a later stage in the same press. "
    "Post a Confirm only when its cardDigest matches the door's latest result "
    "for the current open sequence. "
    "Refuse a closed pack, a wrong sequence, and inventing the next stage. "
    "When a sequence opens, post only the Confirm card in that door result. "
    "That card's sequence id is the sequence that opened. "
    "Do not post a Confirm from another sequence."
)

_PRESS_CONFIRM = re.compile(
    r"^press confirm(?: for stage (?P<stage>[0-9]+[a-z]?|n))?$",
    re.IGNORECASE,
)


def confirm_reply_fields(digest: str) -> dict[str, str]:
    """The confirm call copies these. They are the waiting draft, not a new digest."""
    return {"cardAction": CARD_CONFIRM, "cardDigest": digest}


def confirm_card(
    essay_id: str,
    stage: str,
    digest: str,
    summary: str,
    *,
    stage_title: str,
) -> dict[str, object]:
    """One chat card. The label stays on the action. Speech does not scrub it."""
    return {
        "deliver": "chat",
        "kind": "confirm",
        "name": f"Stage {stage} — {stage_title}",
        "essay_id": essay_id,
        "stage": stage,
        "digest": digest,
        **confirm_reply_fields(digest),
        "text": summary,
        "actions": [
            {"id": CARD_CONFIRM, "label": "Confirm"},
            {"id": CARD_NOT_YET, "label": "Not yet"},
        ],
    }


def typed_save_word(value: str | None) -> bool:
    """True when the whole reply is Confirm, yes, or ok. The card id confirm is not this."""
    if not isinstance(value, str):
        return False
    token = re.sub(r"[^A-Za-z]+", "", value).casefold()
    return token in _TYPED_SAVE


def typed_save_attempt(card_action: str | None, look: str | None) -> bool:
    """A typed Confirm, yes, or ok while a card is the save. Not yet is a choice."""
    if card_action == CARD_NOT_YET or card_action == CARD_CONFIRM:
        return False
    return typed_save_word(card_action) or typed_save_word(look)


def press_confirm_stage(value: str | None) -> str | None:
    """Stage named by a room press. Empty string means this call's stage. None if this is not a press."""
    if not isinstance(value, str):
        return None
    token = re.sub(r"\s+", " ", value).strip().strip(" .!\"'`")
    match = _PRESS_CONFIRM.fullmatch(token)
    if match is None:
        return None
    named = match.group("stage")
    if named is None or named.casefold() == "n":
        return ""
    if named[-1].isalpha():
        return named[:-1] + named[-1].casefold()
    return named


def room_press_confirm(value: str | None) -> bool:
    """A room line that asks to press the waiting card. The line itself does not save."""
    return press_confirm_stage(value) is not None


def accept_card_pick(card_action: str | None):
    """None when the person picked the card. Any other reply refuses."""

    if card_action == CARD_CONFIRM:
        return None
    if card_action == CARD_NOT_YET:
        return refuse(
            "confirm-card",
            "Not yet leaves this step unsaved.",
            wrote=False,
            stored=False,
            advanced=False,
        )
    return refuse(
        "confirm-card",
        "A typed reply does not save this step. Pick the card in the draft reply.",
        wrote=False,
        stored=False,
        advanced=False,
    )


def delete_confirm_card(
    module: str,
    digest: str,
    summary: str,
    *,
    sequence: str | None = None,
) -> dict[str, object]:
    """Delete look, then the same Confirm / Not yet card. A typed yes does not remove."""
    label = sequence or module
    return {
        "deliver": "chat",
        "kind": "confirm",
        "name": f"Delete {label}",
        "essay_id": label,
        "digest": digest,
        **confirm_reply_fields(digest),
        "text": summary,
        "actions": [
            {"id": CARD_CONFIRM, "label": "Confirm"},
            {"id": CARD_NOT_YET, "label": "Not yet"},
        ],
    }


def card_next(stage: str, title: str) -> str:
    """One next step: the Confirm card, or Not yet. A typed reply does not save."""
    return (
        f"Open the Confirm card to save Stage {stage} — {title}, "
        "or choose Not yet to keep working in this chat."
    )


# One sentence after the stage 9 save. Citations and the brief's person stay.
STAGE9_OWN_WORDS = (
    "Rewrite the title, the opening, and one body paragraph in your own words, "
    "and keep the citations and the person the brief names."
)


def saved_next(stage: str, title: str) -> str:
    """The step after a save. Show the card this result returned for that stage.

    Stage 5 stores on its draft and has no Confirm card between it and stage 6.
    After stage 9, the student next line names the own-words rewrite.
    """
    lead = f"Start Stage {stage} — {title} in this chat."
    if stage == "5":
        return lead
    line = (
        f"{lead} Show the card in this result for Stage {stage}. "
        "Do not show a card for a stage that is already saved. "
        "Do not pick the next stage yourself."
    )
    if stage == "10":
        return f"{STAGE9_OWN_WORDS} {line}"
    return line


def missing_confirm_next(stage: str, title: str) -> str:
    """A refused Confirm still names the card. The turn does not end with no ask."""
    return (
        f"Open the Confirm card for Stage {stage} — {title} in this chat. "
        "Show this step first. A typed reply does not save it."
    )


def revisit_plan_next(title: str) -> str:
    return f"Open Stage 3 — {title} in this chat, then start the first draft."


def stage7_lead(questions: list[str], title: str) -> str:
    """Stage 7 opens with the questions and the named Confirm card."""
    if not questions:
        return card_next("7", title)
    numbered = " ".join(f"{index}. {question}" for index, question in enumerate(questions, 1))
    return (
        "Please answer these questions in this chat. "
        f"{numbered} "
        f"Then open the Confirm card to save Stage 7 — {title}, "
        "or choose Not yet to keep working."
    )


def wait_next() -> str:
    return "Wait while this step finishes in this chat."


# First time the writer path needs EQR before Word. Spoken once per workspace.
EQR_FIRST_RUN_SPEECH = (
    "Independent review runs in a separate specialist review. "
    "That review is not a writer-stage save in this chat."
)


def eqr_first_run_tip_sha() -> str:
    """Stable id for the first-run EQR FO line. PR bodies cite this."""
    return hashlib.sha256(EQR_FIRST_RUN_SPEECH.encode("utf-8")).hexdigest()[:12]


def _eqr_first_run_marker_path() -> Path | None:

    root = workspace_root() / "Essay-writer"
    if not root.is_dir() and not os.environ.get("ESSAY_WRITER_ROOT"):
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
    return root / ".eqr-first-run.json"


def _eqr_first_run_seen() -> bool:
    path = _eqr_first_run_marker_path()
    if path is None or not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and data.get("spoken") is True


def _mark_eqr_first_run_seen() -> None:
    path = _eqr_first_run_marker_path()
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"spoken": True}, indent=2) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _take_eqr_first_run_intro() -> str | None:
    if _eqr_first_run_seen():
        return None
    _mark_eqr_first_run_seen()
    return EQR_FIRST_RUN_SPEECH


def attach_eqr_first_run_speech(body: dict[str, object]) -> dict[str, object]:
    """Mark the one-time EQR path line on the writer Word door. Cursor and Build share this."""
    stage = body.get("stage")
    if stage not in {"6", "9"} or body.get("eqr") == "PASS":
        return body
    intro = _take_eqr_first_run_intro()
    if intro:
        body["eqr_first_run_line"] = intro
    return body


_CURTAIN = re.compile(
    r"cli-prompt|agent-cli\.log|5-draft-scratch|status\S{0,40}\.txt|launching\s+cursor\s+cli|"
    r"\bcursor\s+cli\b|\bagent\s+--model\b|--model\b|\bmid_office_launch\b|"
    r"\b(?:Researcher|Writer|Reviewer|EQR)\b|\b(?:mid|front)[ -]office\b|"
    r"(?:Essay-writer|uploads|tracking|sequences)/",
    re.IGNORECASE,
)
_CURTAIN_FALLBACK = "I am still with you on this step. The next choice is in this chat."


def hide_curtain(text: str) -> str:
    """Student speech is what happened and what is next. Not the machinery."""
    if not isinstance(text, str) or not text:
        return text
    if _CURTAIN.search(text):
        return _CURTAIN_FALLBACK
    return text


def _hide_reply(body: dict[str, object]) -> dict[str, object]:
    """Drop the launch payload and any curtain echo from speech fields."""

    intro = body.pop("eqr_first_run_line", None)
    body.pop("mid_office_launch", None)
    for key in ("next", "chat", "reason", "confirm_line"):
        value = body.get(key)
        if isinstance(value, str):
            body[key] = hide_curtain(value)
    status = body.get("status")
    if isinstance(status, list):
        body["status"] = [hide_curtain(line) if isinstance(line, str) else line for line in status]
    if isinstance(intro, str) and intro.strip():
        tail = body.get("next")
        if isinstance(tail, str) and tail.strip():
            body["next"] = say(f"{intro} {tail}")
        else:
            body["next"] = say(intro)
    return body


def confirm_line(stage: str, genre: str | None, *, revisit: bool = False) -> str:
    """The same save line for every stage. The stage title comes from the overlay."""
    from essay_writer.stage_llm import stage_settings, stage_title

    if revisit and stage == "2":
        return (
            "Confirm to save this lock, then save the plan "
            f"(**Stage 3 — {stage_title('3', genre)}**) before the first draft."
        )
    if revisit and stage == "3":
        return (
            "Confirm to save the plan, then go to "
            f"**Stage 5 — {stage_title('5', genre)}**."
        )
    item = stage_settings(stage, genre)
    following = item["next_stage"]
    if following:
        return (
            f"Confirm to save the final look and go to **Stage {following} — "
            f"{item['next_stage_title']}**."
        )
    return "Confirm to save the final look. The tool does not submit."


def basics_pass_lines(essay_id: str) -> tuple[str, str, str]:
    """The three lines chat shows before a save. The question stays in the student's words."""
    import re


    record = essay_assignment_gate.read_assignment(essay_id)
    scheme = mark_scheme_text(essay_id)
    band = record.get("highest_band") if isinstance(record.get("highest_band"), str) else ""
    snippet = ""
    if record.get("mark_scheme") and band:
        for line in scheme.splitlines():
            if band.casefold() in line.casefold() and line.strip():
                snippet = re.sub(r"\s+", " ", line).strip()
                break
    from essay_writer.brief_contract import FINDINGS_HOW_TO_SCORE_HIGH, FINDINGS_NONE

    # The assignment label picks the sentence. A later type uses the same label.
    kind = record.get("findings_opening")
    if kind == FINDINGS_HOW_TO_SCORE_HIGH and record.get("mark_scheme") and band:
        from essay_writer.diary import top_column_quote

        quoted = top_column_quote(scheme, band)
        scores = f"How to score high: {quoted}."
    elif kind == FINDINGS_NONE or not record.get("mark_scheme"):
        scores = "No mark scheme is on this module."
    elif snippet:
        scores = f"The mark scheme scores {snippet}."
    elif band:
        scores = f"The mark scheme scores {band}."
    else:
        scores = "The mark scheme is on this module and does not name what it scores."
    named = record.get("format") if isinstance(record.get("format"), str) else ""
    if named:
        format_line = f"Format: {named}."
    else:
        format_line = "Format: the brief does not name one."
    question = record.get("question") if isinstance(record.get("question"), str) else ""
    if question:
        question_line = f"Question: {question}"
    else:
        question_line = "Question: the brief does not name one."
    return scores, format_line, question_line


def standard_opening(essay_id: str) -> str:
    """The one scores line wherever a standard sentence is required.

    A diary table prints How to score high and the printed top column.
    An essay or a report with a scheme prints what the mark scheme scores.
    With no scheme, the line says no mark scheme is on the module.
    A later writing type uses this function. It does not grow a second sentence.
    """
    return basics_pass_lines(essay_id)[0]


def basics_pass_opens(text: str, lines: tuple[str, str, str]) -> bool:
    opened = [line.strip() for line in text.splitlines() if line.strip()]
    return len(opened) >= 3 and tuple(opened[:3]) == lines


def _scores_line_shaped(line: str) -> bool:
    return (
        line.startswith("The mark scheme scores")
        or line.startswith("How to score high:")
        or line.startswith("No mark scheme is on this module.")
        or line == "The mark scheme is on this module and does not name what it scores."
    )


def basics_pass_replaced_wrong(text: str, lines: tuple[str, str, str]) -> bool:
    """True when the note opens with three Basics-shaped lines that are not the brief's pass."""
    opened = [line.strip() for line in text.splitlines() if line.strip()]
    if len(opened) < 3:
        return False
    triple = tuple(opened[:3])
    if triple == lines:
        return False
    scores, format_line, question_line = triple
    if not format_line.startswith("Format:") or not question_line.startswith("Question:"):
        return False
    return _scores_line_shaped(scores)


def cached_approved_look(essay_id: str) -> str | None:

    value = load_state(essay_id).get("approved_look")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def remember_approved_look(essay_id: str, look: str) -> None:

    if not isinstance(look, str) or not look.strip():
        return
    state = load_state(essay_id)
    state["approved_look"] = look.strip()
    save_state(essay_id, state)


def seed_basics_look(essay_id: str, text: str) -> str:
    """Prefill the three Basics lines from the brief, or reuse the last approved look."""
    lines = basics_pass_lines(essay_id)
    if basics_pass_opens(text, lines):
        return text
    cached = cached_approved_look(essay_id)
    stripped = text.strip()
    if not stripped:
        return cached if cached else "\n".join(lines)
    prefix = "\n".join(lines)
    if cached and basics_pass_opens(cached, lines):
        tail = stripped
        if tail.casefold() == cached.casefold():
            return cached
        return f"{prefix}\n{tail}"
    return f"{prefix}\n{stripped}"


def maybe_seed_basics_on_draft(
    essay_id: str,
    stage: str,
    confirm_phase: str | None,
    text: str,
    *,
    minting: bool,
) -> tuple[str, bool]:
    """On draft, prepend the Basics pass instead of refusing when the note never opened with it."""

    if minting or stage == "5" or confirm_phase != DRAFT:
        return text, False

    if essay_assignment_gate.read_assignment(essay_id).get("active") is not True:
        return text, False
    lines = basics_pass_lines(essay_id)
    if basics_pass_opens(text, lines):
        return text, False
    if basics_pass_replaced_wrong(text, lines):
        return text, False
    from essay_writer.fo_chat_locks import seed_inherited_look

    seeded = seed_basics_look(essay_id, seed_inherited_look(essay_id, stage, text))
    return seeded, seeded != text


def delivery_file_only(text: str) -> bool:
    """True when the note is only a delivered file name. That is not the Basics pass."""
    return text.strip().casefold() in _FILE_ONLY


def critical_reviews_delivery_next(next_line: str) -> str:
    """Name the 4b zip in chat, then the following stage ask."""
    lead = f"{CRITICAL_REVIEWS_ZIP} is attached in this chat."
    if not isinstance(next_line, str) or not next_line.strip():
        return lead
    return f"{lead} {next_line.strip()}"


def findings_delivery_next(
    filename: str,
    *,
    unmounted: bool,
    next_line: str | None = None,
) -> str:
    """Name the findings Word file in chat after a review save."""
    if unmounted:
        lead = (
            f"The review opened the saved Word file. "
            f"{filename} is attached in this chat. "
            "The Mac folder is not on this computer, so the findings stay on this sequence."
        )
    else:
        lead = f"The review opened the saved Word file. {filename} is attached in this chat."
    if isinstance(next_line, str) and next_line.strip():
        return f"{lead} {next_line.strip()}"
    return lead


def basics_pass_block(essay_id: str, text: str) -> dict[str, object] | None:
    """Refuse a save while the short Basics pass is not the first three lines.

    Daily use, with no brief and no mark scheme, is unchanged. Stage 5 does not call this.
    """

    record = essay_assignment_gate.read_assignment(essay_id)
    if record.get("active") is not True:
        return None
    lines = basics_pass_lines(essay_id)
    if basics_pass_opens(text, lines):
        return None
    if basics_pass_replaced_wrong(text, lines):
        reason = (
            "Before the save, the chat opens with the short Basics pass. "
            "The first three lines are what the mark scheme scores, "
            "the format the brief names, and the assignment question in the student's words. "
            "Those three lines must match the brief on this module."
        )
    else:
        reason = (
            "Before the save, the chat opens with the short Basics pass. "
            "The first three lines are what the mark scheme scores, "
            "the format the brief names, and the assignment question in the student's words. "
            "Delivering annotation.docx alone is not this pass."
        )
    return refuse(
        "basics-pass",
        reason,
        basics_pass=list(lines),
    )


def attach_basics_pass(essay_id: str) -> list[str] | None:
    """The three lines for a reply, when a brief or mark scheme is on the module."""

    if essay_assignment_gate.read_assignment(essay_id).get("active") is not True:
        return None
    return list(basics_pass_lines(essay_id))


def confirm_gate(essay_id: str, look: str) -> dict[str, object] | None:
    """Refuse Confirm while the constitution is on and the note misses it."""

    report = assignment_gate(essay_id, look, seat="grok_bot")
    if report.get("ok") is True:
        return None
    return refuse("assignment-gate", str(report.get("reason") or ""), assignment=report)


def sequence_delete_speech(sequence_id: str, *, computer: bool) -> str:
    """Client speech for deleting one sequence. The whole module uses other words."""

    if computer:
        text = (
            f"This deletes only {sequence_id} in this essay workspace, "
            "and it removes the Word and zip files listed for your computer. "
            "Other sequences, the brief, and uploads stay. "
            "Open the Confirm card to remove this list, or choose Not yet to keep it. "
            "These files on your computer will be removed."
        )
    else:
        text = (
            f"This deletes only {sequence_id}. "
            "Other sequences, the brief, and uploads stay. "
            "Copies on your computer stay. "
            "Open the Confirm card to remove this list, or choose Not yet to keep it."
        )
    return say(text)


# Standing chat heading. Sequence id alone. There is no host call that renames
# the Grok chat or the agent, so FO posts this line from the reply field.
STANDING_HEADING = (
    "When a reply includes heading, post that line as the standing chat heading. "
    "The heading is the sequence id alone, such as MOD1004AA-3. "
    "The module already sits inside that id, so the heading is that id and nothing in front of it. "
    "A form such as MOD1004AA · MOD1004AA-3 repeats the module. Post MOD1004AA-3. "
    "Post the heading when an essay opens, after each stage Confirm, and when the active essay changes. "
    "Leave the heading off later turns of the same essay."
)

_PREFIXED_SEQUENCE = re.compile(
    r"^(?P<module>[A-Za-z0-9]+)\s*[·•]\s*(?P<sequence>\S+?)\s*$"
)
_HEADING_SKIP = frozenset(
    {
        "essay.debug.wipe",
        "essay.health",
        "essay.setup",
        "essay.projects",
        "essay.project.archive",
        "essay.project.unarchive",
        "essay.project.delete",
        "essay.unassigned.collect",
        "essay.intake",
    }
)
_LAST_STANDING_HEADING: dict[str, str] = {}


def standing_heading_label(value: object, module: str | None = None) -> str | None:
    """Sequence id alone. A module prefix is dropped when the id already starts with it."""
    from essay_writer.projects import parse_sequence_id, sequence_id

    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    prefixed = _PREFIXED_SEQUENCE.fullmatch(text)
    if prefixed:
        text = prefixed.group("sequence").strip()
    parsed = parse_sequence_id(text)
    if parsed is None:
        return None
    label = sequence_id(parsed[0], parsed[1])
    named = module.strip() if isinstance(module, str) else ""
    if named and label.casefold().startswith(named.casefold()):
        return label
    return label


def _heading_phase(arguments: dict[str, object], body: dict[str, object]) -> str:
    phase = arguments.get("confirmPhase")
    if not isinstance(phase, str) or not phase.strip():
        phase = body.get("confirmPhase")
    if not isinstance(phase, str):
        return ""
    return phase.strip()


def _heading_module(arguments: dict[str, object], body: dict[str, object]) -> str | None:
    for source in (body, arguments):
        module = source.get("module")
        if isinstance(module, str) and module.strip():
            return module.strip()
    return None


def _active_sequence_label(arguments: dict[str, object], body: dict[str, object]) -> str | None:
    module = _heading_module(arguments, body)
    candidates: list[object] = [
        arguments.get("essay_id"),
        arguments.get("sequence"),
        body.get("sequence_id"),
        body.get("essay_id"),
    ]
    card = body.get("card")
    if isinstance(card, dict):
        candidates.append(card.get("essay_id"))
    for item in candidates:
        label = standing_heading_label(item, module=module)
        if label:
            return label
    return None


def _heading_workspace_key() -> str:

    return str(workspace_root())


def attach_standing_heading(
    body: dict[str, object],
    *,
    tool: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Set heading to the sequence id at open, after stage Confirm, and on a switch.

    Later turns of the same essay omit the field so the line is not dumped every turn.
    """
    if body.get("ok") is False or tool in _HEADING_SKIP:
        return body
    phase = _heading_phase(arguments, body)
    stored = body.get("stored") is True
    if tool == "essay.sequence.new" and not (phase == "confirm" and stored):
        return body
    label = _active_sequence_label(arguments, body)
    if label is None:
        return body
    key = _heading_workspace_key()
    previous = _LAST_STANDING_HEADING.get(key)
    opened = tool == "essay.sequence.new" and phase == "confirm" and stored
    after_confirm = tool == "essay.stage" and phase == "confirm" and stored
    if opened or after_confirm or previous != label:
        body["heading"] = label
        _LAST_STANDING_HEADING[key] = label
    return body


def front_office_stage9(essay_id: str) -> dict[str, object]:
    """Thin stop before the final Word. Read the submit-file pass. Do not mark again."""
    from essay_writer.specialists.eqr import submit_pass_unlocked

    report = submit_pass_unlocked(essay_id)
    unlocked = report.get("unlocked") is True
    return {
        "stopped": not unlocked,
        "remarked": False,
        "freeflow": False,
        "gap_fill": False,
        "eqr": report.get("eqr") or "missing",
        "reason": report.get("reason") or "",
    }


def front_office_call(name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Say one writer-door reply. The function is HANDLERS[name]."""
    from essay_writer.debug_log import note_call
    from essay_writer.server import HANDLERS

    handler = HANDLERS[name]
    try:
        result = handler(**arguments)
    except Exception as exc:
        note_call(name, arguments, error=exc)
        raise
    note_call(name, arguments, result=result)
    if isinstance(result, dict):
        spoken = speak(result)
        from essay_writer.build_status import reply_status, take_idle
        from essay_writer.student_progress import shape_student_reply

        mid_started = spoken.get("mid_started") is True
        lines = reply_status(name, arguments, spoken)
        essay_id = arguments.get("essay_id")
        if not isinstance(essay_id, str) or not essay_id.strip():
            found = spoken.get("essay_id")
            essay_id = found if isinstance(found, str) else ""
        if essay_id.strip():
            for line in take_idle(essay_id.strip()):
                if line not in lines:
                    lines.append(line)
        spoken = shape_student_reply(
            spoken,
            tool=name,
            mid_started=mid_started,
            status_lines=lines,
        )
        spoken.pop("mid_phases", None)
        spoken.pop("mid_started", None)
        if (
            spoken.get("ok") is not False
            and spoken.get("status")
            and not isinstance(spoken.get("next"), str)
        ):
            spoken["next"] = wait_next()
        return attach_standing_heading(_hide_reply(spoken), tool=name, arguments=arguments)
    return result
