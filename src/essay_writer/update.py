"""Update an installed copy from the public GitHub release.

First-run unpacks a new tree and attaches MCP. This module upgrades the package
in the environment that is already installed: the setup record, the stored
keys, the remembered Mac folder, and the essays are not touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from essay_writer import __version__, safe_url

REPO = "4zhmv6zvj2-afk/grokbot-essay-writer"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
RELEASES_FEED = f"https://github.com/{REPO}/releases.atom"
RUNTIME_REQUIREMENTS = "requirements-runtime.txt"
API_TIMEOUT = 20.0
JSON_BYTES = 1024 * 1024
FEED_BYTES = 2 * 1024 * 1024
ARCHIVE_BYTES = 32 * 1024 * 1024
PIP_TIMEOUT = 600
_VERSION = re.compile(r"^v?(\d+(?:\.\d+)*)$")
_PLAIN_VERSION = re.compile(r"^v?(\d+\.\d+\.\d+)$")
_ASSET_HOSTS = frozenset(
    {
        "github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }
)


class UpdateError(RuntimeError):
    """A check failed before anything on disk changed."""


def version_tuple(text: object) -> tuple[int, ...] | None:
    """The numeric parts of a release tag. None when the tag is not a version."""
    if not isinstance(text, str):
        return None
    match = _VERSION.fullmatch(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _padded(parts: tuple[int, ...], width: int) -> tuple[int, ...]:
    return parts + (0,) * (width - len(parts))


def is_newer(latest: str, current: str) -> bool:
    """True when latest is a later release than current."""
    left = version_tuple(latest)
    right = version_tuple(current)
    if left is None or right is None:
        return False
    width = max(len(left), len(right))
    return _padded(left, width) > _padded(right, width)


def _get_json(url: str) -> dict[str, Any]:
    try:
        with safe_url.open_url(
            url,
            timeout=API_TIMEOUT,
            max_bytes=JSON_BYTES,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "essay-writer",
            },
        ) as response:
            body = response.read()
            status = int(getattr(response, "status", 200) or 200)
    except (safe_url.Refused, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"the release check did not answer: {exc}") from None
    if status != 200:
        raise UpdateError(f"the release check returned HTTP {status}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UpdateError("the release check did not return JSON") from None
    if not isinstance(payload, dict):
        raise UpdateError("the release check did not return an object")
    return payload


def _get_text(url: str) -> str:
    """GET one public text page, such as the releases feed."""
    try:
        with safe_url.open_url(
            url,
            timeout=API_TIMEOUT,
            max_bytes=FEED_BYTES,
            headers={"User-Agent": "essay-writer"},
        ) as response:
            body = response.read()
            status = int(getattr(response, "status", 200) or 200)
    except (safe_url.Refused, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"the release feed did not answer: {exc}") from None
    if status != 200:
        raise UpdateError(f"the release feed returned HTTP {status}")
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        raise UpdateError("the release feed was not text") from None


def _local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _version_from_release_href(href: str) -> str | None:
    """A plain X.Y.Z tag when it is the last segment of a releases/tag path."""
    try:
        path = urllib.parse.urlsplit(href).path.rstrip("/")
    except ValueError:
        return None
    marker = "/releases/tag/"
    if marker not in path:
        return None
    tag = path.rsplit(marker, 1)[-1]
    if not tag or "/" in tag:
        return None
    match = _PLAIN_VERSION.fullmatch(tag)
    if match is None:
        return None
    return match.group(1)


def _feed_tag(text: str) -> str | None:
    """The version in the first Atom entry's alternate link. Notes are ignored."""
    if len(text) > FEED_BYTES or re.search(r"<!DOCTYPE|<!ENTITY", text, re.IGNORECASE):
        return None
    try:
        # DTD and entity declarations are rejected above. The feed is also size-capped.
        root = ElementTree.fromstring(text)  # noqa: S314
    except ElementTree.ParseError:
        return None
    entry = next((child for child in root if _local_name(child.tag) == "entry"), None)
    if entry is None:
        return None
    for link in entry:
        if _local_name(link.tag) != "link":
            continue
        if link.attrib.get("rel", "alternate") != "alternate":
            continue
        href = link.attrib.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        return _version_from_release_href(href.strip())
    return None


def _release_from_tag(latest: str) -> dict[str, Any]:
    """A release record built from the tag when only the feed is reachable."""
    base = f"https://github.com/{REPO}/releases/download/v{latest}"
    return {
        "tag_name": f"v{latest}",
        "html_url": f"https://github.com/{REPO}/releases/tag/v{latest}",
        "assets": [
            {"name": _archive_name(latest), "url": f"{base}/{_archive_name(latest)}"},
            {"name": "SHA256SUMS", "url": f"{base}/SHA256SUMS"},
        ],
    }


def _release_assets(release: dict[str, Any]) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for asset in release.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url") or asset.get("url")
        if isinstance(name, str) and isinstance(url, str):
            assets.append({"name": name, "url": url})
    return assets


def check_update(
    fetcher: Callable[[str], dict[str, Any]] | None = None,
    feed_fetcher: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Name the newest release and whether this copy is behind it. Reads only.

    The REST API is the first source. When it is blocked or rate-limited, the
    public releases feed gives the tag, and the asset URLs are built from it.
    """
    get = fetcher or _get_json
    try:
        release = get(LATEST_API)
    except UpdateError as exc:
        feed = feed_fetcher or _get_text
        try:
            latest_from_feed = _feed_tag(feed(RELEASES_FEED))
        except UpdateError:
            latest_from_feed = None
        if latest_from_feed is None:
            return {
                "ok": False,
                "current": __version__,
                "reason": str(exc),
                "url": RELEASES_PAGE,
            }
        release = _release_from_tag(latest_from_feed)
    latest = version_tuple(release.get("tag_name"))
    if latest is None:
        return {
            "ok": False,
            "current": __version__,
            "reason": "the release tag was not a version",
            "url": RELEASES_PAGE,
        }
    latest_text = ".".join(str(part) for part in latest)
    html_url = release.get("html_url")
    return {
        "ok": True,
        "current": __version__,
        "latest": latest_text,
        "update_available": is_newer(latest_text, __version__),
        "url": html_url if isinstance(html_url, str) and html_url else RELEASES_PAGE,
        "assets": _release_assets(release),
    }


def is_developer_checkout() -> bool:
    """True when this package runs from a git checkout.

    A friend install is editable too, so editability alone is not the signal.
    The release archive has no .git folder; a developer checkout does.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return True
        if parent.name == "site-packages" or parent.name == "dist-packages":
            return False
    return False


def _archive_name(latest: str) -> str:
    return f"essay_writer-{latest}.tar.gz"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sum_for(text: str, name: str) -> str | None:
    """The SHA-256 for name. Conflicting or non-hex entries are refused."""
    found: str | None = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1].lstrip("*").strip() != name:
            continue
        digest = parts[0].casefold()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise UpdateError(f"SHA256SUMS has an unusable entry for {name}")
        if found is not None and found != digest:
            raise UpdateError(f"SHA256SUMS has conflicting entries for {name}")
        found = digest
    return found


def _checked_asset_url(url: str) -> str:
    """An https asset URL on a GitHub release host, or an UpdateError naming the host."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        raise UpdateError("the release asset host is not allowed: missing host") from None
    host = (parts.hostname or "").casefold().rstrip(".")
    if parts.scheme != "https" or host not in _ASSET_HOSTS:
        raise UpdateError(f"the release asset host is not allowed: {host or 'missing host'}")
    return url


def _download(url: str, path: Path) -> None:
    allowed = _checked_asset_url(url)
    try:
        with safe_url.open_url(
            allowed,
            timeout=API_TIMEOUT,
            max_bytes=ARCHIVE_BYTES,
            headers={"User-Agent": "essay-writer"},
        ) as response:
            body = response.read()
            status = int(getattr(response, "status", 200) or 200)
    except (safe_url.Refused, urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"the release download did not answer: {exc}") from None
    if status != 200:
        raise UpdateError(f"the release download returned HTTP {status}")
    path.write_bytes(body)


def _safe_extract(archive: tarfile.TarFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in archive.getmembers():
        if member.issym() or member.islnk():
            raise UpdateError("the release archive carries a link, not a plain file")
        target = (dest / member.name).resolve()
        if target != dest_resolved and dest_resolved not in target.parents:
            raise UpdateError("the release archive has a path outside its folder")
    archive.extractall(dest, filter="data")  # noqa: S202 - members are checked above


def _project_root(dest: Path) -> Path | None:
    for candidate in [dest, *dest.iterdir()]:
        if not candidate.is_dir() or not (candidate / "pyproject.toml").is_file():
            continue
        try:
            text = (candidate / "pyproject.toml").read_text(encoding="utf-8")
        except OSError:
            continue
        if 'name = "essay-writer"' in text or "name = 'essay-writer'" in text:
            return candidate
    return None


def _lock_path() -> Path:
    override = os.environ.get("ESSAY_WRITER_UPDATE_LOCK", "").strip()
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "essay-writer-update.lock"


def _acquire_update_lock(handle: BinaryIO) -> None:
    """Take the process-wide lock, or say that another update is running."""
    if sys.platform == "win32":  # pragma: no cover - Windows file locking
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise UpdateError("another update is already running") from None
        return
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise UpdateError("another update is already running") from None


def _release_update_lock(handle: BinaryIO) -> None:
    if sys.platform == "win32":  # pragma: no cover - Windows file locking
        import msvcrt

        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        return
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def _update_lock() -> Iterator[None]:
    """One update installs at a time. The lock is released on every path."""
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    locked = False
    try:
        _acquire_update_lock(handle)
        locked = True
        yield
    finally:
        if locked:
            _release_update_lock(handle)
        handle.close()


def _pip(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=PIP_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": 1, "stdout": "", "stderr": str(exc)}
    return {
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-2000:],
        "stderr": (completed.stderr or "")[-2000:],
    }


def _health_report() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "essay_writer", "--health"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": str(exc)}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "essay.health did not return JSON"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "essay.health did not return an object"}
    return payload


def apply_update(
    force: bool = False,
    *,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
    downloader: Callable[[str, Path], None] | None = None,
    pip_runner: Callable[[list[str], Path], dict[str, Any]] | None = None,
    health_runner: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Install the newest release over this copy. Never touches the essay tree."""
    current = __version__
    check = check_update(fetcher)
    if check.get("ok") is not True:
        return {**check, "updated": False}
    if check.get("update_available") is not True:
        return {
            "ok": True,
            "updated": False,
            "current": current,
            "latest": check["latest"],
            "reason": "up-to-date",
            "url": check["url"],
        }
    if is_developer_checkout() and not force:
        return {
            "ok": False,
            "updated": False,
            "current": current,
            "latest": check["latest"],
            "reason": (
                "This is a source checkout. Run git pull, or pass --force to replace "
                "it with the release package."
            ),
            "url": check["url"],
        }
    latest = str(check["latest"])
    wanted = _archive_name(latest)
    assets = {asset["name"]: asset["url"] for asset in check.get("assets") or []}
    if wanted not in assets or "SHA256SUMS" not in assets:
        return {
            "ok": False,
            "updated": False,
            "current": current,
            "latest": latest,
            "reason": f"the release has no {wanted} or SHA256SUMS asset",
            "url": check["url"],
        }
    download = downloader or _download
    run_pip = pip_runner or _pip
    run_health = health_runner or _health_report
    with tempfile.TemporaryDirectory(prefix="essay-writer-update-") as temporary:
        folder = Path(temporary)
        archive = folder / wanted
        sums = folder / "SHA256SUMS"
        try:
            download(assets[wanted], archive)
            download(assets["SHA256SUMS"], sums)
            expected = _sum_for(sums.read_text(encoding="utf-8"), wanted)
        except (UpdateError, OSError, UnicodeDecodeError) as exc:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": str(exc),
                "url": check["url"],
            }
        if expected is None:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": f"SHA256SUMS does not list {wanted}",
                "url": check["url"],
            }
        if _sha256(archive) != expected:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": f"{wanted} did not match its SHA-256",
                "url": check["url"],
            }
        unpacked = folder / "unpacked"
        try:
            unpacked.mkdir()
            with tarfile.open(archive, "r:gz") as bundle:
                _safe_extract(bundle, unpacked)
        except (OSError, tarfile.TarError, UpdateError) as exc:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": f"the release archive did not unpack: {exc}",
                "url": check["url"],
            }
        root = _project_root(unpacked)
        if root is None:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": "the release archive has no essay-writer project",
                "url": check["url"],
            }
        commands = [
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--require-hashes",
                "-r",
                RUNTIME_REQUIREMENTS,
            ],
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--upgrade",
                str(root),
            ],
        ]
        steps: list[dict[str, Any]] = []
        try:
            with _update_lock():
                for index, command in enumerate(commands):
                    report = run_pip(command, root)
                    steps.append({"command": command, **report})
                    if report.get("returncode") != 0:
                        requirements_done = index > 0
                        reason = "the release install did not finish"
                        if requirements_done:
                            reason += (
                                ". The runtime dependencies were installed and were not rolled back."
                            )
                        body: dict[str, Any] = {
                            "ok": False,
                            "updated": False,
                            "current": current,
                            "latest": latest,
                            "reason": reason,
                            "pip": steps,
                            "url": check["url"],
                        }
                        if requirements_done:
                            body["environment_changed"] = True
                            body["rolled_back"] = False
                        return body
        except UpdateError as exc:
            return {
                "ok": False,
                "updated": False,
                "current": current,
                "latest": latest,
                "reason": str(exc),
                "url": check["url"],
            }
    health = run_health()
    installed = health.get("version") if isinstance(health, dict) else None
    if health.get("ok") is not True or installed != latest:
        return {
            "ok": False,
            "updated": False,
            "installed": True,
            "environment_changed": True,
            "rolled_back": False,
            "current": current,
            "latest": latest,
            "reason": (
                "essay.health did not report the new version. "
                "The new code is on disk but unverified, and the environment was not rolled back."
            ),
            "health": health,
            "url": check["url"],
        }
    return {
        "ok": True,
        "updated": True,
        "from": current,
        "to": latest,
        "pip": steps,
        "health": health,
        "restart_required": True,
        "url": check["url"],
    }
