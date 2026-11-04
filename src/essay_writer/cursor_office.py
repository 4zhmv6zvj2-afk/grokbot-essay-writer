"""Cursor mid-office launch. The same stage_settings row as Grok Build.

stage_launch puts model and effort on grok --model and grok --effort.
This module puts model and effort on the agent CLI. The agent command
is agent --model grok-4.7-<reasoning> when fast is off.

Stage 4a research starts that Cursor CLI on this computer. Only the
local agent program is started. Remote agents and cloud agents are
refused. The front office says the door reply and the status sentences.
It does not run essay.dig, and it does not start a shell, as the 4a
research runner. essay.dig stays the one look-up on
essay_writer.server.HANDLERS.

cursor-context-flag remains. agent --help has no --context flag and no
--context-window flag. The bracket example is for a parameterized model
such as claude-opus-4-8[context=1m,effort=high]. agent --list-models
lists grok-4.7 as separate ids, and grok-4.7-<reasoning>[context=N] is
rejected (Cannot use this model). The per-stage context_window stays in
stage_settings. It is not an argument on the agent command, and it is
not written into prompt text to stand in for a flag.
"""

from __future__ import annotations

import os
from typing import Any

from essay_writer.assignment_gate import assignment_requirements as _requirements
from essay_writer.pack_backup import essay_pack_restore as restore_pack  # noqa: F401
from essay_writer.stage_llm import RULES_SOURCE, stage_settings

SOURCE = RULES_SOURCE
MODEL_FLAG = "--model"
EFFORTS = ("low", "medium", "high", "xhigh")

# Id the launch quotes. Ready quotes this.
RESIDUALS: dict[str, str] = {
    "cursor-context-flag": (
        "The agent CLI applies the stage model and the reasoning effort on --model. "
        "Fast off uses the id grok-4.7-<reasoning>. Fast on would be grok-4.7-<reasoning>-fast. "
        "agent --help has no --context flag and no --context-window flag. "
        "The bracket example on --help is for a parameterized model, such as claude-opus-4-8[context=1m,effort=high]. "
        "agent --list-models lists grok-4.7 as separate ids. "
        "grok-4.7-<reasoning>[context=N] is rejected: Cannot use this model. "
        "The per-stage context_window stays in stage_settings. "
        "It is not an argument on the agent command, and it is not written into prompt text to stand in for a flag."
    ),
}


def _refuse_fast(item: dict[str, Any]) -> None:
    if item.get("fast") is not False:
        raise RuntimeError("stage settings have fast on")
    model = str(item.get("model", ""))
    if "fast" in model.casefold():
        raise RuntimeError("stage settings name a fast model")


def cursor_model_id(item: dict[str, Any]) -> str:
    """Model id the agent CLI lists. Effort is the suffix. Fast off omits -fast."""
    _refuse_fast(item)
    model = str(item.get("model", ""))
    reasoning = str(item.get("reasoning", ""))
    if reasoning not in EFFORTS:
        raise RuntimeError("stage settings reasoning is not an agent model id")
    tail = model.split("-")[-1]
    if tail in EFFORTS or model.casefold().endswith("-fast"):
        raise RuntimeError("stage settings model already names effort or fast")
    return f"{model}-{reasoning}"


def cursor_stage_launch(
    stage: str,
    *,
    reviews: list[dict[str, Any]] | None = None,
    reopens: list[dict[str, Any]] | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    """Agent command for one stage. Settings come from stage_settings.

    The only model flag is --model. Its value is grok-4.7-<reasoning>
    when fast is off. Context is not a flag and is not added to the prompt.
    """
    item = stage_settings(stage)
    command = ["agent", MODEL_FLAG, cursor_model_id(item)]
    launch = {
        "ok": True,
        "stage": stage,
        "shell": "cursor",
        "source": SOURCE,
        "settings": item,
        "command": command,
        "model_flag": MODEL_FLAG,
        "context_residual_id": "cursor-context-flag",
        "context_residual": RESIDUALS["cursor-context-flag"],
    }
    if stage == "5":
        from essay_writer.context_fit import fit_critical_reviews

        window = item["context_window"] if budget is None else budget
        launch["context_fit"] = fit_critical_reviews(reviews, reopens=reopens, budget=window)
    from essay_writer.build_status import attach_launch_status

    attach_launch_status(launch, stage)
    return launch


REMOTE_CLOUD_BANNED = "remote-cloud-banned"
_REMOTE_FLAGS = frozenset(
    {
        "--cloud",
        "--remote",
        "--cloud-agent",
        "--remote-agent",
    }
)


def remote_cloud_argv(command: list[str]) -> bool:
    """True when this argv would start a remote or cloud agent."""
    blob = " ".join(str(part) for part in command).casefold()
    if "cursor.com/agents" in blob or "://" in blob:
        return True
    if any(token in blob for token in ("cloud-agent", "cloud_agent", "cloudagent", "remote-agent", "remote_agent")):
        return True
    for part in command:
        flag = str(part).casefold()
        if flag in _REMOTE_FLAGS or flag.startswith("--cloud=") or flag.startswith("--remote="):
            return True
    return False


def _local_agent_argv(command: list[str]) -> bool:
    return bool(command) and command[0] == "agent" and not remote_cloud_argv(command)


def spawn_agent(command: list[str]) -> dict[str, Any]:
    """Start the local Cursor CLI from an argv list.

    The list is the cursor_stage_launch command. argv is passed as a
    list. Remote and cloud agents are refused. Tests skip a local start.
    stdin and stdout are a terminal, and stderr is a pipe (`open_mid_child`).
    A closed stdin makes this CLI exit 1 in the same second.
    """
    argv = [str(part) for part in command]
    if remote_cloud_argv(argv):
        return {"started": False, "reason": REMOTE_CLOUD_BANNED, "command": argv}
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"started": False, "reason": "skipped-under-test", "command": argv}
    if not _local_agent_argv(argv):
        return {"started": False, "reason": "not-cursor-cli", "command": argv}
    from essay_writer.setup import cursor_cli_binary

    binary = cursor_cli_binary()
    if not binary:
        return {"started": False, "reason": "agent-cli-missing", "command": argv}
    from essay_writer.mid_spawn import open_mid_child

    try:
        proc, stream = open_mid_child([binary, *argv[1:]])
    except OSError:
        return {"started": False, "reason": "agent-cli-missing", "command": argv}
    return {
        "started": True,
        "reason": "",
        "pid": proc.pid,
        "command": argv,
        "stdout": stream,
        "proc": proc,
    }


def start_4a_research(
    essay_id: str,
    launch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stage 4a research runner. Starts the local Cursor CLI.

    The command comes from the launch. A Cursor command stays the local
    agent CLI. A Grok Build command stays grok. A remote or cloud command
    is replaced with the local command for the stored shell and is not
    started. Status is the shared tip sheet: a start line only when this
    process starts, a mid tip when it prints a phase, and one calm
    still-working line if it stays silent for about five minutes.
    No watch card.
    """
    return start_stage_mid(essay_id, "4a", launch=launch)


def report_phase(essay_id: str, kind: str) -> list[str]:
    """Cursor CLI finished a real phase. Same tip sheet as Grok Build."""
    from essay_writer.build_status import signal_phase

    return signal_phase(essay_id, kind)


_MID_ACTIVITY = {
    "4a": "gathering",
    "4b": "notes",
    "5": "drafting",
    "6": "work",
    "7": "work",
    "8": "work",
    "9": "work",
    "10": "work",
}


def _resolved_launch(
    stage: str,
    launch: dict[str, Any] | None,
) -> tuple[list[str], Any, str]:
    """Local command for this stage. Grok stays grok. Cursor stays agent."""
    host = launch if isinstance(launch, dict) and isinstance(launch.get("command"), list) else None
    if host is None:
        host = stage_host_launch(stage)
    command = [str(part) for part in host["command"]]
    settings = host.get("settings")
    if command and command[0] == "grok" and not remote_cloud_argv(command):
        return command, settings, "grok"
    if _local_agent_argv(command):
        return command, settings, "cursor"
    local = stage_host_launch(stage)
    local_command = [str(part) for part in local["command"]]
    shell = "grok" if local_command and local_command[0] == "grok" else "cursor"
    return local_command, local.get("settings"), shell


def start_stage_mid(
    essay_id: str,
    stage: str,
    launch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Start the mid-office job for one stage. Arm only when the process starts.

    Cursor CLI and Grok Build each keep their own command. Stdout is read
    for mid-phase lines. A failed start does not open a session.
    """
    from essay_writer.build_status import (
        HEARTBEAT_SECONDS,
        begin_mid_build,
        bind_job,
        follow_mid_process,
        live_mid_job,
    )

    activity = _MID_ACTIVITY.get(stage)
    if activity is None:
        return {
            "ok": True,
            "stage": stage,
            "runner": "",
            "command": [],
            "settings": None,
            "started": False,
            "reason": "no-mid-stage",
            "status": [],
            "heartbeat_seconds": HEARTBEAT_SECONDS,
            "shell": "",
        }
    command, settings, shell = _resolved_launch(stage, launch)
    live = live_mid_job(essay_id)
    if live is not None:
        return {
            "ok": True,
            "stage": stage,
            "runner": "",
            "command": command,
            "settings": settings,
            "started": False,
            "reason": "mid-office-live",
            "status": [],
            "heartbeat_seconds": HEARTBEAT_SECONDS,
            "shell": str(live.get("shell") or ""),
            "live": True,
        }
    if shell == "grok":
        from essay_writer.build_office import report_phase as grok_report
        from essay_writer.build_office import spawn_grok

        spawned = spawn_grok(command)
        report = grok_report
        runner = "grok-build"
    else:
        spawned = spawn_agent(command)
        report = report_phase
        runner = "cursor-cli"
    status: list[str] = []
    if spawned.get("started"):
        status = begin_mid_build(essay_id, activity)
        bind_job(essay_id, pid=spawned.get("pid"), stage=stage, shell=shell)
        office = "Build" if shell == "grok" else "Cursor" if shell == "cursor" else ""
        if office:
            from essay_writer.debug_log import note_mid_office

            note_mid_office("start", essay_id, office, stage=stage)
        stream = spawned.get("stdout")
        if stream is not None:
            follow_mid_process(
                essay_id,
                stream,
                report=report,
                proc=spawned.get("proc"),
                shell=shell,
            )
    elif spawned.get("reason"):
        from essay_writer.build_status import spawn_exit_status

        status = spawn_exit_status(essay_id, str(spawned.get("reason") or ""))
    return {
        "ok": True,
        "stage": stage,
        "runner": runner,
        "command": command,
        "settings": settings,
        "started": bool(spawned.get("started")),
        "reason": spawned.get("reason", ""),
        "status": status,
        "heartbeat_seconds": HEARTBEAT_SECONDS,
        "shell": shell,
    }


def eqr_pass_unlock(essay_id: str) -> dict[str, Any]:
    """Submit-file pass. Grok Build calls this same function."""
    from essay_writer.specialists.eqr import submit_pass_unlocked

    return submit_pass_unlocked(essay_id)


def top_band_mark(essay_id: str, text: str) -> dict[str, Any]:
    """Top-band table rows. Grok Build calls this same function."""
    from essay_writer.specialists.eqr import mark_top_band_rows

    return mark_top_band_rows(essay_id, text)


def opened_word_gate(essay_id: str, text: str) -> dict[str, Any] | None:
    """Requirement list on the opened Word file. Grok Build calls this same function."""
    from essay_writer.specialists.eqr import opened_word_gate as _gate

    return _gate(essay_id, text)


def rewrite_vs_opened_word(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Rewrite and EQR length pressure against the opened Word file.

    Grok Build calls this same function. Build covered.
    """
    from essay_writer.rewrite_baseline import rewrite_vs_opened_word as _gate

    return _gate(*args, **kwargs)


def stage_host_launch(
    stage: str,
    *,
    reviews: list[dict[str, Any]] | None = None,
    reopens: list[dict[str, Any]] | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    """Launch for the stored mid-office. Cursor and Grok Build share stage_settings."""
    from essay_writer.setup import SHELL_CURSOR, persisted_shell

    if persisted_shell() == SHELL_CURSOR:
        return cursor_stage_launch(stage, reviews=reviews, reopens=reopens, budget=budget)
    from essay_writer.build_office import stage_launch

    return stage_launch(stage, reviews=reviews, reopens=reopens, budget=budget)


def assignment_requirements(essay_id: str) -> dict[str, Any]:
    """Requirement list from the brief and mark scheme. Same record as the product doors."""

    return _requirements(essay_id)
