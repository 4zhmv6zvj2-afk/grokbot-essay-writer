"""Chop a PDF read at 20MB without throwing away a readable part.

Bytes stay on this machine. Nothing in this module uploads a PDF.
A slice that is not itself a readable PDF is not written as a part.
That missing part is recorded in pdf-read-gaps.json for a later citation pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PART_LIMIT = 20_000_000
GAPS_NAME = "pdf-read-gaps.json"


def readable_pdf(data: bytes) -> bool:
    """A part is readable when it is a PDF and the file ending is present."""
    from essay_writer.downloads import pdf_magic

    if not data or not pdf_magic(data):
        return False
    tail = data[-2048:]
    return b"%%EOF" in tail


def _concatenated(data: bytes) -> list[bytes]:
    parts: list[bytes] = []
    start = 0
    while start < len(data):
        eof = data.find(b"%%EOF", start)
        if eof < 0:
            remainder = data[start:]
            if remainder.strip():
                parts.append(remainder)
            break
        end = eof + len(b"%%EOF")
        while end < len(data) and data[end : end + 1] in (b"\n", b"\r", b" "):
            end += 1
        chunk = data[start:end]
        if chunk.strip():
            parts.append(chunk)
        start = end
    return parts or [data]


def _load_gaps(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    gaps = data.get("gaps") if isinstance(data, dict) else None
    if not isinstance(gaps, list):
        return []
    return [item for item in gaps if isinstance(item, dict)]


def load_gaps(folder: Path) -> list[dict[str, Any]]:
    """Gaps already recorded beside a PDF. The citation pass reads this list."""
    return _load_gaps(Path(folder) / GAPS_NAME)


def record_read_gaps(folder: Path, gaps: list[dict[str, Any]]) -> Path | None:
    """Append missing parts. The later citation pass reads this file."""
    if not gaps:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / GAPS_NAME
    payload = {
        "bytes_leave_machine": False,
        "gaps": _load_gaps(path) + gaps,
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def chop_pdf(path: Path, *, limit: int = PART_LIMIT) -> dict[str, Any]:
    """Split one on-disk PDF into readable parts of at most `limit` bytes.

    A concatenated PDF becomes one file per readable document that fits.
    A single document larger than the limit stays on disk as itself. The
    span past the limit is a gap, not a broken slice. A truncated body is
    only a gap. PDF bytes are not sent off this machine.
    """
    target = Path(path)
    try:
        data = target.read_bytes()
    except OSError as exc:
        gap = {
            "source": target.name,
            "part": 1,
            "reason": "unreadable",
            "detail": str(exc),
            "bytes_on_machine": False,
        }
        return {
            "ok": False,
            "bytes_leave_machine": False,
            "parts": [],
            "gaps": [gap],
            "gaps_path": None,
        }
    pieces = _concatenated(data)
    parts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    single_fit = (
        len(pieces) == 1
        and pieces[0] == data
        and len(data) <= limit
        and readable_pdf(data)
    )
    if single_fit:
        return {
            "ok": True,
            "bytes_leave_machine": False,
            "parts": [{"name": target.name, "path": str(target), "readable": True}],
            "gaps": [],
            "gaps_path": None,
        }
    folder = target.parent / f"{target.stem}-read-parts"
    index = 0
    for piece in pieces:
        index += 1
        if readable_pdf(piece) and len(piece) <= limit:
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / f"part-{index}.pdf"
            dest.write_bytes(piece)
            parts.append({"name": dest.name, "path": str(dest), "readable": True})
            continue
        if readable_pdf(piece) and len(piece) > limit:
            gaps.append(
                {
                    "source": target.name,
                    "part": index,
                    "reason": "read past 20MB is not a separate readable PDF",
                    "bytes_on_machine": True,
                    "offset": limit,
                    "length": len(piece) - limit,
                }
            )
            continue
        gaps.append(
            {
                "source": target.name,
                "part": index,
                "reason": "unreadable",
                "bytes_on_machine": target.is_file(),
                "offset": 0,
                "length": len(piece),
            }
        )
    gaps_path = record_read_gaps(target.parent, gaps)
    return {
        "ok": True,
        "bytes_leave_machine": False,
        "parts": parts,
        "gaps": gaps,
        "gaps_path": None if gaps_path is None else str(gaps_path),
    }
