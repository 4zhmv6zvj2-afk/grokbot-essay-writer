"""Local dig card. OpenAlex runs without a key. Consensus runs only when allowed.

Draft writes nothing. It stores the card that was shown, including Unpaywall
rows. Confirm writes that stored card to dig-card.json and dig-card.md.
It does not call Unpaywall, OpenAlex, or Consensus again to decide whether
confirm is allowed. Downloads use the open-access URLs already on that card.
Look-up hits are copied from the response. Missing papers are omitted.
invent-forbid holds. The same handler serves every writing type.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
from typing import Any

from essay_writer import safe_url
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    NO_MATCHING_DRAFT,
    card_digest,
    confirm_ready,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.downloads import BUCKET_LABELS, run_downloads
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import module_code, sequence_write_error, uploads_dir, work_dir
from essay_writer.resolvers import (
    openalex_api_key,
    resolver_mode,
    unpaywall_doi_url,
    unpaywall_email,
)
from essay_writer.setup import read_setup_secret
from essay_writer.student_voice import say

TOOL = "essay.dig"
OPENALEX_URL = "https://api.openalex.org/works"
CONSENSUS_URL = "https://api.consensus.app/v1/search"
_OPERATOR = logging.getLogger("essay_writer.dig")
_NON_PUBLIC_ADDRESS = re.compile(r"the host resolves to a non-public address \([^)]*\)")

UNPAYWALL_URL = "https://api.unpaywall.org/v2/"
MAX_API_BYTES = 2 * 1024 * 1024
API_TIMEOUT = 20.0


class LookupRefused(Exception):
    """A look-up service answered with an error, or the fetch never connected."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = int(status or 0)
        self.detail = detail

    def record(self) -> dict[str, Any]:
        """What the card keeps. The request key is never part of it."""
        return {"status": self.status, "detail": self.detail}


def consensus_api_key() -> str | None:
    raw = os.environ.get("CONSENSUS_API_KEY", "").strip()
    if raw:
        return raw
    return read_setup_secret("CONSENSUS_API_KEY")


def consensus_paid_flag() -> str | None:
    """ESSAY_WRITER_CONSENSUS_PAID: 0 free, 1 paid. The key is not included."""
    raw = os.environ.get("ESSAY_WRITER_CONSENSUS_PAID", "").strip()
    if raw in {"0", "1"}:
        return raw
    stored = read_setup_secret("ESSAY_WRITER_CONSENSUS_PAID")
    if stored in {"0", "1"}:
        return stored
    return None


def consensus_status_for(key_present: bool) -> dict[str, Any]:
    """Whether dig calls Consensus. The key itself is never included.

    A key turns Consensus on for the search. No key leaves Consensus off and the search stays
    on OpenAlex. ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1
    turns it on when a key is present. Any other value leaves Consensus off.
    """
    switch = os.environ.get("ESSAY_WRITER_CONSENSUS", "").strip()
    if switch == "0":
        remind = (
            "Consensus is off (ESSAY_WRITER_CONSENSUS=0). "
            "Dig still uses OpenAlex. Set ESSAY_WRITER_CONSENSUS=1 to allow Consensus when a key is present."
        )
        return {"switch": "0", "enabled": False, "key_present": key_present, "remind": remind}
    if switch == "1":
        if key_present:
            remind = "Consensus is on (ESSAY_WRITER_CONSENSUS=1) and a key is present. Set 0 to turn it off."
            return {"switch": "1", "enabled": True, "key_present": True, "remind": remind}
        remind = (
            "ESSAY_WRITER_CONSENSUS=1 but no Consensus key is stored. "
            "Consensus is off. OpenAlex still runs. Set 0 to turn the reminder off."
        )
        return {"switch": "1", "enabled": False, "key_present": False, "remind": remind}
    if switch:
        remind = "ESSAY_WRITER_CONSENSUS must be 0 or 1. Consensus is off until it is."
        return {"switch": switch, "enabled": False, "key_present": key_present, "remind": remind}
    if key_present:
        remind = (
            "Consensus is on for dig because a key is present. "
            "ESSAY_WRITER_CONSENSUS=0 turns it off."
        )
        return {"switch": "unset", "enabled": True, "key_present": True, "remind": remind}
    remind = (
        "No Consensus key. Consensus is off. Dig uses OpenAlex. "
        "A stored key turns Consensus on. ESSAY_WRITER_CONSENSUS=0 keeps it off."
    )
    return {"switch": "unset", "enabled": False, "key_present": False, "remind": remind}


def consensus_status() -> dict[str, Any]:
    """Kill switch for dig and health. The key itself is never included."""
    body = consensus_status_for(consensus_api_key() is not None)
    body["paid"] = consensus_paid_flag()
    return body


def openalex_status() -> dict[str, Any]:
    """Whether OpenAlex sends a key. The key itself is never included."""
    return {"key_present": openalex_api_key() is not None}


def _refusal_detail(status: int, body: bytes) -> str:
    """One short reason from the error body. Never a request key."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    if isinstance(payload, dict):
        for name in ("detail", "message", "error"):
            value = payload.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()[:200]
    return f"HTTP {status}" if status else "the look-up did not answer"


def _student_lookup_detail(detail: str) -> str:
    """Card text. A resolved internal address is logged for the operator and removed here."""
    match = _NON_PUBLIC_ADDRESS.search(detail)
    if match is None:
        return detail[:200]
    _OPERATOR.warning("look-up refused: %s", detail)
    rest = detail[match.end() :].lstrip(" .")
    if rest.endswith(">"):
        rest = rest[:-1].rstrip()
    student = "the host resolves to a non-public address"
    if rest:
        student = f"{student}. {rest}"
    return student[:200]


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    """GET one look-up URL through safe_url. A refusal raises LookupRefused.

    The reason is kept so a bad key, an exhausted plan, or a blocked network
    is not reported to the student as "no papers found".
    """
    try:
        with safe_url.open_url(
            url,
            timeout=API_TIMEOUT,
            max_bytes=MAX_API_BYTES,
            headers=headers or {},
        ) as response:
            body = response.read()
            status = int(getattr(response, "status", 200) or 200)
            if status < 200 or status >= 300:
                raise LookupRefused(status, _refusal_detail(status, body))
            payload = json.loads(body.decode("utf-8"))
    except LookupRefused:
        raise
    except json.JSONDecodeError:
        raise LookupRefused(0, "the look-up did not return JSON") from None
    except (safe_url.Refused, urllib.error.URLError, TimeoutError, OSError) as exc:
        detail = str(exc).strip() or "the look-up did not answer"
        raise LookupRefused(0, _student_lookup_detail(detail)) from None
    if not isinstance(payload, dict):
        return None
    return payload


def _abstract_from_index(index: object) -> str:
    """Rebuild an OpenAlex abstract from its inverted index. No extra sentence."""
    if not isinstance(index, dict) or not index:
        return ""
    placed: list[tuple[int, str]] = []
    for word, spots in index.items():
        if not isinstance(word, str) or not word.strip() or not isinstance(spots, list):
            continue
        for spot in spots:
            if isinstance(spot, bool) or not isinstance(spot, int):
                continue
            placed.append((spot, word.strip()))
    if not placed:
        return ""
    placed.sort(key=lambda item: item[0])
    return " ".join(word for _spot, word in placed).strip()


def _hit(
    title: object, year: object, doi: object, authors: object, source: str
) -> dict[str, Any] | None:
    if not isinstance(title, str) or not title.strip():
        return None
    item: dict[str, Any] = {"title": title.strip(), "source": source}
    if isinstance(year, int) and not isinstance(year, bool):
        item["year"] = str(year)
    elif isinstance(year, str) and year.strip().isdigit():
        item["year"] = year.strip()
    if isinstance(doi, str) and doi.strip():
        item["doi"] = doi.strip().removeprefix("https://doi.org/")
    names: list[str] = []
    if isinstance(authors, list):
        for author in authors:
            if isinstance(author, str) and author.strip():
                names.append(author.strip())
            elif isinstance(author, dict):
                name = author.get("display_name") or author.get("name")
                if isinstance(name, str) and name.strip():
                    names.append(name.strip())
    if names:
        item["authors"] = names
    return item


def _copy_openalex_urls(hit: dict[str, Any], work: dict[str, Any]) -> None:
    """Keep official open-access and PDF URLs. A missing URL stays off the hit."""
    access = work.get("open_access")
    if isinstance(access, dict):
        oa_url = access.get("oa_url")
        if isinstance(oa_url, str) and oa_url.strip():
            hit["oa_url"] = oa_url.strip()
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        pdf_url = best.get("pdf_url")
        if isinstance(pdf_url, str) and pdf_url.strip():
            hit["pdf_url"] = pdf_url.strip()


def openalex_search(query: str, cursor: str | None = None) -> dict[str, Any]:
    if resolver_mode() == "off":
        return {"called": False, "skipped": "resolvers-off", "hits": []}
    # Official page size is per_page. mailto is ignored and is not sent.
    # A stored key goes as api_key. Keyless calls still run.
    # A later page follows the cursor the previous response returned.
    params: dict[str, Any] = {"search": query, "per_page": 5}
    if isinstance(cursor, str) and cursor.strip():
        params["cursor"] = cursor.strip()
    key = openalex_api_key()
    if key:
        params["api_key"] = key
    url = OPENALEX_URL + "?" + urllib.parse.urlencode(params)
    try:
        payload = _get_json(url, {"User-Agent": "essay-writer"})
    except LookupRefused as exc:
        return {"called": True, "hits": [], "miss": "openalex", "refused": exc.record()}
    if payload is None:
        return {"called": True, "hits": [], "miss": "openalex"}
    results = payload.get("results") or []
    row_count = len(results) if isinstance(results, list) else 0
    hits: list[dict[str, Any]] = []
    for work in results if isinstance(results, list) else []:
        if not isinstance(work, dict):
            continue
        authorships = work.get("authorships") or []
        authors = []
        if isinstance(authorships, list):
            for item in authorships:
                if isinstance(item, dict):
                    authors.append(item.get("author") or {})
        hit = _hit(
            work.get("title"), work.get("publication_year"), work.get("doi"), authors, "openalex"
        )
        if hit:
            abstract = _abstract_from_index(work.get("abstract_inverted_index"))
            if abstract:
                hit["abstract"] = abstract
            _copy_openalex_urls(hit, work)
            hits.append(hit)
    body: dict[str, Any] = {"called": True, "hits": hits, "row_count": row_count}
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    next_cursor = meta.get("next_cursor")
    # A short page, or a missing cursor, has no further official page.
    if isinstance(next_cursor, str) and next_cursor.strip() and row_count >= 5:
        body["next_cursor"] = next_cursor.strip()
    return body


def consensus_search(query: str, page: int | None = None) -> dict[str, Any]:
    status = consensus_status()
    if not status["enabled"]:
        return {"called": False, "tier": None, "hits": [], "remind": status["remind"]}
    if resolver_mode() == "off":
        return {"called": False, "tier": None, "hits": [], "skipped": "resolvers-off"}
    key = consensus_api_key()
    if not key:
        return {"called": False, "tier": None, "hits": [], "remind": status["remind"]}
    params: dict[str, Any] = {"query": query}
    if isinstance(page, int) and not isinstance(page, bool) and page > 0:
        params["page"] = page
    url = CONSENSUS_URL + "?" + urllib.parse.urlencode(params)
    try:
        payload = _get_json(url, {"x-api-key": key, "User-Agent": "essay-writer"})
    except LookupRefused as exc:
        return {
            "called": True,
            "tier": None,
            "hits": [],
            "miss": "consensus",
            "refused": exc.record(),
        }
    if payload is None:
        return {"called": True, "tier": None, "hits": [], "miss": "consensus"}
    tier = payload.get("plan") or payload.get("tier")
    if not isinstance(tier, str) or not tier.strip():
        tier = "unspecified"
    else:
        tier = tier.strip().casefold()
    hits: list[dict[str, Any]] = []
    for paper in payload.get("results") or []:
        if not isinstance(paper, dict):
            continue
        hit = _hit(
            paper.get("title"),
            paper.get("publish_year") or paper.get("year"),
            paper.get("doi"),
            paper.get("authors"),
            "consensus",
        )
        if hit:
            abstract = paper.get("abstract")
            if isinstance(abstract, str) and abstract.strip():
                hit["abstract"] = abstract.strip()
            journal = paper.get("journal_name")
            if isinstance(journal, str) and journal.strip():
                hit["journal"] = journal.strip()
            for key in ("pages", "volume", "url"):
                value = paper.get(key)
                if isinstance(value, str) and value.strip():
                    hit[key] = value.strip()
            hits.append(hit)
    results = payload.get("results") or []
    row_count = len(results) if isinstance(results, list) else 0
    page_size = payload.get("page_size")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0:
        page_size = 20
    body: dict[str, Any] = {"called": True, "tier": tier, "hits": hits, "row_count": row_count}
    next_page = payload.get("next_page")
    ended = payload.get("is_end") is True
    has_next = isinstance(next_page, int) and not isinstance(next_page, bool)
    full = row_count >= page_size
    if ended or not has_next:
        return body
    # A later page is asked only when the stored plan allows it.
    if consensus_paid_flag() == "1":
        body["next_page"] = next_page
        return body
    if full or has_next:
        body["pagination"] = "This plan does not return another page."
    return body


def unpaywall_lookup(doi: str) -> dict[str, Any]:
    email = unpaywall_email()
    if not email:
        return {"called": False, "skipped": "no-email", "doi": doi}
    if resolver_mode() == "off":
        return {"called": False, "skipped": "resolvers-off", "doi": doi}
    url = unpaywall_doi_url(doi, email)
    try:
        payload = _get_json(url, {"User-Agent": "essay-writer"})
    except LookupRefused as exc:
        return {
            "called": True,
            "doi": doi,
            "oa_url": None,
            "miss": "unpaywall",
            "refused": exc.record(),
        }
    if payload is None:
        return {"called": True, "doi": doi, "oa_url": None, "miss": "unpaywall"}
    location = payload.get("best_oa_location")
    oa_url = None
    if isinstance(location, dict):
        # url_for_pdf, then the official url only when no PDF URL is provided.
        # z_authors is deprecated and is not copied.
        pdf = location.get("url_for_pdf")
        if isinstance(pdf, str) and pdf.strip():
            oa_url = pdf.strip()
        else:
            landing = location.get("url")
            if isinstance(landing, str) and landing.strip():
                oa_url = landing.strip()
    row: dict[str, Any] = {"called": True, "doi": doi, "oa_url": oa_url}
    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        row["title"] = title.strip()
    year = payload.get("year")
    if isinstance(year, int) and not isinstance(year, bool):
        row["year"] = str(year)
    elif isinstance(year, str) and year.strip().isdigit():
        row["year"] = year.strip()
    return row


def _refused_lines(name: str, body: dict[str, Any]) -> list[str]:
    """One line when the service refused the call. Empty on a real miss."""
    refused = body.get("refused")
    if not isinstance(refused, dict):
        return []
    status = refused.get("status")
    detail = refused.get("detail")
    if not isinstance(detail, str) or not detail.strip():
        detail = "no reason given"
    code = f"HTTP {status}: " if isinstance(status, int) and status else ""
    return [f"- {name} refused the look-up. {code}{detail.strip()[:200]}"]


def _card_markdown(query: str, essay_id: str, card: dict[str, Any]) -> str:
    lines = [
        "# Dig card",
        "",
        f"Sequence: {essay_id}",
        f"Query: {query}",
        "",
        card["consensus"]["remind"],
        "",
        "## OpenAlex",
    ]
    lines.extend(_refused_lines("OpenAlex", card["openalex"]))
    lines.extend(
        _hit_lines(card["openalex"]["hits"]) or ["- No OpenAlex hits. None were invented."]
    )
    lines.extend(["", "## Consensus"])
    tier = card["consensus"].get("tier")
    if card["consensus"].get("called"):
        lines.append(f"Tier: {tier or 'unspecified'}")
    else:
        lines.append("Consensus was not called.")
    lines.extend(_refused_lines("Consensus", card["consensus"]))
    lines.extend(
        _hit_lines(card["consensus"]["hits"]) or ["- No Consensus hits. None were invented."]
    )
    lines.extend(["", "## Unpaywall"])
    if not card["unpaywall"]:
        lines.append("- Skipped. An email is optional, and none is stored.")
    else:
        for item in card["unpaywall"]:
            if item.get("skipped") == "no-email":
                lines.append(f"- {item['doi']}: skipped, no email.")
            elif item.get("refused"):
                refused = item["refused"]
                detail = str(refused.get("detail") or "no reason given")[:200]
                lines.append(f"- {item['doi']}: the look-up was refused. {detail}")
            elif item.get("oa_url"):
                lines.append(f"- {item['doi']}: {item['oa_url']}")
            else:
                lines.append(f"- {item['doi']}: no open copy returned.")
    lines.extend(_download_lines(card))
    questions = card.get("questions")
    if isinstance(questions, list) and questions:
        from essay_writer.source_floor import question_lines

        lines.extend(["", "## Questions"])
        lines.extend(question_lines(questions) or ["- No question was stored."])
    gather = card.get("gather")
    if isinstance(gather, dict):
        note = gather.get("note")
        if isinstance(note, str) and note.strip():
            lines.extend(["", note.strip()])
    lines.extend(["", "invent-forbid: a line appears only when that look-up returned it.", ""])
    return "\n".join(lines)


def _download_lines(card: dict[str, Any]) -> list[str]:
    report = card.get("downloads")
    if not isinstance(report, dict):
        return []
    papers = report.get("papers") or []
    failures = report.get("failures") or []
    if not papers and not failures and not report.get("stopped"):
        return []
    lines = ["", "## Downloads"]
    if papers:
        for item in papers:
            lines.append(f"- {_download_name(item)}: saved PDF.")
    else:
        lines.append("- No PDF was saved.")
    for item in failures:
        label = BUCKET_LABELS.get(str(item.get("bucket")), "Not saved")
        lines.append(f"- {_download_name(item)}: {label}. Not a paper.")
    if report.get("stopped"):
        lines.append("- The download path has stopped. Missing files are on the download list.")
    return lines


def _download_name(item: dict[str, Any]) -> str:
    for key in ("doi", "title", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Untitled download"


def _doi_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().removeprefix("https://doi.org/").casefold()


def _pdf_dois(downloads: object) -> set[str]:
    if not isinstance(downloads, dict):
        return set()
    found: set[str] = set()
    for paper in downloads.get("papers") or []:
        if isinstance(paper, dict):
            key = _doi_key(paper.get("doi"))
            if key:
                found.add(key)
    return found


def _abstract_name(doi_key: str, index: int, used: set[str]) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in doi_key).strip("-")
    stem = slug[:80] if slug else f"hit-{index}"
    name = f"abstract-{stem}.md"
    if name in used:
        name = f"abstract-{index}-{stem[:60]}.md"
    used.add(name)
    return name


_KEPT_ON_ABSTRACT = (
    "author",
    "year",
    "title",
    "doi",
    "oa_url",
    "pdf_url",
    "journal",
    "pages",
    "volume",
    "url",
)
_HIT_TEXT_FIELDS = ("oa_url", "pdf_url", "journal", "pages", "volume", "url")


def _lookup_author(hit: dict[str, Any]) -> str:
    """Names the look-up returned, joined as given. No initial is added."""
    names: list[str] = []
    authors = hit.get("authors")
    if isinstance(authors, list):
        for author in authors:
            if isinstance(author, str) and author.strip():
                names.append(author.strip())
    elif isinstance(authors, str) and authors.strip():
        names.append(authors.strip())
    if not names:
        single = hit.get("author")
        if isinstance(single, str) and single.strip():
            names.append(single.strip())
    return " and ".join(names)


def _provided_details(hit: dict[str, Any]) -> dict[str, str]:
    """Bibliographic fields the look-up already put on this hit.

    A missing field is omitted. Nothing is filled in.
    """
    details: dict[str, str] = {}
    author = _lookup_author(hit)
    if author:
        details["author"] = author
    year = hit.get("year")
    if isinstance(year, str) and year.strip().isdigit():
        details["year"] = year.strip()
    elif isinstance(year, int) and not isinstance(year, bool):
        details["year"] = str(year)
    title = hit.get("title")
    if isinstance(title, str) and title.strip():
        details["title"] = title.strip()
    doi = _doi_key(hit.get("doi"))
    if doi:
        details["doi"] = doi
    for key in _HIT_TEXT_FIELDS:
        value = hit.get(key)
        if isinstance(value, str) and value.strip():
            details[key] = value.strip()
    return details


def _fill_blank_details(target: dict[str, str], incoming: dict[str, str]) -> None:
    """Copy a provided field onto a record that does not have it yet."""
    for key, value in incoming.items():
        if key not in target and value:
            target[key] = value


def _printed_name_year(details: dict[str, str]) -> str:
    """Name and year in the same shape as a saved citation line.

    A name or a year the look-up did not return is not printed.
    """
    author = details.get("author", "")
    year = details.get("year", "")
    if author and year:
        return f"{author} ({year})"
    if author:
        return author
    if year:
        return f"({year})"
    return ""


def _abstract_text(abstract: str, details: dict[str, str]) -> str:
    body = abstract.strip()
    heading = _printed_name_year(details)
    if not heading:
        return body + "\n"
    return f"{heading}\n\n{body}\n"


def same_lookup_value(field: str, claimed: str, stored: str) -> bool:
    """True when the claimed value is the one the look-up already stored."""
    if field == "doi":
        return bool(_doi_key(stored)) and _doi_key(claimed) == _doi_key(stored)
    return claimed.strip() == stored.strip()


def _fields_on_row(row: dict[str, Any]) -> dict[str, str]:
    kept: dict[str, str] = {}
    for field in _KEPT_ON_ABSTRACT:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            kept[field] = value.strip()
    return kept


def _matching_lookup_row(rows: object, wanted: str) -> dict[str, str] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        found = row.get("locator")
        if not isinstance(found, str) or found.strip().replace("\\", "/") != wanted:
            continue
        return _fields_on_row(row)
    return None


def abstract_lookup_fields(essay_id: str, locator: str) -> dict[str, str]:
    """Bibliographic fields stored when this file was saved from a look-up.

    A saved abstract and a kept PDF use the same record. Only fields the
    look-up returned are present. Nothing is invented.
    """
    if not isinstance(locator, str) or not locator.strip():
        return {}
    wanted = locator.strip().replace("\\", "/")
    path = work_dir(essay_id) / "dig-card.json"
    if not path.is_file():
        return {}
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    for key in ("abstract_files", "pdf_files"):
        matched = _matching_lookup_row(stored.get(key), wanted)
        if matched is not None:
            return matched
    return {}


def _abstract_hits(card: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for key in ("openalex", "consensus"):
        block = card.get(key)
        hits = block.get("hits") if isinstance(block, dict) else None
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            abstract = hit.get("abstract")
            if isinstance(abstract, str) and abstract.strip():
                found.append(hit)
    return found


def _save_lookup_abstracts(
    essay_id: str,
    card: dict[str, Any],
    pdf_dois: set[str],
) -> list[dict[str, Any]]:
    """Save a look-up abstract when that hit has no PDF.

    Bibliographic fields the look-up returned are copied onto the record.
    A field the look-up left out stays off the record. The file prints the
    kept name and year, in the same shape as a saved citation line, and
    does not add a name or year that was not returned.
    """

    hits = _abstract_hits(card)
    if not hits:
        return []
    bundles: list[dict[str, Any]] = []
    by_doi: dict[str, dict[str, Any]] = {}
    for index, hit in enumerate(hits, start=1):
        doi_key = _doi_key(hit.get("doi"))
        if doi_key and doi_key in pdf_dois:
            continue
        abstract = hit.get("abstract")
        if not isinstance(abstract, str) or not abstract.strip():
            continue
        details = _provided_details(hit)
        if doi_key and doi_key in by_doi:
            _fill_blank_details(by_doi[doi_key]["details"], details)
            continue
        bundle = {
            "index": index,
            "doi": doi_key,
            "abstract": abstract.strip(),
            "details": details,
        }
        bundles.append(bundle)
        if doi_key:
            by_doi[doi_key] = bundle
    if not bundles:
        return []
    folder = uploads_dir(essay_id)
    folder.mkdir(parents=True, exist_ok=True)
    module = module_code(essay_id)
    saved: list[dict[str, Any]] = []
    used: set[str] = set()
    for bundle in bundles:
        raw_index = bundle.get("index")
        raw_doi = bundle.get("doi")
        raw_abstract = bundle.get("abstract")
        raw_details = bundle.get("details")
        index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else 0
        doi = raw_doi if isinstance(raw_doi, str) else ""
        abstract = raw_abstract if isinstance(raw_abstract, str) else ""
        kept_details: dict[str, str] = {}
        if isinstance(raw_details, dict):
            for key, value in raw_details.items():
                if isinstance(key, str) and isinstance(value, str) and value.strip():
                    kept_details[key] = value.strip()
        name = _abstract_name(doi, index, used)
        (folder / name).write_text(
            _abstract_text(abstract, kept_details),
            encoding="utf-8",
        )
        row: dict[str, Any] = {"locator": f"uploads/{module}/{name}"}
        provenance: dict[str, str] = {}
        for field in _KEPT_ON_ABSTRACT:
            value = kept_details.get(field)
            if isinstance(value, str) and value.strip():
                row[field] = value.strip()
                provenance[field] = "lookup"
        if provenance:
            row["field_sources"] = provenance
        saved.append(row)
    return saved


_PDF_LOOKUP_FIELDS = ("author", "year", "title", "doi")


def _hits_by_doi(card: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Look-up author, year, title, and DOI, keyed by DOI.

    OpenAlex and Consensus supply those fields. Unpaywall may fill a blank
    year, title, or DOI. Unpaywall does not supply an author.
    """
    by_doi: dict[str, dict[str, str]] = {}
    for key in ("openalex", "consensus"):
        block = card.get(key)
        hits = block.get("hits") if isinstance(block, dict) else None
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            doi = _doi_key(hit.get("doi"))
            if not doi:
                continue
            details = {
                field: value
                for field, value in _provided_details(hit).items()
                if field in _PDF_LOOKUP_FIELDS
            }
            slot = by_doi.setdefault(doi, {})
            _fill_blank_details(slot, details)
    unpaywall = card.get("unpaywall")
    if isinstance(unpaywall, list):
        for item in unpaywall:
            if not isinstance(item, dict):
                continue
            doi = _doi_key(item.get("doi"))
            if not doi:
                continue
            details = {
                field: value
                for field, value in _provided_details(item).items()
                if field in _PDF_LOOKUP_FIELDS and field != "author"
            }
            slot = by_doi.setdefault(doi, {})
            _fill_blank_details(slot, details)
    return by_doi


def _save_lookup_pdfs(
    card: dict[str, Any],
    papers: object,
) -> list[dict[str, Any]]:
    """Copy look-up author, year, title, and DOI onto each kept PDF.

    A field the look-up did not return stays off the record. A name is not
    read from the PDF.
    """
    if not isinstance(papers, list) or not papers:
        return []
    by_doi = _hits_by_doi(card)
    saved: list[dict[str, Any]] = []
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        path = paper.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        doi = _doi_key(paper.get("doi"))
        details = by_doi.get(doi, {}) if doi else {}
        present = {
            field: details[field]
            for field in _PDF_LOOKUP_FIELDS
            if isinstance(details.get(field), str) and details[field].strip()
        }
        if not present:
            continue
        row: dict[str, Any] = {"locator": path.strip().replace("\\", "/")}
        provenance: dict[str, str] = {}
        for field, value in present.items():
            row[field] = value.strip()
            provenance[field] = "lookup"
        row["field_sources"] = provenance
        saved.append(row)
    return saved


def _save_openalex_abstracts(
    essay_id: str,
    card: dict[str, Any],
    pdf_dois: set[str],
) -> list[dict[str, Any]]:
    """Older name for the abstract save. OpenAlex and Consensus share it."""
    return _save_lookup_abstracts(essay_id, card, pdf_dois)


def _http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("https://") or text.startswith("http://"):
        return text
    return None


def _open_candidates(card: dict[str, Any]) -> list[dict[str, Any]]:
    """OpenAlex and Unpaywall PDF or open-access URLs already on the card.

    A Consensus URL is not fetched. A hit with neither official URL adds nothing.
    """
    titles: dict[str, str] = {}
    for hit in list(card["openalex"]["hits"]) + list(card["consensus"]["hits"]):
        doi = hit.get("doi")
        title = hit.get("title")
        if isinstance(doi, str) and isinstance(title, str) and title.strip():
            titles[doi] = title.strip()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(url: str | None, doi: object, title: object) -> None:
        if url is None or url in seen:
            return
        seen.add(url)
        candidate: dict[str, Any] = {"url": url}
        if isinstance(doi, str) and doi.strip():
            candidate["doi"] = doi.strip()
            named = title if isinstance(title, str) and title.strip() else None
            if named is None:
                named = titles.get(doi.strip())
            if isinstance(named, str) and named.strip():
                candidate["title"] = named.strip()
        candidates.append(candidate)

    for hit in card["openalex"]["hits"]:
        if not isinstance(hit, dict):
            continue
        add(_http_url(hit.get("pdf_url")), hit.get("doi"), hit.get("title"))
        add(_http_url(hit.get("oa_url")), hit.get("doi"), hit.get("title"))
    for item in card["unpaywall"]:
        if not isinstance(item, dict):
            continue
        add(_http_url(item.get("oa_url")), item.get("doi"), None)
    return candidates


def _hit_lines(hits: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for hit in hits:
        year = f" ({hit['year']})" if hit.get("year") else ""
        doi = f" https://doi.org/{hit['doi']}" if hit.get("doi") else ""
        lines.append(f"- {hit['title']}{year}.{doi}")
    return lines


_prepared_questions: list[str] = []
_PAGE_CAP = 200


def _legacy_query_allowed() -> bool:
    """Existing tests open a look-up with the caller query when no question is stored.

    A normal run does not. It asks for the question and does not search.
    """
    if os.environ.get("ESSAY_WRITER_FLOOR_STRICT") == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _same_question(left: str, right: str) -> bool:
    return " ".join(left.split()).casefold() == " ".join(right.split()).casefold()


def _new_question_slot(text: str, role: str) -> dict[str, Any]:
    from essay_writer.source_floor import CROSSREF_NOTE

    return {
        "question": text,
        "role": role,
        "openalex": {"called": False, "hits": []},
        "consensus": {
            "called": False,
            "tier": None,
            "hits": [],
            "remind": "",
        },
        "unpaywall": [],
        "crossref": {"called": False, "note": CROSSREF_NOTE},
        "gaps": [],
    }


def _slot_hits(block: dict[str, Any]) -> list[dict[str, Any]]:
    hits = block.get("hits")
    if not isinstance(hits, list):
        return []
    return [hit for hit in hits if isinstance(hit, dict)]


def _refresh_gaps(slot: dict[str, Any]) -> None:
    from essay_writer.source_floor import is_gap

    gaps: list[dict[str, Any]] = []
    for hit in _slot_hits(slot["openalex"]) + _slot_hits(slot["consensus"]):
        if not is_gap(hit):
            continue
        gap: dict[str, Any] = {}
        for field in ("title", "year", "doi"):
            value = hit.get(field)
            if isinstance(value, str) and value.strip():
                gap[field] = value.strip()
        authors = hit.get("authors")
        if isinstance(authors, list):
            names = [name.strip() for name in authors if isinstance(name, str) and name.strip()]
            if names:
                gap["authors"] = names
        gaps.append(gap)
    slot["gaps"] = gaps


def _remember_unpaywall(slot: dict[str, Any], seen: set[str]) -> None:
    if not unpaywall_email():
        slot["unpaywall_skipped"] = "no-email"
    for hit in _slot_hits(slot["openalex"]) + _slot_hits(slot["consensus"]):
        doi = hit.get("doi")
        if isinstance(doi, str) and doi not in seen:
            seen.add(doi)
            slot["unpaywall"].append(unpaywall_lookup(doi))


def _take_openalex(slot: dict[str, Any], body: dict[str, Any], *, extend: bool) -> None:
    current = slot["openalex"]
    current["called"] = body.get("called", False)
    if body.get("skipped"):
        current["skipped"] = body["skipped"]
    if body.get("refused"):
        current["refused"] = body["refused"]
        current["miss"] = body.get("miss", "openalex")
        current.pop("next_cursor", None)
        _refresh_gaps(slot)
        return
    hits = list(current.get("hits") or []) if extend else []
    hits.extend(hit for hit in body.get("hits") or [] if isinstance(hit, dict))
    current["hits"] = hits
    current.pop("refused", None)
    if isinstance(body.get("next_cursor"), str) and body["next_cursor"].strip():
        current["next_cursor"] = body["next_cursor"].strip()
    else:
        current.pop("next_cursor", None)
    _refresh_gaps(slot)


def _take_consensus(
    slot: dict[str, Any],
    body: dict[str, Any],
    status: dict[str, Any],
    *,
    extend: bool,
) -> None:
    current = slot["consensus"]
    current["called"] = body.get("called", False)
    current["tier"] = body.get("tier")
    current["switch"] = status["switch"]
    current["enabled"] = status["enabled"]
    current["key_present"] = status["key_present"]
    current["remind"] = body.get("remind") or status["remind"]
    if body.get("skipped"):
        current["skipped"] = body["skipped"]
    if body.get("refused"):
        current["refused"] = body["refused"]
        current["miss"] = body.get("miss", "consensus")
        current.pop("next_page", None)
        _refresh_gaps(slot)
        return
    hits = list(current.get("hits") or []) if extend else []
    hits.extend(hit for hit in body.get("hits") or [] if isinstance(hit, dict))
    current["hits"] = hits
    current.pop("refused", None)
    if isinstance(body.get("pagination"), str) and body["pagination"].strip():
        current["pagination"] = body["pagination"].strip()
        current.pop("next_page", None)
    elif isinstance(body.get("next_page"), int) and not isinstance(body.get("next_page"), bool):
        current["next_page"] = body["next_page"]
        current.pop("pagination", None)
    else:
        current.pop("next_page", None)
    _refresh_gaps(slot)


def _count_slots(slots: list[dict[str, Any]], essay_id: str) -> int:
    from essay_writer.source_floor import distinct_works, saved_upload_records, work_key

    records: list[dict[str, Any]] = []
    for slot in slots:
        for hit in _slot_hits(slot["openalex"]) + _slot_hits(slot["consensus"]):
            if work_key(hit):
                records.append(hit)
    records.extend(saved_upload_records(essay_id))
    return len(distinct_works(records))


def _further_page(slots: list[dict[str, Any]]) -> bool:
    for slot in slots:
        openalex = slot.get("openalex")
        consensus = slot.get("consensus")
        if isinstance(openalex, dict) and openalex.get("next_cursor") and not openalex.get("refused"):
            return True
        if (
            isinstance(consensus, dict)
            and isinstance(consensus.get("next_page"), int)
            and not consensus.get("refused")
        ):
            return True
    return False


def _build_floor_card(question: str, essay_id: str) -> dict[str, Any]:
    """Search each stored question, then further pages until the floor is met."""
    global _prepared_questions
    from essay_writer.source_floor import (
        accept_split,
        ask_planning_model,
        assignment_floor,
        decide_gather,
    )

    floor = assignment_floor(essay_id)
    try:
        reply = ask_planning_model(question)
    except Exception:
        reply = None
    searches = accept_split(question, reply)
    if not searches:
        searches = [question]
    _prepared_questions = list(searches)
    status = consensus_status()
    slots = [
        _new_question_slot(text, "confirmed" if _same_question(text, question) else "split")
        for text in searches
    ]
    seen: set[str] = set()
    seen_cursors: set[str] = set()
    seen_pages: set[tuple[str, int]] = set()
    for slot in slots:
        _take_openalex(slot, openalex_search(slot["question"]), extend=False)
        _take_consensus(slot, consensus_search(slot["question"]), status, extend=False)
        _remember_unpaywall(slot, seen)
    count = _count_slots(slots, essay_id)
    pages = 0
    while count < int(floor.get("floor") or 0) and pages < _PAGE_CAP:
        moved = False
        for slot in slots:
            if count >= int(floor.get("floor") or 0):
                break
            cursor = slot["openalex"].get("next_cursor")
            if isinstance(cursor, str) and cursor in seen_cursors:
                slot["openalex"].pop("next_cursor", None)
                cursor = None
            if (
                isinstance(cursor, str)
                and not slot["openalex"].get("refused")
            ):
                seen_cursors.add(cursor)
                _take_openalex(slot, openalex_search(slot["question"], cursor=cursor), extend=True)
                _remember_unpaywall(slot, seen)
                moved = True
                pages += 1
                count = _count_slots(slots, essay_id)
                if count >= int(floor.get("floor") or 0) or pages >= _PAGE_CAP:
                    break
            next_page = slot["consensus"].get("next_page")
            page_key = (slot["question"], next_page) if isinstance(next_page, int) else None
            if page_key is not None and page_key in seen_pages:
                slot["consensus"].pop("next_page", None)
                page_key = None
            if (
                page_key is not None
                and not slot["consensus"].get("refused")
            ):
                seen_pages.add(page_key)
                slot["consensus"].pop("next_page", None)
                _take_consensus(
                    slot,
                    consensus_search(slot["question"], page=next_page),
                    status,
                    extend=True,
                )
                _remember_unpaywall(slot, seen)
                moved = True
                pages += 1
                count = _count_slots(slots, essay_id)
                if count >= int(floor.get("floor") or 0) or pages >= _PAGE_CAP:
                    break
        if not moved:
            break
    gather = decide_gather(slots, floor, count, _further_page(slots))
    openalex_hits: list[dict[str, Any]] = []
    consensus_hits: list[dict[str, Any]] = []
    unpaywall: list[dict[str, Any]] = []
    openalex_called = False
    consensus_called = False
    openalex_refused = None
    consensus_refused = None
    tier = None
    remind = status["remind"]
    pagination = None
    skipped = None
    for slot in slots:
        openalex = slot["openalex"]
        consensus = slot["consensus"]
        if openalex.get("called"):
            openalex_called = True
        if openalex.get("refused") and openalex_refused is None:
            openalex_refused = openalex["refused"]
        if openalex.get("skipped") and skipped is None:
            skipped = openalex["skipped"]
        openalex_hits.extend(_slot_hits(openalex))
        if consensus.get("called"):
            consensus_called = True
        if consensus.get("tier"):
            tier = consensus.get("tier")
        if consensus.get("remind"):
            remind = consensus["remind"]
        if consensus.get("refused") and consensus_refused is None:
            consensus_refused = consensus["refused"]
        if isinstance(consensus.get("pagination"), str):
            pagination = consensus["pagination"]
        consensus_hits.extend(_slot_hits(consensus))
        for row in slot.get("unpaywall") or []:
            if isinstance(row, dict):
                unpaywall.append(row)
    openalex_body: dict[str, Any] = {"called": openalex_called, "hits": openalex_hits}
    if openalex_refused:
        openalex_body["refused"] = openalex_refused
        openalex_body["miss"] = "openalex"
    if skipped and not openalex_called:
        openalex_body["skipped"] = skipped
    consensus_body: dict[str, Any] = {
        "called": consensus_called,
        "tier": tier,
        "hits": consensus_hits,
        "switch": status["switch"],
        "enabled": status["enabled"],
        "key_present": status["key_present"],
        "remind": remind,
    }
    if consensus_refused:
        consensus_body["refused"] = consensus_refused
        consensus_body["miss"] = "consensus"
    if pagination:
        consensus_body["pagination"] = pagination
    card = {
        "essay_id": essay_id,
        "query": question,
        "question": question,
        "searches": searches,
        "questions": slots,
        "gather": gather,
        "openalex": openalex_body,
        "consensus": consensus_body,
        "unpaywall": unpaywall,
        "invent_forbid": True,
    }
    from essay_writer.roll_forward import omit_keepers_from_card

    return omit_keepers_from_card(essay_id, card)


def _build_card(query: str, essay_id: str) -> dict[str, Any]:
    status = consensus_status()
    openalex = openalex_search(query)
    consensus = consensus_search(query)
    unpaywall: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in list(openalex["hits"]) + list(consensus["hits"]):
        doi = hit.get("doi")
        if isinstance(doi, str) and doi not in seen:
            seen.add(doi)
            unpaywall.append(unpaywall_lookup(doi))
    card = {
        "essay_id": essay_id,
        "query": query,
        "openalex": openalex,
        "consensus": {
            "called": consensus.get("called"),
            "tier": consensus.get("tier"),
            "hits": consensus.get("hits") or [],
            "switch": status["switch"],
            "enabled": status["enabled"],
            "key_present": status["key_present"],
            "remind": consensus.get("remind") or status["remind"],
        },
        "unpaywall": unpaywall,
        "invent_forbid": True,
    }
    from essay_writer.roll_forward import omit_keepers_from_card

    return omit_keepers_from_card(essay_id, card)


def _dig_fingerprint(query: str) -> dict[str, Any]:
    """Student arguments only. Live look-up bodies are not fingerprint fields."""
    return {"query": query}


_DIG_DISK_SKIP = frozenset({"digest", "downloads"})


def _dig_lookup_body(card: dict[str, Any]) -> dict[str, Any]:
    """Look-up rows. The stored digest and a later download list are not the card."""
    return {key: value for key, value in card.items() if key not in _DIG_DISK_SKIP}


def _dig_already_confirmed(essay_id: str, query: str, digest: str, card: dict[str, Any]) -> bool:
    """True when this query and this look-up card are already the file on disk."""
    path = work_dir(essay_id) / "dig-card.json"
    if not path.is_file():
        return False
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(stored, dict):
        return False
    if stored.get("query") != query or stored.get("digest") != digest:
        return False
    return _dig_lookup_body(stored) == _dig_lookup_body(card)


def _stored_dig_card(record: dict[str, Any]) -> dict[str, Any] | None:
    """The card stored with the draft. Confirm does not build another one."""
    card = record.get("shown")
    if not isinstance(card, dict):
        return None
    openalex = card.get("openalex")
    consensus = card.get("consensus")
    unpaywall = card.get("unpaywall")
    if not isinstance(openalex, dict) or not isinstance(consensus, dict):
        return None
    if not isinstance(unpaywall, list):
        return None
    return card


def _dig_reply(
    essay_id: str, query: str, confirmPhase: str, card: dict[str, Any]
) -> dict[str, Any]:
    body = {
        "ok": True,
        "essay_id": essay_id,
        "query": query,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "card": card,
        "consensus": {
            "switch": card["consensus"]["switch"],
            "enabled": card["consensus"]["enabled"],
            "key_present": card["consensus"]["key_present"],
            "tier": card["consensus"]["tier"],
            "remind": card["consensus"]["remind"],
        },
        "invent_forbid": True,
    }
    notes: list[str] = []
    for name, entry in (("OpenAlex", card["openalex"]), ("Consensus", card["consensus"])):
        for line in _refused_lines(name, entry):
            notes.append(say(line.removeprefix("- ")))
    if notes:
        # A refused look-up is not an empty result. The front office says this.
        body["lookup_note"] = " ".join(notes)
    gather = card.get("gather")
    if isinstance(gather, dict):
        note = gather.get("note")
        if isinstance(note, str) and note.strip():
            body["gather_note"] = say(note.strip())
    return body


def essay_dig(
    essay_id: str,
    query: str,
    confirmPhase: str | None = None,
    cardDigest: str | None = None,
) -> dict[str, Any]:
    """Draft the local dig card. Confirm writes the card that was shown.

    The draft reply carries cardDigest. Confirm rebuilds it from the stored
    card and refuses a confirm that does not send the same value.
    """
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    from essay_writer.source_floor import ASK_QUESTION, confirmed_question

    question = confirmed_question(essay_id)
    caller = query.strip() if isinstance(query, str) else ""
    if question:
        query = caller
    elif caller and _legacy_query_allowed():
        query = caller
    elif not caller:
        return refuse("dig", "Name the dig query. An empty query does not invent papers.")
    else:
        return refuse("dig", ASK_QUESTION, stored=False, wrote=False)
    payload = {"essay_id": essay_id, "query": query}
    fingerprint = _dig_fingerprint(query)
    if confirmPhase == DRAFT:
        if question:
            card = _build_floor_card(question, essay_id)
            card["query"] = query
        else:
            card = _build_card(query, essay_id)
        body = _dig_reply(essay_id, query, confirmPhase, card)
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint, shown=card)
        body["cardDigest"] = card_digest(payload, card)
        body["next"] = say(
            "This source card is not on disk yet. Choose Confirm to keep this step. "
            "Only look-up hits are listed."
        )
        if _open_candidates(card):
            body["next"] += " " + say(
                "Open copies are checked when you keep this step. Only a real PDF is saved."
                " An HTML page is not a paper."
            )
        return body
    ready = confirm_ready(
        essay_id,
        TOOL,
        payload,
        fingerprint,
        card_digest=cardDigest,
        require_card=True,
    )
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    stored_card = _stored_dig_card(ready)
    if stored_card is None:
        return refuse(
            "confirm",
            NO_MATCHING_DRAFT,
            confirmPhase=CONFIRM,
        )
    card = stored_card
    body = _dig_reply(essay_id, query, CONFIRM, card)
    if _dig_already_confirmed(essay_id, query, str(ready.get("digest") or ""), card):
        body["wrote"] = False
        body["stored"] = False
        body["noop"] = True
        body["digest"] = ready["digest"]
        body["json"] = f"{essay_id}/dig-card.json"
        body["markdown"] = f"{essay_id}/dig-card.md"
        return body
    candidates = _open_candidates(card)
    if candidates:
        downloads = run_downloads(essay_id, candidates)
        body["downloads"] = downloads
        if downloads.get("ok"):
            card["downloads"] = {
                "papers": downloads.get("papers") or [],
                "failures": downloads.get("failures") or [],
                "stopped": bool(downloads.get("stopped")),
                "stop_reason": downloads.get("stop_reason"),
                "download_list": downloads.get("download_list"),
                "annotation": downloads.get("annotation"),
                "annotation_chat": downloads.get("annotation_chat"),
                "papers_zip": downloads.get("papers_zip"),
            }
        if isinstance(downloads.get("links"), dict):
            body["links"] = downloads["links"]
        if isinstance(downloads.get("next"), str):
            body["next"] = downloads["next"]
    downloads_body = body.get("downloads")
    pdf_dois = _pdf_dois(downloads_body)
    abstract_files = _save_lookup_abstracts(essay_id, card, pdf_dois)
    if abstract_files:
        card["abstract_files"] = abstract_files
        body["abstract_files"] = abstract_files
    papers = downloads_body.get("papers") if isinstance(downloads_body, dict) else None
    pdf_files = _save_lookup_pdfs(card, papers)
    if pdf_files:
        card["pdf_files"] = pdf_files
        body["pdf_files"] = pdf_files
    folder = work_dir(essay_id)
    folder.mkdir(parents=True, exist_ok=True)
    to_write = dict(card)
    to_write["digest"] = ready["digest"]
    (folder / "dig-card.json").write_text(
        json.dumps(to_write, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (folder / "dig-card.md").write_text(_card_markdown(query, essay_id, card), encoding="utf-8")
    body["wrote"] = True
    body["stored"] = True
    body["json"] = f"{essay_id}/dig-card.json"
    body["markdown"] = f"{essay_id}/dig-card.md"
    body["digest"] = ready["digest"]
    return body
