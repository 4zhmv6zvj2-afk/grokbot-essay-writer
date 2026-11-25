# Runbook

## A crash during a save

A saved file is replaced as a whole. The writer puts the new bytes in a temp file in the same directory, flushes that file, sets the mode, then renames it over the previous file. A crash before the rename leaves the previous file. The published file keeps the previous mode. A new file is mode 0644, not the owner-only temp. Secret files are created at 0600 and do not use this path. A second save of the same bytes, with no earlier crash, leaves one file. A killed save can leave a hidden temp beside that file. The temp is not loaded, and the next save does not delete it, because another writer may still be using a temp of its own.

Sequence state is the last file in its pair. `state.json` is written, then `last-saved.json`. A stage note is written, then `tracking/stage.json`. The next load finishes a stage pair whose pointer did not land. A dig card writes the markdown, then `dig-card.json`. The card the product loads is the JSON. A crash after the markdown and before the JSON leaves a new note and the previous card.

These writes stay outside that replace. Each one is a stream, a download, or a tree that is renamed into place:

- `debug.log` and `ml-events.jsonl` headers are append logs. `incident.jsonl` is a separate always-on metadata log for a fallback. It is not part of that opt-in stream.
- An update download is the installer body, not sequence state.
- The first-run installer extracts an archive into a new tree.
- The vendored pin file is not sequence state.
- A pack backup writes bytes inside a staging directory, then renames that directory.
- A photo note is published only after the photo file has moved.

Secret files are still written in place and flushed. They are not sequence state.

## A look-up that does not answer

A read has a connect timeout and a read timeout. The default is 20 seconds for both. A GET or HEAD retries a timeout, a DNS failure, a dropped connection, HTTP 429, or HTTP 500, 502, 503, or 504. It tries three times. The wait doubles from a twentieth of a second and adds a small jitter from the clock. A POST, and any other write, tries once. A retry and the fallback after the last try are recorded in incident.jsonl. The student is not stopped. The message names the next step, such as trying the look-up again or using a direct link or a smaller file.

A response over the byte cap is not returned in part. A redirect stops after three hops. A page cursor that repeats stops the gather. The page cap stops a cursor that keeps changing. None of these write a partial sequence file. The bytes already on disk stay until a later successful save.

## A sequence saved by an earlier 0.9 release

`state.json` and `tracking/stage.json` have the same keys from 0.9.14 through 0.9.19. A file from one of those releases loads, the tracking note is readable, and the next stage confirm advances it. The synthetic copies live in `tests/fixtures/state/`. A stage 6 snapshot with a saved stage 5 look can also write the first-draft Word file.

A load does not rewrite the file. A missing known field is filled in memory and recorded as `state-field-filled` or `pointer-field-filled`. An unknown field is kept, including an unknown saved entry or file entry, and recorded as `state-unknown-field` or `pointer-unknown-field`. The next real save writes that field again.

A `current` value that is not a stage becomes stage 1 in memory and is recorded as `pointer-unknown-current`. A `saved` or `files` value that is not a list or an object is left out of the loaded pointer and recorded as `pointer-field-dropped`. The bytes on disk stay until the next save, and that save writes the value the stage machine can use.

A `state.json` that is not a JSON object is the existing damage refusal. The load records `state-damaged` and does not replace the file. A stage pointer that is not a JSON object stays the existing in-memory fallback. It records `pointer-damaged` and does not replace the file. Neither case adds a new student stop.

## Verify a release in five minutes

From the repository root, on the commit you are about to call the release:

```bash
uv run python tools/check_release_version.py --tag v0.9.22
uv run essay-writer --health
```

The version check exits 0 when `pyproject.toml`, `uv.lock`, and the newest `CHANGELOG.md` release heading agree with that tag. `## Unreleased` does not count as a release heading. `--health` prints JSON. Read `version` and `build_commit`. They are the version and the commit you have checked out.

The published bytes are checked from the GitHub release, not from this checkout. Download the wheel, the sdist, `SHA256SUMS`, each `*.sigstore.json`, and `provenance.intoto.jsonl` into one folder, then run the checksum, `cosign verify-blob`, and `gh attestation verify` commands in the README section "Verify a release". Do not publish a release whose checksum or attestation fails.

## Release acceptance

After the five-minute check and the README verify steps, prove the published
assets outside CI. From the repository root, against a published tag:

```bash
python tools/release_acceptance.py --tag v0.9.22
```

Omit `--tag` to use the version in `pyproject.toml` (`project_tag()` in `tools/release_acceptance.py`). On this tree that tag is `v0.9.22`.

The harness is stdlib-only on the outer path. It downloads the wheel, the
sdist, and `SHA256SUMS` for that tag, checks each named file against
`SHA256SUMS`, installs the wheel into a clean venv, installs the sdist into a
second clean venv, and in each venv runs `essay-writer --health` plus a probe.
The probe plants the shipped `0.9.19` sequence fixture, writes the first-draft
Word file, opens it with python-docx (title and paragraphs), advances stage 6,
kills a save before replace and confirms the previous state still loads, exports
a support bundle (manifest and incident members; no debug logs, no essay text,
no paths), wipes `incident.jsonl` and `incident.jsonl.1`, then loads the same
`0.9.19` fixture again and advances under the installed tag.

A pass prints `PASS:` lines for each check, then `ALL PASS`, and exits 0. Keep
the work tree with `--workdir /tmp/accept-0.9.22` (or `--keep`) when you need
the downloaded hashes and probe folders as evidence. To accept a local build
before the tag is published, put the wheel, the sdist, and `SHA256SUMS` in one
folder and pass `--assets-dir` that folder with `--tag` matching the version
in those filenames. A product bug found here stops the release acceptance; do
not patch the product in the same change as this harness.

## A student report

Ask for these, and nothing that contains the essay:

- `support.zip`, from `essay-writer --support-bundle`
- the sequence id, such as `MOD1004AA-1`
- the step they were on
- the time they saw the problem
- a screenshot of the refusal

Open the zip. What `support.zip` contains, and what `essay-writer --debug-tail` prints, is in [Incident record](operator-log.md#incident-record) and [Opt-in record](operator-log.md#opt-in-record). `debug.log` and `ml-events.jsonl` are not in the zip. When the student already had debug on, `essay-writer --debug-export` is a separate zip and it is redacted. Do not turn debug on to produce that zip.

A line is enough to name the tool, the stage, the code, and the build. Match the code to `docs/refusals.md`. Match `build_commit` in `--health` to `health.json`. Match `state_sha256` to the sequence file only when the student still has that file. Do not ask the student to paste the essay.

## A bad release

A published release is immutable. Do not replace its wheel, sdist, `SHA256SUMS`, signature, or provenance. Do not move or delete the tag.

Ship a new patch tag. Follow "Releases" in `CONTRIBUTING.md`. Create the draft, dispatch the Release workflow, and publish the draft only after that workflow succeeds.

On the bad release, edit the release notes so the first line says it is superseded by the new tag. Notes are not assets. Leave the old assets where they are.

The maintainer is the person who cuts the tag. There is no second on-call. The public notice is the GitHub release note plus a GitHub issue if a student already has the bad bytes.

## Rollback

A rollback is a new patch whose tree restores the last good behavior. It is not a retag and it is not an asset swap. Students who installed the bad tag keep those bytes until they check out the new tag.

`v0.9.19` stays where it was published. Later tags stay where they were published.

## A broken gather

The student is not stopped. The incident line uses a stable code such as `read-bad-json` or `page-cursor-repeat`, with severity `warn` or `info`. The spoken reply already names the next step. Ask for `support.zip` and the sequence id. Do not delete the sequence files to clear the gather.

## A corrupted state file

`state-damaged` means `state.json` is not a JSON object. `pointer-damaged` means the stage pointer is not a JSON object. The load records the code and does not replace the file. Ask for `support.zip`. Use `files.json` for the sequence id and the state hash. Do not tell the student to delete `state.json`.

`essay.debug.wipe` removes `incident.jsonl`, `incident.jsonl.1`, `debug.log`, `debug.log.1`, `ml-events.jsonl`, and `ml-events.jsonl.1`. It does not remove sequence state. The file list is in [Operator log](operator-log.md).
