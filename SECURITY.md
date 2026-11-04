# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.3.x | yes |

## Reporting

Report privately through GitHub's private vulnerability reporting:

https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/security/advisories/new

That reaches the maintainer privately and keeps the report out of the public
timeline. We aim to acknowledge a report within 10 business days (14 calendar
days), agree a disclosure timeline with the reporter, and publish an advisory
alongside the fix.

If that channel is unavailable, open a minimal public issue saying only that you
have a security report and how to reach you. Do not put credentials, tokens, or
exploit details in a public issue.

## Scope

- This project is a local MCP server. It does not bundle, proxy, or host any
  provider key.
- Keys, when used, are read from the environment and are never written to a
  result, an error message, or a log line.
- Drafts and generated documents are ignored by git (`*.docx`, `output/`,
  `Essay-writer/*/`, `uploads/*/`); never commit them.
- Assigned file paths are validated before the tool reads or writes, and the
  Confirm gate must pass before any file is changed.
- Runtime dependencies are pinned: `pyproject.toml` carries exact versions and
  `requirements-runtime.txt` is hash-pinned for a verifiable manual install.
- Setup does not install the Cursor CLI silently. It downloads the installer to
  a file, records its SHA-256, and runs it only after explicit consent
  (`--install-cursor` or `ESSAY_WRITER_ALLOW_CURSOR_INSTALL=1`). The installer is
  an unsigned remote script from the vendor; the manual command is in
  [FIRST-RUN.txt](FIRST-RUN.txt).

## Release verification

Releases from 0.3.0 onward are reproducible from the tag; the release workflow
builds twice and requires identical SHA-256 before signing. See the "Verify a
release" section of [README.md](README.md).

_This policy covers the software as distributed from this repository._
