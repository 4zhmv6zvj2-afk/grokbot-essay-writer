"""Known paths for the research stages.

Mid-office Cursor opens a research file only when that path is already
allowed. The repo checkout is code. It is not a student save. Research
does not search home, whole Documents, or whole Volumes, and it does not
invent a student folder.
"""

from __future__ import annotations

import json
from pathlib import Path

from essay_writer.paths import (
    essay_dir,
    kb1_module_dir,
    kb1_root,
    module_code,
    uploads_dir,
    work_dir,
    workspace_root,
)

RESEARCH_STAGES = ("4a", "4b")

KNOWN_PATHS_LINE = (
    "Research file work on this computer opens only a path already allowed for this sequence. "
    "Allowed: the code checkout, and that checkout is code only, not a student save; "
    "Essay-writer/<module>/ workflow files; "
    "uploads/<module>/ when that is the product path; "
    "a path already named on the download list, the annotation, or a known project file for this sequence; "
    "local subject notes for this module when the module needs it. "
    "Do not search the home folder, whole Documents, or whole Volumes for papers. "
    "Do not invent a student folder path. "
    "Do not save student work in the code checkout."
)

_PATH_KEYS = frozenset({"path", "locator", "file"})


def repo_root() -> Path:
    """The code checkout. Not a student save location."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "essay_writer").is_dir():
            return parent
    return here.parents[2]


def is_roam_root(path: Path) -> bool:
    """True for home, whole Documents, a volume, or the Volumes folder.

    A file inside those trees is not a roam root. Searching the tree is.
    """
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = Path(path.expanduser())
    home = Path.home().resolve()
    if resolved == home or resolved == (home / "Documents").resolve():
        return True
    if resolved == Path("/Volumes").resolve() or resolved == Path("/").resolve():
        return True
    parts = resolved.parts
    return len(parts) == 3 and parts[1] == "Volumes"


def _resolve(raw: str) -> Path | None:
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    try:
        path = Path(text).expanduser()
    except OSError:
        return None
    if not path.is_absolute():
        path = workspace_root() / path
    try:
        return path.resolve()
    except OSError:
        return path


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _collect_paths(value: object, found: set[Path]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _PATH_KEYS and isinstance(item, str):
                resolved = _resolve(item)
                if resolved is not None:
                    found.add(resolved)
            elif isinstance(item, (dict, list)):
                _collect_paths(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_paths(item, found)


def known_recorded_paths(essay_id: str) -> set[Path]:
    """Paths already stored for this sequence. Does not search the disk."""
    found: set[Path] = set()
    folder = work_dir(essay_id)
    _collect_paths(_read_json(folder / "download-run.json"), found)
    _collect_paths(_read_json(folder / "state.json"), found)
    output = folder / "output"
    for name in ("annotation.docx", "download-list.docx", "papers.zip", "critical-reviews.zip"):
        found.add((output / name).resolve())
    return found


def _product_kind(essay_id: str, path: Path) -> str | None:
    module = module_code(essay_id)
    checks = (
        (kb1_module_dir(essay_id), "kb1"),
        (kb1_root() / "Essay-writer" / module, "kb1"),
        (essay_dir(essay_id) / "kb1", "kb1"),
        (uploads_dir(essay_id), "uploads"),
        (essay_dir(essay_id), "workflow"),
    )
    for root, kind in checks:
        if _is_under(path, root):
            return kind
    return None


def allow_research_path(essay_id: str, raw: object, *, save: bool = False) -> dict[str, object]:
    """Decide one research path. This does not look for other files."""
    if not isinstance(raw, str) or not raw.strip():
        return {"allowed": False, "kind": "missing", "reason": "No path was named.", "path": ""}
    path = _resolve(raw)
    if path is None:
        return {"allowed": False, "kind": "missing", "reason": "No path was named.", "path": ""}
    if is_roam_root(path):
        return {
            "allowed": False,
            "kind": "roam",
            "reason": "Do not search the home folder, whole Documents, or whole Volumes.",
            "path": path.as_posix(),
        }
    kind = _product_kind(essay_id, path)
    if kind:
        return {"allowed": True, "kind": kind, "reason": "", "path": path.as_posix()}
    if path in known_recorded_paths(essay_id):
        return {"allowed": True, "kind": "listed", "reason": "", "path": path.as_posix()}
    if _is_under(path, repo_root()):
        if save:
            return {
                "allowed": False,
                "kind": "repo-not-save",
                "reason": "The code checkout is not a student save.",
                "path": path.as_posix(),
            }
        return {"allowed": True, "kind": "repo", "reason": "", "path": path.as_posix()}
    return {
        "allowed": False,
        "kind": "invented",
        "reason": "Do not invent a student folder path.",
        "path": path.as_posix(),
    }


def research_file(essay_id: str, raw: object, *, save: bool = False) -> Path | None:
    """Open or save one research path only when allow_research_path allows it."""
    decision = allow_research_path(essay_id, raw, save=save)
    if decision.get("allowed") is not True:
        return None
    text = decision.get("path")
    if not isinstance(text, str) or not text:
        return None
    return Path(text)


_PRODUCT_ROOTS = frozenset({"Essay-writer", "uploads", "unassigned", "KB1"})
_CODE_ROOTS = frozenset({"src", "tests", "docs"})


class RepoSaveRefused(Exception):
    """A student save landed in the code checkout."""


def repo_save_refused(path: Path) -> bool:
    """True when a student save would land in the code checkout.

    Product folders (Essay-writer, uploads, unassigned, KB1) stay allowed,
    including when the cloud computer keeps them beside the checkout.
    A save under src, tests, docs, or any other checkout file is refused.
    """
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = Path(path)
    root = repo_root().resolve()
    if resolved == root:
        return True
    if not _is_under(resolved, root):
        return False
    try:
        parts = resolved.relative_to(root).parts
    except ValueError:
        return False
    if not parts:
        return True
    if parts[0] in _CODE_ROOTS or parts[0].startswith("."):
        return True
    if parts[0] in _PRODUCT_ROOTS:
        return False
    return True


def guard_write_door(*paths: object) -> dict[str, object] | None:
    """Refuse a write door whose destination is the code checkout."""
    from essay_writer.confirm import refuse

    for raw in paths:
        if raw is None:
            continue
        path = raw if isinstance(raw, Path) else Path(str(raw))
        if repo_save_refused(path):
            return refuse("repo-not-save", "The code checkout is not a student save.")
    return None


def refuse_repo_write(path: Path) -> None:
    """Backstop for writers that do not return a door reply."""
    if repo_save_refused(path):
        raise RepoSaveRefused("The code checkout is not a student save.")
