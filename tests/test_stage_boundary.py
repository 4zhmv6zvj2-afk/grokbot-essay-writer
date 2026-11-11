"""The stage layers are a dependency boundary, not only a file split.

The orchestrator imports the state, hold, landing, reply, confirm, and body
modules at module load and does not re-export the moved names. Those modules
and the note module do not import `stage_track`, either at module load or
inside a function. The next-card mint arrives as an injected `CardRun`, and
the inherited-lock re-entry arrives as an injected callable.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import essay_writer
import essay_writer.stage_track as stage_track

PACKAGE = Path(essay_writer.__file__).resolve().parent
REPO = Path(__file__).resolve().parents[1]
STATE = PACKAGE / "stage_state.py"
TRACK = PACKAGE / "stage_track.py"
LAYERS = (
    STATE,
    PACKAGE / "stage_note.py",
    PACKAGE / "stage_hold.py",
    PACKAGE / "stage_landing.py",
    PACKAGE / "stage_replies.py",
    PACKAGE / "stage_confirm.py",
    PACKAGE / "stage_body.py",
)
ARCHITECTURE = REPO / "ARCHITECTURE.md"

# Moved private names the orchestrator does not use itself, so their presence
# would mean a re-export survived.
MOVED_NAMES = (
    "_MINTING",
    "_apply_commit",
    "_atomic",
    "_attach_mid_run",
    "_commit_pointer",
    "_commit_with_next_card",
    "_draft_next_card",
    "_next_card_look",
    "_note_look",
    "_opening_look",
    "_render_stage10_before_close",
    "_snapshot_stage_save",
    "_store_stage",
    "blank_pointer",
    "door_card_reply",
    "in_first_draft",
    "init_cloned_sequence_pointer",
    "rebind_cloned_confirms",
    "render_tracking",
    "stage_lock",
)


def _imports_stage_track(path: Path) -> bool:
    """True when the module imports essay_writer.stage_track anywhere."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "essay_writer.stage_track":
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "essay_writer":
            if any(alias.name == "stage_track" for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "essay_writer.stage_track" for alias in node.names):
                return True
    return False


def _redundant_aliases(path: Path) -> list[str]:
    """Names written as ``X as X``. The old re-export shim used that form."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found.extend(alias.name for alias in node.names if alias.asname == alias.name)
    return found


def test_the_stage_layers_do_not_import_the_track():
    offenders = [path.name for path in LAYERS if _imports_stage_track(path)]
    assert offenders == []


def test_importing_the_state_layer_does_not_load_the_track():
    code = (
        "import sys\n"
        "import essay_writer.stage_state\n"
        "import essay_writer.stage_note\n"
        "import essay_writer.stage_hold\n"
        "import essay_writer.stage_landing\n"
        "import essay_writer.stage_replies\n"
        "import essay_writer.stage_confirm\n"
        "import essay_writer.stage_body\n"
        "assert 'essay_writer.stage_track' not in sys.modules, "
        "sorted(name for name in sys.modules if name.startswith('essay_writer'))\n"
    )
    env = dict(os.environ)
    paths = [str(PACKAGE.parent)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
    )
    assert completed.returncode == 0, completed.stderr


def test_stage_track_does_not_reexport_the_moved_names():
    assert _redundant_aliases(TRACK) == []
    leaked = [name for name in MOVED_NAMES if hasattr(stage_track, name)]
    assert leaked == []


def test_the_state_layer_dropped_the_minting_contextvar():
    source = STATE.read_text(encoding="utf-8")
    source += (PACKAGE / "stage_hold.py").read_text(encoding="utf-8")
    assert "_MINTING" not in source


def test_architecture_doc_describes_the_real_boundary():
    text = ARCHITECTURE.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert "does not re-export the moved names" in flat
    assert "do not import `stage_track`" in flat
    assert "injected `CardRun`" in flat
    assert "`stage_confirm.py`" in text
    assert "`stage_body.py`" in text
    assert "Re-exported by" not in text
    assert "_MINTING" not in text
    assert "re-exports all three layers" not in text
    assert "reaches back into the orchestrator" not in text
