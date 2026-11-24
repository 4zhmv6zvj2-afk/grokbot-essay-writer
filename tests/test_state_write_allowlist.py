"""Direct writes that are not a saved state file.

A new ``write_text``, ``write_bytes``, ``shutil.copy2``, or ``shutil.copyfile``
under ``src/essay_writer`` fails this test until the write goes through
``durable.replace_bytes`` or the reason is added here. Append logs, a
download, an archive extract, a staging tree, and a photo note that waits
for its photo stay on this list. A copy that truncates an existing file is
not hidden by using ``shutil``.
"""

from pathlib import Path

ROOT = Path(__file__).parents[1] / "src" / "essay_writer"

ALLOWED = {
    "debug_log.py": "append log header, not a state file",
    "ml_events.py": "append log header, not a state file",
    "update.py": "downloaded installer body, not sequence state",
    "first_run_install.py": "archive extract into a new tree",
    "_vendor/python_mcp_bootstrap.py": "vendored pin file, not sequence state",
    "pack_backup.py": "bytes inside a staging directory published by rename",
    "intake.py": "photo note published only after the photo file has moved",
}


def test_direct_writes_stay_on_the_allowlist():
    found = set()
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(
            needle in text
            for needle in ("write_text(", "write_bytes(", "shutil.copy2(", "shutil.copyfile(")
        ):
            found.add(path.relative_to(ROOT).as_posix())
    assert found == set(ALLOWED)
