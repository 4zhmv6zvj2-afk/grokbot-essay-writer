# Essay Writer

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/4zhmv6zvj2-afk/grokbot-essay-writer/badge)](https://securityscorecards.dev/viewer/?uri=github.com/4zhmv6zvj2-afk/grokbot-essay-writer)
[![CI](https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/actions/workflows/ci.yml)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/16338/badge)](https://www.bestpractices.dev/projects/16338)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A confirm-gated MCP server that helps a student research a university assignment
and turn it into a Word essay. It is the backend of the Essay Bot agent product;
this repository is its source.

## What this is

- **An MCP server for one workflow.** The writer seat's 24 tools take a single
  essay from brief to `.docx`: assignment, research, plan, annotated
  bibliography, critical review, first draft, re-read, feedback, edit,
  references, and final Word.
- **A separate reviewer seat.** `essay-writer --reviewer` serves one tool,
  `essay.review`, for the EQR pass. The writer refuses the Word write on stage 6
  and stage 9 until that pass returns `PASS`.
- **Confirm-gated and local.** A save, stage advance, or deliverable write needs
  a matching draft: a stage draft call writes the draft ledger (`.drafts/`), the
  tracking note, and the stage pointer, and the Confirm re-derives the same
  argument digest and checks the on-disk file fingerprint. Stage 5 is the
  designed exception: it stores the first draft and advances to stage 6 on its
  draft call, with no card. `essay.dig` and the research doors bind the card
  they showed with a `cardDigest` that confirm re-derives and requires, and
  `essay.setup` binds the Consensus key, Unpaywall email, and OpenAlex key by SHA-256 so the
  save call must repeat the same values. A typed yes, ok, or Confirm saves the
  waiting stage only when the host cannot send the card fields; a supplied card
  field still has to be the Confirm action; it never saves a later stage.
- **Prompt-heavy by design.** The stage instructions, genre rules, and
  validation checks are the product. They are packaged with the code under
  `src/essay_writer/prompts/` and are not fetched at runtime.
- **Published as source.** Students and operators can read exactly what runs on
  their computer, and anyone can verify that a release was built from this
  repository.

## Why this is public

The product is distributed as source, so publishing it is the distribution
mechanism, not a side effect. It also makes the safety claims checkable: what
the agent can do to a computer, what the Confirm gate refuses, and what a
download was built from.

This is not a community library and is not run like one. It is maintained by
one person, in the open, for bug reports. There is no feature roadmap and no
governance process. See [CONTRIBUTING.md](CONTRIBUTING.md).

## What it is not

- Not a submission service: it never submits. The tool drafts the essay from
  the sources the workflow gathered; the student directs the work, reviews each
  stage, confirms saves on a card (stage 5 stores its first draft on the draft
  call, as documented), and owns what is submitted.
- Not a hosted service: no server, no account, no bundled keys. It is a local
  process the agent talks to.
- Not a general-purpose Word or referencing library.
- Not on PyPI. Releases are source plus verifiable build artifacts on GitHub.

## Academic integrity

The tool researches and gathers sources, then drafts, revises, and formats the
essay from them. The student directs the work, reviews each stage, confirms
saves on a card (stage 5 stores its first draft on the draft call, as
documented), and owns what is submitted. The tool does not decide what is
acceptable at the student's institution, and it never submits anything.

- The student owns what they submit. Using a drafting aid without disclosure, or
  where the institution forbids it, is the student's decision and
  responsibility. The tool does not police it, and the maintainer does not
  endorse it.
- The workflow keeps the student in control: each stage is shown in chat, saves
  are confirmed on a card (stage 5 stores its first draft on the draft call, as
  documented), and the final Word file is theirs.
- If your course forbids generative assistance, do not use this.

## Using Essay Bot (students)

If Essay Bot is already on your Grok Bot, there is nothing to install — start a
new essay.

Words the chat uses are in
[Student-facing terms](docs/GLOSSARY.md#student-facing-terms). The stage rules
are in [docs/workflow.md](docs/workflow.md). Shape notes for an essay, a report,
or a reflective diary are in
[docs/academic-writing-helpers.md](docs/academic-writing-helpers.md).

You share the assignment and start a new essay. You review each stage in the
chat. A save waits on that stage's Confirm card. If the card cannot be used,
typing yes, ok, or Confirm saves that same waiting stage. One Confirm saves
that stage only.

1. **Analyse the task.** The brief is read as you wrote it.
2. **Establish the focus.** An essay locks a thesis. A report locks purpose and
   scope. A reflective diary locks its entries. Once the brief names the kind
   of writing, the chat uses that label: Establish a thesis, Establish purpose
   and scope, or Establish the entries.
3. **Write the plan.** Once the brief names the kind of writing, the chat uses
   that label: Write an essay plan, Write a report plan, or Write a diary plan.
   An essay plan follows the thesis. A report plan holds the central theme, the
   one-sentence answer. A diary plan holds the entries.
4. **Annotated bibliography**, then the **critical review.** Research finds
   papers. It downloads a PDF when it can, or gives you the title and a link.
5. **Write your first draft.** This stage is the exception. The first full
   draft is saved when it is written, then shown. There is no Confirm card
   between that draft and the next stage.
6. **Re-read and make changes.** This is your read-through. The chat shows a
   short list once, then you edit. It does not rewrite the draft for you.
7. **Ask for feedback.** The chat asks about structure, argument, and clarity,
   then edits from your answers.
8. **Edit and redraft.** A reflective diary says "Edit and redraft your diary."
9. **References and citations.** Harvard referencing is checked against the
   sources already gathered.
10. **Finish the Word file.** The tool does not submit.

A draft is written from those sources. You own what you submit.

The finished essay is a Word file (`.docx`). Output is Word only. Referencing
follows Harvard
([docs/referencing-harvard.md](docs/referencing-harvard.md)).

The chat names the folder the tool wrote. It does not invent a Documents path.

- When a Mac folder was chosen at setup, that place is
  `Documents/Essay Bot/<module>/<essay id>/`, or the other folder you named.
- When no Mac folder was chosen and Documents is already on this computer, the
  fallback place is `Documents/<module>-10/`.
- When that folder is not on this computer, the file stays in the chat and on
  this sequence.

A pasted brief is read as you wrote it. Genre: and Question: lines are still
understood. The chat asks when it cannot tell the format or the question, and
the answer is stored beside the brief rather than written into it.

## Citation policy

When the assignment states no source count, the essay cites at most 12 distinct works per 1,000 words. A stated count above that cap raises the cap. The rate is not added to the stated count.

A parenthetical citation, or a narrative citation with a person cue (`et al.`,
a title, an initial, a joint list, a multi-word personal name, or a shouted
surname of five or more letters), must match a gathered source or Word is not
written. A lone ordinary name plus a year is a possible citation: gate 7
passes, the token is named, and Word is still written. An invented lone name
is flagged, not blocked.

Accepted limits of that rule:

- A multi-word label with no word on the non-person list can still be treated
  as a personal name and hard-fail, including `New York (2020)`, `Supreme Court
  (2020)`, and `United States (2020)`. Adding words to the label list is a
  separate change.
- `Page`, `May`, and `June` stay silent label matches. A parenthetical
  `(Page, 2020)` is still a hard failure.
- All-caps labels of two to four letters stay acronyms (`GDP`, `OECD`, `BUSH`,
  `KIM`).
- The author/year metadata check looks at sources already on the pack. With no
  pack sources, that check has nothing to reject.
- Cite-fit still reports an ungathered lone name as a gap.

## Setting it up (operators)

Setting up the Grok Bot on a computer is an operator task. The full procedure is
[FIRST-RUN.txt](FIRST-RUN.txt); the short version is to paste this into the Grok
Bot chat:

```text
Download https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer.
Read the README and FIRST-RUN.txt.
Add Essay Bot to this Grok Bot from docs/templates/essay-bot.share.json.
Set up grokbot-essay-writer.
```

Essay Bot will ask, in the chat, for:

1. Where Word files should be saved on your Mac (or skip for chat-only).
2. Whether setup may install the Cursor CLI, then sign-in on the Grok Bot
   computer when setup asks for it.
3. Your Consensus key and plan, an email for free paper lookup, and a free OpenAlex key.

Paste keys only when the chat asks for a secret — not into ordinary messages.

## Updating

An installed copy updates from the newest GitHub release:

```text
essay-writer --check-update
essay-writer --update
```

`--check-update` asks the GitHub release API for the newest version and prints
the current version, the newest one, and whether an update is available. When
that API is blocked or rate-limited, it reads the public releases feed and
builds the archive and `SHA256SUMS` URLs from the tag. `--update` downloads
those files, verifies the SHA-256, and does not check the Sigstore signature.
The signature check stays manual; see "Verify a release" below. It then
installs the hash-pinned runtime and the new package into the existing
environment and runs `essay.health`. If the requirements install succeeds and
a later step fails, the result says the environment changed and was not rolled
back. The essay tree (`/workspace/Essay-writer`: setup record, stored keys,
remembered Mac folder, essays) is not touched, and setup cards are not shown
again. Start a new chat after the update so the host launches the new code.

On a host whose proxy resolves external names to the standard fake-IP range,
set `ESSAY_WRITER_TRUSTED_EGRESS` to a subnet of `198.18.0.0/15` in the
environment or in the setup secrets file. One invalid token, or any network
outside that range, disables the opt-in. A proxy that uses another range, such
as `10.0.0.0/8` or `100.64.0.0/10`, is not supported: turn that routing off, or
use the standard fake-IP range. Leave the setting empty on every other host.

A git checkout updates with `git pull`; `--update` refuses a source checkout and
says so. Pass `--force` to replace a source checkout with the release package.

A copy older than the first release that carries `--update` updates once through
the first-run download above. After that, the CLI handles updates.

## What setup does to the computer

On the Grok Bot computer, setup will:

- Install the runtime dependencies from the hash-pinned `requirements-runtime.txt`
  first, then Essay Writer itself. A hash mismatch stops the requirements
  install before the package install. If the requirements install succeeds and
  the package install then fails, the result says those dependencies were
  installed and were not rolled back. The `essay-writer --install-upload` offline path requires
  a `requirements-runtime.txt` in the zip before it unpacks anything, and never
  falls back to an unpinned install. A zip checksum is optional: pass
  `--upload-sha256`, or put a matching `essay-writer.zip.sha256` / `SHA256SUMS`
  file beside the zip, and the installer verifies it; with no checksum it still
  installs and the result says `upload_verified` is false. A `SHA256SUMS` file
  that is present but lists no entry for the zip leaves the install unverified
  the same way, and the result says the file does not list it rather than
  treating the file as absent. The zip's build backend runs, so pass only a zip
  you produced or trust.
- Download a private Python 3.15.2 into that folder, only after you agree and only
  if no suitable Python is already there. It never changes the Python already
  installed on the computer.
- Save Word files to `Documents/Essay Bot`, or to a folder you name. If you
  choose neither, the essay stays in the chat.
- Install the Cursor CLI only if you say yes and it is missing, in two steps.
  Consent (`--install-cursor`) authorises the download only: setup fetches the
  installer to a file and reports its SHA-256, byte count, and path, then stops
  (`cursor-install-needs-hash`). Running it needs that expected hash
  (`--cursor-sha256 <hash>` or `ESSAY_WRITER_CURSOR_INSTALL_SHA256`); a mismatch
  stops with `cursor-install-hash-mismatch` and runs nothing. Setup never pipes
  a remote script into a shell. Without your yes it downloads nothing. The hash
  binds the bytes, not the vendor's identity: if vendor trust matters to you,
  install the CLI yourself with the command below and skip setup's automated
  path. To install it yourself:

  ```bash
  curl -fsS https://cursor.com/install -o cursor-agent-install.sh
  shasum -a 256 cursor-agent-install.sh   # Linux: sha256sum cursor-agent-install.sh
  bash cursor-agent-install.sh
  ```

## For developers

Python 3.12 or newer on macOS or Linux (the stage lock uses `fcntl`; Windows is not supported):

```bash
uv sync --extra dev
uv run pytest                      # the full suite
uv run ruff check src tests tools
uv run ruff format --check --force-exclude src tests tools
uv run mypy src
uv run python tools/generate_docs.py --check
uv run python tools/update_prompt_snapshot.py --check
uv run pytest --cov=essay_writer --cov-report=term   # CI floor 85%
```

- `src/essay_writer/server.py` — MCP entry and tool registration.
- `src/essay_writer/doors.py` — the tool catalogue (one "door" per tool).
- `src/essay_writer/stage_track.py` — the stage runner, cards, and confirm flow.
- `src/essay_writer/stage_state.py` — the pointer, the commit journal, and the
  stage lock. Imported by the stage runner; it never imports the runner back.
- `src/essay_writer/stage_note.py` — the tracking-note renderer and look reader.
  It does not write the pointer or the commit journal, and it never imports
  the orchestrator.
- `src/essay_writer/stage_hold.py` — the held and refused reply bodies. The
  pointer write stays in `stage_state.py`. It never imports the orchestrator.
- `src/essay_writer/stage_context.py` — the typed pipeline values (`StageArgs`,
  `StageContext`, `ConfirmState`).
- `src/essay_writer/safe_url.py` — the network opener for model- and
  paper-driven fetches (public http(s), redirect re-validation, byte caps).
- `src/essay_writer/stage_landing.py`, `stage_replies.py` — the landing/report
  helpers and the draft/save reply writers. The runner injects the card and
  confirm runners those helpers need.
- `src/essay_writer/prompts/` — the stage, genre, craft, and review text that is
  the actual product.
- `tests/` — behaviour and acceptance tests; `tests/fixtures/` is synthetic, no
  student work.

Start with [ARCHITECTURE.md](ARCHITECTURE.md), then
[docs/GLOSSARY.md](docs/GLOSSARY.md) for the private vocabulary (doors, seats,
spine, shelf, dig, canon, mid-office). The
[Student-facing terms](docs/GLOSSARY.md#student-facing-terms) section of that
page is the same vocabulary in plain English. [docs/testing.md](docs/testing.md)
covers how the suite is organised and how the prompt snapshot is regenerated.
[docs/operator-log.md](docs/operator-log.md) documents the operator debug log,
the event stream, and the internal environment overrides; and
[docs/writing-type-checklist.md](docs/writing-type-checklist.md) lists what a
new writing type must map before it can be saved.

`uv.lock` is the developer lockfile. `requirements-ci.txt` is the hash-pinned CI
environment; `requirements-build.txt` pins the build tooling; and
`requirements-runtime.txt` is the hash-pinned runtime set for a verifiable
manual install. There is no release on PyPI.

## Verify a release

From 0.9.19, a GitHub release includes the wheel, the sdist, and `SHA256SUMS`.
Each of those three files has a Sigstore signature bundle (`*.sigstore.json`).
The release also includes `provenance.intoto.jsonl`. Releases 0.9.15 through
0.9.18 shipped the wheel, the sdist, and `SHA256SUMS`. Those releases have no
Sigstore bundles and no build-provenance attestations.

Download 0.9.19's files into one folder, then check the checksums. The files
are `essay_writer-0.9.19-py3-none-any.whl`, `essay_writer-0.9.19.tar.gz`,
`SHA256SUMS`, the `.sigstore.json` bundle for each of those three files, and
`provenance.intoto.jsonl`.

```bash
# The checksums and filenames come from the release:
shasum -a 256 -c SHA256SUMS        # macOS; Linux: sha256sum -c SHA256SUMS

# Check the Sigstore signature on each signed file. The certificate identity is
# this repository's Release workflow on main, where the workflow is
# dispatched from.
cosign verify-blob \
  --bundle essay_writer-0.9.19-py3-none-any.whl.sigstore.json \
  --certificate-identity "https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  essay_writer-0.9.19-py3-none-any.whl

cosign verify-blob \
  --bundle essay_writer-0.9.19.tar.gz.sigstore.json \
  --certificate-identity "https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  essay_writer-0.9.19.tar.gz

cosign verify-blob \
  --bundle SHA256SUMS.sigstore.json \
  --certificate-identity "https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  SHA256SUMS

# Check the build provenance GitHub recorded for that release workflow run.
# The attestation covers the wheel and the sdist.
gh attestation verify essay_writer-0.9.19-py3-none-any.whl \
  --repo 4zhmv6zvj2-afk/grokbot-essay-writer
gh attestation verify essay_writer-0.9.19.tar.gz \
  --repo 4zhmv6zvj2-afk/grokbot-essay-writer
```

Releases from 0.3.0 onward use a reproducible build on a pinned runner image
(`ubuntu-24.04`) with a pinned cosign release. The release workflow builds the
wheel and the sdist twice in one run with `SOURCE_DATE_EPOCH` set to the tagged
commit's time and the hash-pinned build tooling, requires identical SHA-256
hashes before it uploads, signs, or attests anything, then verifies each
Sigstore signature and the GitHub attestation after signing. Releases 0.9.15
through 0.9.18 were not built by that workflow. A separate reproduce workflow
downloads a published release, rebuilds it from the tag with the same pinned
toolchain, and fails if the SHA-256 set differs. You can rebuild a tag the same
way:

```bash
git checkout v0.9.19
python -m pip install --require-hashes -r requirements-build.txt
SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" \
    python tools/reproducible_build.py --outdir dist-rebuild
cd dist-rebuild && shasum -a 256 *.whl *.tar.gz   # Linux: sha256sum
```

If those hashes equal the release's `SHA256SUMS`, the artifacts are byte-identical
to what the tag builds here. `tools/reproducible_build.py` normalizes the sdist
metadata to `SOURCE_DATE_EPOCH` and fails unless both builds are byte-identical;
a plain `python -m build` does not reproduce the sdist.

The sdist is complete: it carries the tests, fixtures, and prompt snapshot, so
`pytest` works from the extracted source distribution. The 0.2.1 artifacts
predate this and are not reproducible; see [HISTORY.md](HISTORY.md).

## Project status

Stable source release, maintained for reported bugs. The public history starts
with a 0.2.1 import snapshot; 0.3.0 is the first normal release, built and
tagged from commits in this repository. [HISTORY.md](HISTORY.md) explains that
plainly. The trust model, including what the Confirm gate does and does not
prove, is in [SECURITY.md](SECURITY.md#threat-model). Security reports:
[SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE) © 2026 `4zhmv6zvj2-afk`
