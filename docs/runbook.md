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
