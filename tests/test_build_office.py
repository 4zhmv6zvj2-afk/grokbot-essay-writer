
import json
import zipfile
from pathlib import Path

import pytest

from essay_writer.build_office import (
    RESIDUALS,
    build_deliverable_handoff,
    stage_launch,
    stage_settings,
)
from essay_writer.first_run import attach_build_mcp, install_uploaded_copy, package_root
from essay_writer.review import REVIEW_PROMPT
from essay_writer.server import main as server_main
from essay_writer.stage_llm import STAGE_KEYS
from essay_writer.stage_llm import stage_settings as shared_settings
from essay_writer.writing_basics import CHECKLIST_WALK, CHECKLISTS


def _rules(command: list[str]) -> str:
    return command[command.index("--rules") + 1]


def test_build_imports_the_shared_stage_settings():
    assert stage_settings is shared_settings
    for stage in STAGE_KEYS:
        launch = stage_launch(stage)
        item = shared_settings(stage)
        assert launch["source"] == "essay_writer.stage_llm.stage_settings"
        assert launch["settings"] == item
        command = launch["command"]
        assert command[command.index("--model") + 1] == item["model"] == "grok-4.7"
        assert command[command.index("--effort") + 1] == item["reasoning"]
        rules = _rules(command)
        assert str(item["context_window"]) in rules
        assert item["prompt_overlay"] in rules
        assert "Fast is off" in rules
        assert "--fast" not in command
        assert "fast" not in command[command.index("--model") + 1]


def test_every_launch_carries_256k():
    for stage in STAGE_KEYS:
        rules = _rules(stage_launch(stage)["command"])
        assert "Context window 256000" in rules
        assert "500000" not in rules


def test_effort_on_the_launch_matches_the_locks():
    effort = {
        stage: stage_launch(stage)["command"][stage_launch(stage)["command"].index("--effort") + 1]
        for stage in STAGE_KEYS
    }
    assert effort == {
        "1": "high",
        "2": "high",
        "3": "high",
        "4a": "high",
        "4b": "xhigh",
        "5": "xhigh",
        "6": "high",
        "7": "high",
        "8": "high",
        "9": "high",
        "10": "medium",
        "eqr": "xhigh",
    }
    assert {stage for stage, level in effort.items() if level == "xhigh"} == {"4b", "5", "eqr"}
    assert all(effort[stage] == "high" for stage in ("6", "7", "8"))


def test_prompt_overlay_on_the_launch_is_the_existing_stage_prompt():
    for stage, lines in CHECKLISTS.items():
        rules = _rules(stage_launch(stage)["command"])
        assert "\n".join(f"- {line}" for line in lines) in rules
        assert CHECKLIST_WALK in rules
    for stage in ("2", "3", "4a", "4b", "5"):
        rules = _rules(stage_launch(stage)["command"])
        assert "Do not silently rewrite the plan into the draft." in rules
        assert "purpose and scope" in rules
        assert "central theme" in rules
    assert "An essay locks a thesis." in _rules(stage_launch("2")["command"])
    assert "A report locks purpose and scope." in _rules(stage_launch("2")["command"])
    assert REVIEW_PROMPT in _rules(stage_launch("eqr")["command"])
    assert CHECKLIST_WALK not in _rules(stage_launch("eqr")["command"])
    assert "500000" not in _rules(stage_launch("eqr")["command"])
    assert "256000" in _rules(stage_launch("5")["command"])


def test_committed_grok_config_matches_the_writer(tmp_path):
    from essay_writer.first_run import mcp_launch_command

    attached = attach_build_mcp(
        tmp_path,
        reviewer=False,
        enable=lambda name: {"identifier": name, "enabled": False},
    )
    generated = Path(attached["project_config"]).read_text(encoding="utf-8")
    committed = (package_root() / ".grok" / "config.toml").read_text(encoding="utf-8")
    launch = mcp_launch_command()
    expected = committed.replace('command = "essay-writer"', f'command = "{launch}"', 1)
    assert generated == expected
    assert "[mcp_servers.essay-writer]" in committed
    assert 'command = "essay-writer"' in committed
    assert "args = []" in committed
    assert "essay-reviewer" not in committed
    assert attached["residual_id"] == "40a-open-session"


def test_build_attach_keeps_other_tables_and_adds_the_reviewer(tmp_path):
    user = tmp_path / "user.toml"
    user.write_text(
        "\n".join(
            [
                "# keep",
                "[plugins.demo]",
                "enabled = true",
                "",
                "[mcp_servers.other]",
                'command = "other"',
                'args = ["--keep"]',
                "",
                "[mcp_servers.essay-writer]",
                'command = "stale"',
                'args = ["--old"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    enabled: list[str] = []

    def enable(name: str) -> dict:
        enabled.append(name)
        return {"identifier": name, "enabled": True}

    both = attach_build_mcp(tmp_path, reviewer=True, enable=enable, user_config=user)
    assert both["ok"] is True
    assert both["servers"] == ["essay-writer", "essay-reviewer"]
    assert enabled == ["essay-writer", "essay-reviewer"]
    text = user.read_text(encoding="utf-8")
    assert "# keep" in text
    assert "[plugins.demo]" in text
    assert "[mcp_servers.other]" in text
    assert "--keep" in text
    assert "stale" not in text
    assert "--old" not in text
    assert text.count("[mcp_servers.essay-writer]") == 1
    assert 'args = ["--reviewer"]' in text


def test_install_uses_the_cloud_folder_and_names_the_install_residual(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    upload = tmp_path / "essay-writer.zip"
    with zipfile.ZipFile(upload, "w") as archive:
        archive.writestr("essay-writer-main/pyproject.toml", '[project]\nname = "essay-writer"\n')
        archive.writestr("essay-writer-main/src/essay_writer/__init__.py", "")

    def run(command: list[str], cwd: Path) -> dict:
        assert command[1:] == ["-m", "pip", "install", "-e", "."]
        assert Path(cwd) == cloud / "essay-writer-install" / "essay-writer-main"
        return {"returncode": 0, "stdout": "", "stderr": ""}

    result = install_uploaded_copy(upload, pip_runner=run)
    assert result["ok"] is True
    assert result["install_residual_id"] == "40b-install-root"
    assert result["install_residual"] == RESIDUALS["40b-install-root"]
    root = Path(result["root"])
    assert root == cloud / "essay-writer-install" / "essay-writer-main"
    assert ".grok" not in root.parts[:-2]
    from essay_writer.first_run import mcp_launch_command

    launch = mcp_launch_command()
    grok_text = (root / ".grok" / "config.toml").read_text(encoding="utf-8")
    cursor = json.loads((root / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert "[mcp_servers.essay-writer]" in grok_text
    assert f'command = "{launch}"' in grok_text
    assert cursor["mcpServers"]["essay-writer"]["command"] == launch
    assert cursor["mcpServers"]["essay-writer"]["args"] == []
    assert "essay-reviewer" in grok_text
    assert "essay-reviewer" in cursor["mcpServers"]


def test_build_handoff_copies_word_and_zip_and_names_packing(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    mac = tmp_path / "mac"
    folder = tmp_path / "output"
    folder.mkdir()
    (folder / "essay.docx").write_bytes(b"word-bytes")
    (folder / "papers.zip").write_bytes(b"zip-bytes")
    (folder / "notes.pdf").write_bytes(b"%PDF-1.4")

    copied = build_deliverable_handoff(folder, mac_dir=mac)
    assert copied["handoff"] == "copy_deliverable_to_mac"
    assert copied["copied"] is True
    assert "40d-packing" in copied["residual_ids"]
    assert RESIDUALS["40d-packing"] in copied["residual"]
    assert (mac / "essay.docx").read_bytes() == b"word-bytes"
    assert (mac / "papers.zip").read_bytes() == b"zip-bytes"
    assert not (mac / "notes.pdf").exists()

    missing = build_deliverable_handoff(folder / "essay.docx")
    assert missing["copied"] is False
    assert missing["reason"] == "mac-not-mounted"
    assert missing["residual_ids"] == ["40d-packing", "40d-mac"]
    assert RESIDUALS["40d-mac"] in missing["residual"]


def test_workflow_names_the_build_office():
    workflow = (package_root() / "docs" / "workflow.md").read_text(encoding="utf-8")
    assert "essay_writer.build_office" in workflow
    assert "essay_writer.stage_llm.stage_settings" in workflow


def test_stage_launch_cli_prints_the_4b_command(capsys):
    server_main(["--stage-launch", "4b"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["settings"]["context_window"] == 256_000
    assert payload["command"][payload["command"].index("--effort") + 1] == "xhigh"
    assert payload["context_residual_id"] == "context-flag"
    rules = payload["command"][payload["command"].index("--rules") + 1]
    assert "Walk this Basics checklist internally before the save." in rules
    assert "Do not silently rewrite the plan into the draft." in rules
    assert "central theme" in rules

    with pytest.raises(SystemExit) as caught:
        server_main(["--stage-launch", "nope"])
    assert caught.value.code == "unknown stage nope"
