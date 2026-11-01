# Essay Writer

Helps you research a university assignment and turn it into a Word essay.

You work in Essay Bot inside Grok Bot. The chat looks up papers, writes a draft from those sources, and checks that the essay answers the assignment. When the work is ready, you get a Word file (`.docx`).

## What you need

- A Grok Bot account
- A Consensus account and API key (to find academic papers)
- An email address for Unpaywall (to look up free copies of papers when available)

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

## How a typical essay goes

1. You start a new essay for your module and share the assignment.
2. Research finds papers; downloads a PDF when it can, or gives you the title and a link.
3. A draft is written from those sources.
4. You review each stage in the chat and press Confirm before anything is saved.
5. The finished essay is a Word file (`.docx`).

Drafts are model-assisted. The student owns what they submit and must follow their school's rules.

## More detail

- Output is Word only (`.docx`).
- Referencing follows Harvard: [docs/referencing-harvard.md](docs/referencing-harvard.md).
- Install steps for the person running setup: [FIRST-RUN.txt](FIRST-RUN.txt).
- Full stage guide: [docs/workflow.md](docs/workflow.md).
- Distribution is source install for Essay Bot in Grok Bot. There is no PyPI release.

## For developers

Python 3.10 or newer:

```bash
uv sync --extra dev
uv run python -m essay_writer --health
uv run pytest
```

The chat setup can run an unsigned remote script to install the Cursor CLI. For a manual install, clone this repo and run `uv sync --extra dev`; the chat-driven install is optional.

## License

[MIT](LICENSE) © 2026 `4zhmv6zvj2-afk`
