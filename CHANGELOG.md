# Changelog

## Unreleased

- README rewritten for the reader: who it is for, what setup does to the computer, a session before the setup prompt, and status and help at the foot.
- Developer setup, first-run bootstrap, and vendoring notes move to CONTRIBUTING.md and ARCHITECTURE.md.

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
