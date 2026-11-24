---
name: verify-essay-writer
description: >-
  Drive Essay Writer the way a student does, through the shared MCP doors
  (essay.health, essay.setup, essay.intake, essay.dig, essay.research.full,
  and the Word doors). Use when proving a research gather and citation list,
  the first-draft Word file after review, or the stage 10 Word file.
---

# Verify Essay Writer

Drive the student path on the writer doors. Cursor and the Build shell both mount `essay_writer.server.HANDLERS`. The command both shells run is `essay-writer` with no arguments, from `placeholders/mcp.config.json` and `.cursor/mcp.json`. This harness starts that same server with `python -m essay_writer`.

Keep one run on its own student folder. Set `ESSAY_WRITER_ROOT` to that folder. It must sit outside this checkout. On a machine where `/workspace` is the checkout, omitting `app_path` and `kb1_path` would write into the checkout. Always name both paths, and keep them outside the checkout.

Do not print `CONSENSUS_API_KEY`, `OPENALEX_API_KEY`, or `ESSAY_WRITER_UNPAYWALL_EMAIL`. The helper forwards those values into the server process when they are already set. It does not put them on a door argument.

The script reads the installed package version. Doctor fails when `essay.health` reports a different version.

## Launch

From an empty student folder, launch creates the door tree and stops the server it started.

```bash
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer launch
```

What that does:

1. Creates `/tmp/essay-verify-student/student` and `/tmp/essay-verify-student/KB1` when `ESSAY_WRITER_ROOT` and `ESSAY_WRITER_VERIFY_KB1` are unset. Both stay outside the checkout.
2. Installs the hash-pinned packages in `requirements-runtime.txt` with `pip install --require-hashes` under `/tmp/essay-verify-student/deps` when `essay_writer` or `mcp` cannot be imported. The checkout is imported from `src` on `PYTHONPATH`.
3. Starts `python -m essay_writer` on stdio with `ESSAY_WRITER_ROOT` set to the student folder.
4. Calls `essay.setup` with `confirmPhase` `draft`, then `confirm`. `app_path` is the student folder. `kb1_path` is the KB1 folder. `acknowledge_skipped_searches` is true so a missing stored email or key does not block the folders. Values already in the environment are not sent as arguments.
5. Checks that `Essay-writer/`, `uploads/`, and `unassigned/` exist, then calls `essay.health`. Ready means `alive` is true, `version` is the installed package version, and `app_path` is the student folder.

Override the folders with `ESSAY_WRITER_ROOT`, `ESSAY_WRITER_VERIFY_KB1`, `ESSAY_WRITER_VERIFY_DEPS`, and `ESSAY_WRITER_VERIFY_RUN`. Pass `--run-dir` when the run directory is not under `/tmp/essay-verify-*`. Evidence defaults to `/tmp/essay-verify-evidence` (`ESSAY_WRITER_EVIDENCE`).

## Doctor

Run this before a drive, and again whenever a door looks wrong.

```bash
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer doctor
```

Doctor starts a new server on the same `ESSAY_WRITER_ROOT` and calls `essay.health`. It passes only when all of these hold.

- `ok` and `alive` are true.
- `version` is the installed package version.
- `app_path` is this run's student folder.
- The mounted doors include `essay.dig`, `essay.health`, `essay.research.full`, and `essay.pack.render_word`.
- Consensus, OpenAlex, and Unpaywall are reported as present or absent. The values are not included.

`essay-writer --health` is the same `essay_health` function. Doctor uses the MCP door so the check is the one a student host calls.

## Drive

Read `features/README.md`, then the feature file. One command drives the research gather and citation list.

```bash
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer drive-research-gather
```

That command places `brief.md` in `unassigned/`, files it with `essay.intake`, opens sequence 1 with `essay.sequence.new`, and calls `essay.dig` draft then confirm. The brief states a question and 2000 words. It states no source count. The floor for that brief is 16.

OpenAlex is called. Consensus is called when a key is already in the environment and `ESSAY_WRITER_CONSENSUS` is not `0`. Unpaywall runs only when an email is already in the environment. Confirm writes `Essay-writer/<module>/sequences/<n>/dig-card.json` and does not call the catalogs again.

The distinct citation-list work count is the number of gathered records that have a title, an author, and a year. The helper counts those with `essay_writer.source_floor.distinct_works` on the OpenAlex and Consensus hits stored on the card.

When the gather is not blocked and dig saved an abstract or a PDF, the helper calls `essay.research.full` draft then confirm. Sources are the locators dig returned whose text uses a word from the assignment question. Clarify fields are left open. The citation list, when stage 4b writes it, is `Essay-writer/<module>/sequences/<n>/citation-list.json`.

The command exits 2 when a citation list or a `.docx` is written while the distinct count is under 16 and the card still has `further_page` true. That is a failed journey. Do not lower the floor or skip the remaining pages to make it pass.

The first-draft Word file and the stage 10 Word file are mapped and not driven by this command. Use their feature files when you drive them.

## Evidence

The helper writes proof under `/tmp/essay-verify-evidence/`.

- `launch.json` records the student folder, the version, and the mounted door names.
- `doctor.json` records the health check.
- `research-gather.json` records the distinct works (title, author, year), the floor, which catalogs ran, and whether the citation list or a Word draft was written.
- `run-state.json` records the folders cleanup will remove.
- `cleanup.txt` lists the evidence names that were still there after cleanup.
- `deny-list.txt` is the public-wording scan result when you run `scan-public`.

The files name titles, authors, and years returned by the catalogs. They do not name keys or email addresses.

## Cleanup

```bash
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer cleanup
```

Cleanup reads `run-state.json`. It sends TERM to the server process id stored at launch when that process command still contains `essay_writer`. It does not read `/proc`. It deletes the run directory only when that directory carries the marker written at launch, and only when the directory is `/tmp/essay-verify-*` or the directory passed again with `--run-dir`. A shared parent, a directory this script did not create, and a missing marker stay in place. It does not delete `/tmp/essay-verify-evidence/`.

Run cleanup after a failed drive as well, so a broken attempt does not leave a server or a student folder behind. Start the next launch from an empty student folder.

## Helpers

The helper is `.cursor/skills/verify-essay-writer/scripts/verify-essay-writer`. It is executable.

```bash
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer launch
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer doctor
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer drive-research-gather
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer cleanup
.cursor/skills/verify-essay-writer/scripts/verify-essay-writer scan-public .cursor/skills/verify-essay-writer
```

`scan-public` hashes the same deny-list entries the tests already store and reports `NO HITS` or the opaque id of a hit. It does not print the phrase.

Feature recipes live in `features/`. When the product doors change, update the feature file that names the door, then run that feature once and keep the evidence.
