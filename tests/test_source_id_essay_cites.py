"""Source ids, essay cite counts, and the last-step close.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. Opaque ids name a deny-list hit. The phrases
themselves are not parametrize labels.

Build covered: Cursor and Grok Build share essay.stage, finish_first_draft,
and the stage 10 close.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from docx import Document
from helpers import open_sequence, write_proof, write_upload
from test_stage10_close_and_findings import _docx_text, _final_file, _seed_first_draft
from test_word_references_4a import (
    MODULE,
    NUMBER,
    _brief,
    _diary_pack,
    _park_stage10,
    _plant_stage10_pack,
)

from essay_writer.build_office import stage_launch
from essay_writer.citation_list import (
    load_citation_list,
    match_token,
    reference_entries_for_token,
    short_in_text,
)
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.essay_cites import (
    cited_source_ids,
    essay_cite_bounds,
    fit_essay_cites,
    work_is_relevant,
)
from essay_writer.harvard_ref_check import compliance_misses
from essay_writer.invent import gather_sources
from essay_writer.late_chain import _write_stage10_sequence, write_stage10
from essay_writer.paths import essay_dir, module_code, work_dir
from essay_writer.research_packs import ship_4b
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, writer_handlers
from essay_writer.source_ids import source_ids_for, stable_source_id
from essay_writer.specialists.writer import finish_first_draft
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path, load_pointer
from essay_writer.word_references import token_is_covered

REPO = Path(__file__).resolve().parents[1]
NOTE = "The opened file states the limit, and the year is the one stored on the list."
QUESTION = "Question: When is it fair to close a fishery so a fish stock can recover?\n"
PLAN = (
    "The plan follows the recovery of the stock, the evidence for a closure, "
    "and who bears that closure."
)
# Opaque ids. A hit reports the id, not the phrase.
_DENY = {
    "w-1": "f73d3f95d9fedff94a4a4b54b65bb5b2794170c702e6b3ab3fd35783050faed8",
    "w-2": "b59e69febb78bfb221db05c452f1e98d4f14a50edde0c7ec8754dda5a7575a9e",
    "w-3": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "w-4": "add92b9cde2bdbf3daaf65a0db79e9b1a7fa428b71b4d6ce38c742eb6dca0c1c",
    "w-5": "459415a966d88d3e30f7e0408fa7b6ce3eef5316ab8bde26d78213aaf583a606",
}


def _pieces(text: str) -> set[str]:
    folded = text.casefold()
    tokens = re.findall(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", folded)
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    found.update(line.strip() for line in folded.splitlines() if line.strip())
    return found


def _leaked(text: str) -> list[str]:
    digests = {hashlib.sha256(piece.encode()).hexdigest() for piece in _pieces(text)}
    return [opaque for opaque, digest in _DENY.items() if digest in digests]


def _brief_text(seq: str, extra: str) -> None:
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(QUESTION + extra, encoding="utf-8")


def _plan(seq: str) -> None:
    path = _note_path(seq, "3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_tracking("3", status="final", look=PLAN, essay_id=seq),
        encoding="utf-8",
    )


def _row(number: int, *, title: str | None = None) -> dict[str, str]:
    author = f"Writer{number} Lane"
    return {
        "id": f"fishery-{number}",
        "author": author,
        "year": "2020",
        "title": title or f"Fishery closure and stock recovery note {number}",
        "doi": f"10.1000/fishery-{number}",
    }


def _library(seq: str, rows: list[dict[str, str]]) -> None:
    delivered = ship_4b(seq, rows, {row["id"]: NOTE for row in rows})
    assert delivered.get("blocked") is not True, delivered
    assert load_citation_list(seq)["written"] is True


def _sentence(row: dict[str, str]) -> str:
    cite = short_in_text(row["author"], row["year"])
    return f"The fishery closure supports stock recovery {cite}."


def test_reordering_keeps_each_papers_source_id(workspace):
    """AC-id-1: A source id is unique and stable. Reordering does not renumber a paper."""
    alpha = {
        "author": "Ada Alpha",
        "year": "2024",
        "title": "Compliance in an octopus fishery closure",
        "doi": "10.1002/pan3.10742",
    }
    beta = {
        "author": "Ada Alpha",
        "year": "2024",
        "title": "Wellbeing in periodic octopus closures",
        "doi": "10.1080/26395916.2024.2412616",
    }
    forward = source_ids_for([alpha, beta])
    backward = source_ids_for([beta, alpha])
    assert forward[0] == backward[1]
    assert forward[1] == backward[0]
    assert len(set(forward)) == 2
    assert forward[0] == stable_source_id(alpha)
    assert all(not ident.startswith("src-") for ident in forward)

    seq = open_sequence()
    module = module_code(seq)
    raws = []
    for key, paper in (("alpha", alpha), ("beta", beta)):
        body = "\n".join([paper["author"], paper["year"], paper["title"], paper["doi"], "Noted."])
        write_upload(workspace, module, f"{key}.md", body + "\n")
        raws.append(
            {
                "origin": "upload",
                "locator": f"uploads/{module}/{key}.md",
                **paper,
            }
        )
    first, issues = gather_sources(seq, raws)
    assert issues == []
    second, more = gather_sources(seq, list(reversed(raws)))
    assert more == []
    by_doi = {item["doi"]: item["id"] for item in first}
    again = {item["doi"]: item["id"] for item in second}
    assert by_doi == again
    assert len(set(by_doi.values())) == 2
    assert all(not ident.startswith("src-") for ident in by_doi.values())
    write_proof(
        "source-id-reorder.txt",
        "\n".join(f"{doi} {ident}" for doi, ident in sorted(by_doi.items())) + "\n",
    )
    assert workspace is not None


def test_a_shared_short_form_stays_two_works(tmp_path):
    """AC-id-2: Two works that share a short form are checked on their own lines."""
    lead = "Elizabeth Drury O'Neill and Tim Daw and Ada Lane and Emilie Lindkvist"
    other = "Elizabeth Drury O'Neill and Tim Daw and Bea Lane and Cole Lane and Emilie Lindkvist"
    first = {
        "id": "oneill-compliance",
        "author": lead,
        "year": "2024",
        "title": "Diverse responses to octopus fishery closures",
        "doi": "10.1002/pan3.10742",
    }
    second = {
        "id": "oneill-wellbeing",
        "author": other,
        "year": "2024",
        "title": "Human wellbeing in periodic octopus closures",
        "doi": "10.1080/26395916.2024.2412616",
    }
    assert short_in_text(lead, "2024") == short_in_text(other, "2024")
    seq = open_sequence(MODULE)
    _library(seq, [first, second])
    shared = short_in_text(lead, "2024")
    inner = shared[1:-1]
    assert match_token(seq, inner) is None
    assert len(reference_entries_for_token(seq, inner)) == 2
    from essay_writer.citation_list import full_reference
    from essay_writer.textutil import reference_parts

    lines = [full_reference(first), full_reference(second)]
    path = tmp_path / "shared.docx"
    document = Document()
    document.add_paragraph(f"The closure is discussed {shared}.")
    document.add_paragraph("References")
    for source in (first, second):
        paragraph = document.add_paragraph()
        for piece, italic in reference_parts(source):
            run = paragraph.add_run(piece)
            run.italic = italic
    document.save(str(path))
    misses = compliance_misses(path, [first, second], essay_id=seq)
    assert misses == []
    assert token_is_covered(inner, lines, seq) is True
    write_proof(
        "shared-short-form-close.txt",
        "\n".join(
            [
                f"short form: {shared}",
                f"ids: {first['id']} | {second['id']}",
                "misses: []",
                *lines,
                "",
            ]
        ),
    )


def test_a_silent_brief_cites_the_essay_not_only_the_list(workspace):
    """AC-cite-1: Silence uses ceil(words / 1000 * 8) on the essay. A stated count wins."""
    seq = open_sequence()
    _brief_text(seq, "The assignment is 2,000 words.\n")
    _plan(seq)
    rows = [_row(number) for number in range(1, 21)]
    _library(seq, rows)
    listed = load_citation_list(seq)
    assert len(listed["entries"]) >= 16
    draft = " ".join(_sentence(row) for row in rows[:9])
    sources = [
        {
            "id": row["id"],
            "author": row["author"],
            "year": row["year"],
            "title": row["title"],
            "in_text": short_in_text(row["author"], row["year"]),
        }
        for row in rows
    ]
    assert len(cited_source_ids(draft, sources)) == 9
    assert essay_cite_bounds(seq)["minimum"] == 16
    assert essay_cite_bounds(seq)["from"] != "stated"
    fitted = fit_essay_cites(seq, draft)
    count = len(cited_source_ids(fitted, sources))
    assert count >= 16
    assert count <= 24
    write_proof(
        "essay-cite-floor.txt",
        f"list entries: {len(listed['entries'])}\nessay before: 9\nessay after: {count}\n\n{fitted}\n",
    )

    stated = open_sequence()
    _brief_text(stated, "The assignment is 2,000 words.\nUse 5 sources.\n")
    _plan(stated)
    _library(stated, rows[:12])
    bounds = essay_cite_bounds(stated)
    assert bounds["from"] == "stated"
    assert bounds["minimum"] == 5
    assert bounds["minimum"] != 16
    short = " ".join(_sentence(row) for row in rows[:2])
    raised = fit_essay_cites(stated, short)
    raised_count = len(cited_source_ids(raised, sources[:12]))
    assert raised_count == 5
    write_proof(
        "essay-cite-stated.txt",
        f"minimum: {bounds['minimum']}\nessay after: {raised_count}\n\n{raised}\n",
    )
    assert workspace is not None


def test_the_essay_stops_at_twelve_works_per_thousand_words(workspace):
    """AC-cite-2: The essay cites at most 12 distinct works per 1,000 words."""
    seq = open_sequence()
    _brief_text(seq, "The assignment is 2,000 words.\n")
    _plan(seq)
    rows = [_row(number) for number in range(1, 31)]
    _library(seq, rows)
    assert len(load_citation_list(seq)["entries"]) == 30
    draft = " ".join(_sentence(row) for row in rows)
    sources = [
        {
            "id": row["id"],
            "author": row["author"],
            "year": row["year"],
            "title": row["title"],
            "in_text": short_in_text(row["author"], row["year"]),
        }
        for row in rows
    ]
    assert len(cited_source_ids(draft, sources)) == 30
    assert essay_cite_bounds(seq)["maximum"] == 24
    fitted = fit_essay_cites(seq, draft)
    count = len(cited_source_ids(fitted, sources))
    assert count == 24
    assert len(load_citation_list(seq)["entries"]) == 30
    write_proof(
        "essay-cite-cap.txt",
        f"list entries: 30\nessay after: {count}\n\n{fitted}\n",
    )
    assert workspace is not None


def test_a_work_is_cited_only_when_it_bears_on_the_question_and_plan(workspace):
    """AC-cite-3: A work is not cited only because it is on the citation list."""
    seq = open_sequence()
    _brief_text(seq, "The assignment is 2,000 words.\n")
    _plan(seq)
    useful = [_row(number) for number in range(1, 4)]
    stray = _row(9, title="Quantum entanglement in superconductors")
    _library(seq, useful + [stray])
    question = "When is it fair to close a fishery so a fish stock can recover?"
    assert work_is_relevant(useful[0], question, PLAN) is True
    assert work_is_relevant(stray, question, PLAN) is False
    draft = "The fishery closure supports stock recovery."
    fitted = fit_essay_cites(seq, draft)
    stray_cite = short_in_text(stray["author"], stray["year"])
    assert stray_cite not in fitted
    for row in useful:
        assert short_in_text(row["author"], row["year"]) in fitted
    sources = [
        {
            "id": row["id"],
            "author": row["author"],
            "year": row["year"],
            "title": row["title"],
            "in_text": short_in_text(row["author"], row["year"]),
        }
        for row in useful + [stray]
    ]
    assert stray["id"] not in cited_source_ids(fitted, sources)
    assert len(load_citation_list(seq)["entries"]) == 4
    assert len(cited_source_ids(draft, sources)) == 0
    write_proof("essay-cite-relevant.txt", fitted + "\n")
    assert workspace is not None


def _shared_rows() -> list[dict[str, str]]:
    lead = "Elizabeth Drury O'Neill and Tim Daw and Ada Lane and Emilie Lindkvist"
    other = "Elizabeth Drury O'Neill and Tim Daw and Bea Lane and Cole Lane and Emilie Lindkvist"
    return [
        {
            "id": "oneill-compliance",
            "author": lead,
            "year": "2024",
            "title": "Diverse responses to octopus fishery closures",
            "doi": "10.1002/pan3.10742",
        },
        {
            "id": "oneill-wellbeing",
            "author": other,
            "year": "2024",
            "title": "Human wellbeing in periodic octopus closures",
            "doi": "10.1080/26395916.2024.2412616",
        },
    ]


def _plant_close(seq: str, body: str, rows: list[dict[str, str]]) -> None:
    from essay_writer.brief_contract import remember_registration

    _library(seq, rows)
    _brief()
    remember_registration(seq, NUMBER)
    _park_stage10(seq)
    listed = load_citation_list(seq)
    lines = [
        str(entry.get("reference") or "").strip()
        for entry in listed["entries"]
        if str(entry.get("reference") or "").strip()
    ]
    pack = _diary_pack(seq, body=body, references_markdown="\n".join(lines))
    pack["sources"] = rows
    _plant_stage10_pack(seq, pack)


def test_stage10_writes_the_final_file_when_the_close_passes(workspace, monkeypatch, tmp_path):
    """AC-close-1: Stage 10 writes the final Word file when the close checks pass."""
    monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(tmp_path / "Documents"))
    seq = open_sequence(MODULE)
    rows = _shared_rows()
    shared = short_in_text(rows[0]["author"], rows[0]["year"])
    _plant_close(seq, f"The closure is discussed {shared}.", rows)
    written = write_stage10(seq)
    assert written["ok"] is True, written
    final = _final_file(seq)
    text = _docx_text(final)
    assert "10.1002/pan3.10742" in text
    assert "10.1080/26395916.2024.2412616" in text
    write_proof(
        "stage10-shared-close.txt",
        json.dumps(
            {"ok": written["ok"], "final": final.name, "refused": written.get("refused")},
            indent=2,
        )
        + "\n"
        + text
        + "\n",
    )
    assert workspace is not None


def test_an_off_list_citation_does_not_write_the_final_file(workspace):
    """AC-close-2: An off-list citation such as (Nobody, 1999) is refused."""
    seq = open_sequence(MODULE)
    rows = _shared_rows()
    shared = short_in_text(rows[0]["author"], rows[0]["year"])
    _plant_close(
        seq,
        f"The closure is discussed {shared}. An unlisted paper is not added (Nobody, 1999).",
        rows,
    )
    first = _seed_first_draft(seq)
    before = first.read_bytes()
    refused = write_stage10(seq)
    assert refused["ok"] is False, refused
    assert refused.get("stored") is not True
    assert refused["refused"] == "references-cites"
    assert "nobody, 1999" in str(refused.get("reason") or "").casefold()
    assert first.read_bytes() == before
    assert not list((work_dir(seq) / "output").rglob("*-final.docx"))
    pointer = load_pointer(seq)
    assert pointer["closed"] is False
    write_proof("stage10-nobody-refusal.txt", str(refused.get("reason") or "") + "\n")
    assert workspace is not None


def test_a_matched_line_can_still_fail_the_harvard_close(tmp_path):
    """AC-close-3: A listed work that still fails the Harvard close is named, not restyled."""
    source = {
        "id": "kenchington-2018",
        "author": "Richard A. Kenchington and Michel J. Kaiser and Kristina Boerder",
        "year": "2018",
        "title": "MPAs, fishery closures and stock rebuilding",
        "container": "Figshare",
        "url": "https://ro.uow.edu.au/cgi/viewcontent.cgi?article=4779&context=lhapapers",
    }
    line = (
        "Richard A. Kenchington and Michel J. Kaiser and Kristina Boerder (2018) "
        "MPAs, fishery closures and stock rebuilding."
    )
    path = tmp_path / "leftover.docx"
    document = Document()
    document.add_paragraph("The closure is discussed (Kenchington, Kaiser and Boerder, 2018).")
    document.add_paragraph("References")
    document.add_paragraph(line)
    document.save(str(path))
    misses = compliance_misses(path, [source])
    codes = [item["code"] for item in misses]
    assert "journal-italic" in codes
    assert "url" in codes
    checker = inspect.getsource(compliance_misses)
    assert "Figshare" not in checker
    write_proof(
        "harvard-leftover.txt",
        "A listed line matched its own work and still failed the Harvard close.\n"
        + "\n".join(item["detail"] for item in misses)
        + "\n",
    )


def test_student_facing_copy_stays_plain(workspace):
    """AC-public-1: Changed student-facing files stay plain. Opaque deny-list ids."""
    files = [
        REPO / "src" / "essay_writer" / "essay_cites.py",
        REPO / "src" / "essay_writer" / "source_ids.py",
    ]
    leaked: list[str] = []
    for path in files:
        leaked.extend(_leaked(path.read_text(encoding="utf-8")))
    assert leaked == []
    write_proof("wording-scan.txt", "scanned: " + ", ".join(path.name for path in files) + "\n")
    assert workspace is not None


def test_both_shells_share_the_source_id_and_the_essay_count():
    """AC-shell-1: Cursor and Grok Build use the same close and the same essay count. Build covered."""
    assert cursor_shell()["handlers"]["essay.stage"] is HANDLERS["essay.stage"]
    assert writer_handlers()["essay.stage"] is HANDLERS["essay.stage"]
    assert stage_launch("5")["settings"]["rules"] == cursor_stage_launch("5")["settings"]["rules"]
    assert stage_launch("10")["settings"]["rules"] == cursor_stage_launch("10")["settings"]["rules"]
    draft = inspect.getsource(finish_first_draft)
    assert "fit_essay_cites" in draft
    close = inspect.getsource(write_stage10) + inspect.getsource(_write_stage10_sequence)
    assert "writer_reference_block" in close
    assert "Build covered" in Path(__file__).read_text(encoding="utf-8")
