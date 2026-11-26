# Refusals

A student is stopped only when continuing would be wrong, misleading, or lose saved state.
A recoverable defect is a fallback. The same code is the incident record.
Internal detail stays in the operator log.
The where column is a file name. The test owns the codes.

| code | student copy | disposition | next step | where |
| --- | --- | --- | --- | --- |
| no-brief | (built at the door) | refuse | Add the assignment brief, then answer the format or the question. | assignment_gate.py |
| answer | (built at the door) | refuse | The brief is unchanged. This stage was not saved. | assignment_gate.py |
| named-parts | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py |
| brief-mapping | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py |
| title-page | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py |
| citation-list | (built at the door) | refuse | The reason sentence names the next step. | citation_list.py |
| citation-list | That source is not on the citation list. Nothing was written. | refuse | Add that source to the citation list, then try this step again. | citation_list.py |
| citation-list | That list entry has no research note to point at. Nothing was written. | refuse | The reason sentence names the next step. | citation_list.py |
| confirm | That step was not shown in a form this chat can save. | refuse | The reason sentence names the next step. | confirm.py |
| confirm | This step has not been shown yet. Ask me to show it, then save. | refuse | The reason sentence names the next step. | confirm.py |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py |
| confirm | The saved files changed after that step was shown. Ask me to show it again. | refuse | The reason sentence names the next step. | confirm.py |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py |
| debug-wipe | That request does not clear the run log. | refuse | Ask again with delete the logs, or clear debug log. | debug_log.py |
| debug-export | The export could not be written. | refuse | Ask me to export the log again. | debug_log.py |
| debug-wipe | Say what you want cleared, such as delete the logs or clear debug log. | refuse | The reason sentence names the next step. | debug_log.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | dig.py |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | dig.py |
| dig | Name the dig query. An empty query does not invent papers. | refuse | The reason sentence names the next step. | dig.py |
| dig | (built at the door) | refuse | The reason sentence names the next step. | dig.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | downloads.py |
| lock-choice | lockChoice must be revise, keep, or relock. | refuse | The reason sentence names the next step. | fo_chat_locks.py |
| delete | Ask whether to delete the cloud workspace only, Mac-local copies only, or both. Pass where grokbot, local, or both on essay.project.delete draft. Nothing was removed. | refuse | The reason sentence names the next step. | fo_chat_locks.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | free_alt.py |
| 4a | Confirm the annotated bibliography before fetching leftovers. | refuse | The reason sentence names the next step. | free_alt.py |
| harvard-references | The independent reviewer cannot clear without running the Harvard reference check. | refuse | Run the Harvard reference check, then clear the review. | harvard_ref_check.py |
| harvard-references | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py |
| seat | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py |
| confirm | The latest Word file changed after the draft. Fresh draft required. | refuse | Ask me to show this step again, then save. | intake.py |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py |
| intake | This is a photo, not a Word draft. Name the module and I'll file the words for every sequence. | refuse | The reason sentence names the next step. | intake.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | intake.py |
| intake | Say whether this is a new module or a roll-forward onto a module you already have. | refuse | The reason sentence names the next step. | intake.py |
| intake | create is yes or no. | refuse | Send create as yes or no. | intake.py |
| intake | rollForward is yes or no. | refuse | Send rollForward as yes or no. | intake.py |
| intake | Name the module. I roll this forward onto that module's next sequence. | refuse | The reason sentence names the next step. | intake.py |
| intake | That file isn't a Word draft, so I can't roll it forward. Name the module if you want it filed for every sequence. | refuse | The reason sentence names the next step. | intake.py |
| intake | Name the module code for the new essay, such as MOD1008AA. | refuse | The reason sentence names the next step. | intake.py |
| intake | A new essay from Word needs a Word file. Name the module if you want this one filed for every sequence. | refuse | The reason sentence names the next step. | intake.py |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | intake.py |
| intake | Show the words from this photo first. Nothing was filed. | refuse | The reason sentence names the next step. | intake.py |
| intake | I couldn't file this photo. It is still waiting, and nothing was saved. | refuse | The reason sentence names the next step. | intake.py |
| sequence | I couldn't finish the new sequence, so I didn't keep a partial copy. Say if you want me to try again. | refuse | The reason sentence names the next step. | intake.py |
| repo-not-save | The code checkout is not a student save. | refuse | The reason sentence names the next step. | known_paths.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | originals.py |
| originals | action must be list or read | refuse | Send action as list or read. | originals.py |
| originals | kind must be upload or brief | refuse | The reason sentence names the next step. | originals.py |
| originals | read needs the file name inside this essay | refuse | The reason sentence names the next step. | originals.py |
| originals | brief read only opens brief.md, brief.txt, or brief.docx | refuse | The reason sentence names the next step. | originals.py |
| originals | that file is not in this essay | refuse | The reason sentence names the next step. | originals.py |
| invented | Do not invent a student folder path. | refuse | Name a folder you chose. I will not invent one. | originals.py |
| snapshot-corrupt | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py |
| snapshot-missing | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py |
| snapshot-missing | Name the snapshot to restore. Nothing was written. | refuse | The reason sentence names the next step. | pack_backup.py |
| delete | Choose where to delete: grokbot for this essay workspace only, local for Word and zip files on your computer only, or both. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| projects | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| projects | view must be continue, roll-forward, archive, delete, or unarchive. | refuse | Send view as continue, roll-forward, archive, delete, or unarchive. | projects.py |
| archive | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| unarchive | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| delete | Name each Word file or zip on your computer as a path. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | That path is not a file name. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | Name the full path of the Word file or zip, starting from the top of the computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | That path is not a named file on this computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | That path is a link. Name the Word file or zip itself. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | Name the Word file or zip in its folder. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | That path is not a Word file or a zip. Name a .docx or a .zip on your computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | That file is in this essay workspace. It is not a copy on your computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | This computer will not remove a folder. Name the Word file or zip. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | I can't see that file on this computer, so it was not removed. Name a Word file or zip this computer can already open. If that copy sits on a Mac folder that is not mounted here, it stays until this computer can see it. | refuse | The reason sentence names the next step. | projects.py |
| delete | A workspace-only delete does not remove files on your computer. Choose local or both to include those Word and zip files. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | Name each Word file or zip on your computer. Nothing is removed until those paths are listed and you say yes to that list. | refuse | The reason sentence names the next step. | projects.py |
| delete | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| delete | The confirm did not say the files on your computer will be removed. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| confirm-card | That card does not match this list. Show the list again in this chat. | refuse | The reason sentence names the next step. | projects.py |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| projects | Name the module code for roll-forward. | refuse | The reason sentence names the next step. | projects.py |
| delete | That file changed after the draft, or this computer can no longer see it. Nothing was removed. Show the list again in this chat. | refuse | The reason sentence names the next step. | projects.py |
| delete | Name the sequence id, such as MOD1004AA-2. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | Name a sequence of this module, such as MOD1004AA-2. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | A sequence delete removes that sequence in this essay workspace. Choose the workspace, or both. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | The saved Word and zip copies for this sequence are not on this computer. Name the full path of each file. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| delete | The saved Word and zip copies for this module are not on this computer. Name the full path of each file. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py |
| sequence | parent must be a sequence id of this module, such as MOD1011AA-5. | refuse | Name a sequence in this module, such as MOD1011AA-5. | projects.py |
| delete | I could not remove every named file. The essay workspace was left in place. | refuse | The reason sentence names the next step. | projects.py |
| stage | (built at the door) | refuse | The reason sentence names the next step. | projects.py |
| sequence | I couldn't finish the new sequence, so I didn't keep a partial copy. Say if you want me to try again. | refuse | The reason sentence names the next step. | projects.py |
| delete | Each path must be a Word file or a zip on your computer. Nothing was removed. | refuse | Name a Word file or a zip on this computer. | projects.py |
| misses | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| topic | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| industry | industry must be an object when it is sent. It is not evidence. | refuse | The reason sentence names the next step. | research.py |
| exclude | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| clarify | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| packs | packs must be a list of local pack names from essay.health. Do not invent one. | refuse | The reason sentence names the next step. | research.py |
| exclude | exclude_section_ids must be the section ids a person chose to leave closed. | refuse | Send the section ids you chose to leave closed. | research.py |
| host_voice | That extra field is not stored evidence. Leave it off this save. | refuse | The reason sentence names the next step. | research.py |
| packs | At most two local packs. Do not invent extras. | refuse | Keep at most two local packs. | research.py |
| packs | (built at the door) | refuse | The reason sentence names the next step. | research.py |
| seat | (built at the door) | refuse | The reason sentence names the next step. | review.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | review.py |
| review | EQR stage is 6 (first Word) or 9 (final Word). | refuse | Send stage 6 or stage 9. | review.py |
| review | (built at the door) | refuse | The reason sentence names the next step. | review.py |
| review | The saved Word file could not be opened. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py |
| review | The finished Word file is saved and was not opened. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py |
| review | Stage 9 checks the opened Word file. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py |
| review | Stage 6 only checks whether the draft answers the assignment question. Nothing was recorded. | refuse | Ask the question check again. Nothing was recorded. | review.py |
| review | The opened Word file has no citations. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py |
| review | The saved draft is not intact. Ask me to show this step again. | refuse | The reason sentence names the next step. | review.py |
| review | The saved first draft is not intact. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | revise.py |
| revise | message says what to change. The door does not invent the revision. | refuse | The reason sentence names the next step. | revise.py |
| revise | Nothing is confirmed yet. Confirm research, or Word, before revise. | refuse | The reason sentence names the next step. | revise.py |
| invent-forbid | (built at the door) | refuse | The reason sentence names the next step. | revise.py |
| citation | (built at the door) | refuse | The reason sentence names the next step. | revise.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | roll_forward.py |
| papers | Name the paper and whether to keep, drop, or replace it. | refuse | The reason sentence names the next step. | roll_forward.py |
| papers | choice must be keep, drop, or replace. | refuse | Send keep, drop, or replace. | roll_forward.py |
| papers | This sequence has no saved papers to keep, drop, or replace. | refuse | The reason sentence names the next step. | roll_forward.py |
| papers | That paper is not on this sequence. | refuse | Choose a paper that is on this sequence. | roll_forward.py |
| setup | That file-work pick is not one of the two setup choices. Ask again, then call essay.setup with that choice. Do not infer it from what is installed. | refuse | The reason sentence names the next step. | setup.py |
| setup | The file-work program stays where it is already installed. This door does not install it, and it does not install it on the Mac. Call essay.setup without install_grokbuild. | refuse | The reason sentence names the next step. | setup.py |
| setup | Save both folders on the cloud computer, or both on this computer. A split between the two is refused. | refuse | The reason sentence names the next step. | setup.py |
| setup | The Unpaywall email is not usable. Skip it, or give an email address. The value is not repeated here. | refuse | The reason sentence names the next step. | setup.py |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py |
| setup | Say whether the Consensus plan is Free or Pro before the key is saved. Teams, Deep, and Enterprise use the same paid flag as Pro. Nothing was written. | refuse | The reason sentence names the next step. | setup.py |
| setup | Skip is not saved until the warning is confirmed. Nothing was written. | refuse | The reason sentence names the next step. | setup.py |
| setup | This computer has no cloud workspace. Name both app_path and kb1_path to save on this computer. Documents is not used, and it is not labelled as the cloud computer. | refuse | The reason sentence names the next step. | setup.py |
| setup | Give both app_path and kb1_path, or omit both to use the cloud computer. | refuse | The reason sentence names the next step. | setup.py |
| repo-not-save | The code checkout is not a student save. | refuse | The reason sentence names the next step. | setup.py |
| setup | Could not create the folders. Allow file access, then call essay.setup again. | refuse | The reason sentence names the next step. | setup.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | shelf.py |
| pack | pack must be an object | refuse | Send the pack as an object. | shelf.py |
| shelf | pack_id has characters the local shelf will not store | refuse | Use a pack id this shelf can store. | shelf.py |
| shelf | topic does not match the pack title. Confirm one title, not two. | refuse | The reason sentence names the next step. | shelf.py |
| shelf | Shelf stores a pack only after Word confirm for that same pack. | refuse | The reason sentence names the next step. | shelf.py |
| confirm | The pack or its gathered files changed after Word. Validate and write Word again before the shelf. | refuse | The reason sentence names the next step. | shelf.py |
| shelf | pack_id is not a local shelf id | refuse | Choose a pack id from this shelf. | shelf.py |
| shelf | no shelf pack for this essay id | refuse | The reason sentence names the next step. | shelf.py |
| cross-essay | that shelf record is not this essay | refuse | The reason sentence names the next step. | shelf.py |
| engagement | (built at the door) | refuse | The reason sentence names the next step. | specialists/eqr.py |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/eqr.py |
| confirm-card | A typed reply does not save this step. Pick the card in the draft reply. | refuse | The reason sentence names the next step. | specialists/grok_bot.py |
| basics-pass | (built at the door) | refuse | The reason sentence names the next step. | specialists/grok_bot.py |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/grok_bot.py |
| confirm-card | Not yet leaves this step unsaved. | refuse | The reason sentence names the next step. | specialists/grok_bot.py |
| word-band | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py |
| draft | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py |
| guidance-only | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| stage | Write what changed, or that the plan still holds, and which gathered source shows it. | refuse | The reason sentence names the next step. | stage_track.py |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| master | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| eqr | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| draft | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| word-band | This first draft is not inside the brief's word band. Change the draft so it fits the brief, then save again. | refuse | The reason sentence names the next step. | stage_track.py |
| pointer | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py |
| stage | The last stage is already saved. This tool does not submit. | refuse | The reason sentence names the next step. | stage_hold.py |
| stage | Save the plan note first. The first draft waits until that save. | refuse | The reason sentence names the next step. | stage_hold.py |
| stage | Save the plan again before the first draft. The earlier lock changed. | refuse | The reason sentence names the next step. | stage_hold.py |
| word | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py |
| misses | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| lock-choice | The inherited lock is empty. Revise instead. | refuse | The reason sentence names the next step. | stage_track.py |
| house-jargon | That note uses an internal label. Say it in plain words. | refuse | The reason sentence names the next step. | stage_track.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| stage | Send a stage from 1 to 10, including 4a and 4b. | refuse | The reason sentence names the next step. | stage_track.py |
| confirm-card | This step moves on when the draft is stored. There is no save-card between this step and the next. | refuse | The reason sentence names the next step. | stage_track.py |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| turn | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py |
| stage | Send the look as plain text. | refuse | The reason sentence names the next step. | stage_track.py |
| state | (built at the door) | refuse | The reason sentence names the next step. | state.py |
| stage | (built at the door) | refuse | The reason sentence names the next step. | state.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | validate.py |
| pack | pack must be an object | refuse | Send the pack as an object. | validate.py |
| footer | (built at the door) | refuse | The reason sentence names the next step. | word.py |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | word.py |
| pack | pack must be an object | refuse | Send the pack as an object. | word.py |
| word-only | Word .docx is the only output. PDF is refused. | refuse | Send a Word .docx file. | word.py |
| stage | Word stage is 6 for the first Word file, 7 after the questions and edits, or 9 for the references confirm. | refuse | The reason sentence names the next step. | word.py |
| validate | This pack did not pass validation. Word was not written. | refuse | Fix the pack, then ask me to write the Word file again. | word.py |
| validate | Validate this pack with draft, then confirm, before Word confirm. A changed pack needs both steps again. | refuse | The reason sentence names the next step. | word.py |
| confirm | Gathered files changed after validation. Fresh validate draft required. | refuse | Ask me to validate again, then save. | word.py |
| stage | Ask, then edit from the answers, before this Word save. | refuse | The reason sentence names the next step. | word.py |
| footer | The page number is missing. An empty footer is refused. | refuse | Add the page number, then save the Word file again. | word.py |
| eqr | (built at the door) | refuse | The reason sentence names the next step. | word.py |
| empty-references | The References section has no entries. Add reference lines before this step can close. | refuse | The reason sentence names the next step. | word_references.py |
| references-cites | (built at the door) | refuse | The reason sentence names the next step. | word_references.py |
| smaller-questions | A missing or refused smaller-question list leaves the confirmed question. | fallback | The gather continues with the confirmed question. | tests/test_source_floor.py |
| word-title-spare | A refused Word title becomes the spare title Essay. | fallback | The Word file still uses the spare title. | tests/test_model_contract.py |
| pdf-gap-unwritten | A gap note that cannot be saved stays in memory for this read. | fallback | The paper is still opened. The gap file is unchanged. | tests/test_refusals.py |
| pointer-damaged | A stage pointer that is not JSON is not rewritten. | fallback | Ask me to show this step again before saving. | tests/test_refusals.py |
| crash-recovered | A load found a stage-commit temp. The temp stays. A valid journal beside it is still replayed. | fallback | The load continues and the temp is not removed. | stage_state.py |
| encourage-unwritten | An encourage note that cannot be saved is not stored. | fallback | The plan or the answer is unchanged on disk. Ask again. | tests/test_refusals.py |
| state-damaged | The state file is damaged. | refuse | Ask me to show this step again. The file is not replaced. | state.py |
| state-field-filled | A missing state field is filled in memory. | fallback | The file is unchanged until the next save. | state.py |
| state-unknown-field | An unknown state field is kept. | fallback | The file is unchanged until the next save. | state.py |
| pointer-field-filled | A missing pointer field is filled in memory. | fallback | The file is unchanged until the next save. | stage_state.py |
| pointer-unknown-field | An unknown pointer field is kept. | fallback | The file is unchanged until the next save. | stage_state.py |
| pointer-unknown-current | A current value that is not a stage becomes stage 1 in memory. | fallback | The file is unchanged until the next save. | stage_state.py |
| pointer-field-dropped | A saved or files value of the wrong shape is left out of the loaded pointer. | fallback | The file is unchanged until the next save. | stage_state.py |
| read-retry | A read is tried again after a timeout, a DNS failure, a 429, or a 5xx. | retry | The next try uses the same address. | safe_url.py |
| read-fallback | A read stopped after its tries. | fallback | Try this look-up again. | safe_url.py |
| read-dns | The host did not resolve. | fallback | Check the address and try again. | safe_url.py |
| read-redirect | The address redirected too many times. | fallback | Use a direct link. | safe_url.py |
| read-too-large | The file is larger than the cap. | fallback | Use a smaller file. | safe_url.py |
| read-bad-json | The look-up did not return JSON. | fallback | Try this look-up again. | dig.py |
| page-cursor-repeat | This page repeated a cursor. | fallback | The gather stops on this page. Try the look-up again. | dig.py |
