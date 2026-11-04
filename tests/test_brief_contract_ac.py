"""Batch 2 brief contract. Stable ids: AC-NT1, AC-NT2, AC-NT4.

#22 named parts and #27 title page share one assignment record.
A writing type with no mapping does not ride the essay or report contract.
"""

import inspect
import json
from pathlib import Path

from docx import Document
from helpers import ESSAY, pack, picked

from essay_writer.assignment_gate import read_assignment
from essay_writer.brief_contract import (
    CONTRACT_STAGES,
    FINDINGS_HOW_TO_SCORE_HIGH,
    FINDINGS_MARK_SCHEME,
    FINDINGS_NONE,
    MAPPED_TYPE_OVERLAY,
    REQUIRED_MAPPING_KEYS,
    UNMAPPED_REASON,
    UNNAMED_NOTE,
    register_mapping,
    stage_contract_refusal,
    unregister_mapping,
)
from essay_writer.diary import (
    blocked_identity_keys,
    entry_count,
    named_entries,
    section_plan_for,
    section_word_plan,
    title_page_spec,
)
from essay_writer.late_chain import write_stage10
from essay_writer.paths import essay_dir, work_dir
from essay_writer.projects import essay_sequence_new
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import POINTER_FILE, stage_settings, stage_title
from essay_writer.stage_track import _build_stage_body, _collect_stage_misses, essay_stage
from essay_writer.textutil import genre_from_brief_text
from essay_writer.word import cover_lines, essay_pack_render_word, write_docx

REPO = Path(__file__).resolve().parents[1]
TITLES = ("Quay watch", "Tide log", "Crane turn", "Gate count")
NUMBER = "102938"
NUMBERED = """
Assignment title: Individual reflective diary

Module title: Practice module
Module code: QUA9001HK

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and critically analyses it with theory and evidence.

Workshop topics
1. Quay watch
2. Tide log
3. Crane turn
4. Gate count

Each entry is about 500 words, plus or minus 10%.
The whole diary is 2,000 words, plus or minus 10%.

Title page: module title, module code, assignment title, registration number, and the word count.
The name stays off the title page and the file.

# Marking criteria/feedback form

| Criterion | 0-39 | 40-49 | 50-59 | 60-69 | 70+ |
| --- | --- | --- | --- | --- | --- |
| Clarity of the decisions | thin | partial | sound | clear | exact and evidenced |
"""
UNNAMED = """
Assignment title: Individual reflective diary

Aim: Understand the practice by reflecting on your own decisions.

Assignment task: Write four entries. Each entry names one decision and analyses it with theory.

The whole diary is 2,000 words, plus or minus 10%.
"""
COLON = (
    "Assignment title: Individual reflective diary\n"
    "Write four entries. Each entry names one decision and analyses it with theory.\n"
    "One entry for each occasion: North occasion, South occasion, East occasion, and West occasion.\n"
)
ESSAY_WITH_LIST = (
    "Genre: essay\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Workshop topics\n"
    "1. Quay watch\n"
    "2. Tide log\n"
    "3. Crane turn\n"
    "4. Gate count\n"
)
REPORT_WITH_LIST = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Workshop topics\n"
    "1. Quay watch\n"
    "2. Tide log\n"
    "3. Crane turn\n"
    "4. Gate count\n"
)
FIELDNOTE = """
Genre: fieldnote

Assignment title: Quay notes

Question: What did the quay show on that watch?

Title page: module title and registration number.
The name stays off.

Workshop topics
1. Quay watch
2. Tide log
3. Crane turn
4. Gate count
"""
ESSAY_ASKS = (
    "Genre: essay\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "Title page: student number.\n"
)
SCHEME = "High Distinction (80-100): evidenced\nPass (50-59): adequate\n"


def _open(module: str) -> str:
    draft = essay_sequence_new(module, "draft")
    assert draft["ok"] is True, draft
    opened = essay_sequence_new(module, "confirm")
    assert opened["ok"] is True, opened
    return opened["sequence_id"]


def _write_brief(module: str, text: str) -> None:
    folder = essay_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(text, encoding="utf-8")


def _save(seq: str, stage: str, look: str) -> dict:
    draft = essay_stage(seq, stage, "draft", look)
    assert draft["ok"] is True, draft
    if draft.get("stored") is True:
        return draft
    saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
    assert saved["ok"] is True and saved.get("stored") is True, saved
    return saved


def _look(seq: str, *extra: str) -> str:
    lines = list(basics_pass_lines(seq))
    lines.extend(extra)
    return "\n".join(lines)


def _titles_look(seq: str) -> str:
    return _look(seq, *TITLES, "These are the occasions in brief order.")


def _entry_look(seq: str) -> str:
    return _look(seq, "Entry 1 opens the diary.", "Entry 2 follows it.")


def _sections(body: str) -> list[dict[str, str]]:
    return [{"heading": title, "body": body} for title in TITLES]


def _quiet_spawn(command):
    return {"started": False, "reason": "test", "pid": None, "command": list(command)}


def _map_fieldnote(text: str, *, has_scheme: bool) -> dict:
    names = named_entries(text)
    count = entry_count(text)
    return {
        "named_entries": names,
        "named_by_brief": bool(names),
        "part_count": count,
        "unnamed_note": None if names or not count else UNNAMED_NOTE,
        "lock": "notes",
        "title_page": title_page_spec(text),
        "findings_opening": FINDINGS_MARK_SCHEME if has_scheme else FINDINGS_NONE,
    }


def test_ac_nt1_brief_record_stages_and_unnamed(workspace, monkeypatch):
    """AC-NT1. One record. Unnamed parts say so. Essay and report stay their locks.

    A third type with no mapping fails closed. A thin mapping fails closed.
    A complete mapping fills the record and is not an essay thesis.
    """
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _quiet_spawn)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _quiet_spawn)

    _write_brief("UNM9001HK", UNNAMED)
    unnamed = _open("UNM9001HK")
    seen = read_assignment(unnamed)
    assert seen["mapped"] is True
    assert seen["lock"] == "entries"
    assert seen["named_entries"] == []
    assert seen["named_by_brief"] is False
    assert seen["part_count"] == 4
    assert seen["unnamed_note"] == UNNAMED_NOTE
    plan = section_plan_for(unnamed)
    assert plan["mapped"] is True
    assert [row["name"] for row in plan["sections"]] == ["Entry 1", "Entry 2", "Entry 3", "Entry 4"]
    assert plan["unnamed_note"] == UNNAMED_NOTE
    assert plan["named_by_brief"] is False
    assert stage_contract_refusal(unnamed, "2", "Entry 1 is unnamed.") is None
    _save(unnamed, "1", _look(unnamed))
    stored = _save(unnamed, "2", _look(unnamed, "Entry 1 is the first unnamed part."))
    assert stored["stored"] is True

    _write_brief("ESS9001HK", ESSAY_WITH_LIST)
    essay = _open("ESS9001HK")
    essay_seen = read_assignment(essay)
    assert essay_seen["lock"] == "thesis"
    assert essay_seen["named_entries"] == []
    assert essay_seen["writing_type"] == "essay"
    assert section_plan_for(essay)["sections"] == []
    assert stage_contract_refusal(essay, "2", _look(essay)) is None
    assert "thesis" in stage_settings("2", "essay")["prompt_overlay"]
    _save(essay, "1", _look(essay))
    assert _save(essay, "2", _look(essay, "The thesis answers the question."))["stored"] is True

    _write_brief("REP9001HK", REPORT_WITH_LIST)
    report = _open("REP9001HK")
    report_seen = read_assignment(report)
    assert report_seen["lock"] == "purpose_and_scope"
    assert report_seen["named_entries"] == []
    assert section_plan_for(report)["sections"] == []
    assert "purpose and scope" in stage_settings("2", "report")["prompt_overlay"]

    _write_brief(ESSAY, "Genre: essay\nQuestion: Should the council publish the figure?\n")
    (essay_dir(ESSAY) / "mark-scheme.md").write_text(SCHEME, encoding="utf-8")
    scheme_essay = _open(ESSAY)
    assert read_assignment(scheme_essay)["findings_opening"] == FINDINGS_MARK_SCHEME

    _write_brief("FLD9001HK", FIELDNOTE)
    field = _open("FLD9001HK")
    assert genre_from_brief_text(FIELDNOTE) == "fieldnote"
    closed = read_assignment(field)
    assert closed["mapped"] is False
    assert closed["ok"] is False
    assert closed["lock"] is None
    assert closed["named_entries"] == []
    assert closed["title_page"] is None
    assert closed["findings_opening"] is None
    assert closed["reason"] == UNMAPPED_REASON
    assert "thesis" not in (closed.get("lock") or "")
    for stage in ("2", "3", "5"):
        held = stage_contract_refusal(field, stage, _look(field))
        assert held is not None and held["refused"] == "brief-mapping"
    refused = essay_stage(field, "1", "draft", _look(field))
    assert refused["ok"] is False
    if refused["refused"] == "misses":
        assert any(item["code"] == "brief-mapping" for item in refused["misses"])
        assert UNMAPPED_REASON in refused["reason"]
    else:
        assert refused["refused"] == "brief-mapping"
        assert refused["reason"] == UNMAPPED_REASON
    overlay = stage_settings("2", "fieldnote")["prompt_overlay"]
    assert overlay == UNMAPPED_REASON
    assert "An essay thesis answers" not in overlay
    assert "Establish purpose and scope" not in overlay
    assert stage_title("2", "fieldnote") == "Brief mapping missing"
    assert section_plan_for(field)["mapped"] is False
    assert section_plan_for(field)["sections"] == []
    bare = {"essay_id": field, "title": "Quay notes", "sections": _sections("A note.")}
    word = essay_pack_render_word(field, bare, "confirm", stage="9")
    assert word["ok"] is False
    assert word["refused"] == "brief-mapping"
    assert word.get("wrote") is not True

    def _thin(text: str, *, has_scheme: bool) -> dict:
        return {"lock": "notes"}

    register_mapping("fieldnote", _thin)
    try:
        thin = read_assignment(field)
        assert thin["mapped"] is False
        assert thin["reason"] == UNMAPPED_REASON
        for key in REQUIRED_MAPPING_KEYS:
            assert key
    finally:
        unregister_mapping("fieldnote")

    register_mapping("fieldnote", _map_fieldnote)
    try:
        opened = read_assignment(field)
        assert opened["mapped"] is True
        assert opened["writing_type"] == "fieldnote"
        assert opened["lock"] == "notes"
        assert opened["lock"] != "thesis"
        assert opened["named_entries"] == list(TITLES)
        assert opened["title_page"]["registration"] is True
        assert opened["title_page"]["name"] == "forbidden"
        assert opened["findings_opening"] == FINDINGS_NONE
        assert stage_settings("2", "fieldnote")["prompt_overlay"] == MAPPED_TYPE_OVERLAY
        assert stage_title("2", "fieldnote") == "Establish the lock"
        assert "An essay thesis answers" not in stage_settings("2", "fieldnote")["rules"]
        followed = section_plan_for(field)
        assert [row["name"] for row in followed["sections"]] == list(TITLES)
        same = read_assignment(field)
        assert same["named_entries"] == opened["named_entries"]
        assert same["title_page"] == opened["title_page"]
        assert same["findings_opening"] == opened["findings_opening"]
    finally:
        unregister_mapping("fieldnote")


def test_ac_nt2_named_entries_shapes(workspace, monkeypatch):
    """AC-NT2 and #22. Colon, bullets, and numbered lists. Entry N is refused."""
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _quiet_spawn)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _quiet_spawn)
    assert CONTRACT_STAGES == frozenset({"2", "3", "5"})
    assert "_collect_stage_misses" in inspect.getsource(_build_stage_body)
    assert "stage_contract_refusal" in inspect.getsource(_collect_stage_misses)

    assert named_entries(COLON) == [
        "North occasion",
        "South occasion",
        "East occasion",
        "West occasion",
    ]
    assert named_entries(
        "Occasions\n- Quay watch\n- Tide log\n- Crane turn\n- Gate count\n"
    ) == list(TITLES)
    assert named_entries(
        "Entries\n* Quay watch\n* Tide log\n* Crane turn\n* Gate count\n"
    ) == list(TITLES)
    assert named_entries(
        "Sections:\n1) Quay watch\n2) Tide log\n3) Crane turn\n4) Gate count\n"
    ) == list(TITLES)
    assert named_entries(
        "Entries to cover\n1. Quay watch\n2. Tide log\n\nThis sentence is not an entry.\n"
    ) == ["Quay watch", "Tide log"]
    assert named_entries("Workshop topics\n1. Quay watch\n# Marking criteria\n") == ["Quay watch"]
    assert named_entries(ESSAY_WITH_LIST) == list(TITLES)
    assert "PBS5001" not in NUMBERED
    assert "Mathie" not in NUMBERED

    text_plan = section_word_plan(NUMBERED)
    assert [row["name"] for row in text_plan["sections"]] == list(TITLES)
    assert text_plan["named_by_brief"] is True
    assert text_plan["unnamed_note"] is None
    assert all(row["limit"] == 500 for row in text_plan["sections"])

    _write_brief("QUA9001HK", NUMBERED)
    seq = _open("QUA9001HK")
    seen = read_assignment(seq)
    assert seen["named_entries"] == list(TITLES)
    assert seen["named_by_brief"] is True
    assert seen["findings_opening"] == FINDINGS_HOW_TO_SCORE_HIGH
    assert seen["lock"] == "entries"
    plan = section_plan_for(seq)
    assert [row["name"] for row in plan["sections"]] == list(TITLES)
    assert plan["sections"][0]["limit"] == 500

    _save(seq, "1", _look(seq))
    early = essay_stage(seq, "2", "draft", _entry_look(seq))
    assert early["ok"] is False
    assert early["refused"] == "named-parts"
    assert "Quay watch" in early["reason"]
    assert early.get("stored") is not True
    _save(seq, "2", _titles_look(seq))
    stage3 = essay_stage(seq, "3", "draft", _entry_look(seq))
    assert stage3["refused"] == "named-parts"
    _save(seq, "3", _titles_look(seq))

    pointer = work_dir(seq) / POINTER_FILE
    data = json.loads(pointer.read_text(encoding="utf-8"))
    data["current"] = "5"
    pointer.write_text(json.dumps(data), encoding="utf-8")
    stage5 = essay_stage(seq, "5", "draft", _entry_look(seq))
    assert stage5["ok"] is False
    assert stage5["refused"] == "named-parts"
    accepted = essay_stage(
        seq,
        "5",
        "draft",
        _titles_look(seq)
        + "\n# Quay watch\nOne decision was to wait, and the theory still applies.\n"
        + "# Tide log\nA later decision used the same evidence.\n"
        + "# Crane turn\nThe third decision stayed with the brief.\n"
        + "# Gate count\nThe last decision closed the watch.\n",
    )
    assert accepted["ok"] is True, accepted
    assert accepted.get("stored") is True

    entry_pack = {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "noted",
        "registration_number": NUMBER,
        "sections": [
            {"heading": "Entry 1", "body": "A decision."},
            {"heading": "Entry 2", "body": "A decision."},
            {"heading": "Entry 3", "body": "A decision."},
            {"heading": "Entry 4", "body": "A decision."},
        ],
    }
    headings = essay_pack_render_word(seq, entry_pack, "confirm", stage="6")
    assert headings["ok"] is False
    assert headings["refused"] == "named-parts"
    assert headings.get("wrote") is not True
    target = work_dir(seq) / "output" / f"{seq}.docx"
    assert not target.is_file()

    good = dict(entry_pack)
    good["registration_number"] = NUMBER
    good["sections"] = _sections(
        "Format reflective diary. "
        "Understand the practice by reflecting on your own decisions. "
        "Each entry names one decision and critically analyses it with theory and evidence. "
        "70+."
    )
    preview = essay_pack_render_word(seq, good, "draft", stage="6")
    assert preview.get("refused") not in {"named-parts", "title-page"}
    assert [heading for heading in preview.get("headings") or []] == list(TITLES)


def test_ac_nt4_title_page_identity(workspace, monkeypatch):
    """AC-NT4 and #27. Missing registration is refused. One cover for 6, 7, and final."""
    monkeypatch.setattr("essay_writer.cursor_office.spawn_agent", _quiet_spawn)
    monkeypatch.setattr("essay_writer.build_office.spawn_grok", _quiet_spawn)
    assert "102938" not in (REPO / "src" / "essay_writer" / "brief_contract.py").read_text(encoding="utf-8")
    assert "102938" not in (REPO / "src" / "essay_writer" / "diary.py").read_text(encoding="utf-8")
    assert "cover_lines(" in inspect.getsource(write_docx)
    assert "cover_lines(" in inspect.getsource(essay_pack_render_word)
    assert "write_docx(" in inspect.getsource(write_stage10)
    assert "copy2" not in inspect.getsource(write_stage10)
    assert not hasattr(write_stage10, "stage10_cover")

    _write_brief("QUA9001HK", NUMBERED)
    seq = _open("QUA9001HK")
    seen = read_assignment(seq)
    assert seen["title_page"]["registration"] is True
    assert seen["title_page"]["name"] == "forbidden"
    assert "registration" in seen["title_page"]["fields"]
    body = (
        "Format reflective diary. "
        "Understand the practice by reflecting on your own decisions. "
        "Each entry names one decision and critically analyses it with theory and evidence. "
        "70+."
    )
    empty = {
        "essay_id": seq,
        "title": "Individual reflective diary",
        "referencing": "harvard",
        "assessment": "Individual reflective diary",
        "module_title": "Practice module",
        "conclusion": "noted",
        "sections": _sections(body),
    }
    target = work_dir(seq) / "output" / f"{seq}.docx"
    reasons = set()
    for stage in ("6", "7", "9"):
        refused = essay_pack_render_word(seq, empty, "confirm", stage=stage)
        assert refused["ok"] is False, refused
        assert refused["refused"] == "title-page"
        assert "registration number" in refused["reason"]
        assert "invented" in refused["reason"]
        assert refused.get("wrote") is not True
        reasons.add(refused["reason"])
        assert not target.is_file()
    assert len(reasons) == 1

    filled = dict(empty)
    filled["registration_number"] = NUMBER
    report = {
        "title": "Individual reflective diary",
        "word_count": {"counted": 40, "stated": 2000},
        "sections": filled["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }
    lines = cover_lines(seq, filled, report)
    joined = "\n".join(lines)
    assert f"Registration number: {NUMBER}" in joined
    assert "Practice module" in joined
    assert "QUA9001HK" in joined
    assert "Teaching partner" not in joined
    assert "PROG01" not in joined
    assert "Conclusion:" not in joined
    named = dict(filled)
    named["student_name"] = "Ada Example"
    assert "student_name" in blocked_identity_keys(seq, named)
    assert "Ada Example" not in "\n".join(cover_lines(seq, named, report))
    assert f"Registration number: {NUMBER}" in "\n".join(cover_lines(seq, named, report))
    preview = essay_pack_render_word(seq, filled, "draft", stage="6")
    assert preview.get("student_fields") == "registration"
    assert f"Registration number: {NUMBER}" in "\n".join(preview["cover"])
    write_docx(seq, filled, report, target)
    document = Document(str(target))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert f"Registration number: {NUMBER}" in text
    assert "Ada Example" not in text
    assert "Teaching partner" not in text
    assert text.count(NUMBER) == 1

    _write_brief("ESS9001HK", "Genre: essay\nQuestion: How do chokepoints constrain the corridor?\n")
    essay = _open("ESS9001HK")
    essay_pack = pack("ESS9001HK")
    essay_pack["essay_id"] = essay
    essay_pack["student_number"] = NUMBER
    essay_pack["sections"][0]["body"] = (
        "This is an essay. How do chokepoints constrain the corridor?"
    )
    assert "student_number" in blocked_identity_keys(essay, essay_pack)
    blocked = essay_pack_render_word(essay, essay_pack, "confirm", stage="6")
    assert blocked["ok"] is False
    assert blocked.get("wrote") is not True
    assert not (work_dir(essay) / "output" / f"{essay}.docx").is_file()

    _write_brief("ASK9001HK", ESSAY_ASKS)
    asked = _open("ASK9001HK")
    ask_seen = read_assignment(asked)
    assert ask_seen["lock"] == "thesis"
    assert ask_seen["title_page"]["registration"] is True
    ask_pack = pack("ASK9001HK")
    ask_pack["essay_id"] = asked
    ask_pack["student_number"] = NUMBER
    ask_pack["sections"][0]["body"] = "This is an essay. How do chokepoints constrain the corridor?"
    assert "student_number" not in blocked_identity_keys(asked, ask_pack)
    ask_pack["student_name"] = "Ada Example"
    assert "student_name" in blocked_identity_keys(asked, ask_pack)
    missing = dict(ask_pack)
    missing.pop("student_number")
    missing.pop("student_name")
    missing_word = essay_pack_render_word(asked, missing, "confirm", stage="9")
    assert missing_word["refused"] == "title-page"
    assert "registration number" in missing_word["reason"]
    ask_report = {
        "title": "Chokepoints",
        "word_count": {"counted": 12},
        "sections": ask_pack["sections"],
        "figures": [],
        "tables": [],
        "sources": [],
    }
    present = dict(missing)
    present["student_number"] = NUMBER
    ask_lines = "\n".join(cover_lines(asked, present, ask_report))
    assert f"Registration number: {NUMBER}" in ask_lines
    assert "Teaching partner" in ask_lines
    assert "Ada Example" not in ask_lines

    register_mapping("fieldnote", _map_fieldnote)
    try:
        _write_brief("FLD9001HK", FIELDNOTE)
        field = _open("FLD9001HK")
        record = read_assignment(field)
        assert record["writing_type"] == "fieldnote"
        assert record["title_page"]["registration"] is True
        note = {
            "essay_id": field,
            "title": "Quay notes",
            "referencing": "harvard",
            "module_title": "Quay practice",
            "sections": _sections("What did the quay show on that watch? fieldnote."),
        }
        held = essay_pack_render_word(field, note, "confirm", stage="6")
        assert held["refused"] == "title-page"
        assert "registration number" in held["reason"]
        note["registration_number"] = NUMBER
        note["student_name"] = "Ada Example"
        assert "student_name" in blocked_identity_keys(field, note)
        field_report = {
            "title": "Quay notes",
            "word_count": {"counted": 8},
            "sections": note["sections"],
            "figures": [],
            "tables": [],
            "sources": [],
        }
        field_lines = "\n".join(cover_lines(field, note, field_report))
        assert f"Registration number: {NUMBER}" in field_lines
        assert "Ada Example" not in field_lines
        assert "Teaching partner" not in field_lines
        assert read_assignment(field)["lock"] == "notes"
    finally:
        unregister_mapping("fieldnote")
