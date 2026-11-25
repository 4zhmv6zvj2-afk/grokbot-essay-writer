"""Every key a state.json writer stores is already in the known set.

The set also keeps keys older files stored. Deriving it from current writers
would treat those keys as unknown and record a different incident.
"""

from __future__ import annotations

import ast
from pathlib import Path

from essay_writer.state import _KNOWN_STATE_KEYS

ROOT = Path(__file__).resolve().parents[1] / "src" / "essay_writer"
_SAVERS = {"save_state", "_save_state", "save_sequence_state"}
_FACTORIES = {"empty_state", "empty_sequence_state", "load_state", "load_sequence_state"}
_CONSTRUCTORS = {"empty_state", "empty_sequence_state"}


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _saved_name(call: ast.Call) -> str | None:
    name = _call_name(call)
    if name in {"save_state", "_save_state"} and len(call.args) >= 2:
        arg = call.args[1]
    elif name == "save_sequence_state" and len(call.args) >= 3:
        arg = call.args[2]
    else:
        return None
    if isinstance(arg, ast.Name):
        return arg.id
    return None


def _state_arg(arg: ast.arg) -> bool:
    if arg.arg != "state" and not arg.arg.endswith("_state"):
        return False
    return not (isinstance(arg.annotation, ast.Name) and arg.annotation.id == "Path")


def _assigned_key(target: ast.AST, names: set[str]) -> str | None:
    key: str | None = None
    current = target
    while isinstance(current, ast.Subscript):
        slice_ = current.slice
        if isinstance(slice_, ast.Constant) and isinstance(slice_.value, str):
            key = slice_.value
        current = current.value
    if isinstance(current, ast.Name) and current.id in names and key is not None:
        return key
    return None


def _writer_keys() -> set[str]:
    found: set[str] = set()
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            names = {arg.arg for arg in [*fn.args.args, *fn.args.kwonlyargs] if _state_arg(arg)}
            saves = False
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and _call_name(node) in _SAVERS:
                    saved = _saved_name(node)
                    if saved:
                        names.add(saved)
                        saves = True
            if fn.name in _CONSTRUCTORS or saves:
                for node in ast.walk(fn):
                    value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
                    targets = (
                        list(node.targets)
                        if isinstance(node, ast.Assign)
                        else [node.target]
                        if isinstance(node, ast.AnnAssign)
                        else []
                    )
                    if isinstance(value, ast.Call) and _call_name(value) in _FACTORIES:
                        for target in targets:
                            if isinstance(target, ast.Name):
                                names.add(target.id)
            if fn.name == "empty_state":
                for node in ast.walk(fn):
                    if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                found.add(key.value)
            for node in ast.walk(fn):
                targets = (
                    list(node.targets)
                    if isinstance(node, ast.Assign)
                    else [node.target]
                    if isinstance(node, (ast.AnnAssign, ast.AugAssign))
                    else []
                )
                for target in targets:
                    key = _assigned_key(target, names)
                    if key is not None:
                        found.add(key)
    return found


def test_state_writers_only_store_known_keys() -> None:
    written = _writer_keys()
    assert written
    assert written <= _KNOWN_STATE_KEYS
