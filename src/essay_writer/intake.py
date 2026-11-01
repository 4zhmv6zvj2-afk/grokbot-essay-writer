"""Files that arrive without a module, and a Word draft edited outside the app.

A supporting document is filed on the module and shared by every sequence.
A changed Word draft is identified, confirmed, then rolled forward onto the
next sequence. The parent sequence stays where it is.

A Word file with no saved research trail is a new essay: say so, treat the
first draft as done, and land on user feedback. Research starts only when
the user asks.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from docx import Document

from essay_writer.canon import digest, dump, file_sha256
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    load_draft,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import (
    BRIEF_NAMES,
    confine,
    essay_dir,
    essay_id_error,
    read_last_saved,
    sequence_dir,
    unassigned_dir,
    uploads_dir,
    uploads_root,
    workspace_root,
)
from essay_writer.projects import (
    SequenceCloneError,
    _rewrite_docx,
    clone_sequence,
    empty_sequence_state,
    is_archived,
    load_sequence_state,
    module_sequence_label,
    modules_on_disk,
    parent_tree_pin,
    save_sequence_state,
    sequence_id,
    sequence_numbers,
)
from essay_writer.student_voice import say
from essay_writer.vision import (
    clean_reading,
    is_photo_name,
    photo_words_path,
    prepare_photo,
)

TOOL = "essay.intake"
GENERIC_LINES = frozenset({"reference list", "references", "bibliography"})
REWRITE_MIN_SHARED = 3
REWRITE_MIN_SCORE = 0.6
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "to",
        "in",
        "for",
        "on",
        "with",
        "from",
        "by",
        "at",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "this",
        "that",
        "it",
        "its",
        "their",
        "these",
        "those",
        "not",
        "but",
    }
)
HONESTY = (
    "No saved research trail for this Word file. "
    "Next steps use an upload, a look-up, or a source card from here. "
    "I won't start research unless you ask. "
    "I'm treating this first draft as done, and the next stage is your feedback."
)
WORD_LIST = (
    "I can't tell which module this Word file belongs to. "
    "Here are the modules. Pick one and I will roll this upload forward onto that module's next sequence. "
    "If none of these is yours, say so and I'll start a new module from this file."
)
FILE_LIST = (
    "I can't tell which module this file belongs to. "
    "Here are the modules. Name one and I'll file it there for every sequence."
)
UNIDENTIFIED_CONFIRM = (
    "I still need the module this file belongs to. "
    "Pick a module and I will roll a Word draft forward onto its next sequence, "
    "or say if you want a new module."
)


_README_NAMES = frozenset({"readme", "readme.md", "readme.txt"})
COLLECT = "essay.unassigned.collect"


def _is_readme(name: str) -> bool:
    return name.casefold() in _README_NAMES


def _loose_files() -> list[Path]:
    found: list[Path] = []
    for root in (uploads_root(), workspace_root() / "Essay-writer"):
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if child.is_file() and not _is_readme(child.name):
                found.append(child)
    return found


def essay_unassigned_collect(confirmPhase: str | None = None) -> dict[str, Any]:
    """Draft lists loose files and writes nothing. Confirm moves them. READMEs stay."""
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(unassigned_dir())
    if blocked:
        return blocked
    loose = _loose_files()
    pins = [{"name": path.name, "sha256": file_sha256(path)} for path in loose]
    names = [item["name"] for item in pins]
    payload = {"action": "collect", "files": names}
    fingerprint = {"files": pins}
    body: dict[str, Any] = {
        "ok": True,
        "confirmPhase": confirmPhase,
        "files": names,
        "folder": "unassigned",
        "readmes": "stay",
        "wrote": False,
        "stored": False,
    }
    if confirmPhase == DRAFT:
        body["digest"] = save_draft("unassigned", COLLECT, payload, fingerprint)
        body["next"] = say(
            "These loose files will move into unassigned/. READMEs stay. Nothing moves until you say yes."
        )
        return body
    ready = confirm_ready("unassigned", COLLECT, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    holding = unassigned_dir()
    holding.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for path in loose:
        if not path.is_file():
            continue
        dest = _unique(holding, path.name)
        shutil.move(str(path), str(dest))
        moved.append(dest.name)
    body["files"] = sorted(moved)
    body["wrote"] = True
    body["stored"] = True
    body["digest"] = ready["digest"]
    return body


def _unique(folder: Path, name: str) -> Path:
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while True:
        candidate = folder / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _docx_parts(path: Path) -> tuple[list[str], list[str]]:
    document = Document(str(path))
    headings: list[str] = []
    paragraphs: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style = paragraph.style.name if paragraph.style is not None else ""
        if style.startswith("Heading"):
            headings.append(text)
        paragraphs.append(text)
    return headings, paragraphs


def _words(paragraphs: list[str]) -> int:
    return sum(len(text.split()) for text in paragraphs)


_NOT_THE_ESSAY = frozenset({"annotation.docx", "download-list.docx"})


def _output_path(module: str, number: int) -> Path | None:
    """The sequence Word file. Annotation and the download list are not that file."""
    folder = sequence_dir(module, number) / "output"
    if not folder.is_dir():
        return None
    named = folder / f"{sequence_id(module, number)}.docx"
    if named.is_file():
        return named
    matches = [
        path
        for path in folder.glob("*.docx")
        if path.name.casefold() not in _NOT_THE_ESSAY
    ]
    if not matches:
        return None
    return sorted(matches)[-1]


def _body_paragraphs(paragraphs: list[str]) -> list[str]:
    """Essay body only. Reference lines and the counted-words cover line are not a match."""
    body: list[str] = []
    in_refs = False
    for text in paragraphs:
        folded = text.casefold().strip()
        if folded in GENERIC_LINES:
            in_refs = True
            continue
        if folded.startswith("counted words"):
            continue
        if in_refs:
            continue
        body.append(text)
    return body


def _content_tokens(paragraphs: list[str]) -> set[str]:
    tokens: set[str] = set()
    for text in _body_paragraphs(paragraphs):
        for word in re.findall(r"[a-z0-9]+", text.casefold()):
            if len(word) > 2 and word not in _STOP:
                tokens.add(word)
    return tokens


def _rewrite_score(current: list[str], latest: list[str]) -> float:
    """How much of the shorter body is the same essay, ignoring the cover line and the reference list."""
    left = _content_tokens(current)
    right = _content_tokens(latest)
    if not left or not right:
        return 0.0
    shared = left & right
    if len(shared) < REWRITE_MIN_SHARED:
        return 0.0
    return len(shared) / min(len(left), len(right))


def _is_rewrite(current: list[str], latest: list[str]) -> bool:
    return _rewrite_score(current, latest) >= REWRITE_MIN_SCORE


def _identify(paragraphs: list[str]) -> str | None:
    """The one module whose last-saved Word file this upload rewrites. Ambiguous matches stay unnamed."""
    scores: list[tuple[float, str]] = []
    for module in modules_on_disk():
        if is_archived(module):
            continue
        number = read_last_saved(module)
        if number is None:
            continue
        latest = _output_path(module, number)
        if latest is None:
            continue
        _, latest_paragraphs = _docx_parts(latest)
        scores.append((_rewrite_score(paragraphs, latest_paragraphs), module))
    scores.sort(reverse=True)
    if not scores or scores[0][0] < REWRITE_MIN_SCORE:
        return None
    if len(scores) > 1 and scores[1][0] >= REWRITE_MIN_SCORE:
        return None
    return scores[0][1]


def _sources(state: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    research = state.get("research") or {}
    if not isinstance(research, dict):
        return found
    for depth in ("full", "summary"):
        record = research.get(depth)
        if isinstance(record, dict) and isinstance(record.get("sources"), list):
            for source in record["sources"]:
                if isinstance(source, dict):
                    found.append(source)
    return found


def _research_trail(state: dict[str, Any]) -> bool:
    research = state.get("research") or {}
    if not isinstance(research, dict):
        return False
    for depth in ("full", "summary"):
        record = research.get(depth)
        if isinstance(record, dict) and record:
            return True
    return False


def _reference_lines(paragraphs: list[str]) -> list[str]:
    lines: list[str] = []
    seen = False
    for text in paragraphs:
        if text in {"Reference List", "References"}:
            seen = True
            continue
        if seen:
            lines.append(text)
    return lines


def _title_usable(source: dict[str, Any], title: str) -> bool:
    """A title match is a gathered identity. A surname, or a title that is only a surname, is not."""
    if source.get("gathered") is False:
        return False
    origin = source.get("origin")
    if origin in {"sample", "samples", "reference-list"}:
        return False
    if len(title) < 8 or " " not in title:
        return False
    authors = source.get("authors")
    if isinstance(authors, list):
        names = {author.casefold().strip() for author in authors if isinstance(author, str)}
        if title.casefold() in names:
            return False
    return True


def _match_references(lines: list[str], sources: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    """Link a reference line only when its title is a gathered source. Surnames stay unresolved."""
    matched: list[dict[str, str]] = []
    unresolved: list[str] = []
    for line in lines:
        lowered = line.casefold()
        hit: str | None = None
        for source in sources:
            title = source.get("title")
            if not isinstance(title, str):
                continue
            title = title.strip()
            if not _title_usable(source, title):
                continue
            if title.casefold() in lowered:
                hit = str(source.get("id") or title)
                break
        if hit:
            matched.append({"line": line, "source_id": hit})
        else:
            unresolved.append(line)
    return matched, unresolved


def _summary(
    module: str | None,
    number: int | None,
    headings: list[str],
    paragraphs: list[str],
    latest_headings: list[str],
    latest_paragraphs: list[str],
    current_hash: str,
    latest_path: Path | None,
) -> dict[str, Any]:
    latest_hash = file_sha256(latest_path) if latest_path and latest_path.is_file() else None
    same = latest_hash is not None and latest_hash == current_hash
    return {
        "module": module,
        "latest": sequence_id(module, number) if module and number else None,
        "current_words": _words(paragraphs),
        "latest_words": _words(latest_paragraphs) if latest_paragraphs else None,
        "headings_added": [item for item in headings if item not in latest_headings],
        "headings_removed": [item for item in latest_headings if item not in headings],
        "same_file": same,
        "latest_sha256": latest_hash,
    }


def _text_paragraphs(path: Path) -> tuple[list[str], list[str]]:
    """Headings and paragraphs. Markdown and text count the same way as Word."""
    if path.suffix.lower() == ".docx":
        return _docx_parts(path)
    if path.suffix.lower() in {".md", ".txt", ".csv"}:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return [], []
        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
        return [], paragraphs
    return [], []


def _against_module(path: Path, module: str) -> dict[str, Any]:
    headings, paragraphs = _text_paragraphs(path)
    number = read_last_saved(module)
    latest_headings: list[str] = []
    latest_paragraphs: list[str] = []
    latest_path = _output_path(module, number) if number else None
    if latest_path is not None and path.suffix.lower() == ".docx":
        latest_headings, latest_paragraphs = _docx_parts(latest_path)
    if path.name.lower() in BRIEF_NAMES:
        kind = "brief"
    elif path.suffix.lower() == ".docx" and _is_rewrite(paragraphs, latest_paragraphs):
        kind = "output"
    else:
        kind = "supporting"
    summary = _summary(
        module,
        number,
        headings,
        paragraphs,
        latest_headings,
        latest_paragraphs,
        file_sha256(path),
        latest_path,
    )
    return {"kind": kind, "summary": summary, "paragraphs": paragraphs, "latest_path": latest_path}


def _module_rows() -> list[dict[str, str]]:
    """Continue's modules, with the sequence id left off. An upload does not ask for a sequence."""
    rows: list[dict[str, str]] = []
    for module in modules_on_disk():
        if is_archived(module):
            continue
        saved = read_last_saved(module)
        rows.append({"essay_id": module_sequence_label(module, saved)})
    return rows


def _module_list(path: Path, confirm_phase: str, *, word: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "name": path.name,
        "identified": False,
        "sequence_pick": False,
        "rows": _module_rows(),
        "kind": None,
        "module": None,
        "confirmPhase": confirm_phase,
        "wrote": False,
        "stored": False,
        "sha256": file_sha256(path),
        "research_started": False,
        "next": say(WORD_LIST if word else FILE_LIST),
    }


def _roll_target(module: str) -> tuple[int | None, int] | str:
    parent = read_last_saved(module)
    numbers = sequence_numbers(module)
    if numbers and parent is None:
        return (
            f"I don't know which sequence of {module} was saved last. "
            "Name it with a new sequence, or say if this Word file is a new module. "
            "I won't guess from the highest folder number."
        )
    child = 1 if not numbers else max(numbers) + 1
    return parent, child


def _fresh_child(module: str) -> int:
    numbers = sequence_numbers(module)
    return 1 if not numbers else max(numbers) + 1


def _mark_feedback(state: dict[str, Any]) -> None:
    state["user_feedback"] = True
    state["first_draft"] = "done"
    state["research_on_request"] = True


def _place_word(
    module: str,
    child: int,
    path: Path,
    paragraphs: list[str],
    *,
    parent_number: int | None,
    reason: str,
) -> dict[str, Any] | tuple[dict[str, Any], Path]:
    child_id = sequence_id(module, child)
    if parent_number is None:
        folder = sequence_dir(module, child)
        if folder.exists():
            return refuse("sequence", f"{child_id} already exists. Draft again.")
        dest = folder / "output" / f"{child_id}.docx"
        try:
            dest.parent.mkdir(parents=True)
            shutil.copy2(path, dest)
        except OSError:
            if folder.exists():
                shutil.rmtree(folder)
            return refuse(
                "sequence",
                "I couldn't finish the new sequence, so I didn't keep a partial copy. "
                "Say if you want me to try again.",
            )
        state = empty_sequence_state(module, child, parent=None, reason=reason)
    else:
        try:
            clone_sequence(module, parent_number, child, reason=reason)
        except FileExistsError:
            return refuse("sequence", f"{child_id} already exists. Draft again.")
        except SequenceCloneError:
            return refuse(
                "sequence",
                "I couldn't finish the new sequence, so I didn't keep a partial copy. "
                "Say if you want me to try again.",
            )
        dest = sequence_dir(module, child) / "output" / f"{child_id}.docx"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        _rewrite_docx(dest, sequence_id(module, parent_number), child_id)
        _rewrite_docx(dest, f"sequences/{parent_number}", f"sequences/{child}")
        state = load_sequence_state(module, child)
    path.unlink()
    matched, unresolved = _match_references(_reference_lines(paragraphs), _sources(state))
    word = state.get("word")
    if not isinstance(word, dict):
        word = {}
    word["upload"] = {
        "path": f"Essay-writer/{module}/sequences/{child}/output/{child_id}.docx",
        "sha256": file_sha256(dest),
        "source": reason,
    }
    state["word"] = word
    state["reference_index"] = matched
    state["unresolved_references"] = unresolved
    state["branch_reason"] = reason
    if not _research_trail(state):
        _mark_feedback(state)
    save_sequence_state(module, child, state)
    return state, dest


def _unchanged(module: str, path: Path, confirm_phase: str, summary: dict[str, Any], sha: str) -> dict[str, Any]:
    payload = {
        "name": path.name,
        "module": module,
        "kind": "output",
        "sha256": sha,
        "unchanged": True,
    }
    fingerprint = {
        "sha256": sha,
        "sequences": [sequence_id(module, number) for number in sequence_numbers(module)],
        "kind": "output",
        "latest_docx": summary.get("latest_sha256"),
        "unchanged": True,
    }
    latest = read_last_saved(module)
    body = {
        "ok": True,
        "name": path.name,
        "kind": "output",
        "module": module,
        "essay_id": module_sequence_label(module, latest),
        "summary": summary,
        "confirmPhase": confirm_phase,
        "wrote": False,
        "stored": False,
        "sha256": sha,
        "sequence_pick": False,
        "unchanged": True,
        "stays": "unassigned",
        "research_started": False,
        "next": say(
            f"This Word file matches the latest output of "
            f"{module_sequence_label(module, read_last_saved(module))}. "
            "It stays in unassigned/. I left every sequence as it is. Nothing was written."
        ),
    }
    if confirm_phase == DRAFT:
        body["digest"] = save_draft(module, TOOL, payload, fingerprint)
        return body
    record = load_draft(module, TOOL, payload)
    if record is not None and dump(record.get("fingerprint")) != dump(fingerprint):
        return refuse(
            "confirm",
            "The latest Word file changed after the draft. Fresh draft required.",
            digest=digest(payload),
        )
    return body


def _draft_body(
    path: Path,
    module: str,
    confirm_phase: str,
    kind: str,
    summary: dict[str, Any],
    sha: str,
    child_id: str | None,
    *,
    identified: bool,
    next_text: str,
    create: bool,
) -> dict[str, Any]:
    from essay_writer.projects import strip_duplicate_card_ids

    body = {
        "ok": True,
        "name": path.name,
        "kind": kind,
        "module": module,
        "essay_id": module_sequence_label(module, sequence=child_id),
        "summary": summary,
        "confirmPhase": confirm_phase,
        "wrote": False,
        "stored": False,
        "sha256": sha,
        "sequence_id": child_id,
        "sequence_pick": False,
        "identified": identified,
        "new_from_word": create,
        "research_started": False,
        "next": say(next_text),
    }
    return strip_duplicate_card_ids(body)


def _photo_pair(folder: Path, name: str) -> tuple[Path, Path]:
    """Image and sidecar names that are both free. The sidecar is image name + .txt."""
    candidate = folder / name
    text = photo_words_path(candidate)
    if not candidate.exists() and not text.exists():
        return candidate, text
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while True:
        candidate = folder / f"{stem}-{index}{suffix}"
        text = photo_words_path(candidate)
        if not candidate.exists() and not text.exists():
            return candidate, text
        index += 1


def _place_photo(module: str, path: Path, text: str) -> tuple[Path, Path]:
    folder = uploads_dir(module)
    folder.mkdir(parents=True, exist_ok=True)
    dest, text_path = _photo_pair(folder, path.name)
    temporary = text_path.with_name(text_path.name + ".tmp")
    temporary.write_text(text + "\n", encoding="utf-8")
    try:
        shutil.move(str(path), str(dest))
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(text_path)
    return dest, text_path


def _file_photo(
    path: Path,
    confirm_phase: str,
    module: str | None,
    reading: object,
    *,
    create: bool,
    roll_forward: bool,
) -> dict[str, Any]:
    """Show a photo to the model, then file the words it reads."""
    prepared = prepare_photo(path)
    if prepared.get("ok") is not True:
        return refuse("intake", str(prepared.get("reason")))
    if create or roll_forward:
        return refuse(
            "intake",
            "This is a photo, not a Word draft. Name the module and I'll file the words for every sequence.",
        )
    if module is None:
        if confirm_phase == CONFIRM:
            return refuse("intake", UNIDENTIFIED_CONFIRM)
        body = _module_list(path, confirm_phase, word=False)
        body["kind"] = "photo"
        body["needs_reading"] = True
        body["media_type"] = prepared["media_type"]
        body["prompt"] = prepared["prompt"]
        body["show_image"] = prepared["show_image"]
        body["source"] = prepared["source"]
        body["next"] = say(
            "I can't tell which module this photo belongs to. "
            "Here are the modules. Name one and I'll read the photo and file the words there."
        )
        return body
    error = essay_id_error(module)
    if error:
        return refuse("essay-id", error)
    if is_archived(module):
        return refuse("intake", f"{module} is archived. Unarchive it before filing this document.")
    text, problem = clean_reading(reading)
    if problem:
        return refuse("intake", problem)
    shown = {
        "media_type": prepared["media_type"],
        "prompt": prepared["prompt"],
        "show_image": prepared["show_image"],
        "source": prepared["source"],
    }
    if text is None:
        if confirm_phase == CONFIRM:
            return refuse("intake", "Show the words from this photo first. Nothing was filed.")
        return {
            "ok": True,
            "name": path.name,
            "kind": "photo",
            "module": module,
            "needs_reading": True,
            "confirmPhase": confirm_phase,
            "wrote": False,
            "stored": False,
            "sha256": prepared["sha256"],
            "bytes": prepared["bytes"],
            "sequence_pick": False,
            "research_started": False,
            "next": say(
                f"I'll read the words in this photo and show them before filing them with {module}. "
                "Nothing is written yet."
            ),
            **shown,
        }
    sha = prepared["sha256"]
    payload = {
        "name": path.name,
        "module": module,
        "kind": "photo",
        "sha256": sha,
        "reading": text,
        "create": False,
        "rollForward": False,
    }
    fingerprint = {
        "sha256": sha,
        "sequences": [sequence_id(module, number) for number in sequence_numbers(module)],
        "kind": "photo",
        "reading": text,
    }
    body = {
        "ok": True,
        "name": path.name,
        "kind": "photo",
        "module": module,
        "needs_reading": False,
        "reading": text,
        "confirmPhase": confirm_phase,
        "wrote": False,
        "stored": False,
        "sha256": sha,
        "sequence_pick": False,
        "identified": False,
        "research_started": False,
        "next": say(
            "These are the words I read in the photo. "
            f"Say yes and I'll file the photo and these words with {module} for every sequence. "
            "Nothing is written until then."
        ),
        **shown,
    }
    if confirm_phase == DRAFT:
        essay_dir(module).mkdir(parents=True, exist_ok=True)
        body["digest"] = save_draft(module, TOOL, payload, fingerprint)
        return body
    ready = confirm_ready(module, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    try:
        dest, text_path = _place_photo(module, path, text)
    except OSError:
        return refuse(
            "intake",
            "I couldn't file this photo. It is still waiting, and nothing was saved.",
        )
    body["wrote"] = True
    body["stored"] = True
    body["path"] = f"uploads/{module}/{dest.name}"
    body["text_path"] = f"uploads/{module}/{text_path.name}"
    body["digest"] = ready["digest"]
    body.pop("show_image", None)
    body["next"] = say(f"I've filed this photo and the words from it on {module} for every sequence.")
    return body


def essay_intake(
    name: str,
    confirmPhase: str | None = None,
    module: str | None = None,
    create: bool = False,
    rollForward: bool = False,
    reading: str | None = None,
) -> dict[str, Any]:
    """File one unassigned document.

    A Word draft is identified, then confirmed, then rolled onto the next
    sequence. If it cannot be identified, the reply is the module list and
    the user picks a module. create=True starts a new module from the file.

    A photo is shown to the model. Confirm files the photo and the words
    the model read from it.
    """
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase
    confirm_phase = confirmPhase if isinstance(confirmPhase, str) else ""

    targets = [unassigned_dir(), uploads_dir(module) if isinstance(module, str) and module.strip() else unassigned_dir()]
    if isinstance(module, str) and module.strip():
        targets.append(essay_dir(module))
    blocked = guard_write_door(*targets)
    if blocked:
        return blocked
    if create and rollForward:
        return refuse(
            "intake",
            "Say whether this is a new module or a roll-forward onto a module you already have.",
        )
    if create is not True and create:
        return refuse("intake", "create is yes or no.")
    if rollForward is not True and rollForward:
        return refuse("intake", "rollForward is yes or no.")
    try:
        path = confine(unassigned_dir(), name)
    except ValueError as exc:
        return refuse("intake", str(exc))
    if not path.is_file():
        return refuse("intake", f"{name} is not in unassigned/.")
    if is_photo_name(path.name):
        return _file_photo(
            path,
            confirm_phase,
            module,
            reading,
            create=bool(create),
            roll_forward=bool(rollForward),
        )
    if create:
        return _new_from_word(path, confirm_phase, module)
    if rollForward and module is None:
        return refuse(
            "intake",
            "Name the module. I roll this forward onto that module's next sequence.",
        )
    if rollForward and path.suffix.lower() != ".docx":
        return refuse(
            "intake",
            "That file isn't a Word draft, so I can't roll it forward. "
            "Name the module if you want it filed for every sequence.",
        )

    identified = False
    if module is None:
        if path.suffix.lower() != ".docx":
            if confirm_phase == CONFIRM:
                return refuse("intake", UNIDENTIFIED_CONFIRM)
            return _module_list(path, confirm_phase, word=False)
        _, paragraphs = _docx_parts(path)
        found = _identify(paragraphs)
        if found is None:
            if confirm_phase == CONFIRM:
                return refuse("intake", UNIDENTIFIED_CONFIRM)
            return _module_list(path, confirm_phase, word=True)
        module = found
        identified = True

    error = essay_id_error(module)
    if error:
        return refuse("essay-id", error)
    if is_archived(module):
        return refuse("intake", f"{module} is archived. Unarchive it before filing this document.")

    classified = _against_module(path, module)
    summary = classified["summary"]
    if path.suffix.lower() == ".docx" and summary.get("same_file"):
        return _unchanged(module, path, confirm_phase, summary, file_sha256(path))
    if path.suffix.lower() == ".docx" and (rollForward or identified):
        classified["kind"] = "output"
    return _file_named(
        path,
        confirm_phase,
        module,
        classified,
        identified=identified,
        create=False,
        roll_forward=bool(rollForward),
    )


def _new_from_word(path: Path, confirm_phase: str, module: str | None) -> dict[str, Any]:
    if not isinstance(module, str):
        return refuse("intake", "Name the module code for the new essay, such as MOD1008AA.")
    error = essay_id_error(module)
    if error:
        return refuse("essay-id", error)
    if is_archived(module):
        return refuse("intake", f"{module} is archived. Unarchive it before filing this document.")
    if path.suffix.lower() != ".docx":
        return refuse(
            "intake",
            "A new essay from Word needs a Word file. Name the module if you want this one filed for every sequence.",
        )
    headings, paragraphs = _docx_parts(path)
    child = _fresh_child(module)
    child_id = sequence_id(module, child)
    sha = file_sha256(path)
    summary = _summary(module, None, headings, paragraphs, [], [], sha, None)
    kind = "output"
    next_text = f"{HONESTY} This will start {child_id}. Say yes and I'll file the Word draft there. Nothing is written until then."
    return _file_named(
        path,
        confirm_phase,
        module,
        {"kind": kind, "summary": summary, "paragraphs": paragraphs},
        identified=False,
        create=True,
        roll_forward=False,
        next_text=next_text,
        child=child,
    )


def _file_named(
    path: Path,
    confirm_phase: str,
    module: str,
    classified: dict[str, Any],
    *,
    identified: bool,
    create: bool,
    roll_forward: bool,
    next_text: str | None = None,
    child: int | None = None,
) -> dict[str, Any]:
    kind = classified["kind"]
    summary = classified["summary"]
    sha = file_sha256(path)
    if create:
        parent: int | None = None
        if child is None:
            child = _fresh_child(module)
    elif kind == "output":
        target = _roll_target(module)
        if isinstance(target, str):
            return refuse("intake", target)
        parent, child = target
    else:
        parent, child = None, None
    child_id = sequence_id(module, child) if child else None
    parent_id = sequence_id(module, parent) if parent else None
    if next_text is None:
        if kind == "brief":
            next_text = (
                f"I'll file this as the brief for {module} at "
                f"Essay-writer/{module}/{path.name}. "
                "Say yes and I'll move it. Nothing is written until then."
            )
        elif kind == "supporting":
            next_text = (
                f"I'll file this on {module} so every sequence can use it. "
                "Say yes and I'll move it. Nothing is written until then."
            )
        elif parent_id and parent is not None and _research_trail(load_sequence_state(module, parent)):
            next_text = (
                f"This Word file belongs with {module}. "
                f"I'll leave {parent_id} as it is and roll forward onto {child_id}. "
                "Say yes and I'll do that. Nothing is written until then."
            )
        else:
            next_text = (
                f"{HONESTY} This will start {child_id}. "
                "Say yes and I'll file the Word draft there. Nothing is written until then."
            )
    payload = {
        "name": path.name,
        "module": module,
        "kind": kind,
        "sha256": sha,
        "sequence_id": child_id,
        "create": create,
        "rollForward": roll_forward,
    }
    latest_path = classified.get("latest_path")
    if not isinstance(latest_path, Path) and parent is not None:
        latest_path = _output_path(module, parent)
    latest_sha = file_sha256(latest_path) if isinstance(latest_path, Path) and latest_path.is_file() else None
    fingerprint = {
        "sha256": sha,
        "sequences": [sequence_id(module, number) for number in sequence_numbers(module)],
        "kind": kind,
        "latest_docx": latest_sha,
        "parent_tree": parent_tree_pin(module, parent) if parent is not None else [],
    }
    body = _draft_body(
        path,
        module,
        confirm_phase,
        kind,
        summary,
        sha,
        child_id,
        identified=identified,
        next_text=next_text,
        create=create,
    )
    if kind not in {"supporting", "brief"} and not (
        parent_id and _research_trail(load_sequence_state(module, parent) if parent else {})
    ):
        body["stage"] = "user-feedback"
        body["first_draft"] = "done"
    if confirm_phase == DRAFT:
        essay_dir(module).mkdir(parents=True, exist_ok=True)
        body["digest"] = save_draft(module, TOOL, payload, fingerprint)
        return body
    ready = confirm_ready(module, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    if kind in {"supporting", "brief"}:
        if kind == "brief":
            dest_dir = essay_dir(module)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / path.name
            if dest.exists() and dest.resolve() != path.resolve():
                dest.unlink()
            if dest.resolve() != path.resolve():
                shutil.move(str(path), str(dest))
            body["path"] = f"Essay-writer/{module}/{dest.name}"
            from essay_writer.databases import remember_databases

            body["databases"] = remember_databases(module)
            body["next"] = say(f"I've filed the brief on {module}.")
        else:
            dest_dir = uploads_dir(module)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique(dest_dir, path.name)
            shutil.move(str(path), str(dest))
            body["path"] = f"uploads/{module}/{dest.name}"
            body["next"] = say(f"I've filed this on {module} for every sequence.")
        body["wrote"] = True
        body["stored"] = True
        return body
    assert child is not None
    placed = _place_word(
        module,
        child,
        path,
        classified["paragraphs"],
        parent_number=parent,
        reason="new-from-word" if create or parent is None else "user-upload",
    )
    if isinstance(placed, dict):
        return placed
    state, _dest = placed
    body["wrote"] = True
    body["stored"] = True
    body["path"] = state["word"]["upload"]["path"]
    body["reference_index"] = state["reference_index"]
    body["unresolved_references"] = state["unresolved_references"]
    body["research_started"] = False
    if state.get("user_feedback"):
        body["stage"] = "user-feedback"
        body["first_draft"] = "done"
        body["next"] = say(f"{HONESTY} This is {child_id}.")
    else:
        body.pop("stage", None)
        body.pop("first_draft", None)
        body["next"] = say(f"I've rolled this forward onto {child_id} and left {parent_id} as it is.")
    return body
