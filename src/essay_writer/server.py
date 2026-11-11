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
from essay_writer.debug_log import essay_debug_export, essay_debug_wipe, traced
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
from essay_writer.prompt_loader import render_tokens, text
from essay_writer.review import REVIEW_INSTRUCTIONS
from essay_writer.revise import essay_revise
from essay_writer.seats import seat_reading
from essay_writer.setup import essay_setup, mid_office, setup_prompt
from essay_writer.shelf import essay_shelf_get, essay_shelf_put
from essay_writer.specialists.eqr import essay_review
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

INSTRUCTIONS = render_tokens(text("front_office/briefing.md", "server"))
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

# These sentences name the file-work host that is actually in use.
# Other "Grok Build" lines name the alternate product or the setup argument.
# A blanket replace would tell a Cursor briefing to pass mid_office_shell for
# Cursor, and would call Cursor the alternate host.
_ACTIVE_HOST_LINES = (
    "Grok Build does the file work and does not own the chat.",
    "Grok Build writes these files for either file-work host",
    "Grok Build does not own this chat.",
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
        for line in _ACTIVE_HOST_LINES:
            source = source.replace(line, line.replace("Grok Build", office))
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
    {
        "--install-upload",
        "--attach-mcp",
        "--copy-to-mac",
        "--remember-mac-dir",
        "--upload",
        "--dest",
        "--install-cursor",
        "--no-install-cursor",
        "--cursor-sha256",
        "--upload-sha256",
    }
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
            "--read-photo PATH | --install-upload ZIP [--upload-sha256 SHA256] [--no-reviewer] "
            "[--install-cursor] [--cursor-sha256 SHA256] | "
            "--attach-mcp [--no-reviewer] [--install-cursor] [--cursor-sha256 SHA256] | "
            "--copy-to-mac PATH | --remember-mac-dir FOLDER]"
        )
    build_server().run(transport="stdio")


def tool_names() -> list[str]:
    return [door["tool"] for door in DOORS]


def call_local(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """In-process call. Grok Bot and Cursor use this same handler map."""
    from essay_writer.shells import front_office_call

    return front_office_call(name, arguments)
