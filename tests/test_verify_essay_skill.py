"""The student-path skill stays on the public tree.

AC-ver-1, AC-ver-2, AC-ver-3, AC-ver-4, AC-ver-5, AC-ver-6, AC-ver-7, and AC-public-1.
Opaque ids name a deny-list hit. The phrases stay in the hashed lists.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path

import essay_writer

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".cursor" / "skills" / "verify-essay-writer"
HELPER = SKILL / "scripts" / "verify-essay-writer"


def _grams(text: str) -> set[str]:
    folded = text.casefold()
    tokens = re.findall(r"[a-z0-9]+(?:[._+-][a-z0-9]+)*", folded)
    found = set(tokens)
    found.update(f"{left} {right}" for left, right in zip(tokens, tokens[1:], strict=False))
    found.update(line.strip() for line in folded.splitlines() if line.strip())
    return found


def _deny() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted((REPO / "tests").glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            target = None
            value = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                if isinstance(node.targets[0], ast.Name):
                    target = node.targets[0].id
                    value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target = node.target.id
                value = node.value
            if target != "_DENY" or not isinstance(value, ast.Dict):
                continue
            for key, item in zip(value.keys, value.values, strict=False):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(item, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(item.value, str)
                ):
                    found[f"{path.stem}:{key.value}"] = item.value
    return found


def test_skill_tree_stays_public():
    """AC-ver-6 and AC-public-1. The skill, helper, and feature map carry no deny-list phrase."""
    denied = _deny()
    assert denied
    hits: list[str] = []
    for path in sorted(SKILL.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        digests = {hashlib.sha256(gram.encode()).hexdigest() for gram in _grams(text)}
        hits.extend(
            f"{path.relative_to(REPO)} {opaque}"
            for opaque, digest in denied.items()
            if digest in digests
        )
    assert hits == []


def test_skill_names_the_student_path():
    """AC-ver-1 and AC-ver-2. Frontmatter, the six sections, and the helper command are in the skill."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: verify-essay-writer" in text
    assert "Essay Writer" in text
    assert "MCP" in text
    for heading in (
        "## Launch",
        "## Doctor",
        "## Drive",
        "## Evidence",
        "## Cleanup",
        "## Helpers",
    ):
        assert heading in text
    assert "ESSAY_WRITER_ROOT" in text
    assert essay_writer.__version__ in text
    assert "scripts/verify-essay-writer launch" in text
    assert "scripts/verify-essay-writer doctor" in text
    assert "scripts/verify-essay-writer drive-research-gather" in text
    assert "scripts/verify-essay-writer cleanup" in text
    assert HELPER.is_file()
    assert HELPER.stat().st_mode & 0o111


def _load_harness(env: dict[str, str] | None = None):
    previous: dict[str, str | None] = {}
    if env:
        for key, value in env.items():
            previous[key] = os.environ.get(key)
            os.environ[key] = value
    try:
        loader = importlib.machinery.SourceFileLoader(
            "essay_verify_harness_under_test", str(HELPER)
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    return module


def _function(tree: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(name)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
    return None


def _get_arg(node: ast.AST, key: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and _call_name(node) == "get"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == key
    )


def _compare_is_not_true(node: ast.AST, key: str) -> bool:
    return (
        isinstance(node, ast.Compare)
        and _get_arg(node.left, key)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is True
    )


def _body_fails(body: list[ast.stmt], code: int | None = None) -> bool:
    for statement in body:
        for node in ast.walk(statement):
            if _call_name(node) != "fail":
                continue
            if code is None:
                return True
            assert isinstance(node, ast.Call)
            for keyword in node.keywords:
                if (
                    keyword.arg == "code"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == code
                ):
                    return True
    return False


def test_silent_brief_floor_blocks_a_short_list():
    """AC-ver-4. A silent 2000-word brief keeps a floor of 16 distinct title-author-year works.

    OpenAlex is required. Consensus and Unpaywall follow the switches already set.
    A written citation list or essay draft below that floor, while further_page is still true, exits 2.
    """
    harness = _load_harness()
    assert harness.FLOOR_WORDS == 2000
    assert harness.FLOOR_COUNT == 16
    assert "2000 words" in harness.BRIEF
    assert "source" not in harness.BRIEF.casefold()
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    distinct = _function(tree, "distinct_records")
    skipped = False
    for node in ast.walk(distinct):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.BoolOp):
            continue
        if not isinstance(node.test.op, ast.Or):
            continue
        missing = {
            value.operand.id
            for value in node.test.values
            if isinstance(value, ast.UnaryOp)
            and isinstance(value.op, ast.Not)
            and isinstance(value.operand, ast.Name)
        }
        if missing == {"title", "author", "year"} and any(
            isinstance(item, ast.Continue) for item in node.body
        ):
            skipped = True
    assert skipped
    drive = _function(tree, "do_drive")
    short_uses_floor = False
    openalex_required = False
    consensus_follows_key = False
    short_list_exits_2 = False
    for node in ast.walk(drive):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            if node.targets[0].id == "short" and isinstance(node.value, ast.BoolOp):
                dumped = ast.dump(node.value)
                short_uses_floor = (
                    "FLOOR_COUNT" in dumped and "further_page" in dumped and "works" in dumped
                )
        if isinstance(node, ast.If) and _compare_is_not_true(node.test, "openalex_called"):
            openalex_required = _body_fails(node.body)
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.BoolOp)
            and isinstance(node.test.op, ast.And)
        ):
            dumped = ast.dump(node.test)
            if (
                "consensus_key" in dumped
                and "consensus_called" in dumped
                and "consensus_refused" in dumped
            ):
                consensus_follows_key = _body_fails(node.body)
            names: set[str] = set()
            for value in node.test.values:
                if isinstance(value, ast.Name):
                    names.add(value.id)
                elif isinstance(value, ast.BoolOp):
                    names.update(item.id for item in value.values if isinstance(item, ast.Name))
            if names == {"short", "wrote_list", "wrote_draft"}:
                short_list_exits_2 = _body_fails(node.body, code=2)
    assert short_uses_floor
    assert openalex_required
    assert consensus_follows_key
    assert short_list_exits_2
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "OpenAlex is called." in skill
    assert "Consensus is called when a key is already in the environment" in skill
    assert "`ESSAY_WRITER_CONSENSUS` is not `0`" in skill
    assert "Unpaywall runs only when an email is already in the environment." in skill
    assert "ESSAY_WRITER_CONSENSUS" in harness.FORWARDED
    assert "ESSAY_WRITER_UNPAYWALL_EMAIL" in harness.FORWARDED
    assert "CONSENSUS_API_KEY" in harness.FORWARDED
    assert "OPENALEX_API_KEY" in harness.FORWARDED


def test_cleanup_leaves_the_named_evidence():
    """AC-ver-5. The skill names launch, doctor, drive-research-gather, and cleanup.

    Cleanup removes the run folder and leaves the evidence files in place.
    """
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for command in (
        "scripts/verify-essay-writer launch",
        "scripts/verify-essay-writer doctor",
        "scripts/verify-essay-writer drive-research-gather",
        "scripts/verify-essay-writer cleanup",
    ):
        assert command in skill
    assert "does not delete `/opt/cursor/artifacts/verify-essay-writer/`." in skill
    with tempfile.TemporaryDirectory(prefix="essay-verify-ac-") as root:
        base = Path(root)
        evidence = base / "evidence"
        run = base / "run"
        evidence.mkdir()
        (run / "student").mkdir(parents=True)
        (run / "student" / "marker.txt").write_text("run", encoding="utf-8")
        (evidence / "keep.txt").write_text("keep", encoding="utf-8")
        for name in ("launch.json", "doctor.json", "research-gather.json"):
            (evidence / name).write_text("{}\n", encoding="utf-8")
        (evidence / "run-state.json").write_text(
            json.dumps(
                {
                    "student_root": str(run / "student"),
                    "kb1": str(run / "KB1"),
                    "run_dir": str(run),
                    "deps": str(run / "deps"),
                }
            ),
            encoding="utf-8",
        )
        harness = _load_harness(
            {
                "ESSAY_WRITER_EVIDENCE": str(evidence),
                "ESSAY_WRITER_VERIFY_RUN": str(run),
                "ESSAY_WRITER_ROOT": str(run / "student"),
                "ESSAY_WRITER_VERIFY_KB1": str(run / "KB1"),
                "ESSAY_WRITER_VERIFY_DEPS": str(run / "deps"),
            }
        )
        harness.cmd_cleanup()
        assert not run.exists()
        assert (evidence / "keep.txt").read_text(encoding="utf-8") == "keep"
        for name in ("launch.json", "doctor.json", "research-gather.json"):
            assert (evidence / name).is_file()
        note = (evidence / "cleanup.txt").read_text(encoding="utf-8")
        assert "Evidence files still present:" in note
        assert "keep.txt" in note


def test_package_version_matches_the_skill():
    """AC-ver-7. The package and the skill stay on the same version."""
    version = essay_writer.__version__
    project = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{version}"' in project
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")
    assert version in skill
    assert f'!= "{version}"' in helper
    assert f"Expected {version}." in helper


def test_feature_map_names_the_three_journeys():
    """AC-ver-3. The map has a readme and the three student-facing features."""
    readme = (SKILL / "features" / "README.md").read_text(encoding="utf-8")
    assert "research-gather.md" in readme
    assert "first-draft-word.md" in readme
    assert "stage-10-word.md" in readme
    for name in ("research-gather.md", "first-draft-word.md", "stage-10-word.md"):
        text = (SKILL / "features" / name).read_text(encoding="utf-8")
        assert "## Sub-features" in text
        assert "## How to get to it (user POV)" in text
        assert "## Driving it with verify-essay-writer" in text
        assert "## Gotchas" in text
