# Operator log

Operators and shells use these files. End users do not.

## Debug log (operators and shells)

Operators and shells use this file. End users do not. Essay Bot, Cursor, and Grok Build read it when they diagnose a run. Students do not use it. It is not shown in chat and it is not written into Word.

Student installs leave it off. A shell turns it on by setting `ESSAY_WRITER_DEBUG=1` on the `essay-writer` process (`true`, `on`, and `yes` do the same). `ESSAY_WRITER_DEBUG=0` keeps it off (`false`, `off`, and `no` do the same) and wins over the operator default. When that variable is unset, `"debug": true` in the setup record the server already reads also turns it on. Setup `where` `grokbot-cloud-computer` does not turn it on by itself. An operator end-to-end test flag in the setup record turns it on when that record marks operator e2e on. A student save (`where` `user-local`, or no setup record) stays off. `essay.setup` does not ask for this and does not repeat it. A later setup leaves an existing `debug` flag in place.

The file is `debug.log` in the essay app folder the server already uses. That folder is `ESSAY_WRITER_ROOT` when it is set, otherwise the app folder stored at setup, otherwise the folder that contains this package. When `ESSAY_WRITER_ROOT` is set, the setup record is not consulted, so use `ESSAY_WRITER_DEBUG`. The log is not given its own separate path.

When the operator asks to delete the logs or clear the debug log, `essay.debug.wipe` clears that prose log and the structured ML JSONL in the app folder together. There is no settings toggle and no chat button.

Each line is one tool call: the time, the tool, draft or confirm, the module or sequence, whether it was refused, and whether anything was written. A Consensus key, an Unpaywall email, and a token are not written.

## Event stream (operators and shells)

Operators and shells use this file. End users do not. It is a structured event stream for later review, not a copy of the chat. Students do not use it. It is not shown in chat and it is not written into Word.

It follows the same on/off split as the debug log. Student installs leave it off. `ESSAY_WRITER_DEBUG=1` (`true`, `on`, or `yes`) turns it on. `ESSAY_WRITER_DEBUG=0` (`false`, `off`, or `no`) keeps it off and wins over the operator default. When that variable is unset, `"debug": true` in the setup record also turns it on. Setup `where` `grokbot-cloud-computer` does not turn it on by itself. An operator end-to-end test flag in the setup record turns it on when that record marks operator e2e on. A student save (`where` `user-local`, or no setup record) stays off.

The file is `ml-events.jsonl` in the same essay app folder as `debug.log`. That path is `essay_writer.debug_log.ml_events_path`, the file `wipe_operator_log_files` already clears. Cursor and Grok Build write it through `essay_writer.ml_events.note_events`, which `essay_writer.debug_log.note_call` calls. Grok Build does not keep a second stream.

Each line is one JSON object. The kinds are stage, confirm, digest, paths, shell, and outcome. A line names the tool, the stage, whether a confirm card was present, a digest hash, a file path with its time and checksum, which shell started or finished, and whether the call wrote or was refused. The student's chat, the stage note, and the launch prompt are not copied into the line.

`essay.debug.wipe` is the only clear. Delete the logs, or clear the debug log, removes both files. There is no second wipe door.
