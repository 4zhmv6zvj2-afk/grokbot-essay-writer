# Operator log

Operators and shells use these files. End users do not.

## Debug log (operators and shells)

Operators and shells use this file. End users do not. Essay Bot, Cursor, and Grok Build read it when they diagnose a run. Students do not use it. It is not shown in chat and it is not written into Word.

Student installs leave it off. A shell turns it on by setting `ESSAY_WRITER_DEBUG=1` on the `essay-writer` process (`true`, `on`, and `yes` do the same). `ESSAY_WRITER_DEBUG=0` keeps it off (`false`, `off`, and `no` do the same) and wins over the operator default. When that variable is unset, `"debug": true` in the setup record the server already reads also turns it on. Setup `where` `grokbot-cloud-computer` does not turn it on by itself. An operator end-to-end test flag in the setup record turns it on when that record marks operator e2e on. A student save (`where` `user-local`, or no setup record) stays off. `essay.setup` does not ask for this and does not repeat it. A later setup leaves an existing `debug` flag in place.

The file is `debug.log` in the essay app folder the server already uses. That folder is `ESSAY_WRITER_ROOT` when it is set, otherwise the app folder stored at setup, otherwise the folder that contains this package. When `ESSAY_WRITER_ROOT` is set, the setup record is not consulted, so use `ESSAY_WRITER_DEBUG`. The log is not given its own separate path.

When the operator asks to delete the logs or clear the debug log, `essay.debug.wipe` clears that prose log, the structured ML JSONL, and the incident record in the app folder together. There is no settings toggle and no chat button.

Each line is one tool call: the time, the tool, draft or confirm, the module or sequence, whether it was refused, and whether anything was written. A Consensus key, an Unpaywall email, and a token are not written.

## Event stream (operators and shells)

Operators and shells use this file. End users do not. It is a structured event stream for later review, not a copy of the chat. Students do not use it. It is not shown in chat and it is not written into Word.

It follows the same on/off split as the debug log. Student installs leave it off. `ESSAY_WRITER_DEBUG=1` (`true`, `on`, or `yes`) turns it on. `ESSAY_WRITER_DEBUG=0` (`false`, `off`, or `no`) keeps it off and wins over the operator default. When that variable is unset, `"debug": true` in the setup record also turns it on. Setup `where` `grokbot-cloud-computer` does not turn it on by itself. An operator end-to-end test flag in the setup record turns it on when that record marks operator e2e on. A student save (`where` `user-local`, or no setup record) stays off.

The file is `ml-events.jsonl` in the same essay app folder as `debug.log`. That path is `essay_writer.debug_log.ml_events_path`, the file `wipe_operator_log_files` already clears. Cursor and Grok Build write it through `essay_writer.ml_events.note_events`, which `essay_writer.debug_log.note_call` calls. Grok Build does not keep a second stream.

Each line is one JSON object. The kinds are stage, confirm, digest, paths, shell, and outcome. A line names the tool, the stage, whether a confirm card was present, a digest hash, a file path with its time and checksum, which shell started or finished, and whether the call wrote or was refused. The student's chat, the stage note, and the launch prompt are not copied into the line.

`essay.debug.wipe` is the only clear. Delete the logs, or clear the debug log, removes both files and the incident record. There is no second wipe door.

## Incident record

This file is always on. A student install writes it when the debug log is off. The file is `incident.jsonl` in the app folder, mode 0600. The rotated copy is `incident.jsonl.1`, also mode 0600. At 256 KB or 200 lines, whichever comes first, the live file is renamed to `incident.jsonl.1` and a new file starts. One process lock covers that rename plus the append, and the same lock covers the wipe, so two callers cannot rotate the same file twice or drop a line.

The app folder is `ESSAY_WRITER_ROOT` when it is set, otherwise the folder stored at setup. When neither is set, the folder that contains this package is used. That package-directory fallback is a dev-only degradation. A student install has a setup app folder or `ESSAY_WRITER_ROOT`. In this checkout, `incident.jsonl`, `incident.jsonl.1`, and `support.zip` are gitignored.

Each line is one JSON object. It has the UTC time, the build commit, a prompt hash, the sequence id, the tool, the stage, a stable code, a disposition (`retry`, `fallback`, or `refuse`), and a severity (`error`, `warn`, or `info`). An exception line adds the exception class and the code `unhandled`. The message is empty unless it is exactly `Windows is not supported.` The line does not contain essay text, a prompt, chat, a file body, a path, or a secret value. `debug.log` and `ml-events.jsonl` stay the opt-in stream. Incident lines are not copied into them.

`essay-writer --support-bundle` writes `support.zip` in the app folder. The zip contains the incident lines, `health.json` (version, build commit, prompt hash, and door names), `files.json` (sequence ids and SHA-256 values of state files, not the file contents), and `manifest.json` (counts, including soft incidents by code). Debug logs are added only when they were already on, and they pass through the same redaction as a debug export. A logging failure does not stop the student.

## Environment overrides (operators and tests)

Set these on the `essay-writer` process, not in chat. The first three change behaviour. The last two are internal signals: do not set them by hand.

- `ESSAY_WRITER_MAC_HOME` — the friend's Mac home this computer can see, when a non-Darwin shell already has it mounted. Unset, empty, or `open` means the Mac is not mounted, so the handoff stays chat-only. A named folder that does not exist is treated the same way.
- `ESSAY_WRITER_RESOLVERS` — paper look-up mode: `live` (default), `off` (skip look-ups), or `fixture` (the test set).
- `ESSAY_WRITER_UPDATE_LOCK` — the path of the process-wide `--update` lock. Unset uses `essay-writer-update.lock` in the system temp folder.
- `ESSAY_WRITER_INTERPRETER` — internal handoff signal. The bootstrap sets it to the interpreter it re-execs into, and a consumer reads it to skip a second bootstrap.
- `ESSAY_WRITER_BUILD` — internal build label. It overrides the `BUILD-COMMIT` marker for one run; `essay.health` reports it as `build_commit`.
