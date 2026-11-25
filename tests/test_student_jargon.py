"""Spoken refusal and say() literals stay free of builder jargon."""

import ast
import re
from pathlib import Path

from essay_writer.student_voice import say

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"
JARGON = re.compile(
    r"\b(?:doors?|packs?|shelf|seats?|spine|canon|minted?|house|EQR)\b",
    re.IGNORECASE,
)
TOOL_NAME = re.compile(r"essay\.[a-z]")


def _callee(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _spoken_literals(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee(node)
        pieces: list[ast.expr] = []
        if name == "refuse":
            pieces.extend(node.args[1:3])
            for keyword in node.keywords:
                if keyword.arg in {"reason", "next"}:
                    pieces.append(keyword.value)
        elif name == "say":
            pieces.extend(node.args[:1])
        else:
            continue
        for piece in pieces:
            text = _literal(piece)
            if text is not None:
                found.append((piece.lineno, text))
    return found


def test_spoken_literals_drop_builder_jargon() -> None:
    """A student hears the cleaned reason and next, not a door, pack, or tool name."""
    failures: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts or path.name == "student_voice.py":
            continue
        relative = path.relative_to(REPO)
        for line, text in _spoken_literals(path):
            cleaned = say(text)
            if JARGON.search(cleaned) or TOOL_NAME.search(cleaned):
                failures.append(f"{relative}:{line}: {cleaned}")
    assert not failures, "\n".join(failures)
