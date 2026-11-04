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
uv run mypy src
uv run python tools/generate_docs.py --check
uv run python tools/update_prompt_snapshot.py --check
uv run pytest --cov=essay_writer --cov-report=term
```

The baseline is 1060 passed, 8 skipped in about a minute, at ~87% coverage (CI enforces an 85% floor on one Ubuntu cell). The 8 skips need a real
terminal; see [docs/testing.md](docs/testing.md).

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
- Run the gates above and paste the result.
- Do not commit secrets, API keys, or student work.
- Do not rewrite published history or force-push tags.

## Where things live

- [ARCHITECTURE.md](ARCHITECTURE.md) — module layout and stage flow.
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — the private vocabulary (doors, seats,
  spine, shelf, dig, canon, mid-office).
- [HISTORY.md](HISTORY.md) — why the public history starts with an import.

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

Releases are cut by the maintainer. A release is a tag `vX.Y.Z` on a commit in
this repository, with `pyproject.toml`, `src/essay_writer/__init__.py`, and
`CHANGELOG.md` carrying the same version. The release workflow rebuilds from the
tag with pinned build tooling and `SOURCE_DATE_EPOCH`, builds twice and requires
identical hashes, runs the test suite from the source distribution, then signs
and attests the artifacts before uploading them.

This project is distributed as source for Essay Bot in Grok Bot. There is no
PyPI release; install from a clone with `python -m pip install -e .`.
