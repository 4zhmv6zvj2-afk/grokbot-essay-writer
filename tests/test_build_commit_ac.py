"""The build marker on essay.health. Stable ids: AC1–AC5.

A friend copy carries BUILD-COMMIT next to the package modules, with the commit
the copy was built from. `essay.health` reports it as `build_commit`, so an
install can be matched to the CHANGELOG when the zip includes one. A copy with no marker
reports an empty string and still works.
"""

from pathlib import Path

from essay_writer import BUILD_ENV, BUILD_MARKER, __version__, build_commit
from essay_writer.health import essay_health

REPO = Path(__file__).resolve().parents[1]
SHA = "03c3928dfb2b63493e40a472b8a95faf244c4aa5"


def test_ac1_a_marker_file_names_the_build(monkeypatch):
    """AC1. The marker file next to the package modules is read."""
    monkeypatch.delenv(BUILD_ENV, raising=False)
    folder = Path(__file__).resolve().parent / "_build_marker_tmp"
    folder.mkdir(exist_ok=True)
    try:
        (folder / BUILD_MARKER).write_text(SHA + "\n", encoding="utf-8")
        assert build_commit(folder) == SHA
        assert build_commit(str(folder)) == SHA
    finally:
        (folder / BUILD_MARKER).unlink(missing_ok=True)
        folder.rmdir()


def test_ac2_the_environment_value_wins(monkeypatch):
    """AC2. ESSAY_WRITER_BUILD labels one run, and spaces are trimmed."""
    folder = Path(__file__).resolve().parent / "_build_marker_tmp"
    folder.mkdir(exist_ok=True)
    try:
        (folder / BUILD_MARKER).write_text(SHA, encoding="utf-8")
        monkeypatch.setenv(BUILD_ENV, "  build-42  ")
        assert build_commit(folder) == "build-42"
    finally:
        (folder / BUILD_MARKER).unlink(missing_ok=True)
        folder.rmdir()
    monkeypatch.delenv(BUILD_ENV, raising=False)


def test_ac3_no_marker_is_an_empty_string(monkeypatch, tmp_path):
    """AC3. A copy with no marker reports empty and does not fail."""
    monkeypatch.delenv(BUILD_ENV, raising=False)
    assert build_commit(tmp_path) == ""
    assert BUILD_MARKER == "BUILD-COMMIT"


def test_ac4_health_reports_the_build_commit(monkeypatch, workspace):
    """AC4. essay.health carries build_commit, and it follows the environment."""
    monkeypatch.delenv(BUILD_ENV, raising=False)
    report = essay_health()
    assert report["ok"] is True
    assert isinstance(report["build_commit"], str)
    assert report["build_commit"] == build_commit()
    monkeypatch.setenv(BUILD_ENV, SHA)
    assert essay_health()["build_commit"] == SHA
    assert report["version"] == __version__ == "0.1.0"


def test_ac5_the_friend_docs_point_at_build_commit():
    """AC5. The update check names build_commit in both prompt copies and the workflow."""
    for name in ("FRIEND-PROMPT.txt", "src/essay_writer/FRIEND-PROMPT.txt"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "`build_commit`" in text
        assert "commit this copy was built from" in text
        assert "when the zip includes" in text.casefold()
    for name in ("FIRST-RUN.txt", "src/essay_writer/FIRST-RUN.txt"):
        text = (REPO / name).read_text(encoding="utf-8")
        assert "`build_commit`" in text
        assert "when the zip includes" in text.casefold()
    workflow = (REPO / "docs" / "workflow.md").read_text(encoding="utf-8")
    assert "`build_commit`" in workflow
    assert "CHANGELOG" in workflow
    assert "when the zip includes" in workflow.casefold()
