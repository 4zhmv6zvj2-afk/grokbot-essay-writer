"""PDF sniff, bad-download classification, and stuck download stops."""

import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from docx import Document
from helpers import ESSAY, open_sequence

from essay_writer.dig import essay_dig
from essay_writer.downloads import classify_download, run_downloads
from essay_writer.invent import gather_sources

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
HTML = (
    b"<!DOCTYPE html><html><head><title>Abstract</title></head>"
    b"<body><h1>Abstract</h1><p>Publisher abstract page.</p></body></html>"
)
HTML_URL = "https://publisher.example/html"
PDF_URL = "https://publisher.example/good.pdf"
BAD_URL = "https://publisher.example/missing"
T0 = datetime(2026, 10, 13, 4, 0, tzinfo=timezone.utc)


def _docx_text(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _output(workspace: Path) -> Path:
    return workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"


def test_sniff_rejects_html_and_accepts_pdf_magic():
    assert classify_download(200, "text/html; charset=utf-8", HTML) == "html-abstract"
    assert classify_download(200, "application/pdf", HTML) == "html-abstract"
    assert classify_download(200, "text/html", b"\n%PDF-1.4\n" + HTML) == "html-abstract"
    assert classify_download(200, "Application/PDF", PDF) == "paper"
    assert classify_download(200, "application/pdf; charset=binary", b"\n%PDF-1.7\n") == "paper"
    assert classify_download(200, None, b"\xef\xbb\xbf%PDF-1.4\n") == "paper"
    assert classify_download(404, "text/html", b"<html>subscribe to read</html>") == "404"
    assert classify_download(402, "text/html", b"") == "paywall"
    assert classify_download(403, "text/html", b"<html>Please subscribe to read this article</html>") == "paywall"
    assert classify_download(200, "text/html", b"<html>subscription required for this article</html>") == "paywall"
    assert classify_download(200, "application/pdf", b"") == "empty"
    assert classify_download(200, "application/pdf", b" \n\t") == "empty"
    assert classify_download(0, None, b"") == "empty"


def test_bad_downloads_are_classified_and_valid_pdfs_continue(workspace):
    seq = open_sequence()
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        if url == PDF_URL:
            return 200, "application/pdf", PDF
        if url == HTML_URL:
            return 200, "application/pdf", HTML
        if url == "https://publisher.example/missing-page":
            return 404, "text/html", b"<html>not found</html>"
        if url == "https://publisher.example/pay":
            return 200, "text/html", b"<html>buy this article to continue</html>"
        if url == "https://publisher.example/blank":
            return 200, "application/pdf", b""
        raise AssertionError(url)

    result = run_downloads(
        seq,
        [
            {"url": HTML_URL, "doi": "10.1/html", "title": "Abstract only"},
            {"url": PDF_URL, "doi": "10.1/good", "title": "Real PDF"},
            {"url": "https://publisher.example/missing-page", "doi": "10.1/missing"},
            {"url": "https://publisher.example/pay", "doi": "10.1/pay"},
            {"url": "https://publisher.example/blank", "doi": "10.1/blank"},
        ],
        now=T0,
        fetch=fetch,
    )
    assert result["stopped"] is False
    assert [item["doi"] for item in result["papers"]] == ["10.1/good"]
    buckets = {item["doi"]: item["bucket"] for item in result["failures"]}
    assert buckets == {
        "10.1/html": "html-abstract",
        "10.1/missing": "404",
        "10.1/pay": "paywall",
        "10.1/blank": "empty",
    }
    assert len(calls) == 5
    saved = list((workspace / "uploads" / ESSAY).iterdir())
    assert [path.name for path in saved] == ["10.1_good.pdf"]
    assert saved[0].read_bytes().startswith(b"%PDF-")
    assert b"<html" not in saved[0].read_bytes().lower()
    listed = _docx_text(_output(workspace) / "download-list.docx")
    assert "HTML abstract page" in listed
    assert "Not found (404)" in listed
    assert "Paywall" in listed
    assert "Empty download" in listed
    assert "not a paper" in listed.casefold()
    assert "10.1/html" in listed
    assert not (_output(workspace) / "annotation.docx").exists()
    refused, issues = gather_sources(
        seq,
        [
            {
                "id": "src-html",
                "origin": "upload",
                "locator": "uploads/MOD1004AA/abstract.html",
                "title": "Abstract only",
            }
        ],
    )
    assert refused == []
    assert issues[0]["code"] == "invent-forbid"


def test_third_failure_stops_and_the_same_address_is_not_fetched_again(workspace):
    seq = open_sequence()
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        if url == PDF_URL:
            return 200, "application/pdf", PDF
        return 200, "text/html", HTML

    kept = run_downloads(seq, [{"url": PDF_URL, "doi": "10.1/good"}], fetch=fetch, now=T0)
    assert kept["papers"] and kept["stopped"] is False
    for _ in range(2):
        step = run_downloads(seq, [{"url": BAD_URL, "doi": "10.1/bad"}], fetch=fetch, now=T0)
        assert step["stopped"] is False
    stopped = run_downloads(seq, [{"url": BAD_URL, "doi": "10.1/bad"}], fetch=fetch, now=T0)
    assert stopped["stopped"] is True
    assert stopped["stop_reason"] == "retries"
    assert stopped["attempts"][BAD_URL] == 3
    assert [item["doi"] for item in stopped["papers"]] == ["10.1/good"]
    assert all(item.get("doi") != "10.1/bad" for item in stopped["papers"])
    assert "failed 3 times" in stopped["next"]
    assert "10.1/bad" in stopped["next"]
    assert re.search(r"\btip\b", stopped["next"], re.IGNORECASE) is None
    annotation = _docx_text(_output(workspace) / "annotation.docx")
    assert "Annotated bibliography" in annotation
    assert "10.1/good" in annotation
    assert "10.1/bad" not in annotation
    assert re.search(r"\bdig\b", annotation, re.IGNORECASE) is None
    assert stopped["annotation_chat"]["deliver"] == "chat"
    assert stopped["annotation_chat"]["name"] == "annotation.docx"
    papers = zipfile.ZipFile(_output(workspace) / "papers.zip")
    assert papers.namelist()
    assert all(name.lower().endswith(".pdf") for name in papers.namelist())
    listed = _docx_text(_output(workspace) / "download-list.docx")
    assert "HTML abstract page" in listed
    assert "10.1/bad" in listed
    assert "not a paper" in listed.casefold()
    before = len(calls)
    again = run_downloads(
        seq,
        [{"url": BAD_URL, "doi": "10.1/bad"}, {"url": PDF_URL, "doi": "10.1/good"}],
        fetch=fetch,
        now=T0,
    )
    assert calls[before:] == []
    assert again["stopped"] is True
    assert again["fetched"] == []
    fresh_calls: list[str] = []

    def fetch_new(url: str):
        fresh_calls.append(url)
        return 200, "application/pdf", PDF

    followed = run_downloads(
        seq,
        [{"url": BAD_URL, "doi": "10.1/bad"}, {"url": "https://publisher.example/other.pdf", "doi": "10.1/other"}],
        fetch=fetch_new,
        now=T0,
    )
    assert fresh_calls == ["https://publisher.example/other.pdf"]
    assert {item["doi"] for item in followed["papers"]} == {"10.1/good", "10.1/other"}
    assert all(item.get("doi") != "10.1/bad" for item in followed["papers"])


def test_idle_over_ten_minutes_stops_without_another_fetch(workspace):
    seq = open_sequence()
    calls: list[str] = []

    def fetch(url: str):
        calls.append(url)
        return 404, "text/html", b"<html>gone</html>"

    first = run_downloads(seq, [{"url": BAD_URL, "doi": "10.1/bad"}], fetch=fetch, now=T0)
    assert first["stopped"] is False
    assert len(calls) == 1
    still = run_downloads(
        seq,
        [{"url": BAD_URL, "doi": "10.1/bad"}],
        fetch=fetch,
        now=T0 + timedelta(minutes=10),
    )
    assert still["stopped"] is False
    assert len(calls) == 2
    idle = run_downloads(
        seq,
        [{"url": BAD_URL, "doi": "10.1/bad"}],
        fetch=fetch,
        now=T0 + timedelta(minutes=10, seconds=1),
    )
    assert len(calls) == 2
    assert idle["fetched"] == []
    assert idle["stopped"] is True
    assert idle["stop_reason"] == "idle"
    assert idle["papers"] == []
    assert "more than 10 minutes" in idle["next"]
    assert "10.1/bad" in idle["next"]
    assert (_output(workspace) / "annotation.docx").is_file()
    assert (_output(workspace) / "download-list.docx").is_file()
    idle_note = _docx_text(_output(workspace) / "annotation.docx")
    assert "Annotated bibliography" in idle_note
    assert "No PDF was saved." in idle_note
    assert re.search(r"\bdig\b", idle_note, re.IGNORECASE) is None
    assert idle["annotation_chat"]["deliver"] == "chat"
    assert not (_output(workspace) / "papers.zip").exists()
    repeat = run_downloads(
        seq,
        [{"url": BAD_URL, "doi": "10.1/bad"}],
        fetch=fetch,
        now=T0 + timedelta(minutes=11),
    )
    assert repeat["fetched"] == []
    assert len(calls) == 2


def test_dig_confirm_saves_only_real_pdfs_and_lists_the_html_page(workspace, monkeypatch):
    seq = open_sequence()
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "reader@example.com")
    fetches: list[str] = []

    def fake_json(url, headers=None):
        if "api.openalex.org" in url:
            return {
                "results": [
                    {
                        "title": "HTML only",
                        "publication_year": 2020,
                        "doi": "https://doi.org/10.1/html",
                        "authorships": [],
                    },
                    {
                        "title": "Real PDF",
                        "publication_year": 2021,
                        "doi": "https://doi.org/10.1/good",
                        "authorships": [],
                    },
                ]
            }
        if "api.unpaywall.org" in url:
            if "html" in url:
                return {"best_oa_location": {"url_for_pdf": HTML_URL, "url": HTML_URL}}
            if "good" in url:
                return {"best_oa_location": {"url_for_pdf": PDF_URL}}
            return {}
        return {"results": []}

    def fake_fetch(url):
        fetches.append(url)
        if url == PDF_URL:
            return 200, "application/pdf", PDF
        return 200, "text/html", HTML

    monkeypatch.setattr("essay_writer.dig._get_json", fake_json)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fake_fetch)
    draft = essay_dig(seq, "zara supply chain", "draft")
    assert draft["wrote"] is False
    assert "downloads" not in draft
    assert not (workspace / "uploads" / ESSAY).exists() or not list((workspace / "uploads" / ESSAY).glob("*"))
    assert not (_output(workspace) / "download-list.docx").exists()
    confirmed = essay_dig(seq, "zara supply chain", "confirm")
    assert confirmed["wrote"] is True
    assert confirmed["downloads"]["stopped"] is False
    assert [item["doi"] for item in confirmed["downloads"]["papers"]] == ["10.1/good"]
    assert confirmed["downloads"]["failures"][0]["bucket"] == "html-abstract"
    assert fetches == [HTML_URL, PDF_URL]
    saved = workspace / "uploads" / ESSAY / "10.1_good.pdf"
    assert saved.read_bytes().startswith(b"%PDF-")
    assert [path.name for path in (workspace / "uploads" / ESSAY).iterdir()] == ["10.1_good.pdf"]
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    card = json.loads((folder / "dig-card.json").read_text(encoding="utf-8"))
    text = (folder / "dig-card.md").read_text(encoding="utf-8")
    assert card["downloads"]["failures"][0]["bucket"] == "html-abstract"
    assert "10.1/good: saved PDF." in text
    assert "HTML abstract page. Not a paper." in text
    assert "HTML only" in text
    listed = _docx_text(_output(workspace) / "download-list.docx")
    assert "HTML abstract page" in listed
    assert "not a paper" in listed.casefold()
    download_list = _output(workspace) / "download-list.docx"
    assert download_list.suffix == ".docx"
    assert download_list.read_bytes()[:2] == b"PK"
    assert not (_output(workspace) / "download-list.md").exists()
    assert not (_output(workspace) / "annotation.docx").exists()
    saved_zip = zipfile.ZipFile(download_list.parent / "papers.zip")
    assert saved_zip.namelist() == ["10.1_good.pdf"]
    assert saved_zip.read("10.1_good.pdf").startswith(b"%PDF-")
