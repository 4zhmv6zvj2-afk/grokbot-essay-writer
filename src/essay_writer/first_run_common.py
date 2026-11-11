"""Shared primitives for the first-run modules.

Path discovery, prompt text, and the small path guards are shared by the
install, host-config, Mac-handoff, and CLI modules. Keeping them here means
those modules can depend on one another without a cycle.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

PipRunner = Callable[[list[str], Path], dict[str, Any]]
Enable = Callable[[str], dict[str, Any]]


def package_root() -> Path:
    """Repo root that contains pyproject.toml and src/essay_writer."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "essay_writer").is_dir():
            return parent
    return here.parents[2]


def prompt_path() -> Path:
    packaged = Path(__file__).resolve().parent / "FIRST-RUN.txt"
    if packaged.is_file():
        return packaged
    return package_root() / "FIRST-RUN.txt"


def first_run_prompt() -> str:
    """Prompt text that ships in this copy and inside the package."""
    return prompt_path().read_text(encoding="utf-8")


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _internal_volume(path: Path) -> bool:
    return any(part.casefold() == "researchdrive" for part in path.parts)


def _clone_url(value: str) -> bool:
    text = value.strip()
    folded = text.casefold()
    if folded.startswith(("http://", "https://", "git@", "ssh://", "git://")):
        return True
    return folded.endswith(".git") and "://" in folded


def _fail(reason: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "installed": False, "reason": reason}
    body.update(extra)
    return body
