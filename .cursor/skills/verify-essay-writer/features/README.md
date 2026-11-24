# Essay Writer verification map

This directory is the source for verifying Essay Writer the way a student uses it. Read this index, then use the matching feature file.

The surface is the writer MCP server. The command is `essay-writer` with no arguments (`placeholders/mcp.config.json`). Cursor and the Build shell mount the same handlers. The reviewer is a second process, `essay-writer --reviewer`, and it only adds `essay.review`.

## Baseline preconditions

- Launch with `.cursor/skills/verify-essay-writer/scripts/verify-essay-writer launch` so the student folder starts empty.
- `ESSAY_WRITER_ROOT` is that student folder and sits outside the checkout.
- `essay.setup` has created `Essay-writer/`, `uploads/`, and `unassigned/` there.
- Doctor reports the installed package version, `alive` true, and `app_path` equal to that folder.
- Do not drive a server that this run did not start. Do not point `ESSAY_WRITER_ROOT` at the checkout or at another live essay folder.

## Driving conventions

- Start every recipe from the launched student folder unless the feature names other state.
- Call the doors with `confirmPhase` `draft`, then `confirm`, and send `cardDigest` from the draft when the draft returns one.
- Treat module ids as the codes the product already documents, such as `MOD1004AA`. A sequence id looks like `MOD1004AA-1`.
- Leave catalog keys and emails in the environment. Do not pass them as door arguments and do not print them.
- Keep proof files in `/tmp/essay-verify-evidence/`. Cleanup removes the run directory this script created and leaves that evidence directory.

## Proof and skip reporting

- Record the door call and the file it wrote, not only the final sentence.
- A gather proof includes `dig-card.json` on the sequence and the distinct work count (title, author, year).
- A Word proof includes the `.docx` path and the stage that was allowed to write it.
- Say which feature file and which entry you drove.
- An entry you did not drive is not verified. Say the command you would have run and the precondition that was missing.

## Feature entry contract

Each feature file has an H1, one opening paragraph, and these H2 sections in order.

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with verify-essay-writer`
4. `Gotchas`

## Features

- [Research gather and citation list](./research-gather.md) covers the assignment file, `essay.dig`, and the citation list written at stage 4b.
- [First-draft Word after review](./first-draft-word.md) covers the stage 5 draft, the stage 6 review, and the first Word file.
- [Stage 10 final Word](./stage-10-word.md) covers the stage 9 review and the final Word file.
