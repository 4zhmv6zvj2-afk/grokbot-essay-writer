# First-draft Word after review

After the citation list, the student gets a first draft and then a Word file. Stage 5 stores the draft with no Confirm card. The first Word file waits until the reviewer records PASS for stage 6.

## Sub-features

- `draft-store` stores the stage 5 draft on the draft call.
- `draft-review` records PASS for stage 6 on the reviewer.
- `draft-word` writes the first Word file only after that pass.

## How to get to it (user POV)

- Finish the research gather and the citation list for this sequence. Stage 4b has one critical-review note per paper.
- Read the first draft when stage 5 stores it. There is no Confirm card between that draft and stage 6.
- Ask for the independent review. The reviewer is a separate Essay Writer process.
- Confirm the Word write for stage 6 after the review returns PASS. The chat names the Word file on this sequence.

## Driving it with verify-essay-writer

Preconditions:

- Doctor reports the installed package version on this student folder.
- The sequence already has a written citation list, and `essay.dig` is not blocked for a further page.
- Launch and the research-gather drive have already been run, or the same doors have been driven by hand on this folder.

- **Store the draft.** Call `essay.stage` with the sequence id, `stage` `5`, and `confirmPhase` `draft`. The draft call stores the first draft and moves the pointer to stage 6. Do not send a confirm for stage 5.
- **Review.** Start a second server with `python -m essay_writer --reviewer` and the same `ESSAY_WRITER_ROOT`. Call `essay.review` for stage 6, draft then confirm. The writer server does not mount `essay.review`. PASS is the result that allows Word. On PASS confirm, the reviewer may write a plain first draft to `output/<sequence-id>.docx` when that file is not already there.
- **Write Word.** On the writer server, after `essay.pack.validate` confirm, call `essay.pack.render_word` with `stage` `6`, draft then confirm, for the same pack that validation confirmed. Draft writes nothing. Confirm writes the formatted pack file.
- **Proof.** The file is `Essay-writer/<module>/sequences/<n>/output/<sequence-id>.docx`. A missing PASS, or a gather that is still blocked, leaves that file absent from the render path. Record the review result and the file path.

`drive-research-gather` stops at the citation list. Run the three calls above when you verify this feature, or run `verify-essay-writer conversations` for the synthetic golden path on the real doors. Do not mark it passed from the gather evidence alone.

## Gotchas

- Stage 5 has no Confirm card. A confirm sent for stage 5 is the wrong call.
- The writer door refuses the Word write on stage 6 until `essay.review` returns PASS. The writer does not review itself.
- The first draft is written from the stage 4b notes, one note per paper. A missing note is not replaced with a made-up paragraph.
- A count under the source floor with `further_page` still true blocks the draft. Do not write the Word file to get past that block.
- The Word file stays on the sequence. Do not invent a Documents path when that folder is not on this computer.
