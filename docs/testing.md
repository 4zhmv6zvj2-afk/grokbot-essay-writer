# Tests

The suite is the main safety net for a prompt-driven product: the prompts and
checks *are* the behaviour, so most tests assert observable outcomes (tool
results, files on disk, Word XML) rather than implementation details.

## Running

```bash
./.venv/bin/python -m pytest -q          # or: uv run pytest
./.venv/bin/python -m ruff check src tests tools
./.venv/bin/python -m mypy src
./.venv/bin/python tools/generate_docs.py --check
./.venv/bin/python tools/update_prompt_snapshot.py --check
```

Baseline on macOS / CPython 3.15: **1078 passed in ~65s**. The terminal-backed
tests need a real terminal (see `tests/pty_support.py`) and skip where the host
refuses a pty.

## Coverage

```bash
./.venv/bin/python -m pytest -q --cov=essay_writer --cov-report=term --cov-fail-under=85
```

Current baseline: **~87% total** (22,220 statements, 2,917 missed on the CI
3.12 cell). CI measures coverage on exactly one matrix cell — Ubuntu with
CPython 3.12 — and enforces a floor of **85%**; the other cells run the plain
suite. Configuration lives in `pyproject.toml`: `[tool.coverage.run]` measures
only `essay_writer` (tests are omitted), and `[tool.coverage.report]` sets
`show_missing`, `skip_covered`, and `fail_under = 85`. Use
`--cov-report=term-missing` locally to see the uncovered lines.

CI runs the suite on Ubuntu and macOS, then builds the sdist and wheel, installs
the wheel into a clean environment, extracts the sdist, and runs the suite from
the extracted sdist. A release is only signed after that artifact run passes.

## Layout

| Path | Purpose |
| --- | --- |
| `tests/test_*.py` | One behaviour area per file, named for what it covers. Acceptance-criterion tests label the cases `AC1`, `AC2`, … in the function name and docstring; the label is a stable local id, not a tracker reference. |
| `tests/helpers.py` | Shared builders (call a tool, read a result). |
| `tests/pty_support.py` | Terminal-backed tests; skipped when no pty is available. |
| `tests/fixtures/` | Synthetic assignments, answer keys, and logs. No student work. |
| `tests/snapshots/prompts.json` | Frozen composed prompt text (437 KB). Do not hand-edit; regenerate with `tools/update_prompt_snapshot.py`. |

## Contract pins

Some tests use `inspect.getsource` (213 calls across 51 files) to pin the exact
rule strings the chat contract depends on. These are deliberately brittle: if a
helper moves or a rule string changes, the pin fails and the diff is reviewed.
When a helper moves, update the pin to the new helper and keep the behavioural
assert. If a rule string changes intentionally, update the snapshot with
`tools/update_prompt_snapshot.py` and review the snapshot diff like source.

Test files are named for the behaviour they cover. The `AC1`, `AC2`, … labels in
some function names and docstrings are stable local acceptance-criterion ids;
they are not tracker references. Private ticket and PR references were removed
from the test docstrings before the 0.3.1 release.

## Writing a test

- Every behaviour change lands with a test; a bug fix lands with a regression
  test that fails before the fix.
- Assert the observable result: the tool's returned dict, the file it wrote, the
  Word XML it produced. Do not assert on log lines or private helper names
  unless the name is the published contract.
- Keep tests deterministic. No network in tests; the fixtures are local.
- Prefer one test per behaviour over one test per branch. A test with no
  assertion is a bug.
