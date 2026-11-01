"""Download and read locks."""

import json
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from helpers import ESSAY, open_sequence, picked

from essay_writer.downloads import run_downloads
from essay_writer.first_run import copy_deliverable_to_mac
from essay_writer.pdf_read import PART_LIMIT, chop_pdf, readable_pdf
from essay_writer.pdf_year import apply_citation_year, citation_year
from essay_writer.quarantine import clear_mac_quarantine
from essay_writer.research_packs import (
    open_critical_markdown,
    reconcile_before_4b,
    ship_4a,
    ship_4b,
)
from essay_writer.server import INSTRUCTIONS
from essay_writer.stage_llm import HOUSE_MODEL, stage_settings
from essay_writer.stage_track import essay_stage

REPO = Path(__file__).resolve().parents[1]
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _docx(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _output(workspace: Path) -> Path:
    return workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"


def _pdf_with(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Length "
        + str(len(stream)).encode()
        + b">>stream\n"
        + stream
        + b"\nendstream\nendobj\ntrailer<<>>\n%%EOF\n"
    )


def _empty_download_state(failures: list[dict]) -> dict:
    return {
        "attempts": {},
        "seen_urls": [],
        "failures": failures,
        "papers": [],
        "started_at": None,
        "last_useful_at": None,
        "stopped": False,
        "stop_reason": None,
    }


def test_overlays_name_the_download_locks():
    overlay_4a = stage_settings("4a")["prompt_overlay"]
    overlay_4b = stage_settings("4b")["prompt_overlay"]
    assert "file's modified time" in overlay_4a
    assert "abstract-only" in overlay_4a
    assert "20MB" in overlay_4a
    assert "quarantine mark" in overlay_4a
    assert "on disk and in Documents" in overlay_4b
    assert "papers zip as the only copy" in overlay_4b
    assert "option C: Download leftovers first" in overlay_4b
    assert "grok-4.7" in overlay_4b
    assert "markdown file on disk" in overlay_4b
    assert "page title or header" in INSTRUCTIONS
    year_source = (REPO / "src" / "essay_writer" / "pdf_year.py").read_text(encoding="utf-8")
    assert "st_mtime" not in year_source
    stage_llm = (REPO / "src" / "essay_writer" / "stage_llm.py").read_text(encoding="utf-8")
    assert 'HOUSE_MODEL = "grok-4.7"' in stage_llm


def test_citation_year_comes_from_the_page_header_not_mtime(workspace, tmp_path):
    stamped = datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp()
    dated = workspace / "uploads" / ESSAY / "smith-2018.pdf"
    dated.parent.mkdir(parents=True, exist_ok=True)
    dated.write_bytes(_pdf_with("Smith, J. (2018) Chokepoints and crude"))
    os.utime(dated, (stamped, stamped))
    assert citation_year(dated) == "2018"
    cited = apply_citation_year(
        {"author": "Smith, J.", "year": "2024", "title": "Chokepoints and crude", "locator": f"uploads/{ESSAY}/smith-2018.pdf"},
        dated,
    )
    assert cited["year"] == "2018"
    undated = tmp_path / "undated.pdf"
    undated.write_bytes(_pdf_with("Smith, J. Chokepoints and crude"))
    os.utime(undated, (stamped, stamped))
    assert citation_year(undated) is None
    dropped = apply_citation_year({"author": "Smith, J.", "year": "2024", "title": "Chokepoints and crude"}, undated)
    assert "year" not in dropped
    seq = open_sequence()
    ship_4a(
        seq,
        [
            {
                "id": "src-1",
                "author": "Smith, J.",
                "year": "2024",
                "title": "Chokepoints and crude",
                "locator": f"uploads/{ESSAY}/smith-2018.pdf",
            }
        ],
        {},
    )
    text = _docx(_output(workspace) / "annotation.docx")
    assert "(2018)" in text
    assert "(2024)" not in text


def test_abstract_only_stays_on_the_download_list(workspace):
    seq = open_sequence()
    state = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "download-run.json"
    state.write_text(
        json.dumps(
            _empty_download_state(
                [
                    {
                        "url": "https://example.test/karaosman",
                        "bucket": "html-abstract",
                        "title": "Behind the runway",
                        "doi": "10.1016/j.jbusres.2018.09.017",
                    }
                ]
            )
        ),
        encoding="utf-8",
    )
    ship_4a(
        seq,
        [
            {
                "id": "src-1",
                "author": "Smith, J.",
                "year": "2020",
                "title": "Chokepoints and crude",
            },
            {
                "id": "karaosman",
                "author": "Karaosman, H.",
                "year": "2018",
                "title": "Behind the runway",
                "doi": "10.1016/j.jbusres.2018.09.017",
            },
        ],
        {"src-1": "Smith argues the corridor is narrow."},
    )
    folder = _output(workspace)
    bibliography = _docx(folder / "annotation.docx")
    listed = _docx(folder / "download-list.docx")
    assert "Chokepoints and crude" in bibliography
    assert "Behind the runway" not in bibliography
    assert "10.1016/j.jbusres.2018.09.017" in listed
    assert "HTML abstract page" in listed


def test_reconcile_checks_disk_and_documents_not_the_zip(workspace, tmp_path):
    seq = open_sequence()
    sequence = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    sequence.mkdir(parents=True, exist_ok=True)
    documents = tmp_path / "Documents"
    documents.mkdir()
    named = documents / "behind-the-runway.pdf"
    named.write_bytes(PDF)
    (documents / "other-runway-paper.pdf").write_bytes(PDF)
    (sequence / "download-run.json").write_text(
        json.dumps(
            _empty_download_state(
                [
                    {
                        "url": "https://example.test/runway",
                        "bucket": "html-abstract",
                        "title": "Behind the runway",
                        "path": str(documents / "behind-the-runway.pdf"),
                    },
                    {
                        "url": "https://example.test/other",
                        "bucket": "html-abstract",
                        "title": "Other runway paper",
                    },
                    {
                        "url": "https://example.test/zip-only",
                        "bucket": "leftover",
                        "title": "Only In Zip Paper",
                    },
                ]
            )
        ),
        encoding="utf-8",
    )
    zipped = sequence / "output"
    zipped.mkdir(parents=True)
    archive_path = zipped / "papers.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("only-in-zip-paper.pdf", PDF)
    report = reconcile_before_4b(seq, documents=documents)
    assert report["zip_only"] is False
    assert report["checked"] == "disk-and-documents"
    assert report["option_c"] == "Download leftovers first"
    assert {item["name"] for item in report["matched"]} == {"behind-the-runway.pdf"}
    assert report["matched"][0]["where"] == "Documents"
    assert "Only In Zip Paper" in report["still_listed"]
    assert "Other runway paper" in report["still_listed"]
    assert "Behind the runway" not in report["still_listed"]
    assert (workspace / "uploads" / ESSAY / "behind-the-runway.pdf").is_file()
    refreshed = zipfile.ZipFile(_output(workspace) / "papers.zip")
    assert "behind-the-runway.pdf" in refreshed.namelist()
    assert "only-in-zip-paper.pdf" not in refreshed.namelist()
    assert "Behind the runway" in _docx(_output(workspace) / "annotation.docx")
    for stage in ("1", "2", "3", "4a"):
        drafted = essay_stage(seq, stage, "draft")
        assert drafted["ok"] is True
        assert essay_stage(seq, stage, "confirm", **picked(drafted))["ok"] is True
    draft = essay_stage(seq, "4b", "draft", "The read can start.")
    assert draft["download_check"]["zip_only"] is False
    assert "Option C: Download leftovers first." in draft["confirm_line"]
    assert draft["download_check"]["checked"] == "disk-and-documents"


def test_quarantine_clears_on_handoff_and_is_a_noop_when_absent(tmp_path, monkeypatch):
    mac = tmp_path / "mac"
    source = tmp_path / "essay.docx"
    source.write_bytes(b"word-bytes")
    copied = copy_deliverable_to_mac(source, mac_dir=mac)
    assert copied["copied"] is True
    assert copied["quarantine"]["ok"] is True
    assert copied["quarantine"]["noop"] is True
    target = mac / "essay.docx"

    def _raise(*_args, **_kwargs):
        raise OSError("xattr absent")

    monkeypatch.setattr(os, "removexattr", _raise, raising=False)
    absent = clear_mac_quarantine(target)
    assert absent["ok"] is True
    assert absent["noop"] is True
    assert absent["cleared"] == []
    if hasattr(os, "setxattr") and hasattr(os, "removexattr"):
        monkeypatch.undo()
        try:
            os.setxattr(target, "com.apple.quarantine", b"0083;00000000;essay-writer")
        except OSError:
            return
        cleared = clear_mac_quarantine(target)
        assert cleared["ok"] is True
        assert "com.apple.quarantine" in cleared["cleared"]
        try:
            os.getxattr(target, "com.apple.quarantine")
        except OSError:
            gone = True
        else:
            gone = False
        assert gone is True


def test_pdf_read_chop_keeps_bytes_on_machine(workspace):
    assert PART_LIMIT == 20_000_000
    folder = workspace / "reads"
    folder.mkdir()
    one = _pdf_with("Part one (2019) Alpha")
    two = _pdf_with("Part two (2020) Beta")
    combined = folder / "combined.pdf"
    combined.write_bytes(one + two)
    chopped = chop_pdf(combined, limit=max(len(one), len(two)))
    assert chopped["bytes_leave_machine"] is False
    assert chopped["gaps"] == []
    assert len(chopped["parts"]) == 2
    for part in chopped["parts"]:
        data = Path(part["path"]).read_bytes()
        assert part["readable"] is True
        assert readable_pdf(data)
    huge = folder / "huge.pdf"
    payload = _pdf_with("Huge (2017) Gamma")
    payload = payload.replace(b"%%EOF\n", b"% " + (b"a" * 200) + b"\n%%EOF\n")
    huge.write_bytes(payload)
    over = chop_pdf(huge, limit=80)
    assert over["bytes_leave_machine"] is False
    assert over["parts"] == []
    assert over["gaps"]
    assert over["gaps"][0]["bytes_on_machine"] is True
    assert huge.read_bytes() == payload
    assert not any("part-" in path.name and path.suffix == ".pdf" for path in huge.parent.rglob("part-*.pdf") if "huge" in str(path.parent))
    truncated = folder / "cut.pdf"
    truncated.write_bytes(b"%PDF-1.4\ntruncated-without-end")
    missing = chop_pdf(truncated, limit=PART_LIMIT)
    assert missing["parts"] == []
    assert missing["gaps"][0]["reason"] == "unreadable"
    assert truncated.read_bytes().startswith(b"%PDF-")
    gaps = json.loads((folder / "pdf-read-gaps.json").read_text(encoding="utf-8"))
    assert gaps["bytes_leave_machine"] is False
    assert gaps["gaps"]
    seq = open_sequence()

    def fake_fetch(_url: str):
        return 200, "application/pdf", b"%PDF-1.4\nno-eof"

    saved = run_downloads(seq, [{"url": "https://example.test/big", "title": "Cut paper"}], fetch=fake_fetch)
    assert saved["papers"] == []
    assert saved["failures"][0]["bucket"] == "read-gap"
    uploads = list((workspace / "uploads" / ESSAY).glob("*.pdf"))
    assert uploads
    assert uploads[0].read_bytes().startswith(b"%PDF-")
    fetch_source = (REPO / "src" / "essay_writer" / "downloads.py").read_text(encoding="utf-8")
    assert "response.read()" in fetch_source
    assert "read(_MAX_BYTES)" not in fetch_source


def test_critical_note_opens_the_markdown_and_names_grok(workspace):
    seq = open_sequence()
    delivered = ship_4b(
        seq,
        [{"id": "src-1", "author": "Smith, J.", "year": "2020", "title": "Chokepoints and crude"}],
        {"src-1": "Smith argues the corridor is narrow."},
    )
    review = delivered["reviews"][0]
    assert review["opened"] is True
    assert review["model"] == HOUSE_MODEL == "grok-4.7"
    path = workspace / review["markdown_path"]
    opened = open_critical_markdown(path)
    assert opened == path.read_text(encoding="utf-8")
    assert "Critical note: grok-4.7" in opened
    assert "Chokepoints and crude" in opened
