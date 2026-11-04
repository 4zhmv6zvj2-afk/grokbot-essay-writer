"""Student chat paths and speech locks."""

from pathlib import Path

from docx import Document
from helpers import ESSAY, TOPIC, open_sequence, source, write_upload

from essay_writer.doors import DOORS
from essay_writer.paths import student_chat_path
from essay_writer.research import essay_research_summary
from essay_writer.server import INSTRUCTIONS
from essay_writer.stage_llm import stage_settings
from essay_writer.student_voice import say, speak
from essay_writer.writing_basics import CHECKLIST_WALK, MCP_DOWN_SPEECH

JOURNAL_TEXT = (
    "Smith, J. (2020) Chokepoints and crude. Maritime Policy 12(3) pp. 4-9. doi:10.1000/strait\n"
    "The Strait handles a large share of flows.\n"
)


def _docx(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def test_student_chat_path_never_shows_tilde_internal_volume_or_ssd(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/student")
    monkeypatch.setattr(Path, "home", lambda: Path("/Users/student"))
    assert "~/" not in student_chat_path("~/Documents/Essays/MOD1004AA")
    assert student_chat_path("~/Documents/Essays/MOD1004AA") == "Documents/Essays/MOD1004AA"
    assert student_chat_path("/Users/student/Documents/work") == "Documents/work"
    assert student_chat_path("/Users/student/my-app") == "/Users/student/my-app"
    assert "ResearchDrive" not in student_chat_path("/Volumes/ResearchDrive/out/essay.docx")
    assert student_chat_path("/Volumes/ResearchDrive/out/essay.docx") == "a folder you named on this computer"
    assert student_chat_path("/Volumes/ArchiveDrive/app") == "a folder you named on this computer"
    spoken = say("Save copies under ~/Documents/zips and /Volumes/ResearchDrive/out.zip")
    assert "~/" not in spoken
    assert "ResearchDrive" not in spoken
    assert "Documents/zips" in spoken


def test_speak_scrubs_path_fields(monkeypatch):
    monkeypatch.setenv("HOME", "/Users/student")
    body = speak(
        {
            "ok": True,
            "app_path": "/Volumes/ResearchDrive/app",
            "localPaths": ["~/Documents/paper.zip"],
        }
    )
    assert body["app_path"] == "a folder you named on this computer"
    assert body["localPaths"] == ["Documents/paper.zip"]


def test_checklist_walk_and_instructions_carry_path_speech():
    assert "Student chat never shows ~/…" in CHECKLIST_WALK
    assert MCP_DOWN_SPEECH in INSTRUCTIONS
    assert "hand-write annotation.docx" in INSTRUCTIONS
    assert "option C: Download leftovers first" in INSTRUCTIONS
    overlay_4a = stage_settings("4a")["prompt_overlay"]
    assert "leftovers only" in overlay_4a.casefold()
    assert "speech only" in overlay_4a
    overlay_4b = stage_settings("4b")["prompt_overlay"]
    assert "option C: Download leftovers first" in overlay_4b
    overlay_5 = stage_settings("5")["prompt_overlay"]
    assert "Do not set the conclusion label" in overlay_5
    assert "independent re-review" in overlay_5.casefold()
    summary = next(door["description"] for door in DOORS if door["tool"] == "essay.research.summary")
    assert "leftovers only" in summary.casefold()


def test_4a_download_list_is_leftovers_not_annotation_repeat(workspace):
    write_upload(workspace, text=JOURNAL_TEXT)
    seq = open_sequence()
    ann = (
        "Smith (2020) argues the corridor is narrow. "
        'The paper says "The Strait handles a large share of flows."'
    )
    row = source()
    row["annotation"] = ann
    essay_research_summary(seq, TOPIC, "draft", [row])
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [row])
    assert confirmed["stored"] is True
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    listed = _docx(folder / "download-list.docx")
    assert "Leftovers only" in listed
    assert "Still needs a PDF" in listed
    assert "Chokepoints and crude" in listed
    assert "Annotated bibliography" not in listed
    assert "No failed download is waiting" not in listed
    assert "listed in the annotation" not in listed.casefold()
