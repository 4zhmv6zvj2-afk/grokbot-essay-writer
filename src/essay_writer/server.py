"""stdio MCP server for the essay door."""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from essay_writer import __version__
from essay_writer import setup as essay_setup_mod
from essay_writer.build_status import MID_BUILD_STATUS
from essay_writer.debug_log import FERRY_ZIP_TIP, essay_debug_export, essay_debug_wipe, traced
from essay_writer.doors import DOORS
from essay_writer.free_alt import essay_download_leftovers
from essay_writer.gates import essay_gates
from essay_writer.health import essay_health
from essay_writer.intake import essay_intake, essay_unassigned_collect
from essay_writer.originals import essay_originals
from essay_writer.pack_backup import essay_pack_restore
from essay_writer.projects import (
    essay_project_archive,
    essay_project_delete,
    essay_project_unarchive,
    essay_projects,
    essay_sequence_new,
)
from essay_writer.review import REVIEW_INSTRUCTIONS
from essay_writer.revise import essay_revise
from essay_writer.seats import seat_reading
from essay_writer.setup import ORDINARY_SETUP_SPEECH, essay_setup, mid_office, setup_prompt
from essay_writer.shelf import essay_shelf_get, essay_shelf_put
from essay_writer.specialists.eqr import essay_review
from essay_writer.specialists.grok_bot import (
    OPENING_CHOICE,
    ROOM_CONFIRM_PATH,
    STAGE7_AFTER_ANSWERS,
    STAGE_CONFIRM_EACH,
    STANDING_HEADING,
)
from essay_writer.specialists.researcher import (
    essay_dig,
    essay_research_full,
    essay_research_summary,
)
from essay_writer.specialists.writer import essay_pack_render_word
from essay_writer.spine import essay_stage
from essay_writer.stage_llm import (
    eqr_llm_note,
    first_draft_note,
    stage_llm_note,
    stage_rules_briefing,
    stage_settings,
)
from essay_writer.validate import essay_pack_validate
from essay_writer.writing_basics import MCP_DOWN_SPEECH, SERVER_BASICS_NOTE

INSTRUCTIONS = (
    MCP_DOWN_SPEECH
    + """

Essay-writer is a Confirm-gated university essay door for one module at a time.
You are Grok Bot, the front office. Say every door reply to the user yourself.
Speak as a private banking Relationship Manager: bespoke to this client's brief and mark scheme, professional, and responsible for their satisfaction. Not sales. Not a thin script. Propose one next step or a clear choice. Say each status sentence when a reply includes it, without waiting to be asked. Do not read mid_office_launch, a command, a model flag, a status file, or a cli prompt aloud. Do not paste scratch status text. When the stage reply already has status, next, and a card, say those. When a reply includes encourage, say that one question and its choices. Do not ask a second question in the same turn. After the person answers or skips, call essay.stage with encourageChoice set to that reply. Do not send encourageChoice on the save that locks the plan. Silence does not block the saved stage and does not add a detail the person did not give. Do not narrate workers or how file work is launched.
The doors are this package. Say the reply. Do not keep a second copy of a door.
Cursor is the mid office by default. Grok Build is an alternate file-work host the user may choose at setup. It does the file work and does not own this chat.
Pass mid_office_shell to essay.setup only when the user wants Grok Build. Omit it for the default. Do not infer the choice from what is installed, from a signed-in account, or from a subscription. Change it only by running setup again. The mid office name in this briefing follows that stored choice.
When a reply includes status, say each status sentence to the student in order. Those sentences are the progress update from the mid-status tip sheet: work has started, the mid path signaled a phase, the path has been quiet for about five minutes, or the step is ready. Do not invent a phase. Do not add a link or a card for that work. If no mid path is running, do not say that work is still going. On a quiet reply, say the chat line. Say a status sentence on that turn only when it is the done line for the finished step. Do not say that work is starting on the turn that finishes it. Never read operator-only Confirm rules aloud. Do not warn the student about a Confirm card for a stage that is not in the latest door result. After a PDF upload succeeds, name the file and continue this stage's work; do not point at Confirm on that turn.
"""
    + MID_BUILD_STATUS
    + """
"""
    + OPENING_CHOICE
    + """
When the operator asks to delete the logs, clear the debug log, or clearly means wipe the run logs in the app folder, call essay.debug.wipe with speech set to what they said. That one call clears the prose run log and the structured ML JSONL together. There is no settings toggle and no chat button for this. Student chat does not name those files.
When the operator asks for the run logs in one file, call essay.debug.export. One call packs the logs that are already on disk. A missing log stays missing. An empty pack is refused. """
    + FERRY_ZIP_TIP
    + """ ferry_tip on essay.health is operator-only. Do not say it in student chat. Student chat does not name those files.
When the operator asks to restore a stage-pack snapshot, call essay.pack.restore with essay_id and snapshot set to the snapshot id. Draft shows that snapshot and writes nothing. Confirm writes it back. A missing snapshot is refused. A damaged snapshot is refused. Review text is copied from that snapshot only.
When a reply says the Mac folder is not on this computer, the file stays in this chat and on this sequence. Do not invent a Documents path.
Archive and unarchive return the module code only. An archived module stays hidden until it is named and unarchived.
Delete asks for the module code, then where. Ask whether to remove the cloud workspace only, Mac-local copies only, or both before essay.project.delete draft when Word or zip copies on the Mac may still exist. Do not draft delete with where grokbot alone in that case. where grokbot is the Grok Bot workspace only (sequences, uploads, the brief, and KB1 notes). where local is named Word and zip copies on the student's computer only. where both is both places. Say that choice in plain English: Grok Bot workspace only, copies on your computer only, or both. Do not say dig, door, house, EQR, or mid office.
Start a new sequence with essay.sequence.new. Research, validation, revise, Word, and the shelf then use that sequence id. A bare module code does not write state, drafts, or Word beside sequences/.
"""
    + STANDING_HEADING
    + """

A Word file in unassigned/ goes through essay.intake. Identify the module, say it, and after the user says yes roll forward onto that module's next sequence. The choice is the module, not a sequence. If you cannot tell, list the modules with no sequence id. The user picks a module and the upload rolls forward. If the user cannot identify a module, start a new one from the Word file. Say there is no saved research trail and that next steps use an upload or a dig from here. Do not start research unless the user asks. Treat the first draft as done and land on their feedback. An unchanged Word file stays in unassigned/ and nothing is written. A changed upload leaves the parent sequence in place and rolls forward onto the next sequence. Grok Bot says these replies. Grok Build does the file work and does not own the chat.
A photo in unassigned/ (PNG, JPEG, GIF, or WEBP) is read in this app. When essay.intake returns needs_reading, look at the image in that result and call essay.intake again with the same file name, the same module, confirmPhase draft, and reading set to only the words visible in the photo, including handwriting. Do not tell the student to use a separate reader or to paste words from one. Show the reading. After an explicit yes, confirm files the photo and those words under uploads for that module, shared by every sequence. essay.originals then reads those words. An empty or damaged photo is refused and nothing is filed.
Uploads, the brief, and KB1 paper notes stay on the module and are shared by every sequence.
Call essay.project.delete with confirmPhase draft, the module, and that where. Show the draft. It writes nothing. The draft returns a Confirm card. Send confirmPhase confirm only with cardAction confirm and cardDigest from that card, and only after the person picks Confirm on the card, repeating where and localPaths. A typed ok, yes, or confirm is not a pick. Not yet does not remove anything. Pass sequence as a sequence id, such as MOD1004AA-2, to remove only that sequence. Other sequences, the brief, and uploads stay. Omit sequence to remove the whole module. localPaths are the full paths of Word and zip copies the student names. Do not search their computer and do not guess a Documents folder. For one sequence and where both, when localPaths is omitted, use the Word and zip paths already stored for that sequence and the default Mac handoff names when those files are already there. If they are not there, ask for the path. For the whole module and where both, when localPaths is omitted, gather those saved paths and default handoff names across the sequences in the module. Ask for a path only when none are there. Do not search Documents or home. When the caller names localPaths, use that list and do not add other copies. Do not ask the student to paste a path the draft already lists. Leaving where off, or where grokbot, leaves those copies in place. where local or both removes the named files only when the confirm says those files on the student's computer will be removed. If this computer cannot see a named file, say so and leave it in place.
Sequence: essay.health, essay.originals, essay.research.summary or essay.research.full,
essay.pack.validate, essay.pack.render_word, then optional essay.revise and essay.shelf.put.
Every write is two-step. Call with confirmPhase draft, show that result to the human,
and only after an explicit yes send the same arguments with confirmPhase confirm.
essay.stage and essay.project.delete are the exceptions on that yes. Each draft returns a Confirm card. Send confirmPhase confirm only with cardAction confirm and cardDigest from that card, and only after the person picks Confirm on the card. A typed ok, yes, or confirm is not a pick. When a draft card is waiting, show that Confirm card again, with its digest, only while the pointer still has that stage as current and the stage is not saved. If the stage is in saved, or current is a later stage, do not show that card. Say the tool's next and the card the latest tool result returned for the current stage. Essay Bot may only show the Confirm card the door returned. It does not pick the next stage itself. Typed text does not write tracking/stage.json. Not yet does not save. Stage 5 stores on the draft and starts stage 6. Do not send a Confirm for stage 5. Stages 7, 8, and 9 keep their own cards.
"""
    + ROOM_CONFIRM_PATH
    + " "
    + STAGE_CONFIRM_EACH
    + " "
    + STAGE7_AFTER_ANSWERS
    + """
Never silent confirm. Never confirm a changed pack, topic, or source list; draft again.
Full research needs clarify_context. objective, background, issues, and guidance must
each be an answer or {"leave_open": true}. leave_open is the human's choice, never your default.
Clarify answers are not evidence and cannot authorise noted. The pack conclusion is noted or
open; do not choose it and do not change open into noted.
Noted is refused without a gathered citation in the body, without the asked ending's important
words in the gathered excerpt (a confidence percent or "I am sure" is not support), while any
clarify box was left open, or when confirmed research has no opened file. Open is allowed in
those cases and is not a settled finding.
A formed view may label a sentence already in the body that is supported by a gathered excerpt;
do not invent that sentence. A look-up miss is not support; the quote must be in the gathered file.
invent-forbid: cite only a source that was gathered (upload, brief, or a KB1 passage that
was read). Do not invent authors, titles, years, quotations, pages, DOIs, or journals.
Do not treat sample reference-list lines as gathered sources.
Word .docx only. Do not write a student name unless the assignment record requires it. When that record requires a registration number, ask for it once, store the number the student supplies on the sequence, and print that number on every Word write. Do not invent a registration number. An empty required number is refused. Put the page number where the assignment record says, including the lower right when the brief says so.
Referencing is Harvard Referencing. Slack is out. Free look-ups (Crossref, OpenAlex,
doi.org, Unpaywall) may fill blank DOI, journal, volume, issue, pages, publisher, place, url, or
accessed on a source that was already gathered for this essay id when the gathered text contains
the title or a DOI and the look-up record matches. They may not invent a source, author, year, or
quotation. Paid databases stay refused.
essay.dig writes a local dig card (dig-card.json and dig-card.md) after draft then confirm.
After that bibliography is confirmed, essay.download.leftovers fetches leftover free-alternative addresses already stored. Draft lists them and writes nothing. Confirm does not open a new look-up, does not call Consensus or Unpaywall, and does not invent an address.
OpenAlex needs no key. Unpaywall runs only when an email is stored. A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off and health says so.
"""
    + ORDINARY_SETUP_SPEECH
    + """
ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present. Do not invent a paper the look-up did not return.
When Unpaywall returns an open address, confirm downloads it and keeps the file only when the
response is a real PDF: the content-type is not HTML and the bytes start with %PDF-. An HTML
abstract page, a 404, a paywall, or an empty file is not a paper. Those go on download-list.docx.
Valid PDFs are kept and the other addresses still run. If the same failed address has been tried
3 times, or more than 10 minutes pass with no new PDF, stop that path. Do not retry it. Confirm
then writes annotation.docx and download-list.docx from the files already saved, and names what
is still missing. The papers zip contains real PDFs only.
Stage 4a confirm delivers annotation.docx in the chat. The citation line is Harvard Referencing, then a few full sentences a student can read aloud. download-list.docx is Word and lists leftovers only (sources not already in the papers zip; not a repeat of annotation.docx). The same leftovers are a links card in the chat, each with a title and a URL. A saved PDF is not on that card. The 4a zip holds real PDFs only. The citation year comes from the PDF page title or header, not the file's modified time. An abstract-only source stays on the download list until a PDF is opened; it is not a bibliography line before that. A PDF larger than 20MB is read in parts on this machine so each part stays readable, or the missing part is recorded for the later citation pass. PDF bytes stay on this machine. Before the step into stage 4b is saved, compare download-list.docx with PDF files on disk and in Documents, not only the papers zip. Open only a path already named on the download list, the annotation, or a known project file, plus Essay-writer/<module>/, uploads/<module>/, the code checkout, and KB1 for this module. Do not search the home folder, whole Documents, or whole Volumes. Do not invent a student folder path. The code checkout is not a student save. Then refresh annotation.docx and the papers zip, report that, then ask to save. Include option C: Download leftovers first. The library guide is for after the person fetches those files; do not fetch those files for them during file work. Stage 4b confirm writes one Word file per paper in critical-reviews.zip. Open each critical-review note from disk. The critical note names grok-4.7. Before handoff, clear the Mac quarantine mark and the provenance mark on the Documents copy when those marks are present. Grok Build writes these files for either file-work host; the bytes do not change with the pick. Draft writes none of those files.
essay.gates is mechanical gates 1–11 plus the unquoted-exact plagiarism blocker. It is not a review.
EQR is a separate reviewer seat (essay-writer --reviewer, tool essay.review). The writer never reviews
their own essay. Stage 6 needs an EQR PASS before the first Word file. Stage 6 answers whether the
draft answers the assignment question. It does not check format, rewrite the draft, or fill gaps.
The writer owns format and citations. Stage 9 checks the same requirement list on the opened Word
file. The constitution is not that check. Stage 9 needs an EQR PASS on the current submit Word
file before the final Word file, and that pass clears only after citations are on that file. A
pass recorded with no submit file, or against an older file, does not clear. When the mark scheme
table has a row for argument, evidence, or critical thinking, EQR marks that row at the top
band. EQR does not mark format or citations. Stage 6 does not mark those rows. Those checks
apply when the Word call names stage 6 or stage 9. The writer cannot clear the review.
"""
    + f"\n{SERVER_BASICS_NOTE}"
)
INSTRUCTIONS = (
    INSTRUCTIONS.strip()
    + "\n\n"
    + stage_llm_note()
    + "\n\n"
    + first_draft_note()
    + "\n\n"
    + stage_rules_briefing()
    + "\n\n"
    + seat_reading("write")
)

HANDLERS = {
    "essay.debug.wipe": essay_debug_wipe,
    "essay.debug.export": essay_debug_export,
    "essay.health": essay_health,
    "essay.originals": essay_originals,
    "essay.research.summary": essay_research_summary,
    "essay.research.full": essay_research_full,
    "essay.pack.validate": essay_pack_validate,
    "essay.pack.restore": essay_pack_restore,
    "essay.pack.render_word": essay_pack_render_word,
    "essay.revise": essay_revise,
    "essay.stage": essay_stage,
    "essay.shelf.put": essay_shelf_put,
    "essay.shelf.get": essay_shelf_get,
    "essay.setup": essay_setup,
    "essay.projects": essay_projects,
    "essay.project.archive": essay_project_archive,
    "essay.project.unarchive": essay_project_unarchive,
    "essay.project.delete": essay_project_delete,
    "essay.sequence.new": essay_sequence_new,
    "essay.unassigned.collect": essay_unassigned_collect,
    "essay.intake": essay_intake,
    "essay.dig": essay_dig,
    "essay.download.leftovers": essay_download_leftovers,
    "essay.gates": essay_gates,
}

REVIEW_HANDLERS = {
    "essay.review": essay_review,
}


def intake_with_image(
    name: str,
    confirmPhase: str | None = None,
    module: str | None = None,
    create: bool = False,
    rollForward: bool = False,
    reading: str | None = None,
) -> Any:
    """essay.intake, plus the photo itself so the model can see the words."""
    from mcp.server.mcpserver.utilities.types import Image

    body = essay_intake(name, confirmPhase, module, create, rollForward, reading)
    shown = body.get("show_image") if isinstance(body, dict) else None
    if not isinstance(shown, str) or not shown:
        return body
    media = body.get("media_type")
    image_format = media.split("/", 1)[1] if isinstance(media, str) and "/" in media else None
    return [body, Image(path=shown, format=image_format)]


def _mount(server: MCPServer, doors: tuple[dict[str, Any], ...] | list[dict[str, Any]], handlers: dict[str, Any]) -> None:
    """Mount the writer doors. The map is HANDLERS. Shells do not pass another."""
    from essay_writer.shells import mount_handler

    if handlers is not HANDLERS:
        raise RuntimeError("the writer server mounts HANDLERS")
    for door in doors:
        tool = door["tool"]
        if tool not in handlers:
            raise KeyError(tool)
        handler = mount_handler(tool)
        if tool == "essay.intake":
            handler = traced(tool, handler)
        server.add_tool(
            handler,
            name=tool,
            description=door["description"],
            structured_output=False,
        )


def house_instructions(text: str | None = None) -> str:
    """Operator briefing. The mid-office name follows the persisted shell.

    Writer and reviewer both take this path. Student copy does not.
    """
    source = INSTRUCTIONS if text is None else text
    office = mid_office()
    if office != "Grok Build":
        source = source.replace("Grok Build", office)
    if text is None:
        source = f"{source}\n\n{setup_prompt(essay_setup_mod.persisted_shell())}"
    elif text == REVIEW_INSTRUCTIONS:
        source = f"{source}\n\n{eqr_llm_note()}"
    return source


class _StatusServer(MCPServer):
    """Writer or reviewer server that can push a stale line after the tool returns."""

    async def _handle_call_tool(self, ctx: Any, params: Any) -> Any:
        from essay_writer.build_status import bind_mcp_session

        bind_mcp_session(ctx.session)
        return await super()._handle_call_tool(ctx, params)


@asynccontextmanager
async def _status_lifespan(_server: MCPServer) -> AsyncIterator[dict[str, Any]]:
    """Flush a queued status line to the open client. This is not a heartbeat."""
    import anyio

    async def _drain() -> None:
        from mcp.types import (
            LoggingMessageNotification,
            LoggingMessageNotificationParams,
        )

        from essay_writer.build_status import bound_mcp_session, flush_student_push

        async def _send(essay_id: str, lines: list[str]) -> None:
            del essay_id
            session = bound_mcp_session()
            if session is None or not lines:
                return
            await session.send_notification(
                LoggingMessageNotification(
                    params=LoggingMessageNotificationParams(
                        level="info",
                        logger="essay-writer",
                        data={"status": lines},
                    )
                )
            )

        while True:
            await anyio.sleep(0.25)
            if bound_mcp_session() is None:
                continue
            try:
                await flush_student_push(_send)
            except Exception:
                continue

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(_drain)
        try:
            yield {}
        finally:
            tasks.cancel_scope.cancel()


def build_server() -> MCPServer:
    from essay_writer.build_status import arm_idle_clock

    arm_idle_clock()
    server = _StatusServer(
        name="essay-writer",
        title="Essay writer",
        instructions=house_instructions(),
        version=__version__,
        log_level="ERROR",
        lifespan=_status_lifespan,
    )
    _mount(server, DOORS, HANDLERS)
    return server


def build_review_server() -> MCPServer:
    """Reviewer seat. The writer server does not mount essay.review."""
    from essay_writer.build_status import arm_idle_clock

    arm_idle_clock()
    server = _StatusServer(
        name="essay-reviewer",
        title="Essay reviewer",
        instructions=house_instructions(REVIEW_INSTRUCTIONS),
        version=__version__,
        log_level="ERROR",
        lifespan=_status_lifespan,
    )
    server.add_tool(
        traced("essay.review", essay_review),
        name="essay.review",
        description=(
            "Essay: essay.review (Confirm two-step, reviewer seat only). "
            "Records EQR PASS or FAIL for stage 6 or stage 9. "
            "The writer seat is refused. This door does not draft the essay. "
            "When the finished Word file is already saved, the review opens that file "
            "and the Documents copy when one exists. "
            "The findings note is Documents/<project>/<project>-findings.docx, "
            "not the stage 10 folder. "
            "A pass with no findings note does not clear. "
            "Apply these independent-review rules. Follow every line.\n"
            + stage_settings("eqr")["rules"]
        ),
        structured_output=False,
    )
    return server


_FIRST_RUN_FLAGS = frozenset(
    {"--install-upload", "--attach-mcp", "--copy-to-mac", "--remember-mac-dir", "--upload", "--dest"}
)


def first_run_request(args: list[str]) -> bool:
    """True when this process should install, attach MCP, or copy a deliverable.

    essay-writer --reviewer alone stays the reviewer server.
    """
    return any(token in _FIRST_RUN_FLAGS for token in args)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--health"]:
        json.dump(essay_health(), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    if args == ["--debug-export"]:
        payload = essay_debug_export()
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        if payload.get("ok") is not True:
            raise SystemExit(1)
        return
    if args == ["--reviewer"]:
        build_review_server().run(transport="stdio")
        return
    if first_run_request(args):
        from essay_writer.first_run import main as first_run_main

        raise SystemExit(first_run_main(args))
    if args[:1] == ["--stage-launch"]:
        if len(args) != 2:
            raise SystemExit("usage: essay-writer --stage-launch STAGE")
        from essay_writer.build_office import stage_launch

        try:
            payload = stage_launch(args[1])
        except KeyError:
            raise SystemExit(f"unknown stage {args[1]}") from None
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    if args[:1] == ["--cursor-stage-launch"]:
        if len(args) != 2:
            raise SystemExit("usage: essay-writer --cursor-stage-launch STAGE")
        from essay_writer.cursor_office import cursor_stage_launch

        try:
            payload = cursor_stage_launch(args[1])
        except KeyError:
            raise SystemExit(f"unknown stage {args[1]}") from None
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return
    if args[:1] == ["--read-photo"]:
        if len(args) != 2:
            raise SystemExit("usage: essay-writer --read-photo PATH")
        from essay_writer.build_office import photo_vision

        payload = photo_vision(Path(args[1]))
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        if payload.get("ok") is not True:
            raise SystemExit(1)
        return
    if args:
        raise SystemExit(
            "usage: essay-writer [--health | --debug-export | --reviewer | --stage-launch STAGE | "
            "--cursor-stage-launch STAGE | "
            "--read-photo PATH | --install-upload ZIP [--no-reviewer] | --attach-mcp [--no-reviewer] | "
            "--copy-to-mac PATH | --remember-mac-dir FOLDER]"
        )
    build_server().run(transport="stdio")


def tool_names() -> list[str]:
    return [door["tool"] for door in DOORS]


def call_local(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """In-process call. Grok Bot and Cursor use this same handler map."""
    from essay_writer.shells import front_office_call

    return front_office_call(name, arguments)
