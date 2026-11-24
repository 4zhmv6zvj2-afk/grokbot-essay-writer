"""Read-only report of pins in the test tree.

A pin locks source text, a docstring, another test, or a filename. The
observable artifact is the tool reply, the student text, the docx, the file
on disk, or the saved state. One pin is one line::

    tests/test_foo.py:12 | getsource | write_docx

The last line is the count. Exit status is always 0. This tool does not
write the tree.

When a change touches a file that has a pin, replace that pin with an
assertion on the observable artifact. Do not add a new ``inspect.getsource``
pin. The count should fall by at least a quarter in each release.

Keep these policy ratchets even when they appear in the report: the import
graph, the ban on ``PYTEST_CURRENT_TEST`` under ``src/``, the public-address
scan, ``test_captured_material.py``, the skill-version tests, and the prompt
snapshot.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path

KINDS = (
    "getsource",
    "docstring",
    "source-string",
    "test-of-test",
    "filename-pin",
)
_TEST_FILE = re.compile(r"(?:tests/)?test_[A-Za-z0-9_]+\.py")
_SOURCE_CALLS = frozenset({"count", "index", "find", "startswith", "endswith"})
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_EMPTY = "pins: 0 (getsource 0, docstring 0, source-string 0, test-of-test 0, filename-pin 0)\n"


def _text(node: ast.AST) -> str:
    try:
        rendered = ast.unparse(node)
    except (ValueError, TypeError):
        return ""
    return " ".join(rendered.split())


def _target(text: str) -> str:
    cleaned = " ".join(text.replace("|", "/").split())
    if len(cleaned) > 80:
        return cleaned[:77] + "..."
    return cleaned or "-"


def _py_source(node: ast.AST) -> bool:
    rendered = _text(node)
    return ".py" in rendered and ".pyc" not in rendered


def _is_test_path(node: ast.AST) -> bool:
    rendered = _text(node)
    return "test_" in rendered and ".py" in rendered and ".pyc" not in rendered


def _is_source_read(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "read_text":
        receiver = _text(func.value)
        return _py_source(func.value) or "co_filename" in receiver
    if isinstance(func, ast.Name) and func.id in {"_read", "read_text"}:
        return any(_py_source(arg) for arg in node.args)
    return False


def _call_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _assigned_name(node: ast.AST) -> str:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return target.id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return ""


def _walk(node: ast.AST) -> Iterator[tuple[ast.AST, tuple[ast.AST, ...]]]:
    def visit(
        current: ast.AST, parents: tuple[ast.AST, ...]
    ) -> Iterator[tuple[ast.AST, tuple[ast.AST, ...]]]:
        here = parents + (current,)
        yield current, here
        for child in ast.iter_child_nodes(current):
            if isinstance(child, _NESTED):
                continue
            yield from visit(child, here)

    yield from visit(node, ())


def _collect(
    body: list[ast.stmt], inherited: set[str], inherited_tests: set[str]
) -> tuple[set[str], set[str]]:
    names = set(inherited)
    tests = set(inherited_tests)
    for stmt in body:
        if isinstance(stmt, _NESTED):
            continue
        for child, _parents in _walk(stmt):
            name = _assigned_name(child)
            if not name or not isinstance(child, (ast.Assign, ast.AnnAssign)):
                continue
            value = child.value
            if value is None:
                continue
            if _is_source_read(value) or _call_name(value) == "getsource":
                names.add(name)
                if _is_source_read(value) and _is_test_path(value):
                    tests.add(name)
    return names, tests


def _expr_is_source(node: ast.AST, names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    return _is_source_read(node) or _call_name(node) == "getsource"


def _string_in_source(node: ast.Compare, names: set[str]) -> str | None:
    if len(node.ops) != 1 or not isinstance(node.ops[0], (ast.In, ast.NotIn)):
        return None
    if len(node.comparators) != 1:
        return None
    left, right = node.left, node.comparators[0]
    if (
        isinstance(left, ast.Constant)
        and isinstance(left.value, str)
        and _expr_is_source(right, names)
    ):
        return left.value
    if (
        isinstance(right, ast.Constant)
        and isinstance(right.value, str)
        and _expr_is_source(left, names)
    ):
        return right.value
    return None


def _record(found: list[tuple[int, str, str]], line: int, kind: str, target: str) -> None:
    found.append((line, kind, _target(target)))


def _filename_context(parents: tuple[ast.AST, ...]) -> bool:
    if not any(isinstance(item, (ast.Assert, ast.Assign, ast.AnnAssign)) for item in parents):
        return False
    return not any(_is_source_read(item) and _is_test_path(item) for item in parents)


def _scan_body(
    body: list[ast.stmt],
    names: set[str],
    tests: set[str],
    found: list[tuple[int, str, str]],
) -> None:
    for stmt in body:
        if isinstance(stmt, _NESTED):
            inner_names, inner_tests = _collect(stmt.body, names, tests)
            _scan_body(stmt.body, inner_names, inner_tests, found)
            continue
        for child, parents in _walk(stmt):
            _scan_child(child, parents, names, tests, found)


def _scan_child(
    child: ast.AST,
    parents: tuple[ast.AST, ...],
    names: set[str],
    tests: set[str],
    found: list[tuple[int, str, str]],
) -> None:
    if isinstance(child, ast.Call):
        called = _call_name(child)
        if called == "getsource" and child.args:
            _record(found, child.lineno, "getsource", _text(child.args[0]))
        elif called == "getdoc" and child.args:
            _record(found, child.lineno, "docstring", _text(child.args[0]))
        elif _is_source_read(child) and _is_test_path(child):
            _record(found, child.lineno, "test-of-test", _text(child))
        elif (
            called in _SOURCE_CALLS
            and child.args
            and isinstance(child.func, ast.Attribute)
            and _expr_is_source(child.func.value, names)
            and isinstance(child.args[0], ast.Constant)
            and isinstance(child.args[0].value, str)
        ):
            kind = "test-of-test" if _name_in(child.func.value, tests) else "source-string"
            _record(found, child.lineno, kind, child.args[0].value)
        return
    if isinstance(child, ast.Attribute) and child.attr == "__doc__":
        _record(found, child.lineno, "docstring", _text(child.value))
        return
    if isinstance(child, ast.Compare):
        pinned = _string_in_source(child, names)
        if pinned is None or _TEST_FILE.fullmatch(pinned.strip()):
            return
        kind = "test-of-test" if _compare_is_test(child, tests) else "source-string"
        _record(found, child.lineno, kind, pinned)
        return
    if isinstance(child, ast.ImportFrom):
        module = child.module or ""
        if module.split(".")[-1].startswith("test_"):
            _record(found, child.lineno, "test-of-test", module)
        return
    if isinstance(child, ast.Import):
        for alias in child.names:
            if alias.name.split(".")[-1].startswith("test_"):
                _record(found, child.lineno, "test-of-test", alias.name)
        return
    if (
        isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and _filename_context(parents)
    ):
        match = _TEST_FILE.search(child.value)
        if match:
            _record(found, child.lineno, "filename-pin", match.group(0))


def _name_in(node: ast.AST, tests: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in tests


def _compare_is_test(node: ast.Compare, tests: set[str]) -> bool:
    sides = (node.left, *node.comparators)
    return any(
        _name_in(side, tests) or (_is_source_read(side) and _is_test_path(side)) for side in sides
    )


def scan_file(path: Path, root: Path) -> list[tuple[str, int, str, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return []
    found: list[tuple[int, str, str]] = []
    names, tests = _collect(tree.body, set(), set())
    _scan_body(tree.body, names, tests, found)
    relative = path.relative_to(root).as_posix()
    return [(relative, line, kind, target) for line, kind, target in found]


def scan_tree(tests: Path) -> list[tuple[str, int, str, str]]:
    root = tests.parent
    rows: list[tuple[str, int, str, str]] = []
    for path in sorted(tests.rglob("*.py")):
        rows.extend(scan_file(path, root))
    rows.sort()
    return rows


def report(rows: list[tuple[str, int, str, str]]) -> str:
    lines = [f"{path}:{line} | {kind} | {target}" for path, line, kind, target in rows]
    counts = {kind: 0 for kind in KINDS}
    for _path, _line, kind, _target in rows:
        counts[kind] = counts.get(kind, 0) + 1
    detail = ", ".join(f"{kind} {counts[kind]}" for kind in KINDS)
    lines.append(f"pins: {len(rows)} ({detail})")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    default = Path(__file__).resolve().parent.parent / "tests"
    tests = Path(args[0]) if args else default
    if not tests.is_dir():
        sys.stdout.write(_EMPTY)
        return 0
    sys.stdout.write(report(scan_tree(tests)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
