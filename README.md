# Essay Writer

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/4zhmv6zvj2-afk/grokbot-essay-writer/badge)](https://securityscorecards.dev/viewer/?uri=github.com/4zhmv6zvj2-afk/grokbot-essay-writer)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/16338/badge)](https://www.bestpractices.dev/projects/16338)

A confirm-gated MCP server that helps a student research a university assignment
and turn it into a Word essay. It is the backend of the Essay Bot agent product;
this repository is its source.

## What this is

- **An MCP server for one workflow.** 24 tools take a single essay from brief to
  `.docx`: research, plan, annotated bibliography, critical review, first draft,
  feedback, edit, references, and final Word.
- **Confirm-gated and local.** A write takes two calls: a draft card, then the
  same arguments confirmed. Nothing is saved until the Confirm, and the Confirm
  is bound to the exact arguments by a SHA-256 digest and the on-disk file
  fingerprint.
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

- Not a writing service or an essay mill.
- Not a hosted service: no server, no account, no bundled keys. It is a local
  process the agent talks to.
- Not a general-purpose Word or referencing library.
- Not on PyPI. Releases are source plus verifiable build artifacts on GitHub.

## Academic integrity

The tool helps a student research, plan, draft, and revise. It does not decide
what is acceptable at their institution, and it does not submit anything.

- The student owns what they submit. Using a drafting aid without disclosure, or
  where the institution forbids it, is the student's decision and
  responsibility. The tool does not police it, and the maintainer does not
  endorse it.
- The workflow is built to keep the student in the loop: each stage is reviewed
  and confirmed in chat, and the final Word file is theirs.
- If your course forbids generative assistance, do not use this.

## Using Essay Bot (students)

If Essay Bot is already on your Grok Bot, there is nothing to install — start a
new essay.

1. Start a new essay for your module and share the assignment.
2. Research finds papers; it downloads a PDF when it can, or gives you the title
   and a link.
3. A draft is written from those sources.
4. You review each stage in the chat and press Confirm before anything is saved.
5. The finished essay is a Word file (`.docx`).

Output is Word only (`.docx`); referencing follows Harvard
([docs/referencing-harvard.md](docs/referencing-harvard.md)). The full stage
guide is [docs/workflow.md](docs/workflow.md).

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
3. Your Consensus key and plan, and an email for free paper lookup.

Paste keys only when the chat asks for a secret — not into ordinary messages.

## What setup does to the computer

On the Grok Bot computer, setup will:

- Install Essay Writer and its dependencies into a project folder.
- Download a private Python 3.15.2 into that folder, only after you agree and only
  if no suitable Python is already there. It never changes the Python already
  installed on the computer.
- Save Word files to `Documents/Essay Bot`, or to a folder you name. If you
  choose neither, the essay stays in the chat.
- Install the Cursor CLI only if you say yes and it is missing. Setup downloads
  the installer to a file, records the file's SHA-256 in its report, and then
  runs that file. It never pipes a remote script into a shell. Without your yes
  it downloads nothing and reports `cursor-install-needs-consent`. To install it
  yourself:

  ```bash
  curl -fsS https://cursor.com/install -o cursor-agent-install.sh
  shasum -a 256 cursor-agent-install.sh   # Linux: sha256sum cursor-agent-install.sh
  bash cursor-agent-install.sh
  ```

## For developers

Python 3.12 or newer:

```bash
uv sync --extra dev
uv run pytest                      # 1006 passed, 8 skipped
uv run ruff check src tests tools
uv run mypy src
uv run python tools/generate_docs.py --check
uv run python tools/update_prompt_snapshot.py --check
```

- `src/essay_writer/server.py` — MCP entry and tool registration.
- `src/essay_writer/doors.py` — the tool catalogue (one "door" per tool).
- `src/essay_writer/stage_track.py` — the stage runner, cards, and confirm flow.
- `src/essay_writer/stage_state.py` — the state layer (pointer, commit journal,
  stage lock, tracking note, held/refused replies) re-exported by stage_track.
- `src/essay_writer/prompts/` — the stage, genre, craft, and review text that is
  the actual product.
- `tests/` — behaviour and acceptance tests; `tests/fixtures/` is synthetic, no
  student work.

Start with [ARCHITECTURE.md](ARCHITECTURE.md), then
[docs/GLOSSARY.md](docs/GLOSSARY.md) for the private vocabulary (doors, seats,
spine, shelf, dig, canon, mid-office) and [docs/testing.md](docs/testing.md) for
how the suite is organised and how the prompt snapshot is regenerated.

`uv.lock` is the developer lockfile. `requirements-ci.txt` is the hash-pinned CI
environment; `requirements-build.txt` pins the build tooling; and
`requirements-runtime.txt` is the hash-pinned runtime set for a verifiable
manual install. There is no release on PyPI.

## Verify a release

GitHub releases include the wheel, the sdist, `SHA256SUMS`, a Sigstore signature
bundle (`*.sigstore.json`) for each file, and `provenance.intoto.jsonl`.
Download the files into one folder, then check them:

```bash
# The checksums and filenames come from the release:
sha256sum -c SHA256SUMS

# Check the wheel was built by this repository's release workflow:
gh attestation verify essay_writer-0.3.0-py3-none-any.whl \
  --repo 4zhmv6zvj2-afk/grokbot-essay-writer
```

Releases from 0.3.0 onward are byte-reproducible: CI rebuilds twice from the
tagged commit with `SOURCE_DATE_EPOCH` set to the commit time and the hash-pinned
toolchain, and requires identical SHA256 sets before anything is uploaded or
signed. To verify, check out the tag and rebuild with the same toolchain:

```bash
git checkout v0.3.0
python -m pip install --require-hashes -r requirements-build.txt
SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" \
    python tools/reproducible_build.py --outdir dist-rebuild
cd dist-rebuild && sha256sum *.whl *.tar.gz
```

The hashes must equal the release's `SHA256SUMS`. `tools/reproducible_build.py`
normalizes the sdist metadata to `SOURCE_DATE_EPOCH` and fails unless both builds
are byte-identical; a plain `python -m build` does not reproduce the sdist.

The sdist is complete: it carries the tests, fixtures, and prompt snapshot, so
`pytest` works from the extracted source distribution. The 0.2.1 artifacts
predate this and are not reproducible; see [HISTORY.md](HISTORY.md).

## Project status

Stable source release, maintained for reported bugs. The public history starts
with a 0.2.1 import snapshot; 0.3.0 is the first normal release, built and
tagged from commits in this repository. [HISTORY.md](HISTORY.md) explains that
plainly. Security reports: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 `4zhmv6zvj2-afk`
