"""Unpack an uploaded copy and pip install -e . before the console script exists."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from essay_writer.first_run import main

if __name__ == "__main__":
    raise SystemExit(main())
