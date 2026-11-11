"""Regenerate or check ``tests/snapshots/prompts.json`` from the live sources.

The snapshot freezes the composed runtime prompt text so an extraction change
cannot drift it silently. Nothing used to regenerate it, so this tool is the
single update path:

    .venv/bin/python tools/update_prompt_snapshot.py          # rewrite
    .venv/bin/python tools/update_prompt_snapshot.py --check  # CI: fail on drift

The payload is deterministic: ``indent=2``, ``sort_keys=True`` and one trailing
newline. It covers exactly the values asserted by
``tests/test_prompt_snapshots.py`` plus the door catalogue descriptions:

* ``instructions`` from ``essay_writer.server.INSTRUCTIONS``;
* ``stage_rules`` from ``stage_settings(stage, genre)["rules"]`` for every
  ``STAGE_ORDER`` stage x ``None``/``essay``/``report``/``diary``, plus the
  standalone ``eqr`` stage under ``eqr:none``;
* ``doors`` from ``essay_writer.doors.DOORS`` (``tool`` -> ``description``);
* ``setup`` from ``essay_writer.setup.SETUP_PROMPT`` and
  ``CURSOR_SETUP_PROMPT``;
* ``seats`` from ``seat_reading("write")``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO / "tests" / "snapshots" / "prompts.json"

if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))


def build_snapshot() -> dict:
    """Collect the current composed prompt text from the live modules."""
    from essay_writer.doors import DOORS
    from essay_writer.seats import seat_reading
    from essay_writer.server import INSTRUCTIONS
    from essay_writer.setup import CURSOR_SETUP_PROMPT, SETUP_PROMPT
    from essay_writer.stage_llm import stage_settings
    from essay_writer.writing_basics import STAGE_ORDER

    stage_rules = {
        f"{stage}:{genre or 'none'}": stage_settings(stage, genre)["rules"]
        for stage in STAGE_ORDER
        for genre in (None, "essay", "report", "diary")
    }
    stage_rules["eqr:none"] = stage_settings("eqr")["rules"]
    return {
        "instructions": INSTRUCTIONS,
        "stage_rules": stage_rules,
        "doors": {door["tool"]: door["description"] for door in DOORS},
        "setup": {
            "setup_prompt": SETUP_PROMPT,
            "cursor_setup_prompt": CURSOR_SETUP_PROMPT,
        },
        "seats": {"write": seat_reading("write")},
    }


def render() -> str:
    """Deterministic JSON text for the snapshot file."""
    return json.dumps(build_snapshot(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare without writing; exit 1 when the snapshot is stale",
    )
    args = parser.parse_args(argv)
    text = render()
    current = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.is_file() else ""
    if args.check:
        if current == text:
            print(f"snapshot is current: {SNAPSHOT.relative_to(REPO)}")
            return 0
        print(
            f"snapshot is stale: {SNAPSHOT.relative_to(REPO)}\n"
            "Run: python tools/update_prompt_snapshot.py"
        )
        return 1
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(REPO)} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
