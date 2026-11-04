"""Grok Build mid-office reads the same stage settings and photo helper as Cursor.

Cursor and Build both call essay_writer.stage_llm.stage_settings.
That row's rules and tracking_file are the stage guidance and the tracking path.
Cursor and Build both call essay_writer.vision.prepare_photo (photo_vision).
This module does not keep a second table.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from essay_writer.assignment_gate import assignment_requirements as _requirements
from essay_writer.pack_backup import essay_pack_restore as restore_pack  # noqa: F401
from essay_writer.paths import work_dir
from essay_writer.stage_llm import RULES_SOURCE, stage_settings
from essay_writer.vision import prepare_photo as photo_vision  # noqa: F401

SOURCE = RULES_SOURCE

# Ids the launch quotes. Ready quotes these.
RESIDUALS: dict[str, str] = {
    "context-flag": (
        "The per-stage context_window is applied on grok --rules via stage_launch "
        "(Context window N in the rules text). "
        "The grok CLI sets the model with --model and the reasoning effort with --effort. "
        "It has no separate context-window flag."
    ),
    "40b-install-root": (
        "Unpack and pip install -e . use /workspace/essay-writer-install when /workspace exists. "
        "GROK_HOME and ~/.grok are the grok config home, not an essay install folder."
    ),
    "40d-packing": (
        "Build handoff copies annotation.docx, download-list.docx, papers.zip, and critical-reviews.zip "
        "when those files are already in the sequence output. It does not write them. "
        "A missing file stays missing. "
        "An ad-hoc folder that is not a sequence still copies an existing .docx or .zip only."
    ),
    "40d-mac": (
        "When this computer is not the Mac, set ESSAY_WRITER_MAC_DIR to the mounted "
        "Documents/Essay Bot folder on the Mac, or use Documents/Essay Bot when that folder "
        "already exists on a visible Mac home. Per-sequence Word and zip copies land under "
        "Essay Bot/<module>/<essay_id>/; module-shared files use Essay Bot/<module>/shared/. "
        "Otherwise the copy returns mac-not-mounted and leaves the file in place."
    ),
    "40a-open-session": (
        "Build attach writes project .grok/config.toml and, when ~/.grok or GROK_HOME exists outside tests, the user config.toml, "
        "then runs grok mcp enable when the grok binary is on PATH so an open Grok session picks up essay-writer. "
        "A config write alone is not enough when enable does not run."
    ),
}


def _refuse_fast(item: dict[str, Any]) -> None:
    if item.get("fast") is not False:
        raise RuntimeError("stage settings have fast on")
    model = str(item.get("model", ""))
    if "fast" in model.casefold():
        raise RuntimeError("stage settings name a fast model")


def _rules(item: dict[str, Any]) -> str:
    tracking = item["tracking_file"] if item.get("tracking_file") else "none"
    following = item["next_stage"] if item.get("next_stage") else "none"
    pointer = item["pointer_file"] if item.get("pointer_file") else "none"
    return (
        f"Stage {item['stage']}. Model {item['model']}. "
        f"Reasoning {item['reasoning']}. Fast is off. "
        f"Context window {item['context_window']}. "
        f"Apply the stage guidance as rules:\n{item['rules']}\n"
        f"Tracking file: {tracking}. Pointer: {pointer}. Next stage: {following}. "
        "When a phase on the mid-status tip sheet finishes, print one line: mid-phase: <name>."
    )


def stage_launch(
    stage: str,
    *,
    reviews: list[dict[str, Any]] | None = None,
    reopens: list[dict[str, Any]] | None = None,
    budget: int | None = None,
) -> dict[str, Any]:
    """Grok command for one stage. Settings come from stage_settings.

    Cursor reads that same row through cursor_office.cursor_stage_launch.
    The rules on grok --rules are the Basics checklist walk, and for stages
    2, 3, 4a, 4b, and 5 the plan revisit. There is no second copy for Grok Build.
    """
    item = stage_settings(stage)
    _refuse_fast(item)
    command = [
        "grok",
        "--model",
        item["model"],
        "--effort",
        item["reasoning"],
        "--rules",
        _rules(item),
    ]
    launch = {
        "ok": True,
        "stage": stage,
        "source": SOURCE,
        "settings": item,
        "command": command,
        "context_residual_id": "context-flag",
        "context_residual": RESIDUALS["context-flag"],
    }
    if stage == "5":
        from essay_writer.context_fit import fit_critical_reviews

        window = item["context_window"] if budget is None else budget
        launch["context_fit"] = fit_critical_reviews(reviews, reopens=reopens, budget=window)
    from essay_writer.build_status import attach_launch_status

    attach_launch_status(launch, stage)
    return launch


def eqr_pass_unlock(essay_id: str) -> dict[str, Any]:
    """Submit-file pass. Cursor calls this same function."""
    from essay_writer.specialists.eqr import submit_pass_unlocked

    return submit_pass_unlocked(essay_id)


def top_band_mark(essay_id: str, text: str) -> dict[str, Any]:
    """Top-band table rows. Cursor calls this same function."""
    from essay_writer.specialists.eqr import mark_top_band_rows

    return mark_top_band_rows(essay_id, text)


def opened_word_gate(essay_id: str, text: str) -> dict[str, Any] | None:
    """Requirement list on the opened Word file. Cursor calls this same function."""
    from essay_writer.specialists.eqr import opened_word_gate as _gate

    return _gate(essay_id, text)


def rewrite_vs_opened_word(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Rewrite and EQR length pressure against the opened Word file.

    Cursor calls this same function. Build covered.
    """
    from essay_writer.rewrite_baseline import rewrite_vs_opened_word as _gate

    return _gate(*args, **kwargs)


def report_phase(essay_id: str, kind: str) -> list[str]:
    """Grok Build finished a real phase. Same tip sheet as Cursor CLI."""
    from essay_writer.build_status import signal_phase

    return signal_phase(essay_id, kind)


def spawn_grok(command: list[str]) -> dict[str, Any]:
    """Start the local Grok Build CLI. Stdout is kept so a phase line can be read.

    Remote commands are refused. Tests skip a local start. A failed start
    does not open a mid session; the caller arms only when started is true.
    stdin and stdout are a terminal, and stderr is a pipe (`open_mid_child`).
    A closed stdin is the same immediate-exit pattern as the Cursor CLI.
    """
    import os

    from essay_writer.cursor_office import remote_cloud_argv
    from essay_writer.mid_spawn import open_mid_child
    from essay_writer.setup import grokbuild_binary

    argv = [str(part) for part in command]
    if remote_cloud_argv(argv) or not argv or argv[0] != "grok":
        return {"started": False, "reason": "not-grok-build", "command": argv}
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return {"started": False, "reason": "skipped-under-test", "command": argv}
    binary = grokbuild_binary()
    if not binary:
        return {"started": False, "reason": "grok-cli-missing", "command": argv}
    try:
        proc, stream = open_mid_child([binary, *argv[1:]])
    except OSError:
        return {"started": False, "reason": "grok-cli-missing", "command": argv}
    return {
        "started": True,
        "reason": "",
        "pid": proc.pid,
        "command": argv,
        "stdout": stream,
        "proc": proc,
    }


def _mac_missing(result: dict[str, Any]) -> bool:
    if result.get("reason") == "mac-not-mounted":
        return True
    files = result.get("files")
    if isinstance(files, list):
        return any(isinstance(item, dict) and _mac_missing(item) for item in files)
    return False


_STAGE_DELIVERABLES = (
    "annotation.docx",
    "download-list.docx",
    "papers.zip",
    "critical-reviews.zip",
)


def essay_id_from_deliverable_path(source: Path) -> str | None:
    """Sequence id when source sits under Essay-writer/<module>/sequences/<n>."""
    try:
        parts = source.expanduser().resolve().parts
    except OSError:
        parts = source.expanduser().parts
    for index, part in enumerate(parts):
        if part != "sequences" or index < 1 or index + 1 >= len(parts):
            continue
        number = parts[index + 1]
        if number.isdigit() and int(number) >= 1:
            return f"{parts[index - 1]}-{int(number)}"
    return None


def write_stage_deliverables(essay_id: str) -> list[str]:
    """Write the 4a and 4b files from sources already stored. Nothing is invented."""
    from essay_writer.specialists.researcher import deliver_saved_sources

    if not deliver_saved_sources(essay_id):
        return []
    return list(_STAGE_DELIVERABLES)


def _stage_files(essay_id: str) -> list[Path]:
    """The four stage files already in output/. A missing name stays missing."""

    folder = work_dir(essay_id) / "output"
    return [folder / name for name in _STAGE_DELIVERABLES if (folder / name).is_file()]


def _copy_many(paths: list[Path], *, mac_dir: Path | None) -> dict[str, Any]:
    from essay_writer.first_run import copy_deliverable_to_mac

    copies = [dict(copy_deliverable_to_mac(path, mac_dir=mac_dir)) for path in paths]
    return {
        "ok": all(item.get("ok", False) for item in copies) if copies else True,
        "copied": any(item.get("copied") for item in copies),
        "files": copies,
        "source": str(paths[0].parent) if paths else "",
    }


def build_deliverable_handoff(source: Path, *, mac_dir: Path | None = None) -> dict[str, Any]:
    """Copy existing 4a/4b files for a sequence. Otherwise copy one docx or zip.

    A sequence path does not call write_stage_deliverables. annotation.docx,
    download-list.docx, papers.zip, and critical-reviews.zip are copied only
    when they are already in output/. A missing file stays missing.
    """
    from essay_writer.first_run import copy_deliverable_to_mac

    essay_id = essay_id_from_deliverable_path(source)
    if essay_id:
        staged = _stage_files(essay_id)
        result = _copy_many(staged, mac_dir=mac_dir)
        result["handoff"] = "stage-deliverables"
        result["essay_id"] = essay_id
        result["deliverables"] = [path.name for path in staged]
        from essay_writer.build_status import saved_pack_status

        result["status"] = saved_pack_status(essay_id)
        ids: list[str] = []
        notes: list[str] = []
        if _mac_missing(result):
            ids.append("40d-mac")
            notes.append(RESIDUALS["40d-mac"])
        result["residual_ids"] = ids
        extra = " ".join(notes)
        prior = result.get("residual")
        result["residual"] = f"{prior} {extra}".strip() if isinstance(prior, str) and prior else extra
        return result

    result = dict(copy_deliverable_to_mac(source, mac_dir=mac_dir))
    result["handoff"] = "copy_deliverable_to_mac"
    ids = ["40d-packing"]
    notes = [RESIDUALS["40d-packing"]]
    if _mac_missing(result):
        ids.append("40d-mac")
        notes.append(RESIDUALS["40d-mac"])
    result["residual_ids"] = ids
    extra = " ".join(notes)
    prior = result.get("residual")
    result["residual"] = f"{prior} {extra}".strip() if isinstance(prior, str) and prior else extra
    return result


def assignment_requirements(essay_id: str) -> dict[str, Any]:
    """Requirement list from the brief and mark scheme. Same record as the product doors."""

    return _requirements(essay_id)
