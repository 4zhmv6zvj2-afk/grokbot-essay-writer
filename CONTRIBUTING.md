# Contributing

## Setup

Python 3.10 or newer. Install the package and dev tools with `uv`:

```bash
uv sync --extra dev
```

## Tests

```bash
uv run pytest
```

Run the focused test file first when changing one area.

## Pull requests

- Keep a change small and explain what it does.
- Run `uv run pytest`, `uv run ruff check src tests`, and `uv run mypy src`.
- Do not commit secrets, API keys, or student work.

This project is distributed as source for Essay Bot in Grok Bot. There is no PyPI release; install from a
clone with `python -m pip install -e .`.
