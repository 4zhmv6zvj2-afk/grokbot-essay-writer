# Tests

The suite is the main safety net for a prompt-driven product: the prompts and
checks *are* the behaviour, so most tests assert observable outcomes (tool
results, files on disk, Word XML) rather than implementation details.

## Running

```bash
./.venv/bin/python -m pytest -q          # or: uv run pytest
./.venv/bin/python -m ruff check src tests tools
./.venv/bin/python -m ruff format --check --force-exclude src tests tools
./.venv/bin/python -m mypy src
./.venv/bin/python tools/generate_docs.py --check
./.venv/bin/python tools/update_prompt_snapshot.py --check
```

The whole suite passes on macOS and Linux. The terminal-backed tests need a
real terminal (see `tests/pty_support.py`) and skip where the host refuses a
pty. Duration depends on the machine and on how many pty cases run.

## Coverage

```bash
./.venv/bin/python -m pytest -q --cov=essay_writer --cov-report=term --cov-fail-under=85
```

CI measures coverage on exactly one matrix cell — Ubuntu with CPython 3.12 —
and enforces a floor of **85%**; the other cells run the plain suite. The run
reports the current total, above the floor; read the CI log for the exact
number, which moves with the code. Configuration lives in `pyproject.toml`:
`[tool.coverage.run]` measures only `essay_writer` (tests are omitted), and
`[tool.coverage.report]` sets `show_missing`, `skip_covered`, and
`fail_under = 85`. Use `--cov-report=term-missing` locally to see the uncovered
lines.

CI runs the suite on Ubuntu and macOS, then builds the sdist and wheel, installs
the wheel into a clean environment, extracts the sdist, requires it to carry
every tracked file, builds a wheel from it that must be byte-identical to the
checkout wheel, and runs the suite from the extracted sdist. From 0.9.19,
signing is part of the release flow again. A release is signed after that
artifact run passes. The release workflow repeats the sdist checks before
signing. Releases 0.9.15 through 0.9.18 shipped the wheel, the sdist, and
`SHA256SUMS`. Those releases were not signed. A separate reproduce workflow
rebuilds a published release from its tag with the pinned toolchain and
compares the SHA-256 set.

## Layout

| Path | Purpose |
| --- | --- |
| `tests/test_*.py` | One behaviour area per file, named for what it covers. Acceptance-criterion tests label the cases `AC1`, `AC2`, … in the function name and docstring; the label is a stable local id, not a tracker reference. |
| `tests/helpers.py` | Shared builders (call a tool, read a result). |
| `tests/pty_support.py` | Terminal-backed tests; skipped when no pty is available. |
| `tests/fixtures/` | Synthetic assignments, answer keys, and logs. No student work. |
| `tests/conversations/` | Golden conversations. A fake shell calls the real doors with hand-authored payloads. A prompt change that alters a student reply updates the matching path. |
| `tests/snapshots/prompts.json` | Frozen composed prompt text. Do not hand-edit; regenerate with `tools/update_prompt_snapshot.py`. |

## Contract pins

`tools/pin_audit.py` is a read-only scan of `tests/`. It prints one line per
pin, `file:line | kind | target`, and a count. The kind is `getsource`,
`docstring`, `source-string`, `test-of-test`, or `filename-pin`. It always
exits 0.

```bash
python tools/pin_audit.py
```

When a change touches a file that has a pin, replace that pin with an
assertion on the observable artifact: the tool reply, the student text, the
docx, the file on disk, or the saved state. Do not add a new
`inspect.getsource` pin. The count should fall by at least a quarter in each
release. The 0.9.19 baseline was 727 (getsource 251, docstring 7,
source-string 384, test-of-test 57, filename-pin 28). The three heaviest
files were `tests/test_log_ops.py`, `tests/test_stage_launch_status.py`, and
`tests/test_finished_word.py`.

## Runtime and quarantine

CI runs pytest with `--durations=25`. The 25 slowest tests are printed at
the end of each test job. A flaky test is fixed, or it is listed here with
an issue. The suite does not retry a failure. The quarantine list is empty.

A test that needs a real terminal uses the `requires_pty` fixture and skips
when the host has no pty. CI fails that skip instead of hiding it. No test
calls `ps`. Network tests stub the socket; they do not open one.

Keep the policy ratchets even when the report lists them: the import graph,
the ban on `PYTEST_CURRENT_TEST` under `src/`, the public-address scan,
`test_captured_material.py`, the skill-version tests, and the prompt snapshot.
If a rule string changes intentionally, update the snapshot with
`tools/update_prompt_snapshot.py` and review the snapshot diff like source.

Test files are named for the behaviour they cover. The `AC1`, `AC2`, … labels in
some function names and docstrings are stable local acceptance-criterion ids;
they are not tracker references. Private ticket and PR references were removed
from the test docstrings before the 0.3.1 release.

## Plymouth Cite Them Right

Plymouth Cite Them Right is the Harvard style in `docs/referencing-harvard.md`.
There is no separate Plymouth style to switch on, so a brief or a course page
that names it is not asking for a product feature that is missing. A missing
Plymouth switch is not a product gap. The wording stays internal: the Word file
does not print it and the essay does not announce its referencing method.
`tests/test_internal_style_note.py` holds that line.

## Writing a test

- Every behaviour change lands with a test; a bug fix lands with a regression
  test that fails before the fix.
- Assert the observable result: the tool's returned dict, the file it wrote, the
  Word XML it produced. Do not assert on log lines or private helper names
  unless the name is the published contract.
- Keep tests deterministic. No network in tests; the fixtures are local.
- Prefer one test per behaviour over one test per branch. A test with no
  assertion is a bug.
