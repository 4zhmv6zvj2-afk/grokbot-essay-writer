# Architecture

Essay Writer is a model-assisted, confirm-gated essay workflow served over MCP. A chat
front end (Essay Bot) calls the tools; the package owns the stages, file state,
validation, and Word output.

## Layout

- `src/essay_writer/` — the package.
  - `server.py` — MCP entry and tool registration.
  - `doors.py` — tool catalogue and descriptions.
  - `stage_track.py` — the orchestrator: `essay_stage`, the stage run branches,
    the injected card runner, and the draft/confirm entry points.
  - `stage_state.py` — the state layer: pointer and its commit journal, stage lock,
    tracking-note renderer, and the held/refused reply bodies. It defines
    `CardRun`, the card-only runner the orchestrator injects, and never imports
    the orchestrator.
  - `stage_landing.py` — landing and report helpers: storing a saved stage,
    attaching report bodies, mid-run and missed-stage records, inherited-lock
    bookkeeping, and the stage 6 opener. The inherited-lock keep takes the
    public confirm runner as an injected callable.
  - `stage_replies.py` — the draft and save reply writers (`_draft_reply`,
    `_save_confirm`) and the no-op result.
  - `stage_context.py` — the typed pipeline values: `StageArgs` (the public
    `essay.stage` tool arguments) and `StageContext` (one resolved stage call).
    The old sentinel dict is gone.
  - `safe_url.py` — the one network opener: public http(s) only, every resolved
    address checked, redirects re-validated, and a hard byte cap per caller.
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
mapping to plain terms is in [docs/GLOSSARY.md](docs/GLOSSARY.md). Start there
before reading the modules.

## Entry points and lockfiles

- `first_run.py` at the repository root is the pre-install bootstrap. It chooses
  a Python before the package can be imported and then hands off to
  `essay_writer.first_run`. The package also has a `first_run.py`; that one is
  the installed setup logic that runs after the package is importable. Two
  files, two jobs, by design. The package's `first_run.py` is a thin facade over
  `first_run_common.py`, `first_run_install.py` (install/update + Cursor
  installer), `first_run_host.py` (Cursor/Grok config attach), `first_run_mac.py`
  (Mac handoff), and `first_run_cli.py` (argument parsing and `main`).
- `uv.lock` is the developer lockfile used by `uv sync`.
  `requirements-ci.txt` is the hash-pinned environment CI installs.
  `requirements-build.txt` pins the build tooling.
  `requirements-runtime.txt` is the hash-pinned runtime set for a manual,
  verifiable install.
- Release artifacts are reproducible: `SOURCE_DATE_EPOCH` is derived from the
  tagged commit and the build is run twice, with identical SHA-256 required,
  before anything is signed or uploaded.

## Vendored bootstrap

The bootstrap core is vendored from the public `python-mcp-bootstrap`
repository; `VENDOR.json` pins the release (`v0.2.0`, commit `fd8e0b9`) and the
file SHA-256. The vendored file is byte-identical to the upstream release: there
is no local patch. If the project `.venv` or the MCP dependency disappears
later, rerun `python first_run.py`; it re-enters the same bootstrap. A Python
download still requires `--install-python`, and the system Python is never
changed.

Upstream v0.2.0 installs the hash-pinned `requirements-runtime.txt` with
`--require-hashes` before the project install, which then runs with
`--no-deps`. The core's floor is 3.12; this package supports 3.12 and passes
its own floor through `python_bootstrap.py` (`REQUIRED = (3, 12, 0)`).

## Stage flow

1. A sequence id (for example `MOD1004AA-1`) selects one essay.
2. `essay_stage` reads the stage pointer, checks the request, and either returns a
   draft/Confirm card or saves a confirmed stage.
3. Drafts and confirms are stored under `Essay-writer/<module>/sequences/<n>/`.
4. A save needs the matching draft and file fingerprint; stage 5 is the
   draft-store exception described below (it stores its first draft and advances
   to stage 6 on the draft call when its gate passes). A Word file is written
   only from a confirmed stage.
5. `essay.health` reports the doors, packs, and build marker.

The stage runner keeps the public entry points and the stage decision tree. The
run branches are named helpers: `_confirm_path` (card confirm), `_build_stage_body`
(shared stage body), `_draft_reply` (draft card), and `_save_confirm` (saved
stage); together with `_run_stage` they are several hundred lines of decision
tree, not a thin pass-through. `Pointer` and `StageResult` in `stage_state.py`
name the intended pointer and result shapes; most helpers still take a plain
`pointer: dict`, so treat those two types as documentation of intent rather than
an enforced schema.

The module split is a real dependency boundary, not only a file split. The
orchestrator (`stage_track.py`) imports `stage_state.py`, `stage_landing.py`, and
`stage_replies.py` at module load and keeps `essay_stage` and the public entry
points. It does not re-export the moved names. In the other direction,
`stage_state.py`, `stage_landing.py`, and `stage_replies.py` do not import
`stage_track`, either at module load or inside a function. Where a state helper
needs a stage card, the orchestrator threads an injected `CardRun` through the
commit path: the next-card mint and the reopening of an already-saved stage's
card both call it. The inherited-lock keep receives the public confirm runner
the same way. `spine.py` does not forward `essay_stage`. Other package imports
still happen inside function bodies; that is a package-wide import-graph
question, not evidence for the stage layers.

The stages are 1–10: assignment, thesis or purpose, plan, 4a annotated bibliography,
4b critical review, first draft, feedback, edit, references, and final Word.

## Design notes

Stage behaviour is intentionally prompt-driven: the stage prompts and checklists
are the product, so they live in the packaged `src/essay_writer/prompts/` bundle
and are rendered from there rather than being fetched at runtime.
Intent tests assert observable outcomes (refusals, stored state, and Word
output); a thin set of contract tests pins the exact rule strings the chat
contract depends on. The stage runner and its branch helpers keep that
prompt-heavy path in one place, at the cost of a large decision tree.
`Pointer` and `StageResult` name the intended state shapes rather than enforced
schemas: many helpers still take a plain `pointer: dict`. The module split is
enforced by the boundary test: the state, landing, and reply layers never import
the orchestrator, and the orchestrator supplies the card and confirm runners
explicitly. `StageArgs` and `StageContext` type the pipeline
between the tool signature and the reply writers; no stage body travels as a
string-keyed dict with a sentinel any more.

## Where to start

- Install and run: `README.md`.
- Operator setup for Essay Bot: `FIRST-RUN.txt`.
- Tool contracts: `doors.py` and `docs/workflow.md`.
- Vocabulary: `docs/GLOSSARY.md`.
- How the public history came to be: `HISTORY.md`.
