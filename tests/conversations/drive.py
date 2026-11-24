"""Five student paths. Each one calls the real doors through a fake shell.

A prompt change that alters a student reply updates the matching path.
The fixtures are synthetic. Resolvers stay off, so no catalog is contacted.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from conversations.fixtures import (
    AUTHOR,
    BRIEF,
    BROKEN_DRAFT,
    DRAFT,
    FINAL_SENTENCE,
    MODULE,
    QUESTION,
    REVIEW,
    STAGE_LOOK,
    TITLE,
    TOPIC,
    UPLOAD,
    YEAR,
)
from conversations.shell import FakeShell
from essay_writer.paths import module_code, work_dir
from essay_writer.specialists.writer import UNREADABLE_DRAFT


def source_row(module: str = MODULE) -> dict[str, str]:
    return {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{module}/smith.md",
        "author": AUTHOR,
        "year": YEAR,
        "title": TITLE,
        "quote": "The passage handles a large share of coastal trade.",
    }


def _root() -> Path:
    raw = os.environ.get("ESSAY_WRITER_ROOT", "").strip()
    if not raw:
        raise RuntimeError("ESSAY_WRITER_ROOT is not set")
    return Path(raw)


def _prepare_uploads(module: str = MODULE) -> None:
    folder = _root() / "uploads" / module
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "smith.md").write_text(UPLOAD, encoding="utf-8")


def _write_brief(seq: str) -> None:
    from essay_writer.paths import essay_dir

    folder = essay_dir(module_code(seq))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")


def open_sequence(shell: FakeShell, module: str = MODULE) -> str:
    draft = shell.call("essay.sequence.new", module=module, confirmPhase="draft")
    if draft.get("ok") is not True:
        raise AssertionError(draft)
    opened = shell.call("essay.sequence.new", module=MODULE, confirmPhase="confirm")
    if opened.get("ok") is not True:
        raise AssertionError(opened)
    seq = opened.get("sequence_id")
    if not isinstance(seq, str) or not seq:
        raise AssertionError(opened)
    return seq


def _confirm_digest(seq: str, tool: str, draft: dict[str, Any]) -> str:
    shown = draft.get("cardDigest")
    if isinstance(shown, str) and shown:
        return shown
    from essay_writer.confirm import latest_draft

    record = latest_draft(seq, tool)
    if isinstance(record, dict) and isinstance(record.get("cardDigest"), str):
        return record["cardDigest"]
    digest = draft.get("digest")
    if isinstance(digest, str):
        return digest
    raise AssertionError(draft)


def gather_and_list(shell: FakeShell, seq: str) -> dict[str, Any]:
    """File the synthetic source, then confirm the citation list."""
    _prepare_uploads(module_code(seq))
    _write_brief(seq)
    row = source_row(module_code(seq))
    summary = shell.call(
        "essay.research.summary",
        essay_id=seq,
        topic=TOPIC,
        confirmPhase="draft",
        sources=[row],
    )
    if summary.get("ok") is not True:
        return summary
    stored = shell.call(
        "essay.research.summary",
        essay_id=seq,
        topic=TOPIC,
        confirmPhase="confirm",
        sources=[row],
        cardDigest=_confirm_digest(seq, "essay.research.summary", summary),
    )
    if stored.get("stored") is not True:
        return stored
    reviews = [{"paper_id": "src-1", "markdown": REVIEW}]
    clarify = {
        "objective": {"leave_open": True},
        "background": {"leave_open": True},
        "issues": {"leave_open": True},
        "guidance": {"leave_open": True},
    }
    full = shell.call(
        "essay.research.full",
        essay_id=seq,
        topic=TOPIC,
        confirmPhase="draft",
        sources=[row],
        clarify_context=clarify,
        reviews=reviews,
    )
    if full.get("ok") is not True:
        return full
    confirmed = shell.call(
        "essay.research.full",
        essay_id=seq,
        topic=TOPIC,
        confirmPhase="confirm",
        sources=[row],
        clarify_context=clarify,
        reviews=reviews,
        cardDigest=_confirm_digest(seq, "essay.research.full", full),
    )
    return confirmed


def citation_list_path(seq: str) -> Path:
    return work_dir(seq) / "citation-list.json"


def output_dir(seq: str) -> Path:
    return work_dir(seq) / "output"


def docx_text(path: Path) -> str:
    from docx import Document

    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def walk_through(shell: FakeShell, seq: str, stop: str) -> dict[str, Any]:
    """Save each stage through ``stop`` with one student sentence."""
    from essay_writer.writing_basics import STAGE_ORDER

    last: dict[str, Any] = {}
    for stage in STAGE_ORDER:
        look = f"{STAGE_LOOK} Stage {stage} keeps this sentence."
        draft = shell.call(
            "essay.stage",
            essay_id=seq,
            stage=stage,
            confirmPhase="draft",
            look=look,
        )
        if draft.get("ok") is not True:
            return draft
        last = shell.call(
            "essay.stage",
            essay_id=seq,
            stage=stage,
            confirmPhase="confirm",
            look=look,
            cardAction="confirm",
            cardDigest=draft.get("digest"),
        )
        if last.get("stored") is not True:
            return last
        if stage == stop:
            return last
    return last


def first_draft(shell: FakeShell, seq: str) -> dict[str, Any]:
    reached = walk_through(shell, seq, "4b")
    if reached.get("stored") is not True:
        return reached
    saved = shell.call(
        "essay.stage",
        essay_id=seq,
        stage="5",
        confirmPhase="draft",
        look=DRAFT,
    )
    return saved


def review_first_word(shell: FakeShell, seq: str) -> dict[str, Any]:
    shown = shell.call(
        "essay.review",
        essay_id=seq,
        stage="6",
        verdict="PASS",
        confirmPhase="draft",
        constitution=DRAFT,
    )
    if shown.get("ok") is not True:
        return shown
    return shell.call(
        "essay.review",
        essay_id=seq,
        stage="6",
        verdict="PASS",
        confirmPhase="confirm",
        constitution=DRAFT,
    )


def park_at_stage10(seq: str) -> None:
    """The pointer a finished stage 9 leaves. The shell then calls stage 10."""
    from essay_writer.stage_state import load_pointer

    pointer = load_pointer(seq)
    pointer["current"] = "10"
    pointer["saved"] = ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9"]
    pointer["closed"] = False
    pointer["chain_armed"] = False
    pointer["waiting_stage"] = None
    pointer["waiting_digest"] = None
    path = work_dir(seq) / "tracking" / "stage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")


def store_final_pack(seq: str) -> None:
    """The pack a confirmed validate leaves for the stage 10 door."""
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    state["saved_pack"] = {
        "essay_id": seq,
        "title": "Ports and coastal trade",
        "referencing": "harvard",
        "assessment": "Individual essay",
        "conclusion": "noted",
        "sections": [{"heading": "Notes", "body": FINAL_SENTENCE}],
        "references_markdown": (
            "Smith, J. (2020) 'Chokepoints and crude', Maritime Policy, 12(3), pp. 4-9. "
            "Available at: doi:10.1000/strait."
        ),
    }
    save_state(seq, state)


def final_word(shell: FakeShell, seq: str) -> dict[str, Any]:
    from essay_writer.specialists.grok_bot import basics_pass_lines

    store_final_pack(seq)
    park_at_stage10(seq)
    look = "\n".join(basics_pass_lines(seq)) + "\nThe final file is ready."
    draft = shell.call(
        "essay.stage",
        essay_id=seq,
        stage="10",
        confirmPhase="draft",
        look=look,
    )
    if draft.get("ok") is not True:
        return draft
    return shell.call(
        "essay.stage",
        essay_id=seq,
        stage="10",
        confirmPhase="confirm",
        look=look,
        cardAction="confirm",
        cardDigest=draft.get("digest"),
    )


def missing_question(shell: FakeShell, seq: str) -> dict[str, Any]:
    return shell.call("essay.dig", essay_id=seq, query=QUESTION, confirmPhase="draft")


def unreadable_draft(shell: FakeShell, seq: str) -> dict[str, Any]:
    gathered = gather_and_list(shell, seq)
    if gathered.get("stored") is not True:
        return gathered
    reached = walk_through(shell, seq, "4b")
    if reached.get("stored") is not True:
        return reached
    return shell.call(
        "essay.stage",
        essay_id=seq,
        stage="5",
        confirmPhase="draft",
        look=BROKEN_DRAFT,
    )


def _fresh_root():
    """One student folder. A later path does not inherit this folder's saves."""
    from essay_writer.build_status import reset_status

    root = Path(tempfile.mkdtemp(prefix="essay-conversations-"))
    os.environ["ESSAY_WRITER_ROOT"] = str(root)
    os.environ["ESSAY_WRITER_RESOLVERS"] = "off"
    for name in (
        "CONSENSUS_API_KEY",
        "OPENALEX_API_KEY",
        "ESSAY_WRITER_UNPAYWALL_EMAIL",
        "ESSAY_WRITER_CONSENSUS",
        "ESSAY_WRITER_CONSENSUS_PAID",
    ):
        os.environ.pop(name, None)
    (root / "uploads").mkdir()
    (root / "Essay-writer").mkdir()
    reset_status()
    return root


def run_all() -> list[str]:
    """Run the five paths. Each path gets its own folder. Returns the student lines."""
    lines: list[str] = []
    folders: list[Path] = []
    try:
        folders.append(_fresh_root())
        other = FakeShell()
        bare = open_sequence(other)
        missing = missing_question(other, bare)
        if missing.get("ok") is not False:
            raise SystemExit("missing question was not refused")
        lines.append(other.student_line(missing))

        folders.append(_fresh_root())
        shell = FakeShell()
        seq = open_sequence(shell)
        gathered = gather_and_list(shell, seq)
        if gathered.get("stored") is not True:
            raise SystemExit(f"gather failed: {gathered.get('reason')}")
        lines.append(shell.student_line(gathered))
        drafted = first_draft(shell, seq)
        if drafted.get("stored") is not True:
            raise SystemExit(f"draft failed: {drafted.get('reason')}")
        lines.append(shell.student_line(drafted))
        reviewed = review_first_word(shell, seq)
        if reviewed.get("stored") is not True:
            raise SystemExit(f"review failed: {reviewed.get('reason')}")
        lines.append(shell.student_line(reviewed))
        finished = final_word(shell, seq)
        if finished.get("stored") is not True:
            raise SystemExit(f"final word failed: {finished.get('reason')}")
        lines.append(shell.student_line(finished))

        folders.append(_fresh_root())
        broken_shell = FakeShell()
        broken_seq = open_sequence(broken_shell)
        broken = unreadable_draft(broken_shell, broken_seq)
        if broken.get("reason") != UNREADABLE_DRAFT:
            raise SystemExit(
                "unreadable draft was not refused: "
                + str(broken.get("reason") or broken.get("next") or broken.get("ok"))
            )
        lines.append(broken_shell.student_line(broken))
    finally:
        for folder in folders:
            shutil.rmtree(folder, ignore_errors=True)
    return lines
