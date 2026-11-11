"""Ratchet: production code must not branch on the pytest process environment.

The stage-2 remediation removes `PYTEST_CURRENT_TEST` checks from production
modules. Behaviour must be injectable (an opener collaborator) or explicitly
selectable (a policy), so this guard bans the token under src/essay_writer.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "essay_writer"
TOKEN = "PYTEST_CURRENT_TEST"


def _hits() -> list[str]:
    hits: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            if TOKEN in line:
                hits.append(f"{path.relative_to(REPO)}:{number}: {line.strip()}")
    return hits


def test_no_pytest_env_branch_under_src():
    hits = _hits()
    assert not hits, (
        f"{TOKEN} must not appear under src/essay_writer. "
        "Inject the opener or pass an explicit policy instead:\n" + "\n".join(hits)
    )
