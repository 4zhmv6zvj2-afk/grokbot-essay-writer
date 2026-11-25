# Operator log

## Opt-in record

Operators and shells use these files. End users do not. Essay Bot, Cursor, and Grok Build read them when they diagnose a run. Students do not use them. They are not shown in chat and they are not written into Word.

Student installs leave it off. A shell turns it on by setting `ESSAY_WRITER_DEBUG=1` on the `essay-writer` process (`true`, `on`, and `yes` do the same). `ESSAY_WRITER_DEBUG=0` keeps it off (`false`, `off`, and `no` do the same) and wins over the operator default. When that variable is unset, `"debug": true` in the setup record the server already reads also turns it on. Setup `where` `grokbot-cloud-computer` does not turn it on by itself. An operator end-to-end test flag in the setup record turns it on when that record marks operator e2e on. A student save (`where` `user-local`, or no setup record) stays off. `essay.setup` does not ask for this and does not repeat it. A later setup leaves an existing `debug` flag in place.

One module writes one record per call. The record is one JSON object in `ml-events.jsonl`. `debug.log` is the rendered line of that same record. `essay-writer --debug-tail` prints those rendered lines. It does not turn debug on, does not create a file, and does not write an incident. `--debug-tail SEQUENCE` reads that sequence when `SEQUENCE` is an essay id or a sequence id. Any other argument reads the app-folder log. A missing live `ml-events.jsonl` prints nothing and exits 0, including when `ml-events.jsonl.1` is present. The rotated file is read only while the live file exists.

The app folder is `ESSAY_WRITER_ROOT` when it is set, otherwise the app folder stored at setup, otherwise the folder that contains this package. When `ESSAY_WRITER_ROOT` is set, the setup record is not consulted, so use `ESSAY_WRITER_DEBUG`. A sequence id writes under that sequence's work folder. The log is not given its own separate path.

A record has the UTC time and the tool. It may also have the phase (`draft`, `confirm`, or `read`), the sequence id, the stage, and the other set fields. `query`, `title`, `reason`, and `stderr` are stored only on this opt-in record, and only when the call supplied them. They are clipped and scrubbed before they are stored. The record has no path field. A checksum may be stored.

The first line of a new sequence file is a land record (`essay-writer.land`, the land sha, and the sequence id). That line is its own record.

At 256 KB or 200 lines, whichever comes first, on either live file, both `debug.log` and `ml-events.jsonl` are renamed to `debug.log.1` and `ml-events.jsonl.1` before the next append. These files are not mode 0600. If a rename fails, that append is skipped.

When the operator asks to delete the logs or clear the debug log, `essay.debug.wipe` clears the live files, the rotated files, and the incident record together. There is no settings toggle and no chat button. `essay.debug.wipe` writes nothing of its own.

`essay-writer --debug-export` packs the opt-in files that are already on disk, including the rotated names, into `debug.zip`. The export redacts home paths, volume paths, and secrets. Do not turn debug on to produce that zip.

## Incident record

This file is always on. A student install writes it when the debug log is off. The file is `incident.jsonl` in the app folder, mode 0600. The rotated copy is `incident.jsonl.1`, also mode 0600. At 256 KB or 200 lines, whichever comes first, the live file is renamed to `incident.jsonl.1` and a new file starts. One process lock covers that rename plus the append, and the same lock covers the wipe, so two callers in that process cannot rotate the same file twice or drop a line. Two processes can still pass each other.

The app folder is `ESSAY_WRITER_ROOT` when it is set, otherwise the folder stored at setup. When neither is set, the folder that contains this package is used. That package-directory fallback is a dev-only degradation. A student install has a setup app folder or `ESSAY_WRITER_ROOT`. In this checkout, `incident.jsonl`, `incident.jsonl.1`, and `support.zip` are gitignored.

Each line is one JSON object. It has the UTC time, the build commit, a prompt hash, the sequence id, the tool, the stage, a stable code, a disposition (`retry`, `fallback`, or `refuse`), and a severity (`error`, `warn`, or `info`). An exception line adds the exception class and the code `unhandled`. The message is empty unless it is exactly `Windows is not supported.` The line does not contain essay text, a prompt, chat, a file body, a path, or a secret value. It does not store `query`, `title`, `reason`, or `stderr`. Those four fields stay on the opt-in record. Incident lines are not copied into `debug.log` or `ml-events.jsonl`.

A `guidance-only` line is severity `error` and disposition `refuse`. The look was only the checklist. That row is expected friction. It is not a product fault and it is not a harness fault.

`essay-writer --support-bundle` writes `support.zip` in the app folder. The zip contains the incident lines, `health.json` (version, build commit, prompt hash, and door names), `files.json` (sequence ids and SHA-256 values of state files, not the file contents), and `manifest.json` (counts, including soft incidents by code). `debug.log`, `debug.log.1`, `ml-events.jsonl`, and `ml-events.jsonl.1` are not members. A logging failure does not stop the student.

## Environment overrides (operators and tests)

Set these on the `essay-writer` process, not in chat. The first three change behaviour. The last two are internal signals: do not set them by hand.

- `ESSAY_WRITER_MAC_HOME`. The friend's Mac home this computer can see, when a non-Darwin shell already has it mounted. Unset, empty, or `open` means the Mac is not mounted, so the handoff stays chat-only. A named folder that does not exist is treated the same way.
- `ESSAY_WRITER_RESOLVERS`. Paper look-up mode is `live` (default), `off` (skip look-ups), or `fixture` (the test set).
- `ESSAY_WRITER_UPDATE_LOCK`. The path of the process-wide `--update` lock. Unset uses `essay-writer-update.lock` in the system temp folder.
- `ESSAY_WRITER_INTERPRETER`. Internal handoff signal. The bootstrap sets it to the interpreter it re-execs into, and a consumer reads it to skip a second bootstrap.
- `ESSAY_WRITER_BUILD`. Internal build label. It overrides the `BUILD-COMMIT` marker for one run. `essay.health` reports it as `build_commit`.
