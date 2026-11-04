# Changelog

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
