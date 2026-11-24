# Changelog

## Unreleased

- Captured live-test text is replaced with a synthetic essay of the same shape. A tree scan fails if that module code or that fishery opening returns.
- Cleanup deletes a run directory only when this script created it. The directory must carry the marker written at launch, and it must be `/tmp/essay-verify-*` or the directory passed with `--run-dir`. A shared parent, a pre-existing directory, and a missing marker stay in place.
- Cleanup stops the server process id stored at launch when that process is still `essay_writer`. The process list includes session leaders and the full command. It does not read `/proc`.
- The verify script installs from `requirements-runtime.txt` with `--require-hashes`. Evidence defaults to `/tmp/essay-verify-evidence`, and `ESSAY_WRITER_EVIDENCE` still overrides that path. The dependency folder is checked even when it does not exist yet.
- Doctor fails unless `essay.health` is alive and the doors `essay.dig`, `essay.health`, `essay.research.full`, and `essay.pack.render_word` are mounted. The expected version is the installed package version.
- Research sources keep the id the product stored or minted. The verify script does not rewrite them to `src-n`.
- CI compiles the verify script and Ruff checks it.
- A stage 6 pass is recorded after the first-draft Word file is written from the saved draft. A failed write returns that error and leaves the pass unrecorded. A later reading of the pass requires the same saved draft text.
- A review counts when the markdown already has the structural marker and names the paper. A file that only names the paper does not count. A missing review is the citation line only, and a supplied note is saved as supplied. Neither gains the marker, and a student Word file does not gain it.
- Stripping a citation reports each span it removed. A sentence that loses its subject or its name at that span is not a finished first draft, including when stage 5 strips that cite. The draft is refused, not stored, and no Word file is written. A readable phrase such as a can-do attitude still passes.
- A short first draft stores only the student's text and gathered source text. When gathered claims cannot reach the word band, the draft is refused on the existing shortfall path.
- Student review text, findings text, and the comments Word file drop the model-metadata line and a line that is only the structural marker. A quoted model name stays. The stored markdown that the critical-note check reads keeps the marker.
- The Word cover drops the opening paragraph once. A short section heading stays. A heading longer than 255 characters is that opening paragraph. The document title uses the short title on the first-draft Word file, then the assessment id, then the file name without .docx. A pack title stays on the cover and is not that property. The opening is never the title. The title is at most 255 characters.
- Italic titles are checked on the Word file stage 10 writes, including a review subtitle. A source the check is given and cannot line up is recorded as a miss. A gathered source the finished file does not cite and does not list is not that miss.
- The remaining stage next sentences from the body builder and the stage runner are stored by the stage next module. A helper that only forwarded a sentence is gone.
- One draft ask loads the brief once. The basics opening in that ask reuses the same load.
- A stage 10 build that cannot see the Mac folder remembers that reason. A later confirm of the same build still says the folder is not on this computer.
- The sdist ships `.githooks/pre-push`, so the local push hook is in the extracted tree.
- The sdist ships `.cursor/skills/**`, so the verify-skill checks pass from the extracted tarball.
- A printed source range uses its low end. "Up to N sources" is a cap, not a floor. A stated source count beside a word count stays the floor.
- A silent brief cites at least ceil(words / 1000 * 8) works and at most 12 per 1,000 words. A stated count above that cap raises the cap. The rate is not added to the stated count.
- One work counts once across a DOI record and a no-DOI record. Two works that share a title and a year and name different authors stay two. Uploaded files do not meet the official floor. The gather reports both counts.
- When the OpenAlex page budget stops a gather, the note names the found count, the floor, and that budget, and it either saves the OpenAlex cursor or says that no more official pages are available.
- An empty gather does not write a sourced essay when no source record and no citation entry exist, including when dig-card.json is absent. Stage 4b, stage 5, and stage 10 wait.
- The shell asks once before the gather and passes up to three smaller questions. The gather reads that list once and does not ask again.
- A kept PDF whose hit has no DOI still keeps the author, year, and title the look-up returned. The match uses the URL or the locator, or the title with the author. A title alone does not match. A DOI on that hit is kept too.
- A source id is stored on first sight. A later DOI, author, or title does not mint a new one. A very long title is hashed so the filename stays short. A supplied id is kept only when its shape is safe.
- Two works that share a title stay two entries, two notes, and two source records. A citation matches a source id exactly, or the stored short form when the id is absent. A stored conflict is named, and that citation is not used.
- The download shortlist keeps the works that best fit the saved plan. A tie keeps the earlier work. A draft plan is not a saved plan, so nothing is downloaded until the plan is saved. The essay question still comes first when both are missing.
- A gather with no confirmed question asks for the question and does not search.
- A gathered sentence keeps the citation-list short form when that source is listed. When it is not, the short form comes from the stored author and year, including the stored look-up record. A source with no stored author or year is not appended.
- A remembered author, year, title, or DOI is kept only when it matches the claimed value. A different claimed value refuses the source.
- A first draft that misses the named parts is refused for those parts before the word band is checked. A note that already names those parts is not refused for the word band.

## 0.9.18 — 2026-11-23

- Each stored work has one unique source id that does not change when the list is rebuilt. The opened file, the research note, and the citation-list entry share that id. Matching and look-up use that id, not a short in-text form.
- The finished essay cites at least the locked floor and at most the locked cap, and only relevant works.
- After research, the download step first drops works that are not relevant, then selects from the rest the ones that fit the plan, and only that shortlist is the download set, which must not exceed the essay cite maximum of 12 distinct works per 1,000 words.
- If the essay question is not confirmed, or the plan is not saved, the download step does not fetch the full list of gathered works. The student goes back to confirm the essay question, or to finish the plan when the question is already confirmed. When both are missing, the essay question comes first. Nothing is downloaded, and the student is not given that full list to fetch by hand. The gathered list can stay on file. When both are present, the shorter download set is unchanged.
- A saved Harvard reference keeps the journal or the full work title italic, including a long author list, a review-style title, and a management-plan title.
- A first review refusal does not end the job: the writer can amend and be reviewed again at each review gate on the path, and the last step stays closed while that review is still open. After a fair review pass, the last step writes a new final Word file.
- The citation list keeps the print fields the Harvard line was made from.
- Cursor and Grok Build follow the same rules. Build covered.
- 0.9.18 ships the wheel, the sdist, and `SHA256SUMS`, and does not include Sigstore bundles or build-provenance attestations.

## 0.9.17 — 2026-11-23

- A stated source count is the floor. When the assignment is silent, the floor is eight sources for each 1,000 words of the stated length, rounded up. After the essay question is confirmed, the shell asks once before the gather and passes up to three smaller questions on the same tool field, `smallerQuestions`, before the first catalog call. A missing or unusable reply searches only the confirmed question. Each question keeps its own result. OpenAlex follows its next-page cursor, and Consensus turns the page only when the stored plan allows it. Unpaywall stays a DOI fill. Crossref stays an exact-title fill. The citation list is still written at the end of stage 4b. A further official page blocks that list and the draft while the floor is unmet. An honest short gather writes the list and names the found count. An empty gather does not write a sourced essay. A refused lookup leaves the gather unfinished. Cursor and Grok Build call the same gather, the same smaller questions, the same citation list, and the same pack gate. Build covered.
- 0.9.17 ships the wheel, the sdist, and `SHA256SUMS`, and does not include Sigstore bundles or build-provenance attestations.

## 0.9.16 — 2026-11-23

- Stage 10 treats an in-text citation as covered when it matches a short form stored on the citation list and that entry already has its Harvard line, including when the line names many authors and the year sits far from the first surname. A citation that is not on the list is still refused. A stored short form with no reference line is still refused. A failed last step is not stored, does not write a final Word file, and does not replace a final Word file or a first-draft Word file that is already saved. An author name that differs only by a hyphen character still matches. The findings Word file a student opens uses the heading Overall judgement. Cursor and Grok Build follow the same close and the same student-facing wording. Build covered.
- A research note whose first line leaves out the year stays usable when the stored source id, DOI, author, year, and title already match across the opened source, the research note, and the citation list, including when the DOI contains a four-digit number such as 1371. The research note keeps its own copy of those details, separate from the citation list, and the opened source keeps its own copy. A detail still missing on the note is a gap, filled from the opened source when that source already has it, and is not read from the note heading. A newer uploaded file refreshes the opened source, the research note, and the citation list together. A difference in the note heading is not a disagreement. When those stored details disagree, that conflict is named and the citation is not used. The opened file, the note, and the list entry share one source id. An in-text citation uses the short form stored on the list. A citation that is not on the list is still left out. A review is not refused because the draft contains e.g. or the fragment g. A full sentence copied from an opened paper without quotation marks is still refused, and that refusal does not write the first-draft Word file. Cursor and Grok Build follow these same rules. Build covered.
- The workflow and the composed instructions say the note a student opens does not name a model. The table of which model each stage uses stays.
- A source review a student opens does not name a model. The Word file and the saved review note leave that line out. Annotation, the download list, the first-draft Word file, the final Word file, and the lines a student reads stay free of a model name and of internal labels.
- Stage 5 does not save a first draft as finished, and does not write the first-draft Word file, when citation handling leaves a sentence with the author name missing. An intact saved draft is unchanged. Official look-up author, year, title, and DOI still stay when a PDF is kept or only an abstract is saved.
- Stage 10 treats one author name as the same person when the only difference is the hyphen, and it writes the final Word file. A reference line that is really missing is still refused, and a failed last step does not replace a final Word file that is already saved.
- Cursor and Grok Build follow these same rules. Build covered.
- After the reviewer records a pass against an intact saved first draft, the first-draft Word file is written from that saved text. The writer cannot record that pass. A broken or unsaved draft does not produce the file, and the file is not written before the pass is recorded. Cursor and Grok Build follow this same path. Build covered.
- When a look-up returns an author, a year, a title, or a DOI and a full PDF is kept, those details stay on the source used for the draft. A detail the look-up did not return stays blank. An author is not invented from the PDF. If a citation check removes a name and year and the sentence is no longer readable, that text is not saved as the finished first draft, the step does not move on, and the word count is not treated as a finished draft. A first-draft Word file is written only from intact saved text, and only after the independent review is clear. The writer does not mark that review clear.
- When a look-up returns an author, a year, a title, or a DOI and only an abstract is saved, those details stay on the source. A detail the look-up did not return stays blank. The saved abstract prints a kept name and year. A later first draft can cite that source when the author and year were kept. A first draft below the brief's minimum is still not saved.
- A saved look-up also keeps the other bibliographic fields the official OpenAlex, Consensus, or Unpaywall response already included, including when only an abstract is saved. A field that response did not include stays blank. A file is fetched only from an official OpenAlex or Unpaywall PDF or open-access URL, and it is kept only when it is a real PDF. OpenAlex requests use `per_page` and do not send `mailto`. A contact email stays required for Unpaywall only.
- The internal referencing note says Plymouth Cite Them Right is Harvard referencing, in `docs/referencing-harvard.md` and the agent prompt generated from it. A missing Plymouth switch is not a product gap. The wording stays internal: no student chat or screen copy changes, and the Word file does not announce the referencing method.
- When the brief states a word band, stage 5 writes the first draft inside that band. A first draft below the minimum is not saved and is not shown as the finished first draft.
- The Word document title uses the short title already stored on the first-draft Word file; when that file has no short title, it uses the assessment id, or the file name without `.docx`. The title stays within Word's 255-character limit, and the opening paragraph is not used as the title, so a long opening paragraph no longer stops the final file from being written. Cursor and Grok Build share this title rule. Build covered.
- The Stage 10 final Word file has the short title as the cover line once, with the opening paragraph once underneath it. The opening no longer appears above the cover, and the essay wording is unchanged. Cursor and Grok Build share this body rule. Build covered.
- 0.9.16 ships the wheel, the sdist, and `SHA256SUMS`, and does not include Sigstore bundles or build-provenance attestations.

## 0.9.15 — 2026-11-22

- The stage "what happens next" sentence is stored by one module. The stage reply, hold, landing, and finish paths no longer assign it. Dig, shelf, setup, intake, review, and projects still write their own next sentence. The words a person reads are still cleaned the same way on every door.
- A draft reads the brief once for the Basics pass. The reply and the guidance inside that build reuse those three lines. A save that misses the pass reads the brief on its own, leaves the student's note unchanged, and stage 5 still skips that refusal.
- The finished Word file is built once on the stage 10 save, before that step is marked saved. Page-number and reference checks run on that one build, then those bytes are saved and copied to the final-named file and, when the student's folder is on this computer, to that folder. A failed check leaves the previous files and leaves stage 10 unsaved. Earlier Word steps may update the working file and do not write the final-named file. The references confirm stays the submit file the independent review reads, and the one specialist look-up stays there. A successful build is remembered whether or not the student's folder is on this computer. Cursor CLI and Grok Build follow this same path. Build covered.
- The setup ask is written once in the shared setup block. Both host setup prompts point at that block by token, and the front-office briefing and the first-run text carry the same words, so the student still has one setup door.
- Install, update, and attach read health the same way: one short "did health pass?" answer beside the official door. The install write stays on its own path and is never combined with that check.
- 0.9.15 ships the wheel, the sdist, and `SHA256SUMS`, and does not include Sigstore bundles or build-provenance attestations.

## 0.9.14 — 2026-11-18

- The release check now fails when `uv.lock` names a project version older than `pyproject.toml`. The suite reads the version from the package instead of hardcoding it, and a test fails when the README artifact names are stale.
- README, ARCHITECTURE, and the glossary describe the reviewer seat and the full stage order. The operator log lists the environment overrides.
- `opentelemetry-api` moves to 1.45.2 in `uv.lock`, which clears GHSA-mf5v-w3w3-f6cg, a denial of service in traceparent parsing. The lock also catches up to the project version its sdist entry had fallen behind.
- The update-lock change is formatted to the repository's ruff style. No behaviour changes.

## 0.9.13 — 2026-11-18

- Craft voice adds four short prose-habit rules (dashes, staged run-ups, decorated formatting, model knowledge guesses), written in-house from patterns in [blader/humanizer](https://github.com/blader/humanizer) (MIT). They ride the existing stage rules; there is no rewrite pass and no detector chase. `edit_recheck` also keeps names, numbers, dates, quotes, and citations unchanged.
- The releases-feed fallback reads the first Atom entry's alternate link and accepts only a plain `X.Y.Z` tag at the end of that path. A note that names another tag cannot choose the version, and a prerelease such as `v0.9.12-rc1` is ignored.
- `--update` downloads a release asset only over https from `github.com`, `release-assets.githubusercontent.com`, or `objects.githubusercontent.com`. It verifies SHA-256, not the Sigstore signature.
- Crossref, when no year or author was gathered, accepts a row only when exactly one returned row has that exact title. Several exact titles, or none, are a miss. A gathered year or author still checks every row and still asks for journal articles.
- `safe_url` connects to an address that passed validation and sends the original hostname as TLS SNI and the HTTP Host header. A trusted fake-IP address is still reached that way.
- `--update` takes a process-wide lock around the install. A second update while one is running reports that another update is already running, and the lock is released on every path.
- A dig refusal card tells the student that the host resolves to a non-public address and does not include the resolved address. The address, and the fake-IP hint, stay in the operator log. The hint may still name `198.18.0.0/15`.

## 0.9.12 — 2026-11-18

- `ESSAY_WRITER_TRUSTED_EGRESS` accepts only subnets of `198.18.0.0/15`. One invalid or out-of-range token disables the opt-in. A proxy that uses another range is not supported.
- OpenAlex applies the same gathered year and author check as Crossref, so a same-title row Crossref refused does not become the citation. The Crossref `select` list includes `article-number`. A resolver HTTP error is a miss.
- An environment-only Consensus key is no longer described as a search that will not run. The setup reply still reports only a key this call passed or stored.
- A failed `--update` or upload install says when the requirements or package step already changed the environment and was not rolled back. `SHA256SUMS` entries must be 64 hex digits, and two different hashes for one name refuse the update. `--update` checks SHA-256; the Sigstore signature stays a manual check.

## 0.9.11 — 2026-11-18

- `safe_url` accepts an operator-trusted egress range through `ESSAY_WRITER_TRUSTED_EGRESS` (environment or the setup secrets file), as a comma-separated list of CIDRs. A host whose proxy resolves every external name to a fake-IP range such as `198.18.0.0/15` can opt in; every other address check stays. The refusal message names the setting when the blocked address is in that range.

## 0.9.10 — 2026-11-18

- `essay-writer --check-update` and `--update` fall back to the public GitHub releases feed when the REST API is blocked or rate-limited. The tag comes from the feed and the sdist/`SHA256SUMS` URLs are built from it, so an update no longer depends on `api.github.com`.

## 0.9.9 — 2026-11-18

- `essay.health` reports `unpaywall.email_present` as a boolean, beside `consensus.key_present` and `openalex.key_present`. The update path does not ask for keys; one health call now shows whether all three are stored, without echoing any value.

## 0.9.8 — 2026-11-17

- Crossref enrichment follows the documented REST API guidance: the stored Unpaywall email goes with each request as the polite-pool `mailto`, the query asks for five rows with a `select` field list, and a row is accepted when its title matches and any gathered year or author also matches. With a year or author the query filters to `type:journal-article`, so "Faculty Opinions recommendation" datasets no longer crowd out the work. OpenAlex requests send the same contact email. Without a year or author, the resolver still reads only the first row.

## 0.9.7 — 2026-11-17

- `essay-writer --install-upload` finds the project root inside the zip itself. An install folder that already held an older copy used to make the installer pip install that older tree and still report success; the update now installs the uploaded copy, and a fresh interpreter must report the uploaded version before the result says `ok`.
- `essay.setup` counts the secrets already stored in `setup.secrets.json` when it decides what is skipped. A later setup that adds only the OpenAlex key no longer warns that the stored Consensus key and Unpaywall email will not run, and the reply reports the secrets that are present.
- The setup preview again names the Consensus key when it exists only in the environment, matching what `essay.dig` uses. Setup still warns about, records, and reports only the passed or stored key.

## 0.9.6 — 2026-11-17

Free look-ups that the app could not make were reported as empty results, and every HTTPS call failed on a Python build with no CA bundle of its own.

- `safe_url` now builds its HTTPS context from `certifi` when it is installed, then from `SSL_CERT_FILE`, then from the macOS, Red Hat, or Debian CA bundle. A python.org framework build with no `Install Certificates.command` used to fail every OpenAlex, Consensus, Unpaywall, and PDF request with `CERTIFICATE_VERIFY_FAILED`; both look-ups then looked dead.
- A refused look-up keeps its HTTP status and reason on the dig card instead of becoming "no hits". An invalid Consensus key, a spent plan, an OpenAlex rate limit, or a blocked network now appears on `dig-card.md`, in the reply as `lookup_note`, and as `refused` on the card. `invent-forbid` is unchanged.
- OpenAlex accepts a key from `OPENALEX_API_KEY` (environment or stored setup secret). Keyless calls share a small daily budget with everyone on the same network address, and OpenAlex rate-limits them under load; mailto no longer raises that budget. `essay.health` reports `openalex.key_present`.
- Ordinary setup collects that OpenAlex key on the same secret card as the Consensus key and the Unpaywall email. `essay.setup` binds it by SHA-256, stores it as `OPENALEX_API_KEY`, and names the shared budget when the key is skipped. A later setup that omits it keeps a key already stored.
- Debug export redacts `OPENALEX_API_KEY` values and `api_key=` query values.
- The public tree ships `FIRST-RUN.txt` as the only setup manual. `FRIEND-PROMPT.txt` is no longer tracked, packaged, or copied into a release; it remains a local-only email prompt outside the public repo.
- New `essay-writer --check-update` reads the newest GitHub release, and `essay-writer --update` verifies the release source archive against `SHA256SUMS` and upgrades the installed package in place. The essay tree, setup record, stored keys, and remembered Mac folder are not touched, and the setup cards are not shown again. A git checkout is refused unless `--force` is given.
- A later `essay.setup` keeps the secrets it was not given. Before, confirming with only a key dropped the stored Unpaywall email and the remembered Mac handoff folder, and confirming with only the email dropped the key. The stored secrets file is merged, and the setup record reports the secrets that are actually on disk.

## 0.9.4 — 2026-11-15

Student docs, the final-folder scheme, mark-fit notes, the unmounted-Mac line, the prompt-density pass, and the mid-office session-token fix.

- The README and `docs/GLOSSARY.md` explain the words a student meets, and the README walks a student through the run: the ten stages, where the student confirms, the stage 5 save, and the folder the tool returns.
- Stage 10 names the folder `final_place` returns. `Documents/<project>-10/` stays the fallback when no Mac handoff is configured. A findings note under a mounted Mac folder is spoken from that folder, and a copy also lands in the sequence folder with the final Word. Existing files are not moved.
- When the Mac folder is not available, the chat says so in student words: the file stays in the chat and on this sequence, and the student can ask the operator to set it up or copy the file. The four-way card, the sign-in card, and FIRST-RUN.txt are unchanged.
- Mark-fit notes still read section names and weights only. A grade band is never a section weight, including a range such as `Distinction 70-79%`. A reflective diary and a brief with no weights stay silent.
- Front-office paragraphs and the long stage bullets are one sentence or one rule per line. Every clause stays. “The essay is balanced” is glossed as weighing both sides, without repeating the shared opposing-views sentence. “A thin edit” in the stage rules is glossed as a small wording change. The reopen rule stays. `review/eqr.md`, `install/operator.md`, `status/mid.md`, `seats/write.md`, `voice.md`, and the Harvard page are unchanged.
- A mid-office reader can close only the session it started. Each session has its own token, captured before the reader thread starts. A later session under the same sequence id keeps a new token and is left alone, including after a reset in the same folder and after the run folder moves. A direct finish still closes with no token, and a stage-5 draft that closes its own job still records the child exit code. This stops a late reader from clearing the next session and replacing the stage-7 Confirm line with the wait line.

## 0.9.3 — 2026-11-15

Brief gap lines, stored answers, cover rules, stage titles, helpful-friend voice, answer-field replies, the mid-office reader-log fix, Apache 2.0, author metadata, and CI fixes.

- The chat sounds like a helpful friend. Stage 6 still leaves the edit with the student, and it says the next step asks questions and edits from the answers.
- After a save, the next stage's card appears only when that stage is drafted with
  the student's own text. A guidance-only draft is refused and writes no look.
  Both waiting fields stay clear until a real draft. A typed yes still saves only
  the waiting stage when the host sends no card fields. A typed yes does not
  delete a module.
- Student chat keeps ordinary English, including confirm, pack, and the names
  Cursor, Grok Build, and Grok Bot. Word files still drop those labels. Save
  lines say to choose Confirm or to say yes. A missing file-work app is named,
  and the essay so far stays safe. The typed-yes stage rule is stated once, and
  it never saves a later stage.
- Research summary and full research drafts carry no card, so their student line
  is "Say yes to keep this step." The dig draft keeps its card and its
  "Choose Confirm to keep this step." line. The copy tests assert the two lines
  separately.
- The host sheet and the `essay.pack.validate` description say the host sets
  `word_count_acknowledged` only after the student accepts the stated length. The
  student word-band line is unchanged, and the flag stays out of the student
  `next` and `reason`.
- The leftover free-alternative reply keeps "Nothing was fetched." and drops
  "Do not invent an address." The delete sentence in the generated bot docs, the
  template, and `briefing.md` now starts with a capital A.
- The spoken Basics pass stops calling a brief silent when its own prose still
  shows a format word, a task verb, or a question mark. Those lines now say
  "I could not read a format from this brief." and "I could not read the
  assignment question from this brief." A brief that carries none of those
  signals keeps "the brief does not name one". A mark scheme that lists
  percentage weights without a band says "The brief lists percentage weights,
  not grade bands." No band is invented, and the brief file is not rewritten.
  A brief that prints its weights under `Section weights:` rather than under a
  mark scheme heading is read the same way, so a percentage table with no band
  gets that sentence too. A mark scheme heading with nothing under it is not
  filled from later prose, so that brief keeps "No mark scheme is on this
  module." A `Section weights:` heading with no table is not read from the
  labelled field or prose below it either. Only a table row, a weight row, or a
  column header opens that block, so `Word count: …10%` under an empty weights
  heading keeps "No mark scheme is on this module."
- An obvious cue fills a format or a question the brief left empty. "Individual
  report", "reflective diary", and "essay" or "report" used as the assignment
  type set the format, including a heading line that opens with the type, such
  as "Individual report, 2,000 words, due 12 December 2026." One task sentence,
  or one question that ends with a question mark, sets the question, and a
  mark-scheme bullet is not that question. If two assignment types both match,
  the format stays empty. A mention is not the assignment type, so "Write an
  essay on the annual report of one named firm" is an essay, and a later line
  that only mentions an individual report does not set one. A refusal in the
  same sentence is not the assignment type either: not, never, no, cannot,
  can't, don't, doesn't, and won't count, in either apostrophe form, so "Do not
  write a reflective diary" and "Don't write an essay" set no format while a
  later clear cue still fills. A labelled Genre, Format, Question, Task,
  assignment ask, or Title line still wins, and a word count that already
  parses stays as it is. The brief file is not rewritten, no remembered answer
  is stored, and the combined stage title stays when the brief still has no
  Genre or Format label.
- A format or question the brief leaves empty can be answered once in the
  chat. The answer is stored beside the brief, and the brief file is not
  rewritten. A later sequence of the same module sees that answer. An empty
  answer clears the stored field.
- The Word cover prints a programme row only when the brief asks for it.
  A real stored title is the first visible line, and a placeholder is left
  off. The conclusion stays noted or open on the pack. Chat says that in one
  sentence when Word is written. Neither sentence is printed on the cover.
- Until the genre is known, stages 2 and 3 use Establish the focus and Write
  the plan, and stage 10 is Finish the Word file. The opening card names the
  first-full-draft exception: the student decides when each other stage is
  saved, and the first full draft is saved when it is written. Word metadata
  uses a real stored title. A Draft placeholder is not the document title.
- A mid-office reader that is still finishing after the run folder moves stays
  on the folder that started it. The exit line is written there, and the open
  session is closed there first, so the new folder does not get that log,
  sequence directory, session file, or spoken stop line.
- The licence is the Apache License, Version 2.0. `LICENSE` carries the
  Apache text with `Copyright 2026 4zhmv6zvj2-afk` on the appendix line,
  `pyproject.toml` declares `license = "Apache-2.0"` with
  `license-files = ["LICENSE"]`. It does not declare a `License ::` classifier,
  because setuptools 84 rejects that classifier beside a PEP 639 licence
  expression. The README badge and License section name Apache 2.0. Licence and
  metadata only: no product behaviour changes, and no NOTICE file is added.
- `pyproject.toml` names the package author and maintainer: `authors` and
  `maintainers` are both the one record `{ name = "Ron", email =
  "4zhmv6zvj2-afk@users.noreply.github.com" }`. Author and maintainer metadata
  only: the licence stays Apache 2.0, and no other metadata moves.
- A stage 7 draft still asks its questions when a mid step starts in the same
  turn. The reply says the draft question line, including "If the draft is fine
  as it is, say all fine.", and is not only the wait line. The wait line still
  appears while a step is actually running on a stage that is not showing that
  ask, and a stage 7 reply with no card says the wait line. Skipping the questions is still
  refused, and all fine still opens Confirm without saving until Confirm is
  pressed.
- An unmapped brief still prints the title-page rows it asks for. A programme
  or registration ask stays on the Word cover; the cover does not stop at the
  title. A programme-name ask is not a student name, so the cover does not
  print a blank Name line unless the brief asks for the student's name.
  "Name of the programme" and "programme's name" are programme asks too.
- A format or question answer is stored on a draft. A confirm that sends an
  answer field still has to be a real look; guidance alone does not save the
  stage. The reply says whether the answer was stored, cleared, or left
  unused. An empty answer on a fresh brief, or a format that is not essay,
  report, or reflective diary, does not say it was stored. A call that sends
  both fields and stores one while clearing or leaving the other unused names
  each field. A field that was not sent stays on the single line.
- The answer file beside the brief is read and written only when it is a
  regular file in a real folder. A symlink is not followed, and neither is a
  linked folder that would hold the file.
- Ruff format is clean across the test files the format check reads. The author
  address scan ignores generated egg-info, so the sdist suite does not treat
  PKG-INFO as product code.

## 0.9.2 — 2026-11-13

Setup defaults, damaged-record handling, final-Word safety, and dependency updates.

- Setup secrets and the file-work choice load from the record beside the chosen app.
  A missing choice stays Cursor; an unknown choice fails clearly. Backup and archive
  drives are refused as save folders, and those drive names stay out of student chat.
- The plagiarism scan and source gathering use one text rule: invalid text is
  refused, valid UTF-8/BOM/UTF-16 is kept, and no replaced copy continues. The word
  band and section budgets share one citation-word rule while keeping a tighter
  pack maximum.
- Inherited locks stay pending until a save actually stores. A damaged confirm
  record or state file stops the tool, says so, and is not applied.
- After the last stage is saved, a missing final Word file is not written again;
  the tool says it is missing. An unmounted Documents reply stays unmounted. A web
  link in rules or a longer instruction is not treated as a remote launch; real
  remote targets and cloud flags are still refused.
- Dependencies: cosign-installer v4.1.3, codeql upload-sarif v4.39.3, ruff 0.17.4,
  click 8.5.1, pydantic 2.14.3, pydantic-core 2.50.4, sse-starlette 3.7.0. The
  hash-pinned CI set and `uv.lock` are updated together; the build set is unchanged.

## 0.9.1 — 2026-11-12

Maintenance patch: one draft-ordering fix and the architecture and test cleanup behind it.

- Two saves can share one whole-second timestamp and one file-clock tick. The later
  draft now wins on a monotonic write-order stamp; the fingerprint is unchanged.
- The stage runner is split into `stage_confirm.py`, `stage_body.py`,
  `stage_note.py`, and `stage_hold.py`. `stage_track.py` falls from 1,115 to 463
  lines. Behaviour, the confirm gate, and the public tool contract stay the same.
- A static import-graph guard keeps the load graph acyclic: 28 cycle-breaking
  deferred pairs and 46 direct mutual pairs.
- Thirty-one brittle source-text pins are replaced by behavioural checks:
  `getsource` call sites fall from 222 to 191.
- No prompt, tool-schema, or student-facing wording changes.

## 0.9.0 — 2026-11-11

Student-facing lines for the opening, four redirects, and stages 6 and 7.

- The opening says the approved first-turn card in those words before the three choices.
- A short ask for one of the four blocked turns gets that approved reply and does not save.
- Stage 6 says the approved lead-in once, then the shipped short read list. That read list is unchanged.
- Stage 7 says the approved student line before the questions. The shared stage 7 rules stay.
- Cursor and Grok Build read the same stage rules, including those two student lines.

## 0.8.2 — 2026-11-11

Formatting and gate-only patch. No runtime behaviour change; every Python file
is AST-identical to 0.8.1.

- Apply `ruff format` to `src`, `tests`, and `tools` (223 files: 217 Python plus
  the CI workflow, pre-commit hook, README, CONTRIBUTING, docs/testing, and
  pyproject). The vendored bootstrap is excluded from formatting and remains
  byte-identical; `ruff check` still lints it.
- Add `ruff format --check --force-exclude src tests tools` beside the existing
  `ruff check` in CI, the local gates, the pre-commit hook, and the testing docs.
- No prompt, catalogue, wording, architecture, dependency, or behaviour changes
  in this release.

## 0.8.1 — 2026-11-11

Prompt catalogue trim, with the release version guard and the omitted-checksum note.

- The release job checks that the tag, `pyproject.toml`, and the newest changelog
  heading agree before it builds, signs, or uploads anything. A `SHA256SUMS`
  file that is present but has no entry for the zip is reported as omitted, the
  install stays unverified, and the README and SECURITY notes describe that case.
- Door descriptions keep the contract. Duplicated stage rules are one copy,
  stages 6 and 7 tell the same story on both launch paths, and the shared rules
  are mirrored into the generated helper. The assembled prompt measures 24,365
  tokens and the 24 door descriptions measure 14,295 characters. The caps stay
  33,600 assembled tokens, 1,200 characters per door, and 24,000 for the catalogue.
- Unused public helpers are removed. The same paragraphs still reach the
  instructions and both setup prompts from the prompt files. Cursor still reads
  `CURSOR_SETUP_PROMPT`. Grok Build still reads `SETUP_PROMPT`.
- Four source pins that matched only a function name, a `def` line, or any
  function with source now point at the call they were meant to check.

## 0.8.0 — 2026-11-11

Structural cleanup round: one sentence splitter, one JSON record store, a real stage boundary, a single-sourced prompt bundle, module splits, and hygiene hardening.

Infrastructure:
- A single `textutil.sentences` splitter serves gates, brief_checks, cite_fit and
  stage7. Gates no longer silently drops sentences shorter than eight words; the
  EQR claim check scans the body before the reference list, so a bibliography
  line is not reported as copied prose. A single `textutil.content_words`
  extractor serves the assignment and cite-fit checks.
- A single `records.py` helper (tolerant read, repo-write guard, writer-unique
  temp file and atomic replace) replaces the hand-rolled JSON stores; each store
  keeps its own defaults and validation.
- New tests pin cross-module sentence segmentation, the short-sentence gate
  regression, and record concurrency/tolerant reads.

Stage boundary:
- `stage_track` is the orchestrator only: the 99-name re-export shim and the
  `_MINTING` contextvar recursion are gone. The state, landing and reply layers
  no longer import the orchestrator; the next-card mint and inherited-lock
  confirm arrive as injected `CardRun` callbacks. A guard test holds the
  boundary, and ARCHITECTURE.md describes the real layering.

Prompt bundle:
- `craft/voice.md` is the single rendered source for the shared voice/craft
  rules; stages 5-8 render it once. Precedence (brief > rubric/mark scheme >
  shared rules) and four repeated non-craft rules moved to one shared source,
  and 14 duplicate bullets were removed. The dead research seat and dead
  writing_basics re-exports were deleted. Prompt files are down about 31%, the
  helper doc about 34%, and the snapshot about 12.5%; new tests cap the
  assembled instructions plus door descriptions and fail on new duplicated
  long lines.

Module splits and adapter:
- `first_run.py` (2,141 lines) is split into `first_run_common`,
  `first_run_install`, `first_run_host`, `first_run_mac` and `first_run_cli`
  behind a thin facade. `late_chain.write_stage10` and
  `stage_track._build_stage_body` are split into named steps, and the stage-7
  skip probe is one predicate.
- MCP adapter tests pin the 24 typed tool schemas, the private call-path
  touchpoint, and active host-line replacement. Production asserts became
  explicit raises; a `py.typed` marker and a POSIX classifier were added.

Hygiene:
- The `fcntl` import is guarded with a clear Unix-only error; `state.json`
  writes take an fcntl lock; legacy setup adoption only accepts real product
  folders; an essay.intake mount-parity test was added. README states that
  macOS or Linux is required.
- The installer now reports a `SHA256SUMS` file that exists beside the zip but
  does not list it, instead of silently treating that file as absent; the result
  stays `upload_verified: false` with a note saying why.

## 0.7.0 — 2026-11-11

Hardening round: bound confirm side effects, real launch/install branches under test, a verified release chain, and a typed Confirm fallback.

Confirm:
- `essay.setup` binds the Consensus key and Unpaywall email by SHA-256 in the
  draft payload, so a save call that repeats different values is refused; the
  values are never echoed or stored in the draft record.
- `essay.dig` and `essay.research.summary|full` return `cardDigest` on the draft
  and require it on the save call. Confirm re-derives it from the stored payload
  and shown card, so a local edit to the draft record's card is refused. Drafts
  written before the binding refuse with a "show this step again" action.
- A typed yes, ok, or Confirm saves the waiting card when the host cannot send
  the card fields; a supplied card field still has to be the Confirm action.
  Student-facing next and refusal text no longer carries model directives.

Install, launch, and install-path hardening:
- Removed every `PYTEST_CURRENT_TEST` branch from production. Spawn, MCP enable,
  config resolution, PATH exposure, Mac-folder discovery, and the idle clock use
  explicit injected collaborators; tests exercise the real branches with fake
  binaries and launchers, and a guard fails if the pytest key returns.
- `essay-writer --install-upload` verifies a zip checksum when one is available
  (`--upload-sha256`, a sibling `.sha256` file, or `SHA256SUMS`) and otherwise
  installs the zip as trusted operator input, reporting `upload_verified: false`.
  A zip without `requirements-runtime.txt` is refused, and there is no unpinned
  dependency install. Quarantine/provenance clearing is limited to app-generated
  sequence deliverables; operator-named files keep their marks.

Release proof:
- Release builds run on `ubuntu-24.04` with a pinned cosign release, verify each
  Sigstore signature and the GitHub attestation after signing, and CI's Ubuntu
  jobs are pinned too.
- A new reproduce workflow downloads a published release, rebuilds it from the
  tag with the pinned toolchain, and fails on any SHA-256 mismatch.

Tests:
- Added confirm-binding, typed-Confirm/UX, no-pytest-env, and release-proof
  guards; the docs, sdist, and unfenced-content guards stay green.

## 0.6.3 — 2026-11-11

Review follow-up fixes: truthful claims, a document fence, and packaging coverage.

Docs and claims:
- Say what the Confirm gate actually guarantees: a save, stage advance, or
  deliverable write needs a matching draft, while a draft call writes the draft
  ledger, tracking note, and pointer; stage 5 stores its first draft and
  advances on its draft call by design. Name the shown-card and setup-credential
  digest limits, and say that tighter binding is planned.
- Name document bodies (uploads, briefs, PDFs, fetched pages) as untrusted in
  the threat model, scope `safe_url` to content-driven fetches with the installer
  and pip exceptions, correct the vendored-bootstrap sentence (no local patch),
  and call an `--install-upload` zip trusted operator input.
- Refresh the release-verification instructions (macOS `shasum`, current assets,
  `cosign verify-blob`, `gh attestation verify`), the supported-versions table,
  the v0.6.1 re-cut history, and the architecture wording; remove drifting test
  counts and fix the glossary link.

Prompt fence:
- Add an untrusted-content fence to the server instructions, both seats, and
  every stage's rules: document text is quoted evidence, never instructions.
  Mark `essay.originals` read results untrusted and say so in the tool
  description.

Packaging and tests:
- The sdist now carries `HISTORY.md`, `requirements-runtime.in`, and the
  remaining tracked GitHub/pre-commit files.
- CI and the release workflow require the sdist to carry every tracked file and
  the wheel rebuilt from the sdist to be byte-identical to the checkout wheel;
  CI checkouts set `persist-credentials: false`.
- Add docs-truth, sdist-completeness, and untrusted-content guards; the
  upgrade-card test no longer writes its marker into the checkout.

## 0.6.2 — 2026-11-11

Writing-quality, citation-policy, and recovery round.

Narrative citations:
- Personal names in prose are recognised, including Unicode names, titles,
  initials, name particles, Oxford lists, and `et al.` with or without a comma
  before the year. A gathered `et al.` citation matches; an ungathered one
  fails. Narrative and parenthetical forms leave the same word count.
- Policy B: a parenthetical citation, or a narrative citation with a clear
  person cue, is a hard failure when it was not gathered. A lone ordinary name
  plus a year is a possible citation: gate 7 passes, the token is named on
  `questionable_citations` and the gate's `questionable` list, and Word is still
  written. Cite-fit still reports the gap. A hard miss still refuses Word.
- Common labels are not citations: document and event head nouns, months,
  weekdays, and five-plus organisation initials stay silent. Accepted limits
  (multi-word labels outside the list, `Page`/`May`/`June` collisions,
  two-to-four-letter all-caps acronyms) are documented in the README and the
  review note.
- Gate 9 requires author and year metadata whenever a citation record is
  present, including a possible one.

Recovery and setup:
- A damaged confirm journal is renamed to `.stage.commit.damaged-<UTC stamp>`
  and is not applied. The next save continues and names the set-aside file. If
  the rename fails, the save refuses, names the journal path, and says to move
  that file out of the tracking folder; the damaged file stays in place. A
  valid torn journal still replays; a damaged `state.json` still raises.
- A setup record written only beside the app, up to two folders under the home
  directory, is copied to `~/.essay-writer/setup.json` with its secret and is
  read from there. A test root does not write the real
  `/workspace/Essay-writer/setup.json`.
- The plagiarism scan, gathered-text reads, and the module brief accept UTF-8,
  UTF-8 with a BOM, and UTF-16 with a BOM. cp1252 is still refused as
  `gathered-encoding`; an unreadable file is `gathered-unreadable`, not bad
  UTF-8.

Other fixes:
- The Release workflow is dispatched against a draft release and attaches
  assets, signatures, and provenance before publication, so the repository's
  immutable-release setting does not reject them.
- The word band and section budget share one citation-count flag. An explicit
  pack flag wins, then the mark scheme, the brief, and the studied default; the
  pack minimum and maximum stay as sent.
- `keep` marks an inherited lock only after the save stores. A failure to mark
  the lock leaves the stage saved and says so.
- The first-run folder check reads the app path on the setup record.
- A repeat stage 10 write reuses the previous copy when the pack is unchanged,
  the marker says the sequence file was written, and the final file is present.
- A launch is remote for a remote flag, an `--endpoint`/`-e` URL, or a URL
  token. A model named `cloud-agent` and a URL inside a longer instruction are
  not launches.
- Tests: 1110 (8 terminal-backed cases skip on hosts without a pty); ruff,
  mypy, docs, and the prompt snapshot are current.

## 0.6.0 — 2026-11-05

Bootstrap v0.2.0 and the Python version policy.

- The vendored bootstrap core is upstream `python-mcp-bootstrap` v0.2.0 (tag
  `v0.2.0`, commit `fd8e0b9`), byte-identical to the release: the local
  requirements patch is gone because the hash-pinned install is upstream now.
  `VENDOR.json` records the source, the release, and the file SHA-256.
- Install command order is upstream's: `requirements-runtime.txt` installs with
  `uv pip install --require-hashes -r ... --python <venv python>` first, then
  the project with `uv pip install --python <venv python> --no-deps -e .`. A
  copy without the requirements file keeps the single upstream install.
- The Python floor is 3.12 for the package and for the vendored core; the
  adapter keeps `REQUIRED = (3, 12, 0)` explicit. `first_run.py` now says 3.12+;
  the product provisioning pin stays 3.15.2.
- Version policy: CI runs the 3.12, 3.13, 3.14, and 3.15 lines with
  `check-latest: true` and prints the resolved patch (`python -VV`). Coverage
  stays on the 3.12 cell, the macOS job runs 3.15, the artifact job builds on
  3.12, and `release.yml` keeps the exact 3.12.13 build pin. A committed root
  `.python-version` names the 3.15 line.
- `tests/test_version_policy.py` guards the floor, the CI lines, the committed
  `.python-version`, and the `VENDOR.json` release and hash.
- `ARCHITECTURE.md` and `docs/testing.md` describe the v0.2.0 vendoring and the
  3.12 coverage cell.
- Tests: 1078 passed (8 terminal-backed cases skip on a host without a pty);
  ~87% coverage.

## 0.5.0 — 2026-11-05

Final clean-up round.

- `stage_track.py` is split again: it is now 847 lines with 4 top-level
  functions. `stage_landing.py` (396 lines) owns saved-stage storage, report
  attaching, mid-run and missed-stage records, inherited-lock bookkeeping, and
  the stage 6 opener; `stage_replies.py` (382 lines) owns the draft and save
  reply writers and the no-op result. The orchestrator re-exports every layer,
  so existing imports and contract pins are unchanged. Function bodies are
  byte-identical apart from one call-time import that closes the only cycle
  edge.
- Coverage is measured: `pytest-cov` is a dev dependency, coverage config sets
  an 85% floor (current baseline ~87%), CI runs coverage on the Ubuntu 3.12.13
  cell, and `docs/testing.md` documents the command and the floor.
- CI housekeeping: Python 3.13 joins the Ubuntu matrix (3.12–3.15); workflow
  concurrency cancels superseded runs; the test job carries a timeout.
  `requirements-ci.txt` is regenerated with the new dev dependency.
- Cursor installer guidance: the hash binds the bytes, not the vendor's
  identity. README, FIRST-RUN, and SECURITY recommend the manual install for a
  trust-sensitive setup.
- README badges for CI, the Python floor, and the license; `pyproject.toml`
  gains keywords, classifiers, and project URLs.
- Tests: 1060 passed, 8 skipped; ~87% coverage.

## 0.4.1 — 2026-11-05

Small follow-ups from the third review pass.

- `essay-writer --install-upload` (the update path on an already-installed
  copy) now uses the same standard as `python first_run.py`: when the zip
  carries `requirements-runtime.txt`, it installs the hash-pinned runtime
  requirements with `--require-hashes` first, then the project with
  `--no-deps`. A hash or network failure stops before the project install.
  Older zips without that file keep the single upstream install; the report
  lists the commands and sets `requirements_verified`.
- Residual report ids are public behaviour names: `install-root`,
  `deliverable-packing`, `mac-handoff`, and `open-grok-session` replace the
  internal ticket ids. The residual text is unchanged.
- Tests: 1060 passed, 8 skipped.

## 0.4.0 — 2026-11-05

Security and state-model round; no intended workflow change.

Install integrity:
- The first-run install now runs `uv pip install --require-hashes -r
  requirements-runtime.txt` before the project install, which then runs with
  `--no-deps`. A hash mismatch or network failure stops the install. The
  vendored bootstrap carries this one documented local patch; `VENDOR.json`
  records it and the new file hash.
- Cursor CLI install is no longer TOFU. Consent (`--install-cursor`) authorises
  the download only; setup reports the file's SHA-256 and stops with
  `cursor-install-needs-hash`. Execution requires that expected hash
  (`--cursor-sha256` or `ESSAY_WRITER_CURSOR_INSTALL_SHA256`); a mismatch stops
  with `cursor-install-hash-mismatch` and runs nothing.

Network and data:
- Every remote fetch goes through the new `safe_url` opener: public http(s)
  only, every resolved address checked (no loopback, private, link-local,
  reserved, multicast, or ULA), redirects re-validated and capped at three
  same-scheme hops, and hard byte caps (25 MiB paper, 2 MiB research API, 1 MiB
  look-up). Over-cap bodies are refused, not truncated.
- `essay.debug.export` redacts each member before zipping: absolute home/volume
  paths, emails, `Bearer`/`x-api-key` values, and common token shapes. Key names
  stay; values go.
- Secret files are created with mode 0600 before any content is written (setup
  secrets and the remembered Mac folder), instead of write-then-chmod.

Trust model:
- `SECURITY.md` now has a plain threat-model section: the Confirm gate binds
  arguments and file fingerprints, not human identity; the host model is
  trusted to relay the person's yes; the server cannot prove a human clicked.
  Attended sessions, the reviewer server, and read-only where possible are the
  recommendations.

State model:
- The stage pipeline is typed: new `StageArgs`, `StageContext`, and
  `ConfirmState` dataclasses replace the 15–17 argument helpers and the
  `"_state": True` sentinel dict. Internal helper parameters go from 52 to 13 and
  the untyped state-key reads from 39 to 0. `essay_stage` keeps its MCP tool
  signature.
- `stage_track.py` stays the orchestrator and keeps its reply-dict contract.

Fixes:
- A fresh clone no longer emits `SyntaxWarning: 'return' in a 'finally' block`
  from `build_status.py`.
- `ARCHITECTURE.md` fixed two stale claims: the prompts live in the packaged
  `prompts/` bundle, and the vendored bootstrap source repository is public.

Tests: 1058 passed, 8 skipped.

## 0.3.1 — 2026-11-05

Structural clean-up; no intended behaviour change.

- `src/essay_writer/stage_track.py` is split: the pointer and its commit journal,
  the stage lock, the tracking-note renderer, and the held/refused reply bodies
  move to the new `stage_state.py` (1,334 lines). `stage_track.py` keeps the
  orchestrator and the run branches, and re-exports the state layer so existing
  imports keep working. The kept code is unchanged.
- Test files are renamed from `test_*_ac.py` to behaviour names, and private
  ticket/PR references are removed from test docstrings. `AC1`, `AC2`, … labels
  are now documented as stable local acceptance-criterion ids, not tracker
  references.
- README, CONTRIBUTING, ARCHITECTURE, `docs/testing.md`, and `docs/GLOSSARY.md`
  are updated for the new suite layout and the module split.
- Tests: 1006 passed, 8 skipped.

## 0.3.0 — 2026-11-05

Distribution and release engineering:

- The source distribution is complete and self-testable: it carries the full
  test suite, `conftest.py`, `helpers.py`, `pty_support.py`, fixtures, the prompt
  snapshot, docs, and tools. `pytest` works from the extracted sdist.
- Builds are reproducible. `SOURCE_DATE_EPOCH` comes from the tagged commit;
  `tools/reproducible_build.py` builds twice, normalizes the sdist, and fails on
  any hash drift. The release workflow runs the same check before signing.
- New CI `artifacts` job: build the wheel and sdist, install the wheel into a
  clean environment, extract the sdist, and run the full suite from it. The
  release workflow runs that artifact test before uploading or signing.
- macOS CI job added, matching the Mac-centric product.
- The CI "Repository checks" step no longer greps for a private domain-word
  denylist. It checks generic things a public repository should check: machine
  paths and secret material.

Install path:

- Runtime dependencies are exact-pinned (`mcp==2.3.0`, `python-docx==1.2.0`) and
  `requirements-runtime.txt` is hash-pinned for a verifiable manual install.
- Setup no longer pipes `curl … | bash` into a shell. It downloads the Cursor
  installer to a file, records the file's SHA-256, and runs it only after
  explicit consent (`--install-cursor` or `ESSAY_WRITER_ALLOW_CURSOR_INSTALL=1`).
  Without consent it changes nothing and prints the manual command.

Python floor:

- The package floor is 3.12, verified with the full suite on CPython 3.12.13
  (1006 passed, 8 skipped — the same as the 3.15 baseline). `pyproject.toml`,
  ruff, mypy, `uv.lock`, and the CI matrix move together.
- The first-run bootstrap still provisions a private CPython 3.15.2 when it has
  to; the floor only says what the package itself runs on.

Documentation:

- README rewritten around what the project is, why it is public, what it is not,
  and what setup does to a computer. Academic-integrity position stated plainly.
- `HISTORY.md` records that `v0.2.1` is an import snapshot and that `0.3.0` is
  the first normal release.
- New `docs/GLOSSARY.md` maps the private vocabulary (doors, seats, spine,
  shelf, dig, canon, mid-office) to plain terms.
- New `docs/testing.md` explains the `_ac` naming, the contract pins, and the
  prompt snapshot; `tools/update_prompt_snapshot.py` regenerates the snapshot
  and supports `--check`.
- The version is checked against `pyproject.toml` instead of a hard-coded string,
  so the package and the metadata cannot drift.

## 0.2.1 — 2026-11-04

- Python floor is 3.14; CI pins 3.14.10 and 3.15.2.
- 3.14 compatibility fixes for `datetime.UTC` and `Path.rglob` test monkeypatching.

## 0.2.0 — 2026-11-04

- One `prompts/` bundle owns stage, genre, craft, review, front-office, status, and install text.
- Stages use shared bodies plus additive genre sections; the override/concatenation path is removed.
- Confirm and status text each have one source; briefing and door descriptions render it.
- Seat prompts are packaged with the bundle; docs generation keeps the exact prompt blocks in sync.
- Version now reports `0.2.0`. No intended workflow or tool behaviour change.
- Tests: 980 passed, 8 skipped.

## 0.1.2 — 2026-11-02

- README and release wording: stable source release.

## 0.1.1 — 2026-11-02

- README: demonstration / limited-maintenance status line; model-assisted purpose moved into the opening.
- Add GitHub bug-report issue template mirroring CONTRIBUTING.

## 0.1.0 — 2026-11-01

- First public source release.
- Ten-stage, confirm-gated essay workflow with MCP tools.
- Research packs, Harvard reference checks, invent-forbid citation rules, and Word output.
- Synthetic teaching fixtures and behaviour tests.
- Documentation and type-boundary cleanup.
- Stage runner split into named helpers; pointer and stage-result boundaries typed.
