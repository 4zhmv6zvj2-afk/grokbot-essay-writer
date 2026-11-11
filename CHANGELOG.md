# Changelog

## 0.8.2 — 2026-11-11

Formatting and gate-only patch. No runtime behaviour change; every Python file
is AST-identical to 0.8.1.

- Apply `ruff format` to `src`, `tests`, and `tools` (223 files: 217 Python plus
  the CI workflow, pre-commit hook, README, CONTRIBUTING, docs/testing, and
  pyproject). The vendored bootstrap is excluded from formatting and remains
  byte-identical; `ruff check` still lints it.
- Add `ruff format --check --force-exclude src tests tools` beside the existing
  `ruff check` in CI, the local gates, the pre-commit hook, and the testing docs.
- No prompt, catalogue, wording, architecture, dependency, or behaviour changes
  in this release.

## 0.8.1 — 2026-11-11

Prompt catalogue trim, with the release version guard and the omitted-checksum note.

- The release job checks that the tag, `pyproject.toml`, and the newest changelog
  heading agree before it builds, signs, or uploads anything. A `SHA256SUMS`
  file that is present but has no entry for the zip is reported as omitted, the
  install stays unverified, and the README and SECURITY notes describe that case.
- Door descriptions keep the contract. Duplicated stage rules are one copy,
  stages 6 and 7 tell the same story on both launch paths, and the shared rules
  are mirrored into the generated helper. The assembled prompt measures 24,365
  tokens and the 24 door descriptions measure 14,295 characters. The caps stay
  33,600 assembled tokens, 1,200 characters per door, and 24,000 for the catalogue.
- Unused public helpers are removed. The same paragraphs still reach the
  instructions and both setup prompts from the prompt files. Cursor still reads
  `CURSOR_SETUP_PROMPT`. Grok Build still reads `SETUP_PROMPT`.
- Four source pins that matched only a function name, a `def` line, or any
  function with source now point at the call they were meant to check.

## 0.8.0 — 2026-11-11

Structural cleanup round: one sentence splitter, one JSON record store, a real stage boundary, a single-sourced prompt bundle, module splits, and hygiene hardening.

Infrastructure:
- A single `textutil.sentences` splitter serves gates, brief_checks, cite_fit and
  stage7. Gates no longer silently drops sentences shorter than eight words; the
  EQR claim check scans the body before the reference list, so a bibliography
  line is not reported as copied prose. A single `textutil.content_words`
  extractor serves the assignment and cite-fit checks.
- A single `records.py` helper (tolerant read, repo-write guard, writer-unique
  temp file and atomic replace) replaces the hand-rolled JSON stores; each store
  keeps its own defaults and validation.
- New tests pin cross-module sentence segmentation, the short-sentence gate
  regression, and record concurrency/tolerant reads.

Stage boundary:
- `stage_track` is the orchestrator only: the 99-name re-export shim and the
  `_MINTING` contextvar recursion are gone. The state, landing and reply layers
  no longer import the orchestrator; the next-card mint and inherited-lock
  confirm arrive as injected `CardRun` callbacks. A guard test holds the
  boundary, and ARCHITECTURE.md describes the real layering.

Prompt bundle:
- `craft/voice.md` is the single rendered source for the shared voice/craft
  rules; stages 5-8 render it once. Precedence (brief > rubric/mark scheme >
  shared rules) and four repeated non-craft rules moved to one shared source,
  and 14 duplicate bullets were removed. The dead research seat and dead
  writing_basics re-exports were deleted. Prompt files are down about 31%, the
  helper doc about 34%, and the snapshot about 12.5%; new tests cap the
  assembled instructions plus door descriptions and fail on new duplicated
  long lines.

Module splits and adapter:
- `first_run.py` (2,141 lines) is split into `first_run_common`,
  `first_run_install`, `first_run_host`, `first_run_mac` and `first_run_cli`
  behind a thin facade. `late_chain.write_stage10` and
  `stage_track._build_stage_body` are split into named steps, and the stage-7
  skip probe is one predicate.
- MCP adapter tests pin the 24 typed tool schemas, the private call-path
  touchpoint, and active host-line replacement. Production asserts became
  explicit raises; a `py.typed` marker and a POSIX classifier were added.

Hygiene:
- The `fcntl` import is guarded with a clear Unix-only error; `state.json`
  writes take an fcntl lock; legacy setup adoption only accepts real product
  folders; an essay.intake mount-parity test was added. README states that
  macOS or Linux is required.
- The installer now reports a `SHA256SUMS` file that exists beside the zip but
  does not list it, instead of silently treating that file as absent; the result
  stays `upload_verified: false` with a note saying why.

## 0.7.0 — 2026-11-11

Hardening round: bound confirm side effects, real launch/install branches under test, a verified release chain, and a typed Confirm fallback.

Confirm:
- `essay.setup` binds the Consensus key and Unpaywall email by SHA-256 in the
  draft payload, so a save call that repeats different values is refused; the
  values are never echoed or stored in the draft record.
- `essay.dig` and `essay.research.summary|full` return `cardDigest` on the draft
  and require it on the save call. Confirm re-derives it from the stored payload
  and shown card, so a local edit to the draft record's card is refused. Drafts
  written before the binding refuse with a "show this step again" action.
- A typed yes, ok, or Confirm saves the waiting card when the host cannot send
  the card fields; a supplied card field still has to be the Confirm action.
  Student-facing next and refusal text no longer carries model directives.

Install, launch, and install-path hardening:
- Removed every `PYTEST_CURRENT_TEST` branch from production. Spawn, MCP enable,
  config resolution, PATH exposure, Mac-folder discovery, and the idle clock use
  explicit injected collaborators; tests exercise the real branches with fake
  binaries and launchers, and a guard fails if the pytest key returns.
- `essay-writer --install-upload` verifies a zip checksum when one is available
  (`--upload-sha256`, a sibling `.sha256` file, or `SHA256SUMS`) and otherwise
  installs the zip as trusted operator input, reporting `upload_verified: false`.
  A zip without `requirements-runtime.txt` is refused, and there is no unpinned
  dependency install. Quarantine/provenance clearing is limited to app-generated
  sequence deliverables; operator-named files keep their marks.

Release proof:
- Release builds run on `ubuntu-24.04` with a pinned cosign release, verify each
  Sigstore signature and the GitHub attestation after signing, and CI's Ubuntu
  jobs are pinned too.
- A new reproduce workflow downloads a published release, rebuilds it from the
  tag with the pinned toolchain, and fails on any SHA-256 mismatch.

Tests:
- Added confirm-binding, typed-Confirm/UX, no-pytest-env, and release-proof
  guards; the docs, sdist, and unfenced-content guards stay green.

## 0.6.3 — 2026-11-11

Review follow-up fixes: truthful claims, a document fence, and packaging coverage.

Docs and claims:
- Say what the Confirm gate actually guarantees: a save, stage advance, or
  deliverable write needs a matching draft, while a draft call writes the draft
  ledger, tracking note, and pointer; stage 5 stores its first draft and
  advances on its draft call by design. Name the shown-card and setup-credential
  digest limits, and say that tighter binding is planned.
- Name document bodies (uploads, briefs, PDFs, fetched pages) as untrusted in
  the threat model, scope `safe_url` to content-driven fetches with the installer
  and pip exceptions, correct the vendored-bootstrap sentence (no local patch),
  and call an `--install-upload` zip trusted operator input.
- Refresh the release-verification instructions (macOS `shasum`, current assets,
  `cosign verify-blob`, `gh attestation verify`), the supported-versions table,
  the v0.6.1 re-cut history, and the architecture wording; remove drifting test
  counts and fix the glossary link.

Prompt fence:
- Add an untrusted-content fence to the server instructions, both seats, and
  every stage's rules: document text is quoted evidence, never instructions.
  Mark `essay.originals` read results untrusted and say so in the tool
  description.

Packaging and tests:
- The sdist now carries `HISTORY.md`, `requirements-runtime.in`, and the
  remaining tracked GitHub/pre-commit files.
- CI and the release workflow require the sdist to carry every tracked file and
  the wheel rebuilt from the sdist to be byte-identical to the checkout wheel;
  CI checkouts set `persist-credentials: false`.
- Add docs-truth, sdist-completeness, and untrusted-content guards; the
  upgrade-card test no longer writes its marker into the checkout.

## 0.6.2 — 2026-11-11

Writing-quality, citation-policy, and recovery round.

Narrative citations:
- Personal names in prose are recognised, including Unicode names, titles,
  initials, name particles, Oxford lists, and `et al.` with or without a comma
  before the year. A gathered `et al.` citation matches; an ungathered one
  fails. Narrative and parenthetical forms leave the same word count.
- Policy B: a parenthetical citation, or a narrative citation with a clear
  person cue, is a hard failure when it was not gathered. A lone ordinary name
  plus a year is a possible citation: gate 7 passes, the token is named on
  `questionable_citations` and the gate's `questionable` list, and Word is still
  written. Cite-fit still reports the gap. A hard miss still refuses Word.
- Common labels are not citations: document and event head nouns, months,
  weekdays, and five-plus organisation initials stay silent. Accepted limits
  (multi-word labels outside the list, `Page`/`May`/`June` collisions,
  two-to-four-letter all-caps acronyms) are documented in the README and the
  review note.
- Gate 9 requires author and year metadata whenever a citation record is
  present, including a possible one.

Recovery and setup:
- A damaged confirm journal is renamed to `.stage.commit.damaged-<UTC stamp>`
  and is not applied. The next save continues and names the set-aside file. If
  the rename fails, the save refuses, names the journal path, and says to move
  that file out of the tracking folder; the damaged file stays in place. A
  valid torn journal still replays; a damaged `state.json` still raises.
- A setup record written only beside the app, up to two folders under the home
  directory, is copied to `~/.essay-writer/setup.json` with its secret and is
  read from there. A test root does not write the real
  `/workspace/Essay-writer/setup.json`.
- The plagiarism scan, gathered-text reads, and the module brief accept UTF-8,
  UTF-8 with a BOM, and UTF-16 with a BOM. cp1252 is still refused as
  `gathered-encoding`; an unreadable file is `gathered-unreadable`, not bad
  UTF-8.

Other fixes:
- The Release workflow is dispatched against a draft release and attaches
  assets, signatures, and provenance before publication, so the repository's
  immutable-release setting does not reject them.
- The word band and section budget share one citation-count flag. An explicit
  pack flag wins, then the mark scheme, the brief, and the studied default; the
  pack minimum and maximum stay as sent.
- `keep` marks an inherited lock only after the save stores. A failure to mark
  the lock leaves the stage saved and says so.
- The first-run folder check reads the app path on the setup record.
- A repeat stage 10 write reuses the previous copy when the pack is unchanged,
  the marker says the sequence file was written, and the final file is present.
- A launch is remote for a remote flag, an `--endpoint`/`-e` URL, or a URL
  token. A model named `cloud-agent` and a URL inside a longer instruction are
  not launches.
- Tests: 1110 (8 terminal-backed cases skip on hosts without a pty); ruff,
  mypy, docs, and the prompt snapshot are current.

## 0.6.0 — 2026-11-05

Bootstrap v0.2.0 and the Python version policy.

- The vendored bootstrap core is upstream `python-mcp-bootstrap` v0.2.0 (tag
  `v0.2.0`, commit `fd8e0b9`), byte-identical to the release: the local
  requirements patch is gone because the hash-pinned install is upstream now.
  `VENDOR.json` records the source, the release, and the file SHA-256.
- Install command order is upstream's: `requirements-runtime.txt` installs with
  `uv pip install --require-hashes -r ... --python <venv python>` first, then
  the project with `uv pip install --python <venv python> --no-deps -e .`. A
  copy without the requirements file keeps the single upstream install.
- The Python floor is 3.12 for the package and for the vendored core; the
  adapter keeps `REQUIRED = (3, 12, 0)` explicit. `first_run.py` now says 3.12+;
  the product provisioning pin stays 3.15.2.
- Version policy: CI runs the 3.12, 3.13, 3.14, and 3.15 lines with
  `check-latest: true` and prints the resolved patch (`python -VV`). Coverage
  stays on the 3.12 cell, the macOS job runs 3.15, the artifact job builds on
  3.12, and `release.yml` keeps the exact 3.12.13 build pin. A committed root
  `.python-version` names the 3.15 line.
- `tests/test_version_policy.py` guards the floor, the CI lines, the committed
  `.python-version`, and the `VENDOR.json` release and hash.
- `ARCHITECTURE.md` and `docs/testing.md` describe the v0.2.0 vendoring and the
  3.12 coverage cell.
- Tests: 1078 passed (8 terminal-backed cases skip on a host without a pty);
  ~87% coverage.

## 0.5.0 — 2026-11-05

Final clean-up round.

- `stage_track.py` is split again: it is now 847 lines with 4 top-level
  functions. `stage_landing.py` (396 lines) owns saved-stage storage, report
  attaching, mid-run and missed-stage records, inherited-lock bookkeeping, and
  the stage 6 opener; `stage_replies.py` (382 lines) owns the draft and save
  reply writers and the no-op result. The orchestrator re-exports every layer,
  so existing imports and contract pins are unchanged. Function bodies are
  byte-identical apart from one call-time import that closes the only cycle
  edge.
- Coverage is measured: `pytest-cov` is a dev dependency, coverage config sets
  an 85% floor (current baseline ~87%), CI runs coverage on the Ubuntu 3.12.13
  cell, and `docs/testing.md` documents the command and the floor.
- CI housekeeping: Python 3.13 joins the Ubuntu matrix (3.12–3.15); workflow
  concurrency cancels superseded runs; the test job carries a timeout.
  `requirements-ci.txt` is regenerated with the new dev dependency.
- Cursor installer guidance: the hash binds the bytes, not the vendor's
  identity. README, FIRST-RUN, and SECURITY recommend the manual install for a
  trust-sensitive setup.
- README badges for CI, the Python floor, and the license; `pyproject.toml`
  gains keywords, classifiers, and project URLs.
- Tests: 1060 passed, 8 skipped; ~87% coverage.

## 0.4.1 — 2026-11-05

Small follow-ups from the third review pass.

- `essay-writer --install-upload` (the update path on an already-installed
  copy) now uses the same standard as `python first_run.py`: when the zip
  carries `requirements-runtime.txt`, it installs the hash-pinned runtime
  requirements with `--require-hashes` first, then the project with
  `--no-deps`. A hash or network failure stops before the project install.
  Older zips without that file keep the single upstream install; the report
  lists the commands and sets `requirements_verified`.
- Residual report ids are public behaviour names: `install-root`,
  `deliverable-packing`, `mac-handoff`, and `open-grok-session` replace the
  internal ticket ids. The residual text is unchanged.
- Tests: 1060 passed, 8 skipped.

## 0.4.0 — 2026-11-05

Security and state-model round; no intended workflow change.

Install integrity:
- The first-run install now runs `uv pip install --require-hashes -r
  requirements-runtime.txt` before the project install, which then runs with
  `--no-deps`. A hash mismatch or network failure stops the install. The
  vendored bootstrap carries this one documented local patch; `VENDOR.json`
  records it and the new file hash.
- Cursor CLI install is no longer TOFU. Consent (`--install-cursor`) authorises
  the download only; setup reports the file's SHA-256 and stops with
  `cursor-install-needs-hash`. Execution requires that expected hash
  (`--cursor-sha256` or `ESSAY_WRITER_CURSOR_INSTALL_SHA256`); a mismatch stops
  with `cursor-install-hash-mismatch` and runs nothing.

Network and data:
- Every remote fetch goes through the new `safe_url` opener: public http(s)
  only, every resolved address checked (no loopback, private, link-local,
  reserved, multicast, or ULA), redirects re-validated and capped at three
  same-scheme hops, and hard byte caps (25 MiB paper, 2 MiB research API, 1 MiB
  look-up). Over-cap bodies are refused, not truncated.
- `essay.debug.export` redacts each member before zipping: absolute home/volume
  paths, emails, `Bearer`/`x-api-key` values, and common token shapes. Key names
  stay; values go.
- Secret files are created with mode 0600 before any content is written (setup
  secrets and the remembered Mac folder), instead of write-then-chmod.

Trust model:
- `SECURITY.md` now has a plain threat-model section: the Confirm gate binds
  arguments and file fingerprints, not human identity; the host model is
  trusted to relay the person's yes; the server cannot prove a human clicked.
  Attended sessions, the reviewer server, and read-only where possible are the
  recommendations.

State model:
- The stage pipeline is typed: new `StageArgs`, `StageContext`, and
  `ConfirmState` dataclasses replace the 15–17 argument helpers and the
  `"_state": True` sentinel dict. Internal helper parameters go from 52 to 13 and
  the untyped state-key reads from 39 to 0. `essay_stage` keeps its MCP tool
  signature.
- `stage_track.py` stays the orchestrator and keeps its reply-dict contract.

Fixes:
- A fresh clone no longer emits `SyntaxWarning: 'return' in a 'finally' block`
  from `build_status.py`.
- `ARCHITECTURE.md` fixed two stale claims: the prompts live in the packaged
  `prompts/` bundle, and the vendored bootstrap source repository is public.

Tests: 1058 passed, 8 skipped.

## 0.3.1 — 2026-11-05

Structural clean-up; no intended behaviour change.

- `src/essay_writer/stage_track.py` is split: the pointer and its commit journal,
  the stage lock, the tracking-note renderer, and the held/refused reply bodies
  move to the new `stage_state.py` (1,334 lines). `stage_track.py` keeps the
  orchestrator and the run branches, and re-exports the state layer so existing
  imports keep working. The kept code is unchanged.
- Test files are renamed from `test_*_ac.py` to behaviour names, and private
  ticket/PR references are removed from test docstrings. `AC1`, `AC2`, … labels
  are now documented as stable local acceptance-criterion ids, not tracker
  references.
- README, CONTRIBUTING, ARCHITECTURE, `docs/testing.md`, and `docs/GLOSSARY.md`
  are updated for the new suite layout and the module split.
- Tests: 1006 passed, 8 skipped.

## 0.3.0 — 2026-11-05

Distribution and release engineering:

- The source distribution is complete and self-testable: it carries the full
  test suite, `conftest.py`, `helpers.py`, `pty_support.py`, fixtures, the prompt
  snapshot, docs, and tools. `pytest` works from the extracted sdist.
- Builds are reproducible. `SOURCE_DATE_EPOCH` comes from the tagged commit;
  `tools/reproducible_build.py` builds twice, normalizes the sdist, and fails on
  any hash drift. The release workflow runs the same check before signing.
- New CI `artifacts` job: build the wheel and sdist, install the wheel into a
  clean environment, extract the sdist, and run the full suite from it. The
  release workflow runs that artifact test before uploading or signing.
- macOS CI job added, matching the Mac-centric product.
- The CI "Repository checks" step no longer greps for a private domain-word
  denylist. It checks generic things a public repository should check: machine
  paths and secret material.

Install path:

- Runtime dependencies are exact-pinned (`mcp==2.3.0`, `python-docx==1.2.0`) and
  `requirements-runtime.txt` is hash-pinned for a verifiable manual install.
- Setup no longer pipes `curl … | bash` into a shell. It downloads the Cursor
  installer to a file, records the file's SHA-256, and runs it only after
  explicit consent (`--install-cursor` or `ESSAY_WRITER_ALLOW_CURSOR_INSTALL=1`).
  Without consent it changes nothing and prints the manual command.

Python floor:

- The package floor is 3.12, verified with the full suite on CPython 3.12.13
  (1006 passed, 8 skipped — the same as the 3.15 baseline). `pyproject.toml`,
  ruff, mypy, `uv.lock`, and the CI matrix move together.
- The first-run bootstrap still provisions a private CPython 3.15.2 when it has
  to; the floor only says what the package itself runs on.

Documentation:

- README rewritten around what the project is, why it is public, what it is not,
  and what setup does to a computer. Academic-integrity position stated plainly.
- `HISTORY.md` records that `v0.2.1` is an import snapshot and that `0.3.0` is
  the first normal release.
- New `docs/GLOSSARY.md` maps the private vocabulary (doors, seats, spine,
  shelf, dig, canon, mid-office) to plain terms.
- New `docs/testing.md` explains the `_ac` naming, the contract pins, and the
  prompt snapshot; `tools/update_prompt_snapshot.py` regenerates the snapshot
  and supports `--check`.
- The version is checked against `pyproject.toml` instead of a hard-coded string,
  so the package and the metadata cannot drift.

## 0.2.1 — 2026-11-04

- Python floor is 3.14; CI pins 3.14.10 and 3.15.2.
- 3.14 compatibility fixes for `datetime.UTC` and `Path.rglob` test monkeypatching.

## 0.2.0 — 2026-11-04

- One `prompts/` bundle owns stage, genre, craft, review, front-office, status, and install text.
- Stages use shared bodies plus additive genre sections; the override/concatenation path is removed.
- Confirm and status text each have one source; briefing and door descriptions render it.
- Seat prompts are packaged with the bundle; docs generation keeps the exact prompt blocks in sync.
- Version now reports `0.2.0`. No intended workflow or tool behaviour change.
- Tests: 980 passed, 8 skipped.

## 0.1.2 — 2026-11-02

- README and release wording: stable source release.

## 0.1.1 — 2026-11-02

- README: demonstration / limited-maintenance status line; model-assisted purpose moved into the opening.
- Add GitHub bug-report issue template mirroring CONTRIBUTING.

## 0.1.0 — 2026-11-01

- First public source release.
- Ten-stage, confirm-gated essay workflow with MCP tools.
- Research packs, Harvard reference checks, invent-forbid citation rules, and Word output.
- Synthetic teaching fixtures and behaviour tests.
- Documentation and type-boundary cleanup.
- Stage runner split into named helpers; pointer and stage-result boundaries typed.
