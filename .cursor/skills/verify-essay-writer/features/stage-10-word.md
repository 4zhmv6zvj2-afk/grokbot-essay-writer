# Stage 10 final Word

The finished essay is the stage 10 Word file. It is written only after the reviewer records PASS for stage 9 on the current Word file. Stage 10 does not submit the essay.

## Sub-features

- `final-review` records PASS for stage 9 against the current Word file.
- `final-copy` writes `<module>-final.docx` under the stage 10 folder on the sequence.
- `final-stop` leaves submission to the student.

## How to get to it (user POV)

- Finish the first Word file and the later edit stages until stage 9 is the open stage.
- Ask for the independent review of that Word file.
- Confirm stage 10 after the review returns PASS. The chat names the final Word file on this sequence.
- Submit the file yourself. The tool does not submit.

## Driving it with verify-essay-writer

Preconditions:

- Doctor reports version `0.9.17` on this student folder.
- A current Word file already exists on the sequence, and stage 9 is the open stage.
- The citation list for this sequence is already written.

- **Review the current file.** Start `python -m essay_writer --reviewer` with the same `ESSAY_WRITER_ROOT`. Call `essay.review` for stage 9, draft then confirm, against the Word file that is about to be finished. An older file, or a pass with no file, does not clear the write.
- **Finish.** On the writer server, call `essay.stage` with `stage` `10`, draft then confirm, using `cardAction` `confirm` and the `cardDigest` from that draft. Stage 10 writes the final copy and does not submit.
- **Proof.** The file is `Essay-writer/<module>/sequences/<n>/output/<module>-10/<module>-final.docx`. A mark file `.stage10-copied.json` sits beside the Word file that was copied. Both must be present. The final file is absent when stage 9 has no PASS.

`drive-research-gather` does not reach stage 10. A research-gather evidence pack is not proof of this feature.

## Gotchas

- Stage 9 and stage 6 use the same reviewer. A stage 6 PASS does not clear stage 9.
- The writer server has no `essay.review` tool. Looking for it there and then writing Word anyway fails this feature.
- The final folder is `<module>-10` on the sequence, not a Documents path. Name Documents only when that folder is already on this computer.
- Stage 10 does not submit. A run that uploads the file somewhere has left the student path.
- Cursor and the Build shell write the same bytes through the same writer doors. The stage launch command differs by shell (`essay-writer --cursor-stage-launch` and `essay-writer --stage-launch`). The file check above is the proof either way.
