"""The student-path skill stays on the public tree.

AC-ver-1, AC-ver-2, AC-ver-3, AC-ver-6, and AC-public-1.
Opaque ids name a deny-list hit. The phrases stay in the hashed lists.
"""

from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path

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
            f"{path.relative_to(REPO)} {opaque}" for opaque, digest in denied.items() if digest in digests
        )
    assert hits == []


def test_skill_names_the_student_path():
    """AC-ver-1 and AC-ver-2. Frontmatter, the six sections, and the helper command are in the skill."""
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "name: verify-essay-writer" in text
    assert "Essay Writer" in text
    assert "MCP" in text
    for heading in ("## Launch", "## Doctor", "## Drive", "## Evidence", "## Cleanup", "## Helpers"):
        assert heading in text
    assert "ESSAY_WRITER_ROOT" in text
    assert "0.9.17" in text
    assert "scripts/verify-essay-writer launch" in text
    assert "scripts/verify-essay-writer doctor" in text
    assert "scripts/verify-essay-writer drive-research-gather" in text
    assert "scripts/verify-essay-writer cleanup" in text
    assert HELPER.is_file()
    assert HELPER.stat().st_mode & 0o111


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
