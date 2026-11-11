"""Install and update path: unpack a release zip, then install it pinned.

The upload hash is optional: verify it when a pin is available (explicit,
sidecar, or SHA256SUMS), and report the zip as unverified when it is not. The
project install always runs the hash-pinned runtime requirements first. The
Cursor CLI installer is consent-gated, then hash-pinned before anything runs.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from essay_writer import first_run_host, first_run_mac
from essay_writer import paths as essay_paths
from essay_writer.build_office import RESIDUALS
from essay_writer.first_run_common import (
    Enable,
    PipRunner,
    _clone_url,
    _fail,
    _internal_volume,
    _under,
    package_root,
    prompt_path,
)

INSTALL_DIRNAME = "essay-writer-install"
RUNTIME_REQUIREMENTS = "requirements-runtime.txt"
# Cursor CLI install. Consent (--install-cursor / env) authorises the download
# only. The URL is downloaded to a file and hashed; nothing runs until the
# operator also supplies the expected SHA-256 (--cursor-sha256 / env). A match
# runs that file with a fixed argv. It is never piped into a shell.
CURSOR_AGENT_INSTALL_URL = "https://cursor.com/install"
CURSOR_INSTALL_CONSENT_ENV = "ESSAY_WRITER_ALLOW_CURSOR_INSTALL"
CURSOR_INSTALL_SHA256_ENV = "ESSAY_WRITER_CURSOR_INSTALL_SHA256"
CURSOR_INSTALL_NEEDS_CONSENT = "cursor-install-needs-consent"
CURSOR_INSTALL_NEEDS_HASH = "cursor-install-needs-hash"
CURSOR_INSTALL_HASH_MISMATCH = "cursor-install-hash-mismatch"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
CURSOR_AGENT_MANUAL_INSTALL = (
    f"curl -fsS {CURSOR_AGENT_INSTALL_URL} -o cursor-agent-install.sh\n"
    "shasum -a 256 cursor-agent-install.sh  # Linux: sha256sum cursor-agent-install.sh\n"
    "bash cursor-agent-install.sh"
)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _member_target(dest: Path, name: str) -> Path:
    if not name or "\x00" in name:
        raise ValueError(name or "empty zip member")
    pure = Path(name.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(name)
    target = (dest / pure).resolve()
    if not _under(target, dest):
        raise ValueError(name)
    return target


def _safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    planned: list[tuple[zipfile.ZipInfo, Path]] = []
    root = dest.resolve()
    for info in archive.infolist():
        filename = info.filename
        if not filename or filename.endswith("/"):
            continue
        if _is_symlink(info):
            raise ValueError(filename)
        planned.append((info, _member_target(root, filename)))
    for info, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))


def _project_root(dest: Path) -> Path | None:
    matches = [path.parent for path in dest.rglob("pyproject.toml")]
    if (dest / "pyproject.toml").is_file() and dest not in matches:
        matches.append(dest)
    named = []
    for root in matches:
        try:
            text = (root / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            continue
        if 'name = "essay-writer"' in text or "name = 'essay-writer'" in text:
            named.append(root)
    pool = named or matches
    if not pool:
        return None
    pool.sort(key=lambda path: len(path.resolve().relative_to(dest.resolve()).parts))
    return pool[0]


def _saved_app_folder() -> Path | None:
    """App folder named on the setup record later tools read."""
    saved = essay_paths.load_saved_setup()
    if not isinstance(saved, dict):
        return None
    raw = saved.get("app_path") or saved.get("app")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or text.casefold() == "open":
        return None
    return Path(text).expanduser()


def _blocked_dest(dest: Path) -> str | None:
    if _internal_volume(dest):
        return "That folder is not an install path on this computer. Name a folder on this computer, or use the cloud computer."
    save_tree = "That folder is the save tree. Install the copy beside it, not inside it."
    if (dest / "setup.json").is_file() and (dest / "app").is_dir():
        return save_tree
    app = _saved_app_folder()
    if app is not None:
        try:
            dest_resolved = dest.resolve()
            app_resolved = app.resolve()
        except OSError:
            dest_resolved = dest
            app_resolved = app
        inside = False
        try:
            dest_resolved.relative_to(app_resolved)
            inside = True
        except ValueError:
            inside = False
        beside = dest_resolved == app_resolved.parent and (app_resolved.parent / "setup.json").is_file()
        if inside or beside:
            return save_tree
    if dest.exists() and not dest.is_dir():
        return "That install path is a file."
    return None


def install_folder(dest: Path | None = None) -> Path | None:
    """Cloud install folder. A named dest wins. Documents is not a fallback."""
    if dest is not None:
        return Path(dest).expanduser()
    cloud = essay_paths.CLOUD_WORKSPACE
    if cloud.is_dir():
        return cloud / INSTALL_DIRNAME
    return None


def _run_pip(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 1, "stdout": "", "stderr": str(exc)}
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def _install_commands() -> list[list[str]]:
    """The only install pair for one uploaded copy.

    The hash-pinned runtime requirements install first, then the project with
    --no-deps. A copy without requirements-runtime.txt is refused before this
    runs, so there is no unpinned ``pip install -e .`` fallback.
    """
    return [
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "-r",
            RUNTIME_REQUIREMENTS,
        ],
        [sys.executable, "-m", "pip", "install", "--no-deps", "-e", "."],
    ]


def _file_sha256(path: Path) -> str:
    """SHA-256 of a file, read in chunks so a large zip stays off the heap."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_has_runtime_requirements(path: Path) -> bool:
    """True when the zip carries requirements-runtime.txt at its project root.

    An unreadable zip returns True so the extractor reports the bad archive
    instead of this check masking it.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            return any(
                name == RUNTIME_REQUIREMENTS or name.endswith("/" + RUNTIME_REQUIREMENTS)
                for name in archive.namelist()
            )
    except (OSError, zipfile.BadZipFile):
        return True


def _expected_upload_sha256(value: str | None = None) -> str | None:
    """A 64-character hex pin for the uploaded zip, or None. An invalid pin is not a pin."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    return normalized if _SHA256_HEX.fullmatch(normalized) else None


def _upload_checksum(source: Path, explicit: str | None) -> tuple[str | None, str | None]:
    """Expected SHA-256 and where it came from, for an uploaded zip.

    The explicit --upload-sha256 wins. Otherwise a sibling ``<zip>.sha256`` file
    or a ``SHA256SUMS`` file beside the zip may carry the expected value.
    ``(None, None)`` means no checksum is available: the caller proceeds and
    reports the zip as unverified. A value that is present but unusable raises
    ValueError so a broken checksum file is loud instead of silently skipped.
    """
    if isinstance(explicit, str) and explicit.strip():
        pinned = _expected_upload_sha256(explicit)
        if pinned is None:
            raise ValueError("--upload-sha256 needs a 64-character hex SHA-256")
        return pinned, "--upload-sha256"
    sidecar = source.with_name(source.name + ".sha256")
    if sidecar.is_file():
        try:
            content = sidecar.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(f"The checksum file {sidecar.name} was not read: {exc}") from exc
        token = content.split()[0] if content else ""
        if _SHA256_HEX.fullmatch(token.casefold()) is None:
            raise ValueError(f"{sidecar.name} is not a usable SHA-256 file.")
        return token.casefold(), sidecar.name
    sums = source.parent / "SHA256SUMS"
    if sums.is_file():
        try:
            lines = sums.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ValueError(f"The checksum file SHA256SUMS was not read: {exc}") from exc
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            candidate, name = parts[0].casefold(), parts[1].strip()
            if name.startswith("*"):
                name = name[1:]
            if _SHA256_HEX.fullmatch(candidate) and name == source.name:
                return candidate, f"SHA256SUMS ({source.name})"
    return None, None


def _ensure_prompt(root: Path) -> bool:
    target = root / "FIRST-RUN.txt"
    if target.is_file():
        return True
    source = prompt_path()
    if not source.is_file() or source.resolve() == target.resolve():
        return False
    shutil.copyfile(source, target)
    return True


def cursor_install_consent(allow: bool | None = None) -> bool:
    """Explicit consent for the Cursor CLI installer. The env value is an opt-in."""
    if allow is not None:
        return allow is True
    value = os.environ.get(CURSOR_INSTALL_CONSENT_ENV, "")
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _download_cursor_installer() -> dict[str, Any]:
    """Download the installer to a temp file with a fixed argv. No shell, no execution."""
    curl = shutil.which("curl")
    if not curl:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "curl is not on PATH, so the installer was not downloaded",
            "reason": "cursor-install-curl-missing",
            "url": CURSOR_AGENT_INSTALL_URL,
            "sha256": None,
        }
    folder = Path(tempfile.mkdtemp(prefix="essay-writer-cursor-"))
    target = folder / "cursor-agent-install.sh"
    try:
        completed = subprocess.run(
            [
                curl,
                "-fsS",
                "--proto",
                "=https",
                "--max-time",
                "60",
                CURSOR_AGENT_INSTALL_URL,
                "-o",
                str(target),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"download-failed: {exc}",
            "reason": "cursor-install-download-failed",
            "url": CURSOR_AGENT_INSTALL_URL,
            "sha256": None,
        }
    if completed.returncode != 0 or not target.is_file():
        return {
            "returncode": 1,
            "stdout": (completed.stdout or "")[-500:],
            "stderr": (completed.stderr or "")[-500:] or "download-failed",
            "reason": "cursor-install-download-failed",
            "url": CURSOR_AGENT_INSTALL_URL,
            "sha256": None,
        }
    try:
        payload = target.read_bytes()
        target.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError as exc:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"download-failed: {exc}",
            "reason": "cursor-install-download-failed",
            "url": CURSOR_AGENT_INSTALL_URL,
            "sha256": None,
        }
    return {
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "url": CURSOR_AGENT_INSTALL_URL,
        "path": str(target),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _expected_cursor_sha256(value: str | None = None) -> str | None:
    """A 64-character hex pin, or None. An invalid pin is not a pin.

    The explicit value (--cursor-sha256) wins over the env fallback. A value
    that is not 64 hex characters is treated as no pin, so execution still
    waits for an explicit hash instead of trusting the download.
    """
    candidate = value if value is not None else os.environ.get(CURSOR_INSTALL_SHA256_ENV)
    if not isinstance(candidate, str):
        return None
    normalized = candidate.strip().casefold()
    return normalized if _SHA256_HEX.fullmatch(normalized) else None


def _run_cursor_installer(expected_sha256: str | None = None) -> dict[str, Any]:
    """Download the installer to a file, report its SHA-256, run it only on a match.

    Consent authorises the download; execution also needs an expected SHA-256
    (--cursor-sha256 or ESSAY_WRITER_CURSOR_INSTALL_SHA256). Without a pin the
    file is left on disk and nothing runs. Never pipes the remote payload into
    a shell and never uses bash -lc.
    """
    download = _download_cursor_installer()
    if download.get("returncode") != 0:
        return download
    script = Path(str(download["path"]))
    digest = str(download["sha256"])
    pinned = _expected_cursor_sha256(expected_sha256)
    if pinned is None:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "nothing was executed: execution needs an expected SHA-256",
            "reason": CURSOR_INSTALL_NEEDS_HASH,
            "url": CURSOR_AGENT_INSTALL_URL,
            "path": str(script),
            "sha256": digest,
            "bytes": download.get("bytes"),
            "executed": False,
            "instruction": (
                "The installer was downloaded and hashed but not run. Check that hash, "
                f"then rerun setup with --cursor-sha256 {digest} "
                f"(or set {CURSOR_INSTALL_SHA256_ENV}={digest}) to run this exact file."
            ),
        }
    if pinned != digest:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "downloaded installer did not match the expected SHA-256",
            "reason": CURSOR_INSTALL_HASH_MISMATCH,
            "url": CURSOR_AGENT_INSTALL_URL,
            "path": str(script),
            "sha256": digest,
            "bytes": download.get("bytes"),
            "expected_sha256": pinned,
            "executed": False,
            "instruction": (
                "The downloaded file did not match the expected SHA-256, so nothing ran. "
                "Rerun the download later or install manually; do not run this file."
            ),
        }
    shell = shutil.which("bash") or "/bin/bash"
    try:
        completed = subprocess.run(
            [shell, str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": str(exc),
            "reason": "cursor-install-failed",
            "url": CURSOR_AGENT_INSTALL_URL,
            "path": str(script),
            "sha256": digest,
            "bytes": download.get("bytes"),
            "expected_sha256": pinned,
            "executed": False,
        }
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-500:],
        "stderr": (completed.stderr or "")[-500:],
        "url": CURSOR_AGENT_INSTALL_URL,
        "path": str(script),
        "sha256": digest,
        "bytes": download.get("bytes"),
        "expected_sha256": pinned,
        "executed": True,
        "command": f"{shell} {script}",
    }


def _install_report(report: dict[str, Any]) -> dict[str, Any]:
    """Installer facts copied into the setup report. The hash is always kept."""
    return {
        "returncode": report.get("returncode"),
        "command": report.get("command"),
        "url": report.get("url"),
        "path": report.get("path"),
        "sha256": report.get("sha256"),
        "bytes": report.get("bytes"),
        "expected_sha256": report.get("expected_sha256"),
        "executed": report.get("executed"),
        "instruction": report.get("instruction"),
        "reason": report.get("reason"),
        "stdout": report.get("stdout"),
        "stderr": report.get("stderr"),
    }


def ensure_cursor_agent(
    installer: Callable[[], dict[str, Any]] | None = None,
    *,
    allow_install: bool | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Install the Cursor agent CLI when it is missing. Never on the Mac. Never grok.

    Nothing is downloaded without explicit consent. Consent authorises the
    download only; execution also needs an expected SHA-256. Without consent
    the report says cursor-install-needs-consent. With consent and no pin it
    says cursor-install-needs-hash and reports the downloaded file's hash.
    """
    from essay_writer.setup import cursor_cli_binary, cursor_cli_version

    binary = cursor_cli_binary()
    if binary:
        version = cursor_cli_version(binary)
        return {
            "ok": bool(version),
            "installed": True,
            "ran_install": False,
            "path": binary,
            "version": version,
            "reason": None if version else "agent-version-missing",
        }
    if first_run_mac._on_mac():
        return {
            "ok": False,
            "installed": False,
            "ran_install": False,
            "path": None,
            "version": None,
            "reason": "mac-no-install",
        }
    if not cursor_install_consent(allow_install):
        return {
            "ok": False,
            "installed": False,
            "ran_install": False,
            "path": None,
            "version": None,
            "reason": CURSOR_INSTALL_NEEDS_CONSENT,
            "consent_required": True,
            "downloaded": False,
            "manual_install": CURSOR_AGENT_MANUAL_INSTALL,
            "residual": (
                "No Cursor CLI install was attempted and nothing was downloaded. "
                "Ask before installing it, then rerun setup with --install-cursor "
                f"or set {CURSOR_INSTALL_CONSENT_ENV}=1. Consent only authorises the "
                "download; that rerun also reports the file's SHA-256, and a second "
                "rerun with --cursor-sha256 is what runs it."
            ),
        }
    if installer is not None:
        report = installer()
    else:
        report = _run_cursor_installer(expected_sha256)
    if not isinstance(report, dict):
        report = {"returncode": 1}
    binary = cursor_cli_binary()
    version = cursor_cli_version(binary) if binary else None
    installer_reason = report.get("reason")
    if not binary:
        if installer_reason in {CURSOR_INSTALL_NEEDS_HASH, CURSOR_INSTALL_HASH_MISMATCH}:
            reason = str(installer_reason)
        else:
            reason = "agent-cli-missing"
    elif not version:
        reason = "agent-version-missing"
    elif report.get("returncode") != 0:
        reason = "agent-install-failed"
    else:
        reason = None
    return {
        "ok": reason is None,
        "installed": binary is not None,
        "ran_install": True,
        "path": binary,
        "version": version,
        "reason": reason,
        "installer": _install_report(report),
    }


def install_uploaded_copy(
    upload: Path | None = None,
    *,
    dest: Path | None = None,
    reviewer: bool = True,
    pip_runner: PipRunner | None = None,
    attach: bool = True,
    enable: Enable | None = None,
    cursor_installer: Callable[[], dict[str, Any]] | None = None,
    allow_cursor_install: bool | None = None,
    cursor_sha256: str | None = None,
    upload_sha256: str | None = None,
    path_exposer: Callable[[], str | None] | None = None,
    include_user: bool = True,
) -> dict[str, Any]:
    """Unpack an uploaded zip, then install the hash-pinned project.

    The zip's SHA-256 is verified when an expected value is available: the
    explicit `upload_sha256`, a sibling ``<zip>.sha256`` file, or a ``SHA256SUMS``
    file beside the zip. A mismatch refuses before anything is written. With no
    checksum the zip is trusted operator input: it installs, and the result says
    `upload_verified` is false so the caller can report that honestly.
    The copy must carry requirements-runtime.txt: the install runs
    `--require-hashes -r requirements-runtime.txt` then `--no-deps -e .`, and a
    copy without that file is refused rather than falling back to an unpinned
    install. The Cursor CLI install runs only with consent (allow_cursor_install
    or ESSAY_WRITER_ALLOW_CURSOR_INSTALL=1); consent downloads the installer and
    reports its hash, and execution also needs cursor_sha256. `path_exposer` and
    `include_user` are injection points: production leaves them at the real
    PATH writer and user config, while tests pass fakes so they never write the
    system PATH or the real home.
    """
    if isinstance(upload, str) and _clone_url(upload):
        return _fail("Nothing is cloned. Pass the uploaded zip, not a git URL.")
    unpacked = False
    upload_verified: bool | None = None
    upload_checksum_source: str | None = None
    upload_sha256_value: str | None = None
    if upload is None:
        root = package_root()
        if not (root / "pyproject.toml").is_file():
            return _fail("This folder has no project to install.")
    else:
        source = Path(upload).expanduser()
        if _clone_url(str(source)):
            return _fail("Nothing is cloned. Pass the uploaded zip, not a git URL.")
        if source.is_dir():
            found = _project_root(source)
            if found is None:
                return _fail("That folder does not contain the essay-writer project.", upload=str(source))
            root = found
        elif source.is_file():
            folder = install_folder(dest)
            if folder is None:
                return _fail(
                    "This computer has no cloud workspace. "
                    "Name dest to install on this computer. Documents is not used.",
                    upload=str(source),
                )
            blocked = _blocked_dest(folder)
            if blocked:
                return _fail(blocked, upload=str(source), dest=str(folder))
            try:
                pinned, checksum_source = _upload_checksum(source, upload_sha256)
            except ValueError as exc:
                return _fail(str(exc), upload=str(source), dest=str(folder))
            try:
                digest = _file_sha256(source)
            except OSError as exc:
                return _fail(
                    f"The upload was not read: {exc}",
                    upload=str(source),
                    dest=str(folder),
                )
            upload_sha256_value = digest
            if pinned is not None:
                if digest != pinned:
                    return _fail(
                        "The upload zip did not match its checksum. Nothing was unpacked.",
                        upload=str(source),
                        dest=str(folder),
                        expected_sha256=pinned,
                        actual_sha256=digest,
                        checksum_source=checksum_source,
                    )
                upload_verified = True
            else:
                upload_verified = False
            upload_checksum_source = checksum_source
            if not _zip_has_runtime_requirements(source):
                return _fail(
                    "That upload has no requirements-runtime.txt, so nothing was unpacked "
                    "or installed with unpinned dependencies. Use the release zip.",
                    upload=str(source),
                    dest=str(folder),
                    requirements_verified=False,
                )
            folder.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(source) as archive:
                    _safe_extract(archive, folder)
            except (OSError, zipfile.BadZipFile, ValueError) as exc:
                return _fail(f"The upload was not unpacked: {exc}", upload=str(source), dest=str(folder))
            found = _project_root(folder)
            if found is None:
                return _fail(
                    "That upload does not contain the essay-writer project.",
                    upload=str(source),
                    dest=str(folder),
                    unpacked=True,
                )
            root = found
            unpacked = True
        else:
            return _fail("That upload is not on disk.", upload=str(source))

    if not (root / RUNTIME_REQUIREMENTS).is_file():
        return _fail(
            "That copy has no requirements-runtime.txt, so nothing was installed "
            "with unpinned dependencies. Use the release zip.",
            root=str(root),
            unpacked=unpacked,
            requirements_verified=False,
        )

    prompt_present = _ensure_prompt(root)
    runner = pip_runner or _run_pip
    commands = _install_commands()
    pip_steps: list[dict[str, Any]] = []
    pip_body: dict[str, Any] = {}
    for index, command in enumerate(commands):
        report = runner(command, root)
        pip_body = {"command": command, "cwd": str(root), **report}
        pip_steps.append(pip_body)
        if report.get("returncode") != 0:
            message = (
                "The hash-pinned runtime install did not finish."
                if index == 0 and len(commands) > 1
                else "pip install -e . did not finish."
            )
            return _fail(
                message,
                unpacked=unpacked,
                root=str(root),
                pip=pip_body,
                pip_steps=pip_steps,
                requirements_verified=False,
                prompt_present=prompt_present,
            )
    exposer = path_exposer or first_run_host.expose_writer_on_path
    exposer()
    cursor_cli = ensure_cursor_agent(
        installer=cursor_installer,
        allow_install=allow_cursor_install,
        expected_sha256=cursor_sha256,
    )
    launch = first_run_host.mcp_launch_command()
    mcp = (
        first_run_host.attach_custom_mcp(root, reviewer=reviewer, include_user=include_user, enable=enable)
        if attach
        else None
    )
    build_mcp = (
        first_run_host.attach_build_mcp(root, reviewer=reviewer, include_user=include_user) if attach else None
    )
    unpack_parent = install_folder(dest) if unpacked else None
    health_check = install_self_check()
    if not health_check.get("ok"):
        return _fail(
            "essay.health did not pass after install.",
            unpacked=unpacked,
            root=str(root),
            pip=pip_body,
            pip_steps=pip_steps,
            prompt_present=prompt_present,
            health_check=health_check,
        )
    payload: dict[str, Any] = {
        "ok": True,
        "installed": True,
        "unpacked": unpacked,
        "root": str(root),
        "code_install_folder": str(root),
        "unpack_parent": str(unpack_parent) if unpack_parent is not None else None,
        "grok_config_home": first_run_host.grok_config_home(),
        "pip": pip_body,
        "pip_steps": pip_steps,
        "requirements_verified": bool(
            len(commands) > 1 and pip_steps and pip_steps[0]["returncode"] == 0
        ),
        "upload_verified": upload_verified,
        "upload_checksum": upload_checksum_source,
        "upload_sha256": upload_sha256_value,
        "prompt_present": prompt_present,
        "writer_command": launch,
        "cursor_cli": cursor_cli,
        "mcp": mcp,
        "build_mcp": build_mcp,
        "health_check": health_check,
        "install_residual_id": "install-root",
        "install_residual": RESIDUALS["install-root"],
    }
    if upload_verified is False:
        payload["upload_note"] = (
            "The zip was not checksum-verified. It is trusted operator input. "
            "Pass --upload-sha256, or place a matching <zip>.sha256 or SHA256SUMS "
            "file beside the zip, to verify it."
        )
    return first_run_mac.attach_friend_upgrade_fo_card(payload, root=root)


def install_self_check() -> dict[str, Any]:
    """Read-only essay.health after install or attach. Cursor and Grok Build share this."""
    from essay_writer.health import essay_health

    health = essay_health()
    doors = health.get("doors")
    tool_count = len(doors) if isinstance(doors, list) else 0
    ok = bool(health.get("ok") and health.get("alive") and tool_count > 0)
    return {
        "ok": ok,
        "tool": "essay.health",
        "alive": health.get("alive"),
        "tool_count": tool_count,
    }
