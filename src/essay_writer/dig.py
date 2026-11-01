"""Local dig card. OpenAlex needs no key. Consensus runs only when allowed.

Draft writes nothing. It stores the card that was shown, including Unpaywall
rows. Confirm writes that stored card to dig-card.json and dig-card.md.
It does not call Unpaywall, OpenAlex, or Consensus again to decide whether
confirm is allowed. Downloads use the open-access URLs already on that card.
Look-up hits are copied from the response. Missing papers are omitted.
invent-forbid holds. The same handler serves every writing type.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.downloads import BUCKET_LABELS, run_downloads
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import module_code, sequence_write_error, uploads_dir, work_dir
from essay_writer.resolvers import resolver_mode, unpaywall_doi_url, unpaywall_email
from essay_writer.setup import read_setup_secret

TOOL = "essay.dig"
OPENALEX_URL = "https://api.openalex.org/works"
CONSENSUS_URL = "https://api.consensus.app/v1/search"
UNPAYWALL_URL = "https://api.unpaywall.org/v2/"


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


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
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


def _hit(title: object, year: object, doi: object, authors: object, source: str) -> dict[str, Any] | None:
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


def openalex_search(query: str) -> dict[str, Any]:
    if resolver_mode() == "off":
        return {"called": False, "skipped": "resolvers-off", "hits": []}
    url = OPENALEX_URL + "?" + urllib.parse.urlencode({"search": query, "per-page": 5})
    payload = _get_json(url, {"User-Agent": "essay-writer"})
    if payload is None:
        return {"called": True, "hits": [], "miss": "openalex"}
    hits: list[dict[str, Any]] = []
    for work in payload.get("results") or []:
        if not isinstance(work, dict):
            continue
        authorships = work.get("authorships") or []
        authors = []
        if isinstance(authorships, list):
            for item in authorships:
                if isinstance(item, dict):
                    authors.append(item.get("author") or {})
        hit = _hit(work.get("title"), work.get("publication_year"), work.get("doi"), authors, "openalex")
        if hit:
            abstract = _abstract_from_index(work.get("abstract_inverted_index"))
            if abstract:
                hit["abstract"] = abstract
            hits.append(hit)
    return {"called": True, "hits": hits}


def consensus_search(query: str) -> dict[str, Any]:
    status = consensus_status()
    if not status["enabled"]:
        return {"called": False, "tier": None, "hits": [], "remind": status["remind"]}
    if resolver_mode() == "off":
        return {"called": False, "tier": None, "hits": [], "skipped": "resolvers-off"}
    key = consensus_api_key()
    if not key:
        return {"called": False, "tier": None, "hits": [], "remind": status["remind"]}
    url = CONSENSUS_URL + "?" + urllib.parse.urlencode({"query": query})
    payload = _get_json(url, {"x-api-key": key, "User-Agent": "essay-writer"})
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
            hits.append(hit)
    return {"called": True, "tier": tier, "hits": hits}


def unpaywall_lookup(doi: str) -> dict[str, Any]:
    email = unpaywall_email()
    if not email:
        return {"called": False, "skipped": "no-email", "doi": doi}
    if resolver_mode() == "off":
        return {"called": False, "skipped": "resolvers-off", "doi": doi}
    url = unpaywall_doi_url(doi, email)
    payload = _get_json(url, {"User-Agent": "essay-writer"})
    if payload is None:
        return {"called": True, "doi": doi, "oa_url": None, "miss": "unpaywall"}
    location = payload.get("best_oa_location")
    oa_url = None
    if isinstance(location, dict):
        candidate = location.get("url_for_pdf") or location.get("url")
        if isinstance(candidate, str) and candidate.strip():
            oa_url = candidate.strip()
    return {"called": True, "doi": doi, "oa_url": oa_url}


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
    lines.extend(_hit_lines(card["openalex"]["hits"]) or ["- No OpenAlex hits. None were invented."])
    lines.extend(["", "## Consensus"])
    tier = card["consensus"].get("tier")
    if card["consensus"].get("called"):
        lines.append(f"Tier: {tier or 'unspecified'}")
    else:
        lines.append("Consensus was not called.")
    lines.extend(_hit_lines(card["consensus"]["hits"]) or ["- No Consensus hits. None were invented."])
    lines.extend(["", "## Unpaywall"])
    if not card["unpaywall"]:
        lines.append("- Skipped. An email is optional, and none is stored.")
    else:
        for item in card["unpaywall"]:
            if item.get("skipped") == "no-email":
                lines.append(f"- {item['doi']}: skipped, no email.")
            elif item.get("oa_url"):
                lines.append(f"- {item['doi']}: {item['oa_url']}")
            else:
                lines.append(f"- {item['doi']}: no open copy returned.")
    lines.extend(_download_lines(card))
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


def _save_openalex_abstracts(
    essay_id: str,
    card: dict[str, Any],
    pdf_dois: set[str],
) -> list[dict[str, str]]:
    """Save an OpenAlex abstract when that hit has no PDF. The file is the abstract only."""

    openalex = card.get("openalex")
    hits = openalex.get("hits") if isinstance(openalex, dict) else None
    if not isinstance(hits, list):
        return []
    folder = uploads_dir(essay_id)
    module = module_code(essay_id)
    saved: list[dict[str, str]] = []
    used: set[str] = set()
    for index, hit in enumerate(hits, start=1):
        if not isinstance(hit, dict):
            continue
        abstract = hit.get("abstract")
        if not isinstance(abstract, str) or not abstract.strip():
            continue
        doi_key = _doi_key(hit.get("doi"))
        if doi_key and doi_key in pdf_dois:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        name = _abstract_name(doi_key, index, used)
        (folder / name).write_text(abstract.strip() + "\n", encoding="utf-8")
        row: dict[str, str] = {"locator": f"uploads/{module}/{name}"}
        if doi_key:
            row["doi"] = doi_key
        title = hit.get("title")
        if isinstance(title, str) and title.strip():
            row["title"] = title.strip()
        saved.append(row)
    return saved


def _open_candidates(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Unpaywall addresses only. A look-up hit is not a downloaded paper."""
    titles: dict[str, str] = {}
    for hit in list(card["openalex"]["hits"]) + list(card["consensus"]["hits"]):
        doi = hit.get("doi")
        title = hit.get("title")
        if isinstance(doi, str) and isinstance(title, str) and title.strip():
            titles[doi] = title.strip()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in card["unpaywall"]:
        url = item.get("oa_url")
        if not isinstance(url, str) or not url.strip():
            continue
        url = url.strip()
        if url in seen:
            continue
        seen.add(url)
        candidate: dict[str, Any] = {"url": url}
        doi = item.get("doi")
        if isinstance(doi, str) and doi.strip():
            candidate["doi"] = doi.strip()
            if doi.strip() in titles:
                candidate["title"] = titles[doi.strip()]
        candidates.append(candidate)
    return candidates


def _hit_lines(hits: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for hit in hits:
        year = f" ({hit['year']})" if hit.get("year") else ""
        doi = f" https://doi.org/{hit['doi']}" if hit.get("doi") else ""
        lines.append(f"- {hit['title']}{year}.{doi}")
    return lines


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


def _dig_reply(essay_id: str, query: str, confirmPhase: str, card: dict[str, Any]) -> dict[str, Any]:
    return {
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


def essay_dig(essay_id: str, query: str, confirmPhase: str | None = None) -> dict[str, Any]:
    """Draft the local dig card. Confirm writes the card that was shown."""
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if not isinstance(query, str) or not query.strip():
        return refuse("dig", "Name the dig query. An empty query does not invent papers.")
    query = query.strip()
    payload = {"essay_id": essay_id, "query": query}
    fingerprint = _dig_fingerprint(query)
    if confirmPhase == DRAFT:
        card = _build_card(query, essay_id)
        body = _dig_reply(essay_id, query, confirmPhase, card)
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint, shown=card)
        body["next"] = (
            "This source card is not on disk yet. Say yes to write dig-card.json and dig-card.md. "
            "Only look-up hits are listed."
        )
        if _open_candidates(card):
            body["next"] += (
                " Open copies are checked when you say yes. Only a real PDF is saved."
                " An HTML page is not a paper."
            )
        return body
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    stored_card = _stored_dig_card(ready)
    if stored_card is None:
        return refuse(
            "confirm",
            "No matching draft is waiting. Show this step in the chat again before it can be saved. "
            "If the draft, the topic, or the source list changed, show it again.",
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
    pdf_dois = _pdf_dois(body.get("downloads"))
    abstract_files = _save_openalex_abstracts(essay_id, card, pdf_dois)
    if abstract_files:
        card["abstract_files"] = abstract_files
        body["abstract_files"] = abstract_files
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
