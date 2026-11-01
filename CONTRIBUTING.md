# Contributing

## Setup

Python 3.12 or newer. Install the package and dev tools with `uv`:

```bash
uv sync --extra dev
```

## Tests

```bash
uv run pytest
```

Run the focused test file first when changing one area.

Some tests pin source-level contract points with `inspect.getsource`; if a
helper moves, update the pin to the new helper and keep the behaviour assert.

## If you hit a bug

Open an issue with:

- the output of `essay-writer --health` (it includes `build_commit`);
- your Python version, OS, and install method (`uv sync` or `pip`);
- whether `ESSAY_WRITER_DEBUG=1` was set, and the zip from
  `essay-writer --debug-export` if it was;
- the tool and arguments, and the smallest reproduction, with secrets removed.

## Pull requests

- Keep a change small and explain what it does.
- Run `uv run pytest`, `uv run ruff check src tests`, and `uv run mypy src`.
- Do not commit secrets, API keys, or student work.

This project is distributed as source for Essay Bot in Grok Bot. There is no PyPI release; install from a
clone with `python -m pip install -e .`.
