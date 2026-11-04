# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.2.x | yes |

## Reporting

Use GitHub's private vulnerability reporting: open the repository's
**Security** tab and choose **Report a vulnerability**. That reaches the
maintainers privately and keeps the report out of the public timeline.

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
