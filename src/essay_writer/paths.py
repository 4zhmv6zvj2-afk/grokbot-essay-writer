"""Essay roots, module ids, and path confinement."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

# A brief code such as MOD1004AA or RPT5001AA, or a short id minted from a title.
_COURSE_CODE = r"[A-Z]{2,6}\d{3,4}[A-Z]{2,8}"
_MINTED_CODE = r"[A-Z]{4,16}"
ESSAY_ID = re.compile(rf"^(?:{_COURSE_CODE}|{_MINTED_CODE})$")
SEQUENCE_ID = re.compile(rf"^({_COURSE_CODE}|{_MINTED_CODE})-([1-9][0-9]*)$")
BRIEF_NAMES = frozenset({"brief.md", "brief.txt", "brief.docx"})
TEXT_SUFFIXES = frozenset({".md", ".txt", ".csv", ".json", ".html", ".htm"})
SETUP_DIRNAME = "Essay-writer"
# Grok Bot keeps durable files on its cloud computer, in /workspace.
CLOUD_WORKSPACE = Path("/workspace")


def recommended_base() -> Path | None:
    """Parent of the app store and the KB1 vault.

    The Grok Bot cloud computer is /workspace. There is no Documents fallback.
    A user-local save is an explicit path passed to essay.setup.
    """
    if CLOUD_WORKSPACE.is_dir():
        return CLOUD_WORKSPACE / SETUP_DIRNAME
    return None


def recommended_paths() -> tuple[Path, Path] | None:
    base = recommended_base()
    if base is None:
        return None
    return base / "app", base / "KB1"


def saved_setup_path() -> Path | None:
    """Where setup.json lives. Later tools do not read recommended_base."""
    if not CLOUD_WORKSPACE.is_dir():
        return None
    return CLOUD_WORKSPACE / SETUP_DIRNAME / "setup.json"


def _folder_from_setup(saved: dict) -> str | None:
    """app_path is the folder later tools load. The word open is not a folder."""
    for key in ("app_path", "app"):
        raw = saved.get(key)
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text or text.casefold() == "open":
            continue
        return text
    return None


def load_saved_setup() -> dict | None:
    """Read the setup record. Ignored when a test root is set."""
    if os.environ.get("ESSAY_WRITER_ROOT"):
        return None
    path = saved_setup_path()
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def workspace_root() -> Path:
    override = os.environ.get("ESSAY_WRITER_ROOT")
    if override:
        return Path(override).resolve()
    saved = load_saved_setup()
    app = _folder_from_setup(saved) if saved else None
    if app:
        return Path(app).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "essay_writer").is_dir():
            return parent
    return here.parents[2]


def essay_id_error(value: object) -> str | None:
    if not isinstance(value, str) or not ESSAY_ID.fullmatch(value):
        return (
            "essay_id must be one module code, such as MOD1004AA, "
            "or the code the brief prints. "
            "One id per essay; briefs and uploads are not shared."
        )
    return None


def module_code(value: str) -> str:
    """Module folder name. A sequence id such as MOD1011AA-5 uses the module MOD1011AA."""
    match = SEQUENCE_ID.fullmatch(value)
    if match:
        return match.group(1)
    return value


def sequence_number(value: str) -> int | None:
    match = SEQUENCE_ID.fullmatch(value)
    if match:
        return int(match.group(2))
    return None


def sequence_numbers(module: str) -> list[int]:
    """Sequence folders named 1, 2, 3, … Partial clone folders are not included."""
    root = essay_dir(module) / "sequences"
    if not root.is_dir():
        return []
    numbers: list[int] = []
    for child in root.iterdir():
        if child.is_dir() and child.name.isdigit() and int(child.name) >= 1:
            numbers.append(int(child.name))
    return sorted(numbers)


def last_saved_path(module: str) -> Path:
    return essay_dir(module) / "last-saved.json"


def read_last_saved(module: str) -> int | None:
    """Sequence whose state was saved last. Never the highest folder number."""
    path = last_saved_path(module)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    number = data.get("sequence")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        return None
    if number not in sequence_numbers(module):
        return None
    return number


def write_last_saved(module: str, number: int) -> None:
    path = last_saved_path(module)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"sequence": number, "sequence_id": f"{module}-{number}"},
        indent=2,
    ) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def sequence_write_error(value: object) -> str | None:
    """Research, validation, revise, Word, and the shelf write only on a real sequence.

    The reply is for Grok Bot to say to the user. A bare module code writes nothing.
    """
    if not isinstance(value, str):
        return "I can't find that sequence. Start a new one with essay.sequence.new?"
    number = sequence_number(value)
    if number is None:
        if essay_id_error(value):
            return "I can't find that module. Start a new sequence with essay.sequence.new?"
        if (essay_dir(value) / "archived.json").is_file():
            return f"{value} is archived. Unarchive it before continuing."
        saved = read_last_saved(value)
        if saved is not None:
            saved_id = f"{value}-{saved}"
            return (
                f"I can't write {value} beside its sequences. "
                f"The last-saved sequence is {saved_id}. "
                "Tell me that id to continue, or say if you want a new sequence."
            )
        if sequence_numbers(value):
            return (
                f"I can't write {value} beside its sequences. "
                "Name the sequence id, or start a new one with essay.sequence.new?"
            )
        return f"I can't find a sequence for {value}. Start a new one with essay.sequence.new?"
    module = module_code(value)
    if not sequence_dir(module, number).is_dir():
        return f"I can't find {value}. Start a new sequence with essay.sequence.new?"
    if (essay_dir(module) / "archived.json").is_file():
        return f"{module} is archived. Unarchive it before continuing."
    return None


def target_error(value: object) -> str | None:
    """Accept a module code, or a sequence id whose folder is already on disk."""
    if not isinstance(value, str):
        return essay_id_error(value)
    number = sequence_number(value)
    if number is None:
        error = essay_id_error(value)
        if error:
            return error
        module = value
    else:
        module = module_code(value)
        if not sequence_dir(module, number).is_dir():
            return f"{value} is not on disk. Start it with essay.sequence.new."
    if (essay_dir(module) / "archived.json").is_file():
        return f"{module} is archived. Unarchive it before continuing."
    return None


def essay_dir(essay_id: str) -> Path:
    return workspace_root() / "Essay-writer" / module_code(essay_id)


def work_dir(essay_id: str) -> Path:
    """State, drafts, shelf, and Word output. Shared uploads stay on the module."""
    number = sequence_number(essay_id)
    if number is None:
        return essay_dir(essay_id)
    return sequence_dir(module_code(essay_id), number)


def uploads_dir(essay_id: str) -> Path:
    return workspace_root() / "uploads" / module_code(essay_id)


def uploads_root() -> Path:
    return workspace_root() / "uploads"


def unassigned_dir() -> Path:
    return workspace_root() / "unassigned"


def kb1_root() -> Path:
    saved = load_saved_setup()
    kb1 = saved.get("kb1") if saved else None
    if isinstance(kb1, str) and kb1.strip():
        return Path(kb1).expanduser().resolve()
    return workspace_root() / "KB1"


def kb1_module_dir(essay_id: str) -> Path:
    return kb1_root() / module_code(essay_id)


def sequence_dir(essay_id: str, number: int) -> Path:
    return essay_dir(essay_id) / "sequences" / str(number)


def kb1_sequence_dir(essay_id: str, number: int) -> Path:
    return kb1_module_dir(essay_id) / "sequences" / str(number)


def local_pack_index() -> list[dict[str, str]]:
    """KB1-style markdown the research door may name. Names come from disk only."""
    root = workspace_root() / "Essay-writer"
    found: list[dict[str, str]] = []
    if not root.is_dir():
        return found
    for essay in sorted(path for path in root.iterdir() if path.is_dir() and ESSAY_ID.fullmatch(path.name)):
        if (essay / "archived.json").is_file():
            continue
        kb1 = essay / "kb1"
        if not kb1.is_dir():
            continue
        for path in sorted(kb1.rglob("*.md")):
            if any(part.startswith(".") for part in path.relative_to(kb1).parts):
                continue
            found.append({"essay_id": essay.name, "name": relative(path)})
    return found


def local_pack_names(essay_id: str) -> list[str]:
    module = module_code(essay_id)
    return [item["name"] for item in local_pack_index() if item["essay_id"] == module]


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root()).as_posix()
    except ValueError:
        return path.name


def _path_parts_casefold(path: Path) -> list[str]:
    return [part.casefold() for part in path.parts]


_INTERNAL_VOLUME_PARTS = frozenset({"researchdrive", "backupdrive", "archivedrive"})


def _refuse_internal_volume(path: Path) -> bool:
    return any(part in _INTERNAL_VOLUME_PARTS for part in _path_parts_casefold(path))


def student_chat_path(raw: object) -> str:
    """Path wording for student chat. Never a volume or internal drive path.

    Folders on the cloud computer stay distinct. The app, KB1, and the setup
    record are not collapsed into one phrase.
    """
    if not isinstance(raw, str) or not raw.strip():
        return "" if raw is None else str(raw)
    text = raw.strip().replace("\\", "/")
    if text.casefold() == "open":
        return text
    try:
        expanded = Path(text).expanduser()
        resolved = expanded.resolve() if expanded.is_absolute() or text.startswith("~") else expanded
    except OSError:
        resolved = Path(text).expanduser()
    if _refuse_internal_volume(resolved):
        return "a folder you named on this computer"
    cloud = CLOUD_WORKSPACE
    try:
        tail = resolved.resolve().relative_to(cloud.resolve())
    except (OSError, ValueError):
        tail = None
    if tail is not None:
        spoken = tail.as_posix()
        if spoken and spoken != ".":
            return spoken
        return "the cloud computer"
    home = Path.home()
    try:
        under_home = resolved.resolve().relative_to(home.resolve())
    except (OSError, ValueError):
        return resolved.as_posix()
    if under_home.parts and under_home.parts[0].casefold() == "documents":
        documents_tail = "/".join(under_home.parts[1:])
        return f"Documents/{documents_tail}" if documents_tail else "Documents"
    return resolved.as_posix()


def confine(base: Path, relative_name: str) -> Path:
    """Resolve relative_name inside base, or raise ValueError."""
    if not isinstance(relative_name, str) or not relative_name.strip():
        raise ValueError("missing file name")
    raw = relative_name.strip().replace("\\", "/")
    if raw.startswith("/") or raw.startswith("~"):
        raise ValueError("absolute paths are not allowed")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("path escapes the essay folder")
    if any("\x00" in part or part.startswith(".") for part in parts):
        raise ValueError("hidden or empty path parts are not allowed")
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if not target.is_relative_to(base_resolved):
        raise ValueError("path escapes the essay folder")
    return target


def locator_target(essay_id: str, locator: str) -> tuple[str, Path | None]:
    """Return (kind, path) for a gathered locator.

    kind is upload, brief, or kb1-file. A KB1 note is the file on disk.
    Raises ValueError with a short reason.
    """
    if not isinstance(locator, str) or not locator.strip():
        raise ValueError("locator is required")
    raw = locator.strip().replace("\\", "/")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("absolute locators are not allowed")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise ValueError("locator escapes the essay folder")
    lowered = raw.casefold()
    if "samples-study" in lowered or lowered.startswith("docs/"):
        raise ValueError("sample-reference")
    if len(parts) < 3 or parts[0] not in {"uploads", "Essay-writer", "kb1"}:
        raise ValueError("locator must start with uploads/, Essay-writer/, or kb1/ for this essay id")
    if parts[1] != module_code(essay_id):
        raise ValueError("cross-essay")
    if parts[0] == "uploads":
        return "upload", confine(uploads_dir(essay_id), "/".join(parts[2:]))
    if parts[0] == "kb1":
        relative_name = "/".join(parts[2:])
        if not relative_name:
            raise ValueError("KB1 locators name a note file for this essay")
        return "kb1-file", confine(kb1_module_dir(essay_id), relative_name)
    if len(parts) >= 4 and parts[2] == "kb1" and parts[-1].lower().endswith(".md"):
        return "kb1-file", confine(essay_dir(essay_id) / "kb1", "/".join(parts[3:]))
    filename = parts[-1].lower()
    if filename not in BRIEF_NAMES or len(parts) != 3:
        raise ValueError("Essay-writer locators can only be the brief or a kb1 markdown note for this essay")
    if parts[2] in {"state.json"}:
        raise ValueError("that file is not a source")
    return "brief", confine(essay_dir(essay_id), parts[2])
