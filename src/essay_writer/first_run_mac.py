"""Mac handoff: the friend's Documents/Essay Bot folder and copies to it.

Everything here answers one question: where does a delivered Word or zip file
land on the friend's Mac, and how is that place remembered? The quarantine
clearing on a copy is scoped to paths the product generated.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from essay_writer import paths as essay_paths
from essay_writer.first_run_common import _internal_volume
from essay_writer.known_paths import RepoSaveRefused, refuse_repo_write
from essay_writer.paths import SETUP_DIRNAME, kb1_root, work_dir, workspace_root
from essay_writer.prompt_loader import text
from essay_writer.student_voice import say

MAC_DIRNAME = "Essay-writer-deliverables"
MAC_HANDOFF_SECRET = "ESSAY_WRITER_MAC_DIR"
RECOMMENDED_MAC_HANDOFF_NAME = "Essay Bot"
MAC_FOUR_WAY_CARD = text("install/operator.md", "four_way_card")
MAC_FOUR_WAY_FRIEND_SPEECH = text("install/operator.md", "four_way_friend")
MAC_DELIVERABLES_NAME = "mac-deliverables.json"
# Names copy_to_mac writes for a sequence. Not a directory listing.
KNOWN_MAC_DELIVERABLE_NAMES = (
    "annotation.docx",
    "download-list.docx",
    "papers.zip",
    "critical-reviews.zip",
)
DELIVERABLE_SUFFIXES = frozenset({".docx", ".zip"})

MAC_RESIDUAL = (
    "No Mac folder is available. Set ESSAY_WRITER_MAC_DIR to a folder on the Mac. "
    "This helper only copies an existing .docx or .zip."
)
MAC_NOT_MOUNTED_CHAT = (
    "The Mac handoff folder is not available on this computer. "
    "The Word or zip file stays where it is. "
    "Set ESSAY_WRITER_MAC_DIR to a mounted Mac folder, or copy the file yourself."
)
UPGRADE_REREAD_SPEECH = text("install/operator.md", "upgrade_reread")
UPGRADE_REREAD_MARKER = ".essay-writer-upgrade-reread.json"


def _on_mac() -> bool:
    return sys.platform == "darwin"


def _process_home() -> Path:
    """Home of this process. On Grok Bot that is the Linux computer, not the Mac."""
    return Path.home()


def _under_dir(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _one_mounted_mac_home() -> Path | None:
    """One Mac home already visible on this computer. Never creates /Users."""
    users = Path("/Users")
    if not users.is_dir():
        return None
    found: list[Path] = []
    try:
        children = list(users.iterdir())
    except OSError:
        return None
    for child in children:
        if not child.is_dir() or child.name.startswith(".") or child.name in {"Shared", "root"}:
            continue
        if (child / "Documents").is_dir() or (child / "Library").is_dir():
            found.append(child)
    if len(found) == 1:
        return found[0]
    return None


def friend_mac_home(*, discover_mounted: bool = True) -> Path | None:
    """Home folder on the friend's Mac when this computer can already see it.

    Darwin uses this process home. Grok Bot Linux does not: that home is the
    bot computer. A mounted Mac home is ESSAY_WRITER_MAC_HOME when that
    directory already exists, or the one /Users home this computer can see.
    This function does not create the home. Tests that must assert an unmounted
    Mac pass ``discover_mounted=False`` or replace ``_one_mounted_mac_home``.
    """
    if _on_mac():
        home = _process_home()
        return home if home.is_dir() else None
    override = os.environ.get("ESSAY_WRITER_MAC_HOME")
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        home = Path(text).expanduser()
        return home if home.is_dir() else None
    if not discover_mounted:
        return None
    return _one_mounted_mac_home()


def recommended_mac_handoff_dir() -> Path | None:
    """Documents/Essay Bot on the friend's Mac. Not the Grok Bot Linux home."""
    home = friend_mac_home()
    if home is None:
        return None
    return home / "Documents" / RECOMMENDED_MAC_HANDOFF_NAME


def visible_canonical_mac_handoff_dir() -> Path | None:
    """Documents/Essay Bot when this computer already sees that folder on the Mac."""
    target = recommended_mac_handoff_dir()
    if target is None or not target.is_dir():
        return None
    return target


def upgrade_reread_tip_sha() -> str:
    """Stable id for the one-shot upgrade FO card. PR bodies cite this."""
    return hashlib.sha256(UPGRADE_REREAD_SPEECH.encode("utf-8")).hexdigest()[:12]


def _upgrade_reread_marker_path(root: Path) -> Path:
    return Path(root) / UPGRADE_REREAD_MARKER


def _take_upgrade_reread_card(root: Path) -> str | None:
    path = _upgrade_reread_marker_path(root)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict) and data.get("shown") is True:
            return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"shown": True}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return UPGRADE_REREAD_SPEECH
    return UPGRADE_REREAD_SPEECH


def attach_friend_upgrade_fo_card(result: dict[str, Any], *, root: Path) -> dict[str, Any]:
    """One-shot operator card after friend install or Custom MCP upgrade. Not student chat."""
    if not result.get("ok"):
        return result
    card = _take_upgrade_reread_card(root)
    if card:
        result["fo_card"] = card
        result["upgrade_reread_tip_sha"] = upgrade_reread_tip_sha()
    return result


def _folder_on_friend_mac(path: Path | str) -> tuple[Path | None, str | None]:
    """Where a handoff path is created. The second value blocks a Linux mkdir."""
    raw = str(path).strip()
    if raw.casefold() == "open":
        return Path(raw), None
    if _on_mac():
        if raw.startswith("~") or Path(raw).is_absolute():
            return Path(raw).expanduser(), None
        home = friend_mac_home()
        if home is None:
            return None, "mac-not-mounted"
        return home / raw, None
    home = friend_mac_home()
    if raw.startswith("~"):
        if home is None:
            return None, "mac-not-mounted"
        rest = raw[1:].lstrip("/")
        return (home / rest) if rest else home, None
    folder = Path(raw).expanduser()
    if not folder.is_absolute():
        if home is None:
            return None, "mac-not-mounted"
        return home / folder, None
    process = _process_home()
    cloud = essay_paths.CLOUD_WORKSPACE
    if _under_dir(folder, process):
        if home is None:
            return None, "mac-not-mounted"
        tail = folder.resolve().relative_to(process.resolve())
        return home / tail, None
    if _under_dir(folder, cloud):
        return None, "mac-not-mounted"
    return folder, None


def _mac_handoff_store_path() -> Path | None:
    from essay_writer.setup import _secrets_path

    record = essay_paths.saved_setup_path()
    if record is not None:
        return _secrets_path(record)
    if essay_paths.CLOUD_WORKSPACE.is_dir():
        return essay_paths.CLOUD_WORKSPACE / SETUP_DIRNAME / "setup.secrets.json"
    return None


def read_mac_handoff_dir() -> Path | None:
    """Mac handoff folder from ESSAY_WRITER_MAC_DIR or setup.secrets.json."""
    override = os.environ.get(MAC_HANDOFF_SECRET)
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        return Path(text).expanduser()
    from essay_writer.setup import read_setup_secret

    stored = read_setup_secret(MAC_HANDOFF_SECRET)
    if stored:
        return Path(stored).expanduser()
    return None


_SKIP_HANDOFF = frozenset({"later", "skip", "decline"})
_OK_HANDOFF = frozenset({"ok", "okay", "confirm"})
_ANOTHER_HANDOFF = frozenset({"another", "another folder", "another path"})


def choose_mac_handoff(choice: str, *, folder: str | None = None) -> dict[str, Any]:
    """Apply the four-way Mac card. OK and a named folder are created on the Mac.

    Later, skip, and decline do not create a folder and do not set
    ESSAY_WRITER_MAC_DIR. Cursor and Grok Build both call this function.
    """
    text = choice.strip()
    folded = text.casefold()
    if folded in _SKIP_HANDOFF:
        return {
            "ok": True,
            "remembered": False,
            "created": False,
            "choice": "skip",
            "chat_only": True,
            "mac_folder_ready": False,
        }
    if folded in _OK_HANDOFF or folded == f"documents/{RECOMMENDED_MAC_HANDOFF_NAME}".casefold():
        target = recommended_mac_handoff_dir()
        if target is None:
            return {
                "ok": False,
                "remembered": False,
                "created": False,
                "choice": "ok",
                "reason": "mac-not-mounted",
                "chat_only": False,
                "mac_folder_ready": False,
            }
        result = remember_mac_handoff_dir(target)
        result["choice"] = "ok"
        result["remembered"] = bool(result.get("ok"))
        result["created"] = bool(result.get("ok"))
        result["chat_only"] = False
        result["mac_folder_ready"] = bool(result.get("ok"))
        return result
    if folded in _ANOTHER_HANDOFF and (not isinstance(folder, str) or not folder.strip()):
        return {
            "ok": False,
            "remembered": False,
            "created": False,
            "choice": "another",
            "reason": "Name the Mac folder.",
            "chat_only": False,
            "mac_folder_ready": False,
        }
    named = folder.strip() if folded in _ANOTHER_HANDOFF and isinstance(folder, str) else text
    if not named:
        return {
            "ok": False,
            "remembered": False,
            "created": False,
            "reason": "Name the Mac folder.",
            "chat_only": False,
            "mac_folder_ready": False,
        }
    result = remember_mac_handoff_dir(named)
    result["choice"] = "another"
    result["remembered"] = bool(result.get("ok"))
    result["created"] = bool(result.get("ok"))
    result["chat_only"] = False
    result["mac_folder_ready"] = bool(result.get("ok"))
    return result


def remember_mac_handoff_dir(path: Path | str) -> dict[str, Any]:
    """Remember the Mac handoff folder for copy_to_mac and mac_deliverables_dir.

    The folder is created on the friend's Mac. A Grok Bot Linux home path is
    not created and is not stored as ESSAY_WRITER_MAC_DIR.
    """
    located, blocked = _folder_on_friend_mac(path)
    if blocked:
        return {"ok": False, "reason": blocked, "remembered": False, "created": False}
    folder = located if located is not None else Path(path).expanduser()
    if _internal_volume(folder):
        return {"ok": False, "reason": "That folder is not a copy path on this computer."}
    if folder.name.casefold() == "open":
        return {
            "ok": False,
            "reason": "Name the Mac handoff folder. The word open is not a folder.",
        }
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "reason": str(exc)}
    if not folder.is_dir():
        return {"ok": False, "reason": "The Mac handoff path is not a folder."}
    resolved = str(folder.resolve())
    store = _mac_handoff_store_path()
    if store is not None:
        existing: dict[str, str] = {}
        if store.is_file():
            try:
                data = json.loads(store.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            if isinstance(data, dict):
                existing = {
                    key: value
                    for key, value in data.items()
                    if isinstance(key, str) and isinstance(value, str) and value.strip()
                }
        existing[MAC_HANDOFF_SECRET] = resolved
        from essay_writer.setup import _write_secret_text

        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            _write_secret_text(store, json.dumps(existing, indent=2) + "\n")
        except OSError as exc:
            return {"ok": False, "reason": str(exc), "path": resolved}
    return {"ok": True, "path": resolved}


def mac_deliverables_dir(*, read_remembered: bool | None = None) -> Path | None:
    """Mac handoff root: ESSAY_WRITER_MAC_DIR, else visible Documents/Essay Bot on the Mac.

    ``read_remembered`` is an explicit policy. The default reads the remembered
    folder from setup.secrets.json unless ESSAY_WRITER_ROOT isolates this run to
    a test ledger; a caller that must not consult it passes False. The
    documented ESSAY_WRITER_MAC_DIR override still wins.
    """
    override = os.environ.get(MAC_HANDOFF_SECRET)
    if override is not None:
        text = override.strip()
        if not text or text.casefold() == "open":
            return None
        return Path(text).expanduser()
    if read_remembered is None:
        read_remembered = not os.environ.get("ESSAY_WRITER_ROOT")
    remembered = read_mac_handoff_dir() if read_remembered else None
    if remembered is not None:
        return remembered
    return visible_canonical_mac_handoff_dir()


def module_mac_deliverables_dir(module: str) -> Path | None:
    """Documents/Essay Bot/<module> when the Mac handoff root is remembered."""
    if not isinstance(module, str) or not module.strip():
        return None
    base = mac_deliverables_dir()
    if base is None:
        return None
    return base / module.strip()


def module_shared_mac_deliverables_dir(essay_id: str) -> Path | None:
    """Documents/Essay Bot/<module>/shared for module-common Mac copies."""
    if not isinstance(essay_id, str) or not essay_id.strip():
        return None
    module = essay_paths.module_code(essay_id.strip())
    parent = module_mac_deliverables_dir(module)
    if parent is None:
        return None
    return parent / "shared"


def sequence_mac_deliverables_dir(essay_id: str) -> Path | None:
    """Documents/Essay Bot/<module>/<essay_id> when the Mac handoff root is remembered."""
    if not isinstance(essay_id, str) or not essay_id.strip():
        return None
    module = essay_paths.module_code(essay_id.strip())
    parent = module_mac_deliverables_dir(module)
    if parent is None:
        return None
    return parent / essay_id.strip()


def sequence_mac_handoff_place(essay_id: str, leaf: str) -> str:
    """Chat display path under Documents/Essay Bot/<module>/<essay_id>/."""
    text = essay_id.strip()
    module = essay_paths.module_code(text)
    return f"Documents/Essay Bot/{module}/{text}/{leaf}"


def ensure_sequence_mac_folder(essay_id: str) -> dict[str, Any]:
    """Create module, shared, and per-sequence Mac folders. Stage 1 Confirm calls this."""
    module_dir = module_mac_deliverables_dir(essay_paths.module_code(essay_id))
    shared_dir = module_shared_mac_deliverables_dir(essay_id)
    folder = sequence_mac_deliverables_dir(essay_id)
    if folder is None or module_dir is None or shared_dir is None:
        return {
            "ok": True,
            "created": False,
            "remembered": False,
            "reason": "mac-not-mounted",
        }
    for target in (module_dir, shared_dir, folder):
        if _internal_volume(target):
            return {
                "ok": False,
                "created": False,
                "remembered": True,
                "reason": "That folder is not a copy path on this computer.",
            }
    existed = folder.is_dir()
    try:
        module_dir.mkdir(parents=True, exist_ok=True)
        shared_dir.mkdir(parents=True, exist_ok=True)
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "created": False, "remembered": True, "reason": str(exc)}
    if not folder.is_dir():
        return {
            "ok": False,
            "created": False,
            "remembered": True,
            "reason": "The Mac copy path is not a folder.",
        }
    return {
        "ok": True,
        "created": not existed,
        "remembered": True,
        "path": str(folder.resolve()),
        "module_path": str(module_dir.resolve()),
        "shared_path": str(shared_dir.resolve()),
    }


def _mac_copy_folder(source: Path, mac_dir: Path | None) -> Path | None:
    if mac_dir is not None:
        return Path(mac_dir).expanduser()
    from essay_writer.build_office import essay_id_from_deliverable_path

    essay_id = essay_id_from_deliverable_path(source)
    if essay_id:
        seq_folder = sequence_mac_deliverables_dir(essay_id)
        if seq_folder is not None:
            return seq_folder
    return mac_deliverables_dir()


def mac_deliverables_record(essay_id: str) -> Path:
    """Where this sequence remembers Mac copies. One file. No folder listing."""

    return work_dir(essay_id) / MAC_DELIVERABLES_NAME


def remember_mac_deliverable(source: Path, target: Path) -> None:
    """Store one copied Word or zip path on the sequence it came from."""
    from essay_writer.build_office import essay_id_from_deliverable_path

    essay_id = essay_id_from_deliverable_path(source)
    if not essay_id or target.suffix.lower() not in DELIVERABLE_SUFFIXES:
        return
    try:
        expanded = target.expanduser()
    except OSError:
        return
    if expanded.is_symlink() or not expanded.is_file():
        return
    try:
        resolved = expanded.resolve()
    except OSError:
        return
    if _internal_volume(resolved):
        return
    for root in (workspace_root(), kb1_root()):
        try:
            base = root.resolve()
        except OSError:
            base = root
        if resolved == base or resolved.is_relative_to(base):
            return
    path = mac_deliverables_record(essay_id)
    try:
        refuse_repo_write(path)
    except RepoSaveRefused:
        return
    existing: list[str] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        raw = data.get("paths") if isinstance(data, dict) else None
        if isinstance(raw, list):
            existing = [item for item in raw if isinstance(item, str) and item.strip()]
    stored = str(resolved)
    if stored not in existing:
        existing.append(stored)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"paths": existing}, indent=2) + "\n"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return


def sequence_mac_candidates(essay_id: str) -> list[str]:
    """Saved copy_to_mac paths, then exact default names in the Mac handoff folder.

    Does not list Documents, home, or the handoff folder.
    """
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        text = raw.strip()
        if not text or text in seen:
            return
        seen.add(text)
        found.append(text)

    record = mac_deliverables_record(essay_id)
    if record.is_file():
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        paths = data.get("paths") if isinstance(data, dict) else None
        if isinstance(paths, list):
            for item in paths:
                if isinstance(item, str):
                    add(item)
    folder = sequence_mac_deliverables_dir(essay_id)
    if folder is not None:
        try:
            base = folder.expanduser()
        except OSError:
            base = folder
        if not base.is_absolute():
            base = base.resolve()
        for name in (f"{essay_id}.docx", *KNOWN_MAC_DELIVERABLE_NAMES):
            add(str(base / name))
    return found


def copy_deliverable_to_mac(source: Path, *, mac_dir: Path | None = None) -> dict[str, Any]:
    """Copy an existing .docx or .zip onto the Mac. Other files stay where they are.

    A directory copies each Word file and zip sitting directly in it. Quarantine
    and provenance are only cleared on a copy the product generated for a
    sequence (a path under ``Essay-writer/<module>/sequences/<n>``); an
    operator-named file keeps its marks and the report says the clearing was
    skipped.
    """
    path = Path(source).expanduser()
    if path.is_dir():
        files = [
            child
            for child in sorted(path.iterdir())
            if child.is_file() and child.suffix.lower() in DELIVERABLE_SUFFIXES
        ]
        copies = [copy_deliverable_to_mac(child, mac_dir=mac_dir) for child in files]
        return {
            "ok": all(item.get("ok", False) for item in copies) if copies else True,
            "copied": any(item.get("copied") for item in copies),
            "source": str(path),
            "files": copies,
        }
    if path.suffix.lower() not in DELIVERABLE_SUFFIXES:
        return {
            "ok": False,
            "copied": False,
            "source": str(path),
            "reason": "Only a Word .docx or a .zip is copied.",
        }
    if not path.is_file():
        return {
            "ok": False,
            "copied": False,
            "source": str(path),
            "reason": "That deliverable is not a file.",
        }
    generated = _app_generated_deliverable(path)
    folder = _mac_copy_folder(path, mac_dir)
    if folder is None:
        return {
            "ok": True,
            "copied": False,
            "source": str(path),
            "reason": "mac-not-mounted",
            "residual": MAC_RESIDUAL,
            "next": say(MAC_NOT_MOUNTED_CHAT),
        }
    if _internal_volume(folder):
        return {
            "ok": False,
            "copied": False,
            "source": str(path),
            "reason": "That folder is not a copy path on this computer.",
        }
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / path.name
        if target.exists() and not target.is_file():
            return {
                "ok": False,
                "copied": False,
                "source": str(path),
                "reason": "The Mac copy path is a folder.",
            }
        if path.resolve() == target.resolve():
            cleared = _clear_delivered(target, generated=generated)
            remember_mac_deliverable(path, target)
            return {
                "ok": True,
                "copied": True,
                "source": str(path),
                "path": str(target),
                "already": True,
                "quarantine": cleared,
            }
        replaced = target.is_file()
        shutil.copy2(path, target)
        cleared = _clear_delivered(target, generated=generated)
    except OSError as exc:
        return {"ok": False, "copied": False, "source": str(path), "reason": str(exc)}
    remember_mac_deliverable(path, target)
    return {
        "ok": True,
        "copied": True,
        "source": str(path),
        "path": str(target),
        "replaced": replaced,
        "quarantine": cleared,
    }


def _app_generated_deliverable(path: Path) -> bool:
    """True when the product wrote this path for a sequence."""
    from essay_writer.build_office import essay_id_from_deliverable_path

    try:
        return essay_id_from_deliverable_path(path) is not None
    except (OSError, ValueError):
        return False


def _clear_delivered(path: Path, *, generated: bool) -> dict[str, Any]:
    """Clear quarantine and provenance on an app-generated Documents copy.

    An operator-named .docx or .zip crossing the same copy path keeps its
    marks: ``skipped`` and ``reason`` report that nothing was cleared.
    """
    from essay_writer.quarantine import clear_mac_quarantine

    if not generated:
        return {
            "ok": True,
            "cleared": [],
            "absent": [],
            "noop": True,
            "skipped": True,
            "reason": "not-an-app-deliverable",
        }
    result = dict(clear_mac_quarantine(path))
    result["skipped"] = False
    return result
