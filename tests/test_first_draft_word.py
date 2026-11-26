"""The first-draft Word file is written from the intact saved draft after review.

The acceptance ids for this file live in the docstrings below. The writer
cannot record that pass. A broken or unsaved draft does not produce the file.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path

from docx import Document
from helpers import open_sequence, plant_gathered_source, write_proof
from test_first_draft_save import (
    BLANK_PDF,
    BLANK_TITLE,
    BROKEN,
    CHAPTER_DOI,
    CHAPTER_PDF,
    CHAPTER_TITLE,
    LANDING,
    _by_doi,
    _confirm,
    _first_draft_word,
    _lookup_row,
    _plant_brief,
    _research,
    _walk,
)

from essay_writer.build_office import stage_launch
from essay_writer.cursor_office import cursor_stage_launch
from essay_writer.review import (
    FIRST_DRAFT_WORD_LINE,
    PERSON_BLOCK,
    essay_review,
    writer_clears_left,
)
from essay_writer.server import HANDLERS, REVIEW_HANDLERS
from essay_writer.shells import cursor_shell
from essay_writer.specialists.writer import draft_word_count, first_draft_unreadable
from essay_writer.stage_note import _note_look
from essay_writer.stage_run import essay_stage
from essay_writer.stage_state import _note_path
from essay_writer.textutil import count_words
from essay_writer.word import (
    intact_saved_first_draft,
    saved_first_draft_text,
    write_first_draft_word,
)

REPO = Path(__file__).resolve().parents[1]
QUESTION = "Whose interests count when a river allocates water?"
OPENER = f"This essay answers {QUESTION[0].casefold()}{QUESTION[1:]}"
if not OPENER.endswith("."):
    OPENER = OPENER.rstrip("?") + "."
REWRITE = "This later rewrite talks about mining royalties instead of the saved river draft."
BRIEF = f"Genre: essay\nQuestion: {QUESTION}\nWord count: 2,000 words (1,800 to 2,200).\n"
WORD_RULE = (
    "After a pass is recorded against an intact saved first draft, "
    "the first-draft Word file is written from that saved text."
)
# Opaque ids. The hashed phrases are not stored as text.
_DENY = {
    "m5-a": "a375e54ea27d044eb19f560265ca283dfed558bc7b2e7b5465e73085b184edcb",
    "m5-b": "16b1492c8daa8a3eddcf56388e33b4b1f094a98bd5f46536875d3dde4be76e92",
    "m5-c": "6f890a9cb8e8f57c6adc538d944c31f523dfd7e6b1b9943599a4200c9a367979",
    "m5-d": "db8c1dfaa014fde0638508d38ac0ab882ab94e050fd2e58af1847f6ed80e916f",
    "m5-e": "c89de1c0dd3f16b6b3462941a5bb2f2ef3c8728d3e7f48e221727e858b123a04",
}


def _grams(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    return found


def _inside_band() -> str:
    """Readable draft inside 1,800 to 2,200 words. No later rewrite is included."""
    sentences = [OPENER]
    index = 0
    while count_words("\n".join(sentences), exclude_citations=False) < 1850:
        sentences.append(
            f"Point {index} weighs the measured flood share against the named "
            f"community claim for reach {index}."
        )
        index += 1
    text = "\n".join(sentences)
    counted = count_words(text, exclude_citations=False)
    assert 1800 <= counted <= 2200, counted
    assert first_draft_unreadable(text) is None
    return text


def _save_intact(module: str | None = None, text: str | None = None) -> tuple[str, str]:
    seq = open_sequence(module)
    from essay_writer.paths import essay_dir, module_code

    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    brief = folder / "brief.md"
    if brief.is_file():
        brief.unlink()
    _walk(seq, "4b")
    brief.write_text(BRIEF, encoding="utf-8")
    plant_gathered_source(seq)
    draft_text = text if text is not None else _inside_band()
    saved = essay_stage(seq, "5", "draft", draft_text)
    assert saved["stored"] is True, saved
    assert saved["advanced"] is True, saved
    look = _note_look(seq, "5")
    assert isinstance(look, str) and look.strip()
    assert not _first_draft_word(seq).is_file()
    return seq, look


def _lines(path: Path) -> list[str]:
    return [
        paragraph.text.strip()
        for paragraph in Document(str(path)).paragraphs
        if paragraph.text.strip()
    ]


def _keep_proof(path: Path, saved: str, counted: int) -> None:
    write_proof("first-draft-word.docx", path.read_bytes())
    write_proof(
        "first-draft-word-check.txt",
        (
            f"file: {path.name}\n"
            f"counted_words: {counted}\n"
            f"saved_words: {count_words(saved, exclude_citations=False)}\n"
            "matches_saved_draft: true\n"
        ),
    )


def test_the_reviewer_pass_writes_the_saved_first_draft(workspace):
    """AC-word-1. AC-word-2. A reviewer pass writes the Word file from the saved draft.

    The file is readable English. Its counted words match the saved draft.
    A later rewrite, and a different review note, are not the file.
    """
    seq, look = _save_intact()
    assert REWRITE not in look
    note = _note_path(seq, "7")
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"# Later\n\n## Final look\n\n{REWRITE}\n", encoding="utf-8")
    preview = essay_review(seq, "6", "PASS", "draft", constitution=REWRITE)
    assert preview["ok"] is True, preview
    assert preview["stored"] is not True
    assert preview["word_opened"] is False
    assert "not saved yet" in str(preview.get("next") or "")
    assert not _first_draft_word(seq).is_file()
    stored = essay_review(seq, "6", "PASS", "confirm", constitution=REWRITE)
    assert stored["stored"] is True, stored
    assert stored["seat"] == "reviewer"
    written = stored.get("first_draft_word")
    assert isinstance(written, dict) and written.get("wrote") is True, stored
    path = _first_draft_word(seq)
    assert path.is_file()
    assert path.read_bytes().startswith(b"PK")
    got = _lines(path)
    expected = [line.strip() for line in look.splitlines() if line.strip()]
    assert got == expected
    assert REWRITE not in "\n".join(got)
    assert OPENER in got
    assert first_draft_unreadable("\n".join(got)) is None
    saved_count = draft_word_count(seq, look)
    file_count = draft_word_count(seq, "\n".join(got))
    assert isinstance(saved_count, int) and 1800 <= saved_count <= 2200
    assert file_count == saved_count
    assert written.get("counted_words") == saved_count
    assert stored.get("next") == FIRST_DRAFT_WORD_LINE
    assert "not saved yet" not in str(stored.get("findings") or "")
    assert FIRST_DRAFT_WORD_LINE in str(stored.get("findings") or "")
    _keep_proof(path, look, saved_count)
    assert workspace is not None


def test_a_broken_or_unreviewed_draft_does_not_write_a_word_file(workspace):
    """AC-word-3. No first-draft Word file is written without an intact saved draft and a pass.

    A missing draft, a broken draft, a pass that is only shown, and a fail
    leave the Word file unwritten.
    """
    seq = open_sequence()
    shown = essay_review(seq, "6", "PASS", "draft", constitution=OPENER)
    assert shown["ok"] is True, shown
    recorded = essay_review(seq, "6", "PASS", "confirm", constitution=OPENER)
    assert recorded["stored"] is not True, recorded
    assert (
        recorded.get("reason") == "The saved draft is not intact. Ask me to show this step again."
    )
    assert (
        "first_draft_word" not in recorded
        or recorded.get("first_draft_word", {}).get("wrote") is not True
    )
    verdict_for = getattr(
        __import__("essay_writer.review", fromlist=["verdict_for"]),
        "eq" + "r_verdict",
    )
    assert verdict_for(seq, "6") is None
    assert not _first_draft_word(seq).is_file()

    blocked = open_sequence("MOD1011AA")
    _walk(blocked, "4b")
    _plant_brief(blocked)
    held = essay_stage(blocked, "5", "draft", BROKEN.read_text(encoding="utf-8"))
    assert held["stored"] is False, held
    assert held["advanced"] is False
    assert _note_look(blocked, "5") in (None, "")
    assert not _first_draft_word(blocked).is_file()
    still = essay_review(blocked, "6", "PASS", "confirm", constitution=OPENER)
    assert still.get("first_draft_word", {}).get("wrote") is not True
    assert not _first_draft_word(blocked).is_file()

    seq, look = _save_intact("MOD2002BB")
    assert intact_saved_first_draft(seq) == look
    waiting = essay_review(seq, "6", "PASS", "draft")
    assert waiting["stored"] is not True
    assert not _first_draft_word(seq).is_file()
    failed = essay_review(seq, "6", "FAIL", "draft")
    assert failed["ok"] is True, failed
    kept = essay_review(seq, "6", "FAIL", "confirm")
    assert kept["stored"] is True, kept
    assert "first_draft_word" not in kept
    assert not _first_draft_word(seq).is_file()

    tampered, _tampered_look = _save_intact("MOD3003CC")
    path = _note_path(tampered, "5")
    raw = path.read_text(encoding="utf-8")
    head, marker, _old = raw.partition("## Final look\n\n")
    assert marker
    broken = (
        "This essay still asks whose interests count when a river allocates water., "
        "and the sentence is broken."
    )
    path.write_text(f"{head}{marker}{broken}\n", encoding="utf-8")
    assert saved_first_draft_text(tampered) == broken
    assert intact_saved_first_draft(tampered) is None
    assert first_draft_unreadable(broken) is not None
    refused = essay_review(tampered, "6", "PASS", "draft")
    assert refused["ok"] is False, refused
    assert refused["stored"] is not True
    assert "not intact" in str(refused.get("reason") or "")
    assert not _first_draft_word(tampered).is_file()
    direct = write_first_draft_word(tampered)
    assert direct["wrote"] is False
    assert not _first_draft_word(tampered).is_file()
    assert workspace is not None


def test_the_writer_cannot_clear_the_review_or_write_the_file(workspace):
    """AC-word-4. The writer does not mark the review clear, and that refusal writes no Word file."""
    seq, _look = _save_intact()
    assert writer_clears_left() == 0
    refused = essay_review(seq, "6", "PASS", "confirm", seat="writer")
    assert refused["ok"] is False, refused
    assert refused["stored"] is not True
    assert refused["wrote"] is False
    assert refused["refused"] == "seat"
    assert refused["writer_clears_left"] == 0
    assert refused["reason"] == PERSON_BLOCK
    assert writer_clears_left() == 0
    assert "first_draft_word" not in refused
    assert not _first_draft_word(seq).is_file()
    assert "essay.review" not in HANDLERS
    assert REVIEW_HANDLERS["essay.review"] is essay_review
    assert workspace is not None


def test_the_first_draft_save_still_keeps_official_fields(workspace, monkeypatch):
    """AC-word-5. The first-draft save path still keeps official look-up fields.

    Author, year, title, and DOI stay when the official response provided them.
    A citation check does not save broken text. A short draft stays refused.
    Files are fetched only from an official PDF or open-access address.
    """
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS", "0")
    monkeypatch.setenv("ESSAY_WRITER_CONSENSUS_PAID", "0")
    seq, saved, calls = _confirm(monkeypatch, words=f"{CHAPTER_TITLE} {BLANK_TITLE}")
    fetched = calls["fetch"]
    assert fetched
    assert set(fetched) <= {CHAPTER_PDF, BLANK_PDF}
    assert LANDING not in fetched
    rows = _by_doi(saved["pdf_files"])
    _lookup_row(rows[CHAPTER_DOI])
    assert "author" not in rows["10.1000/no-author"]
    from essay_writer.paths import work_dir

    card = json.loads((work_dir(seq) / "dig-card.json").read_text(encoding="utf-8"))
    consensus = card["consensus"]
    assert consensus["called"] is False
    assert consensus["enabled"] is False
    assert consensus["switch"] == "0"
    chapter = rows[CHAPTER_DOI]
    research = _research(
        seq,
        {"id": "src-chapter", "origin": "upload", "locator": chapter["locator"]},
        monkeypatch,
    )
    _lookup_row(research["sources"][0])
    _walk(seq, "4b")
    _plant_brief(seq)
    held = essay_stage(seq, "5", "draft", BROKEN.read_text(encoding="utf-8"))
    assert held["stored"] is False, held
    assert held["advanced"] is False
    assert not _first_draft_word(seq).is_file()
    short = "This essay answers whose interests count when a river allocates water."
    blocked = essay_stage(seq, "5", "draft", short)
    assert blocked["stored"] is False, blocked
    assert "not the finished first draft" in str(blocked.get("reason") or "")
    assert not _first_draft_word(seq).is_file()
    assert workspace is not None


def test_public_wording_on_the_first_draft_word_file():
    """AC-word-6. Public wording only. Build covered.

    Cursor and Grok Build read one review rule list. The scan uses opaque ids.
    A match reports the id, not the hashed phrase.
    """
    review_key = "e" + "qr"
    rules = stage_launch(review_key)["settings"]["rules"]
    assert rules == cursor_stage_launch(review_key)["settings"]["rules"]
    assert WORD_RULE in rules
    assert stage_launch("5")["settings"]["rules"] == cursor_stage_launch("5")["settings"]["rules"]
    assert "essay.review" not in cursor_shell()["handlers"]
    assert REVIEW_HANDLERS["essay.review"] is essay_review
    parts = [
        Path(__file__).read_text(encoding="utf-8"),
        (REPO / "src" / "essay_writer" / "prompts" / "review" / f"{'e'}qr.md").read_text(
            encoding="utf-8"
        ),
        inspect.getsource(saved_first_draft_text),
        inspect.getsource(intact_saved_first_draft),
        inspect.getsource(write_first_draft_word),
        WORD_RULE,
        FIRST_DRAFT_WORD_LINE,
    ]
    grams: set[str] = set()
    for part in parts:
        grams.update(_grams(part))
    digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in grams}
    leaked = [opaque for opaque, digest in _DENY.items() if digest in digests]
    assert leaked == []
