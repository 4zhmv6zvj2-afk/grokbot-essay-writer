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

## A sequence saved by an earlier 0.9 release

`state.json` and `tracking/stage.json` have the same keys from 0.9.14 through 0.9.19. A file from one of those releases loads, the tracking note is readable, and the next stage confirm advances it. The synthetic copies live in `tests/fixtures/state/`. A stage 6 snapshot with a saved stage 5 look can also write the first-draft Word file.

A load does not rewrite the file. A missing known field is filled in memory and recorded as `state-field-filled` or `pointer-field-filled`. An unknown field is kept, including an unknown saved entry or file entry, and recorded as `state-unknown-field` or `pointer-unknown-field`. The next real save writes that field again.

A `current` value that is not a stage becomes stage 1 in memory and is recorded as `pointer-unknown-current`. A `saved` or `files` value that is not a list or an object is left out of the loaded pointer and recorded as `pointer-field-dropped`. The bytes on disk stay until the next save, and that save writes the value the stage machine can use.

A `state.json` that is not a JSON object is the existing damage refusal. The load records `state-damaged` and does not replace the file. A stage pointer that is not a JSON object stays the existing in-memory fallback. It records `pointer-damaged` and does not replace the file. Neither case adds a new student stop.
