"""Regressions for invent-forbid citation bugs.

A citation may name only a file that was gathered. A year, a page, a
quotation, and a download address come from that file, not from a look-up
miss, a file timestamp, or a shared topic.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from docx import Document
from helpers import ESSAY, open_sequence, write_upload

from essay_writer.cite_fit import (
    apply_body_cites,
    same_idea,
    strip_token,
    withhold_body_cites,
)
from essay_writer.cite_open import cite_look, page_span_printed
from essay_writer.downloads import classify_download, links_card
from essay_writer.gates import _gathered_texts, unquoted_exact
from essay_writer.invent import check_claims
from essay_writer.pdf_year import citation_year, publication_year
from essay_writer.resolvers import doi_org_lookup


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(lines: list[str]) -> bytes:
    commands = " ".join(f"({_escape(line)}) Tj" for line in lines)
    stream = f"BT /F1 12 Tf 72 720 Td {commands} ET".encode()
    return (
        b"%PDF-1.4\n1 0 obj<</Length "
        + str(len(stream)).encode()
        + b">>stream\n"
        + stream
        + b"\nendstream\nendobj\ntrailer<<>>\n%%EOF\n"
    )


def _plant(seq: str, name: str, **source: object) -> None:
    from essay_writer.state import load_state, save_state

    row = {
        "id": "src-hasan",
        "author": "Hasan, M. and Sarker, S.",
        "year": "1999",
        "title": "Corridor risk",
        "locator": f"uploads/{ESSAY}/{name}",
    }
    row.update(source)
    state = load_state(seq)
    research = state.setdefault("research", {})
    research["summary"] = {"sources": [row]}
    save_state(seq, state)


class _Handle:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> _Handle:
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_check_claims_rejects_a_source_that_was_not_gathered(workspace):
    """A claim is not evidence when the source would not survive gather."""
    quote = "The strait handles a large share of flows."
    write_upload(workspace, name="smith.md", text=quote + "\n")
    brief = workspace / "Essay-writer" / ESSAY / "brief.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(quote + "\n", encoding="utf-8")
    locator = f"uploads/{ESSAY}/smith.md"
    cases = [
        (
            {"id": "sample", "origin": "sample", "locator": locator},
            "sample reference list",
        ),
        ({"id": "none", "origin": "upload"}, "no gathered locator"),
        (
            {"id": "paid", "origin": "upload", "locator": locator, "resolver": "Scopus"},
            "paid resolver",
        ),
        (
            {
                "id": "mismatch",
                "origin": "upload",
                "locator": f"Essay-writer/{ESSAY}/brief.md",
            },
            "does not match",
        ),
        (
            {"id": "missing", "origin": "upload", "locator": f"uploads/{ESSAY}/gone.md"},
            "not a file",
        ),
        (
            {"id": "kb1", "origin": "kb1", "locator": f"kb1/{ESSAY}/note.md"},
            "not a file",
        ),
    ]
    for source, needle in cases:
        texts = {source["locator"]: quote} if "locator" in source else {}
        issues = check_claims(
            [source],
            [{"source_id": source["id"], "quote": quote}],
            texts,
        )
        assert issues, source
        assert any(needle in item["reason"] for item in issues), (needle, issues)
    clean = check_claims(
        [{"id": "real", "origin": "upload", "locator": locator}],
        [{"source_id": "real", "quote": quote}],
        {locator: quote},
    )
    assert clean == []
    other = workspace / "uploads" / "RPT1008AA"
    other.mkdir(parents=True)
    (other / "foreign.md").write_text(quote + "\n", encoding="utf-8")
    foreign = "uploads/RPT1008AA/foreign.md"
    crossed = check_claims(
        [{"id": "other", "origin": "upload", "locator": foreign}],
        [{"source_id": "other", "quote": quote}],
        {foreign: quote},
        ESSAY,
    )
    assert any(item["code"] == "cross-essay" for item in crossed), crossed


def test_check_claims_quote_must_be_an_exact_span_of_the_opened_pdf(workspace):
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "strait.pdf"
    real = "The strait handles a large share of flows."
    path.write_bytes(_pdf([real, "32"]))
    fake = "The strait was closed for nine months."
    source = {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{ESSAY}/{path.name}",
    }
    issues = check_claims(
        [source],
        [{"source_id": "src-1", "quote": fake}],
        {source["locator"]: fake},
    )
    assert any("exact span" in item["reason"] for item in issues), issues
    clean = check_claims(
        [source],
        [{"source_id": "src-1", "quote": real}],
        {source["locator"]: fake},
    )
    assert clean == []


def test_same_idea_needs_most_claim_words_not_half():
    """Three of six claim words is not most of the claim. Four of six is."""
    sentence = "Maritime corridors reveal fragile routing stress."
    thin = "Maritime corridors reveal weather patterns offshore."
    supported = "Maritime corridors reveal fragile routing stress offshore."
    assert same_idea(sentence, thin) is False
    assert same_idea(sentence, supported) is True


def test_withheld_page_cite_is_removed_from_the_returned_text(workspace):
    from essay_writer.cite_fit import _write_record

    page = strip_token("The claim (Peng, 2018, p. 12) stands.", "peng, 2018")
    assert "Peng" not in page
    assert "stands" in page
    et_al = strip_token("Peng et al. (2018) found the same.", "peng, 2018")
    assert "Peng" not in et_al
    seq = open_sequence()
    _write_record(seq, {"ok": [], "rejected": [], "withheld": ["peng, 2018"]})
    applied = apply_body_cites(seq, "5", "The claim (Peng, 2018, p. 12) stands.")
    assert "Peng" not in applied["text"]
    assert "stands" in applied["text"]
    _kept, sections = withhold_body_cites(
        seq,
        [],
        [{"body": "The claim (Peng, 2018, p. 4; Yamoah, 2020) stands."}],
    )
    body = sections[0]["body"]
    assert "Peng" not in body
    assert "Yamoah" in body
    idle = apply_body_cites(seq, "4a", "The claim (Peng, 2018, p. 12) stands.")
    assert "Peng" in idle["text"]
    assert idle["applied"] is False


def test_cite_look_does_not_give_a_joint_paper_year_to_one_author(workspace):
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "hasan-sarker.pdf"
    path.write_bytes(_pdf(["Hasan and Sarker (2023)", "Corridor risk"]))
    seq = open_sequence()
    _plant(seq, path.name)
    solo = "Sarker (1999) found the opposite."
    assert cite_look(seq, solo) == solo
    both = "Hasan and Sarker (1999) found it."
    assert cite_look(seq, both) == "Hasan and Sarker (2023) found it."


def test_page_span_requires_every_page_in_the_printed_list():
    assert page_span_printed("1-3", ("1", "3")) is False
    assert page_span_printed("1-3", ("1", "2", "3")) is True
    assert page_span_printed("32", ("32",)) is True
    assert page_span_printed("12–14", ("12", "14")) is False
    assert page_span_printed("1, 3", ("1", "3")) is True


def test_publication_year_uses_the_printed_header_not_a_download(workspace):
    header = "Journal of Transport Geography 76 (2019) 102-115"
    download = "Downloaded by Awarding university (2024)"
    assert publication_year(f"{header}\n{download}") == "2019"
    assert publication_year(header) == "2019"
    assert publication_year(download) is None
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    path = folder / "header-2019.pdf"
    path.write_bytes(_pdf([header, download]))
    stamped = datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamped, stamped))
    assert citation_year(path) == "2019"


def test_unquoted_exact_flags_an_unquoted_copy_and_keeps_a_quotation():
    sentence = "The corridor depends on a narrow strait that carries crude today."
    both = f'"{sentence}" Later the draft copies it. {sentence}'
    assert sentence in unquoted_exact(both, [sentence])
    quoted = f'A gathered line says "{sentence}" and then stops.'
    assert unquoted_exact(quoted, [sentence]) == []
    inner = 'The corridor depends on a narrow "strait" that carries crude today.'
    wrapped = f'"{inner}"'
    assert unquoted_exact(wrapped, [inner]) == []


def test_unquoted_exact_reads_a_gathered_pdf_and_a_docx_table(workspace):
    sentence = "The strait handles a large share of seaborne crude flows."
    folder = workspace / "uploads" / ESSAY
    folder.mkdir(parents=True)
    pdf_path = folder / "flows.pdf"
    pdf_path.write_bytes(_pdf([sentence]))
    docx_path = folder / "flows.docx"
    document = Document()
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = sentence
    document.save(docx_path)
    seq = open_sequence()
    pdf_pack = {"sources": [{"locator": f"uploads/{ESSAY}/{pdf_path.name}"}]}
    docx_pack = {"sources": [{"locator": f"uploads/{ESSAY}/{docx_path.name}"}]}
    assert sentence in unquoted_exact(sentence, _gathered_texts(seq, pdf_pack))
    assert sentence in unquoted_exact(sentence, _gathered_texts(seq, docx_pack))


def test_classify_download_does_not_save_html_or_a_paywall_as_pdf():
    paywall = b"%PDF-1.4\nPlease subscribe to read this article\n"
    assert classify_download(200, "application/pdf", paywall) == "paywall"
    html = b"%PDF-1.4\n<html><body>Abstract only</body></html>"
    assert classify_download(200, "application/pdf", html) == "html-abstract"
    assert classify_download(200, "application/pdf", b"This is not a pdf body") == "not-pdf"
    assert classify_download(200, "application/octet-stream", b"PDF-1.4\n%%EOF\n") != "paper"


def test_links_card_does_not_invent_a_doi_url():
    card = links_card(
        [{"doi": "10.1000/strait", "title": "Chokepoints", "bucket": "leftover"}]
    )
    assert card["items"]
    assert "url" not in card["items"][0]
    given = links_card(
        [
            {
                "doi": "10.1000/strait",
                "title": "Chokepoints",
                "url": "https://doi.org/10.1000/strait",
                "bucket": "leftover",
            }
        ]
    )
    assert given["items"][0]["url"] == "https://doi.org/10.1000/strait"


def test_doi_org_miss_does_not_invent_a_url(monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    payloads = [
        json.dumps(
            {"values": [{"type": "HS_ADMIN", "data": {"value": "10.1000/not-a-match"}}]}
        ).encode(),
        json.dumps(
            {
                "values": [
                    {
                        "type": "URL",
                        "data": {"value": "https://publisher.example/paper"},
                    }
                ]
            }
        ).encode(),
    ]

    def fake_urlopen(url: str, timeout: int = 15) -> _Handle:
        return _Handle(payloads.pop(0))

    monkeypatch.setattr("essay_writer.resolvers.urllib.request.urlopen", fake_urlopen)
    assert doi_org_lookup("10.1000/not-a-match") is None
    found = doi_org_lookup("10.1000/not-a-match")
    assert found == {"doi": "10.1000/not-a-match", "url": "https://publisher.example/paper"}
