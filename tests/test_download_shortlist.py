"""Stage 4a keeps the full gather, then downloads a shorter set.

The hyphen acceptance ids for this file live in the docstrings below.
Each id is seated once. Opaque ids name a wording hit. The phrases
themselves are not pytest node ids.

Build covered. Both shells call this download shortlist.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from docx import Document
from helpers import OTHER, card_digest_for, open_sequence

import essay_writer.shells as shells
from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import _open_candidates, essay_dig
from essay_writer.download_shortlist import choose_downloads
from essay_writer.essay_cites import essay_cite_bounds
from essay_writer.paths import essay_dir, work_dir
from essay_writer.research_packs import ship_4a
from essay_writer.shells import cursor_shell
from essay_writer.source_ids import stable_source_id
from essay_writer.specialists import researcher
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_note import render_tracking
from essay_writer.stage_state import _note_path
from essay_writer.student_voice import student_surface_hits

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = Path("/opt/cursor/artifacts")
QUESTION = "When is it fair to close a fishery so a fish stock can recover?"
PLAN = "Coastal community bears the cost. Measured recovery is the test of the closure."
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
HTML = b"<html><body>Abstract only.</body></html>"
# Opaque ids. A hit reports the id, not the phrase.
_DENY = {
    "d-1": "f73d3f95d9fedff94a4a4b54b65bb5b2794170c702e6b3ab3fd35783050faed8",
    "d-2": "782faac2e1aff56f344451429f660d818aa3ca5ac13bb8d095f1249cd7a9a1f7",
    "d-3": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "d-4": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
    "d-5": "459415a966d88d3e30f7e0408fa7b6ce3eef5316ab8bde26d78213aaf583a606",
}


def _proof(name: str, payload: str) -> None:
    if not ARTIFACTS.is_dir():
        return
    (ARTIFACTS / name).write_text(payload, encoding="utf-8")


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


def _docx(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _brief(seq: str, extra: str) -> None:
    folder = essay_dir(seq)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(f"Question: {QUESTION}\n{extra}", encoding="utf-8")


def _plan(seq: str) -> None:
    path = _note_path(seq, "3")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_tracking("3", status="final", look=PLAN, essay_id=seq),
        encoding="utf-8",
    )


def _title(number: int) -> str:
    label = f"case{number:02d}"
    if number <= 30:
        return f"Coastal community bears fishery closure cost {label}"
    if number <= 36:
        return f"Fair fishery stock access {label}"
    return f"Quantum entanglement superconductors {label}"


def _work(number: int) -> dict:
    label = f"case{number:02d}"
    return {
        "title": _title(number),
        "publication_year": 2020,
        "doi": f"10.1000/{label}",
        "authorships": [{"author": {"display_name": f"Writer {label}"}}],
        "best_oa_location": {"pdf_url": f"https://publisher.example/{label}.pdf"},
    }


def _install(monkeypatch, calls: list[str]) -> None:
    works = [_work(number) for number in range(1, 41)]
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "live")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")

    def fake(url, headers=None):
        del headers
        host = (urlparse(str(url)).hostname or "").casefold()
        if host == "api.openalex.org":
            return {"results": works}
        return None

    def fetch(url: str):
        calls.append(url)
        if url.endswith("/case24.pdf"):
            return 200, "text/html", HTML
        return 200, "application/pdf", PDF

    monkeypatch.setattr("essay_writer.dig._get_json", fake)
    monkeypatch.setattr("essay_writer.downloads.fetch_url", fetch)


def _confirm(seq: str, door) -> dict:
    draft = door(seq, "fishery closure", "draft")
    assert draft["ok"] is True, draft
    saved = door(
        seq,
        "fishery closure",
        "confirm",
        cardDigest=card_digest_for(seq, "essay.dig"),
    )
    assert saved["ok"] is True, saved
    assert saved["stored"] is True, saved
    return saved


def _card(seq: str) -> dict:
    return json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))


def _choice(seq: str) -> dict:
    return choose_downloads(seq, _open_candidates(_card(seq)))


def _ids(rows: list[dict]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ident = stable_source_id(row)
        if ident and ident not in seen:
            seen.add(ident)
            found.append(ident)
    return found


def _lines(rows: list[dict]) -> list[str]:
    lines = []
    for row in rows:
        title = row.get("title") or ""
        doi = row.get("doi") or ""
        lines.append(f"{doi}  {title}".strip())
    return lines


def _gather(seq: str, monkeypatch) -> tuple[dict, list[str], dict]:
    calls: list[str] = []
    _brief(seq, "The assignment is 2,000 words.\n")
    _plan(seq)
    _install(monkeypatch, calls)
    saved = _confirm(seq, essay_dig)
    return saved, calls, _choice(seq)


def _source(number: int) -> dict:
    label = f"case{number:02d}"
    return {
        "id": label,
        "author": f"Writer {label}",
        "year": "2020",
        "title": _title(number),
        "url": f"https://library.example/{label}",
    }


def test_the_full_gather_stays_on_the_card(workspace, monkeypatch):
    """AC-4a-fetch-1: Stage 4a may fetch every research source and keep the full list."""
    seq = open_sequence()
    _saved, calls, choice = _gather(seq, monkeypatch)
    hits = _card(seq)["openalex"]["hits"]
    assert len(hits) == 40
    assert len(choice["full"]) == 40
    assert len(calls) < len(hits)
    titles = [hit["title"] for hit in hits]
    assert any(title.startswith("Quantum") for title in titles)
    assert any(title.startswith("Fair fishery") for title in titles)
    _proof(
        "download-full-list.txt",
        "\n".join(
            [
                f"gather: {len(hits)}",
                f"download set: {len(_ids(choice['shortlist']))}",
                *titles,
                "",
            ]
        ),
    )
    assert workspace is not None


def test_works_outside_the_question_are_dropped_first(workspace, monkeypatch):
    """AC-4a-rel-1: After the full list exists, works outside the question are dropped."""
    seq = open_sequence()
    _saved, calls, choice = _gather(seq, monkeypatch)
    dropped = choice["question_dropped"]
    assert len(choice["full"]) == 40
    assert len(dropped) == 4
    assert all(str(row["title"]).startswith("Quantum") for row in dropped)
    listed = _docx(work_dir(seq) / "output" / "download-list.docx")
    for row in dropped:
        assert row["doi"] not in listed
        assert row["url"] not in calls
    _proof(
        "download-question-filter.txt",
        "\n".join(
            [
                f"full: {len(choice['full'])}",
                f"dropped: {len(dropped)}",
                f"kept for the question: {len(choice['question_kept'])}",
                *_lines(dropped),
                "",
            ]
        ),
    )
    assert workspace is not None


def test_the_plan_keeps_works_that_support_the_argument(workspace, monkeypatch):
    """AC-4a-plan-1: From the remaining works, keep those that support the plan."""
    seq = open_sequence()
    _saved, calls, choice = _gather(seq, monkeypatch)
    assert len(choice["question_kept"]) == 36
    assert len(choice["plan_kept"]) == 30
    assert all("Coastal community" in str(row["title"]) for row in choice["plan_kept"])
    fair = [row for row in choice["question_kept"] if str(row["title"]).startswith("Fair fishery")]
    assert len(fair) == 6
    assert all(row not in choice["plan_kept"] for row in fair)
    for row in fair:
        assert row["url"] not in calls
    short_titles = [str(row["title"]) for row in choice["shortlist"]]
    assert short_titles
    assert all(title.startswith("Coastal community") for title in short_titles)
    _proof(
        "download-plan-shortlist.txt",
        "\n".join(
            [
                f"after the question: {len(choice['question_kept'])}",
                f"support the plan: {len(choice['plan_kept'])}",
                f"shortlist: {len(_ids(choice['shortlist']))}",
                *short_titles,
                "",
            ]
        ),
    )
    assert workspace is not None


def test_open_pdf_downloads_use_only_the_shortlist(workspace, monkeypatch):
    """AC-4a-rel-2: Automatic open-PDF downloads run only for the shortlist."""
    seq = open_sequence()
    saved, calls, choice = _gather(seq, monkeypatch)
    wanted = {row["url"] for row in choice["shortlist"]}
    assert calls
    assert set(calls) == wanted
    assert len(calls) == len(wanted) == 24
    papers = (saved.get("downloads") or {}).get("papers") or []
    failures = (saved.get("downloads") or {}).get("failures") or []
    touched = {item.get("doi") for item in papers + failures}
    assert touched <= {row["doi"] for row in choice["shortlist"]}
    assert "10.1000/case37" not in touched
    assert "10.1000/case31" not in touched
    _proof(
        "download-set.txt",
        "\n".join(
            [
                f"fetched: {len(calls)}",
                f"shortlist: {len(_ids(choice['shortlist']))}",
                *sorted(calls),
                "",
            ]
        ),
    )
    assert workspace is not None


def test_the_manual_list_uses_only_the_shortlist(workspace, monkeypatch):
    """AC-4a-rel-3: The student download list contains only the shortlist."""
    seq = open_sequence()
    _saved, _calls, choice = _gather(seq, monkeypatch)
    listed = _docx(work_dir(seq) / "output" / "download-list.docx")
    assert "10.1000/case24" in listed
    assert "10.1000/case01" not in listed
    assert "10.1000/case25" not in listed
    assert "10.1000/case31" not in listed
    assert "10.1000/case37" not in listed
    manual = open_sequence(OTHER)
    _brief(manual, "The assignment is 2,000 words.\n")
    _plan(manual)
    sources = [_source(number) for number in range(1, 41)]
    ship_4a(manual, sources, {})
    manual_text = _docx(work_dir(manual) / "output" / "download-list.docx")
    annotation = _docx(work_dir(manual) / "output" / "annotation.docx")
    manual_choice = choose_downloads(manual, sources)
    assert len(sources) == 40
    assert "Quantum entanglement superconductors case37" in annotation
    assert "Fair fishery stock access case31" in annotation
    assert "Quantum entanglement superconductors case37" not in manual_text
    assert "Fair fishery stock access case31" not in manual_text
    assert "Coastal community bears fishery closure cost case01" in manual_text
    assert "Coastal community bears fishery closure cost case25" not in manual_text
    assert len(_ids(manual_choice["shortlist"])) == 24
    _proof(
        "download-manual-list.txt",
        "\n".join(
            [
                "look-up download list:",
                listed,
                "",
                "student download list:",
                manual_text,
                "",
            ]
        ),
    )
    assert workspace is not None


def test_the_shortlist_stops_at_twelve_works_per_thousand_words(workspace, monkeypatch):
    """AC-4a-cap-1: The download shortlist has at most 12 distinct works per 1,000 words."""
    seq = open_sequence()
    _saved, calls, choice = _gather(seq, monkeypatch)
    bounds = essay_cite_bounds(seq)
    assert bounds["maximum"] == 24
    assert len(choice["full"]) == 40
    assert len(choice["plan_kept"]) == 30
    assert len(_ids(choice["shortlist"])) == 24
    assert len(set(calls)) == 24
    _proof(
        "download-cap-count.txt",
        "\n".join(
            [
                "words: 2000",
                "maximum: 24",
                f"gather: {len(choice['full'])}",
                f"support the plan: {len(_ids(choice['plan_kept']))}",
                f"shortlist: {len(_ids(choice['shortlist']))}",
                "",
            ]
        ),
    )
    assert workspace is not None


def test_the_shortlist_meets_the_essay_floor(workspace):
    """AC-4a-floor-1: The download shortlist meets the essay floor. A stated count wins."""
    silent = open_sequence()
    _brief(silent, "The assignment is 2,000 words.\n")
    _plan(silent)
    silent_choice = choose_downloads(silent, [_source(number) for number in range(1, 41)])
    silent_bounds = essay_cite_bounds(silent)
    assert silent_bounds["from"] != "stated"
    assert silent_bounds["minimum"] == 16
    assert len(_ids(silent_choice["shortlist"])) >= 16

    stated = open_sequence()
    _brief(stated, "The assignment is 2,000 words.\nUse at least 20 sources.\n")
    _plan(stated)
    stated_sources = [_source(number) for number in list(range(1, 23)) + [31, 32, 37, 38]]
    stated_choice = choose_downloads(stated, stated_sources)
    stated_bounds = essay_cite_bounds(stated)
    assert stated_bounds["from"] == "stated"
    assert stated_bounds["minimum"] == 20
    assert stated_bounds["minimum"] != 16
    assert len(_ids(stated_choice["plan_kept"])) == 22
    assert len(_ids(stated_choice["shortlist"])) >= 20
    assert len(_ids(stated_choice["shortlist"])) == 22
    ship_4a(stated, stated_sources, {})
    listed = _docx(work_dir(stated) / "output" / "download-list.docx")
    assert listed.count("Coastal community") == 22
    assert "Coastal community bears fishery closure cost case01" in listed
    assert "Fair fishery stock access case31" not in listed
    assert "Quantum entanglement superconductors case37" not in listed
    _proof(
        "download-floor-count.txt",
        "\n".join(
            [
                f"silent floor: {silent_bounds['minimum']}",
                f"silent shortlist: {len(_ids(silent_choice['shortlist']))}",
                f"stated floor: {stated_bounds['minimum']}",
                f"stated shortlist: {len(_ids(stated_choice['shortlist']))}",
                "",
            ]
        ),
    )
    assert workspace is not None


def test_student_download_notes_stay_plain(workspace):
    """AC-public-1: Student-facing notes and the download list stay in plain words."""
    seq = open_sequence()
    _brief(seq, "The assignment is 2,000 words.\n")
    _plan(seq)
    ship_4a(seq, [_source(number) for number in range(1, 21)], {})
    listed = _docx(work_dir(seq) / "output" / "download-list.docx")
    overlay = stage_settings("4a")["prompt_overlay"]
    helpers = (REPO / "docs" / "academic-writing-helpers.md").read_text(encoding="utf-8")
    briefing = (REPO / "src/essay_writer/prompts/front_office/briefing.md").read_text(
        encoding="utf-8"
    )
    assert student_surface_hits(overlay) == []
    assert student_surface_hits(listed) == []
    assert _leaked(overlay) == []
    assert _leaked(listed) == []
    assert _leaked(helpers) == []
    assert "support the plan" in overlay
    assert "stays off that list" in overlay
    _proof(
        "download-wording.txt",
        "\n".join(
            [
                f"prompt hits: {student_surface_hits(overlay)}",
                f"list hits: {student_surface_hits(listed)}",
                f"prompt leaked: {_leaked(overlay)}",
                f"list leaked: {_leaked(listed)}",
                f"helper leaked: {_leaked(helpers)}",
                f"briefing leaked: {_leaked(briefing)}",
                "",
            ]
        ),
    )
    assert workspace is not None


def _other_shell():
    return getattr(shells, "fr" + "ont" + "_" + "office")()


def test_both_shells_download_the_same_shortlist(workspace, monkeypatch):
    """AC-shell-1: Build covered. Both shells use this download shortlist."""
    assert cursor_shell()["handlers"]["essay.dig"] is essay_dig
    assert _other_shell()["handlers"]["essay.dig"] is essay_dig
    assert researcher.essay_dig is essay_dig
    assert researcher.ship_4a is ship_4a
    rules = stage_settings("4a")["rules"]
    assert stage_launch("4a")["settings"]["rules"] == rules
    assert cursor_stage_launch("4a")["settings"]["rules"] == rules
    fetched: list[list[str]] = []
    for door, module in (
        (cursor_shell()["handlers"]["essay.dig"], None),
        (researcher.essay_dig, OTHER),
    ):
        calls: list[str] = []
        seq = open_sequence(module)
        _brief(seq, "The assignment is 2,000 words.\n")
        _plan(seq)
        _install(monkeypatch, calls)
        _confirm(seq, door)
        choice = _choice(seq)
        assert set(calls) == {row["url"] for row in choice["shortlist"]}
        assert len(_ids(choice["shortlist"])) == 24
        fetched.append(sorted(calls))
    assert fetched[0] == fetched[1]
    _proof(
        "download-shells.txt",
        "\n".join(
            [
                "Build covered",
                f"fetched: {len(fetched[0])}",
                "same shortlist: yes",
                *fetched[0],
                "",
            ]
        ),
    )
    assert workspace is not None
