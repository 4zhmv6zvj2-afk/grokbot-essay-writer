"""First-run glue: unpack and install, prompt text, MCP attach, copy to the Mac."""

import hashlib
import json
import stat
import zipfile
from pathlib import Path

import pytest

from essay_writer.first_run import (
    attach_custom_mcp,
    copy_deliverable_to_mac,
    expose_writer_on_path,
    first_run_prompt,
    friend_mac_home,
    install_uploaded_copy,
    mac_deliverables_dir,
    mcp_launch_command,
    mcp_template,
    package_root,
    resolve_build_config,
    resolve_user_config,
)
from essay_writer.first_run import (
    main as first_run_main,
)
from essay_writer.first_run_cli import _parse
from essay_writer.server import first_run_request
from essay_writer.server import main as server_main


def _pyproject() -> str:
    return '[project]\nname = "essay-writer"\nversion = "0.1.0"\n'


def _requirements() -> bytes:
    return b"mcp==2.3.0 --hash=sha256:" + b"0" * 64 + b"\n"


def _zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _no_path_expose() -> None:
    return None


def _runner(calls: list[tuple[list[str], Path]]):
    def run(command: list[str], cwd: Path) -> dict:
        calls.append((command, Path(cwd)))
        return {"returncode": 0, "stdout": "", "stderr": ""}

    return run


def test_prompt_text_ships_with_the_copy():
    root = package_root() / "FIRST-RUN.txt"
    packaged = package_root() / "src" / "essay_writer" / "FIRST-RUN.txt"
    assert root.is_file()
    assert packaged.is_file()
    assert root.read_text(encoding="utf-8") == packaged.read_text(encoding="utf-8")
    text = first_run_prompt()
    assert text == root.read_text(encoding="utf-8")
    assert "pip install -e ." in text
    assert "Custom MCP" in text
    assert "essay-writer" in text
    assert "--reviewer" in text
    assert "/workspace/essay-writer-install" in text
    assert "do not also clone a git url" in text.casefold()
    assert "public repo" in text.casefold()
    cited = (
        "https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md",
        "https://github.com/CrossRef/rest-api-doc/blob/master/README.md",
    )
    leftover = text
    for url in cited:
        assert url in text
        leftover = leftover.replace(url, "")
    assert "github.com" not in leftover.casefold()
    assert "defaults to Cursor" in text
    assert "Grok Build" in text
    assert "from a subscription" in text.casefold()
    bootstrap = (package_root() / "first_run.py").read_text(encoding="utf-8")
    assert "python_bootstrap.bootstrap" in bootstrap


def test_project_mcp_attaches_essay_writer_without_the_reviewer():
    config = json.loads((package_root() / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    template = mcp_template()
    assert config["mcpServers"]["essay-writer"] == template["essay-writer"]
    assert template["essay-writer"]["command"] == "essay-writer"
    assert template["essay-writer"]["args"] == []
    assert template["essay-reviewer"]["args"] == ["--reviewer"]
    assert "essay-reviewer" not in config["mcpServers"]


def test_unpack_then_pip_install_on_the_cloud_computer(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    upload = tmp_path / "essay-writer.zip"
    _zip(
        upload,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/FIRST-RUN.txt": b"pip install -e .\n",
            "essay-writer-main/requirements-runtime.txt": _requirements(),
            "essay-writer-main/src/essay_writer/__init__.py": b"",
        },
    )
    calls: list[tuple[list[str], Path]] = []
    exposed: list[str] = []

    def fake_expose() -> str:
        exposed.append("essay-writer")
        return "essay-writer"

    result = install_uploaded_copy(
        upload,
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(upload),
        path_exposer=fake_expose,
        allow_cursor_install=False,
    )
    assert exposed == ["essay-writer"]
    assert result["ok"] is True
    assert result["installed"] is True
    assert result["unpacked"] is True
    assert result["prompt_present"] is True
    assert result["requirements_verified"] is True
    root = Path(result["root"])
    assert root == cloud / "essay-writer-install" / "essay-writer-main"
    assert (root / "pyproject.toml").is_file()
    assert (root / "FIRST-RUN.txt").read_text(encoding="utf-8").startswith("pip install -e .")
    assert "Essay-writer" not in root.parts
    assert [command[1:] for command, _cwd in calls] == [
        ["-m", "pip", "install", "--require-hashes", "-r", "requirements-runtime.txt"],
        ["-m", "pip", "install", "--no-deps", "-e", "."],
    ]
    assert all(".[dev]" not in command for command, _cwd in calls)
    assert all(cwd == root for _command, cwd in calls)


def test_zip_slip_and_clone_urls_do_not_install(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    calls: list[tuple[list[str], Path]] = []
    slipped = tmp_path / "slip.zip"
    _zip(
        slipped,
        {
            "../outside.txt": b"nope",
            "nested/../../outside.txt": b"nope",
            "essay-writer-main/requirements-runtime.txt": _requirements(),
        },
    )
    refused = install_uploaded_copy(
        slipped,
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(slipped),
        path_exposer=_no_path_expose,
    )
    assert refused["ok"] is False
    assert refused["reason"].startswith("The upload was not unpacked")
    assert not (tmp_path / "outside.txt").exists()
    assert calls == []

    linked = tmp_path / "link.zip"
    with zipfile.ZipFile(linked, "w") as archive:
        info = zipfile.ZipInfo("escape")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"/tmp/elsewhere")
        archive.writestr("essay-writer-main/requirements-runtime.txt", _requirements())
    refused_link = install_uploaded_copy(
        linked,
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(linked),
        path_exposer=_no_path_expose,
    )
    assert refused_link["ok"] is False
    assert calls == []

    cloned = install_uploaded_copy(
        "https://github.com/example/essay-writer.git",
        pip_runner=_runner(calls),
        attach=False,
    )
    assert cloned["ok"] is False
    assert "clone" in cloned["reason"].casefold()
    assert calls == []


def test_missing_cloud_does_not_fall_back_to_documents(tmp_path, monkeypatch):
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", tmp_path / "missing")
    upload = tmp_path / "copy.zip"
    _zip(upload, {"pyproject.toml": _pyproject().encode()})
    calls: list[tuple[list[str], Path]] = []
    result = install_uploaded_copy(
        upload, pip_runner=_runner(calls), attach=False, upload_sha256=_sha(upload)
    )
    assert result["ok"] is False
    assert "Documents" in result["reason"]
    assert calls == []


def test_internal_volume_and_the_save_tree_are_refused(tmp_path):
    upload = tmp_path / "copy.zip"
    _zip(upload, {"pyproject.toml": _pyproject().encode()})
    digest = _sha(upload)
    calls: list[tuple[list[str], Path]] = []
    volume = tmp_path / "ResearchDrive" / "essay-writer-install"
    refused = install_uploaded_copy(
        upload, dest=volume, pip_runner=_runner(calls), attach=False, upload_sha256=digest
    )
    assert refused["ok"] is False
    assert "not an install path on this computer" in refused["reason"]
    assert calls == []

    door = tmp_path / "save"
    (door / "app").mkdir(parents=True)
    (door / "setup.json").write_text("{}", encoding="utf-8")
    refused_door = install_uploaded_copy(
        upload, dest=door, pip_runner=_runner(calls), attach=False, upload_sha256=digest
    )
    assert refused_door["ok"] is False
    assert calls == []


def test_upload_zip_verifies_a_checksum_only_when_one_is_available(tmp_path):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    upload = tmp_path / "copy.zip"
    _zip(
        upload,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/requirements-runtime.txt": _requirements(),
        },
    )
    calls: list[tuple[list[str], Path]] = []

    # No checksum is supplied: the zip is trusted operator input and installs,
    # but the result says it was not verified.
    no_pin = install_uploaded_copy(
        upload,
        dest=tmp_path / "dest-none",
        pip_runner=_runner(calls),
        attach=False,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert no_pin["ok"] is True, no_pin
    assert no_pin["upload_verified"] is False
    assert no_pin["upload_checksum"] is None
    assert no_pin["upload_sha256"] == _sha(upload)
    assert "not checksum-verified" in no_pin["upload_note"]

    # An explicit pin that does not match refuses before unpacking.
    wrong = install_uploaded_copy(
        upload,
        dest=tmp_path / "dest-wrong",
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256="0" * 64,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert wrong["ok"] is False
    assert "did not match" in wrong["reason"]
    assert wrong["expected_sha256"] == "0" * 64
    assert wrong["actual_sha256"] == _sha(upload)
    assert not (tmp_path / "dest-wrong").exists()

    # An explicit matching pin verifies.
    accepted = install_uploaded_copy(
        upload,
        dest=tmp_path / "dest-pin",
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(upload),
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert accepted["ok"] is True
    assert accepted["upload_verified"] is True
    assert accepted["upload_checksum"] == "--upload-sha256"
    assert accepted["unpacked"] is True
    assert (tmp_path / "dest-pin").is_dir()


def test_upload_zip_reads_a_sidecar_checksum(tmp_path):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    upload = tmp_path / "copy.zip"
    _zip(
        upload,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/requirements-runtime.txt": _requirements(),
        },
    )
    digest = _sha(upload)
    calls: list[tuple[list[str], Path]] = []

    upload.with_name(upload.name + ".sha256").write_text(f"{digest}\n", encoding="utf-8")
    verified = install_uploaded_copy(
        upload,
        dest=tmp_path / "dest-sidecar",
        pip_runner=_runner(calls),
        attach=False,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert verified["ok"] is True, verified
    assert verified["upload_verified"] is True
    assert verified["upload_checksum"] == upload.name + ".sha256"

    other = tmp_path / "second.zip"
    _zip(
        other,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/requirements-runtime.txt": _requirements(),
        },
    )
    (tmp_path / "SHA256SUMS").write_text(f"{_sha(other)}  {other.name}\n", encoding="utf-8")
    verified_sums = install_uploaded_copy(
        other,
        dest=tmp_path / "dest-sums",
        pip_runner=_runner(calls),
        attach=False,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert verified_sums["ok"] is True, verified_sums
    assert verified_sums["upload_verified"] is True
    assert verified_sums["upload_checksum"] == f"SHA256SUMS ({other.name})"


def test_install_refuses_a_copy_without_runtime_requirements(tmp_path):
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(_pyproject(), encoding="utf-8")
    calls: list[tuple[list[str], Path]] = []
    result = install_uploaded_copy(
        source,
        pip_runner=_runner(calls),
        attach=False,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert result["ok"] is False
    assert "requirements-runtime.txt" in result["reason"]
    assert "unpinned" in result["reason"]
    assert result["requirements_verified"] is False
    assert calls == []


def test_zip_without_runtime_requirements_fails_closed_before_unpacking(tmp_path):
    upload = tmp_path / "copy.zip"
    _zip(
        upload,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/src/essay_writer/__init__.py": b"",
        },
    )
    calls: list[tuple[list[str], Path]] = []
    dest = tmp_path / "dest"
    result = install_uploaded_copy(
        upload,
        dest=dest,
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(upload),
        path_exposer=_no_path_expose,
    )
    assert result["ok"] is False
    assert "requirements-runtime.txt" in result["reason"]
    assert result["requirements_verified"] is False
    assert not dest.exists()
    assert calls == []


def test_failed_pip_does_not_attach(tmp_path):
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(_pyproject(), encoding="utf-8")
    (source / "requirements-runtime.txt").write_bytes(_requirements())
    enabled: list[str] = []

    def fail(command: list[str], cwd: Path) -> dict:
        return {"returncode": 1, "stdout": "", "stderr": "pip failed"}

    def enable(name: str) -> dict:
        enabled.append(name)
        return {"identifier": name, "enabled": True}

    result = install_uploaded_copy(
        source,
        pip_runner=fail,
        enable=enable,
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert result["ok"] is False
    assert result["installed"] is False
    assert result["unpacked"] is False
    assert enabled == []


def test_attach_merges_essay_writer_and_optional_reviewer(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    user = tmp_path / "mcp.json"
    user.write_text(
        json.dumps({"extra": True, "mcpServers": {"other": {"command": "other"}}}) + "\n",
        encoding="utf-8",
    )
    enabled: list[str] = []

    def enable(name: str) -> dict:
        enabled.append(name)
        return {"identifier": name, "enabled": True}

    writer = attach_custom_mcp(project, reviewer=False, enable=enable, user_config=user)
    assert writer["ok"] is True
    assert writer["servers"] == ["essay-writer"]
    assert enabled == ["essay-writer"]
    assert writer["residual"]
    project_config = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert project_config["mcpServers"]["essay-writer"]["args"] == []
    assert "essay-reviewer" not in project_config["mcpServers"]

    enabled.clear()
    both = attach_custom_mcp(project, reviewer=True, enable=enable, user_config=user)
    assert both["servers"] == ["essay-writer", "essay-reviewer"]
    assert enabled == ["essay-writer", "essay-reviewer"]
    loaded = json.loads(user.read_text(encoding="utf-8"))
    assert loaded["extra"] is True
    assert loaded["mcpServers"]["other"]["command"] == "other"
    assert loaded["mcpServers"]["essay-reviewer"]["args"] == ["--reviewer"]
    assert loaded["mcpServers"]["essay-writer"]["command"] == mcp_launch_command()


def test_copy_to_mac_takes_word_and_zip_only(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    # The unmounted branch is explicit: a test never discovers the real home.
    monkeypatch.setattr("essay_writer.first_run_mac.mac_deliverables_dir", lambda **_kwargs: None)
    mac = tmp_path / "mac"
    folder = tmp_path / "output"
    folder.mkdir()
    (folder / "essay.docx").write_bytes(b"word-bytes")
    (folder / "papers.zip").write_bytes(b"zip-bytes")
    (folder / "notes.pdf").write_bytes(b"%PDF-1.4")
    (folder / "plain.txt").write_text("leave me", encoding="utf-8")

    copied = copy_deliverable_to_mac(folder, mac_dir=mac)
    assert copied["copied"] is True
    assert (mac / "essay.docx").read_bytes() == b"word-bytes"
    assert (mac / "papers.zip").read_bytes() == b"zip-bytes"
    assert not (mac / "notes.pdf").exists()
    assert not (mac / "plain.txt").exists()
    assert (folder / "notes.pdf").is_file()
    assert (folder / "essay.docx").read_bytes() == b"word-bytes"

    refused = copy_deliverable_to_mac(folder / "notes.pdf", mac_dir=mac)
    assert refused["ok"] is False
    assert refused["copied"] is False

    # The folder holds operator-named files, not sequence output, so the
    # quarantine/provenance marks stay and the report says the clear was skipped.
    assert copied["files"][0]["quarantine"]["skipped"] is True
    assert copied["files"][0]["quarantine"]["cleared"] == []

    missing = copy_deliverable_to_mac(folder / "essay.docx")
    assert missing["copied"] is False
    assert missing["reason"] == "mac-not-mounted"
    assert "residual" in missing

    volume = copy_deliverable_to_mac(
        folder / "essay.docx", mac_dir=tmp_path / "ResearchDrive" / "out"
    )
    assert volume["ok"] is False
    assert "not a copy path on this computer" in volume["reason"]


def test_reviewer_flag_alone_is_the_review_server():
    assert first_run_request(["--reviewer"]) is False
    assert first_run_request(["--install-upload", "copy.zip"]) is True
    assert first_run_request(["--install-upload", "copy.zip", "--reviewer"]) is True
    assert first_run_request(["--install-upload", "copy.zip", "--upload-sha256", "a" * 64]) is True
    assert first_run_request(["--attach-mcp", "--reviewer"]) is True
    assert first_run_request(["--copy-to-mac", "essay.docx"]) is True


def test_server_routes_install_and_copy(monkeypatch, capsys, tmp_path):
    seen: dict = {}

    def fake(upload=None, dest=None, reviewer=False, **kwargs):
        seen["upload"] = upload
        seen["reviewer"] = reviewer
        return {"ok": True, "installed": True}

    monkeypatch.setattr("essay_writer.first_run_install.install_uploaded_copy", fake)
    with pytest.raises(SystemExit) as caught:
        server_main(["--install-upload", str(tmp_path / "copy.zip"), "--reviewer"])
    assert caught.value.code == 0
    assert seen["reviewer"] is True
    assert seen["upload"] == tmp_path / "copy.zip"

    source = tmp_path / "essay.docx"
    source.write_bytes(b"word-bytes")
    mac = tmp_path / "mac"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    capsys.readouterr()
    code = first_run_main(["--copy-to-mac", str(source)])
    assert code == 0
    assert (mac / "essay.docx").read_bytes() == b"word-bytes"
    payload = json.loads(capsys.readouterr().out)
    assert payload["copied"] is True


def test_unknown_flag_does_not_install(monkeypatch):
    def fake(*args, **kwargs):
        raise AssertionError("install should not run")

    monkeypatch.setattr("essay_writer.first_run_install.install_uploaded_copy", fake)
    with pytest.raises(SystemExit) as caught:
        server_main(["--not-a-flag"])
    assert caught.value.code != 0


def _upload_with_requirements(tmp_path: Path) -> Path:
    upload = tmp_path / "essay-writer.zip"
    _zip(
        upload,
        {
            "essay-writer-main/pyproject.toml": _pyproject().encode(),
            "essay-writer-main/FIRST-RUN.txt": b"pip install -e .\n",
            "essay-writer-main/requirements-runtime.txt": b"mcp==2.3.0 --hash=sha256:"
            + b"0" * 64
            + b"\n",
            "essay-writer-main/src/essay_writer/__init__.py": b"",
        },
    )
    return upload


def test_upload_with_runtime_requirements_installs_hashes_first(tmp_path, monkeypatch):
    """A zip carrying requirements-runtime.txt installs hashes, then --no-deps."""
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    upload = _upload_with_requirements(tmp_path)
    calls: list[tuple[list[str], Path]] = []
    result = install_uploaded_copy(
        upload,
        pip_runner=_runner(calls),
        attach=False,
        upload_sha256=_sha(upload),
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert result["ok"] is True
    assert result["requirements_verified"] is True
    assert [command[1:] for command, _cwd in calls] == [
        ["-m", "pip", "install", "--require-hashes", "-r", "requirements-runtime.txt"],
        ["-m", "pip", "install", "--no-deps", "-e", "."],
    ]
    assert [step["command"][1:] for step in result["pip_steps"]] == [
        command[1:] for command, _cwd in calls
    ]


def test_upload_stops_when_the_hash_pinned_install_fails(tmp_path, monkeypatch):
    """A failed hash install stops before the project install and says so."""
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    upload = _upload_with_requirements(tmp_path)
    calls: list[tuple[list[str], Path]] = []

    def failing_runner(command: list[str], cwd: Path) -> dict:
        calls.append((command, Path(cwd)))
        return {"returncode": 1, "stdout": "", "stderr": "hash mismatch"}

    result = install_uploaded_copy(
        upload,
        pip_runner=failing_runner,
        attach=False,
        upload_sha256=_sha(upload),
        path_exposer=_no_path_expose,
        allow_cursor_install=False,
    )
    assert result["ok"] is False
    assert "hash-pinned" in result["reason"]
    assert len(calls) == 1
    assert result["pip_steps"][0]["returncode"] == 1
    assert result["requirements_verified"] is False


def test_expose_writer_on_path_links_an_explicit_script_into_a_temp_dir(tmp_path):
    script = tmp_path / "install" / "essay-writer"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    search = tmp_path / "bin"
    search.mkdir()

    exposed = expose_writer_on_path(
        script=script, search_dirs=[str(search)], which=lambda _name: None
    )
    assert exposed == "essay-writer"
    link = search / "essay-writer"
    assert link.is_symlink()
    assert link.resolve() == script.resolve()


def test_expose_writer_on_path_handles_the_already_on_path_and_missing_script_cases(
    tmp_path, monkeypatch
):
    already = expose_writer_on_path(
        search_dirs=[], which=lambda _name: "/usr/local/bin/essay-writer"
    )
    assert already == "essay-writer"

    monkeypatch.setattr("essay_writer.first_run_host.writer_script", lambda: None)
    search = tmp_path / "bin"
    search.mkdir()
    assert expose_writer_on_path(search_dirs=[str(search)], which=lambda _name: None) is None


def test_resolve_user_and_build_config_take_an_explicit_include_user_policy(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.delenv("GROK_HOME", raising=False)

    assert resolve_user_config(include_user=False) is None
    assert resolve_user_config() == home / ".cursor" / "mcp.json"
    explicit = tmp_path / "explicit.json"
    assert resolve_user_config(explicit, include_user=False) == explicit

    assert resolve_build_config() is None
    (home / ".grok").mkdir()
    assert resolve_build_config() == home / ".grok" / "config.toml"
    assert resolve_build_config(include_user=False) is None

    grok_home = tmp_path / "grok-home"
    grok_home.mkdir()
    monkeypatch.setenv("GROK_HOME", str(grok_home))
    assert resolve_build_config() == grok_home / "config.toml"


def test_friend_mac_home_takes_an_explicit_mounted_discovery_policy(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_MAC_HOME", raising=False)
    mounted = tmp_path / "Users" / "friend"
    mounted.mkdir(parents=True)
    monkeypatch.setattr("essay_writer.first_run_mac._on_mac", lambda: False)
    monkeypatch.setattr("essay_writer.first_run_mac._one_mounted_mac_home", lambda: mounted)

    assert friend_mac_home() == mounted
    assert friend_mac_home(discover_mounted=False) is None

    monkeypatch.setattr("essay_writer.first_run_mac._on_mac", lambda: True)
    monkeypatch.setattr("essay_writer.first_run_mac._process_home", lambda: tmp_path)
    assert friend_mac_home() == tmp_path


def test_mac_deliverables_dir_takes_an_explicit_remembered_read_policy(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    remembered = tmp_path / "remembered"
    remembered.mkdir()
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    monkeypatch.setattr("essay_writer.first_run_mac.read_mac_handoff_dir", lambda: remembered)
    monkeypatch.setattr(
        "essay_writer.first_run_mac.visible_canonical_mac_handoff_dir", lambda: canonical
    )

    assert mac_deliverables_dir() == remembered
    assert mac_deliverables_dir(read_remembered=False) == canonical

    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(canonical))
    assert mac_deliverables_dir(read_remembered=True) == canonical


def test_quarantine_clearing_is_scoped_to_app_generated_deliverables(tmp_path, monkeypatch):
    from essay_writer import quarantine

    calls: list[Path] = []

    def fake_clear(path):
        calls.append(Path(path))
        return {
            "ok": True,
            "cleared": [],
            "absent": list(quarantine.QUARANTINE_ATTRS),
            "noop": True,
        }

    monkeypatch.setattr(quarantine, "clear_mac_quarantine", fake_clear)
    monkeypatch.setattr(
        "essay_writer.first_run_mac.remember_mac_deliverable", lambda *_a, **_k: None
    )
    mac = tmp_path / "mac"

    output = tmp_path / "Essay-writer" / "MOD1011AA" / "sequences" / "1" / "output"
    output.mkdir(parents=True)
    generated = output / "annotation.docx"
    generated.write_bytes(b"generated")
    result = copy_deliverable_to_mac(generated, mac_dir=mac)
    assert result["copied"] is True
    assert calls == [mac / "annotation.docx"]
    assert result["quarantine"]["skipped"] is False

    calls.clear()
    loose = tmp_path / "Downloads" / "MyEssay.docx"
    loose.parent.mkdir()
    loose.write_bytes(b"loose")
    result = copy_deliverable_to_mac(loose, mac_dir=mac)
    assert result["copied"] is True
    assert calls == []
    assert result["quarantine"]["skipped"] is True
    assert result["quarantine"]["reason"] == "not-an-app-deliverable"


def test_parse_accepts_upload_sha256_and_refuses_a_bad_pin():
    parsed = _parse(["--install-upload", "copy.zip", "--upload-sha256", "A" * 64])
    assert parsed["upload_sha256"] == "a" * 64
    assert parsed["upload"] == "copy.zip"

    for bad in ("not-a-hash", "a" * 63, "g" * 64):
        with pytest.raises(ValueError):
            _parse(["--upload-sha256", bad])
    with pytest.raises(ValueError):
        _parse(["--upload-sha256"])
    with pytest.raises(ValueError):
        _parse(["--upload-sha256", "a" * 64])
    with pytest.raises(ValueError):
        _parse(["--copy-to-mac", "essay.docx", "--upload-sha256", "a" * 64])


def test_usage_names_the_upload_sha256_flag(capsys):
    code = first_run_main(["--not-a-flag"])
    assert code == 2
    stderr = capsys.readouterr().err
    assert "--upload-sha256 SHA256" in stderr
    assert "--upload ZIP" in stderr
