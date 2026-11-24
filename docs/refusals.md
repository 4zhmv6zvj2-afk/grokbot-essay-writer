# Refusals

A student is stopped only when continuing would be wrong, misleading, or lose saved state.
A recoverable defect is a fallback. The same code is the incident record.
Internal detail stays in the operator log.

| code | student copy | disposition | next step | where |
| --- | --- | --- | --- | --- |
| no-brief | (built at the door) | refuse | Add the assignment brief, then answer the format or the question. | assignment_gate.py:823 |
| answer | (built at the door) | refuse | The brief is unchanged. This stage was not saved. | assignment_gate.py:833 |
| named-parts | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py:329 |
| brief-mapping | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py:309 |
| brief-mapping | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py:392 |
| title-page | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py:410 |
| named-parts | (built at the door) | refuse | The reason sentence names the next step. | brief_contract.py:424 |
| citation-list | (built at the door) | refuse | The reason sentence names the next step. | citation_list.py:657 |
| citation-list | (built at the door) | refuse | The reason sentence names the next step. | citation_list.py:659 |
| citation-list | (built at the door) | refuse | The reason sentence names the next step. | citation_list.py:661 |
| citation-list | That source is not on the citation list. Nothing was written. | refuse | Add that source to the citation list, then try this step again. | citation_list.py:902 |
| citation-list | That list entry has no research note to point at. Nothing was written. | refuse | The reason sentence names the next step. | citation_list.py:911 |
| citation-list | (built at the door) | refuse | The reason sentence names the next step. | citation_list.py:669 |
| confirm | That step was not shown in a form this chat can save. | refuse | The reason sentence names the next step. | confirm.py:86 |
| confirm | This step has not been shown yet. Ask me to show it, then save. | refuse | The reason sentence names the next step. | confirm.py:82 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:249 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:257 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:265 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:273 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:280 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | confirm.py:307 |
| confirm | The saved files changed after that step was shown. Ask me to show it again. | refuse | The reason sentence names the next step. | confirm.py:313 |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py:460 |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py:463 |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py:476 |
| debug-wipe | That request does not clear the run log. | refuse | Ask again with delete the logs, or clear debug log. | debug_log.py:507 |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py:447 |
| debug-export | (built at the door) | refuse | The reason sentence names the next step. | debug_log.py:457 |
| debug-export | The export could not be written. | refuse | Ask me to export the log again. | debug_log.py:469 |
| debug-wipe | Say what you want cleared, such as delete the logs or clear debug log. | refuse | The reason sentence names the next step. | debug_log.py:503 |
| debug-export | The export could not be written. | refuse | Ask me to export the log again. | debug_log.py:452 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | dig.py:1362 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | dig.py:1431 |
| dig | Name the dig query. An empty query does not invent papers. | refuse | The reason sentence names the next step. | dig.py:1377 |
| dig | (built at the door) | refuse | The reason sentence names the next step. | dig.py:1383 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | downloads.py:743 |
| lock-choice | lockChoice must be revise, keep, or relock. | refuse | The reason sentence names the next step. | fo_chat_locks.py:206 |
| delete | Ask whether to delete the cloud workspace only, Mac-local copies only, or both. Pass where grokbot, local, or both on essay.project.delete draft. Nothing was removed. | refuse | The reason sentence names the next step. | fo_chat_locks.py:258 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | free_alt.py:102 |
| 4a | Confirm the annotated bibliography before fetching leftovers. | refuse | The reason sentence names the next step. | free_alt.py:110 |
| harvard-references | The independent reviewer cannot clear without running the Harvard reference check. | refuse | Run the Harvard reference check, then clear the review. | harvard_ref_check.py:46 |
| harvard-references | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py:106 |
| harvard-references | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py:40 |
| seat | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py:129 |
| harvard-references | (built at the door) | refuse | The reason sentence names the next step. | harvard_ref_check.py:138 |
| confirm | The latest Word file changed after the draft. Fresh draft required. | refuse | Ask me to show this step again, then save. | intake.py:613 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:701 |
| intake | This is a photo, not a Word draft. Name the module and I'll file the words for every sequence. | refuse | The reason sentence names the next step. | intake.py:703 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | intake.py:724 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:726 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:729 |
| intake | Say whether this is a new module or a roll-forward onto a module you already have. | refuse | The reason sentence names the next step. | intake.py:854 |
| intake | create is yes or no. | refuse | Send create as yes or no. | intake.py:859 |
| intake | rollForward is yes or no. | refuse | Send rollForward as yes or no. | intake.py:861 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:867 |
| intake | Name the module. I roll this forward onto that module's next sequence. | refuse | The reason sentence names the next step. | intake.py:880 |
| intake | That file isn't a Word draft, so I can't roll it forward. Name the module if you want it filed for every sequence. | refuse | The reason sentence names the next step. | intake.py:885 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | intake.py:908 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:910 |
| intake | Name the module code for the new essay, such as MOD1008AA. | refuse | The reason sentence names the next step. | intake.py:931 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | intake.py:934 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:936 |
| intake | A new essay from Word needs a Word file. Name the module if you want this one filed for every sequence. | refuse | The reason sentence names the next step. | intake.py:938 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | intake.py:518 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:709 |
| intake | Show the words from this photo first. Nothing was filed. | refuse | The reason sentence names the next step. | intake.py:738 |
| intake | I couldn't file this photo. It is still waiting, and nothing was saved. | refuse | The reason sentence names the next step. | intake.py:806 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:865 |
| sequence | I couldn't finish the new sequence, so I didn't keep a partial copy. Say if you want me to try again. | refuse | The reason sentence names the next step. | intake.py:526 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | intake.py:536 |
| sequence | I couldn't finish the new sequence, so I didn't keep a partial copy. Say if you want me to try again. | refuse | The reason sentence names the next step. | intake.py:538 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:895 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:901 |
| intake | (built at the door) | refuse | The reason sentence names the next step. | intake.py:984 |
| repo-not-save | The code checkout is not a student save. | refuse | The reason sentence names the next step. | known_paths.py:238 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | originals.py:61 |
| originals | action must be list or read | refuse | Send action as list or read. | originals.py:63 |
| originals | kind must be upload or brief | refuse | The reason sentence names the next step. | originals.py:65 |
| originals | read needs the file name inside this essay | refuse | The reason sentence names the next step. | originals.py:80 |
| originals | brief read only opens brief.md, brief.txt, or brief.docx | refuse | The reason sentence names the next step. | originals.py:87 |
| originals | that file is not in this essay | refuse | The reason sentence names the next step. | originals.py:89 |
| invented | Do not invent a student folder path. | refuse | Name a folder you chose. I will not invent one. | originals.py:94 |
| snapshot-corrupt | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py:382 |
| snapshot-missing | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py:386 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | pack_backup.py:73 |
| snapshot-missing | Name the snapshot to restore. Nothing was written. | refuse | The reason sentence names the next step. | pack_backup.py:99 |
| snapshot-missing | Name the snapshot to restore. Nothing was written. | refuse | The reason sentence names the next step. | pack_backup.py:83 |
| delete | Choose where to delete: grokbot for this essay workspace only, local for Word and zip files on your computer only, or both. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:536 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py:300 |
| projects | (built at the door) | refuse | The reason sentence names the next step. | projects.py:302 |
| projects | (built at the door) | refuse | The reason sentence names the next step. | projects.py:305 |
| projects | view must be continue, roll-forward, archive, delete, or unarchive. | refuse | Send view as continue, roll-forward, archive, delete, or unarchive. | projects.py:335 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py:442 |
| archive | (built at the door) | refuse | The reason sentence names the next step. | projects.py:451 |
| archive | (built at the door) | refuse | The reason sentence names the next step. | projects.py:453 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py:489 |
| unarchive | (built at the door) | refuse | The reason sentence names the next step. | projects.py:498 |
| delete | Name each Word file or zip on your computer as a path. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:559 |
| delete | That path is not a file name. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:584 |
| delete | Name the full path of the Word file or zip, starting from the top of the computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:587 |
| delete | That path is not a named file on this computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:594 |
| delete | That path is a link. Name the Word file or zip itself. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:600 |
| delete | Name the Word file or zip in its folder. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:606 |
| delete | That path is not a Word file or a zip. Name a .docx or a .zip on your computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:612 |
| delete | That file is in this essay workspace. It is not a copy on your computer. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:619 |
| delete | This computer will not remove a folder. Name the Word file or zip. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:625 |
| delete | I can't see that file on this computer, so it was not removed. Name a Word file or zip this computer can already open. If that copy sits on a Mac folder that is not mounted here, it stays until this computer can see it. | refuse | The reason sentence names the next step. | projects.py:631 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py:843 |
| delete | A workspace-only delete does not remove files on your computer. Choose local or both to include those Word and zip files. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:861 |
| delete | Name each Word file or zip on your computer. Nothing is removed until those paths are listed and you say yes to that list. | refuse | The reason sentence names the next step. | projects.py:904 |
| delete | (built at the door) | refuse | The reason sentence names the next step. | projects.py:934 |
| delete | The confirm did not say the files on your computer will be removed. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:973 |
| confirm-card | That card does not match this list. Show the list again in this chat. | refuse | The reason sentence names the next step. | projects.py:1059 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1391 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1400 |
| projects | Name the module code for roll-forward. | refuse | The reason sentence names the next step. | projects.py:332 |
| delete | That file changed after the draft, or this computer can no longer see it. Nothing was removed. Show the list again in this chat. | refuse | The reason sentence names the next step. | projects.py:674 |
| delete | Name the sequence id, such as MOD1004AA-2. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:749 |
| delete | Name a sequence of this module, such as MOD1004AA-2. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:755 |
| delete | A sequence delete removes that sequence in this essay workspace. Choose the workspace, or both. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:760 |
| delete | (built at the door) | refuse | The reason sentence names the next step. | projects.py:767 |
| delete | The saved Word and zip copies for this sequence are not on this computer. Name the full path of each file. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:880 |
| delete | The saved Word and zip copies for this module are not on this computer. Name the full path of each file. Nothing was removed. | refuse | The reason sentence names the next step. | projects.py:893 |
| delete | Name each Word file or zip on your computer. Nothing is removed until those paths are listed and you say yes to that list. | refuse | The reason sentence names the next step. | projects.py:919 |
| delete | (built at the door) | refuse | The reason sentence names the next step. | projects.py:928 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1405 |
| sequence | parent must be a sequence id of this module, such as MOD1011AA-5. | refuse | Name a sequence in this module, such as MOD1011AA-5. | projects.py:1414 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1420 |
| delete | I could not remove every named file. The essay workspace was left in place. | refuse | The reason sentence names the next step. | projects.py:1080 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1471 |
| sequence | (built at the door) | refuse | The reason sentence names the next step. | projects.py:1478 |
| sequence | I couldn't finish the new sequence, so I didn't keep a partial copy. Say if you want me to try again. | refuse | The reason sentence names the next step. | projects.py:1480 |
| delete | Each path must be a Word file or a zip on your computer. Nothing was removed. | refuse | Name a Word file or a zip on this computer. | projects.py:553 |
| misses | (built at the door) | refuse | The reason sentence names the next step. | research.py:230 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | research.py:399 |
| topic | (built at the door) | refuse | The reason sentence names the next step. | research.py:402 |
| confirm | (built at the door) | refuse | The reason sentence names the next step. | research.py:485 |
| industry | industry must be an object when it is sent. It is not evidence. | refuse | The reason sentence names the next step. | research.py:94 |
| exclude | (built at the door) | refuse | The reason sentence names the next step. | research.py:243 |
| clarify | (built at the door) | refuse | The reason sentence names the next step. | research.py:414 |
| packs | packs must be a list of local pack names from essay.health. Do not invent one. | refuse | The reason sentence names the next step. | research.py:64 |
| exclude | exclude_section_ids must be the section ids a person chose to leave closed. | refuse | Send the section ids you chose to leave closed. | research.py:87 |
| host_voice | That extra field is not stored evidence. Leave it off this save. | refuse | The reason sentence names the next step. | research.py:100 |
| packs | At most two local packs. Do not invent extras. | refuse | Keep at most two local packs. | research.py:69 |
| packs | (built at the door) | refuse | The reason sentence names the next step. | research.py:76 |
| seat | (built at the door) | refuse | The reason sentence names the next step. | review.py:74 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | review.py:82 |
| review | EQR stage is 6 (first Word) or 9 (final Word). | refuse | Send stage 6 or stage 9. | review.py:84 |
| review | (built at the door) | refuse | The reason sentence names the next step. | review.py:89 |
| review | The saved Word file could not be opened. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py:101 |
| review | The finished Word file is saved and was not opened. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py:103 |
| review | (built at the door) | refuse | The reason sentence names the next step. | review.py:118 |
| review | Stage 9 checks the opened Word file. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py:128 |
| review | Stage 6 only checks whether the draft answers the assignment question. Nothing was recorded. | refuse | Ask the question check again. Nothing was recorded. | review.py:153 |
| review | (built at the door) | refuse | The reason sentence names the next step. | review.py:167 |
| review | The opened Word file has no citations. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py:175 |
| review | The saved draft is not intact. Ask me to show this step again. | refuse | The reason sentence names the next step. | review.py:256 |
| review | (built at the door) | refuse | The reason sentence names the next step. | review.py:262 |
| review | The saved first draft is not intact. Nothing was recorded. | refuse | The reason sentence names the next step. | review.py:145 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | revise.py:42 |
| revise | message says what to change. The door does not invent the revision. | refuse | The reason sentence names the next step. | revise.py:51 |
| revise | Nothing is confirmed yet. Confirm research, or Word, before revise. | refuse | The reason sentence names the next step. | revise.py:58 |
| invent-forbid | (built at the door) | refuse | The reason sentence names the next step. | revise.py:65 |
| citation | (built at the door) | refuse | The reason sentence names the next step. | revise.py:94 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | roll_forward.py:275 |
| papers | Name the paper and whether to keep, drop, or replace it. | refuse | The reason sentence names the next step. | roll_forward.py:277 |
| papers | choice must be keep, drop, or replace. | refuse | Send keep, drop, or replace. | roll_forward.py:280 |
| papers | This sequence has no saved papers to keep, drop, or replace. | refuse | The reason sentence names the next step. | roll_forward.py:284 |
| papers | That paper is not on this sequence. | refuse | Choose a paper that is on this sequence. | roll_forward.py:288 |
| setup | That file-work pick is not one of the two setup choices. Ask again, then call essay.setup with that choice. Do not infer it from what is installed. | refuse | The reason sentence names the next step. | setup.py:104 |
| setup | The file-work program stays where it is already installed. This door does not install it, and it does not install it on the Mac. Call essay.setup without install_grokbuild. | refuse | The reason sentence names the next step. | setup.py:435 |
| setup | Save both folders on the cloud computer, or both on this computer. A split between the two is refused. | refuse | The reason sentence names the next step. | setup.py:476 |
| setup | The Unpaywall email is not usable. Skip it, or give an email address. The value is not repeated here. | refuse | The reason sentence names the next step. | setup.py:487 |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py:495 |
| setup | Say whether the Consensus plan is Free or Pro before the key is saved. Teams, Deep, and Enterprise use the same paid flag as Pro. Nothing was written. | refuse | The reason sentence names the next step. | setup.py:497 |
| setup | Skip is not saved until the warning is confirmed. Nothing was written. | refuse | The reason sentence names the next step. | setup.py:528 |
| setup | This computer has no cloud workspace. Name both app_path and kb1_path to save on this computer. Documents is not used, and it is not labelled as the cloud computer. | refuse | The reason sentence names the next step. | setup.py:448 |
| setup | Give both app_path and kb1_path, or omit both to use the cloud computer. | refuse | The reason sentence names the next step. | setup.py:464 |
| repo-not-save | The code checkout is not a student save. | refuse | The reason sentence names the next step. | setup.py:470 |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py:473 |
| setup | Could not create the folders. Allow file access, then call essay.setup again. | refuse | The reason sentence names the next step. | setup.py:643 |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py:666 |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py:677 |
| setup | (built at the door) | refuse | The reason sentence names the next step. | setup.py:698 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | shelf.py:71 |
| pack | pack must be an object | refuse | Send the pack as an object. | shelf.py:80 |
| shelf | pack_id has characters the local shelf will not store | refuse | Use a pack id this shelf can store. | shelf.py:82 |
| shelf | topic does not match the pack title. Confirm one title, not two. | refuse | The reason sentence names the next step. | shelf.py:88 |
| shelf | Shelf stores a pack only after Word confirm for that same pack. | refuse | The reason sentence names the next step. | shelf.py:97 |
| confirm | The pack or its gathered files changed after Word. Validate and write Word again before the shelf. | refuse | The reason sentence names the next step. | shelf.py:102 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | shelf.py:166 |
| shelf | pack_id is not a local shelf id | refuse | Choose a pack id from this shelf. | shelf.py:176 |
| shelf | no shelf pack for this essay id | refuse | The reason sentence names the next step. | shelf.py:179 |
| shelf | no shelf pack for this essay id | refuse | The reason sentence names the next step. | shelf.py:182 |
| cross-essay | that shelf record is not this essay | refuse | The reason sentence names the next step. | shelf.py:184 |
| engagement | (built at the door) | refuse | The reason sentence names the next step. | specialists/eqr.py:968 |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/eqr.py:964 |
| confirm-card | A typed reply does not save this step. Pick the card in the draft reply. | refuse | The reason sentence names the next step. | specialists/grok_bot.py:121 |
| basics-pass | (built at the door) | refuse | The reason sentence names the next step. | specialists/grok_bot.py:580 |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/grok_bot.py:602 |
| confirm-card | Not yet leaves this step unsaved. | refuse | The reason sentence names the next step. | specialists/grok_bot.py:114 |
| word-band | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py:440 |
| assignment-gate | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py:885 |
| draft | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py:653 |
| draft | (built at the door) | refuse | The reason sentence names the next step. | specialists/writer.py:663 |
| guidance-only | (built at the door) | refuse | The reason sentence names the next step. | stage_body.py:40 |
| stage | Write what changed, or that the plan still holds, and which gathered source shows it. | refuse | The reason sentence names the next step. | stage_body.py:553 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_body.py:379 |
| master | (built at the door) | refuse | The reason sentence names the next step. | stage_body.py:580 |
| eqr | (built at the door) | refuse | The reason sentence names the next step. | stage_body.py:605 |
| draft | (built at the door) | refuse | The reason sentence names the next step. | stage_body.py:485 |
| word-band | This first draft is not inside the brief's word band. Change the draft so it fits the brief, then save again. | refuse | The reason sentence names the next step. | stage_body.py:511 |
| pointer | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:113 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:599 |
| stage | The last stage is already saved. This tool does not submit. | refuse | The reason sentence names the next step. | stage_hold.py:785 |
| stage | Save the plan note first. The first draft waits until that save. | refuse | The reason sentence names the next step. | stage_hold.py:800 |
| stage | Save the plan again before the first draft. The earlier lock changed. | refuse | The reason sentence names the next step. | stage_hold.py:805 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:810 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:815 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:797 |
| word | (built at the door) | refuse | The reason sentence names the next step. | stage_hold.py:782 |
| misses | (built at the door) | refuse | The reason sentence names the next step. | stage_landing.py:268 |
| lock-choice | The inherited lock is empty. Revise instead. | refuse | The reason sentence names the next step. | stage_landing.py:360 |
| house-jargon | That note uses an internal label. Say it in plain words. | refuse | The reason sentence names the next step. | stage_landing.py:293 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py:264 |
| stage | Send a stage from 1 to 10, including 4a and 4b. | refuse | The reason sentence names the next step. | stage_track.py:293 |
| confirm-card | This step moves on when the draft is stored. There is no save-card between this step and the next. | refuse | The reason sentence names the next step. | stage_track.py:373 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py:214 |
| turn | (built at the door) | refuse | The reason sentence names the next step. | stage_track.py:237 |
| stage | Send the look as plain text. | refuse | The reason sentence names the next step. | stage_track.py:302 |
| state | (built at the door) | refuse | The reason sentence names the next step. | state.py:124 |
| stage | (built at the door) | refuse | The reason sentence names the next step. | state.py:165 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | validate.py:945 |
| pack | pack must be an object | refuse | Send the pack as an object. | validate.py:954 |
| footer | (built at the door) | refuse | The reason sentence names the next step. | word.py:104 |
| essay-id | (built at the door) | refuse | The reason sentence names the next step. | word.py:751 |
| pack | pack must be an object | refuse | Send the pack as an object. | word.py:760 |
| word-only | Word .docx is the only output. PDF is refused. | refuse | Send a Word .docx file. | word.py:775 |
| stage | Word stage is 6 for the first Word file, 7 after the questions and edits, or 9 for the references confirm. | refuse | The reason sentence names the next step. | word.py:782 |
| validate | This pack did not pass validation. Word was not written. | refuse | Fix the pack, then ask me to write the Word file again. | word.py:912 |
| validate | Validate this pack with draft, then confirm, before Word confirm. A changed pack needs both steps again. | refuse | The reason sentence names the next step. | word.py:921 |
| confirm | Gathered files changed after validation. Fresh validate draft required. | refuse | Ask me to validate again, then save. | word.py:929 |
| footer | (built at the door) | refuse | The reason sentence names the next step. | word.py:102 |
| stage | Ask, then edit from the answers, before this Word save. | refuse | The reason sentence names the next step. | word.py:791 |
| footer | The page number is missing. An empty footer is refused. | refuse | Add the page number, then save the Word file again. | word.py:994 |
| eqr | (built at the door) | refuse | The reason sentence names the next step. | word.py:944 |
| eqr | (built at the door) | refuse | The reason sentence names the next step. | word.py:963 |
| empty-references | The References section has no entries. Add reference lines before this step can close. | refuse | The reason sentence names the next step. | word_references.py:490 |
| references-cites | (built at the door) | refuse | The reason sentence names the next step. | word_references.py:516 |
| smaller-questions | A missing or refused smaller-question list leaves the confirmed question. | fallback | The gather continues with the confirmed question. | tests/test_source_floor.py |
| word-title-spare | A refused Word title becomes the spare title Essay. | fallback | The Word file still uses the spare title. | tests/test_model_contract.py |
| pdf-gap-unwritten | A gap note that cannot be saved stays in memory for this read. | fallback | The paper is still opened. The gap file is unchanged. | tests/test_refusals.py |
| pointer-damaged | A stage pointer that is not JSON is not rewritten. | fallback | Ask me to show this step again before saving. | tests/test_refusals.py |
| encourage-unwritten | An encourage note that cannot be saved is not stored. | fallback | The plan or the answer is unchanged on disk. Ask again. | tests/test_refusals.py |
