"""Path and setup notes."""

from pathlib import Path

from test_projects import MODULE, _confirm_new

from essay_writer.build_office import RESIDUALS, stage_launch
from essay_writer.first_run import (
    copy_deliverable_to_mac,
    grok_config_home,
    install_uploaded_copy,
)
from essay_writer.projects import essay_project_delete
from essay_writer.shells import front_office_call
from essay_writer.student_voice import student_surface_hits

REPO = Path(__file__).resolve().parents[1]


def _outside(workspace: Path) -> Path:
    folder = workspace.parent / f"{workspace.name}-mac"
    folder.mkdir(exist_ok=True)
    return folder


def test_delete_workspace_only_names_leave_behind(workspace):
    _confirm_new()
    draft = essay_project_delete(MODULE, "draft")
    assert draft["computer_list"] == []
    assert draft.get("leave_behind_notice")
    assert "mounted" in draft["leave_behind_notice"].casefold()
    assert student_surface_hits(draft["leave_behind_notice"]) == []
    assert student_surface_hits(draft["next"].replace("Confirm card", "")) == []


def test_delete_refuses_invisible_path_with_leave_behind(workspace):
    missing = workspace.parent / "nowhere" / f"{MODULE}.docx"
    refused = essay_project_delete(MODULE, "draft", where="local", localPaths=[str(missing)])
    assert refused["ok"] is False
    assert refused.get("leave_behind") is True
    assert "mounted" in refused["reason"].casefold()


def test_front_office_call_scrubs_delete_chat(workspace):
    _confirm_new()
    body = front_office_call(
        "essay.project.delete",
        {"module": MODULE, "confirmPhase": "draft"},
    )
    assert body["ok"] is True
    assert student_surface_hits(body.get("next", "").replace("Confirm card", "")) == []
    assert student_surface_hits(body.get("leave_behind_notice", "")) == []


def test_stage_launch_documents_context_window_on_rules():
    launch = stage_launch("4b")
    rules = launch["command"][-1]
    assert "Context window 256000" in rules
    assert launch["context_residual_id"] == "context-flag"
    assert RESIDUALS["context-flag"] in launch["context_residual"]


def test_install_json_separates_code_folder_from_grok_home(tmp_path, monkeypatch):
    cloud = tmp_path / "workspace"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    monkeypatch.setenv("GROK_HOME", str(tmp_path / "grok-home"))
    upload = tmp_path / "essay-writer.zip"
    import zipfile

    with zipfile.ZipFile(upload, "w") as archive:
        archive.writestr("essay-writer-main/pyproject.toml", '[project]\nname = "essay-writer"\n')
        archive.writestr("essay-writer-main/src/essay_writer/__init__.py", "")

    def run(command, cwd):
        return {"returncode": 0, "stdout": "", "stderr": ""}

    result = install_uploaded_copy(upload, pip_runner=run, attach=False)
    assert result["grok_config_home"] == grok_config_home()
    assert result["code_install_folder"] == result["root"]
    assert result["unpack_parent"] == str(cloud / "essay-writer-install")
    assert ".grok" not in Path(result["unpack_parent"]).name


def test_mac_not_mounted_returns_plain_next(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_MAC_DIR", raising=False)
    doc = tmp_path / "essay.docx"
    doc.write_bytes(b"x")
    missing = copy_deliverable_to_mac(doc)
    assert missing["reason"] == "mac-not-mounted"
    assert missing.get("next")
    assert student_surface_hits(missing["next"]) == []
    assert "stay" in missing["next"].casefold()


def test_docs_batch_d_index_and_cites():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    assert "FIRST-RUN.txt" in readme
    samples = (REPO / "docs" / "samples-study.md").read_text(encoding="utf-8")
    assert "scaffold" not in samples.casefold()
    assert "out of scope" in samples.casefold() or "out of product scope" in (
        REPO / "docs" / "report-writing-helpers.md"
    ).read_text(encoding="utf-8").casefold()
