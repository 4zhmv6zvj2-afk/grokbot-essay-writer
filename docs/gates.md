# Local gates

`tools/run_gates.py` runs the checkout checks CI runs. A clean pass writes a stamp into the git directory (`git rev-parse --git-dir` / `gate-stamp.json`), never into the worktree. `tools/tag_release.py` creates an annotated tag only when that stamp is a fresh full pass for this commit on `main`. `--allow-branch` is the maintainer exception for any other branch. It does not run the gate, and it does not push.

Use the project interpreter so ruff, mypy, and pytest are the ones the suite uses:

```bash
uv run python tools/run_gates.py
uv run python tools/run_gates.py --full
uv run python tools/tag_release.py v0.9.19 --dry-run
```

`--allow-dirty` runs the fast checks on a dirty tree and does not write a stamp. `--json` prints a machine-readable result on stdout.

`--full` adds the Python 3.12 coverage run and the sdist job from `.github/workflows/ci.yml`. The coverage run uses its own environment, so it does not replace the project `.venv`. That job sets `SOURCE_DATE_EPOCH` from the commit, runs `tools/reproducible_build.py` (which normalizes the tarball with `tools/normalize_sdist.py`), extracts the sdist, requires every tracked file, rebuilds the wheel, and runs `pytest -q` in the extracted tree. Install `requirements-build.txt` into that interpreter the way CI does before expecting `--full` to pass. The tool sets `UV_LINK_MODE=copy` when it is unset.

A stamp authorizes a tag for 60 minutes, and only when it records this commit, a clean tree, mode `full`, every step passed, and the same Python, ruff, and mypy versions. A fast stamp does not authorize a tag.

Exit 1 means a step failed. Exit 2 means the environment cannot run the gate.

## Optional push hook

```bash
git config core.hooksPath .githooks
```

The hook runs the fast gate when a push updates `main`. It uses `uv run --no-sync python` when `uv` is on `PATH`, and `python3` otherwise. Any other push prints a one-line skip. CI covers pull-request branches. If the gate fails, the push stops and the message names the interpreter that ran it. `git push --no-verify` is the emergency path. Never use it to publish a tag.
