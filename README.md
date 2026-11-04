# Essay Writer

[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/4zhmv6zvj2-afk/grokbot-essay-writer/badge)](https://securityscorecards.dev/viewer/?uri=github.com/4zhmv6zvj2-afk/grokbot-essay-writer)

Helps you research a university assignment and turn it into a Word essay.

You work in Essay Bot inside Grok Bot. Drafts are model-assisted: the chat looks up papers, writes a draft from those sources, and checks that the essay answers the assignment. The student owns what they submit and must follow their school's rules. When the work is ready, you get a Word file (`.docx`).

**Using Essay Bot, or setting it up?** If Essay Bot is already on your Grok Bot, there is nothing to install — start a new essay. If you are setting up this Grok Bot on a computer, the setup steps are in "Get started" below and in [FIRST-RUN.txt](FIRST-RUN.txt).

## What this will do to your computer

On the Grok Bot computer, setup will:

- Install Essay Writer and its dependencies into a project folder.
- Download a private Python 3.15.2 into that folder, only if no suitable Python is already there. It never changes the Python already installed on the computer.
- Save Word files to `Documents/Essay Bot`, or to a folder you name. If you choose neither, the essay stays in the chat.
- Install the Cursor CLI with an unsigned remote script it downloads, and ask you to sign in there, when that is not already done.

## What you need

- A Grok Bot account
- A Consensus account and API key (to find academic papers)
- An email address for Unpaywall (to look up free copies of papers when available)

## How a typical essay goes

1. You start a new essay for your module and share the assignment.
2. Research finds papers; downloads a PDF when it can, or gives you the title and a link.
3. A draft is written from those sources.
4. You review each stage in the chat and press Confirm before anything is saved.
5. The finished essay is a Word file (`.docx`).

## Get started

Paste this into your Grok Bot chat:

```
Download https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer.
Read the README and FIRST-RUN.txt.
Add Essay Bot to this Grok Bot from docs/templates/essay-bot.share.json.
Set up grokbot-essay-writer.
```

Essay Bot will ask you, in the chat, for:

1. Where Word files should be saved on your Mac (or skip if you prefer chat only)
2. Sign-in on the Grok Bot computer when setup asks for it
3. Your Consensus key and plan, and an email for free paper lookup

Paste keys only when the chat asks for a secret — not into ordinary messages.

## More detail

- Output is Word only (`.docx`).
- Referencing follows Harvard: [docs/referencing-harvard.md](docs/referencing-harvard.md).
- Operators attaching Essay Bot: see [FIRST-RUN.txt](FIRST-RUN.txt).
- Full stage guide: [docs/workflow.md](docs/workflow.md).

## For developers

Python 3.14 or newer:

```bash
uv sync --extra dev
uv run pytest
```

Setup, the `first_run.py` bootstrap, and bug reports: [CONTRIBUTING.md](CONTRIBUTING.md). Stage flow and module layout: [ARCHITECTURE.md](ARCHITECTURE.md).

## Status and help

This is a stable source release. Maintenance is limited to reported bugs. To report one, open an issue with the details listed in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 `4zhmv6zvj2-afk`
