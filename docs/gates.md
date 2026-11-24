# Local gates

`tools/run_gates.py` runs the checkout checks CI runs. A clean pass writes a stamp into the git directory (`git rev-parse --git-dir` / `gate-stamp.json`), never into the worktree. `tools/tag_release.py` creates an annotated tag only when that stamp is a fresh full pass for this commit on `main`. `--allow-branch` is the maintainer exception for any other branch. It does not run the gate, and it does not push.

Use the project interpreter so ruff, mypy, and pytest are the ones the suite uses. The ruff step compiles `.cursor/skills/verify-essay-writer/scripts/verify-essay-writer` and checks it with `src`, `tests`, and `tools`. The format step checks those same paths.

```bash
uv run python tools/run_gates.py
uv run python tools/run_gates.py --full
uv run python tools/tag_release.py v0.9.19 --dry-run
```

`--allow-dirty` runs the fast checks on a dirty tree and does not write a stamp. `--json` prints a machine-readable result on stdout.

`--full` adds the Python 3.12 coverage run and the sdist job from `.github/workflows/ci.yml`. The coverage run uses its own environment, so it does not replace the project `.venv`. That job sets `SOURCE_DATE_EPOCH` from the commit, runs `tools/reproducible_build.py` (which normalizes the tarball with `tools/normalize_sdist.py`), extracts the sdist, requires every tracked file, rebuilds the wheel, and runs `pytest -q` in the extracted tree. Install `requirements-build.txt` into that interpreter the way CI does before expecting `--full` to pass. The tool sets `UV_LINK_MODE=copy` when it is unset.

A stamp authorizes a tag for 60 minutes, and only when it records this commit, a clean tree, mode `full`, every step passed, and the same Python, ruff, and mypy versions. A fast stamp does not authorize a tag.

## Pull requests

On `main`, and on a manual run, CI runs the Python 3.12–3.15 matrix, the macOS Python 3.15 suite, and the shipped-artifacts job. A pull request runs that same matrix and the artifacts job. It runs the macOS suite only when the diff touches a macOS-sensitive path: `src/essay_writer/first_run_mac.py`, `intake.py`, `word.py`, `paths.py`, `setup.py`, `server.py`, a test whose name contains mac, first-run, word, or path, `pyproject.toml`, `requirements*.txt`, `MANIFEST.in`, or `.github/workflows/`. Any other pull request skips the macOS job. macOS is not a required check. The six required checks stay the four Linux test jobs and the two CodeQL analyze jobs. A failed path decision runs the macOS suite.

A pull request runs the shipped-artifacts job when the diff adds or deletes a file, or touches `pyproject.toml`, `MANIFEST.in`, `tools/normalize_sdist.py`, `tools/reproducible_build.py`, `docs/`, or `src/essay_writer/prompts/`. A rename counts as a path change. Any other pull request skips that job. `main`, a manual run, and the release workflow still build the artifacts. A failed path decision runs the job. The decision is the same Changed paths job as the macOS filter.

Exit 1 means a step failed. Exit 2 means the environment cannot run the gate.

## Optional push hook

```bash
git config core.hooksPath .githooks
```

The hook runs the fast gate when a push updates `main`. It uses `uv run --no-sync python` when `uv` is on `PATH`, and `python3` otherwise. Any other push prints a one-line skip. CI covers pull-request branches. If the gate fails, the push stops and the message names the interpreter that ran it. `git push --no-verify` is the emergency path. Never use it to publish a tag.
