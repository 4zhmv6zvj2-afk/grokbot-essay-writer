"""Leftovers, brief checks, known paths, and citations."""

import json
import zipfile
from pathlib import Path

import pytest
from helpers import (
    ESSAY,
    TOPIC,
    open_sequence,
    pack,
    plant_gathered_source,
    source,
    write_upload,
)

from essay_writer.brief_checks import SAFE_DEFAULT, section_budgets
from essay_writer.cite_open import open_for_citation, pdf_from_source
from essay_writer.dig import consensus_search, essay_dig, unpaywall_lookup
from essay_writer.doors import DOORS
from essay_writer.downloads import fetch_url
from essay_writer.free_alt import essay_download_leftovers
from essay_writer.gates import essay_gates
from essay_writer.handbook import read_handbook
from essay_writer.intake import essay_intake, essay_unassigned_collect
from essay_writer.invent import read_gathered_text
from essay_writer.known_paths import (
    RepoSaveRefused,
    repo_root,
    repo_save_refused,
    research_file,
)
from essay_writer.pdf_year import citation_year
from essay_writer.programme import referencing_record
from essay_writer.projects import (
    essay_project_archive,
    essay_project_unarchive,
    essay_sequence_new,
)
from essay_writer.research import essay_research_full, essay_research_summary
from essay_writer.research_packs import (
    _pdf_path,
    _review_body,
    open_critical_markdown,
    write_annotation_docx,
)
from essay_writer.revise import essay_revise
from essay_writer.server import HANDLERS
from essay_writer.setup import essay_setup
from essay_writer.shelf import essay_shelf_get, essay_shelf_put
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import QUOTATION_HOUSE_POLICY, prose_for_surface
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word, write_docx

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
QUOTE = "The pack on the house door left a tip in the smoke"
BUDGETS = (
    "Genre: report\n"
    "Section budgets: Introduction 400, Supply chain context 400, "
    "Analysis and findings 400, Conclusion 200\n"
)
CLASH = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "This assignment is a group assessment and it is also individual.\n"
    "The mark is 50% of the module and also 100% of the module.\n"
    "Referencing is Harvard/APA.\n"
    "Learning outcomes: maritime chokepoints\n"
    "Rubric: agricultural irrigation methods\n"
)
SIMULATION = (
    "Genre: report\n"
    "Question: How do chokepoints constrain the corridor?\n"
    "The module names simulation events.\n"
    "The corridor drill stays on the brief.\n"
)


def _codes(items):
    return [item["code"] for item in items]


def _ready(workspace, brief="Genre: report\nQuestion: How do chokepoints constrain the corridor?\n"):
    write_upload(workspace)
    folder = workspace / "Essay-writer" / ESSAY
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    saved = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert saved["stored"] is True
    return seq


def _plant_4a(workspace, seq, url=None):
    plant_gathered_source(seq)
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    output = folder / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "annotation.docx").write_bytes(b"PK annotated bibliography")
    card = {"unpaywall": []}
    if url:
        card["unpaywall"] = [{"doi": "10.1000/left", "oa_url": url}]
    (folder / "dig-card.json").write_text(json.dumps(card), encoding="utf-8")


def test_leftover_door_fetches_stored_addresses_only(workspace, monkeypatch):
    seq = open_sequence()
    early = essay_download_leftovers(seq, "draft")
    assert early["ok"] is False
    assert early["refused"] == "4a"
    assert early["wrote"] is False

    url = "https://example.test/leftover.pdf"
    _plant_4a(workspace, seq, url)
    calls = {"lookup": 0, "fetch": []}

    def explode(*_args, **_kwargs):
        calls["lookup"] += 1
        raise AssertionError("a new look-up was opened")

    def fetch(address):
        calls["fetch"].append(address)
        return 200, "application/pdf", PDF

    monkeypatch.setattr("essay_writer.dig.unpaywall_lookup", explode)
    monkeypatch.setattr("essay_writer.dig.consensus_search", explode)
    monkeypatch.setattr("essay_writer.resolvers.unpaywall_lookup", explode)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fetch)

    draft = essay_download_leftovers(seq, "draft")
    assert draft["ok"] is True
    assert draft["wrote"] is False
    assert draft["lookup"] is False
    assert draft["invent_forbid"] is True
    assert [item["url"] for item in draft["leftovers"]] == [url]
    assert not list((workspace / "uploads" / ESSAY).glob("*.pdf"))

    confirmed = essay_download_leftovers(seq, "confirm")
    assert confirmed["ok"] is True
    assert confirmed["wrote"] is True
    assert calls["fetch"] == [url]
    assert calls["lookup"] == 0
    saved = list((workspace / "uploads" / ESSAY).glob("*.pdf"))
    assert len(saved) == 1
    assert saved[0].read_bytes().startswith(b"%PDF-")
    assert unpaywall_lookup is not fetch_url
    assert consensus_search is not fetch_url

    overlay = stage_settings("4a")["prompt_overlay"]
    assert "speech only" in overlay
    assert "later download step can fetch leftover free alternatives already found" in overlay
    assert any(door["tool"] == "essay.download.leftovers" for door in DOORS)
    assert HANDLERS["essay.download.leftovers"] is essay_download_leftovers


def test_section_budgets_block_before_word_and_are_not_invented(workspace):
    assert section_budgets("Write about corridors.\n") == []
    seq = _ready(workspace, BUDGETS)
    body = pack()
    draft = essay_pack_validate(seq, body, "draft")
    assert "section-budget" in _codes(draft["blockers"])
    assert draft["passed"] is False
    assert draft["ok"] is True
    assert draft["section_budgets"]
    preview = essay_pack_render_word(seq, body, "draft")
    assert preview["wrote"] is False
    assert "section-budget" in _codes(preview["blockers"])
    assert preview["section_budgets"]
    blocked = essay_pack_render_word(seq, body, "confirm")
    assert blocked["refused"] == "validate"
    assert blocked["wrote"] is False
    target = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / f"{seq}.docx"
    assert not target.exists()

    acked = pack(section_words_acknowledged=True)
    noted = essay_pack_validate(seq, acked, "draft")
    assert "section-budget" not in _codes(noted["blockers"])
    assert "section-budget" in _codes(noted["notes"])


def test_brief_contradiction_is_shown_before_word(workspace):
    seq = _ready(workspace, CLASH)
    body = pack()
    draft = essay_pack_validate(seq, body, "draft")
    assert "brief-contradiction" in _codes(draft["blockers"])
    assert draft["safe_default"] == SAFE_DEFAULT
    assert "task headings and the rubric" in draft["safe_default"]
    preview = essay_pack_render_word(seq, body, "draft")
    assert preview["wrote"] is False
    assert preview["safe_default"] == SAFE_DEFAULT
    assert "brief-contradiction" in _codes(preview["blockers"])
    acked = pack(contradiction_acknowledged=True)
    noted = essay_pack_validate(seq, acked, "draft")
    assert "brief-contradiction" not in _codes(noted["blockers"])
    assert "brief-contradiction" in _codes(noted["notes"])
    assert noted["safe_default"] == SAFE_DEFAULT


def test_simulation_events_are_noticed_and_not_invented(workspace):
    seq = _ready(workspace, SIMULATION)
    noticed = pack()
    draft = essay_pack_validate(seq, noticed, "draft")
    assert draft["simulation_events"]["noticed"] is True
    assert "simulation-events" in _codes(draft["blockers"])
    assert "invent-forbid" not in _codes(draft["blockers"])
    preview = essay_pack_render_word(seq, noticed, "draft")
    assert preview["wrote"] is False
    assert preview["simulation_events"]["noticed"] is True

    copied = pack()
    copied["sections"] = list(copied["sections"])
    copied["sections"][0] = {
        "heading": "Introduction",
        "body": "The module names simulation events. The corridor depends on a narrow strait (Smith, 2020).",
    }
    copied["simulation_acknowledged"] = True
    allowed = essay_pack_validate(seq, copied, "draft")
    assert "invent-forbid" not in _codes(allowed["blockers"])
    assert "simulation-events" in _codes(allowed["notes"])

    invented = pack(simulation_acknowledged=True)
    invented["sections"] = list(invented["sections"])
    invented["sections"][0] = {
        "heading": "Introduction",
        "body": "The simulation closed the strait for nine whole days (Smith, 2020).",
    }
    blocked = essay_pack_validate(seq, invented, "draft")
    assert blocked["ok"] is False
    assert blocked["refused"] == "invent-forbid"
    word = essay_pack_render_word(seq, invented, "draft")
    assert word["wrote"] is False
    assert word["refused"] == "invent-forbid"


def test_research_opens_go_through_allow_research_path(workspace, tmp_path):
    seq = open_sequence()
    upload = write_upload(workspace)
    assert research_file(seq, f"uploads/{ESSAY}/smith.md") == upload.resolve()
    assert "Strait" in read_gathered_text(upload, seq)

    secret = tmp_path / "not-a-student" / "paper.pdf"
    secret.parent.mkdir()
    secret.write_bytes(PDF)
    note = secret.parent / "note.md"
    note.write_text("invented simulation events\n", encoding="utf-8")
    assert research_file(seq, str(secret)) is None
    with pytest.raises(ValueError, match="invent"):
        read_gathered_text(secret, seq)
    assert pdf_from_source({"locator": str(secret)}, seq) is None
    assert open_for_citation(secret, seq).text == ""
    assert citation_year(secret, seq) is None
    assert _pdf_path(seq, str(secret)) is None
    assert open_critical_markdown(note, seq) == ""

    checkout = repo_root() / "src" / "essay_writer" / "known_paths.py"
    assert research_file(seq, str(checkout)) is not None
    assert research_file(seq, str(checkout), save=True) is None


def test_repo_save_is_refused_on_write_doors(workspace, monkeypatch):
    root = repo_root()
    assert repo_save_refused(root / "src" / "essay_writer" / "word.py") is True
    assert repo_save_refused(root / "tests" / "test_leftovers_and_known_paths.py") is True
    assert repo_save_refused(root / "Essay-writer" / ESSAY / "brief.md") is False
    assert repo_save_refused(root / "uploads" / ESSAY / "a.pdf") is False
    assert repo_save_refused(workspace / "Essay-writer" / ESSAY) is False

    refused = essay_setup(
        app_path=str(root / "src"),
        kb1_path=str(root / "docs"),
        confirmPhase="draft",
    )
    assert refused["refused"] == "repo-not-save"
    assert refused["wrote"] is False
    assert not (root / "src" / "Essay-writer").exists()

    seq = open_sequence()
    report = {
        "title": "Probe",
        "sections": [{"heading": "Introduction", "body": "A short line."}],
        "figures": [],
        "tables": [],
        "sources": [],
        "word_count": {},
    }
    bad = root / "src" / "not-a-student.docx"
    with pytest.raises(RepoSaveRefused):
        write_docx(seq, {}, report, bad)
    assert not bad.exists()

    monkeypatch.setattr("essay_writer.known_paths.repo_save_refused", lambda _path: True)
    doors = [
        essay_research_summary(seq, TOPIC, "draft"),
        essay_research_full(seq, TOPIC, "draft"),
        essay_pack_validate(seq, pack(), "draft"),
        essay_pack_render_word(seq, pack(), "draft"),
        essay_stage(seq, "1", "draft"),
        essay_revise(seq, "A note.", "draft"),
        essay_shelf_put(seq, pack(), "draft"),
        essay_shelf_get(seq, "local", "draft"),
        essay_setup(app_path=str(workspace / "app"), kb1_path=str(workspace / "KB1"), confirmPhase="draft"),
        essay_project_archive(ESSAY, "draft"),
        essay_project_unarchive(ESSAY, "draft"),
        essay_sequence_new(ESSAY, "draft"),
        essay_unassigned_collect("draft"),
        essay_dig(seq, "chokepoints", "draft"),
        essay_intake("notes.docx", "draft"),
        essay_download_leftovers(seq, "draft"),
    ]
    assert [item["refused"] for item in doors] == ["repo-not-save"] * len(doors)
    assert all(item["wrote"] is False for item in doors)


def test_decorative_citation_fails_validate_and_gate_7(workspace):
    seq = _ready(workspace)
    body = pack()
    body["sections"] = list(body["sections"])
    body["sections"][0] = {
        "heading": "Introduction",
        "body": "It is widely known that corridors matter (Smith, 2020).",
    }
    draft = essay_pack_validate(seq, body, "draft")
    assert draft["ok"] is True
    assert draft["passed"] is False
    parked = [item for item in draft["blockers"] if item["code"] == "decorative-citation"]
    assert parked
    assert parked[0]["reason"].startswith("A citation is parked on a general sentence.")
    report = essay_gates(seq, body)
    assert [item["gate"] for item in report["gates"]] == list(range(1, 12))
    gate = next(item for item in report["gates"] if item["gate"] == 7)
    assert gate["passed"] is False
    assert gate["reason"].startswith("A citation is parked on a general sentence.")
    assert report["passed"] is False


def test_endnote_and_csl_come_from_the_handbook_file(tmp_path, monkeypatch):
    checked = read_handbook()
    assert checked["checked"] is True
    assert checked["endnote"] == "Harvard"
    assert checked["csl"] is None
    assert "invent" in checked["csl_reason"].casefold() or "no csl" in checked["csl_reason"].casefold()
    record = referencing_record()
    assert record["endnote"] == checked["endnote"]
    assert record["csl"] is None
    source_text = (repo_root() / "src" / "essay_writer" / "programme.py").read_text(encoding="utf-8")
    assert "Harvard Referencing 13th Edition" not in source_text
    missing = read_handbook(tmp_path / "missing.md")
    assert missing["checked"] is False
    assert missing["endnote"] is None
    assert "memory" in missing["csl_reason"].casefold()

    folder = tmp_path / "handbook"
    folder.mkdir()
    csl = folder / "style.csl"
    csl.write_text("<style/>", encoding="utf-8")
    book = folder / "hand.md"
    book.write_text(
        "EndNote style to select: **Example Style**\n- CSL file: style.csl\n",
        encoding="utf-8",
    )
    named = read_handbook(book)
    assert named["endnote"] == "Example Style"
    assert named["csl"] == str(csl.resolve())
    monkeypatch.setattr("essay_writer.handbook.handbook_path", lambda: book)
    assert referencing_record()["csl"] == str(csl.resolve())
    assert referencing_record()["endnote"] == "Example Style"


def test_quotation_house_words_stay_on_every_surface(workspace):
    assert "Word" in QUOTATION_HOUSE_POLICY
    assert "annotation" in QUOTATION_HOUSE_POLICY
    assert "4b markdown" in QUOTATION_HOUSE_POLICY
    quoted = f'"The dig {QUOTE}"'
    for surface in ("word", "annotation", "review"):
        text = prose_for_surface(quoted, surface)
        assert "look-up" in text
        for word in ("pack", "house", "door", "tip", "smoke"):
            assert word in text
        assert "dig" not in text.casefold()
    assert "pack" not in prose_for_surface("the pack size", "word")
    assert prose_for_surface("the pack size", "annotation") == "the pack size"
    assert prose_for_surface("the pack size", "review") == "the pack size"

    seq = open_sequence()
    report = {
        "title": "Quote",
        "sections": [{"heading": "Introduction", "body": f'The source says "{QUOTE}".'}],
        "figures": [],
        "tables": [],
        "sources": [],
        "word_count": {},
    }
    target = workspace / "quote.docx"
    write_docx(seq, {}, report, target)
    xml = zipfile.ZipFile(target).read("word/document.xml").decode("utf-8")
    for word in ("pack", "house", "door", "tip", "smoke"):
        assert word in xml

    annotation = workspace / "annotation.docx"
    write_annotation_docx(
        annotation,
        [{"parts": [("Smith (2020).", False)], "paragraph": f'The source says "{QUOTE}".'}],
        empty_note="No PDF was saved.",
    )
    from docx import Document

    noted = "\n".join(paragraph.text for paragraph in Document(str(annotation)).paragraphs)
    for word in ("pack", "house", "door", "tip", "smoke"):
        assert word in noted
    review = _review_body(
        seq,
        {
            "id": "src-1",
            "author": "Smith, J.",
            "year": "2020",
            "title": "Chokepoints",
            "quote": QUOTE,
        },
        None,
    )
    for word in ("pack", "house", "door", "tip", "smoke"):
        assert word in review
    assert Path(annotation).is_file()
