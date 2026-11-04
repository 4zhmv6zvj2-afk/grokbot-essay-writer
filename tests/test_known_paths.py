"""#1 known paths — ResearchDrive research stays on the allowlist."""

import json
from pathlib import Path

from helpers import ESSAY, OTHER, open_sequence

from essay_writer.known_paths import (
    KNOWN_PATHS_LINE,
    RESEARCH_STAGES,
    allow_research_path,
    guard_write_door,
    is_roam_root,
    repo_root,
)
from essay_writer.research_packs import gathered_pdfs, reconcile_before_4b
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import student_surface_hits

REPO = Path(__file__).resolve().parents[1]
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def test_research_overlays_carry_the_allowlist():
    assert "code checkout" in KNOWN_PATHS_LINE
    assert "Essay-writer/<module>/" in KNOWN_PATHS_LINE
    assert "uploads/<module>/" in KNOWN_PATHS_LINE
    assert "download list" in KNOWN_PATHS_LINE
    assert "known project file" in KNOWN_PATHS_LINE
    assert "local subject notes" in KNOWN_PATHS_LINE
    assert "Do not search the home folder, whole Documents, or whole Volumes" in KNOWN_PATHS_LINE
    assert "Do not invent a student folder path." in KNOWN_PATHS_LINE
    assert "not a student save" in KNOWN_PATHS_LINE
    for stage in RESEARCH_STAGES:
        item = stage_settings(stage)
        assert KNOWN_PATHS_LINE in item["prompt_overlay"]
        assert KNOWN_PATHS_LINE in item["rules"]
        assert student_surface_hits(item["prompt_overlay"]) == []
        assert student_surface_hits(item["rules"]) == []
    assert KNOWN_PATHS_LINE not in stage_settings("5")["prompt_overlay"]
    assert KNOWN_PATHS_LINE not in stage_settings("10")["prompt_overlay"]

    blocked = guard_write_door(repo_root() / "src" / "essay_writer" / "known_paths.py")
    assert blocked is not None
    assert blocked["refused"] == "repo-not-save"


def test_allowlist_accepts_known_paths_and_refuses_the_rest(workspace, tmp_path):
    seq = open_sequence()
    code = repo_root() / "src" / "essay_writer" / "known_paths.py"
    reading = allow_research_path(seq, str(code))
    assert reading["allowed"] is True
    assert reading["kind"] == "repo"
    saving = allow_research_path(seq, str(code), save=True)
    assert saving["allowed"] is False
    assert saving["kind"] == "repo-not-save"

    workflow = workspace / "Essay-writer" / ESSAY / "brief.md"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("brief", encoding="utf-8")
    assert allow_research_path(seq, str(workflow))["kind"] == "workflow"

    upload = workspace / "uploads" / ESSAY / "paper.pdf"
    upload.parent.mkdir(parents=True, exist_ok=True)
    upload.write_bytes(PDF)
    assert allow_research_path(seq, f"uploads/{ESSAY}/paper.pdf")["kind"] == "uploads"
    assert gathered_pdfs(seq, [{"locator": f"uploads/{ESSAY}/paper.pdf"}]) == [upload.resolve()]

    kb1 = workspace / "KB1" / ESSAY / "note.md"
    kb1.parent.mkdir(parents=True)
    kb1.write_text("note", encoding="utf-8")
    assert allow_research_path(seq, str(kb1))["kind"] == "kb1"
    kb1_essay = workspace / "KB1" / "Essay-writer" / ESSAY / "note.md"
    kb1_essay.parent.mkdir(parents=True)
    kb1_essay.write_text("note", encoding="utf-8")
    assert allow_research_path(seq, str(kb1_essay))["kind"] == "kb1"
    other_kb1 = workspace / "KB1" / OTHER / "note.md"
    other_kb1.parent.mkdir(parents=True)
    other_kb1.write_text("note", encoding="utf-8")
    assert allow_research_path(seq, str(other_kb1))["allowed"] is False

    named = tmp_path / "Documents" / "behind-the-runway.pdf"
    named.parent.mkdir()
    named.write_bytes(PDF)
    stray = named.parent / "other-runway-paper.pdf"
    stray.write_bytes(PDF)
    state = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "download-run.json"
    state.write_text(
        json.dumps(
            {
                "attempts": {},
                "seen_urls": [],
                "failures": [
                    {
                        "url": "https://example.test/runway",
                        "title": "Behind the runway",
                        "path": str(named),
                    }
                ],
                "papers": [],
            }
        ),
        encoding="utf-8",
    )
    listed = allow_research_path(seq, str(named))
    assert listed["allowed"] is True
    assert listed["kind"] == "listed"
    assert allow_research_path(seq, str(stray))["kind"] == "invented"
    assert gathered_pdfs(seq, [{"locator": str(stray)}]) == []

    invented = tmp_path / "StudentEssays" / "paper.pdf"
    invented.parent.mkdir()
    invented.write_bytes(PDF)
    assert allow_research_path(seq, str(invented))["kind"] == "invented"

    for raw in (Path.home(), Path.home() / "Documents", Path("/Volumes"), Path("/Volumes/ResearchDrive")):
        assert is_roam_root(raw) is True
        refused = allow_research_path(seq, str(raw))
        assert refused["allowed"] is False
        assert refused["kind"] == "roam"


def test_reconcile_does_not_search_home_documents_or_volumes(workspace, monkeypatch):
    seq = open_sequence()
    walked: list[Path] = []
    real_rglob = Path.rglob

    def tracking(self: Path, pattern: str):
        walked.append(self)
        if is_roam_root(self):
            raise AssertionError(f"searched {self}")
        return real_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", tracking)
    report = reconcile_before_4b(seq, documents=Path.home() / "Documents")
    assert report["checked"] == "disk-and-documents"
    assert report["matched"] == []
    assert all(not is_roam_root(path) for path in walked)
    reconcile_before_4b(seq, documents=Path("/Volumes"))
    assert all(not is_roam_root(path) for path in walked)
