"""Direct writes that are not a saved state file.

A new ``write_text``, ``write_bytes``, ``shutil.copy2``, ``shutil.copyfile``,
``shutil.move``, ``Path.touch``, ``os.write``, or ``open(..., "w")`` under
``src/essay_writer`` fails this test until the write goes through
``durable.replace_bytes`` or the reason is added here. Append logs, a
download, an archive extract, a staging tree, a photo move, the replace
helper's own temp write, and secret files created at 0600 stay on this list.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1] / "src" / "essay_writer"

ALLOWED = {
    "debug_log.py": "append log header, not a state file",
    "ml_events.py": "append log header, not a state file",
    "update.py": "downloaded installer body, not sequence state",
    "first_run_install.py": "archive extract into a new tree",
    "_vendor/python_mcp_bootstrap.py": "vendored pin file, not sequence state",
    "pack_backup.py": "bytes inside a staging directory published by rename",
    "intake.py": "a photo or upload is moved into place, and the note waits for the photo",
    "durable.py": "the replace helper writes its temp with os.write, then renames",
    "paths.py": "a secret file is created at 0600 in place",
    "setup.py": "a secret file is created at 0600 in place",
}

_NEEDLES = (
    "write_text(",
    "write_bytes(",
    "shutil.copy2(",
    "shutil.copyfile(",
    "shutil.move(",
    ".touch(",
    "os.write(",
)
_WRITE_OPEN = re.compile(r"""(?:open|fdopen)\([^)]*["']w""")


def test_direct_writes_stay_on_the_allowlist():
    found = set()
    for path in ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(needle in text for needle in _NEEDLES) or _WRITE_OPEN.search(text):
            found.add(path.relative_to(ROOT).as_posix())
    assert found == set(ALLOWED)
