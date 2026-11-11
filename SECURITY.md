# Security policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.7.x | yes |
| < 0.7 | no |

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

What the gate does guarantee: a save, stage advance, or deliverable write needs
a draft of the same arguments already on disk. A stage draft call writes that
draft ledger, the tracking note, and the stage pointer, and the confirm
re-derives the argument digest and the on-disk file fingerprint.

What the gate does not prevent: draft calls are not inert (they change those
files before any confirm), and stage 5 stores its first draft and advances to
stage 6 on its draft call by design, with no card. The card a side-effect door
showed is bound to the draft by `cardDigest`, and `essay.setup` binds the
Consensus key and Unpaywall email by SHA-256 instead of only their presence.

Trusted: the host model and its chat transport. They are trusted to relay the
person's yes and no truthfully, to keep operator setup notes out of student
chat, and not to call a tool the person did not approve.

Not trusted: remote addresses and their redirects. URLs can come from model
output or from fetched paper metadata, so they are treated as
attacker-controlled. Document bodies are untrusted too: uploaded assignments
and briefs, PDFs, and fetched pages are text from outside this computer, and
they can carry instructions aimed at the host model. The prompts fence that
text as quoted evidence rather than instructions, but the fence is a mitigation,
not a guarantee, and harm from following document text happens before a Confirm.
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
- Draft ledgers under `Essay-writer/<module>/.../.drafts/` keep the draft text
  until the workflow folder is deleted; nothing prunes them automatically.
- Assigned file paths are validated before the tool reads or writes. A save,
  stage advance, or deliverable write requires a draft of the same arguments
  already on disk: the confirm re-derives the argument digest and the on-disk
  file fingerprint. This is not "nothing is written before Confirm": a draft
  call writes the draft ledger under `.drafts/`, the tracking note, and the
  stage pointer, and stage 5 stores its first draft and advances to stage 6 on
  its draft call by design, with no card. `essay.dig` and the research doors
  store the card they showed and bind it with `cardDigest`; the confirm call
  must send that digest, and a missing or different value is refused.
  `essay.setup` includes a SHA-256 of the stripped Consensus key and Unpaywall
  email in the draft, so the confirm call must repeat the same values; neither
  value is echoed in a reply or written into the draft record.
- Every fetch driven by model- or paper-supplied content goes through
  `safe_url` (paper downloads, research look-ups, and dig look-ups): only http
  and https, a host that resolves, every resolved address public (no loopback,
  private, link-local, reserved, multicast, unspecified, or IPv6 ULA), no
  userinfo, the default port, redirects re-validated with the same rules and
  capped at three same-scheme hops. Bodies are read whole up to a per-call cap
  (25 MiB for a paper, 2 MiB for a research API, 1 MiB for a look-up); an
  over-cap body is refused, not truncated, and maps to the existing
  empty-download or `None` result instead of an exception to the MCP tool. The
  address is resolved once for validation and again when the connection is
  made, so a DNS answer that changes between those two lookups remains a
  residual risk. Two fetches are outside that opener, both in the setup CLI and
  not reachable from the MCP tools: the Cursor installer is downloaded with
  `curl` from the fixed vendor URL `https://cursor.com/install` and is
  hash-gated before execution, and `pip`/`uv` fetch the pinned packages at
  install time.
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
  network failure stops the install; nothing after it is installed. The
  vendored bootstrap core is byte-identical to the upstream release, with no
  local patch: `VENDOR.json` records the source, release, and file SHA-256. See
  [ARCHITECTURE.md](ARCHITECTURE.md).
- `essay-writer --install-upload` is a CLI update path for an already-installed
  copy; the MCP server never spawns it. The zip must carry
  `requirements-runtime.txt`, and the install is always hash-pinned for
  dependencies with no unpinned fallback. A zip checksum is optional and is
  checked when one is available: `--upload-sha256`, a sibling
  `<zip>.sha256`, or a matching `SHA256SUMS` entry; a present but wrong checksum
  refuses. With no checksum the zip is trusted operator input, the install
  proceeds, and the result reports `upload_verified: false`. The zip's own build
  backend still executes, so pass only a zip you produced or trust.
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

Releases from 0.3.0 onward use a reproducible build on a pinned `ubuntu-24.04`
runner with a pinned cosign release. The release workflow builds the artifacts
twice in one run with `SOURCE_DATE_EPOCH` from the tagged commit, requires
identical SHA-256 hashes before uploading, signing, or attesting them, then
verifies each Sigstore signature and the GitHub attestation in the same run. A
separate reproduce workflow rebuilds a published release from its tag and fails
on any hash mismatch. The "Verify a release" section of [README.md](README.md)
gives the independent rebuild and the signature and provenance checks.

_This policy covers the software as distributed from this repository._
