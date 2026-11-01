"""First-run folders. Draft writes nothing. Confirm creates the door tree.

The front office says the replies. File work does not own the chat. The
mid-office shell is a one-time setup pick, stored as mid_office_shell.
Save on the cloud computer, or on a path the user names on this computer.
A path the user did not name is refused. Documents is not a fallback and is never labelled as the cloud.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from essay_writer import known_paths as essay_known_paths
from essay_writer import paths as essay_paths
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.debug_log import record_requests_debug
from essay_writer.first_run import MAC_FOUR_WAY_CARD
from essay_writer.paths import recommended_paths
from essay_writer.student_voice import speak

TOOL = "essay.setup"
SHELL_CURSOR = "cursor"
SHELL_GROK_BUILD = "grok_build"


def parse_shell(value: object) -> str | None:
    """Map a setup pick onto mid_office_shell. None when it is not a pick.

    Cursor stores cursor. SuperGrok stores grok_build. The stored enum
    grok_build is accepted on a later setup. grokbuild is the binary token,
    not a shell.
    """
    if not isinstance(value, str):
        return None
    folded = " ".join(value.strip().casefold().replace("-", " ").replace("_", " ").split())
    if not folded:
        return None
    if folded == "cursor":
        return SHELL_CURSOR
    if folded in {"supergrok", "super grok", "grok build"}:
        return SHELL_GROK_BUILD
    return None


def persisted_shell() -> str:
    """Shell on the setup record later tools already read. Absent means cursor."""

    saved = essay_paths.load_saved_setup()
    if not isinstance(saved, dict) or "mid_office_shell" not in saved:
        return SHELL_CURSOR
    parsed = parse_shell(saved.get("mid_office_shell"))
    return parsed if parsed is not None else SHELL_GROK_BUILD


def mid_office() -> str:
    """Operator name for the persisted mid-office shell. Absent field is Cursor."""
    if persisted_shell() == SHELL_CURSOR:
        return "Cursor"
    return "Grok Build"


def resolve_setup_shell(value: object) -> str | dict[str, object]:
    """Blank keeps cursor. Any other unknown pick is refused."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return SHELL_CURSOR
    parsed = parse_shell(value)
    if parsed is None:
        return refuse(
            "setup",
            "That file-work pick is not one of the two setup choices. "
            "Ask again, then call essay.setup with that choice. "
            "Do not infer it from what is installed.",
        )
    return parsed


CARD_RULES = """The Consensus key is for academic research search: it finds papers for the research step. Consensus's help center says the API is how a tool programmatically searches academic research and retrieves relevant papers: https://help.consensus.app/en/articles/16516328-the-consensus-api

Create that key with Consensus's own steps from that page. Click the profile icon in the bottom-left corner, select API & MCP Dashboard, open the Keys and Clients tab, click New key, give the key a name so you can tell what it is for, then create it and copy it somewhere secure. The full key is shown once. If it is lost, revoke it and create a new one. The same path is on https://docs.consensus.app/api-plans-and-access : profile icon, then API & MCP Dashboard, then Keys and clients, then New key. The dashboard named from get-started is https://consensus.app/api-mcp

Ask which Consensus plan they have. Free stores ESSAY_WRITER_CONSENSUS_PAID as 0. Pro stores it as 1. Teams, Deep, and Enterprise use 1, the same paid flag as Pro. Do not add another flag. The published limits are only those on https://docs.consensus.app/api-plans-and-access : Free includes 30 calls a month and the maximum with additional usage is 30; Pro includes 500 and the maximum with additional usage is 1,000. Max papers per request is 20 on Free and 300 on Pro. Pagination past the first page is no on Free and yes on Pro. Full-text excerpts are no on Free and yes on Pro. The rate limit is 1 request per second on Free and 1 request per second on Pro.

The email is for Unpaywall free-PDF lookup. Unpaywall's API docs say a request must include the email as ?email=YOUR_EMAIL, and they ask for at most 100,000 calls a day: https://unpaywall.org/products/api . OpenAlex, from the same team, asks for an email where they can contact you if a script goes wrong, and says that approach is copied from Crossref: https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md . Crossref's REST API FAQ answers "Will you spam me with marketing bumf once you have our contact info?" with "No. We will only use it to contact you about problems with your scripts." https://github.com/CrossRef/rest-api-doc/blob/master/README.md . Say that limit, attributed to the Crossref FAQ by way of OpenAlex. Do not say that Unpaywall's own page promised never to email.

If the user skips the Consensus key, the Unpaywall email, or both, show the warning before the skip is accepted. Consensus is not used when the key is missing. Unpaywall free PDF lookup will not run when the email is missing. OpenAlex still runs. After an explicit yes to that warning, call essay.setup with confirmPhase draft, acknowledge_skipped_searches true, and the same other arguments. Show that result. After another explicit yes, call essay.setup with confirmPhase confirm and those same arguments. A confirm that skips without acknowledge_skipped_searches writes nothing.

Do not ask the user to edit a .env file. Do not repeat the key or the email.
"""

FIRST_RUN_MAC_SPEECH = (
    "On the Mac at first-run, recommend Documents/Essay Bot for Word and zip copies. "
    "The person may confirm that folder, name another path, set this up later, or decline. "
    "Later or decline without a path is chat-only: do not invent a Mac copy folder and do not set "
    "ESSAY_WRITER_MAC_DIR. Do not say the Mac folder is ready. "
    "Both file-work picks call essay_writer.first_run.choose_mac_handoff. "
    "When they confirm Documents/Essay Bot, call choose_mac_handoff with ok, "
    "or run essay-writer --remember-mac-dir ok. "
    "That creates Documents/Essay Bot on the friend's Mac and remembers the path. "
    "Stage 1 Confirm on a sequence creates Documents/Essay Bot/<module>/, "
    "Documents/Essay Bot/<module>/shared/, and Documents/Essay Bot/<module>/<essay_id>/ "
    "for that run's Word and zip copies. "
    "When they name another path, call choose_mac_handoff with that folder, "
    "or run essay-writer --remember-mac-dir with that folder. "
    "That creates the named folder on the Mac and remembers it. "
    "Later or skip does not create a folder. "
    f'Show this card: "{MAC_FOUR_WAY_CARD}" '
    "Do that before essay-writer --copy-to-mac. "
    "essay.setup still refuses unnamed Documents as the cloud save folder. Documents is not the cloud computer."
)

ORDINARY_SETUP_SPEECH = (
    "Ordinary setup collects the Consensus key, the Consensus plan, and the Unpaywall email "
    "on the secret card, then passes them to essay.setup.\n\n"
    + CARD_RULES
)


SETUP_PROMPT = f"""Set up essay writer. You talk to the user. File work does not own this chat.

Nothing is cloned.

Call essay.setup with confirmPhase draft and no path arguments. Show that result. After an explicit yes, call essay.setup with confirmPhase confirm and the same arguments.

That creates /workspace/Essay-writer/app and /workspace/Essay-writer/KB1, and the folders later steps read under the app: Essay-writer, uploads, and unassigned.

Save on the cloud computer, or on a folder the user names on this computer. Do not use a path the user did not name. Do not fall back to Documents and call it the cloud computer.

Run grok version and include the result. Do not install grok, and do not install it on the Mac.

{FIRST_RUN_MAC_SPEECH}

{ORDINARY_SETUP_SPEECH}
A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present.

Do not write notes or sample files.

If a file-access prompt appears, wait until I allow it, then finish the setup.

When the folders exist, reply with the folder paths and the grok version line. Then stop.
"""

CURSOR_SETUP_PROMPT = f"""Set up essay writer. You talk to the user. File work does not own this chat.

Nothing is cloned.

Call essay.setup with confirmPhase draft and no path arguments. Show that result. After an explicit yes, and after that sign-in yes when the card was shown, call essay.setup with confirmPhase confirm and the same arguments.

That creates /workspace/Essay-writer/app and /workspace/Essay-writer/KB1, and the folders later steps read under the app: Essay-writer, uploads, and unassigned.

Save on the cloud computer, or on a folder the user names on this computer. Do not use a path the user did not name. Do not fall back to Documents and call it the cloud computer. The worker host is not a save folder.

Run agent --version and include the result. That is the Cursor CLI check. When agent is missing, first-run on the Grok Bot computer installs the Cursor CLI. This check only reports the version, and it never installs on the Mac. Do not install grok.

On the Grok Bot computer, run agent login while the person holds that desktop when they are not already logged in and CURSOR_API_KEY is not on that machine. Show this card before or during login: "I'll sign in to Cursor on my computer. Open my computer and take over. On that screen, choose Allow or Continue. If Google appears, pick the Google account for this Cursor account. Tell me when you're signed in." Tell them Open computer → Take over → I'm done. Use the same Cursor account as Grok Bot. Do not put a key or login URL in chat. Skip that card when agent status shows logged in or CURSOR_API_KEY is already on the machine. After login, run agent status. Wait for that yes before essay.setup confirm.

{FIRST_RUN_MAC_SPEECH}

{ORDINARY_SETUP_SPEECH}
A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present.

Do not write notes or sample files.

If a file-access prompt appears, wait until I allow it, then finish the setup.

When the folders exist, reply with the folder paths and the Cursor CLI version line. Then stop.
"""


def setup_prompt(shell: str | None = None) -> str:
    """Check text for the stored pick. Absent or Cursor uses the Cursor CLI prompt."""
    if parse_shell(shell) == SHELL_GROK_BUILD:
        return SETUP_PROMPT
    return CURSOR_SETUP_PROMPT


def grokbuild_binary() -> str | None:
    found = shutil.which("grok")
    if found:
        return found
    home = Path.home()
    for candidate in (
        home / ".grok" / "bin" / "grok",
        home / ".local" / "bin" / "grok",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def grokbuild_version(binary: str) -> str | None:
    try:
        completed = subprocess.run(
            [binary, "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else None


def cursor_cli_binary() -> str | None:
    found = shutil.which("agent")
    if found:
        return found
    home = Path.home()
    for candidate in (
        home / ".local" / "bin" / "agent",
        home / ".cursor" / "bin" / "agent",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def cursor_cli_version(binary: str) -> str | None:
    try:
        completed = subprocess.run(
            [binary, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0] if text else None


def _file_work_report(shell: str, where: str) -> dict[str, object]:
    """Version check for the stored pick. This door never installs either program."""
    if shell == SHELL_CURSOR:
        binary = cursor_cli_binary()
        return {
            "cursor_cli": {
                "installed": binary is not None,
                "path": binary,
                "version": cursor_cli_version(binary) if binary else None,
                "command": "agent --version",
                "worker_save_root": False,
                "ran_install": False,
            },
            "grokbuild": {"where": where, "ran_install": False},
        }
    binary = grokbuild_binary()
    return {
        "grokbuild": {
            "installed": binary is not None,
            "path": binary,
            "version": grokbuild_version(binary) if binary else None,
            "where": where,
            "ran_install": False,
        }
    }


def _secrets_path(record_path: Path) -> Path:
    return record_path.parent / "setup.secrets.json"


def read_setup_secret(name: str) -> str | None:
    """Local setup secret. Never returned from a door reply."""
    if os.environ.get("ESSAY_WRITER_ROOT"):
        return None

    record = essay_paths.saved_setup_path()
    if record is None:
        return None
    path = _secrets_path(record)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _mkdir(path: Path) -> str | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return str(exc)
    return None


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _internal_volume(path: Path) -> bool:
    return any(part.casefold() == "researchdrive" for part in path.parts)


def _save_where(app: Path, kb1: Path) -> str | None:

    if not essay_paths.CLOUD_WORKSPACE.is_dir():
        return "user-local"
    cloud = essay_paths.CLOUD_WORKSPACE.resolve()
    app_cloud = _under(app, cloud)
    kb1_cloud = _under(kb1, cloud)
    if app_cloud and kb1_cloud:
        return "grokbot-cloud-computer"
    if app_cloud or kb1_cloud:
        return None
    return "user-local"


def _check_path(path: Path) -> str | None:
    if _internal_volume(path):
        return (
            "That folder is not a named save path on this computer. "
            "Save on a folder you name on this computer, or on the cloud computer."
        )
    if not path.is_absolute():
        return "That path is not absolute. Name a full path, or omit both paths on the cloud computer."
    if path.exists() and not path.is_dir():
        return "That path is a file, so the folder was not created."
    if path.name.casefold() == "open":
        return "Name the save folder. The word open is not a folder."
    return None


def _door_dirs(app: Path, kb1: Path) -> list[Path]:
    return [app, app / "Essay-writer", app / "uploads", app / "unassigned", kb1]


def parse_consensus_plan(plan: object) -> tuple[str | None, str | None]:
    """Map a named plan onto ESSAY_WRITER_CONSENSUS_PAID. Omitted is unset."""
    if plan is None or (isinstance(plan, str) and not plan.strip()):
        return None, None
    if not isinstance(plan, str):
        return None, "Say whether the Consensus plan is Free or Pro."
    folded = plan.strip().casefold()
    if folded == "free":
        return "0", None
    if folded in {"pro", "teams", "deep", "enterprise"}:
        return "1", None
    return None, (
        "Say whether the Consensus plan is Free or Pro. "
        "Teams, Deep, and Enterprise use the same paid flag as Pro."
    )


def search_warning(has_key: bool, has_email: bool) -> str | None:
    """Name the searches that stay off. OpenAlex is unchanged."""
    if has_key and has_email:
        return None
    parts: list[str] = []
    if not has_key:
        parts.append("Consensus dig will not run, because no Consensus key was given.")
    if not has_email:
        parts.append("Unpaywall free PDF lookup will not run, because no Unpaywall email was given.")
    parts.append("OpenAlex still runs.")
    parts.append("Skip is saved only after this warning is confirmed.")
    return " ".join(parts)


def essay_setup(
    install_grokbuild: bool = False,
    app_path: str | None = None,
    kb1_path: str | None = None,
    confirmPhase: str | None = None,
    consensus_api_key: str | None = None,
    unpaywall_email: str | None = None,
    mid_office_shell: str | None = None,
    acknowledge_skipped_searches: bool = False,
    consensus_plan: str | None = None,
) -> dict[str, object]:
    """Draft shows the door tree and writes nothing. Confirm creates it.

    Omit the paths on the cloud computer. Name both paths to save on this
    computer. A Consensus key and an Unpaywall email are collected on the
    secret card and are not repeated in the reply. A skip writes nothing
    until acknowledge_skipped_searches is true on a matching draft and confirm.
    mid_office_shell is the one-time file-work pick: omit or Cursor for the
    default, or Grok Build when the user asks.
    """
    if install_grokbuild:
        return refuse(
            "setup",
            "The file-work program stays where it is already installed. "
            "This door does not install it, and it does not install it on the Mac. "
            "Call essay.setup without install_grokbuild.",
        )
    shell = resolve_setup_shell(mid_office_shell)
    if isinstance(shell, dict):
        return shell

    if app_path is None and kb1_path is None:
        recommended = recommended_paths()
        if recommended is None:
            return refuse(
                "setup",
                "This computer has no cloud workspace. "
                "Name both app_path and kb1_path to save on this computer. "
                "Documents is not used, and it is not labelled as the cloud computer.",
            )
        app, kb1 = recommended
    elif isinstance(app_path, str) and app_path.strip() and isinstance(kb1_path, str) and kb1_path.strip():
        app = Path(app_path).expanduser()
        kb1 = Path(kb1_path).expanduser()
    else:
        return refuse("setup", "Give both app_path and kb1_path, or omit both to use the cloud computer.")


    for path in (app, kb1):
        if essay_known_paths.repo_save_refused(path):
            return refuse("repo-not-save", "The code checkout is not a student save.", wrote=False)
        problem = _check_path(path)
        if problem:
            return refuse("setup", problem, wrote=False)
    where = _save_where(app, kb1)
    if where is None:
        return refuse(
            "setup",
            "Save both folders on the cloud computer, or both on this computer. "
            "A split between the two is refused.",
            wrote=False,
        )

    key = consensus_api_key.strip() if isinstance(consensus_api_key, str) else ""
    email = unpaywall_email.strip() if isinstance(unpaywall_email, str) else ""
    if email and "@" not in email:
        return refuse(
            "setup",
            "The Unpaywall email is not usable. Skip it, or give an email address. "
            "The value is not repeated here.",
            wrote=False,
        )
    paid, plan_error = parse_consensus_plan(consensus_plan)
    if plan_error:
        return refuse("setup", plan_error, wrote=False)
    if key and paid is None and confirmPhase == CONFIRM:
        return refuse(
            "setup",
            "Say whether the Consensus plan is Free or Pro before the key is saved. "
            "Teams, Deep, and Enterprise use the same paid flag as Pro. Nothing was written.",
            wrote=False,
            needs_consensus_plan=True,
        )
    warning = search_warning(bool(key), bool(email))
    skipped = [name for name, present in (("consensus", bool(key)), ("unpaywall", bool(email))) if not present]
    acked = acknowledge_skipped_searches is True
    if warning and confirmPhase == CONFIRM and not acked:
        return refuse(
            "setup",
            "Skip is not saved until the warning is confirmed. Nothing was written.",
            wrote=False,
            search_warning=warning,
            skipped_searches=skipped,
        )

    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    payload = {
        "action": "setup",
        "app": str(app),
        "kb1": str(kb1),
        "where": where,
        "consensus_key": bool(key),
        "unpaywall_email": bool(email),
        "consensus_paid": paid or "",
        "acknowledge_skipped_searches": acked if warning else False,
        "mid_office_shell": shell,
    }
    fingerprint = payload
    body: dict[str, object] = {
        "ok": True,
        "app": str(app),
        "app_path": str(app),
        "kb1": str(kb1),
        "door": ["Essay-writer", "uploads", "unassigned"],
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "wrote_notes": False,
        "where": where,
        "consensus_key": bool(key),
        "unpaywall_email": bool(email),
        "consensus_paid": paid,
        "mid_office_shell": shell,
        "grokbuild": {"where": where, "ran_install": False},
    }
    if warning:
        body["search_warning"] = warning
        body["skipped_searches"] = skipped
    if key and paid is None:
        body["needs_consensus_plan"] = True
    from essay_writer.dig import consensus_api_key as stored_consensus_key
    from essay_writer.dig import consensus_paid_flag, consensus_status_for

    preview = consensus_status_for(stored_consensus_key() is not None or bool(key))
    body["consensus"] = {
        "switch": preview["switch"],
        "enabled": preview["enabled"],
        "key_present": preview["key_present"],
        "remind": preview["remind"],
        "paid": paid if paid else consensus_paid_flag(),
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft("setup", TOOL, payload, fingerprint)
        if preview["enabled"]:
            consensus_line = " Consensus is on for essay.dig."
        else:
            consensus_line = " Consensus stays off for essay.dig."
        extra = ""
        if key and paid is None:
            extra += (
                " Say whether the Consensus plan is Free or Pro before the key is saved."
                " Teams, Deep, and Enterprise use the same paid flag as Pro."
            )
        if warning and not acked:
            extra += " Show search_warning. The skip is not kept until that warning is confirmed."
        body["next"] = (
            "Nothing has been written. Say yes to create these folders. "
            "A Consensus key and an Unpaywall email are not repeated."
            + consensus_line
            + extra
        )
        return speak(body)
    ready = confirm_ready("setup", TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["wrote"] = False
        return ready

    created: list[Path] = []

    def ensure(path: Path) -> str | None:
        existed = path.exists()
        error = _mkdir(path)
        if error:
            return error
        if not existed:
            created.append(path)
        return None

    def rollback() -> None:
        for path in reversed(created):
            try:
                path.rmdir()
            except OSError:
                return

    for path in _door_dirs(app, kb1):
        error = ensure(path)
        if error:
            rollback()
            return refuse(
                "setup",
                "Could not create the folders. Allow file access, then call essay.setup again.",
                app=str(app),
                kb1=str(kb1),
                wrote=False,
            )

    record = {
        "app_path": str(app.resolve()),
        "app": str(app.resolve()),
        "kb1": str(kb1.resolve()),
        "grokbuild": "grok",
        "where": where,
        "mid_office_shell": shell,
        "consensus_key": bool(key),
        "unpaywall_email": bool(email),
    }
    record_path = app.parent / "setup.json"
    if record_requests_debug(record_path):
        record["debug"] = True
    temporary = record_path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, record_path)
    except OSError as exc:
        rollback()
        return refuse("setup", f"Folders were not kept because the setup record was not written: {exc}", wrote=False)

    if key or email:
        secrets: dict[str, str] = {}
        if key:
            secrets["CONSENSUS_API_KEY"] = key
            secrets["ESSAY_WRITER_CONSENSUS_PAID"] = paid or "0"
        if email:
            secrets["ESSAY_WRITER_UNPAYWALL_EMAIL"] = email
        secret_path = _secrets_path(record_path)
        try:
            secret_path.write_text(json.dumps(secrets, indent=2) + "\n", encoding="utf-8")
            os.chmod(secret_path, 0o600)
        except OSError as exc:
            return refuse(
                "setup",
                f"The door tree exists but the optional key was not stored: {exc}",
                wrote=False,
            )

    body["app"] = str(app.resolve())
    body["kb1"] = str(kb1.resolve())
    body["setup"] = str(record_path.resolve())
    body["wrote"] = True
    body["stored"] = True
    body.update(_file_work_report(shell, where))
    body["digest"] = ready["digest"]
    return speak(body)
