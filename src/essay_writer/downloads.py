"""Open-copy downloads on a sequence.

essay.dig confirm calls this with Unpaywall addresses. A file is kept only
when the response is a real PDF: the content-type is not HTML, and the bytes
carry the %PDF- magic. An HTML abstract page, a 404, a paywall, or an empty
body is classified onto download-list.docx. It is not saved and it is not a
paper. A saved PDF stays off that list. Valid PDFs are kept, and the rest of
the list still runs. The same cannot-open rows are a links card on the reply.

The same failed address is fetched at most 3 times. If more than 10 minutes
pass with no new PDF, that path stops. Stopping writes annotation.docx and
download-list.docx from the PDFs already saved and names what is still missing.
A later confirm does not fetch those same addresses again.

A PDF body is stored whole on this machine. The 20MB figure is the read chop
in essay_writer.pdf_read, not a cut that drops the tail of the file.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from essay_writer.confirm import refuse
from essay_writer.known_paths import guard_write_door, research_file
from essay_writer.paths import (
    relative,
    sequence_write_error,
    uploads_dir,
    work_dir,
    workspace_root,
)
from essay_writer.student_voice import _scrub_paths_in_text, prose_for_surface, say
from essay_writer.word import _style_document

Fetch = Callable[[str], tuple[int, str | None, bytes]]

STATE_NAME = "download-run.json"
DOWNLOAD_LIST_NAME = "download-list.docx"
ANNOTATION_NAME = "annotation.docx"
STUCK_AFTER = timedelta(minutes=10)
MAX_ATTEMPTS = 3

_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml", "application/xhtml"})
_PDF_TYPES = frozenset({"application/pdf", "application/x-pdf", "application/octet-stream"})
_PAYWALL_MARKERS = (
    "paywall",
    "subscribe to",
    "subscription required",
    "purchase this article",
    "buy this article",
    "rent this article",
    "sign in to download",
    "log in to access",
)
BUCKET_LABELS = {
    "html-abstract": "HTML abstract page",
    "404": "Not found (404)",
    "paywall": "Paywall",
    "empty": "Empty download",
    "not-pdf": "Not a PDF",
    "leftover": "Still needs a PDF",
    "read-gap": "Part not readable",
}


def content_type_base(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.split(";", 1)[0].strip().casefold()


def pdf_magic(body: bytes) -> bool:
    """True when the bytes are a PDF, allowing a short BOM or whitespace prefix."""
    if not body:
        return False
    window = body[:1024].lstrip(b"\xef\xbb\xbf \t\r\n\x0c\x00")
    return window.startswith(b"%PDF-")


def _looks_like_html(body: bytes) -> bool:
    sample = body[:4096].lstrip().lower()
    if sample.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        return True
    return b"<html" in sample[:800] or b"<!doctype html" in sample[:800]


def _paywall_text(body: bytes) -> bool:
    text = body[:8192].decode("utf-8", errors="ignore").casefold()
    return any(marker in text for marker in _PAYWALL_MARKERS)


def classify_download(status: int, content_type: str | None, body: bytes) -> str:
    """Return paper, html-abstract, 404, paywall, empty, or not-pdf.

    A paper requires PDF magic and a content-type that is not HTML. HTML
    served as application/pdf is an HTML abstract page.
    """
    code = int(status or 0)
    raw = body or b""
    kind = content_type_base(content_type)
    if code in {404, 410}:
        return "404"
    if code in {401, 402, 403}:
        return "paywall"
    if not raw.strip():
        return "empty"
    pdf_type = kind in _PDF_TYPES or kind == ""
    # A %PDF- prefix on an HTML or paywall page is not a saved PDF.
    # A body without the %PDF- magic is not a PDF either.
    if (
        pdf_magic(raw)
        and kind not in _HTML_TYPES
        and pdf_type
        and not _looks_like_html(raw)
        and not _paywall_text(raw)
    ):
        return "paper"
    if _paywall_text(raw):
        return "paywall"
    if kind in _HTML_TYPES or _looks_like_html(raw) or (kind in _PDF_TYPES and _looks_like_html(raw)):
        return "html-abstract"
    return "not-pdf"


def fetch_url(url: str) -> tuple[int, str | None, bytes]:
    """GET one address. Network failure is an empty download, not a paper."""
    request = urllib.request.Request(url, headers={"User-Agent": "essay-writer"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = int(getattr(response, "status", 200) or 200)
            header = response.headers.get("Content-Type")
            return status, header, response.read()
    except urllib.error.HTTPError as exc:
        header = exc.headers.get("Content-Type") if exc.headers else None
        try:
            payload = exc.read()
        except OSError:
            payload = b""
        return int(exc.code), header, payload or b""
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return 0, None, b""


def _empty_state() -> dict[str, Any]:
    return {
        "attempts": {},
        "seen_urls": [],
        "failures": [],
        "papers": [],
        "started_at": None,
        "last_useful_at": None,
        "stopped": False,
        "stop_reason": None,
    }


def _state_path(essay_id: str):
    return work_dir(essay_id) / STATE_NAME


def _load_state(essay_id: str) -> dict[str, Any]:
    path = _state_path(essay_id)
    state = _empty_state()
    if not path.is_file():
        return state
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return state
    if not isinstance(data, dict):
        return state
    attempts = data.get("attempts")
    if isinstance(attempts, dict):
        state["attempts"] = {
            str(key): int(value)
            for key, value in attempts.items()
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        }
    seen = data.get("seen_urls")
    if isinstance(seen, list):
        state["seen_urls"] = [item for item in seen if isinstance(item, str)]
    failures = data.get("failures")
    if isinstance(failures, list):
        state["failures"] = [item for item in failures if isinstance(item, dict) and item.get("url")]
    papers = data.get("papers")
    if isinstance(papers, list):
        state["papers"] = [item for item in papers if isinstance(item, dict) and item.get("url")]
    for key in ("started_at", "last_useful_at"):
        if isinstance(data.get(key), str):
            state[key] = data[key]
    state["stopped"] = bool(data.get("stopped"))
    reason = data.get("stop_reason")
    if reason in {"retries", "idle"}:
        state["stop_reason"] = reason
    return state


def _save_state(essay_id: str, state: dict[str, Any]) -> None:

    path = _state_path(essay_id)
    if research_file(essay_id, str(path), save=True) is None:
        from essay_writer.known_paths import refuse_repo_write

        refuse_repo_write(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _parse_time(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _clock(now: datetime | None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _http_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _pdf_name(doi: str | None, url: str, taken: set[str]) -> str:
    stem = doi or url
    stem = re.sub(r"^https?://", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._")[:80] or "download"
    name = f"{stem}.pdf"
    if name not in taken:
        return name
    number = 2
    while f"{stem}-{number}.pdf" in taken:
        number += 1
    return f"{stem}-{number}.pdf"


def _live_papers(essay_id: str, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop a saved path that is missing or no longer a PDF."""
    kept: list[dict[str, Any]] = []
    root = uploads_dir(essay_id).resolve()
    base = workspace_root()
    for item in papers:
        raw = item.get("path")
        if not isinstance(raw, str) or not raw.startswith("uploads/"):
            continue
        target = (base / raw).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            continue
        try:
            with target.open("rb") as handle:
                magic = pdf_magic(handle.read(1024))
        except OSError:
            continue
        if magic:
            kept.append(item)
    return kept


def _label(bucket: str) -> str:
    return BUCKET_LABELS.get(bucket, bucket)


def _cite(item: dict[str, Any]) -> str:
    for key in ("doi", "title", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Untitled download"


_URL = re.compile(r"https?://[^\s]+")
_LIST_INTRO = (
    "Leftovers only: sources not already in the papers zip. "
    "Citation lines stay on annotation.docx. "
    "Fetch each file from the university library."
)


def _web_address(value: object) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip()
    if _http_url(token):
        return token
    return ""


def _doi_url(value: object) -> str:
    """A doi.org address the row already carries. A bare DOI is not a URL."""
    if not isinstance(value, str):
        return ""
    token = value.strip()
    lower = token.casefold()
    if lower.startswith("https://doi.org/"):
        return token
    if lower.startswith("http://doi.org/"):
        return "https://doi.org/" + token.split("doi.org/", 1)[-1]
    return ""


def _row_url(item: dict[str, Any]) -> str:
    direct = _web_address(item.get("url"))
    if direct:
        return direct
    return _doi_url(item.get("doi"))


def _partition_download_list(
    failures: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    leftovers: list[dict[str, Any]] | None = None,
    opened: list[dict[str, Any]] | None = None,
    pdfs: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Cannot-open rows only. A saved PDF is not a leftover."""
    from essay_writer.research_packs import record_is_opened, same_source

    opened_rows = [item for item in (opened or []) if isinstance(item, dict)]
    saved = list(pdfs or [])

    def keep(item: dict[str, Any]) -> bool:
        return not record_is_opened(item, saved, opened_rows)

    failed = [item for item in failures if isinstance(item, dict) and keep(item)]
    held = [item for item in skipped if isinstance(item, dict) and keep(item)]
    blocked = failed + held
    waiting = [
        item
        for item in (leftovers or [])
        if isinstance(item, dict) and keep(item) and not any(same_source(item, other) for other in blocked)
    ]
    return waiting, failed, held


def _leftover_sentence(item: dict[str, Any]) -> str:
    label = _label(str(item.get("bucket") or "leftover"))
    cite = _cite(item)
    url = _web_address(item.get("url"))
    if url and url not in cite:
        return f"{label}. {cite}. {url}. Fetch a PDF for this gathered source."
    return f"{label}. {cite}. Fetch a PDF for this gathered source."


def _list_line(text: str) -> str:
    """Student Word line. Titles stay. House labels and private paths do not."""

    return prose_for_surface(_scrub_paths_in_text(text), "annotation")


def _add_hyperlink(paragraph, url: str, text: str) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    relation = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relation)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attribute in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attribute), "Arial")
    props.append(fonts)
    size = OxmlElement("w:sz")
    size.set(qn("w:val"), "24")
    props.append(size)
    size_cs = OxmlElement("w:szCs")
    size_cs.set(qn("w:val"), "24")
    props.append(size_cs)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    props.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    run.append(props)
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _write_line(document, text: str, *, bold: bool = False, hang: bool = False, size: int = 12) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    from essay_writer.word import _font

    cleaned = _list_line(text)
    if not cleaned:
        return
    if len(document.paragraphs) == 1 and not document.paragraphs[0].text:
        paragraph = document.paragraphs[0]
    else:
        paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.line_spacing = 1.5
    if hang:
        paragraph.paragraph_format.left_indent = Inches(0.5)
        paragraph.paragraph_format.first_line_indent = Inches(-0.5)
        paragraph.paragraph_format.space_after = Pt(8)
    cursor = 0
    for match in _URL.finditer(cleaned):
        if match.start() > cursor:
            run = paragraph.add_run(cleaned[cursor : match.start()])
            _font(run, size, bold=bold)
        raw = match.group(0)
        href = raw.rstrip(".,;:")
        tail = raw[len(href) :]
        if href:
            _add_hyperlink(paragraph, href, href)
        if tail:
            run = paragraph.add_run(tail)
            _font(run, size, bold=bold)
        cursor = match.end()
    if cursor < len(cleaned):
        run = paragraph.add_run(cleaned[cursor:])
        _font(run, size, bold=bold)


def _save_docx(path, lines: list[tuple[str, bool, bool]]) -> None:
    from docx import Document

    document = Document()
    _style_document(document)
    document.core_properties.title = "Sources to download"
    for index, (text, bold, hang) in enumerate(lines):
        _write_line(document, text, bold=bold, hang=hang, size=14 if index == 0 and bold else 12)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".docx.tmp")
    document.save(str(temporary))
    os.replace(temporary, path)


def links_card(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Chat card for sources that still need a PDF. Title, cite, and URL."""

    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = _row_url(item)
        cite = say(_cite(item)) or _cite(item)
        title_raw = item.get("title")
        title = title_raw.strip() if isinstance(title_raw, str) and title_raw.strip() else cite
        title = say(title) or title
        key = (url or cite).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        entry = {
            "title": title,
            "cite": cite,
            "label": _label(str(item.get("bucket") or "leftover")),
        }
        if url:
            entry["url"] = url
        items.append(entry)
    text = (
        "These sources still need a PDF. Each line has the title and a link. "
        "Fetch the file from the university library."
        if items
        else "Nothing is waiting on this list."
    )
    return {
        "deliver": "chat",
        "kind": "links",
        "name": "Sources to download",
        "text": say(text),
        "items": items,
    }


def download_links(
    failures: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    leftovers: list[dict[str, Any]] | None = None,
    *,
    opened: list[dict[str, Any]] | None = None,
    pdfs: list[Path] | None = None,
) -> dict[str, Any]:
    waiting, failed, held = _partition_download_list(failures, skipped, leftovers, opened, pdfs)
    return links_card(waiting + failed + held)


def _write_download_list(
    essay_id: str,
    failures: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    *,
    leftovers: list[dict[str, Any]] | None = None,
    opened: list[dict[str, Any]] | None = None,
    pdfs: list[Path] | None = None,
) -> str:
    from essay_writer.roll_forward import without_keepers

    failures = without_keepers(essay_id, failures)
    skipped = without_keepers(essay_id, skipped)
    leftovers = without_keepers(essay_id, leftovers)
    waiting, failed, held = _partition_download_list(failures, skipped, leftovers, opened, pdfs)
    lines: list[tuple[str, bool, bool]] = [
        ("Sources to download", True, False),
        (_LIST_INTRO, False, False),
    ]
    if not waiting and not failed and not held:
        lines.append(("Nothing is waiting on this list.", False, False))
    for item in waiting:
        lines.append((_leftover_sentence(item), False, True))
    for item in failed:
        lines.append(
            (
                f"{_label(str(item.get('bucket')))}. {_cite(item)}. {item.get('url', '')}. "
                "This file was not saved and is not a paper.",
                False,
                True,
            ),
        )
    for item in held:
        lines.append(
            (
                f"Not fetched. {_cite(item)}. {item.get('url', '')}. "
                "The download path stopped before this file was fetched. It is not a paper.",
                False,
                True,
            ),
        )
    path = work_dir(essay_id) / "output" / DOWNLOAD_LIST_NAME
    _save_docx(path, lines)
    return relative(path)


def _write_annotation(essay_id: str, papers: list[dict[str, Any]]) -> str:
    from essay_writer.research_packs import download_annotation

    path = work_dir(essay_id) / "output" / ANNOTATION_NAME
    download_annotation(path, papers, essay_id)
    return relative(path)


def _write_papers_zip(essay_id: str, papers: list[dict[str, Any]]) -> str | None:
    from essay_writer.research_packs import write_papers_zip

    paths = []
    for item in papers:
        raw = item.get("path")
        if isinstance(raw, str) and raw.strip():
            paths.append(workspace_root() / raw.strip())
    if not paths:
        return None
    path = work_dir(essay_id) / "output" / "papers.zip"
    write_papers_zip(path, paths)
    return relative(path)


def _failure_row(candidate: dict[str, Any], bucket: str, attempts: int) -> dict[str, Any]:
    row: dict[str, Any] = {"url": candidate["url"], "bucket": bucket, "attempts": attempts}
    if candidate.get("doi"):
        row["doi"] = candidate["doi"]
    if candidate.get("title"):
        row["title"] = candidate["title"]
    return row


def _upsert_failure(failures: list[dict[str, Any]], row: dict[str, Any]) -> None:
    for index, item in enumerate(failures):
        if item.get("url") == row["url"]:
            failures[index] = row
            return
    failures.append(row)


def _next_text(
    failures: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    papers: list[dict[str, Any]],
    stopped: bool,
    reason: str | None,
) -> str | None:
    parts: list[str] = []
    for item in failures:
        parts.append(f"{_cite(item)} ({_label(str(item.get('bucket')))})")
    for item in skipped:
        parts.append(f"{_cite(item)} (not fetched)")
    listed = "; ".join(parts) if parts else "nothing further"
    saved = ", ".join(_cite(item) for item in papers) if papers else "none"
    if stopped and reason == "retries":
        return (
            "The same download failed 3 times, so that path has stopped. "
            f"Saved PDFs: {saved}. Still missing: {listed}. "
            "annotation.docx and download-list.docx are written from the files already saved. "
            "Fetch the missing ones from the university library. Do not retry the failed address."
        )
    if stopped and reason == "idle":
        return (
            "No new PDF was saved for more than 10 minutes, so that path has stopped. "
            f"Saved PDFs: {saved}. Still missing: {listed}. "
            "annotation.docx and download-list.docx are written from the files already saved. "
            "Fetch the missing ones from the university library."
        )
    if failures:
        return (
            f"Some files were not saved and are not papers. Still missing: {listed}. "
            f"Saved PDFs: {saved}. "
            "The download list names each one to fetch from the university library."
        )
    return None


def _result(
    essay_id: str,
    state: dict[str, Any],
    *,
    fetched: list[str],
    skipped: list[dict[str, Any]],
    download_list: str | None,
    annotation: str | None,
    papers_zip: str | None = None,
) -> dict[str, Any]:
    papers = state["papers"]
    failures = state["failures"]
    stopped = bool(state.get("stopped"))
    reason = state.get("stop_reason") if stopped else None
    _waiting, failed, held = _partition_download_list(failures, skipped, [], papers)
    return {
        "ok": True,
        "essay_id": essay_id,
        "wrote": bool(download_list or annotation or papers),
        "papers": papers,
        "failures": failures,
        "skipped": skipped,
        "stopped": stopped,
        "stop_reason": reason,
        "missing": [_cite(item) for item in failed] + [_cite(item) for item in held],
        "attempts": state["attempts"],
        "fetched": fetched,
        "download_list": download_list,
        "annotation": annotation,
        "annotation_chat": _annotation_chat(annotation),
        "papers_zip": papers_zip,
        "links": links_card(failed + held),
        "next": _next_text(failed, held, papers, stopped, reason),
    }


def _annotation_chat(annotation: str | None) -> dict[str, Any] | None:
    if not isinstance(annotation, str) or not annotation.strip():
        return None
    path = workspace_root() / annotation
    if not path.is_file():
        return None
    from essay_writer.research_packs import chat_docx

    return chat_docx(path)


def _normalise_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        url = raw.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        url = url.strip()
        if url in seen:
            continue
        seen.add(url)
        item: dict[str, Any] = {"url": url}
        doi = raw.get("doi")
        title = raw.get("title")
        if isinstance(doi, str) and doi.strip():
            item["doi"] = doi.strip()
        if isinstance(title, str) and title.strip():
            item["title"] = title.strip()
        chosen.append(item)
    return chosen


def run_downloads(
    essay_id: str,
    candidates: list[dict[str, Any]],
    *,
    fetch: Fetch | None = None,
    now: datetime | None = None,
    retry_known: bool = False,
) -> dict[str, Any]:
    """Fetch each open copy once. Keep real PDFs. Classify the rest.

    A stopped path does not fetch the same addresses again. A new address
    can still be saved. retry_known fetches leftover addresses already
    stored, still stopping after 3 tries, and does not open a new look-up.
    """
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)

    blocked = guard_write_door(work_dir(essay_id), uploads_dir(essay_id))
    if blocked:
        return blocked
    moment = _clock(now)
    getter = fetch or fetch_url
    rows = _normalise_candidates(candidates)
    state = _load_state(essay_id)
    state["papers"] = _live_papers(essay_id, state["papers"])
    fetched: list[str] = []
    skipped: list[dict[str, Any]] = []
    seen = set(state["seen_urls"])
    fresh = [item for item in rows if item["url"] not in seen]
    if retry_known:
        paper_urls = {item["url"] for item in state["papers"]}
        attempts = state["attempts"]
        work = [
            item
            for item in rows
            if item["url"] not in paper_urls and attempts.get(item["url"], 0) < MAX_ATTEMPTS
        ]
        skipped = [
            item
            for item in rows
            if item["url"] not in paper_urls and attempts.get(item["url"], 0) >= MAX_ATTEMPTS
        ]
        if state.get("started_at") is None:
            state["started_at"] = _stamp(moment)
        state["stopped"] = False
        state["stop_reason"] = None
        paper_urls = {item["url"] for item in state["papers"]}
        for candidate in work:
            url = candidate["url"]
            seen.add(url)
            if url in paper_urls:
                continue
            if attempts.get(url, 0) >= MAX_ATTEMPTS:
                state["stopped"] = True
                state["stop_reason"] = "retries"
                continue
            bucket, body = _fetch_bucket(url, getter)
            fetched.append(url)
            if bucket == "paper":
                saved = _save_pdf(essay_id, candidate, body, state["papers"])
                if saved is None:
                    attempts[url] = attempts.get(url, 0) + 1
                    _upsert_failure(state["failures"], _failure_row(candidate, "empty", attempts[url]))
                elif saved.get("gap_only"):
                    attempts[url] = attempts.get(url, 0) + 1
                    row = _failure_row(candidate, "read-gap", attempts[url])
                    gaps = saved.get("read_gaps")
                    if isinstance(gaps, list) and gaps:
                        row["read_gaps"] = gaps
                    _upsert_failure(state["failures"], row)
                else:
                    state["failures"] = [item for item in state["failures"] if item.get("url") != url]
                    state["papers"].append(saved)
                    paper_urls.add(url)
                    state["last_useful_at"] = _stamp(moment)
                if attempts.get(url, 0) >= MAX_ATTEMPTS:
                    state["stopped"] = True
                    state["stop_reason"] = "retries"
                continue
            attempts[url] = attempts.get(url, 0) + 1
            _upsert_failure(state["failures"], _failure_row(candidate, bucket, attempts[url]))
            if attempts[url] >= MAX_ATTEMPTS:
                state["stopped"] = True
                state["stop_reason"] = "retries"
        state["seen_urls"] = sorted(seen)
        state["attempts"] = attempts
        download_list = None
        annotation = None
        if state.get("stopped") or state["failures"]:
            download_list = _write_download_list(
                essay_id,
                state["failures"],
                skipped,
                opened=state["papers"],
            )
        if state.get("stopped"):
            _listed, annotation = _ship(essay_id, state, skipped)
            download_list = _listed
        papers_zip = _write_papers_zip(essay_id, state["papers"])
        _save_state(essay_id, state)
        return _result(
            essay_id,
            state,
            fetched=fetched,
            skipped=skipped,
            download_list=download_list,
            annotation=annotation,
            papers_zip=papers_zip,
        )
    if state.get("stopped") and not fresh:
        listed, noted = _ship(essay_id, state, skipped)
        zipped = _write_papers_zip(essay_id, state["papers"])
        _save_state(essay_id, state)
        return _result(
            essay_id,
            state,
            fetched=fetched,
            skipped=skipped,
            download_list=listed,
            annotation=noted,
            papers_zip=zipped,
        )
    if state.get("stopped") and fresh:
        state["stopped"] = False
        state["stop_reason"] = None

    mark = _parse_time(state.get("last_useful_at")) or _parse_time(state.get("started_at"))
    idle = bool(mark and moment - mark > STUCK_AFTER)
    if idle and not fresh:
        state["stopped"] = True
        state["stop_reason"] = "idle"
        listed, noted = _ship(essay_id, state, skipped)
        zipped = _write_papers_zip(essay_id, state["papers"])
        _save_state(essay_id, state)
        return _result(
            essay_id,
            state,
            fetched=fetched,
            skipped=skipped,
            download_list=listed,
            annotation=noted,
            papers_zip=zipped,
        )

    if state.get("started_at") is None:
        state["started_at"] = _stamp(moment)
    work = fresh if idle else rows
    if idle:
        state["stopped"] = False
        state["stop_reason"] = None
        known = {item["url"] for item in state["papers"]} | {item["url"] for item in state["failures"]}
        skipped = [item for item in rows if item["url"] not in known and item not in work]

    paper_urls = {item["url"] for item in state["papers"]}
    url_attempts: dict[str, int] = state["attempts"]
    for candidate in work:
        url = candidate["url"]
        seen.add(url)
        if url in paper_urls:
            continue
        if url_attempts.get(url, 0) >= MAX_ATTEMPTS:
            state["stopped"] = True
            state["stop_reason"] = "retries"
            continue
        bucket, body = _fetch_bucket(url, getter)
        fetched.append(url)
        if bucket == "paper":
            saved = _save_pdf(essay_id, candidate, body, state["papers"])
            if saved is None:
                url_attempts[url] = url_attempts.get(url, 0) + 1
                _upsert_failure(state["failures"], _failure_row(candidate, "empty", url_attempts[url]))
            elif saved.get("gap_only"):
                url_attempts[url] = url_attempts.get(url, 0) + 1
                row = _failure_row(candidate, "read-gap", url_attempts[url])
                gaps = saved.get("read_gaps")
                if isinstance(gaps, list) and gaps:
                    row["read_gaps"] = gaps
                _upsert_failure(state["failures"], row)
            else:
                state["failures"] = [item for item in state["failures"] if item.get("url") != url]
                state["papers"].append(saved)
                paper_urls.add(url)
                state["last_useful_at"] = _stamp(moment)
            if url_attempts.get(url, 0) >= MAX_ATTEMPTS:
                state["stopped"] = True
                state["stop_reason"] = "retries"
            continue
        url_attempts[url] = url_attempts.get(url, 0) + 1
        _upsert_failure(state["failures"], _failure_row(candidate, bucket, url_attempts[url]))
        if url_attempts[url] >= MAX_ATTEMPTS:
            state["stopped"] = True
            state["stop_reason"] = "retries"

    state["seen_urls"] = sorted(seen)
    state["attempts"] = url_attempts
    download_list = None
    annotation = None
    if state.get("stopped"):
        download_list, annotation = _ship(essay_id, state, skipped)
    elif state["failures"]:
        download_list = _write_download_list(
            essay_id,
            state["failures"],
            skipped,
            opened=state["papers"],
        )
    papers_zip = _write_papers_zip(essay_id, state["papers"])
    _save_state(essay_id, state)
    return _result(
        essay_id,
        state,
        fetched=fetched,
        skipped=skipped,
        download_list=download_list,
        annotation=annotation,
        papers_zip=papers_zip,
    )


def _fetch_bucket(url: str, getter: Fetch) -> tuple[str, bytes]:
    if not _http_url(url):
        return "empty", b""
    status, content_type, body = getter(url)
    return classify_download(status, content_type, body), body or b""


def _paper_row(candidate: dict[str, Any], path) -> dict[str, Any]:
    row: dict[str, Any] = {"url": candidate["url"], "path": relative(path), "bucket": "paper"}
    if candidate.get("doi"):
        row["doi"] = candidate["doi"]
    if candidate.get("title"):
        row["title"] = candidate["title"]
    return row


def _save_pdf(
    essay_id: str,
    candidate: dict[str, Any],
    body: bytes,
    papers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not pdf_magic(body):
        return None
    folder = uploads_dir(essay_id)
    folder.mkdir(parents=True, exist_ok=True)
    taken = {path.name for path in folder.glob("*.pdf")}
    for item in papers:
        raw = item.get("path")
        if isinstance(raw, str) and raw:
            taken.add(raw.rsplit("/", 1)[-1])
    name = _pdf_name(candidate.get("doi"), candidate["url"], taken)
    path = folder / name

    if research_file(essay_id, str(path), save=True) is None:
        return None
    temporary = path.with_suffix(".pdf.tmp")
    temporary.write_bytes(body)
    os.replace(temporary, path)
    from essay_writer.pdf_read import PART_LIMIT, chop_pdf, readable_pdf

    if not readable_pdf(body) or len(body) > PART_LIMIT:
        chopped = chop_pdf(path)
        gaps = chopped.get("gaps") or []
        readable_parts = chopped.get("parts") or []
        if readable_pdf(body) and len(body) > PART_LIMIT:
            row = _paper_row(candidate, path)
            if gaps:
                row["read_gaps"] = gaps
            return row
        if readable_parts:
            first = readable_parts[0]
            part_path = first.get("path")
            if isinstance(part_path, str):
                row = _paper_row(candidate, Path(part_path))
                if gaps:
                    row["read_gaps"] = gaps
                return row
        return {
            "gap_only": True,
            "path": relative(path),
            "read_gaps": gaps,
            "bytes_leave_machine": False,
        }
    with path.open("rb") as handle:
        saved = handle.read(1024)
    if not pdf_magic(saved):
        path.unlink(missing_ok=True)
        return None
    return _paper_row(candidate, path)


def _ship(
    essay_id: str,
    state: dict[str, Any],
    skipped: list[dict[str, Any]],
) -> tuple[str, str]:
    listed = _write_download_list(
        essay_id,
        state["failures"],
        skipped,
        opened=state["papers"],
    )
    noted = _write_annotation(essay_id, state["papers"])
    return listed, noted

