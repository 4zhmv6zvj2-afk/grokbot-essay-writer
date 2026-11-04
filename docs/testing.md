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

Baseline on macOS / CPython 3.15: **1006 passed, 8 skipped in ~56s**.
The skipped tests need a real terminal (see `tests/pty_support.py`).

CI runs the suite on Ubuntu and macOS, then builds the sdist and wheel, installs
the wheel into a clean environment, extracts the sdist, and runs the suite from
the extracted sdist. A release is only signed after that artifact run passes.

## Layout

| Path | Purpose |
| --- | --- |
| `tests/test_*_ac.py` | Acceptance-criteria tests. The module docstring names the internal ticket and the ACs; the test asserts the behaviour, not the ticket. `_ac` is just a suffix. |
| `tests/test_*.py` | Behaviour and contract tests for one area. |
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

Ticket ids in `_ac` docstrings ("Bug #30") refer to the private tracker that
predates this repository. The docstring is the public record of what the test
pins; the number is only a stable label.

## Writing a test

- Every behaviour change lands with a test; a bug fix lands with a regression
  test that fails before the fix.
- Assert the observable result: the tool's returned dict, the file it wrote, the
  Word XML it produced. Do not assert on log lines or private helper names
  unless the name is the published contract.
- Keep tests deterministic. No network in tests; the fixtures are local.
- Prefer one test per behaviour over one test per branch. A test with no
  assertion is a bug.
