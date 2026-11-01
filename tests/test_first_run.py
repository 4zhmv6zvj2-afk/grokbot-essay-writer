"""First-run glue: unpack and install, prompt text, MCP attach, copy to the Mac."""

import json
import stat
import zipfile
from pathlib import Path

import pytest

from essay_writer.first_run import (
    attach_custom_mcp,
    copy_deliverable_to_mac,
    first_run_prompt,
    install_uploaded_copy,
    mcp_launch_command,
    mcp_template,
    package_root,
)
from essay_writer.first_run import (
    main as first_run_main,
)
from essay_writer.server import first_run_request
from essay_writer.server import main as server_main


def _pyproject() -> str:
    return '[project]\nname = "essay-writer"\nversion = "0.1.0"\n'


def _zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)


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
    assert "essay_writer.first_run" in bootstrap


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
            "essay-writer-main/src/essay_writer/__init__.py": b"",
        },
    )
    calls: list[tuple[list[str], Path]] = []
    result = install_uploaded_copy(upload, pip_runner=_runner(calls), attach=False)
    assert result["ok"] is True
    assert result["installed"] is True
    assert result["unpacked"] is True
    assert result["prompt_present"] is True
    root = Path(result["root"])
    assert root == cloud / "essay-writer-install" / "essay-writer-main"
    assert (root / "pyproject.toml").is_file()
    assert (root / "FIRST-RUN.txt").read_text(encoding="utf-8").startswith("pip install -e .")
    assert "Essay-writer" not in root.parts
    command, cwd = calls[0]
    assert command[1:] == ["-m", "pip", "install", "-e", "."]
    assert ".[dev]" not in command
    assert cwd == root


def test_zip_slip_and_clone_urls_do_not_install(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    calls: list[tuple[list[str], Path]] = []
    slipped = tmp_path / "slip.zip"
    _zip(slipped, {"../outside.txt": b"nope", "nested/../../outside.txt": b"nope"})
    refused = install_uploaded_copy(slipped, pip_runner=_runner(calls), attach=False)
    assert refused["ok"] is False
    assert not (tmp_path / "outside.txt").exists()
    assert calls == []

    linked = tmp_path / "link.zip"
    with zipfile.ZipFile(linked, "w") as archive:
        info = zipfile.ZipInfo("escape")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, b"/tmp/elsewhere")
    refused_link = install_uploaded_copy(linked, pip_runner=_runner(calls), attach=False)
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
    result = install_uploaded_copy(upload, pip_runner=_runner(calls), attach=False)
    assert result["ok"] is False
    assert "Documents" in result["reason"]
    assert calls == []


def test_internal_volume_and_the_save_tree_are_refused(tmp_path):
    upload = tmp_path / "copy.zip"
    _zip(upload, {"pyproject.toml": _pyproject().encode()})
    calls: list[tuple[list[str], Path]] = []
    volume = tmp_path / "ResearchDrive" / "essay-writer-install"
    refused = install_uploaded_copy(upload, dest=volume, pip_runner=_runner(calls), attach=False)
    assert refused["ok"] is False
    assert "not an install path on this computer" in refused["reason"]
    assert calls == []

    door = tmp_path / "save"
    (door / "app").mkdir(parents=True)
    (door / "setup.json").write_text("{}", encoding="utf-8")
    refused_door = install_uploaded_copy(upload, dest=door, pip_runner=_runner(calls), attach=False)
    assert refused_door["ok"] is False
    assert calls == []


def test_failed_pip_does_not_attach(tmp_path):
    source = tmp_path / "tree"
    source.mkdir()
    (source / "pyproject.toml").write_text(_pyproject(), encoding="utf-8")
    enabled: list[str] = []

    def fail(command: list[str], cwd: Path) -> dict:
        return {"returncode": 1, "stdout": "", "stderr": "pip failed"}

    def enable(name: str) -> dict:
        enabled.append(name)
        return {"identifier": name, "enabled": True}

    result = install_uploaded_copy(source, pip_runner=fail, enable=enable)
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

    missing = copy_deliverable_to_mac(folder / "essay.docx")
    assert missing["copied"] is False
    assert missing["reason"] == "mac-not-mounted"
    assert "residual" in missing

    volume = copy_deliverable_to_mac(folder / "essay.docx", mac_dir=tmp_path / "ResearchDrive" / "out")
    assert volume["ok"] is False
    assert "not a copy path on this computer" in volume["reason"]


def test_reviewer_flag_alone_is_the_review_server():
    assert first_run_request(["--reviewer"]) is False
    assert first_run_request(["--install-upload", "copy.zip"]) is True
    assert first_run_request(["--install-upload", "copy.zip", "--reviewer"]) is True
    assert first_run_request(["--attach-mcp", "--reviewer"]) is True
    assert first_run_request(["--copy-to-mac", "essay.docx"]) is True


def test_server_routes_install_and_copy(monkeypatch, capsys, tmp_path):
    seen: dict = {}

    def fake(upload=None, dest=None, reviewer=False, **kwargs):
        seen["upload"] = upload
        seen["reviewer"] = reviewer
        return {"ok": True, "installed": True}

    monkeypatch.setattr("essay_writer.first_run.install_uploaded_copy", fake)
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

    monkeypatch.setattr("essay_writer.first_run.install_uploaded_copy", fake)
    with pytest.raises(SystemExit) as caught:
        server_main(["--not-a-flag"])
    assert caught.value.code != 0
