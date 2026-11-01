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
