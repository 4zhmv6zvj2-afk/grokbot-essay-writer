"""Chat and Mac handoff for assignment-facing files.

Word the student submits is always reachable in chat. Large research zips
stay path-only unless the product already attaches them elsewhere.
"""

from __future__ import annotations

from pathlib import Path


def chat_word_file(path: Path) -> dict[str, object]:
    from essay_writer.research_packs import chat_docx

    return chat_docx(path)


def attach_word_chat(body: dict[str, object], path: Path, *, key: str = "word") -> dict[str, object]:
    """Record a student Word file for chat delivery on this tool result."""
    chat = chat_word_file(path)
    body["chat_docx"] = chat
    delivery = body.get("delivery")
    if not isinstance(delivery, dict):
        delivery = {}
    delivery[key] = chat
    body["delivery"] = delivery
    return chat


def papers_zip_pointer(name: str, path: str, *, entries: list[str] | None = None) -> dict[str, object]:
    """Path-only handoff for papers.zip. No zip_base64 in chat."""
    row: dict[str, object] = {
        "name": name,
        "path": path,
        "deliver": "path",
    }
    if entries is not None:
        row["entries"] = entries
    return row
