# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.5.x | yes |

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

## Threat model

This is a local MCP server. The host model (Cursor or Grok Build) drives it and
relays the person's words. The server does not prove that a human clicked
Confirm. The Confirm gate binds the arguments and file fingerprints that the
host sent; it cannot bind a human identity. A host model that lies, or that a
page or document has steered, can present a Confirm, and the gate will not
detect that. The server also cannot tell an attended session from an unattended
one.

Trusted: the host model and its chat transport. They are trusted to relay the
person's yes and no truthfully, to keep operator setup notes out of student
chat, and not to call a tool the person did not approve.

Not trusted: remote addresses and their redirects. URLs can come from model
output or from fetched paper metadata, so they are treated as attacker-controlled.
The debug log, the setup secrets file, and exported debug archives contain data
from this computer, so they are treated as sensitive.

Recommendations, in order of value:

- Run the host in an attended session: the person is at the desk and reads the
  cards before approving a save.
- Use the reviewer server (`essay-reviewer`) for the independent review. It is
  a separate seat and does not write the tracking note or advance the stage.
- Make the checkout, the workflow folder, and anything else that only needs to
  be read read-only for the account that runs the server where the operating
  system allows it.

## Scope

- This project is a local MCP server. It does not bundle, proxy, or host any
  provider key.
- Keys, when used, are read from the environment and are never written to a
  result, an error message, or a log line.
- Drafts and generated documents are ignored by git (`*.docx`, `output/`,
  `Essay-writer/*/`, `uploads/*/`); never commit them.
- Assigned file paths are validated before the tool reads or writes, and the
  Confirm gate must pass before any file is changed.
- Every direct remote fetch goes through `safe_url`: only http and https, a
  host that resolves, every resolved address public (no loopback, private,
  link-local, reserved, multicast, unspecified, or IPv6 ULA), no userinfo, the
  default port, redirects re-validated with the same rules and capped at three
  same-scheme hops. Bodies are read whole up to a per-call cap (25 MiB for a
  paper, 2 MiB for a research API, 1 MiB for a look-up); an over-cap body is
  refused, not truncated, and maps to the existing empty-download or `None`
  result instead of an exception to the MCP tool. The address is resolved once
  for validation and again when the connection is made, so a DNS answer that
  changes between those two lookups remains a residual risk.
- `essay.debug.export` redacts each zip member before it is written: absolute
  `/Users/<name>/...`, `/Volumes/<name>/...`, and `/home/<name>/...` paths,
  email addresses, `Bearer` values, `x-api-key` values, and common token
  shapes (`sk-...`, `ghp_...`, `github_pat_...`, `AKIA...`, `xox...`). Key
  names such as `CONSENSUS_API_KEY` stay so a diagnosis still reads; the value
  goes. The zip is still a debug archive: review it before sharing it further.
- Secret files are created with mode 0600 before any content is written, never
  written at 0644 and narrowed afterwards. That covers `setup.secrets.json` for
  the optional Consensus key, Unpaywall email, and remembered Mac folder.
- The `python first_run.py` entry point installs the hash-pinned runtime
  requirements (`requirements-runtime.txt` with `--require-hashes`) before the
  project install, which then runs with `--no-deps`. A hash mismatch or a
  network failure stops the install; nothing after it is installed. See
  [ARCHITECTURE.md](ARCHITECTURE.md) for the vendored bootstrap and its one
  recorded local patch.
- Setup does not install the Cursor CLI silently. Consent (`--install-cursor`
  or `ESSAY_WRITER_ALLOW_CURSOR_INSTALL=1`) authorises the **download** only:
  setup downloads the installer to a file and reports its SHA-256, byte count,
  and path, then stops with `cursor-install-needs-hash`. Execution additionally
  requires the expected SHA-256 (`--cursor-sha256` or
  `ESSAY_WRITER_CURSOR_INSTALL_SHA256`). A mismatch stops with
  `cursor-install-hash-mismatch` and runs nothing; a match runs the downloaded
  file with a fixed argv and no shell. The installer is an unsigned remote
  script from the vendor, and the hash confirms which bytes were downloaded,
  not that the vendor is trustworthy. For a trust-sensitive install, skip the
  automated path and run the vendor's manual install command yourself; the
  command is in [FIRST-RUN.txt](FIRST-RUN.txt).
- Runtime dependencies are pinned: `pyproject.toml` carries exact versions and
  `requirements-runtime.txt` is hash-pinned for a verifiable manual install.

## Release verification

Releases from 0.3.0 onward are reproducible from the tag; the release workflow
builds twice and requires identical SHA-256 before signing. See the "Verify a
release" section of [README.md](README.md).

_This policy covers the software as distributed from this repository._
