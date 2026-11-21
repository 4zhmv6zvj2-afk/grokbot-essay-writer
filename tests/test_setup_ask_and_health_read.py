"""Two tidy-ups: one setup ask, and one short "did health pass?" read.

The setup ask is written once in the shared setup block. Both host setup
prompts point at that block by token, and the front-office briefing and the
first-run text carry the same words, so the student still has one setup door.

Install, update, and attach read the same short health answer. The install
write stays on its own path and is never combined with the official check.

Ids are seated once. The id is the pytest id, the docstring, and the assert.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from essay_writer import update
from essay_writer.first_run_common import first_run_prompt
from essay_writer.first_run_install import install_self_check, install_uploaded_copy
from essay_writer.health import essay_health, health_read
from essay_writer.prompt_loader import raw, render_tokens, sections, text
from essay_writer.server import INSTRUCTIONS
from essay_writer.setup import CURSOR_SETUP_PROMPT, SETUP_PROMPT

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"

# The setup ask, in the public words the student and the operator read.
SETUP_ASK = (
    "Ordinary setup collects the Consensus key, the Consensus plan, the Unpaywall email, "
    "and the OpenAlex key on the setup secret card, then passes them to essay.setup."
)
SETUP_ASK_TOKEN = "{{install:ordinary_setup}}"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(name)


def _health_payload(version: str = "0.9.14") -> dict[str, object]:
    """An essay.health payload shaped like the official door's report."""
    return {
        "ok": True,
        "alive": True,
        "version": version,
        "doors": [{"id": "essay.health", "tool": "essay.health"}],
    }


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-tidy-setup-1", id="AC-ew-tidy-setup-1")],
)
def test_the_setup_ask_has_one_source_and_one_door(case_id: str) -> None:
    """AC-ew-tidy-setup-1: The setup ask has one source, and every copy stays the same, so the student still has one setup door."""
    assert case_id == "AC-ew-tidy-setup-1"
    block = sections("install/operator.md")["ordinary_setup"]
    assert block.startswith(SETUP_ASK)
    assert SETUP_ASK in block

    # The shared setup block is the only place the ask is written out. The two
    # host setup prompts point at it by token, so the ask has one source.
    operator = raw("install/operator.md")
    assert operator.count(SETUP_ASK) == 1
    assert operator.count(SETUP_ASK_TOKEN) == 2
    assert text("install/operator.md", "setup_prompt").count(SETUP_ASK_TOKEN) == 1
    assert text("install/operator.md", "cursor_setup_prompt").count(SETUP_ASK_TOKEN) == 1
    assert operator.count("## ordinary_setup") == 1
    assert render_tokens(SETUP_ASK_TOKEN) == block

    # The front-office briefing and the first-run text carry the same words,
    # so the student reads one setup ask, not a paraphrase.
    briefing = raw("front_office/briefing.md")
    first_run = first_run_prompt()
    for copy in (briefing, first_run):
        assert copy.count(block) == 1
    assert (REPO / "FIRST-RUN.txt").read_text(encoding="utf-8") == first_run

    # Every rendered copy says the same words, with no token left behind.
    for rendered in (SETUP_PROMPT, CURSOR_SETUP_PROMPT, INSTRUCTIONS, first_run):
        assert rendered.count(SETUP_ASK) == 1
        assert SETUP_ASK_TOKEN not in rendered

    # One setup door: the host prompts still call essay.setup, and no second
    # setup door was added to the catalogue.
    from essay_writer.doors import DOORS

    setup_doors = [door for door in DOORS if door["tool"].split(".")[-1] == "setup"]
    assert [door["tool"] for door in setup_doors] == ["essay.setup"]
    for prompt in (SETUP_PROMPT, CURSOR_SETUP_PROMPT):
        assert prompt.count("essay.setup") >= 2


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-tidy-health-1", id="AC-ew-tidy-health-1")],
)
def test_install_update_and_attach_share_the_short_health_read(
    case_id: str, tmp_path, workspace
) -> None:
    """AC-ew-tidy-health-1: Install, update, and attach share the short "did health pass?" read, without combining the install write with the official check."""
    assert case_id == "AC-ew-tidy-health-1"
    del workspace

    # The shared read answers from one payload and names the official door.
    read = health_read(_health_payload())
    assert read["ok"] is True
    assert read["tool"] == "essay.health"
    assert read["tool_count"] == 1
    failed = health_read({"ok": True, "alive": True, "version": "0.9.14", "doors": []})
    assert failed["ok"] is False
    assert (
        health_read({"ok": False, "alive": False, "doors": [{"tool": "essay.health"}]})["ok"]
        is False
    )

    # Attach reads it through the one self check.
    assert install_self_check()["tool"] == "essay.health"

    # Update reads it, so a payload with no doors is not a pass.
    for body in (_health_payload("9.9.9"), {"ok": True, "alive": True, "version": "9.9.9"}):
        assert health_read(body)["ok"] is bool(body.get("doors"))

    # Install reports the same read, and the install write is a separate step.
    source = _install_tree(tmp_path)
    result = install_uploaded_copy(
        source,
        pip_runner=lambda _command, _cwd: {"returncode": 0, "stdout": "", "stderr": ""},
        attach=False,
        path_exposer=lambda: None,
        allow_cursor_install=False,
    )
    assert result["ok"] is True, result
    assert result["health_check"]["tool"] == "essay.health"
    assert set(result["health_check"]) <= {"ok", "tool", "alive", "tool_count"}

    # The install function is the only writer of the install, and it does not
    # reach for the official door to write anything.
    install = inspect.getsource(install_uploaded_copy)
    assert "essay_health(" not in install
    assert "health_read(" not in install


def _install_tree(root: Path) -> Path:
    """A minimal project tree the uploaded-copy install accepts."""
    folder = root / "tree"
    folder.mkdir()
    (folder / "pyproject.toml").write_text(
        '[project]\nname = "essay-writer"\nversion = "0.9.14"\n', encoding="utf-8"
    )
    (folder / "FIRST-RUN.txt").write_text("prompt", encoding="utf-8")
    (folder / "requirements-runtime.txt").write_text(
        "mcp==2.3.0 --hash=sha256:" + "0" * 64 + "\n", encoding="utf-8"
    )
    return folder


def test_the_short_read_is_one_function_and_names_no_install() -> None:
    """One function answers "did health pass?", and no caller mixes that answer with the install write."""
    tree = ast.parse((PACKAGE / "health.py").read_text(encoding="utf-8"))
    readers = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "health_read"
    ]
    assert readers == ["health_read"]

    # The install report, the attach check, and the update check all read it.
    for module, names in (
        ("first_run_install.py", ("install_self_check", "_health_summary")),
        ("update.py", ("apply_update",)),
    ):
        source = (PACKAGE / module).read_text(encoding="utf-8")
        assert "health_read" in source, module
        for name in names:
            node = _function(PACKAGE / module, name)
            names_used = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
            assert "health_read" in names_used, name

    # The update applies the read after the pip steps, not inside them.
    apply_source = inspect.getsource(update.apply_update)
    assert apply_source.count("run_pip(") == 1
    assert apply_source.index("health_read(") > apply_source.index("run_pip(")
    assert apply_source.index("health_read(") > apply_source.index("with _update_lock():")


def test_the_short_read_matches_the_official_report(workspace) -> None:
    """A live essay.health report and the shared read agree on pass and door."""
    report = essay_health()
    read = health_read(report)
    assert read["ok"] is True
    assert read["alive"] is True
    assert read["tool"] == "essay.health"
    assert read["version"] == report["version"]
    assert read["tool_count"] == len(report["doors"])
    assert json.dumps(read, sort_keys=True)
