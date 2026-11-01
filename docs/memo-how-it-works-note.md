# How the essay door works — noted, open, and evidence

Essay-writer reference for one module id at a time. It sets out the research inputs, the draft-then-confirm rule, and the noted-or-open ending.

## research.full inputs

The same inputs serve the short and the full research step, pointed at this essay's store.

- `confirmPhase`: `draft` or `confirm`. Required on the write. Missing it is a refusal, not a silent confirm.
- `topic`: the essay question. Required. The door does not invent it.
- `clarify_context`: `objective`, `background`, `issues`, and `guidance`. Each is an answer or `{"leave_open": true}`. `leave_open` is a person's choice. The door never fills it in.
- `packs`: optional, at most two names taken from `essay.health` `local_packs`. Those names are local subject-note markdown under `Essay-writer/<essay_id>/kb1/`. A name that is not on that list is refused. The door does not invent a pack, and a named pack is not itself a citation.
- `exclude_section_ids`: optional. Sections a person closed. A source in that list is not evidence.
- `industry` and `host_voice`: optional context. They are stored on the draft so a change needs a fresh confirm. They are not evidence and they are not written into the reference list.

`essay.research.summary` uses the same confirm rule and the same optional `packs`, `exclude_section_ids`, `industry`, and `host_voice`. It does not require `clarify_context`.

## The write-and-confirm order

The human and the model take turns. A write is never one shot.

1. `essay.health` if the door state is unclear. Do not invent that the door is up.
2. `essay.originals` lists or reads uploads and the brief for **one** essay id.
3. Research is `essay.research.summary` or `essay.research.full`.
4. Call the write tool with `confirmPhase: "draft"`. Stop. Show that draft to the person.
5. Confirm only after an explicit yes on **that** draft: the same arguments with `confirmPhase: "confirm"`.
6. Never silent confirm. Never confirm a changed pack, topic, or source list. Draft again.
7. Then `essay.pack.validate` (draft, then confirm), then `essay.pack.render_word` (draft, then confirm).
8. `essay.revise` records feedback on the same essay. It does not write a new Word file and does not replace the Word confirm.
9. `essay.shelf.put` / `essay.shelf.get` are a **local** shelf for that essay id. They are local to that essay id.

`essay.health` and `essay.originals` are read-only. Every other door above is draft-then-confirm.

## Enough to start is not enough to close

Answering the four clarify boxes only frames the question. That is enough to **start** full research. It is not enough to **close** the essay with a settled finding.

`essay.research.full` will not run until `clarify_context` has all four parts: `objective`, `background`, `issues`, and `guidance`. Each part is a non-empty answer or `{"leave_open": true}`.

Those clarify answers are not sources. They cannot be cited. They do not authorise a noted conclusion. Evidence is still only what was gathered: an upload for this essay id, the assignment for this essay id, or a local subject note that was read, with the excerpt in hand.

If a page, DOI, author, title, year, quotation, or journal is not in that gathered text, it stays blank. A free look-up may fill a blank bibliographic field on a source that was already gathered when the match rules pass. A look-up **miss** is an honest miss. It is not a made-up source and it is not support for a claim.

## Noted versus open — stand-back

The person marks the pack `conclusion` as `noted` or `open`. The door does not choose, and it does not change `open` into `noted`.

### Open

**Open** means the ending is not a settled finding. Word labels it that way. Open is a real outcome, not a draft the model should quietly close.

Open is allowed when support is thin: no gathered citation in the body, important words missing from the gathered excerpt, a clarify box left open, or a research pack with no opened file. The record says the ending is not a settled finding.

### Noted

**Noted** means the ending stands on gathered evidence. The door refuses noted when any of these is true:

- no gathered source is cited in the body;
- the asked ending’s important words are not in the gathered excerpt for the cited source (a confidence percent, or “I am sure”, is not support);
- any of `objective`, `background`, `issues`, or `guidance` was left open in confirmed full research;
- the confirmed research pack has no opened file.

The asked ending must already be a sentence in the body. The door does not write a new sentence to create a finding.

If the asked ending fails the support test but another sentence already in the body is supported by a gathered excerpt, the asked ending stays **open**. That other sentence may be labelled as a **formed view** in the pack (`formed_views`). The label is only allowed when the sentence is already there and the quote is in the gathered file.

Validate records the stand-back. It does not write Word and it does not write the shelf.

## invent-forbid

Cite only a gathered source. Do not invent authors, titles, years, quotations, page numbers, DOIs, or journal names. If the source is missing, omit the citation.

`docs/samples-study.md` is a synthetic teaching note. Reference-list lines in that note were not gathered. Do not treat them as sources, and do not copy student names or numbers out of sample drafts.

Paid resolvers are refused. Free look-ups may fill blanks on a gathered source under the match rule; they may not invent a paper.

## What stays essay-specific

- One essay id per module folder, such as `Essay-writer/MOD1004AA/` and `uploads/MOD1004AA/`. Briefs and uploads do not cross ids.
- Referencing is Harvard Referencing. See `docs/referencing-harvard.md`. The EndNote style name to select is Harvard Referencing 13th Edition. Module detail lives in the local subject notes for that id, not in this file.
- Output is Word `.docx` only.
- The draft is model-assisted; the student owns what they submit and must follow their school's rules.
- No chat-app integration. A bot template is not this tool.
- Programme text on the cover is the Teaching partner award: Undergraduate programme (PROG01), Awarding university. No student name and no student number.

## What does not transfer

Do not run a library search, a client-pack review, a standards book choice, or a client-file shelf from this tool. Do not send the essay by email. Do not treat another job's conclusion as this essay's conclusion.
