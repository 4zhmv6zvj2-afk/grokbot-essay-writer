# Essay workflow

One module id per assignment. A normal semester has about four essays; you can have more. Each sits in its own folder. Nothing in `MOD1004AA` is readable as if it belonged to `MOD1011AA`.

**Templates:** `docs/templates/review.md` (person review checklist) and `docs/templates/bot.md` (Essay Bot, switched on). The bot uses the same MCP entry as Cursor. The share file is `docs/templates/essay-bot.share.json`. There is no separate bot door in `essay.health`.

**Workplace:** Essay Bot is the chat. Cursor is the default place for file work on this computer; Grok Build is an alternate chosen at setup. Save on this computer, or on a folder you name on this computer. A path you did not name is not a save target. Documents is not used as a stand-in for this computer.

Cursor and Essay Bot share the same doors. The doors live once in the essay-writer package (`essay_writer.shells`). Essay Bot says the replies. A door change is made once in that package.

```
Essay-writer/<module>/                  assignment file, shared by every sequence
Essay-writer/<module>/sequences/<n>/   confirm state, local shelf, Word output
uploads/<module>/                      Cursor-readable originals, shared by the module
```

Example ids: `MOD1011AA`, `MOD1008AA`, `RPT1008AA`, `MOD1004AA`. An id matches the module code (`MOD1004AA`). A sequence id is that code plus a number, such as `MOD1011AA-5`.

## Sequence

Opening choice, before the writing doors: new (`essay.sequence.new`), continue, roll-forward (`essay.projects` with view `roll-forward` and the module), archive, unarchive, or delete (`essay.projects`). Continue names the last-saved sequence id on each row (`essay_id`, such as MOD1011AA-5). Roll-forward asks which existing sequence to copy; `essay.sequence.new` then starts last+1 on that module. Archive hides the module until it is named and unarchived. The writing doors then take that sequence id. Uploads and the assignment stay on the module.

The standing chat heading for the active essay is the sequence id alone (`heading` on the Essay Bot reply), such as `MOD1004AA-3`. It is posted when the essay opens, after each stage Confirm, and when the active essay changes.

Delete is three steps. Ask which module. Then ask where: essay workspace only (`where` `grokbot`), copies on the student's computer only (`where` `local`), or both (`where` `both`). Then draft, show the exact list, and remove it only after the person picks Confirm on that card. A typed yes does not remove anything. `grokbot`, or leaving `where` off, removes sequences, uploads, the assignment, and local subject notes in this essay workspace and leaves Word and zip copies on the student's computer. Say `leave_behind_notice` and show `computer_list` (empty when workspace-only). A whole-module `where` `local` needs `localPaths`, the full path of each Word file or zip the student names. `where` `both`, for one sequence or the whole module, uses Word and zip paths already stored for the sequence or across the sequences in the module, and the default Mac handoff names, when those files are already there. Ask for a path only when none are there. A path the caller names is the list. For one sequence, `where` `local` is refused. Those copies are removed only when the confirm says the files on the student's computer will be removed. This tool does not search the computer for them and does not list Documents. If a path is not visible here — including on an unmounted Mac folder — it stays and the draft says so.

1. `essay.health` — alive, and the doors and packs on disk. The pack stage is the latest sequence when one exists. `version` names the release, and `essay-writer --check-update` compares it with the newest GitHub release.
2. `essay.originals` — list or read this essay's uploads and assignment.
3. `essay.research.summary` or `essay.research.full` — draft, then the same arguments with confirm.
4. `essay.pack.validate` — draft, then confirm, for that pack. A successful confirm stores a snapshot under `Essay-writer/<module>/backups/<essay_id>/`. A successful stage save stores the same kind of snapshot. `essay.pack.restore` puts one snapshot back. Draft writes nothing. A missing or damaged snapshot is refused, and review text is copied from that snapshot only.
5. `essay.pack.render_word` — draft writes nothing; confirm writes `.docx` only after that pack's validation is confirmed.
6. `essay.revise` — feedback on the same essay. No new Word file.
7. `essay.shelf.put` / `essay.shelf.get` — a saved copy after Word confirm, local to that essay id.

Full research also needs `clarify_context`, and may name at most two local packs from `essay.health`. See `docs/memo-how-it-works-note.md` for the live input shape, noted versus open, and why a clarify answer is not evidence.

## Confirm

`confirmPhase` is `draft` or `confirm`. Omit it and the write is refused. Confirm with arguments that were not drafted is refused. If a gathered file or an earlier confirm changes after the draft, confirm is refused until a fresh draft.

While Cursor CLI or Grok Build is doing the file work, and on any other file-work path, say a short start line when that work starts. Say a mid status line only when that path signals a phase, using the mid-status sheet, and do not invent a phase. If that path stays silent for about five minutes, say one calm line that work is still going, then wait for a status signal or until the step is ready. Do not repeat that line on a fixed clock. A short job does not get that five-minute line. This is for every file-work stage on the stage 1 to 10 line, not only research. When the step is ready, say so and give the next ask. Name the Confirm card only when that stage's card is in the latest door result and the artifact is ready to lock. Do not warn about a later stage's card while file work is still running. Use the status sentences on the reply. Say them in that same turn. Do not wait for another poke. A logging notification is not the chat line. Say a short start line when the reply includes status for a started job. A status line does not save the stage and does not replace the Confirm card. Do not add a watch link. If no file-work path is running, do not say that work is still going. When file work stops early or the CLI exits with an error, say the short exit line from the status sheet. Do not go quiet. When a tip names the standard, use the opening already printed for this assignment. A diary with a table uses How to score high and the printed top column. An essay or a report with a scheme uses what the mark scheme scores. If there is no scheme, use the assignment and the ask. Never invent a band. Do not rename a diary column to the words mark scheme. The templates are `docs/templates/mid-status.md`.

One Confirm saves one stage. Press Confirm for Stage N, sent with `cardAction` and `cardDigest` from that stage's waiting draft, saves that stage only. It does not save the next stage. The next stage stays unsaved until its own Confirm. Before any card is shown, follow the pointer. If this stage is already saved, or the current stage is later, do not show that card. Say the tool's next and the card the latest tool result returned for the current stage. Essay Bot may only show the Confirm card the door returned. It does not pick the next stage itself. Post a Confirm only when its cardDigest matches the door's latest result for the current open sequence. Refuse a closed pack, a wrong sequence, and inventing the next stage. When a sequence opens, post only the Confirm card in that door result. That card's sequence id is the sequence that opened. Do not post a Confirm from another sequence. A skip after the stage 7 questions is refused, and the questions are asked again in that reply. All fine, no changes, or none opens the Confirm card and leaves the tracking note on Status draft until that card is pressed. A finished answer, including all fine, is one tool call whose result is spoken in that same turn.

## Word

`.docx` only. Draft writes nothing; confirm writes the file only after validation of the same pack is confirmed.

A changed Word upload leaves the parent sequence in place and rolls forward onto the next sequence. It does not replace that draft. An unchanged Word file stays in `unassigned/` and nothing is written. A Word file with no saved research trail lands on user feedback; research starts only when the user asks, and the first draft is treated as done.

The Word draft preview and the `.docx` use the same words: cover lines, section headings, body text, figure and table source lines, and the reference list. There is not a second story in the preview.

The cover prints a programme row only when the brief asks for it. It prints the module or sequence id and the counted words when those are real fields. A real stored title is the first visible line. A placeholder title is left off, and the question is not turned into a title. The conclusion stays noted or open on the pack. Chat says that in one sentence when Word is written, and neither sentence is printed on the cover. Body text is Arial 12, 1.5 line spacing, justified, with a page number where the assignment record says (the lower right when the assignment says lower or bottom right) and Heading 1 for top-level sections. No student name unless that record requires it. When the record requires a registration number, ask once, store it on the sequence, and print that number. Do not invent a registration number. An empty required number is refused. The draft is model-assisted; the student owns what they submit and must follow their school's rules. Stages 6, 7, 9, and the stage 10 final all use that same cover and footer.

Word count follows that module’s assignment: the band and whether in-text Harvard citations count come from the assignment for this essay id (with any `word_rules` on the pack overriding). A count outside the band blocks Word until the host sets `word_count_acknowledged` on the pack, and the host sets `word_count_acknowledged` only after the student accepts the stated length. The door never sets that flag itself.

Referencing: `docs/referencing-harvard.md`.

## Research packs (4a and 4b)

Stage 4a confirm delivers `annotation.docx` in the chat. The citation line is Harvard Referencing, then a few full sentences a student can read aloud. `download-list.docx` is Word and lists **leftovers only** (sources not already in the papers zip; not a repeat of `annotation.docx`). The confirm reply also includes a links card with a title and a URL for each leftover. A saved PDF is not on that list or that card. The 4a zip holds real PDFs only. When you offer the move into 4b, include **option C: Download leftovers first**. The library guide is for after the person fetches those files; file work does not fetch them for the person. Before that step is saved, compare the download list with PDF files on disk and in Documents, not only the papers zip. Open only a path already named on the download list, the annotation, or a known project file, plus `Essay-writer/<module>/`, `uploads/<module>/`, the code checkout, and local subject notes for this module. Do not search the home folder, whole Documents, or whole Volumes. Do not invent a student folder path. The code checkout is not a student save. When a listed source now has a PDF, refresh `annotation.docx` and the papers zip, report that comparison, then ask to save. The citation year is the year in the PDF page title or header, not the file's modified time. An abstract-only source stays on the download list until a PDF of that source is opened. A PDF larger than 20MB is read in parts on this machine so each part stays readable; a part that cannot be read is recorded for the later citation pass. PDF bytes stay on this machine. Stage 4b confirm writes one Word file per paper in `critical-reviews.zip`. Each critical-review note is opened from disk, and the critical note names grok-4.7. A Documents copy of a Word file or zip has the Mac quarantine mark and the provenance mark cleared before handoff when those marks are present.

If essay-writer MCP tools are unavailable, stop. Do not hand-write `annotation.docx`, `download-list.docx`, or `papers.zip`.

Student chat never shows `~/…` or a drive path the student did not name. Name `Documents/…` only when that folder is already on this computer. When it is not, the file stays in this chat and on this sequence. Do not invent a Documents path.

Grok Build and Cursor write the same bytes. Draft writes none of these files. A quotation in an annotation or a paper note has to be an exact span of the gathered text. The internal step name is not written in those files.

## Photos

A PNG, JPEG, GIF, or WEBP file in `unassigned/` is read in the app. The draft shows the words from the photo. Confirm files the photo and those words under `uploads/<module>/` for every sequence. `essay.originals` reads those words. An empty or damaged photo is refused and nothing is filed.

Cursor and Grok Build both use `essay_writer.vision.prepare_photo` (`essay_writer.build_office.photo_vision`).

## Research search, gates, and the reviewer

`essay.dig` is draft then confirm. Confirm writes `dig-card.json` and `dig-card.md` on the sequence. OpenAlex runs without a key. Keyless calls share a small daily budget with everyone on the network address and can be rate-limited; an `OPENALEX_API_KEY` value raises the budget. Unpaywall runs only when an email is already stored. A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. `ESSAY_WRITER_CONSENSUS=0` turns Consensus off. `ESSAY_WRITER_CONSENSUS=1` turns it on when a key is present. The health report says which it is. Cursor and Grok Build both call `essay_writer.dig.essay_dig`, so the card bytes are the same. invent-forbid: a paper appears on the card only when the look-up returned it. A look-up that is refused (a key, a plan limit, a budget, or the network) keeps its status and reason on the card and in `lookup_note`; it is not reported as no papers found.

Ordinary first-run collects the Consensus key, the plan, the Unpaywall email, and the OpenAlex key on the secret card. The same `essay.setup` arguments are what Cursor and Grok Build store. Neither file host shows a second card. Do not ask an ordinary user to edit a `.env` file. A local environment value for `CONSENSUS_API_KEY`, `ESSAY_WRITER_UNPAYWALL_EMAIL`, `ESSAY_WRITER_CONSENSUS_PAID`, or `OPENALEX_API_KEY` is specialist local development only.

The Consensus key finds papers for the research step. The help-center wording is that the API programmatically searches academic research and retrieves relevant papers: https://help.consensus.app/en/articles/16516328-the-consensus-api . The key is created from the profile icon, then API & MCP Dashboard, then Keys and Clients, then New key. The same path is on https://docs.consensus.app/api-plans-and-access . The dashboard is https://consensus.app/api-mcp . Free stores `ESSAY_WRITER_CONSENSUS_PAID` as `0`. Pro stores it as `1`. Teams, Deep, and Enterprise use `1`. The call limits in that plans page are the only ones named: Free 30 included calls a month and a maximum of 30; Pro 500 included and a maximum of 1,000 with additional usage; 20 papers per request on Free and 300 on Pro; pagination past the first page and full-text excerpts on Pro only; 1 request per second on both.

The Unpaywall email is for free-PDF lookup only. Requests include `?email=YOUR_EMAIL`, with a published limit of 100,000 calls a day: https://unpaywall.org/products/api . That email does not change OpenAlex limits. OpenAlex ignores mailto, and the polite pool was retired in February 2026: https://help.openalex.org/api/deprecations/ . Do not invent an email address. Unpaywall's privacy page is not a promise that they never email.

Skipping the Consensus key, the Unpaywall email, the OpenAlex key, or any of them needs a warning confirm. Consensus is not used without the key. Unpaywall free PDF lookup does not run without the email. OpenAlex still runs without a key, on that shared daily budget, and a free key raises it. The key is copied from Settings → API key after an account at openalex.org: https://help.openalex.org/api/authentication/ . Pricing is https://help.openalex.org/access/pricing/ . `GET /v2/search` on Unpaywall was retired on 18 September 2026 and returns 410. Free-PDF lookup uses the DOI endpoint `https://api.unpaywall.org/v2/{doi}?email=` and OpenAlex `best_oa_location` (https://api.openalex.org/works).

`essay.gates` is read-only. It runs mechanical gates 1–11 and blocks an unquoted exact sentence copied from a gathered file. It does not record a review.

EQR is the reviewer (`essay-writer --reviewer`, tool `essay.review`). The writer server does not include that tool. Stage 6 needs an EQR pass before the first Word file. Stage 6 answers whether the draft answers the assignment question. It does not check format, rewrite the draft, or fill gaps. The writer owns format and citations. When the mark scheme table has a row for argument, evidence, or critical thinking, the review marks that row at the top band and does not mark format or citations. Stage 6 does not mark those rows. Stage 9 checks the same requirement list on the opened Word file. The constitution is not that check. Stage 9 needs an EQR pass on the current submit Word file before the final Word file, and that pass clears only after citations are on that file. A pass recorded with no submit file, or against an older file, does not clear. Pass `stage` `6` or `9` on `essay.pack.render_word` for those paths. The writer does not mark its own essay passed. The findings note may name a leftover chatbot habit, an overconfident claim, or a real opened paper stretched past what it found. Naming that line does not fail the review and does not block the Word file. Invented sources still fail on the existing source check.

## Brief-fit notes

`essay.pack.validate` and `essay.pack.render_word` return `notes` as well as `blockers`. When the brief prints section weights, names a supply chain or a case, or names a specialist source class, the notes name a draft that misses one: `mark-fit-section`, `mark-fit-heading`, `mark-fit-chain`, `mark-fit-case`, `mark-fit-source`. A note never blocks a save, and no criterion, weight, or band is invented. Before the word-band stretch, a brief-weighted section the draft lacks may be lifted from gathered claims; each lifted sentence keeps its author-year, and a section with no gathered support stays out.

## Body cites, short cites, and a student outline

A body cite lands only when the gathered text supports the student's own sentence: the same idea, not the shared topic. A paper the student did not ask for is asked about before it lands. A cite the student rejected stays out, and it keeps staying out: a snapshot restore, a draft overwrite, or a later Word save does not put it back. When a swap does not fit the sentence, the reply offers the gap and asks what goes there instead of restoring the rejected set. The record lives at `Essay-writer/<module>/sequences/<n>/cite-fit.json`, and a rejected family name is read on every later save.

A student can ask for the cites to be shortened to about one or two sentences. That ask is kept at `Essay-writer/<module>/sequences/<n>/short-cites.json`, and each later save cuts a cited point to that length. A sentence is cut only when every paper it cites is still cited in the sentences that stay, so no paper leaves the reference list. Quoted text is not cut, and the reply says how many long stretches were cut.

When the student puts an outline or their own prose in `Essay-writer/<module>/sequences/<n>/student-outline/` (or at `student-outline.md` on the sequence), that outline is the structure for stages 3 to 6. Its headings keep the student's order, a section the outline does not name is reported rather than dropped, no section is lifted from the brief, and the body is not stretched from gathered files. Each woven cite stays to one or two sentences. With no student outline the earlier path is unchanged.

## References confirm look-up

At the references confirm (stage 9, after the reviewer pass), one look-up runs when the brief names a specialist source class and the gathered files do not name one. A hit is reported with its title, year, and DOI. A miss says the look-up found none. Nothing is added to the sources or the reference list, so no source or reference line is invented. One attempt is kept per pack, and a preview does not call. Finish does not run that look-up again. The finished Word file is the stage 10 file.

## Stage LLM

<!-- generated:stage_llm -->

## Stage rules and tracking

Each stage's guidance is applied as rules. The rules are that stage's checklist, loaded from `essay_writer.stage_llm.stage_settings` (`rules`). Cursor tool text and Grok Build `stage_launch` both use that field. Follow every line. The rules include the internal Basics checklist walk. For stages 2, 3, 4a, 4b, and 5 they also include the post-research plan revisit. `stage_launch` puts that same text on grok `--rules`. The Cursor launch does not put that text on an agent flag.

`essay.stage` writes the tracking note at `Essay-writer/<module>/sequences/<n>/tracking/<stage>.md`. The note is that stage's guidance. Draft does not move the stage. Confirm saves the final look in that file, then `tracking/stage.json` moves to the next stage. look is the student's own sentence for this stage; omit it and no final look is written. Stage 10 does not submit. A copied sequence starts again at stage 1. Stages 1 to 3 are written again. Research and saved papers stay. The previous final is parked under reference/.

## First draft

The first draft is authored from the stage 4b critical-review markdowns. One markdown per paper. Pass `critical_reviews` on the pack. A source paper is re-opened only with `reopen` when that markdown does not cover the gap. A quotation has to be an exact span of the markdown, or of the re-opened passage. invent-forbid and Confirm stay in force.

Stage 5 chat stays quiet. The content check is part of writing that draft: keep the specific finding, drop importance the source does not state, and name the source. There is no rewrite before the student sees the draft. A draft that stores the final look starts stage 6, and the progress line says the first draft is ready. After the reviewer records a pass against that intact saved text, the first-draft Word file is written from it. The first read includes a short list the student uses for their own edits. There is no Confirm card between them. The person sees the finished first draft after the Word save. The Word preview and revise stay quiet unless the draft is blocked. When the 4b markdowns fill the stage 5 window, trim only the repeated model line, then split into whole-paper groups, then reopen with an exact passage. Do not cut a note off in silence. Keep revising while a clear path remains. Tell the person only when those paths are exhausted.

## Out of this door

Slack, a friend-bot template, paid resolvers, and PDF as the output.

Free look-ups (Crossref, OpenAlex, doi.org, Unpaywall) may fill blank `doi`, `container`, `volume`,
`issue`, `pages`, `publisher`, `place`, `url`, or `accessed` on a source already gathered for this
essay id when the gathered text contains the title or a DOI and the record matches. Author, year, and
quotations still come from the file only. A miss leaves the field blank and is recorded in
`resolvers_called`. Confirm stores the research pack for later steps.
