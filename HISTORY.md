# Project history

This repository is the public source for Essay Writer, the backend of the
Essay Bot agent product. It was not developed in public from the first commit.
This file records that plainly.

## What the git history means

| Ref | Meaning |
| --- | --- |
| `v0.2.1` (2026-11-04) | An import commit. The whole working tree was published in one commit; it is a snapshot, not a development history. |
| Commits after `v0.2.1` | Release-engineering and documentation changes made in public. The `src/` tree was unchanged in this window. |
| `v0.3.0` and later | Normal releases: tagged commits in this repository, built from this repository, with reproducible artifacts. |
| `v0.6.1` (2026-11-11) | A tag that was re-cut as `v0.6.2`. It exists on origin; no v0.6.1 release is published. |

The `v0.6.1` tag exists on origin, and its Release workflow ran, but no v0.6.1
release is published. The release was re-cut as `v0.6.2` from a follow-up
commit with a release-workflow fix and a changelog entry renumbered from 0.6.1
to 0.6.2; the `v0.6.1` tag was not moved.

Versions `0.1.0` through `0.2.0` are described in [CHANGELOG.md](CHANGELOG.md)
but were tagged in a private working repository. They are not tags here and
their commit history is not available. We do not force-push or rewrite the
published `v0.2.1` tag to disguise this.

## Why it was published as a snapshot

The product is distributed as source: a student or operator can read what the
agent can do on their computer, and anyone can verify a release. That
distribution need arrived after the workflow already existed, so the first
public commit is an export of a working tree rather than a replay of its
development.

## What changed with 0.3.0

The 0.3.0 release is the first one whose history is fully in this repository
and whose artifacts are reproducible from the tag. It also fixes the
distribution problems the snapshot exposed: the source distribution was not
testable, the release workflow did not run the tests, and the setup path
installed the Cursor CLI from an unsigned remote script.
