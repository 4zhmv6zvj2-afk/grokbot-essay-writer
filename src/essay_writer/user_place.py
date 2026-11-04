"""User-facing place for a Word file.

Student chat says Grok Bot chat delivery, or a folder the student already
named. Volume, internal, and ~/ paths are not said. Stage 6 uses this
same place. A missing or renamed draft is a question, not a guess.
"""

from __future__ import annotations

from pathlib import Path

from essay_writer.paths import _refuse_internal_volume, module_code, student_chat_path, work_dir

CHAT_PLACE = "Grok Bot chat delivery"
NAMED_PLACE = "a folder the student already named"
# Stage 4a writes these beside the essay. They are not master-copy choices.
BIBLIOGRAPHY_DOCX = frozenset({"annotation.docx", "download-list.docx"})


def chat_place(named_folder: str | None = None) -> str:
    """Place wording for student chat. No internal volume path."""
    if not isinstance(named_folder, str) or not named_folder.strip():
        return CHAT_PLACE
    raw = named_folder.strip()
    try:
        candidate = Path(raw).expanduser()
    except OSError:
        return NAMED_PLACE
    if _refuse_internal_volume(candidate):
        return NAMED_PLACE
    spoken = student_chat_path(raw)
    if not spoken or _refuse_internal_volume(Path(spoken)):
        return NAMED_PLACE
    if spoken == "a folder you named on this computer":
        return NAMED_PLACE
    return spoken


def _folder(raw: str | None) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        candidate = Path(raw.strip()).expanduser()
    except OSError:
        return None
    if _refuse_internal_volume(candidate):
        return None
    if candidate.is_dir():
        return candidate
    return None


def _docx_names(folder: Path | None) -> list[str]:
    if folder is None or not folder.is_dir():
        return []
    names = [
        path.name
        for path in folder.iterdir()
        if path.is_file() and not path.name.startswith(".") and path.suffix.lower() == ".docx"
    ]
    return sorted(names)


def expected_draft_name(essay_id: str) -> str:
    return f"{essay_id}.docx"


def master_word(
    essay_id: str,
    *,
    master: str | None = None,
    named_folder: str | None = None,
) -> dict[str, object]:
    """Stage 6 first read. Do not pick a Word file the person did not name."""
    place = chat_place(named_folder)
    output = work_dir(essay_id) / "output"
    expected = expected_draft_name(essay_id)
    present = _docx_names(output)
    named = _folder(named_folder)
    if named is not None:
        for name in _docx_names(named):
            if name not in present:
                present.append(name)
        present.sort()
    present = [name for name in present if name.casefold() not in BIBLIOGRAPHY_DOCX]
    expected_here = expected in present or (output / expected).is_file()
    named_master = master.strip() if isinstance(master, str) else ""
    if named_master:
        named_master = Path(named_master).name
    chosen = named_master if named_master and named_master in present else ""
    if expected_here and not chosen:
        chosen = expected
    others = [name for name in present if name != expected]
    missing_or_renamed = not expected_here
    block = False
    if missing_or_renamed and not chosen:
        if others or named is not None or (isinstance(named_folder, str) and named_folder.strip()):
            block = True
    ask = missing_or_renamed and not chosen
    return {
        "place": place,
        "expected": expected,
        "expected_present": expected_here,
        "master_ask": ask,
        "block_confirm": block,
        "choices": others if ask else [],
        "master": chosen,
    }


def finished_word_copies(essay_id: str, *, documents: Path | None = None) -> list[dict[str, object]]:
    """The Word file the student receives, and the Documents copy when that file is already there.

    Known paths only. This does not search Documents.
    """
    from essay_writer.late_chain import documents_root, final_place

    copies: list[dict[str, object]] = []
    student = work_dir(essay_id) / "output" / f"{essay_id}.docx"
    if student.is_file():
        copies.append({"role": "student", "place": "the saved Word file", "path": student})
    root = documents_root(documents)
    if root is None:
        return copies
    project = module_code(essay_id)
    from essay_writer.first_run import sequence_mac_deliverables_dir

    seq_mac = sequence_mac_deliverables_dir(essay_id)
    if seq_mac is not None:
        documents_copy = seq_mac / f"{project}-final.docx"
    else:
        documents_copy = root / f"{project}-10" / f"{project}-final.docx"
    if documents_copy.is_file():
        copies.append(
            {
                "role": "documents",
                "place": final_place(essay_id),
                "path": documents_copy,
            }
        )
    return copies
