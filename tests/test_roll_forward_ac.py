"""Roll-forward parent to child. Stable ids: AC1–AC9.

Open and closed parents both start the child on stage 1. Stages 1–3 run
again. A dropped PDF leaves the list only. Research and papers stay, and
the old final is parked under reference/. Stage 4a researches first, then
keep, drop, or replace. Stage 4b is skipped only when every keeper already
has a critical note. Keepers are not dug again and are not re-listed.
Engagement and the marking table stay as they were.

Build covered: Cursor and Grok Build share essay.sequence.new, essay.stage,
and the roll-forward helpers those doors call.
"""

import inspect
import json
from pathlib import Path

from helpers import picked

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.diary import extract_marking_table
from essay_writer.dig import essay_dig
from essay_writer.free_alt import leftover_addresses
from essay_writer.paths import sequence_dir, uploads_dir, work_dir
from essay_writer.projects import (
    essay_sequence_new,
    save_sequence_state,
    sequence_id,
)
from essay_writer.shells import cursor_shell, front_office
from essay_writer.specialists.eqr import engagement_misses
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.writing_basics import STAGE_ORDER

MODULE = "MOD2002AA"
LOOK = "The task is a short report."
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
KEEPER_DOI = "10.1000/keeper"
KEEPER_TITLE = "Keeper paper on ports"
KEEPER_URL = "https://files.example.test/keeper.pdf"
KEEPER_OA = "https://oa.example.test/keeper-oa"
OTHER_DOI = "10.1000/other"
BRIEF = """
Module code: MOD2002AA

Word count: 1500-2000 words.

## Marking criteria

| Criterion | High distinction |
| Argument | A clear line |
"""


def _pointer_path(module: str, number: int) -> Path:
    return sequence_dir(module, number) / "tracking" / "stage.json"


def _write_pointer(module: str, number: int, pointer: dict) -> None:
    path = _pointer_path(module, number)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")


def _state(module: str, number: int, *, topic: str = "ports") -> None:
    save_sequence_state(
        module,
        number,
        {
            "essay_id": sequence_id(module, number),
            "sequence": number,
            "sequence_id": sequence_id(module, number),
            "research": {"summary": {"topic": topic, "sources": []}, "full": None},
            "validations": {},
            "word": {},
            "revisions": [],
            "shelf": {},
        },
    )


def _open(module: str, parent: str | None = None) -> dict:
    draft = essay_sequence_new(module, "draft", parent)
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm", parent)
    assert opened["ok"] is True, opened
    return opened


def _paper_row(module: str) -> dict:
    return {
        "url": KEEPER_URL,
        "path": f"uploads/{module}/keeper.pdf",
        "doi": KEEPER_DOI,
        "title": KEEPER_TITLE,
        "bucket": "paper",
    }


def _plant_paper(module: str, number: int) -> Path:
    folder = uploads_dir(sequence_id(module, number))
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / "keeper.pdf"
    pdf.write_bytes(PDF)
    run = sequence_dir(module, number) / "download-run.json"
    run.write_text(
        json.dumps({"papers": [_paper_row(module)], "failures": [], "seen_urls": []}) + "\n",
        encoding="utf-8",
    )
    return pdf


def _plant_final(module: str, number: int) -> None:
    from docx import Document

    def write(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        document = Document()
        document.add_paragraph("parent-final-word")
        document.save(str(path))

    write(sequence_dir(module, number) / "output" / f"{module}-10" / f"{module}-final.docx")
    write(sequence_dir(module, number) / "output" / f"{sequence_id(module, number)}.docx")


def _mac_copies(mac: Path, module: str, parent: str) -> list[Path]:
    paths = [
        mac / module / "shared" / "keeper.pdf",
        mac / module / parent / "keeper.pdf",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PDF)
    return paths


def _set_stage(seq: str, current: str, saved: list[str]) -> None:
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "current": current,
                "saved": saved,
                "files": {},
                "closed": False,
                "revision": 3,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _note(seq: str, paper_id: str, text: str) -> None:
    folder = work_dir(seq) / "output" / "reviews"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{paper_id}.md").write_text(text, encoding="utf-8")


def _watch(monkeypatch):
    calls: list[str] = []

    def fake(essay_id, stage, launch=None):
        calls.append(stage)
        return {
            "started": True,
            "status": ["started"],
            "runner": "test",
            "command": ["test"],
            "reason": "",
            "heartbeat_seconds": 300,
        }

    monkeypatch.setattr("essay_writer.cursor_office.start_stage_mid", fake)
    monkeypatch.setattr(
        "essay_writer.cursor_office.start_4a_research",
        lambda essay_id, launch=None: fake(essay_id, "4a", launch),
    )
    return calls


def test_ac1_open_or_closed_parent_resets_to_stage_1(workspace):
    """AC1. The child is a real stage 1 run. The writing pointer is not inherited."""
    closed = "MOD2002AA"
    _state(closed, 1)
    saved = list(STAGE_ORDER)
    _write_pointer(
        closed,
        1,
        {
            "current": "10",
            "saved": saved,
            "files": {stage: f"tracking/{stage}.md" for stage in saved},
            "closed": True,
            "chain_armed": True,
            "waiting_stage": "10",
            "waiting_digest": "a" * 64,
        },
    )
    before = _pointer_path(closed, 1).read_bytes()
    opened = _open(closed, sequence_id(closed, 1))
    child = opened["sequence_id"]
    fresh = load_pointer(child)
    assert fresh["current"] == "1"
    assert fresh["saved"] == []
    assert fresh["files"] == {}
    assert fresh["closed"] is False
    assert fresh["chain_armed"] is False
    assert fresh["waiting_stage"] is None
    assert fresh["waiting_digest"] is None
    assert _pointer_path(closed, 1).read_bytes() == before

    module = "MOD2001AA"
    _state(module, 1)
    _write_pointer(
        module,
        1,
        {
            "current": "3",
            "saved": ["1", "2"],
            "files": {"1": "tracking/1.md"},
            "closed": False,
            "chain_armed": False,
            "waiting_stage": "3",
            "waiting_digest": "b" * 64,
        },
    )
    parent_before = _pointer_path(module, 1).read_bytes()
    opened = _open(module, sequence_id(module, 1))
    child = opened["sequence_id"]
    fresh = load_pointer(child)
    assert fresh["current"] == "1"
    assert fresh["saved"] == []
    assert fresh["files"] == {}
    assert fresh["closed"] is False
    assert fresh["waiting_digest"] is None
    assert load_pointer(sequence_id(module, 1))["current"] == "3"
    assert load_pointer(sequence_id(module, 1))["saved"] == ["1", "2"]
    assert _pointer_path(module, 1).read_bytes() == parent_before


def test_ac2_stages_1_to_3_rerun_from_the_first_card(workspace):
    """AC2. Tracking for stages 1–3 is cleared. The first card is stage 1."""
    _state(MODULE, 1)
    _write_pointer(
        MODULE,
        1,
        {"current": "4a", "saved": ["1", "2", "3"], "files": {}, "closed": False},
    )
    for stage in ("1", "2", "3"):
        note = sequence_dir(MODULE, 1) / "tracking" / f"{stage}.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(f"# Stage {stage}\n\nStatus: final\n\n## Final look\n\nSaved.\n", encoding="utf-8")
    opened = _open(MODULE, sequence_id(MODULE, 1))
    child = opened["sequence_id"]
    for stage in ("1", "2", "3"):
        assert not (work_dir(child) / "tracking" / f"{stage}.md").exists()
    assert load_pointer(child)["current"] == "1"
    assert load_pointer(child)["saved"] == []
    draft = essay_stage(child, "1", "draft", LOOK)
    assert draft["ok"] is True, draft
    assert draft["stage"] == "1"
    assert draft["current"] == "1"
    assert draft["card"]["stage"] == "1"
    assert draft["card"]["essay_id"] == child
    blocked = essay_stage(child, "2", "draft", LOOK)
    assert blocked["ok"] is False
    assert "The current stage is 1" in str(blocked.get("reason", ""))


def test_ac3_drop_unlists_the_pdf_and_keeps_the_file(workspace, monkeypatch, tmp_path):
    """AC3. Drop removes the list row. The PDF stays in uploads and on the Mac."""
    mac = tmp_path / "mac"
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(mac))
    _state(MODULE, 1)
    pdf = _plant_paper(MODULE, 1)
    parent = sequence_id(MODULE, 1)
    mac_files = _mac_copies(mac, MODULE, parent)
    parent_list = (sequence_dir(MODULE, 1) / "download-run.json").read_bytes()
    opened = _open(MODULE, parent)
    child = opened["sequence_id"]
    dropped = essay_stage(child, "4a", paperChoice={"paper": KEEPER_DOI, "choice": "drop"})
    assert dropped["ok"] is True, dropped
    assert dropped["unlisted"] is True
    assert dropped["file_kept"] is True
    assert dropped["paper"]["path"] == f"uploads/{MODULE}/keeper.pdf"
    assert pdf.read_bytes() == PDF
    for path in mac_files:
        assert path.read_bytes() == PDF
    listed = json.loads((work_dir(child) / "download-run.json").read_text(encoding="utf-8"))
    assert listed["papers"] == []
    assert (sequence_dir(MODULE, 1) / "download-run.json").read_bytes() == parent_list


def test_ac4_research_and_papers_stay_and_the_final_is_parked(workspace):
    """AC4. Research and the PDF stay. The old final moves under reference/."""
    _state(MODULE, 1, topic="ports")
    pdf = _plant_paper(MODULE, 1)
    _plant_final(MODULE, 1)
    _write_pointer(MODULE, 1, {"current": "10", "saved": list(STAGE_ORDER), "files": {}, "closed": True})
    opened = _open(MODULE, sequence_id(MODULE, 1))
    child = opened["sequence_id"]
    state = json.loads((work_dir(child) / "state.json").read_text(encoding="utf-8"))
    assert state["research"]["summary"]["topic"] == "ports"
    assert pdf.read_bytes() == PDF
    listed = json.loads((work_dir(child) / "download-run.json").read_text(encoding="utf-8"))
    assert listed["papers"][0]["path"] == f"uploads/{MODULE}/keeper.pdf"
    assert listed["papers"][0]["doi"] == KEEPER_DOI
    parked = work_dir(child) / "reference" / f"{MODULE}-final.docx"
    parent_final = sequence_dir(MODULE, 1) / "output" / f"{MODULE}-10" / f"{MODULE}-final.docx"
    assert parked.is_file()
    assert parked.read_bytes() == parent_final.read_bytes()
    assert not (work_dir(child) / "output" / f"{MODULE}-10" / f"{MODULE}-final.docx").exists()
    assert parent_final.is_file()


def test_ac5_stage_4a_researches_before_keep_drop_replace(workspace, monkeypatch):
    """AC5. Research starts first. Keep reuses the paper. Confirm waits for a choice."""
    calls = _watch(monkeypatch)
    _state(MODULE, 1)
    _plant_paper(MODULE, 1)
    _write_pointer(MODULE, 1, {"current": "4a", "saved": ["1", "2", "3"], "files": {}, "closed": False})
    opened = _open(MODULE, sequence_id(MODULE, 1))
    child = opened["sequence_id"]
    _set_stage(child, "4a", ["1", "2", "3"])
    draft = essay_stage(child, "4a", "draft", LOOK)
    assert draft["ok"] is True, draft
    assert calls[0] == "4a"
    order = draft["roll_forward"]["order"]
    assert order == ["research", "keep-drop-replace"]
    assert draft["roll_forward"]["research_first"] is True
    assert draft["roll_forward"]["reuse_ok"] is True
    assert draft["roll_forward"]["papers"][0]["doi"] == KEEPER_DOI
    blocked = essay_stage(child, "4a", "confirm", LOOK, **picked(draft))
    assert blocked["ok"] is False, blocked
    assert blocked["refused"] == "papers"
    kept = essay_stage(child, "4a", paperChoice={"paper": KEEPER_URL, "choice": "keep"})
    assert kept["ok"] is True, kept
    assert kept["unlisted"] is False
    assert kept["paper"]["path"] == f"uploads/{MODULE}/keeper.pdf"
    assert kept["paper"]["doi"] == KEEPER_DOI
    assert kept["paper"]["url"] == KEEPER_URL
    listed = json.loads((work_dir(child) / "download-run.json").read_text(encoding="utf-8"))
    assert listed["papers"][0]["url"] == KEEPER_URL


def test_ac6_4b_skips_only_when_every_keeper_has_notes(workspace, monkeypatch):
    """AC6. Missing notes, or a replacement, still start 4b research."""
    calls = _watch(monkeypatch)
    _state(MODULE, 1)
    _plant_paper(MODULE, 1)
    _write_pointer(MODULE, 1, {"current": "1", "saved": [], "files": {}, "closed": False})
    child = _open(MODULE, sequence_id(MODULE, 1))["sequence_id"]
    essay_stage(child, "4a", paperChoice={"paper": KEEPER_DOI, "choice": "keep"})
    _set_stage(child, "4b", ["1", "2", "3", "4a"])
    missing = essay_stage(child, "4b", "draft", LOOK)
    assert missing["ok"] is True, missing
    assert missing["roll_forward_4b"] == "research"
    assert calls == ["4b"]

    noted = "MOD2001AA"
    _state(noted, 1)
    _plant_paper(noted, 1)
    _write_pointer(noted, 1, {"current": "1", "saved": [], "files": {}, "closed": False})
    ready = _open(noted, sequence_id(noted, 1))["sequence_id"]
    essay_stage(ready, "4a", paperChoice={"paper": KEEPER_DOI, "choice": "keep"})
    _note(ready, "keeper", f"Critical note: grok-4.7\n\n{KEEPER_TITLE}\n{KEEPER_DOI}\n")
    _set_stage(ready, "4b", ["1", "2", "3", "4a"])
    calls.clear()
    skipped = essay_stage(ready, "4b", "draft", LOOK)
    assert skipped["ok"] is True, skipped
    assert skipped["roll_forward_4b"] == "skip"
    assert calls == []

    replaced = "MOD2004AA"
    _state(replaced, 1)
    _plant_paper(replaced, 1)
    _write_pointer(replaced, 1, {"current": "1", "saved": [], "files": {}, "closed": False})
    other = _open(replaced, sequence_id(replaced, 1))["sequence_id"]
    essay_stage(other, "4a", paperChoice={"paper": KEEPER_DOI, "choice": "replace"})
    _note(other, "keeper", f"Critical note: grok-4.7\n\n{KEEPER_TITLE}\n{KEEPER_DOI}\n")
    _set_stage(other, "4b", ["1", "2", "3", "4a"])
    calls.clear()
    again = essay_stage(other, "4b", "draft", LOOK)
    assert again["ok"] is True, again
    assert again["roll_forward_4b"] == "research"
    assert calls == ["4b"]


def test_ac7_keepers_are_not_redug_or_relisted(workspace, monkeypatch):
    """AC7. A keeper stays off dig and off leftovers. DOI, title, URL, and path stay."""
    _state(MODULE, 1)
    _plant_paper(MODULE, 1)
    state_path = sequence_dir(MODULE, 1) / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["research"]["summary"]["sources"] = [
        {"id": "src-keeper", "doi": KEEPER_DOI, "title": KEEPER_TITLE, "url": KEEPER_OA}
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    run = json.loads((sequence_dir(MODULE, 1) / "download-run.json").read_text(encoding="utf-8"))
    run["failures"] = [{"url": KEEPER_OA, "doi": KEEPER_DOI, "title": KEEPER_TITLE, "bucket": "leftover"}]
    (sequence_dir(MODULE, 1) / "download-run.json").write_text(json.dumps(run), encoding="utf-8")
    _write_pointer(MODULE, 1, {"current": "1", "saved": [], "files": {}, "closed": False})
    child = _open(MODULE, sequence_id(MODULE, 1))["sequence_id"]
    before = json.loads((work_dir(child) / "roll-forward.json").read_text(encoding="utf-8"))
    essay_stage(child, "4a", paperChoice={"paper": KEEPER_DOI, "choice": "keep"})
    kept = json.loads((work_dir(child) / "roll-forward.json").read_text(encoding="utf-8"))["papers"][0]
    assert kept["doi"] == before["papers"][0]["doi"] == KEEPER_DOI
    assert kept["title"] == KEEPER_TITLE
    assert kept["url"] == KEEPER_URL
    assert kept["path"] == f"uploads/{MODULE}/keeper.pdf"

    def fake(url, headers=None):
        if "api.openalex.org" in url:
            return {
                "results": [
                    {
                        "title": KEEPER_TITLE,
                        "publication_year": 2020,
                        "doi": f"https://doi.org/{KEEPER_DOI}",
                        "authorships": [],
                    },
                    {
                        "title": "Other paper on ports",
                        "publication_year": 2021,
                        "doi": f"https://doi.org/{OTHER_DOI}",
                        "authorships": [],
                    },
                ]
            }
        if "api.unpaywall.org" in url:
            doi = KEEPER_DOI if KEEPER_DOI in url else OTHER_DOI
            oa = KEEPER_OA if doi == KEEPER_DOI else "https://oa.example.test/other"
            return {"best_oa_location": {"url_for_pdf": oa}}
        return {"results": []}

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "study@example.test")
    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    card = essay_dig(child, "ports", "draft")
    assert card["ok"] is True, card
    hits = card["card"]["openalex"]["hits"]
    assert [hit["doi"] for hit in hits] == [OTHER_DOI]
    assert all(item.get("doi") != KEEPER_DOI for item in card["card"]["unpaywall"])
    rows = leftover_addresses(child)
    assert all(item.get("doi") != KEEPER_DOI and item.get("url") != KEEPER_OA for item in rows)
    after = json.loads((work_dir(child) / "roll-forward.json").read_text(encoding="utf-8"))["papers"][0]
    assert after["doi"] == KEEPER_DOI
    assert after["title"] == KEEPER_TITLE
    assert after["url"] == KEEPER_URL
    assert after["path"] == f"uploads/{MODULE}/keeper.pdf"


def test_ac8_engagement_and_marking_table_stay(workspace):
    """AC8. Roll-forward does not rewrite the marking table or engagement asks."""
    module_dir = workspace / "Essay-writer" / MODULE
    module_dir.mkdir(parents=True)
    brief = module_dir / "brief.md"
    brief.write_text(BRIEF, encoding="utf-8")
    parent = sequence_id(MODULE, 1)
    _state(MODULE, 1)
    _write_pointer(MODULE, 1, {"current": "10", "saved": ["10"], "files": {}, "closed": True})
    table = extract_marking_table(parent)
    assert "High distinction" in table
    marking = module_dir / "marking-table.md"
    before_brief = brief.read_bytes()
    before_table = marking.read_bytes()
    asks = engagement_misses(parent, "A short opened file.")
    _open(MODULE, parent)
    assert brief.read_bytes() == before_brief
    assert marking.read_bytes() == before_table
    assert extract_marking_table(parent) == table
    assert engagement_misses(parent, "A short opened file.") == asks


def test_ac9_build_covered_cursor_and_grok_build_share_roll_forward():
    """AC9. One roll-forward path. Cursor and Grok Build do not keep a second copy."""
    assert cursor_shell()["handlers"]["essay.sequence.new"] is front_office()["handlers"]["essay.sequence.new"]
    assert cursor_shell()["handlers"]["essay.stage"] is front_office()["handlers"]["essay.stage"]
    from essay_writer.projects import clone_sequence as clone
    from essay_writer.stage_track import _attach_mid_run
    from essay_writer.stage_track import essay_stage as stage

    assert "shape_cloned_child" in inspect.getsource(clone)
    assert "four_b_action" in inspect.getsource(_attach_mid_run)
    assert "attach_stage_roll" in inspect.getsource(stage)
    assert "start_4a_research" in inspect.getsource(_attach_mid_run)
    for source in (inspect.getsource(stage_launch), inspect.getsource(cursor_stage_launch)):
        assert "shape_cloned_child" not in source
        assert "four_b_action" not in source
    assert "paperChoice" in inspect.getsource(stage)
