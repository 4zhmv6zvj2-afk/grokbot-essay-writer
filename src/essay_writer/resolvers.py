"""Free public look-ups for gathered sources only. invent-forbid on misses."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from essay_writer.cite_open import page_value_kind
from essay_writer.programme import FREE_RESOLVERS, PAID_RESOLVERS

RESOLVER_FILLABLE = (
    "doi",
    "container",
    "volume",
    "issue",
    "pages",
    "article_number",
    "publisher",
    "place",
    "url",
    "accessed",
)

LookupRecord = dict[str, str]
ResolverCall = dict[str, str]
EnrichResult = tuple[list[dict[str, Any]], list[ResolverCall], dict[str, Any]]

# Saved Crossref-style sample for tests (no live network).
FIXTURE_TITLE = "Maritime chokepoints and energy security"
FIXTURE_SAMPLE: LookupRecord = {
    "doi": "10.5555/fixture-chokepoint",
    "container": "Journal of Transport Geography",
    "volume": "42",
    "issue": "3",
    "pages": "101-112",
    "publisher": "Elsevier",
    "place": "London",
    "url": "https://doi.org/10.5555/fixture-chokepoint",
}

OPPOSING_MARKERS = (
    "opposing view",
    "counterargument",
    "counter-argument",
    "critics argue",
    "on the other hand",
)


def resolver_mode() -> str:
    return os.environ.get("ESSAY_WRITER_RESOLVERS", "live").strip().casefold() or "live"


def unpaywall_email() -> str | None:
    raw = os.environ.get("ESSAY_WRITER_UNPAYWALL_EMAIL", "").strip()
    if raw:
        return raw
    from essay_writer.setup import read_setup_secret

    return read_setup_secret("ESSAY_WRITER_UNPAYWALL_EMAIL")


def _paid_name(text: str) -> str | None:
    lowered = text.casefold()
    for name in PAID_RESOLVERS:
        if name in lowered:
            return name
    return None


def refuse_paid_resolver(name: object) -> str | None:
    if not isinstance(name, str) or not name.strip():
        return None
    return _paid_name(name)


def _normalize_title(title: str) -> str:
    collapsed = re.sub(r"\s+", " ", title.strip().casefold())
    return collapsed


def _title_matches(gathered_title: str, record_title: str) -> bool:
    return _normalize_title(gathered_title) == _normalize_title(record_title)


def _doi_in_text(doi: str, text: str) -> bool:
    needle = doi.strip().casefold()
    return needle in text.casefold()


def _record_from_crossref_message(message: dict[str, Any]) -> LookupRecord:
    record: LookupRecord = {}
    doi = message.get("DOI")
    if isinstance(doi, str) and doi.strip():
        record["doi"] = doi.strip()
    for key, field in (
        ("container-title", "container"),
        ("volume", "volume"),
        ("issue", "issue"),
        ("page", "pages"),
        ("publisher", "publisher"),
        ("publisher-location", "place"),
    ):
        value = message.get(key)
        if isinstance(value, list) and value and isinstance(value[0], str):
            record[field] = value[0].strip()
        elif isinstance(value, str) and value.strip():
            record[field] = value.strip()
    page = record.pop("pages", None)
    article = message.get("article-number")
    if isinstance(article, str) and article.strip():
        record["article_number"] = article.strip()
    if isinstance(page, str) and page.strip():
        kind = page_value_kind(page)
        if kind == "article" and "article_number" not in record:
            record["article_number"] = page.strip()
        elif kind != "article":
            record["pages"] = page.strip()
    if record.get("doi"):
        record["url"] = f"https://doi.org/{record['doi']}"
    return record


def crossref_lookup(query: str, *, fetch: Callable[[str], dict[str, Any]] | None = None) -> LookupRecord | None:
    if fetch is None:
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query.bibliographic": query, "rows": 3})
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
    else:
        payload = fetch(query)
    items = payload.get("message", {}).get("items", [])
    if not items:
        return None
    first = items[0]
    if not isinstance(first, dict):
        return None
    titles = first.get("title") or []
    title = titles[0] if titles else ""
    if not isinstance(title, str) or not _title_matches(query, title):
        return None
    return _record_from_crossref_message(first)


def fixture_crossref_fetch(query: str) -> dict[str, object]:
    if not _title_matches(query, FIXTURE_TITLE):
        return {"message": {"items": []}}
    return {
        "message": {
            "items": [
                {
                    "DOI": FIXTURE_SAMPLE["doi"],
                    "title": [FIXTURE_TITLE],
                    "container-title": [FIXTURE_SAMPLE["container"]],
                    "volume": FIXTURE_SAMPLE["volume"],
                    "issue": FIXTURE_SAMPLE["issue"],
                    "page": FIXTURE_SAMPLE["pages"],
                    "publisher": FIXTURE_SAMPLE["publisher"],
                    "publisher-location": FIXTURE_SAMPLE["place"],
                }
            ]
        }
    }


def openalex_lookup(query: str) -> LookupRecord | None:
    # OpenAlex is optional enrichment; fixture mode returns nothing (Crossref carries tests).
    if resolver_mode() == "fixture":
        return None
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per_page": 3})
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    results = payload.get("results") or []
    if not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    title = first.get("title") or ""
    if not isinstance(title, str) or not _title_matches(query, title):
        return None
    record: LookupRecord = {}
    doi = first.get("doi") or ""
    if isinstance(doi, str) and doi.startswith("https://doi.org/"):
        record["doi"] = doi.removeprefix("https://doi.org/")
    primary = first.get("primary_location") or {}
    if isinstance(primary, dict):
        source = primary.get("source") or {}
        if isinstance(source, dict):
            name = source.get("display_name")
            if isinstance(name, str) and name.strip():
                record["container"] = name.strip()
    oa_url = openalex_oa_url(first)
    if oa_url:
        record["url"] = oa_url
    return record


def doi_org_lookup(doi: str) -> LookupRecord | None:
    if resolver_mode() == "fixture":
        if doi.strip().casefold() == FIXTURE_SAMPLE["doi"].casefold():
            return dict(FIXTURE_SAMPLE)
        return None
    url = f"https://doi.org/api/handles/{urllib.parse.quote(doi)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    values = payload.get("values") or []
    for item in values:
        if isinstance(item, dict) and item.get("type") == "URL":
            data = item.get("data", {})
            if isinstance(data, dict):
                value = data.get("value")
                if isinstance(value, str) and value.strip():
                    return {"doi": doi.strip(), "url": value.strip()}
    return None


def unpaywall_doi_url(doi: str, email: str) -> str:
    """DOI lookup. GET /v2/search is retired and is not used."""
    return (
        "https://api.unpaywall.org/v2/"
        + urllib.parse.quote(doi, safe="")
        + "?"
        + urllib.parse.urlencode({"email": email})
    )


def openalex_oa_url(work: dict[str, Any]) -> str | None:
    """Free-PDF address from best_oa_location, then the primary landing page."""
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        pdf = best.get("pdf_url")
        if isinstance(pdf, str) and pdf.strip():
            return pdf.strip()
        landing = best.get("landing_page_url")
        if isinstance(landing, str) and landing.strip():
            return landing.strip()
    primary = work.get("primary_location")
    if isinstance(primary, dict):
        landing = primary.get("landing_page_url")
        if isinstance(landing, str) and landing.strip():
            return landing.strip()
    return None


def unpaywall_lookup(doi: str, email: str) -> LookupRecord | None:
    if resolver_mode() == "fixture":
        if doi.strip().casefold() == FIXTURE_SAMPLE["doi"].casefold():
            return {"url": "https://example.org/fixture-open-access.pdf"}
        return None
    url = unpaywall_doi_url(doi, email)
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    best = payload.get("best_oa_location") or {}
    if isinstance(best, dict):
        landing = best.get("url_for_landing_page") or best.get("url")
        if isinstance(landing, str) and landing.strip():
            return {"url": landing.strip()}
    return None


def _merge_record(target: LookupRecord, incoming: LookupRecord) -> None:
    for key, value in incoming.items():
        if key in RESOLVER_FILLABLE and isinstance(value, str) and value.strip():
            if key not in target:
                target[key] = value.strip()


def _lookup_chain(title: str | None, doi_in_file: str | None) -> tuple[LookupRecord | None, list[ResolverCall]]:
    calls: list[ResolverCall] = []
    merged: LookupRecord = {}
    mode = resolver_mode()
    if mode == "off":
        return None, calls

    fetch = fixture_crossref_fetch if mode == "fixture" else None

    if title:
        looked_up = title.strip()
        record = crossref_lookup(looked_up, fetch=fetch)
        if record:
            calls.append({"name": "crossref", "looked_up": looked_up, "result": "matched"})
            _merge_record(merged, record)
        else:
            calls.append({"name": "crossref", "looked_up": looked_up, "result": "missed"})
        oa = openalex_lookup(looked_up)
        if oa:
            calls.append({"name": "openalex", "looked_up": looked_up, "result": "matched"})
            _merge_record(merged, oa)
        else:
            calls.append({"name": "openalex", "looked_up": looked_up, "result": "missed"})

    doi_key = doi_in_file or merged.get("doi")
    if doi_key:
        looked_up = doi_key.strip()
        record = doi_org_lookup(looked_up)
        if record:
            calls.append({"name": "doi.org", "looked_up": looked_up, "result": "matched"})
            _merge_record(merged, record)
        else:
            calls.append({"name": "doi.org", "looked_up": looked_up, "result": "missed"})
        email = unpaywall_email()
        if email:
            record = unpaywall_lookup(looked_up, email)
            if record:
                calls.append({"name": "unpaywall", "looked_up": looked_up, "result": "matched"})
                _merge_record(merged, record)
            else:
                calls.append({"name": "unpaywall", "looked_up": looked_up, "result": "missed"})
        elif mode != "off":
            calls.append(
                {
                    "name": "unpaywall",
                    "looked_up": looked_up,
                    "result": "missed",
                    "reason": "email not configured",
                }
            )

    if not merged:
        return None, calls
    return merged, calls


def _gathered_title_or_doi(source: dict[str, Any], text: str) -> tuple[str | None, str | None]:
    title = source.get("title")
    title_text = title.strip() if isinstance(title, str) and title.strip() else None
    if title_text and title_text.casefold() in text.casefold():
        return title_text, None
    for field in ("doi",):
        value = source.get(field)
        if isinstance(value, str) and value.strip() and _doi_in_text(value, text):
            return None, value.strip()
    folded = text.casefold()
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned.casefold() in folded and len(cleaned) > 12 and " " in cleaned:
            # Allow a title line in the file even when the caller omitted title in the payload.
            if title_text and _normalize_title(cleaned) == _normalize_title(title_text):
                return title_text, None
    return None, None


def apply_lookup_fields(
    source: dict[str, Any],
    text: str,
) -> tuple[dict[str, Any], list[ResolverCall], dict[str, str]]:
    """Fill blank resolver fields when the gathered text supports a match."""
    title, doi_in_file = _gathered_title_or_doi(source, text)
    needs_fill = any(field not in source for field in RESOLVER_FILLABLE)
    if not needs_fill or (title is None and doi_in_file is None):
        return source, [], {}

    record, calls = _lookup_chain(title, doi_in_file)
    provenance: dict[str, str] = dict(source.get("field_sources") or {})
    updated = dict(source)
    if not record:
        return updated, calls, provenance

    for field in RESOLVER_FILLABLE:
        if field in updated:
            continue
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            updated[field] = value.strip()
            provenance[field] = "lookup"
    if provenance:
        updated["field_sources"] = provenance
    return updated, calls, provenance


def enrich_sources(
    sources: list[dict[str, Any]], texts: dict[str, str]
) -> EnrichResult:
    """Fill blank resolver fields. The third value is what this pass showed.

    Those fills belong on the draft card. They are not a confirm fingerprint.
    A later pass that fills a field this pass missed does not change file hashes.
    """
    enriched: list[dict[str, Any]] = []
    all_calls: list[ResolverCall] = []
    resolver_digest: dict[str, Any] = {}
    for source in sources:
        text = texts.get(source["locator"], "")
        updated, calls, _provenance = apply_lookup_fields(source, text)
        enriched.append(updated)
        all_calls.extend(calls)
        resolver_digest[source["id"]] = {
            field: updated[field]
            for field in RESOLVER_FILLABLE
            if field in updated
        }
    return enriched, all_calls, resolver_digest


def find_opposing_point(sources: list[dict[str, Any]], texts: dict[str, str]) -> dict[str, object]:
    for source in sources:
        text = texts.get(source["locator"], "")
        lowered = text.casefold()
        for marker in OPPOSING_MARKERS:
            if marker not in lowered:
                continue
            start = lowered.index(marker)
            snippet = text[start : start + 240].strip()
            return {
                "found": True,
                "source_id": source["id"],
                "quote": snippet,
            }
    return {"found": False, "note": "no opposing point was found in gathered sources"}


def field_provenance(source: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    explicit = source.get("field_sources") or {}
    for field in (*("author", "title", "year", "quote"), *RESOLVER_FILLABLE):
        if field not in source:
            continue
        if field in explicit:
            mapping[field] = explicit[field]
        elif field in RESOLVER_FILLABLE and explicit.get(field) == "lookup":
            mapping[field] = "lookup"
        else:
            mapping[field] = "file"
    for field, origin in explicit.items():
        if field in source:
            mapping[field] = origin
    return mapping


def allowed_free_resolver(name: str) -> bool:
    return name.strip().casefold() in FREE_RESOLVERS
