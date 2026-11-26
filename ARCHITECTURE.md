# Architecture

Essay Writer is a model-assisted, confirm-gated essay workflow served over MCP. A chat
front end (Essay Bot) calls the tools; the package owns the stages, file state,
validation, and Word output.

## Layout

- `src/essay_writer/` — the package.
  - `server.py` — MCP entry and tool registration.
  - `doors.py` — tool catalogue and descriptions.
  - `stage_run.py` — the orchestrator. It keeps `essay_stage` and the stage
    decision tree. The folded writers live in this file: the confirm path and
    the stage-7 skip probe, the body builder, the draft and save replies
    (`_draft_reply`, `_save_confirm`), the landing and report helpers, and the
    held and refused replies. A card calls `_run_card_only` directly. The
    inherited-lock keep calls `_inherited_keep_confirm` directly.
  - `stage_state.py` — the pointer, the commit journal, and the stage lock. The
    lock and the journal stay one protocol: the note and the pointer that names
    it are published together. Its import rule is in [Stage flow](#stage-flow).
  - `stage_llm.py` — stage settings and prompt assembly.
  - `stage_context.py` — the typed pipeline values: `StageArgs` (the public
    `essay.stage` tool arguments), `StageContext` (one resolved stage call),
    and `ConfirmState`.
  - `stage_note.py` — the tracking-note renderer and look reader. It returns
    the stage markdown and reads the working or final look back out of that
    markdown. It does not write the pointer or the commit journal. Its import
    rule is in [Stage flow](#stage-flow).
  - `stage_next.py` — the one writer for the stage runner's next sentence
    on an `essay.stage` reply, including the upload line, the stage 7 ask,
    the mid-run wait, and Confirm wording stripped while a mid-run is going.
    A reply that only repeats a sentence already chosen calls
    `write_stage_next` directly. Other reply modules set their own next
    sentence: dig, shelf, setup, intake, review, projects, research, word,
    validate, encourage, free_alt, late_chain, the specialist wrapper
    `specialists/grok_bot`, and the tool wrappers `student_progress` and
    `student_voice`.
  - `safe_url.py` — the one network opener: public http(s) only, every resolved
    address checked, redirects re-validated, and a hard byte cap per caller.
  - `spine.py` — stage definitions. Prompt text is assembled in `stage_llm.py`.
  - `validate.py`, `gates.py`, `invent.py` — pack checks, citation integrity, and invent-forbid.
  - `citation_list.py` — the citation list for one sequence, written when stage 4b finishes.
  - `sources.py` — the one source record, the one minted id, and the one same-work check.
  - `source_ids.py` — reads the id already stored for a file. Minting stays in `sources.py`. A later DOI, author, or title keeps that stored id.
  - `source_floor.py` — the gather floor. A stated count is that floor. A silent brief uses eight works per 1,000 words, rounded up. Distinct works use the identity in `sources.py`.
  - `essay_cites.py` — how many distinct relevant works the essay cites.
  - `download_shortlist.py` — the download set that fits the saved plan, after works that do not fit the question are dropped.
  - `word.py`, `word_references.py` — Word output and Harvard reference lines.
    Paragraphs, runs, the title limit, and the `.docx.tmp` replace live in
    `word.py`. `projects.py` uses that same title limit.
  - `specialists/` — writer, reviewer, researcher, and front-office helpers.
- `tests/` — behaviour tests and synthetic fixtures.
- `docs/` — operator and writing helpers.
- `src/essay_writer/_vendor/` — vendored bootstrap core, pinned by `VENDOR.json`.

## Package modules

Every product module under `src/essay_writer/` is named here.
`__init__.py` is the package marker and `__main__.py` is the `python -m` entry.
They are not product modules. `specialists/` is a package of helpers, already named in Layout.

- `assignment_gate.py`
- `assignment_handoff.py`
- `brief_checks.py`
- `brief_contract.py`
- `build_office.py`
- `build_status.py`
- `canon.py`
- `citation_list.py`
- `cite_fit.py`
- `cite_open.py`
- `clarify.py`
- `confirm.py`
- `context_fit.py`
- `cursor_office.py`
- `databases.py`
- `debug_log.py`
- `diary.py`
- `dig.py`
- `doors.py`
- `download_shortlist.py`
- `downloads.py`
- `draft_from_review.py`
- `durable.py`
- `encourage.py`
- `essay_cites.py`
- `first_run.py`
- `first_run_cli.py`
- `first_run_common.py`
- `first_run_host.py`
- `first_run_install.py`
- `first_run_mac.py`
- `fo_chat_locks.py`
- `free_alt.py`
- `gates.py`
- `gathered_set.py`
- `handbook.py`
- `harvard_4a.py`
- `harvard_ref_check.py`
- `health.py`
- `incident.py`
- `intake.py`
- `invent.py`
- `known_paths.py`
- `late_chain.py`
- `lookup_fields.py`
- `mark_fit.py`
- `mid_spawn.py`
- `ml_events.py`
- `model_contract.py`
- `operator_event.py`
- `originals.py`
- `outline_primary.py`
- `pack_backup.py`
- `paths.py`
- `pdf_read.py`
- `pdf_year.py`
- `programme.py`
- `projects.py`
- `prompt_content.py`
- `prompt_loader.py`
- `python_bootstrap.py`
- `quarantine.py`
- `records.py`
- `research.py`
- `research_packs.py`
- `resolvers.py`
- `review.py`
- `review_block.py`
- `revise.py`
- `rewrite_baseline.py`
- `roll_forward.py`
- `runtime_data.py`
- `safe_url.py`
- `seats.py`
- `server.py`
- `setup.py`
- `shelf.py`
- `shells.py`
- `short_cites.py`
- `source_floor.py`
- `source_ids.py`
- `source_match.py`
- `sources.py`
- `spine.py`
- `stage7.py`
- `stage_context.py`
- `stage_llm.py`
- `stage_next.py`
- `stage_note.py`
- `stage_state.py`
- `stage_run.py`
- `state.py`
- `student_progress.py`
- `student_turns.py`
- `student_voice.py`
- `textutil.py`
- `update.py`
- `user_place.py`
- `validate.py`
- `vision.py`
- `word.py`
- `word_references.py`
- `writing_basics.py`

## Sources

`sources.py` is the single home for a stored work. It imports nothing from the rest of the package. `SourceRecord` is the record. `mint_source_id` keeps an id already on the record, then a valid supplied id, then a minted id. `same_source` matches an id, then a locator, then a canonical DOI, then a normalized title, year, and author. A title by itself is not a match, and two different DOIs stay two works. `source_ids.py` reads the id already written for a file and does not mint a second one. `source_floor.py` counts distinct works with that identity. The citation list, the Harvard check, and the gather call these helpers. An opened PDF still uses a separate filename-token check. That check is not the identity.

## Words used here

The module names use a small private vocabulary — doors, seats, spine, shelf,
dig, canon, mid-office. The names are stable and are not being renamed; the
mapping to plain terms is in [docs/GLOSSARY.md](docs/GLOSSARY.md). Words the
chat uses with a student are in the
[Student-facing terms](docs/GLOSSARY.md#student-facing-terms) section of that
page. Start there before reading the modules.

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
4. A save needs the matching draft and file fingerprint. Stage 5 is the
   draft-store exception: it stores its first draft and advances to stage 6 on
   the draft call when its gate passes. Review writes the
   first-draft Word file from the intact saved draft, and records the stage 6
   pass after that write. The last stage writes the final Word file when that
   stage is confirmed.
5. `essay.health` reports the doors, packs, and build marker.

The stage runner keeps the public entry points and the stage decision tree in
`stage_run.py`. The run branches are named helpers in that file:
`_confirm_path` (card confirm), `_build_stage_body` (shared stage body),
`_draft_reply` (draft card), and `_save_confirm` (saved stage); together with
`_run_stage` they are several hundred lines of decision tree, not a thin
pass-through. `Pointer` and `StageResult` in `stage_state.py` name the intended
pointer and result shapes; most helpers still take a plain `pointer: dict`, so
treat those two types as documentation of intent rather than an enforced schema.

`stage_state.py` and `stage_note.py` do not import the orchestrator
(`stage_run.py`), either at module load or inside a function. The
orchestrator does not re-export the names that stay in `stage_state.py`.
A card calls `_run_card_only` directly: the next-card mint passes
`minting=True`, and reopening an already-saved stage's card passes
`minting=False`. The inherited-lock keep calls `_inherited_keep_confirm`
directly. `spine.py` does not forward `essay_stage`. Other package imports
still happen inside function bodies; that is a package-wide import-graph
question, not evidence for a stage-module boundary.

The stages are 1–10: assignment, thesis or purpose, plan, 4a annotated bibliography,
4b critical review, first draft, re-read and make changes, feedback, edit,
references, and final Word.

## Design notes

Stage behaviour is intentionally prompt-driven: the stage prompts and checklists
are the product, so they live in the packaged `src/essay_writer/prompts/` bundle
and are rendered from there rather than being fetched at runtime.
Intent tests assert observable outcomes (refusals, stored state, and Word
output); a thin set of contract tests pins the exact rule strings the chat
contract depends on. The stage runner and its branch helpers keep that
prompt-heavy path in one place, at the cost of a large decision tree.
`Pointer` and `StageResult` name the intended state shapes rather than enforced
schemas: many helpers still take a plain `pointer: dict`. `StageArgs` and
`StageContext` type the pipeline between the tool signature and the reply
writers; no stage body travels as a string-keyed dict with a sentinel any more.

## Where to start

- Install and run: `README.md`.
- Operator setup for Essay Bot: `FIRST-RUN.txt`.
- Tool contracts: `doors.py` and `docs/workflow.md`.
- Vocabulary: `docs/GLOSSARY.md`.
- How the public history came to be: `HISTORY.md`.

The stage runner and the pointer file were split into further modules, then
folded back. That split was tried and reverted. The layout above is the one
that ships.
