# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.2.x | yes |

## Reporting

Report privately through GitHub's private vulnerability reporting:

https://github.com/4zhmv6zvj2-afk/grokbot-essay-writer/security/advisories/new

That reaches the maintainers privately and keeps the report out of the public
timeline. We aim to acknowledge a report within 10 business days (14 calendar
days), agree a disclosure timeline with the reporter, and publish an advisory
alongside the fix.

If that channel is unavailable, open a minimal public issue saying only that
you have a security report and how to reach you. Do not put credentials,
tokens, or exploit details in a public issue.

## Scope

- This project is a local MCP server. It does not bundle, proxy, or host any
  provider key.
- Keys, when used, are read from the environment and are never written to a
  result, an error message, or a log line.
- Drafts and generated documents are ignored by git (`*.docx`, `output/`,
  `Essay-writer/*/`, `uploads/*/`); never commit them.
- Assigned file paths are validated before the tool reads or writes, and the
  confirm gate must pass before any file is changed.

_This policy covers the software as distributed from this repository._
