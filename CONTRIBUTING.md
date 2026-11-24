# Contributing

This is a source-available distribution of the Essay Writer backend, maintained
by one person. It is public so users and operators can inspect what runs on
their computer and verify releases. It is not run as a community project.

## What kind of help is useful

- **Bug reports** with a reproduction. That is the main supported channel.
- **Security reports** through the private channel in [SECURITY.md](SECURITY.md).
- **Small, focused fixes** are welcome after an issue confirms the problem.
  Unsolicited feature pull requests are likely to be closed: there is no feature
  roadmap and no review capacity for them.
- **Do not send student work, drafts, keys, or real essay files.** Use the
  synthetic fixtures in `tests/fixtures/` or a minimal fake document.

## Setup

Python 3.12 or newer. Install the package and dev tools with `uv`:

```bash
uv sync --extra dev
```

Run the gates before sending a change:

```bash
uv run pytest
uv run ruff check src tests tools
uv run ruff format --check --force-exclude src tests tools
uv run mypy src
uv run python tools/generate_docs.py --check
uv run python tools/update_prompt_snapshot.py --check
uv run pytest --cov=essay_writer --cov-report=term
```

The suite is the baseline gate: it must pass, and CI enforces an 85% coverage
floor on one Ubuntu cell. The terminal-backed tests need a real terminal and
skip where the host refuses a pty; see [docs/testing.md](docs/testing.md).

## Tests

New functionality lands with tests. Every pull request that adds behaviour must
add or extend the automated suite, and a bug fix should include a regression
test. Some tests pin source-level contract points with `inspect.getsource`; if a
helper moves, update the pin to the new helper and keep the behaviour assert.
The prompt snapshot is regenerated with `tools/update_prompt_snapshot.py`, never
by hand. [docs/testing.md](docs/testing.md) explains the test layout, the
contract pins, and the snapshot.

## Sending a change

- Keep a change small and explain what it does.
- CI runs on every push and pull request and is free for this public repo. Never add `[skip ci]` to a commit that changes code, workflows, or tests.
- Run the gates above and paste the result.
- Do not commit secrets, API keys, or student work.
- Do not rewrite published history or force-push tags.

## Where things live

- [ARCHITECTURE.md](ARCHITECTURE.md) — module layout and stage flow.
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — the private vocabulary (doors, seats,
  spine, shelf, dig, canon, mid-office).
- [HISTORY.md](HISTORY.md) — why the public history starts with an import.
- [docs/runbook.md](docs/runbook.md) — the five-minute release check, a student
  report, and what to do with a bad immutable release.

`uv.lock` is the developer lockfile. `requirements-ci.txt` is the hash-pinned CI
environment, `requirements-build.txt` pins the build tooling, and
`requirements-runtime.txt` is the hash-pinned runtime set for a manual install.
The root `first_run.py` is the pre-install bootstrap; the package's
`first_run.py` is the installed setup logic. They are different files on
purpose.

## If you hit a bug

Open an issue with:

- the output of `essay-writer --health` (it includes `build_commit`);
- your Python version, OS, and install method (`uv sync` or `pip`);
- whether `ESSAY_WRITER_DEBUG=1` was set, and the zip from
  `essay-writer --debug-export` if it was;
- the tool and arguments, and the smallest reproduction, with secrets removed.

## Releases

Releases are cut by the maintainer in two passes. A release is a tag `vX.Y.Z`
on a commit in this repository, with four sources carrying the same version:
`pyproject.toml`, `src/essay_writer/__init__.py`, the `essay-writer` entry in
`uv.lock`, and the newest release heading in `CHANGELOG.md`. The README verify
snippets name the release artifacts, so they carry it too.

Before tagging, check every source in one step:

- run `uv lock` so `uv.lock` names the new project version (it also picks up
  any dependency change, such as a security bump);
- update the README artifact names and the `git checkout` tag;
- rename `## Unreleased` to the version heading, with the date;
- run `python tools/check_release_version.py --tag vX.Y.Z`, then the suite,
  `ruff check`, `ruff format --check`, `mypy`, and `uv lock --check`.

The version literal no longer appears in the test suite: tests import
`essay_writer.__version__`, so a bump only touches the files above. The
checker fails on a stale `uv.lock` or changelog heading, and a suite test
fails on stale README artifact names, so a missed file stops the release
before it ships.
First tag the commit and create a **draft** GitHub release for that tag. Then
dispatch the Release workflow with the tag input. It rebuilds from the tag with
pinned build tooling and `SOURCE_DATE_EPOCH`, builds twice and requires
identical hashes, runs the test suite from the source distribution, and signs
and attests the artifacts while the release is still a draft. Publish the draft
only after the workflow succeeds. Never publish first: immutable releases reject
asset uploads after publication.

This project is distributed as source for Essay Bot in Grok Bot. There is no
PyPI release; install from a clone with `python -m pip install -e .`.
