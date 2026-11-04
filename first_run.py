"""Unpack an uploaded copy and pip install -e . before the console script exists.

The bootstrap module picks the interpreter before the package is imported:
an existing Python 3.14+, a good project .venv, an explicit --python, or a
project-local 3.15.2 installed with uv after the operator consents with
--install-python. Without consent and without a usable interpreter it prints a
typed python_too_old result and exits without installing anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

from essay_writer import python_bootstrap  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(python_bootstrap.bootstrap(sys.argv[1:], _ROOT))
