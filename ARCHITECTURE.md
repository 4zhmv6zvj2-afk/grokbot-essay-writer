# Architecture

Essay Writer is a model-assisted, confirm-gated essay workflow served over MCP. A chat
front end (Essay Bot) calls the tools; the package owns the stages, file state,
validation, and Word output.

## Layout

- `src/essay_writer/` — the package.
  - `server.py` — MCP entry and tool registration.
  - `doors.py` — tool catalogue and descriptions.
  - `stage_track.py` — stage pointer, cards, and confirm state.
  - `spine.py`, `stage_llm.py` — stage definitions and prompts.
  - `validate.py`, `gates.py`, `invent.py` — pack checks, citation integrity, and invent-forbid.
  - `word.py`, `word_references.py` — Word output and Harvard reference lines.
  - `specialists/` — writer, reviewer, researcher, and front-office helpers.
- `tests/` — behaviour tests and synthetic fixtures.
- `docs/` — operator and writing helpers.
- `src/essay_writer/_vendor/` — vendored bootstrap core, pinned by `VENDOR.json`.

## Words used here

The module names use a small private vocabulary — doors, seats, spine, shelf,
dig, canon, mid-office. The names are stable and are not being renamed; the
mapping to plain terms is in [docs/GLOSSARY.md](GLOSSARY.md). Start there before
reading the modules.

## Entry points and lockfiles

- `first_run.py` at the repository root is the pre-install bootstrap. It chooses
  a Python before the package can be imported and then hands off to
  `essay_writer.first_run`. The package also has a `first_run.py`; that one is
  the installed setup logic that runs after the package is importable. Two
  files, two jobs, by design.
- `uv.lock` is the developer lockfile used by `uv sync`.
  `requirements-ci.txt` is the hash-pinned environment CI installs.
  `requirements-build.txt` pins the build tooling.
  `requirements-runtime.txt` is the hash-pinned runtime set for a manual,
  verifiable install.
- Release artifacts are reproducible: `SOURCE_DATE_EPOCH` is derived from the
  tagged commit and the build is run twice, with identical SHA-256 required,
  before anything is signed or uploaded.

## Vendored bootstrap

The bootstrap core is vendored from the private `python-mcp-bootstrap` repository;
`VENDOR.json` pins the release. If the project `.venv` or the MCP dependency
disappears later, rerun `python first_run.py`; it re-enters the same bootstrap. A
Python download still requires `--install-python`, and the system Python is never
changed.

The vendored file is kept byte-identical to its upstream release, so its default
floor stays 3.14. This package supports 3.12 and passes its own floor through
`python_bootstrap.py` (`REQUIRED = (3, 12, 0)`); the vendored file's hash and
`VENDOR.json` stay untouched.

## Stage flow

1. A sequence id (for example `MOD1004AA-1`) selects one essay.
2. `essay_stage` reads the stage pointer, checks the request, and either returns a
   draft/Confirm card or saves a confirmed stage.
3. Drafts and confirms are stored under `Essay-writer/<module>/sequences/<n>/`.
4. Validation and Word write only after the matching Confirm.
5. `essay.health` reports the doors, packs, and build marker.

The stage runner is a thin dispatcher (`essay_stage` → `_run_stage`). The
run branches are named helpers: `_confirm_path` (card confirm),
`_build_stage_body` (shared stage body), `_draft_reply` (draft card), and
`_save_confirm` (saved stage). The pointer boundary uses `Pointer`; stage
replies use `StageResult`.

The stages are 1–10: assignment, thesis or purpose, plan, 4a annotated bibliography,
4b critical review, first draft, feedback, edit, references, and final Word.

## Design notes

Stage behaviour is intentionally prompt-driven: the stage prompts and checklists
are the product, so they live in Python rather than in a separate prompt store.
Intent tests assert observable outcomes (refusals, stored state, and Word
output); a thin set of contract tests pins the exact rule strings the chat
contract depends on. The dispatcher and its branch helpers keep that
prompt-heavy path readable, while `Pointer` and `StageResult` mark the main
state boundaries.

## Where to start

- Install and run: `README.md`.
- Operator setup for Essay Bot: `FIRST-RUN.txt`.
- Tool contracts: `doors.py` and `docs/workflow.md`.
- Vocabulary: `docs/GLOSSARY.md`.
- How the public history came to be: `HISTORY.md`.
