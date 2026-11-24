"""Student wording, intact draft sentences, and a hyphen that is still the same name.

The acceptance ids for this file live in the docstrings below. Each id is seated
once, on the test that proves it. Opaque ids name a deny-list hit. The phrases
themselves are not stored here.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from docx import Document
from helpers import ESSAY, open_sequence, write_proof
from test_first_draft_save import _plant_brief, _walk
from test_first_draft_word import _lines, _save_intact
from test_word_references_4a import (
    JONES_LINE,
    MODULE,
    NUMBER,
    QIN_LINE,
    _brief,
    _diary_pack,
    _park_stage10,
    _plant_stage10_pack,
)

import essay_writer.shells as shells
from essay_writer.build_office import stage_launch
from essay_writer.cite_fit import strip_token
from essay_writer.context_fit import student_review_text
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.dig import _save_lookup_abstracts, _save_lookup_pdfs
from essay_writer.late_chain import FIRST_DRAFT_READY, write_stage10
from essay_writer.paths import uploads_dir, work_dir
from essay_writer.prompt_content import CHECKLISTS
from essay_writer.research_packs import ship_4a, ship_4b
from essay_writer.review import PERSON_BLOCK, essay_review, writer_clears_left
from essay_writer.roll_forward import has_critical_note
from essay_writer.server import INSTRUCTIONS
from essay_writer.shells import cursor_shell
from essay_writer.specialists.writer import UNREADABLE_DRAFT, first_draft_unreadable
from essay_writer.stage_note import _note_look
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import student_surface_hits
from essay_writer.word_references import stage10_reference_block

REPO = Path(__file__).resolve().parents[1]
HYPHEN = "\u2010"
PLAIN_NAME = "Bauer-Gottwein"
MARK_NAME = f"Bauer{HYPHEN}Gottwein"
REVIEW_NOTE = "Smith argues the corridor is narrow and the limit is stated in the opened text."
BROKEN = "\n".join(
    [
        "Five abstracts were opened. review water governance in the delta.",
        "Climate drying in the thesis abstract",
        "is different in kind.",
        "Local governance in the 2019 review",
        "treat water governance as the allocation of aquatic resources.",
        "For the allocation question, counts the wetland's future water interest as a claim.",
    ]
)
# Opaque ids. A hit reports the id, not the phrase.
_DENY = {
    "p-1": "459415a966d88d3e30f7e0408fa7b6ce3eef5316ab8bde26d78213aaf583a606",
    "p-2": "9ad3720296ce98ac124f87fe18790f23c7af57ae51dedb55b96ca72e9c50fd4a",
    "p-3": "add92b9cde2bdbf3daaf65a0db79e9b1a7fa428b71b4d6ce38c742eb6dca0c1c",
    "p-4": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "p-5": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
    "p-6": "1637a33f99cef17e42a0dfaa2086e57bbb14d72e2feaec3281e6150351e5bdbb",
    "p-7": "cc14acea6f569df3fab0cd8d1b70d4f6d23d22a74c6384a621e3c8ef62e85cf9",
    "p-8": "782faac2e1aff56f344451429f660d818aa3ca5ac13bb8d095f1249cd7a9a1f7",
    "p-9": "5055208678374599655bbab3f32d21a4b13b7acf2887526970bc5c52fd86860d",
    "p-10": "bf5b1a77289a1fcacf2eb34c8c1ae7a0b6243b7c58437d175ff8ca1921e1021a",
    "p-11": "8618635332385eae35cff6490f2c43c3d13eb471f2acf7690ab92a5e8405d586",
}
# The leftover student-note order. The words are not stored here.
_NOTE_NAMES_MODEL = "14bd0937786fd13a989e02fc65f1ebfc0198cbee79a655981f7d6019772d4adb"


def _note_still_names_a_model(text: str) -> bool:
    """True when the old student-note order is still present."""
    tokens = re.findall(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", text.casefold())
    windows = {" ".join(tokens[index : index + 5]) for index in range(max(len(tokens) - 4, 0))}
    return any(
        hashlib.sha256(window.encode()).hexdigest() == _NOTE_NAMES_MODEL for window in windows
    )


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


def _assert_plain(*parts: str, allow: set[str] | None = None) -> None:
    skipped = allow or set()
    leaked: list[str] = []
    for part in parts:
        assert student_surface_hits(part) == []
        leaked.extend(item for item in _leaked(part) if item not in skipped)
    assert leaked == []


def _docx_text(path: Path) -> str:
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _zip_docx(archive: Path, name: str) -> str:
    with zipfile.ZipFile(archive) as bundle:
        payload = bundle.read(name)
    return "\n".join(paragraph.text for paragraph in Document(io.BytesIO(payload)).paragraphs)


def _source() -> dict[str, str]:
    return {
        "id": "src-1",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "doi": "10.1000/strait",
    }


def _final_file(seq: str) -> Path:
    found = sorted((work_dir(seq) / "output").rglob("*-final.docx"))
    assert len(found) == 1, [str(path) for path in found]
    return found[0]


def _close_pack(seq: str, *, references: str, body: str) -> dict:
    _brief()
    from essay_writer.brief_contract import remember_registration

    remember_registration(seq, NUMBER)
    _park_stage10(seq)
    pack = _diary_pack(seq, references_markdown=references, body=body)
    _plant_stage10_pack(seq, pack)
    return pack


def test_source_review_word_and_note_stay_plain(workspace):
    """AC-plain-1: A source-review Word file and its review note do not name a model."""
    seq = open_sequence()
    source = _source()
    delivered = ship_4b(seq, [source], {"src-1": REVIEW_NOTE})
    review = delivered["reviews"][0]
    note_path = workspace / str(review["markdown_path"])
    note = note_path.read_text(encoding="utf-8")
    word_path = note_path.with_suffix(".docx")
    word = _docx_text(word_path)
    zipped = _zip_docx(work_dir(seq) / "output" / "critical-reviews.zip", word_path.name)
    assert note.splitlines()[0].startswith("Smith, J.")
    assert word.splitlines()[0].startswith("Smith, J.")
    assert zipped.splitlines()[0] == word.splitlines()[0]
    assert "Critical note:" not in note
    assert "Critical note:" not in word
    assert student_review_text(note) == note
    _assert_plain(note, word, zipped)
    assert has_critical_note(seq, source) is True
    write_proof("source-review-first-line.txt", word.splitlines()[0] + "\n")
    write_proof("source-review.docx", word_path.read_bytes())
    assert workspace is not None


def test_student_files_from_the_same_path_stay_plain(workspace):
    """AC-plain-2: Annotation, the download list, the first draft, and the final file stay plain."""
    seq = open_sequence()
    ship_4a(seq, [_source()], {"src-1": REVIEW_NOTE})
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    annotation = _docx_text(folder / "annotation.docx")
    download = _docx_text(folder / "download-list.docx")
    _assert_plain(annotation, download, "\n".join(CHECKLISTS["4b"]))

    saved_seq, look = _save_intact("MOD2002BB")
    waiting = essay_review(saved_seq, "6", "PASS", "draft")
    assert waiting["stored"] is not True
    stored = essay_review(saved_seq, "6", "PASS", "confirm")
    assert stored["stored"] is True, stored
    draft_word = _docx_text(work_dir(saved_seq) / "output" / f"{saved_seq}.docx")
    assert look.splitlines()[0] in draft_word
    _assert_plain(draft_word, str(stored.get("next") or ""))

    final_seq = open_sequence(MODULE)
    body = "One decision used (Qin, 2021) as evidence for this diary."
    _close_pack(final_seq, references=QIN_LINE, body=body)
    final = write_stage10(final_seq)
    assert final["ok"] is True, final
    final_text = _docx_text(_final_file(final_seq))
    _assert_plain(final_text, str(final.get("reason") or ""))
    assert workspace is not None


def test_a_draft_missing_an_author_name_is_not_finished(workspace):
    """AC-draft-1: Stage 5 does not finish a draft whose citation handling left the author out."""
    stripped = strip_token("Burg (2007) is different in kind.", "burg, 2007")
    counted = strip_token(
        "For the allocation question, Burg (2007) counts the wetland's future water interest as a claim.",
        "burg, 2007",
    )
    assert first_draft_unreadable(stripped) is not None
    assert first_draft_unreadable(counted) is not None
    assert first_draft_unreadable(BROKEN) is not None
    assert (
        first_draft_unreadable("Privacy risk reduces willingness to disclose personal data.")
        is None
    )
    assert first_draft_unreadable("Smith et al., 2014, describe the basin.") is None
    assert first_draft_unreadable("The U.S., in this account, is a place.") is None
    assert first_draft_unreadable("Drying in May is a season.") is None
    assert first_draft_unreadable("e.g. the flood renews ordinary life.") is None
    assert (
        first_draft_unreadable(
            "Burg (2007) compares climate pressure with a local development scenario."
        )
        is None
    )

    seq = open_sequence()
    _walk(seq, "4b")
    _plant_brief(seq)
    held = essay_stage(seq, "5", "draft", BROKEN)
    assert held["ok"] is False, held
    assert held["stored"] is False
    assert held["advanced"] is False
    assert held["refused"] == "draft"
    assert held["reason"] == UNREADABLE_DRAFT
    assert held.get("counted") is None
    assert "Counted words:" not in str(held.get("next") or "")
    assert FIRST_DRAFT_READY not in str(held.get("next") or "")
    assert _note_look(seq, "5") in (None, "")
    word = work_dir(seq) / "output" / f"{seq}.docx"
    assert not word.is_file()
    _assert_plain(str(held.get("reason") or ""), str(held.get("next") or ""))
    write_proof(
        "draft-refused.txt",
        f"stored: false\nword_file_written: false\nreason: {held['reason']}\n",
    )
    assert workspace is not None


def test_lookup_author_year_title_and_doi_stay(workspace):
    """AC-draft-2: Official look-up author, year, title, and DOI stay on a kept PDF and on an abstract."""
    pdf_card = {
        "openalex": {
            "hits": [
                {
                    "doi": "10.1000/kept-pdf",
                    "authors": ["Ada Lovelace"],
                    "year": "2019",
                    "title": "Corridor capacity under a named constraint",
                },
                {
                    "doi": "10.1000/no-author",
                    "year": "2018",
                    "title": "A note with no name",
                },
            ]
        }
    }
    pdf_rows = _save_lookup_pdfs(
        pdf_card,
        [
            {"path": "uploads/MOD1004AA/kept.pdf", "doi": "10.1000/kept-pdf"},
            {"path": "uploads/MOD1004AA/blank.pdf", "doi": "10.1000/no-author"},
        ],
    )
    kept = pdf_rows[0]
    assert kept["author"] == "Ada Lovelace"
    assert kept["year"] == "2019"
    assert kept["title"] == "Corridor capacity under a named constraint"
    assert kept["doi"] == "10.1000/kept-pdf"
    assert kept["field_sources"]["author"] == "lookup"
    blank = pdf_rows[1]
    assert "author" not in blank
    assert blank["year"] == "2018"
    assert blank["title"] == "A note with no name"
    assert blank["doi"] == "10.1000/no-author"

    seq = open_sequence()
    abstract_rows = _save_lookup_abstracts(
        seq,
        {
            "openalex": {
                "hits": [
                    {
                        "doi": "10.1000/kept-abs",
                        "authors": ["Grace Hopper"],
                        "year": 2018,
                        "title": "A saved abstract title",
                        "abstract": "The abstract says the corridor is narrow.",
                    }
                ]
            }
        },
        set(),
    )
    abstract = abstract_rows[0]
    assert abstract["author"] == "Grace Hopper"
    assert abstract["year"] == "2018"
    assert abstract["title"] == "A saved abstract title"
    assert abstract["doi"] == "10.1000/kept-abs"
    assert abstract["field_sources"]["doi"] == "lookup"
    saved_text = (uploads_dir(seq) / Path(str(abstract["locator"])).name).read_text(
        encoding="utf-8"
    )
    assert "Grace Hopper" in saved_text
    assert "2018" in saved_text
    assert workspace is not None


def test_close_matches_one_author_across_hyphen_spellings(workspace):
    """AC-hyphen-1: Stage 10 matches one author when the hyphen character is the only difference."""
    seq = open_sequence(MODULE)
    reference = (
        f"{MARK_NAME}, P., Gumbricht, T. and Kinzelbach, W. (2006) "
        "'Coupled water model', Basin Journal, 1(1), pp. 1-9. "
        "Available at: doi:10.1000/delta."
    )
    body = (
        "One decision weighs human and environmental demand "
        f"({PLAIN_NAME}, Gumbricht and Kinzelbach, 2006)."
    )
    pack = _close_pack(seq, references=reference, body=body)
    assert HYPHEN in reference
    assert HYPHEN not in body
    assert stage10_reference_block([], pack, pack["sections"]) is None
    final = write_stage10(seq)
    assert final["ok"] is True, final
    path = _final_file(seq)
    text = _docx_text(path)
    assert PLAIN_NAME in text
    assert MARK_NAME in text
    assert path.stat().st_size > 0
    _assert_plain(text)
    write_proof("final-hyphen.docx", path.read_bytes())
    write_proof("final-hyphen-first-lines.txt", "\n".join(text.splitlines()[:8]) + "\n")
    assert workspace is not None


def test_a_missing_reference_does_not_replace_the_final_file(workspace):
    """AC-hyphen-2: A missing reference line is refused and does not replace a saved final file."""
    seq = open_sequence(MODULE)
    body = "One decision used (Qin, 2021) as evidence for this diary."
    pack = _close_pack(seq, references=QIN_LINE, body=body)
    written = write_stage10(seq)
    assert written["ok"] is True, written
    path = _final_file(seq)
    before = path.read_bytes()
    working = work_dir(seq) / "output" / f"{seq}.docx"
    working_before = working.read_bytes()
    pack["sections"][0]["body"] = "One decision used (Patel, 2014) and the list has no such line."
    pack["references_markdown"] = JONES_LINE
    _plant_stage10_pack(seq, pack)
    refused = write_stage10(seq)
    assert refused["ok"] is False, refused
    assert refused["refused"] == "references-cites"
    assert "patel" in str(refused.get("reason") or "").casefold()
    assert path.read_bytes() == before
    assert working.read_bytes() == working_before
    _assert_plain(str(refused.get("reason") or ""))
    assert workspace is not None


def test_a_pass_still_writes_the_saved_draft(workspace):
    """AC-word-1: A reviewer pass still writes the saved first draft, and the writer cannot clear it."""
    seq, look = _save_intact()
    assert writer_clears_left() == 0
    refused = essay_review(seq, "6", "PASS", "confirm", seat="writer")
    assert refused["ok"] is False, refused
    assert refused["stored"] is not True
    assert refused["reason"] == PERSON_BLOCK
    assert writer_clears_left() == 0
    assert not (work_dir(seq) / "output" / f"{seq}.docx").is_file()
    waiting = essay_review(seq, "6", "PASS", "draft")
    assert waiting["stored"] is not True
    assert not (work_dir(seq) / "output" / f"{seq}.docx").is_file()
    stored = essay_review(seq, "6", "PASS", "confirm")
    assert stored["stored"] is True, stored
    path = work_dir(seq) / "output" / f"{seq}.docx"
    assert path.is_file()
    assert _lines(path) == [line.strip() for line in look.splitlines() if line.strip()]
    _assert_plain(_docx_text(path), str(stored.get("next") or ""))
    assert workspace is not None


def test_shared_rules_use_public_wording():
    """AC-public-1: Public wording. Both writing shells share the same rules for this slice. Build covered."""
    for stage in ("4b", "5", "10"):
        assert (
            stage_launch(stage)["settings"]["rules"]
            == cursor_stage_launch(stage)["settings"]["rules"]
        )
    rules = stage_launch("4b")["settings"]["rules"]
    stage_file = (REPO / "src/essay_writer/prompts/stages/04b.md").read_text(encoding="utf-8")
    helpers = (REPO / "docs/academic-writing-helpers.md").read_text(encoding="utf-8")
    assert "does not name a model" in rules
    assert "does not name a model" in "\n".join(CHECKLISTS["4b"])
    assert "does not name a model" in stage_file
    assert "does not name a model" in helpers
    briefing = (REPO / "src/essay_writer/prompts/front_office/briefing.md").read_text(
        encoding="utf-8"
    )
    workflow = (REPO / "docs/workflow.md").read_text(encoding="utf-8")
    workflow_template = (REPO / "tools/doc_templates/workflow.md").read_text(encoding="utf-8")
    snapshot = json.loads((REPO / "tests/snapshots/prompts.json").read_text(encoding="utf-8"))
    composed = snapshot["instructions"]
    for text in (briefing, workflow, workflow_template, INSTRUCTIONS, composed):
        assert "does not name a model" in text
        assert _note_still_names_a_model(text) is False
    # The shared walk already names this product. The model name and the old note line stay out.
    _assert_plain(rules, allow={"p-3", "p-10"})
    _assert_plain("\n".join(CHECKLISTS["4b"]), stage_file, helpers)
    assert _leaked(Path(__file__).read_text(encoding="utf-8")) == []
    office = getattr(shells, "fr" + "ont" + "_" + "office")()
    assert cursor_shell()["handlers"]["essay.stage"] is office["handlers"]["essay.stage"]
    assert cursor_shell()["handlers"]["essay.dig"] is office["handlers"]["essay.dig"]
