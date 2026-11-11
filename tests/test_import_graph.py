"""Static import-graph guard.

The walk covers every module under ``src/essay_writer``, including ``_vendor``
and package ``__init__`` files. Nothing is imported. Load edges are
module-level imports, with ``TYPE_CHECKING`` and function and class bodies
left out. ``from pkg import name`` also loads ``pkg.name`` when that submodule
exists, and a module-level import of a specialist ``__getattr__`` name loads
the mapped module. Deferred edges are function-body imports plus every
specialist ``__getattr__`` map entry.

The load graph stays a DAG. Deferred pairs that would cycle it, and direct
two-module mutual imports, are checked-in allowlists. Either allowlist may
shrink in the change that removes a pair. Neither may grow. A new direct
mutual pair fails even when both directions are deferred.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"
PACKAGE_NAME = "essay_writer"

# Directed (importer, imported). Hoisting any pair to module level cycles the
# load graph. Includes the map-only specialists.researcher → research edge.
CYCLE_BREAKERS: frozenset[tuple[str, str]] = frozenset(
    {
        ("assignment_gate", "brief_contract"),
        ("assignment_gate", "specialists.eqr"),
        ("assignment_gate", "specialists.writer"),
        ("build_office", "first_run"),
        ("cite_open", "research_packs"),
        ("debug_log", "health"),
        ("debug_log", "ml_events"),
        ("diary", "assignment_gate"),
        ("invent", "validate"),
        ("known_paths", "confirm"),
        ("pdf_read", "downloads"),
        ("pdf_year", "cite_open"),
        ("projects", "fo_chat_locks"),
        ("setup", "dig"),
        ("specialists.eqr", "review"),
        ("specialists.eqr", "word"),
        ("specialists.grok_bot", "fo_chat_locks"),
        ("specialists.grok_bot", "server"),
        ("specialists.grok_bot", "stage_llm"),
        ("specialists.researcher", "research"),
        ("state", "stage_state"),
        ("textutil", "assignment_gate"),
        ("textutil", "cite_fit"),
        ("textutil", "diary"),
        ("textutil", "harvard_4a"),
        ("textutil", "specialists.writer"),
        ("textutil", "validate"),
        ("user_place", "late_chain"),
    }
)

# Undirected pairs, stored sorted. load and defer both count.
MUTUAL_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("assignment_gate", "brief_contract"),
        ("assignment_gate", "diary"),
        ("assignment_gate", "specialists.eqr"),
        ("assignment_gate", "specialists.writer"),
        ("assignment_gate", "textutil"),
        ("assignment_handoff", "research_packs"),
        ("brief_contract", "validate"),
        ("build_office", "cursor_office"),
        ("build_status", "specialists.grok_bot"),
        ("cite_fit", "textutil"),
        ("cite_fit", "word_references"),
        ("cite_open", "pdf_year"),
        ("cite_open", "research_packs"),
        ("debug_log", "health"),
        ("debug_log", "late_chain"),
        ("debug_log", "ml_events"),
        ("diary", "textutil"),
        ("dig", "setup"),
        ("downloads", "pdf_read"),
        ("downloads", "research_packs"),
        ("downloads", "roll_forward"),
        ("fo_chat_locks", "projects"),
        ("gates", "specialists.writer"),
        ("harvard_4a", "textutil"),
        ("harvard_ref_check", "late_chain"),
        ("harvard_ref_check", "review"),
        ("invent", "textutil"),
        ("invent", "validate"),
        ("late_chain", "ml_events"),
        ("late_chain", "review"),
        ("late_chain", "specialists.eqr"),
        ("late_chain", "user_place"),
        ("late_chain", "word"),
        ("pack_backup", "validate"),
        ("projects", "specialists.grok_bot"),
        ("research", "specialists.researcher"),
        ("review", "specialists.eqr"),
        ("rewrite_baseline", "specialists.writer"),
        ("server", "shells"),
        ("specialists.eqr", "specialists.grok_bot"),
        ("specialists.eqr", "word"),
        ("specialists.grok_bot", "stage_llm"),
        ("specialists.writer", "textutil"),
        ("specialists.writer", "validate"),
        ("specialists.writer", "word"),
        ("textutil", "validate"),
    }
)

STAGE_LAYERS = frozenset(
    {
        "stage_body",
        "stage_confirm",
        "stage_hold",
        "stage_landing",
        "stage_note",
        "stage_replies",
        "stage_state",
    }
)
STAGE_TRACK_IMPORTS = (
    ("projects", "function", ("_run_card_only",)),
    ("server", "module", ("essay_stage",)),
)


class ImportGraph(NamedTuple):
    modules: frozenset[str]
    load_edges: frozenset[tuple[str, str]]
    deferred_edges: frozenset[tuple[str, str]]
    stage_track_imports: tuple[tuple[str, str, tuple[str, ...]], ...]


def _module_id(path: Path) -> str:
    parts = list(path.relative_to(PACKAGE).parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        if not parts:
            return "__init__"
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _modules() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in PACKAGE.rglob("*.py"):
        module_id = _module_id(path)
        if module_id in found:
            raise AssertionError(f"two files share the module id {module_id}")
        found[module_id] = path
    return found


def _string(node: ast.AST | None) -> str:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise AssertionError("specialist map entry is not a string")
    return node.value


def _assigned(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return node.value
    raise AssertionError(f"missing {name}")


def _internal_id(dotted: str) -> str:
    prefix = PACKAGE_NAME + "."
    if not dotted.startswith(prefix):
        raise AssertionError(f"{dotted} is outside the package")
    return dotted[len(prefix) :]


def _getattr_function(tree: ast.Module) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "__getattr__":
            return node
    raise AssertionError("missing __getattr__")


def _dict_map(tree: ast.Module, name: str) -> dict[str, str]:
    value = _assigned(tree, name)
    if not isinstance(value, ast.Dict):
        raise AssertionError(f"{name} is not a dict")
    found: dict[str, str] = {}
    for key, item in zip(value.keys, value.values, strict=True):
        found[_string(key)] = _internal_id(_string(item))
    if not found:
        raise AssertionError(f"{name} is empty")
    return found


def _set_names(tree: ast.Module, name: str) -> set[str]:
    value = _assigned(tree, name)
    if not isinstance(value, ast.Set):
        raise AssertionError(f"{name} is not a set")
    names = {_string(elt) for elt in value.elts}
    if not names:
        raise AssertionError(f"{name} is empty")
    return names


def _imported_module(node: ast.ImportFrom) -> str | None:
    """Package-relative module named by a ``from`` import, if it is internal."""
    if node.level:
        return None
    module = node.module or ""
    if module == PACKAGE_NAME:
        return "__init__"
    prefix = PACKAGE_NAME + "."
    if module.startswith(prefix):
        return module[len(prefix) :]
    return None


def _first_draft_blockers_target(fn: ast.FunctionDef) -> str:
    """Module loaded for the writer map's special-cased name."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare):
            continue
        if not (
            isinstance(test.left, ast.Name)
            and test.left.id == "name"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "first_draft_blockers"
        ):
            continue
        for child in node.body:
            for statement in ast.walk(child):
                if not isinstance(statement, ast.ImportFrom):
                    continue
                if any(alias.name == "first_draft_blockers" for alias in statement.names):
                    target = _imported_module(statement)
                    if target is None or target == "__init__":
                        raise AssertionError("first_draft_blockers import is not internal")
                    return target
    raise AssertionError("writer __getattr__ does not import first_draft_blockers")


def _review_target(fn: ast.FunctionDef, modules: set[str]) -> str:
    """Submodule loaded by eqr ``__getattr__`` for every ``_REVIEW`` name."""
    for node in ast.walk(fn):
        if not isinstance(node, ast.ImportFrom):
            continue
        if _imported_module(node) != "__init__":
            continue
        for alias in node.names:
            if alias.name in modules:
                return alias.name
    raise AssertionError("eqr __getattr__ does not import a package submodule")


def _specialist_maps(files: dict[str, Path]) -> dict[str, dict[str, str]]:
    """Attribute name to internal module, for the three specialist maps."""
    researcher = ast.parse(files["specialists.researcher"].read_text(encoding="utf-8"))
    writer = ast.parse(files["specialists.writer"].read_text(encoding="utf-8"))
    eqr = ast.parse(files["specialists.eqr"].read_text(encoding="utf-8"))
    maps = {
        "specialists.researcher": _dict_map(researcher, "_HOME"),
        "specialists.writer": _dict_map(writer, "_WORD"),
        "specialists.eqr": {},
    }
    blockers = _first_draft_blockers_target(_getattr_function(writer))
    maps["specialists.writer"]["first_draft_blockers"] = blockers
    review = _review_target(_getattr_function(eqr), set(files))
    maps["specialists.eqr"] = {name: review for name in _set_names(eqr, "_REVIEW")}
    for mapping in maps.values():
        for target in mapping.values():
            if target not in files:
                raise AssertionError(f"map target {target} is not a module")
    return maps


def _is_type_checking(test: ast.AST) -> bool:
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


class _Walker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.function_depth = 0
        self.class_depth = 0
        self.type_checking_depth = 0
        self.records: list[tuple[str, ast.Import | ast.ImportFrom]] = []

    def _enter_function(self, node: ast.AST) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_depth += 1
        self.generic_visit(node)
        self.class_depth -= 1

    def visit_If(self, node: ast.If) -> None:
        if _is_type_checking(node.test):
            self.type_checking_depth += 1
            for statement in node.body:
                self.visit(statement)
            self.type_checking_depth -= 1
            for statement in node.orelse:
                self.visit(statement)
            return
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._keep(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._keep(node)

    def _keep(self, node: ast.Import | ast.ImportFrom) -> None:
        if self.type_checking_depth:
            kind = "type-checking"
        elif self.function_depth:
            kind = "function"
        elif self.class_depth:
            kind = "class"
        else:
            kind = "module"
        self.records.append((kind, node))


def _package_parts(module: str, packages: set[str]) -> list[str]:
    if module == "__init__":
        return []
    parts = module.split(".")
    if module in packages:
        return parts
    return parts[:-1]


def _resolve_from(current: str, node: ast.ImportFrom, packages: set[str]) -> str | None:
    if node.level == 0:
        return _imported_module(node)
    parts = _package_parts(current, packages)
    drop = node.level - 1
    if drop > len(parts):
        return None
    base = parts[: len(parts) - drop]
    if node.module:
        base.extend(node.module.split("."))
    if not base:
        return "__init__"
    return ".".join(base)


def _targets(
    current: str,
    node: ast.Import | ast.ImportFrom,
    modules: set[str],
    packages: set[str],
    maps: dict[str, dict[str, str]],
    *,
    trigger_maps: bool,
) -> list[str]:
    found: list[str] = []

    def add(name: str | None) -> None:
        if name is not None and name in modules and name not in found:
            found.append(name)

    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == PACKAGE_NAME:
                add("__init__")
            elif alias.name.startswith(PACKAGE_NAME + "."):
                add(alias.name[len(PACKAGE_NAME) + 1 :])
        return found

    base = _resolve_from(current, node, packages)
    if base is None:
        return found
    add(base)
    for alias in node.names:
        if alias.name == "*":
            continue
        submodule = alias.name if base == "__init__" else f"{base}.{alias.name}"
        if submodule in modules:
            add(submodule)
        if trigger_maps and base in maps and alias.name in maps[base]:
            add(maps[base][alias.name])
    return found


def _import_names(node: ast.Import | ast.ImportFrom) -> tuple[str, ...]:
    return tuple(alias.name for alias in node.names)


def import_graph() -> ImportGraph:
    files = _modules()
    modules = set(files)
    packages = {name for name, path in files.items() if path.name == "__init__.py"}
    maps = _specialist_maps(files)
    load: set[tuple[str, str]] = set()
    deferred: set[tuple[str, str]] = set()
    stage_hits: list[tuple[str, str, tuple[str, ...]]] = []
    for module_id, path in files.items():
        walker = _Walker()
        walker.visit(ast.parse(path.read_text(encoding="utf-8")))
        for kind, node in walker.records:
            targets = _targets(
                module_id,
                node,
                modules,
                packages,
                maps,
                trigger_maps=kind == "module",
            )
            for target in targets:
                if kind == "module":
                    load.add((module_id, target))
                elif kind == "function":
                    deferred.add((module_id, target))
            if "stage_track" in targets:
                stage_hits.append((module_id, kind, _import_names(node)))
    for module_id, mapping in maps.items():
        for target in set(mapping.values()):
            deferred.add((module_id, target))
    return ImportGraph(
        modules=frozenset(modules),
        load_edges=frozenset(load),
        deferred_edges=frozenset(deferred),
        stage_track_imports=tuple(sorted(stage_hits)),
    )


def _components(nodes: frozenset[str], edges: frozenset[tuple[str, str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    adjacent: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        adjacent[source].append(target)
    components: list[list[str]] = []

    def strong(node: str) -> None:
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in adjacent[node]:
            if nxt not in indices:
                strong(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], indices[nxt])
        if low[node] == indices[node]:
            component: list[str] = []
            while True:
                nxt = stack.pop()
                on_stack.remove(nxt)
                component.append(nxt)
                if nxt == node:
                    break
            components.append(component)

    for node in sorted(nodes):
        if node not in indices:
            strong(node)
    return components


def _reaches(start: str, goal: str, adjacent: dict[str, set[str]]) -> bool:
    seen: set[str] = set()
    pending = list(adjacent.get(start, ()))
    while pending:
        node = pending.pop()
        if node == goal:
            return True
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacent.get(node, ()))
    return False


def _cycle_breakers(graph: ImportGraph) -> set[tuple[str, str]]:
    adjacent: dict[str, set[str]] = defaultdict(set)
    for source, target in graph.load_edges:
        adjacent[source].add(target)
    return {
        (source, target)
        for source, target in graph.deferred_edges
        if source != target
        and (source, target) not in graph.load_edges
        and _reaches(target, source, adjacent)
    }


def _mutual_pairs(edges: frozenset[tuple[str, str]]) -> set[tuple[str, str]]:
    present = set(edges)
    pairs: set[tuple[str, str]] = set()
    for source, target in present:
        if source < target and (target, source) in present:
            pairs.add((source, target))
    return pairs


def _pair_diff(measured: set[tuple[str, str]], allowed: frozenset[tuple[str, str]]) -> str:
    added = sorted(measured - allowed)
    missing = sorted(allowed - measured)
    return f"added {added}; missing {missing}"


def test_the_walk_covers_vendor_and_package_inits() -> None:
    graph = import_graph()
    files = list(PACKAGE.rglob("*.py"))
    assert len(graph.modules) == len(files)
    assert "__init__" in graph.modules
    assert "_vendor" in graph.modules
    assert "_vendor.python_mcp_bootstrap" in graph.modules
    assert "specialists" in graph.modules
    assert "tools" in graph.modules
    assert "prompts" in graph.modules


def test_load_graph_is_a_dag() -> None:
    graph = import_graph()
    self_imports = sorted(edge for edge in graph.load_edges if edge[0] == edge[1])
    assert self_imports == []
    multi = [
        tuple(sorted(component))
        for component in _components(graph.modules, graph.load_edges)
        if len(component) > 1
    ]
    assert multi == []


def test_cycle_breaking_deferred_pairs_match_the_allowlist() -> None:
    measured = _cycle_breakers(import_graph())
    assert measured == CYCLE_BREAKERS, _pair_diff(measured, CYCLE_BREAKERS)


def test_direct_mutual_pairs_match_the_allowlist() -> None:
    graph = import_graph()
    measured = _mutual_pairs(graph.load_edges | graph.deferred_edges)
    assert measured == MUTUAL_PAIRS, _pair_diff(measured, MUTUAL_PAIRS)


def test_stage_track_is_imported_only_by_server_and_projects() -> None:
    graph = import_graph()
    assert graph.stage_track_imports == STAGE_TRACK_IMPORTS


def test_stage_layers_do_not_import_stage_track() -> None:
    graph = import_graph()
    offenders = [hit for hit in graph.stage_track_imports if hit[0] in STAGE_LAYERS]
    assert offenders == []
