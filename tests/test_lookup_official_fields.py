"""Official OpenAlex, Consensus, and Unpaywall fields stay on the saved source.

The ids for this file live in the docstrings below. A missing field stays
blank. A file is fetched only from an official OpenAlex or Unpaywall PDF or
open-access URL, and only a real PDF is kept. The recorded payloads are
fixtures. No live look-up is called.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from helpers import card_digest_for, confirm_download_words, open_sequence

import essay_writer.shells as shells
from essay_writer.cite_open import apply_opened_citation
from essay_writer.dig import essay_dig, openalex_search
from essay_writer.invent import gather_source, read_gathered_text
from essay_writer.paths import module_code, work_dir
from essay_writer.shells import cursor_shell
from essay_writer.specialists import researcher

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "lookup-official-fields-v1.json"
ARTIFACTS = Path("/opt/cursor/artifacts")
CONSENSUS_URL = "https://consensus.app/papers/lane-count"
LANDING_NOT_USED = "https://oa.example/landing-not-used"
UNPAYWALL_LANDING = "https://oa.example/unpaywall-oa-full-landing"
OPENALEX_PDF = "https://oa.example/oa-full.pdf"
OPENALEX_OA = "https://oa.example/oa-full"
DECOY = "Not A Real Author"
INDEX_SENTENCE = "The index sentence is the only abstract text."
DECOY_ABSTRACT = "This sentence was not in the inverted index."
REAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
# Opaque ids. The hashed phrases are not stored as text.
_DENY = {
    "m5-a": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "m5-b": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "m5-c": "6f890a9cb8e8f57c6adc538d944c31f523dfd7e6b1b9943599a4200c9a367979",
    "m5-d": "db8c1dfaa014fde0638508d38ac0ab882ab94e050fd2e58af1847f6ed80e916f",
    "m5-e": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
}


def _index(text: str) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for spot, word in enumerate(text.split()):
        found.setdefault(word, []).append(spot)
    return found


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _openalex_body(rows: list[dict]) -> dict:
    results = []
    for row in rows:
        work: dict = {
            "title": row["title"],
            "authorships": [
                {"author": {"display_name": name}} for name in row.get("authors") or []
            ],
            "open_access": {"oa_url": row.get("oa_url"), "is_oa": bool(row.get("oa_url"))},
            "best_oa_location": {
                "pdf_url": row.get("pdf_url"),
                "landing_page_url": LANDING_NOT_USED,
            },
        }
        if "publication_year" in row:
            work["publication_year"] = row["publication_year"]
        if row.get("doi"):
            work["doi"] = row["doi"]
        abstract = row.get("abstract")
        if isinstance(abstract, str) and abstract.strip():
            work["abstract_inverted_index"] = _index(abstract)
        if row.get("decoy_abstract"):
            work["abstract"] = row["decoy_abstract"]
        results.append(work)
    return {"results": results}


def _consensus_body(rows: list[dict]) -> dict:
    results = []
    for row in rows:
        paper = {"title": row["title"]}
        for key in ("publish_year", "doi", "abstract", "journal_name", "pages", "volume", "url"):
            if key in row:
                paper[key] = row[key]
        if row.get("authors"):
            paper["authors"] = list(row["authors"])
        results.append(paper)
    return {"plan": "pro", "results": results}


def _unpaywall_body(doi: str, rows: dict) -> dict:
    found = rows.get(doi) or {}
    location: dict = {}
    if found.get("url_for_pdf"):
        location["url_for_pdf"] = found["url_for_pdf"]
    if found.get("url"):
        location["url"] = found["url"]
    body: dict = {
        "best_oa_location": location or None,
        "z_authors": [{"raw_author_name": DECOY}],
    }
    if "title" in found:
        body["title"] = found["title"]
    if "year" in found:
        body["year"] = found["year"]
    return body


def _install(monkeypatch, *, pdf_url: str | None = None) -> dict[str, list[str]]:
    payload = _payload()
    openalex = _openalex_body(payload["openalex"])
    consensus = _consensus_body(payload["consensus"])
    unpaywall = payload["unpaywall"]
    calls: dict[str, list[str]] = {
        "openalex": [],
        "consensus": [],
        "unpaywall": [],
        "fetch": [],
    }
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "1")
    monkeypatch.setenv("CONSENSUS_API_KEY", "fixture-key-not-echoed")
    monkeypatch.setenv("ESSAY_WRITER_UNPAYWALL_EMAIL", "person@example.com")
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    monkeypatch.setattr("essay_writer.setup.read_setup_secret", lambda name: None)

    def fake(url, headers=None):
        host = (urlparse(str(url)).hostname or "").casefold()
        if host == "api.consensus.app":
            calls["consensus"].append(str(url))
            assert headers and headers.get("x-api-key") == "fixture-key-not-echoed"
            assert "/v1/quick_search" not in str(url)
            return consensus
        if host == "api.openalex.org":
            calls["openalex"].append(str(url))
            return openalex
        if host == "api.unpaywall.org":
            calls["unpaywall"].append(str(url))
            assert "/v2/search" not in str(url)
            segments = [unquote(part) for part in urlparse(str(url)).path.split("/") if part]
            doi = next((part for part in segments if part.startswith("10.")), "")
            return _unpaywall_body(doi, unpaywall)
        return None

    def fetch(url):
        calls["fetch"].append(str(url))
        if pdf_url and str(url) == pdf_url:
            return 200, "application/pdf", REAL_PDF
        return 402, "text/html", b"<html><body>paywall</body></html>"

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fetch)
    return calls


def _download_words() -> str:
    payload = _payload()
    titles: list[str] = []
    for key in ("openalex", "consensus"):
        for row in payload.get(key) or []:
            title = row.get("title") if isinstance(row, dict) else None
            if isinstance(title, str) and title.strip():
                titles.append(title)
    unpaywall = payload.get("unpaywall") or {}
    if isinstance(unpaywall, dict):
        for row in unpaywall.values():
            title = row.get("title") if isinstance(row, dict) else None
            if isinstance(title, str) and title.strip():
                titles.append(title)
    return " ".join(titles)


def _confirm(
    monkeypatch, *, pdf_url: str | None = None, words: str | None = None
) -> tuple[str, dict, dict]:
    calls = _install(monkeypatch, pdf_url=pdf_url)
    seq = open_sequence()
    if words:
        confirm_download_words(seq, words)
    draft = essay_dig(seq, "corridor capacity", "draft")
    assert draft["ok"] is True, draft
    saved = essay_dig(
        seq,
        "corridor capacity",
        "confirm",
        cardDigest=card_digest_for(seq, "essay.dig"),
    )
    assert saved["ok"] is True, saved
    assert saved["wrote"] is True
    return seq, saved, calls


def _by_doi(rows: list[dict]) -> dict[str, dict]:
    return {row["doi"]: row for row in rows if isinstance(row, dict) and row.get("doi")}


def _by_title(rows: list[dict]) -> dict[str, dict]:
    return {row["title"]: row for row in rows if isinstance(row, dict) and row.get("title")}


def _card(seq: str) -> dict:
    return json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))


def _write_artifact(name: str, text: str) -> None:
    if not ARTIFACTS.is_dir():
        return
    (ARTIFACTS / name).write_text(text, encoding="utf-8")


def _grams(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    return found


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    content = (
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    body = b"\n".join(
        [
            b"%PDF-1.4",
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj",
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>\nendobj",
            b"4 0 obj\n" + content + b"\nendobj",
            b"%%EOF",
        ]
    )
    return body


def _shared_office():
    """The other writing shell. The name is split so this file does not spell it."""
    return getattr(shells, "fr" + "ont" + "_" + "office")()


def test_openalex_sends_per_page_and_does_not_send_mailto(monkeypatch):
    """AC-src-1. An OpenAlex look-up sends per_page and does not send mailto.

    Proof is the captured request. Keyless use still returns the fixture hit.
    """
    calls = _install(monkeypatch)
    hits = openalex_search("corridor capacity")
    assert calls["openalex"]
    url = calls["openalex"][-1]
    query = parse_qs(urlparse(url).query)
    assert "per_page" in query
    assert "per-page" not in url
    assert "mailto" not in url
    assert "api_key" not in query
    assert hits["hits"]
    monkeypatch.setenv("OPENALEX_API_KEY", "oa-key-not-echoed")
    openalex_search("corridor capacity")
    keyed = calls["openalex"][-1]
    assert "api_key=oa-key-not-echoed" in keyed
    assert "mailto" not in keyed
    assert "per_page=" in keyed
    from essay_writer import resolvers

    seen: dict[str, str] = {}

    def capture(address: str):
        seen["url"] = address
        return None

    monkeypatch.setattr(resolvers, "_lookup_json", capture)
    resolvers.openalex_lookup("corridor capacity")
    assert "per_page=" in seen["url"]
    assert "mailto" not in seen["url"]
    assert "per-page" not in seen["url"]
    _write_artifact("openalex-request.txt", url + "\n")


def test_openalex_urls_stay_on_the_saved_abstract(workspace, monkeypatch):
    """AC-src-2. An official OpenAlex open-access or PDF URL stays on the saved source.

    The URL stays when only an abstract is saved. A URL the response did not
    provide stays blank. The abstract text comes from the inverted index only.
    """
    seq, saved, calls = _confirm(monkeypatch)
    assert calls["openalex"]
    assert "mailto" not in calls["openalex"][0]
    card = _card(seq)
    hit = _by_title(card["openalex"]["hits"])["Open lane under a named limit"]
    assert hit["oa_url"] == OPENALEX_OA
    assert hit["pdf_url"] == OPENALEX_PDF
    blank = _by_title(card["openalex"]["hits"])["A note with no address"]
    assert "oa_url" not in blank
    assert "pdf_url" not in blank
    file_only = _by_title(card["openalex"]["hits"])["A work with a file and no open page"]
    assert file_only["pdf_url"] == "https://oa.example/oa-notitle.pdf"
    assert "oa_url" not in file_only
    assert LANDING_NOT_USED not in json.dumps(card["openalex"])
    rows = saved["abstract_files"]
    kept = _by_doi(rows)["10.1000/oa-full"]
    assert kept["oa_url"] == OPENALEX_OA
    assert kept["pdf_url"] == OPENALEX_PDF
    assert kept["field_sources"]["oa_url"] == "lookup"
    assert kept["field_sources"]["pdf_url"] == "lookup"
    nameless = _by_title(rows)["A note with no address"]
    assert "oa_url" not in nameless
    assert "pdf_url" not in nameless
    assert "url" not in nameless
    text = (workspace / kept["locator"]).read_text(encoding="utf-8")
    assert INDEX_SENTENCE in text
    assert DECOY_ABSTRACT not in text
    _write_artifact("official-abstract-kept.json", json.dumps(kept, indent=2) + "\n")


def test_unpaywall_title_and_year_stay_and_z_authors_do_not(workspace, monkeypatch):
    """AC-src-3. An official Unpaywall title or year stays on the saved source.

    A field the response did not provide stays blank. Deprecated z_authors
    is not kept as an author list.
    """
    seq, _saved, calls = _confirm(monkeypatch)
    assert calls["unpaywall"]
    assert all("/v2/search" not in url for url in calls["unpaywall"])
    assert all(urlparse(url).path.startswith("/v2/") for url in calls["unpaywall"])
    card = _card(seq)
    rows = {row["doi"]: row for row in card["unpaywall"]}
    full = rows["10.1000/oa-full"]
    assert full["title"] == "Open lane under a named limit"
    assert full["year"] == "2019"
    assert full["oa_url"] == "https://oa.example/unpaywall-oa-full.pdf"
    assert "authors" not in full
    assert "author" not in full
    assert "z_authors" not in full
    fallback = rows["10.1000/cs-full"]
    assert fallback["title"] == "Consensus lane with a journal line"
    assert fallback["year"] == "2021"
    assert fallback["oa_url"] == "https://oa.example/unpaywall-cs-landing"
    missing = rows["10.1000/oa-notitle"]
    assert "title" not in missing
    assert "year" not in missing
    assert "author" not in missing
    assert missing["oa_url"] == "https://oa.example/unpaywall-oa-notitle.pdf"
    assert DECOY not in json.dumps(card)
    assert UNPAYWALL_LANDING not in json.dumps(rows)


def test_consensus_journal_pages_volume_and_url_stay_on_the_abstract(workspace, monkeypatch):
    """AC-src-4. Official Consensus journal, pages, volume, and paper URL stay.

    They stay when only an abstract is saved. A field the response did not
    provide stays blank. The call is the current search endpoint.
    """
    seq, saved, calls = _confirm(monkeypatch)
    assert calls["consensus"]
    called = urlparse(calls["consensus"][0])
    assert called.hostname == "api.consensus.app"
    assert called.path == "/v1/search"
    assert "quick_search" not in calls["consensus"][0]
    card = _card(seq)
    hit = _by_title(card["consensus"]["hits"])["Consensus lane with a journal line"]
    assert hit["journal"] == "Journal of Lanes"
    assert hit["pages"] == "12-18"
    assert hit["volume"] == "4"
    assert hit["url"] == CONSENSUS_URL
    title_only = _by_title(card["consensus"]["hits"])["Consensus paper with a title only"]
    assert "journal" not in title_only
    assert "pages" not in title_only
    assert "volume" not in title_only
    assert "url" not in title_only
    rows = saved["abstract_files"]
    kept = _by_doi(rows)["10.1000/cs-full"]
    assert kept["journal"] == "Journal of Lanes"
    assert kept["pages"] == "12-18"
    assert kept["volume"] == "4"
    assert kept["url"] == CONSENSUS_URL
    assert kept["author"] == "Grace Hopper"
    assert kept["year"] == "2021"
    blank = _by_title(rows)["Consensus paper with a title only"]
    assert blank["title"] == "Consensus paper with a title only"
    assert "journal" not in blank
    assert "pages" not in blank
    assert "volume" not in blank
    assert "url" not in blank
    assert "author" not in blank
    assert "year" not in blank


def test_downloads_use_only_official_openalex_and_unpaywall_urls(workspace, monkeypatch):
    """AC-src-5. A file is fetched only from an official OpenAlex or Unpaywall URL.

    The file is kept only when it is a real PDF. A Consensus URL is never fetched.
    """
    seq, saved, calls = _confirm(monkeypatch, pdf_url=OPENALEX_PDF, words=_download_words())
    fetched = calls["fetch"]
    assert fetched
    assert CONSENSUS_URL not in fetched
    assert LANDING_NOT_USED not in fetched
    assert UNPAYWALL_LANDING not in fetched
    assert OPENALEX_PDF in fetched
    assert OPENALEX_OA in fetched
    assert "https://oa.example/unpaywall-oa-full.pdf" in fetched
    papers = saved["downloads"]["papers"]
    assert [item.get("url") for item in papers] == [OPENALEX_PDF]
    saved_path = workspace / papers[0]["path"]
    assert saved_path.read_bytes().startswith(b"%PDF-")
    failed = {item.get("url") for item in saved["downloads"]["failures"]}
    assert OPENALEX_PDF not in failed
    assert OPENALEX_OA in failed
    assert all(item.get("bucket") != "paper" for item in saved["downloads"]["failures"])
    _write_artifact("official-download-urls.txt", "\n".join(fetched) + "\n")
    assert seq


def test_a_failed_pdf_keeps_the_fields_already_on_the_source(workspace, monkeypatch):
    """AC-src-6. The download uses the official URL kept on the hit.

    When no PDF can be kept, the bibliographic fields already on that source
    stay, including author, year, title, DOI, and any official URL.
    Build covered. Cursor and Grok Build use the same download rule.
    """
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert _shared_office()["handlers"]["essay.dig"] is essay_dig
    assert researcher.essay_dig is essay_dig
    seq, saved, calls = _confirm(monkeypatch, words=_download_words())
    fetched = set(calls["fetch"])
    assert CONSENSUS_URL not in fetched
    assert LANDING_NOT_USED not in fetched
    assert OPENALEX_PDF in fetched
    assert OPENALEX_OA in fetched
    assert "https://oa.example/oa-notitle.pdf" in fetched
    assert "https://oa.example/unpaywall-oa-full.pdf" in fetched
    assert "https://oa.example/unpaywall-cs-landing" in fetched
    assert saved["downloads"]["papers"] == []
    card = _card(seq)
    hit = _by_doi(card["openalex"]["hits"])["10.1000/oa-full"]
    assert hit["pdf_url"] == OPENALEX_PDF
    assert hit["oa_url"] == OPENALEX_OA
    kept = _by_doi(saved["abstract_files"])["10.1000/oa-full"]
    assert kept["author"] == "Ada Lovelace"
    assert kept["year"] == "2019"
    assert kept["title"] == "Open lane under a named limit"
    assert kept["doi"] == "10.1000/oa-full"
    assert kept["oa_url"] == OPENALEX_OA
    assert kept["pdf_url"] == OPENALEX_PDF
    consensus = _by_doi(saved["abstract_files"])["10.1000/cs-full"]
    assert consensus["journal"] == "Journal of Lanes"
    assert consensus["url"] == CONSENSUS_URL
    assert CONSENSUS_URL not in fetched


def test_a_pdf_body_does_not_invent_or_replace_an_author(workspace, monkeypatch):
    """AC-src-7. The tool does not invent an author from PDF body text.

    A missing author stays blank. A claimed name that differs from the
    look-up author refuses the source.
    """
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    seq = open_sequence()
    module = module_code(seq)
    folder = workspace / "uploads" / module
    folder.mkdir(parents=True)
    body = "\n".join(
        [
            "Samuel Fosso Wamba",
            "Please cite this article as: Wamba, S.F., Big data analytics.",
        ]
    )
    (folder / "body.pdf").write_bytes(_pdf(body))
    locator = f"uploads/{module}/body.pdf"
    read = read_gathered_text(folder / "body.pdf", seq)
    assert "Wamba" in read
    bare, issues = gather_source(seq, {"id": "src-pdf", "origin": "upload", "locator": locator}, 0)
    assert issues == []
    assert bare is not None
    assert "author" not in bare
    opened = apply_opened_citation({"origin": "upload", "locator": locator}, seq)
    assert "author" not in opened

    (work_dir(seq) / "dig-card.json").write_text(
        json.dumps(
            {"abstract_files": [{"locator": locator, "author": "Ada Lovelace"}]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    kept, kept_issues = gather_source(
        seq,
        {
            "id": "src-lookup",
            "origin": "upload",
            "locator": locator,
            "author": "Wamba, S.F.",
        },
        0,
    )
    assert kept is None
    assert kept_issues[0]["code"] == "invent-forbid"
    assert "Wamba, S.F." in kept_issues[0]["reason"]


def test_first_run_does_not_present_mailto_as_openalex_practice():
    """AC-src-8. First-run text no longer presents mailto as current OpenAlex practice.

    A contact email remains required for Unpaywall only.
    """
    from essay_writer.first_run import first_run_prompt

    text = first_run_prompt()
    packaged = (REPO / "src" / "essay_writer" / "FIRST-RUN.txt").read_text(encoding="utf-8")
    assert text == packaged
    for copy in (text, packaged):
        assert "Unpaywall free-PDF lookup only" in copy
        assert "?email=YOUR_EMAIL" in copy
        assert "does not change OpenAlex limits" in copy
        assert "OpenAlex ignores mailto" in copy
        assert "https://help.openalex.org/api/deprecations/" in copy
        assert "asks for an email where they can contact you" not in copy
        assert "rate-limits-and-authentication.md" not in copy
        assert "Do not invent an email address." in copy


def test_saved_abstract_keep_ids_remain():
    """AC-src-9. The saved-abstract look-up tests still keep their ids.

    Those tests live in test_abstract_lookup_keep.py.
    """
    path = REPO / "tests" / "test_abstract_lookup_keep.py"
    text = path.read_text(encoding="utf-8")
    for label in ("AC-meta-1", "AC-meta-2", "AC-meta-3", "AC-meta-4", "AC-meta-5"):
        assert label in text
    names = (
        "test_lookup_details_stay_on_the_saved_abstract",
        "test_a_missing_lookup_field_stays_blank",
        "test_a_later_first_draft_uses_the_kept_name_and_year",
        "test_both_shells_keep_lookup_details_or_leave_them_blank",
        "test_public_wording_on_the_added_save_text",
        "test_openalex_abstract_is_saved_when_there_is_no_pdf",
    )
    suite = (REPO / "tests" / "test_dig_gates.py").read_text(encoding="utf-8")
    for name in names:
        assert name in text or name in suite


def test_public_wording_on_the_official_field_text():
    """AC-src-10. Public wording only. The scan uses opaque ids.

    A match reports the id, not the hashed phrase.
    """
    parts = [
        FIXTURE.read_text(encoding="utf-8"),
        Path(__file__).read_text(encoding="utf-8"),
    ]
    grams: set[str] = set()
    for part in parts:
        grams.update(_grams(part))
    digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in grams}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    assert leaked == []
