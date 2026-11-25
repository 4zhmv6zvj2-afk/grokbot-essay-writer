"""Check the GitHub release and upgrade this copy in place.

The checks are hermetic: the release JSON, the archive, pip, and essay.health
are injected, so no test reaches GitHub or changes the environment.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from essay_writer import update

CURRENT = "1.2.4"
LATEST = "9.9.9"


def _release(tag: str = "v9.9.9", *, with_assets: bool = True) -> dict:
    assets = []
    if with_assets:
        assets = [
            {
                "name": f"essay_writer-{LATEST}.tar.gz",
                "browser_download_url": f"https://example.org/essay_writer-{LATEST}.tar.gz",
            },
            {
                "name": "SHA256SUMS",
                "browser_download_url": "https://example.org/SHA256SUMS",
            },
        ]
    return {"tag_name": tag, "html_url": "https://example.org/release", "assets": assets}


def _sdist_bytes(tmp_path: Path) -> bytes:
    root = tmp_path / f"essay_writer-{LATEST}"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    (root / "requirements-runtime.txt").write_text("", encoding="utf-8")
    archive = tmp_path / f"essay_writer-{LATEST}.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(root, arcname=root.name)
    return archive.read_bytes()


def _health_payload(version: str) -> dict:
    """An essay.health payload as the official door returns it."""
    return {
        "ok": True,
        "alive": True,
        "version": version,
        "doors": [{"id": "essay.health", "tool": "essay.health"}],
    }


def test_version_compare_reads_a_tag_and_ignores_noise():
    assert update.version_tuple("v1.2.5") == (1, 2, 5)
    assert update.version_tuple("1.2.5") == (1, 2, 5)
    assert update.version_tuple("release") is None
    assert update.is_newer("1.2.10", "1.2.9")
    assert update.is_newer("1.10.0", "1.9.9")
    assert not update.is_newer("1.2.4", "1.2.4")
    assert not update.is_newer("1.2.3", "1.2.4")


def test_check_update_names_the_newer_release(monkeypatch):
    monkeypatch.setattr(update, "__version__", CURRENT)
    body = update.check_update(lambda url: _release())
    assert body["ok"] is True
    assert body["current"] == CURRENT
    assert body["latest"] == LATEST
    assert body["update_available"] is True
    assert body["url"] == "https://example.org/release"
    assert {asset["name"] for asset in body["assets"]} == {
        f"essay_writer-{LATEST}.tar.gz",
        "SHA256SUMS",
    }


def test_check_update_reports_an_unreachable_release(monkeypatch):
    monkeypatch.setattr(update, "__version__", CURRENT)

    def refused(url):
        raise update.UpdateError("the release check returned HTTP 403")

    def feed_refused(url):
        raise update.UpdateError("the release feed returned HTTP 403")

    body = update.check_update(refused, feed_fetcher=feed_refused)
    assert body["ok"] is False
    assert "403" in body["reason"]
    assert body["url"] == update.RELEASES_PAGE


def test_check_update_keeps_the_current_copy(monkeypatch):
    monkeypatch.setattr(update, "__version__", LATEST)
    body = update.check_update(lambda url: _release(tag=f"v{LATEST}"))
    assert body["update_available"] is False


def test_feed_tag_reads_a_normal_atom_entry():
    feed = (
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
        "<title>v9.9.9</title>"
        '<link rel="alternate" type="text/html" '
        'href="https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/releases/tag/v9.9.9"/>'
        "</entry></feed>"
    )
    assert update._feed_tag(feed) == LATEST


def test_feed_tag_ignores_a_note_that_appears_before_the_link():
    feed = (
        "<feed><title>Also see releases/tag/v8.8.8</title><entry>"
        "<content>Ship notes mention releases/tag/v1.2.3 before the real link.</content>"
        '<link rel="alternate" '
        'href="https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/releases/tag/v1.2.12"/>'
        "</entry>"
        '<entry><link rel="alternate" '
        'href="https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/releases/tag/v9.9.9"/>'
        "</entry></feed>"
    )
    assert update._feed_tag(feed) == "1.2.12"


def test_feed_tag_rejects_a_prerelease_suffix():
    feed = (
        '<feed><entry><link rel="alternate" '
        'href="https://github.com/org/repo/releases/tag/v1.2.12-rc1"/>'
        "</entry></feed>"
    )
    assert update._feed_tag(feed) is None
    longer = (
        '<feed><entry><link rel="alternate" '
        'href="https://github.com/org/repo/releases/tag/v1.2.12/notes"/>'
        "</entry></feed>"
    )
    assert update._feed_tag(longer) is None


def test_feed_tag_rejects_malformed_or_missing_xml():
    assert update._feed_tag("") is None
    assert update._feed_tag("<feed>") is None
    assert update._feed_tag("not xml") is None
    assert update._feed_tag("<feed><entry><title>v9.9.9</title></entry></feed>") is None
    missing_href = '<feed><entry><link rel="alternate"/></entry></feed>'
    assert update._feed_tag(missing_href) is None
    declared = '<!DOCTYPE feed [<!ENTITY x "v9.9.9">]><feed>&x;</feed>'
    assert update._feed_tag(declared) is None


def test_check_update_falls_back_to_the_releases_feed(monkeypatch):
    monkeypatch.setattr(update, "__version__", CURRENT)

    def refused(url):
        raise update.UpdateError("the release check returned HTTP 403")

    feed = (
        "<feed><entry><title>v9.9.9</title>"
        '<link href="https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/releases/tag/v9.9.9"/>'
        "</entry></feed>"
    )
    body = update.check_update(refused, feed_fetcher=lambda url: feed)
    assert body["ok"] is True
    assert body["latest"] == LATEST
    assert body["update_available"] is True
    assets = {asset["name"]: asset["url"] for asset in body["assets"]}
    assert f"essay_writer-{LATEST}.tar.gz" in assets
    assert assets["SHA256SUMS"].endswith(f"/v{LATEST}/SHA256SUMS")


def test_check_update_reports_when_both_sources_fail(monkeypatch):
    monkeypatch.setattr(update, "__version__", CURRENT)

    def refused(url):
        raise update.UpdateError("the release check returned HTTP 403")

    def feed_refused(url):
        raise update.UpdateError("the release feed returned HTTP 403")

    body = update.check_update(refused, feed_fetcher=feed_refused)
    assert body["ok"] is False
    assert "403" in body["reason"]


def test_apply_refuses_a_developer_checkout(monkeypatch):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: True)
    body = update.apply_update(fetcher=lambda url: _release())
    assert body["ok"] is False
    assert body["updated"] is False
    assert "source checkout" in body["reason"].casefold()
    assert "git pull" in body["reason"]


def test_apply_says_up_to_date(monkeypatch):
    monkeypatch.setattr(update, "__version__", LATEST)
    body = update.apply_update(fetcher=lambda url: _release(tag=f"v{LATEST}"))
    assert body["ok"] is True
    assert body["updated"] is False
    assert body["reason"] == "up-to-date"


def test_download_refuses_a_non_github_asset_host(monkeypatch, tmp_path):
    seen: list[str] = []

    def fake(url, **kwargs):
        seen.append(url)
        return update.safe_url.Response(200, {}, b"archive")

    monkeypatch.setattr(update.safe_url, "open_url", fake)
    with pytest.raises(update.UpdateError, match="evil.example"):
        update._download("https://evil.example/essay_writer-9.9.9.tar.gz", tmp_path / "asset")
    with pytest.raises(update.UpdateError, match="github.com"):
        update._download("http://github.com/owner/repo/archive.tar.gz", tmp_path / "asset")
    assert seen == []


@pytest.mark.parametrize(
    "host",
    [
        "github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    ],
)
def test_download_accepts_a_github_asset_host(monkeypatch, tmp_path, host):
    seen: list[str] = []

    def fake(url, **kwargs):
        seen.append(url)
        return update.safe_url.Response(200, {}, b"archive")

    monkeypatch.setattr(update.safe_url, "open_url", fake)
    dest = tmp_path / "asset"
    update._download(f"https://{host}/owner/repo/releases/download/v9.9.9/file.tar.gz", dest)
    assert seen == [f"https://{host}/owner/repo/releases/download/v9.9.9/file.tar.gz"]
    assert dest.read_bytes() == b"archive"


def test_sum_for_refuses_a_conflicting_or_unusable_entry():
    name = f"essay_writer-{LATEST}.tar.gz"
    real = "ab" * 32
    other = "cd" * 32
    assert update._sum_for(f"{real}  {name}\n{real}  *{name}\n", name) == real
    assert update._sum_for(f"{real}  {name}.evil\n", name) is None
    with pytest.raises(update.UpdateError, match="conflicting"):
        update._sum_for(f"{real}  {name}\n{other}  {name}\n", name)
    with pytest.raises(update.UpdateError, match="unusable"):
        update._sum_for(f"deadbeef  {name}\n{real}  {name}\n", name)


def test_apply_refuses_conflicting_checksums(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)
    real = hashlib.sha256(archive_bytes).hexdigest()

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(
                f"{real}  essay_writer-{LATEST}.tar.gz\n{'cd' * 32}  essay_writer-{LATEST}.tar.gz\n",
                encoding="utf-8",
            )
        else:
            path.write_bytes(archive_bytes)

    pip_calls: list[list[str]] = []
    body = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=lambda command, cwd: pip_calls.append(command) or {"returncode": 0},
    )
    assert body["ok"] is False
    assert "conflicting" in body["reason"]
    assert pip_calls == []


def test_apply_refuses_a_checksum_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(f"{'0' * 64}  essay_writer-{LATEST}.tar.gz\n", encoding="utf-8")
        else:
            path.write_bytes(archive_bytes)

    pip_calls: list[list[str]] = []

    def pip_runner(command, cwd):
        pip_calls.append(command)
        return {"returncode": 0, "stdout": "", "stderr": ""}

    body = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=pip_runner,
    )
    assert body["ok"] is False
    assert body["updated"] is False
    assert "SHA-256" in body["reason"]
    assert pip_calls == []


def test_apply_installs_the_archive_and_checks_health(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)
    digest = hashlib.sha256(archive_bytes).hexdigest()

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(f"{digest}  essay_writer-{LATEST}.tar.gz\n", encoding="utf-8")
        else:
            path.write_bytes(archive_bytes)

    calls: list[tuple[list[str], Path]] = []

    def pip_runner(command, cwd):
        calls.append((command, Path(cwd)))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    body = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=pip_runner,
        health_runner=lambda: _health_payload(LATEST),
    )
    assert body["ok"] is True
    assert body["updated"] is True
    assert body["from"] == CURRENT
    assert body["to"] == LATEST
    assert body["restart_required"] is True
    assert "--require-hashes" in calls[0][0]
    assert "-r" in calls[0][0]
    assert "--no-deps" in calls[1][0]
    assert "--upgrade" in calls[1][0]
    assert calls[1][1].name == f"essay_writer-{LATEST}"


_HOLD_LOCK = """
import fcntl, sys
handle = open(sys.argv[1], "a+b")
fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
print("held", flush=True)
sys.stdin.readline()
"""

_PROBE_LOCK = """
import fcntl, sys
handle = open(sys.argv[1], "a+b")
try:
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print("busy")
else:
    print("acquired")
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
"""


def _probe_lock(path: Path) -> str:
    probe = subprocess.run(
        [sys.executable, "-c", _PROBE_LOCK, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    return probe.stdout.strip()


def test_a_second_update_is_refused_and_the_lock_is_released(monkeypatch, tmp_path):
    """Another process holding the lock stops the install, and a failed install releases it."""
    lock = tmp_path / "update.lock"
    monkeypatch.setenv("ESSAY_WRITER_UPDATE_LOCK", str(lock))
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)
    digest = hashlib.sha256(archive_bytes).hexdigest()

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(f"{digest}  essay_writer-{LATEST}.tar.gz\n", encoding="utf-8")
        else:
            path.write_bytes(archive_bytes)

    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_LOCK, str(lock)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    pip_calls: list[str] = []
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        blocked = update.apply_update(
            fetcher=lambda url: _release(),
            downloader=download,
            pip_runner=lambda command, cwd: pip_calls.append("pip") or {"returncode": 0},
            health_runner=lambda: _health_payload(LATEST),
        )
    finally:
        if holder.stdin is not None:
            holder.stdin.close()
        holder.wait(timeout=5)
    assert blocked["ok"] is False
    assert blocked["reason"] == "another update is already running"
    assert pip_calls == []

    def pip_runner(command, cwd):
        pip_calls.append(_probe_lock(lock))
        return {"returncode": 1, "stdout": "", "stderr": ""}

    failed = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=pip_runner,
        health_runner=lambda: _health_payload(LATEST),
    )
    assert failed["ok"] is False
    assert "did not finish" in failed["reason"]
    assert pip_calls == ["busy"]
    assert _probe_lock(lock) == "acquired"


def test_apply_reports_a_partial_install_when_the_second_pip_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)
    digest = hashlib.sha256(archive_bytes).hexdigest()

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(f"{digest}  essay_writer-{LATEST}.tar.gz\n", encoding="utf-8")
        else:
            path.write_bytes(archive_bytes)

    def pip_runner(command, cwd):
        if "--require-hashes" in command:
            return {"returncode": 0, "stdout": "", "stderr": ""}
        return {"returncode": 1, "stdout": "", "stderr": "package install failed"}

    body = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=pip_runner,
        health_runner=lambda: _health_payload(LATEST),
    )
    assert body["ok"] is False
    assert body["updated"] is False
    assert body["environment_changed"] is True
    assert body["rolled_back"] is False
    assert "not rolled back" in body["reason"]
    assert len(body["pip"]) == 2


def test_apply_refuses_when_health_names_the_old_version(monkeypatch, tmp_path):
    monkeypatch.setattr(update, "__version__", CURRENT)
    monkeypatch.setattr(update, "is_developer_checkout", lambda: False)
    archive_bytes = _sdist_bytes(tmp_path)
    digest = hashlib.sha256(archive_bytes).hexdigest()

    def download(url, path: Path):
        if path.name == "SHA256SUMS":
            path.write_text(f"{digest}  essay_writer-{LATEST}.tar.gz\n", encoding="utf-8")
        else:
            path.write_bytes(archive_bytes)

    body = update.apply_update(
        fetcher=lambda url: _release(),
        downloader=download,
        pip_runner=lambda command, cwd: {"returncode": 0, "stdout": "", "stderr": ""},
        health_runner=lambda: _health_payload(CURRENT),
    )
    assert body["ok"] is False
    assert body["updated"] is False
    assert body["installed"] is True
    assert body["environment_changed"] is True
    assert body["rolled_back"] is False
    assert "new version" in body["reason"]
    assert "on disk but unverified" in body["reason"]


def test_the_cli_prints_the_check(monkeypatch, capsys):
    from essay_writer import server

    monkeypatch.setattr(update, "check_update", lambda: {"ok": True, "latest": LATEST})
    server.main(["--check-update"])
    printed = json.loads(capsys.readouterr().out)
    assert printed["latest"] == LATEST


def test_a_symlink_in_the_archive_is_refused(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        link = tarfile.TarInfo("essay_writer-9.9.9/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        bundle.addfile(link)
    with pytest.raises(update.UpdateError):
        with tarfile.open(archive, "r:gz") as bundle:
            update._safe_extract(bundle, tmp_path / "out")
