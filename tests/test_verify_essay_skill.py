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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    assert "installed package version" in text
    assert essay_writer.__version__ not in text
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
    assert "does not delete `/tmp/essay-verify-evidence/`." in skill
    run = Path("/tmp") / f"essay-verify-ac-{os.getpid()}"
    evidence = Path("/tmp") / f"essay-verify-evidence-ac-{os.getpid()}"
    if run.exists():
        shutil.rmtree(run)
    if evidence.exists():
        shutil.rmtree(evidence)
    token = "ac-marker"
    try:
        evidence.mkdir()
        (run / "student").mkdir(parents=True)
        (run / ".essay-verify-created").write_text(token + "\n", encoding="utf-8")
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
                    "marker": token,
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
    finally:
        if run.exists():
            shutil.rmtree(run)
        if evidence.exists():
            shutil.rmtree(evidence)


def test_package_version_matches_the_skill():
    """AC-ver-7. The package version has one source. The skill does not copy the number."""
    version = essay_writer.__version__
    project = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{version}"' in project
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")
    assert "installed package version" in skill
    assert version not in skill
    assert version not in helper
    assert "package_version()" in helper
    assert "Expected {expected}." in helper


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


def _outside(tmp_path: Path) -> dict[str, str]:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    return {
        "ESSAY_WRITER_EVIDENCE": str(evidence),
        "ESSAY_WRITER_ROOT": str(tmp_path / "student"),
        "ESSAY_WRITER_VERIFY_KB1": str(tmp_path / "KB1"),
        "ESSAY_WRITER_VERIFY_DEPS": str(tmp_path / "deps"),
        "ESSAY_WRITER_VERIFY_RUN": str(tmp_path / "essay-verify-run"),
    }


def _proof(evidence: Path, run: Path, token: str, pid: int | None = None) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ("launch.json", "doctor.json", "research-gather.json", "keep.txt"):
        (evidence / name).write_text("keep\n", encoding="utf-8")
    body: dict[str, object] = {
        "student_root": str(run / "student"),
        "kb1": str(run / "KB1"),
        "run_dir": str(run),
        "deps": str(run / "deps"),
        "marker": token,
    }
    if pid is not None:
        body["server_pid"] = pid
    (evidence / "run-state.json").write_text(json.dumps(body), encoding="utf-8")


def test_cleanup_refuses_a_shared_parent(tmp_path: Path):
    """A run dir that is the parent of the student folder is not deleted."""
    docs = tmp_path / "Documents"
    student = docs / "student"
    student.mkdir(parents=True)
    (docs / "KB1").mkdir()
    (docs / "keep-me.txt").write_text("stay", encoding="utf-8")
    (docs / ".essay-verify-created").write_text("parent-token\n", encoding="utf-8")
    evidence = tmp_path / "evidence"
    _proof(evidence, docs, "parent-token")
    harness = _load_harness(
        {
            "ESSAY_WRITER_EVIDENCE": str(evidence),
            "ESSAY_WRITER_ROOT": str(student),
            "ESSAY_WRITER_VERIFY_KB1": str(docs / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(docs / "deps"),
            "ESSAY_WRITER_VERIFY_RUN": str(tmp_path / "essay-verify-run"),
        }
    )
    harness.launch_paths()
    assert harness.RUN_DIR.resolve() != docs.resolve()
    with pytest.raises(SystemExit):
        harness.cmd_cleanup()
    assert (docs / "keep-me.txt").read_text(encoding="utf-8") == "stay"
    assert student.is_dir()


def test_a_preexisting_directory_is_left_in_place(tmp_path: Path):
    """Launch does not claim a directory this script did not create."""
    run = tmp_path / "already"
    run.mkdir()
    (run / "keep.txt").write_text("stay", encoding="utf-8")
    harness = _load_harness(_outside(tmp_path))
    with pytest.raises(SystemExit):
        harness.claim_run_dir(run)
    assert (run / "keep.txt").read_text(encoding="utf-8") == "stay"
    assert list(run.iterdir()) == [run / "keep.txt"]


def test_cleanup_refuses_a_missing_marker():
    """A verify-shaped directory without the launch marker stays in place."""
    run = Path("/tmp") / f"essay-verify-missing-{os.getpid()}"
    evidence = Path("/tmp") / f"essay-verify-evidence-missing-{os.getpid()}"
    if run.exists():
        shutil.rmtree(run)
    if evidence.exists():
        shutil.rmtree(evidence)
    try:
        (run / "student").mkdir(parents=True)
        (run / "keep.txt").write_text("stay", encoding="utf-8")
        _proof(evidence, run, "absent-token")
        harness = _load_harness(
            {
                "ESSAY_WRITER_EVIDENCE": str(evidence),
                "ESSAY_WRITER_VERIFY_RUN": str(run),
                "ESSAY_WRITER_ROOT": str(run / "student"),
                "ESSAY_WRITER_VERIFY_KB1": str(run / "KB1"),
                "ESSAY_WRITER_VERIFY_DEPS": str(run / "deps"),
            }
        )
        with pytest.raises(SystemExit):
            harness.cmd_cleanup()
        assert (run / "keep.txt").read_text(encoding="utf-8") == "stay"
    finally:
        if run.exists():
            shutil.rmtree(run)
        if evidence.exists():
            shutil.rmtree(evidence)


def test_cleanup_refuses_a_run_dir_that_overlaps_evidence(tmp_path: Path):
    """Cleanup leaves a run directory that sits inside the evidence directory or contains it."""
    evidence = tmp_path / "evidence"
    inside = evidence / "essay-verify-inside"
    inside.mkdir(parents=True)
    token = "overlap-token"
    (inside / ".essay-verify-created").write_text(token + "\n", encoding="utf-8")
    (inside / "keep.txt").write_text("stay", encoding="utf-8")
    _proof(evidence, inside, token)
    harness = _load_harness(
        {
            "ESSAY_WRITER_EVIDENCE": str(evidence),
            "ESSAY_WRITER_VERIFY_RUN": str(inside),
            "ESSAY_WRITER_ROOT": str(inside / "student"),
            "ESSAY_WRITER_VERIFY_KB1": str(inside / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(inside / "deps"),
        }
    )
    harness.EXPLICIT_RUN_DIR = inside.resolve()
    with pytest.raises(SystemExit):
        harness.cmd_cleanup()
    assert (inside / "keep.txt").read_text(encoding="utf-8") == "stay"

    outer = tmp_path / "essay-verify-outer"
    nested = outer / "evidence"
    outer.mkdir()
    (outer / ".essay-verify-created").write_text(token + "\n", encoding="utf-8")
    (outer / "keep.txt").write_text("stay", encoding="utf-8")
    _proof(nested, outer, token)
    harness = _load_harness(
        {
            "ESSAY_WRITER_EVIDENCE": str(nested),
            "ESSAY_WRITER_VERIFY_RUN": str(outer),
            "ESSAY_WRITER_ROOT": str(outer / "student"),
            "ESSAY_WRITER_VERIFY_KB1": str(outer / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(outer / "deps"),
        }
    )
    harness.EXPLICIT_RUN_DIR = outer.resolve()
    with pytest.raises(SystemExit):
        harness.cmd_cleanup()
    assert (outer / "keep.txt").read_text(encoding="utf-8") == "stay"


def test_cleanup_removes_only_the_explicit_run_dir(tmp_path: Path):
    """--run-dir removes that directory and leaves its parent."""
    parent = tmp_path / "Documents"
    run = parent / "student-run"
    evidence = tmp_path / "evidence"
    token = "explicit-marker"
    parent.mkdir()
    (parent / "keep.txt").write_text("stay", encoding="utf-8")
    (run / "student").mkdir(parents=True)
    (run / ".essay-verify-created").write_text(token + "\n", encoding="utf-8")
    _proof(evidence, run, token)
    harness = _load_harness(
        {
            "ESSAY_WRITER_EVIDENCE": str(evidence),
            "ESSAY_WRITER_VERIFY_RUN": str(run),
            "ESSAY_WRITER_ROOT": str(run / "student"),
            "ESSAY_WRITER_VERIFY_KB1": str(run / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(run / "deps"),
        }
    )
    with pytest.raises(SystemExit):
        harness.cmd_cleanup()
    assert (parent / "keep.txt").read_text(encoding="utf-8") == "stay"
    assert run.is_dir()
    harness.EXPLICIT_RUN_DIR = run.resolve()
    harness.cmd_cleanup()
    assert not run.exists()
    assert (parent / "keep.txt").read_text(encoding="utf-8") == "stay"
    assert (evidence / "keep.txt").read_text(encoding="utf-8") == "keep\n"


def test_cleanup_stops_the_stored_server_and_leaves_another_process():
    """The stored pid is stopped when its command is essay_writer. Another process stays."""
    run = Path("/tmp") / f"essay-verify-pid-{os.getpid()}"
    evidence = Path("/tmp") / f"essay-verify-evidence-pid-{os.getpid()}"
    target = None
    decoy = None
    try:
        if run.exists():
            shutil.rmtree(run)
        if evidence.exists():
            shutil.rmtree(evidence)
        token = "pid-marker"
        (run / "student").mkdir(parents=True)
        (run / ".essay-verify-created").write_text(token + "\n", encoding="utf-8")
        target = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)", "-m", "essay_writer"],
            start_new_session=True,
        )
        decoy = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        _proof(evidence, run, token, pid=target.pid)
        harness = _load_harness(
            {
                "ESSAY_WRITER_EVIDENCE": str(evidence),
                "ESSAY_WRITER_VERIFY_RUN": str(run),
                "ESSAY_WRITER_ROOT": str(run / "student"),
                "ESSAY_WRITER_VERIFY_KB1": str(run / "KB1"),
                "ESSAY_WRITER_VERIFY_DEPS": str(run / "deps"),
            }
        )
        assert "essay_writer" not in harness.process_command(decoy.pid)
        assert harness.current_server_pid() == target.pid
        assert "/proc" not in HELPER.read_text(encoding="utf-8")
        harness.cmd_cleanup()
        assert target.wait(timeout=5) is not None or target.poll() is not None
        assert decoy.poll() is None
        assert not run.exists()
    finally:
        for proc in (target, decoy):
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
        if run.exists():
            shutil.rmtree(run)
        if evidence.exists():
            shutil.rmtree(evidence)


def test_a_missing_deps_dir_inside_the_checkout_is_refused(tmp_path: Path):
    """The dependency check runs before the folder exists."""
    missing = REPO / "deps-not-created"
    assert not missing.exists()
    env = _outside(tmp_path)
    env["ESSAY_WRITER_VERIFY_DEPS"] = str(missing)
    harness = _load_harness(env)
    with pytest.raises(SystemExit):
        harness.launch_paths()
    assert not missing.exists()


def test_evidence_defaults_to_tmp_and_the_override_is_kept(tmp_path: Path, monkeypatch):
    """The evidence root is a tmp path unless ESSAY_WRITER_EVIDENCE names another."""
    monkeypatch.delenv("ESSAY_WRITER_EVIDENCE", raising=False)
    harness = _load_harness()
    assert harness.EVIDENCE == harness.tmp_root() / "essay-verify-evidence"
    chosen = tmp_path / "proof"
    over = _load_harness({"ESSAY_WRITER_EVIDENCE": str(chosen)})
    assert over.EVIDENCE == chosen


def test_deps_install_uses_the_hashed_runtime_file():
    """Runtime packages come from the hash-pinned requirements file."""
    harness = _load_harness()
    cmd = harness.deps_install_command()
    assert "--require-hashes" in cmd
    assert str(REPO / "requirements-runtime.txt") in cmd
    helper = HELPER.read_text(encoding="utf-8")
    assert "mcp==" not in helper
    assert "DEPS.exists() or True" not in helper


def test_doctor_requires_alive_and_the_four_doors(tmp_path: Path, monkeypatch):
    """A mounted essay.dig is not enough. Alive and the other three doors are required."""
    student = tmp_path / "student"
    (student / "Essay-writer").mkdir(parents=True)
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    harness = _load_harness(
        {
            "ESSAY_WRITER_EVIDENCE": str(evidence),
            "ESSAY_WRITER_ROOT": str(student),
            "ESSAY_WRITER_VERIFY_KB1": str(tmp_path / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(tmp_path / "deps"),
            "ESSAY_WRITER_VERIFY_RUN": str(tmp_path / "essay-verify-run"),
        }
    )
    harness.launch_paths()

    def report(**overrides: object) -> dict[str, object]:
        body: dict[str, object] = {
            "ok": True,
            "alive": True,
            "version": harness.package_version(),
            "app_path": str(harness.STUDENT),
            "has_dig": True,
            "has_health": True,
            "has_research_full": True,
            "has_render_word": True,
            "door_count": 4,
            "consensus_enabled": False,
            "openalex_key_present": False,
            "unpaywall_email_present": False,
        }
        body.update(overrides)
        return body

    def answer(body: dict[str, object]):
        def run(coro):
            coro.close()
            return body

        return run

    monkeypatch.setattr(harness.asyncio, "run", answer(report(has_render_word=False)))
    with pytest.raises(SystemExit):
        harness.cmd_doctor()
    assert not (evidence / "doctor.json").exists()
    monkeypatch.setattr(harness.asyncio, "run", answer(report(alive=False, has_render_word=True)))
    with pytest.raises(SystemExit):
        harness.cmd_doctor()
    monkeypatch.setattr(harness.asyncio, "run", answer(report()))
    harness.cmd_doctor()
    assert (evidence / "doctor.json").is_file()


def test_saved_sources_keep_the_product_id(tmp_path: Path):
    """A minted DOI id stays, and a stored id is not replaced by a later DOI or by src-n."""
    student = tmp_path / "student"
    uploads = student / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "one.txt").write_text("ports move coastal trade\n", encoding="utf-8")
    (uploads / "two.txt").write_text("ports stay in coastal trade\n", encoding="utf-8")
    previous = os.environ.get("ESSAY_WRITER_ROOT")
    os.environ["ESSAY_WRITER_ROOT"] = str(student)
    try:
        from essay_writer.paths import work_dir

        root = work_dir("MOD1004AA-1")
        root.mkdir(parents=True, exist_ok=True)
        (root / "citation-list.json").write_text(
            json.dumps(
                {"entries": [{"locator": "uploads/two.txt", "source_id": "doi:10.1000/kept"}]}
            ),
            encoding="utf-8",
        )
    finally:
        if previous is None:
            os.environ.pop("ESSAY_WRITER_ROOT", None)
        else:
            os.environ["ESSAY_WRITER_ROOT"] = previous
    harness = _load_harness(
        {
            "ESSAY_WRITER_ROOT": str(student),
            "ESSAY_WRITER_EVIDENCE": str(tmp_path / "evidence"),
            "ESSAY_WRITER_VERIFY_KB1": str(tmp_path / "KB1"),
            "ESSAY_WRITER_VERIFY_DEPS": str(tmp_path / "deps"),
            "ESSAY_WRITER_VERIFY_RUN": str(tmp_path / "essay-verify-run"),
        }
    )
    fresh = harness.saved_sources(
        {
            "abstract_files": [
                {
                    "locator": "uploads/one.txt",
                    "author": "Ada Lane",
                    "year": "2020",
                    "title": "Ports and trade",
                    "doi": "10.1000/one",
                }
            ]
        },
        "MOD1004AA-1",
    )
    kept = harness.saved_sources(
        {
            "pdf_files": [
                {
                    "locator": "uploads/two.txt",
                    "author": "Bea Quay",
                    "year": "2021",
                    "title": "A later title",
                    "doi": "10.9999/other",
                }
            ]
        },
        "MOD1004AA-1",
    )
    assert fresh[0]["id"] == "doi:10.1000/one"
    assert kept[0]["id"] == "doi:10.1000/kept"
    tied = harness.tied_sources(fresh + kept)
    assert [item["id"] for item in tied] == ["doi:10.1000/one", "doi:10.1000/kept"]


def test_skill_docs_match_the_script():
    """The skill names the same doors, install, and evidence path as the script."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for door in ("essay.dig", "essay.health", "essay.research.full", "essay.pack.render_word"):
        assert door in text
    assert "/tmp/essay-verify-evidence" in text
    assert "requirements-runtime.txt" in text
    assert "--require-hashes" in text
    assert "--run-dir" in text
    for path in SKILL.rglob("*.md"):
        body = path.read_text(encoding="utf-8")
        assert "/opt/cursor/artifacts" not in body
        assert essay_writer.__version__ not in body
    helper = HELPER.read_text(encoding="utf-8")
    assert "mcp==" not in helper
    assert "/proc" not in helper
    assert 'f"src-' not in helper


def test_ci_compiles_the_verify_script():
    """The extensionless helper is compiled, and the gates lint that path."""
    script = ".cursor/skills/verify-essay-writer/scripts/verify-essay-writer"
    completed = subprocess.run(
        [sys.executable, "-m", "py_compile", str(HELPER)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    gates = (REPO / "tools" / "run_gates.py").read_text(encoding="utf-8")
    assert f"py_compile {script}" in ci
    assert script in gates
    assert "py_compile" in gates
