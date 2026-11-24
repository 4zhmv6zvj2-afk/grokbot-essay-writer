# Research gather and citation list

The student files an assignment, asks for sources, and gets a citation list of the works the catalogs actually returned. A silent brief states a length and no source count. At 2000 words the floor is 16 distinct works. Each counted work has a title, an author, and a year.

## Sub-features

- `research-file-brief` files the assignment onto the module.
- `research-open-sequence` opens sequence 1 for that module.
- `research-dig` runs OpenAlex, and Consensus or Unpaywall when those switches are on, then stores the card.
- `research-floor` keeps a sourced list or a draft from being written under the floor while another official page is still available.
- `research-citation-list` writes `citation-list.json` from the saved gather when the gather is allowed to continue.

## How to get to it (user POV)

- Put `brief.md` in `unassigned/`. The file used here is a question line plus `The assignment is 2000 words.` It does not state a source count.
- Confirm filing that file on `MOD1004AA`.
- Confirm starting the first sequence.
- Confirm the source card `essay.dig` shows. The card lists only look-up hits.
- When the gather is allowed to continue, confirm full research. Stage 4b writes the citation list. The student can open `citation-list.json` on the sequence.

## Driving it with verify-essay-writer

Preconditions:

- Launch has finished and the student folder is empty of essays.
- Doctor reports version `0.9.18` and `essay.dig` is mounted.
- `ESSAY_WRITER_ROOT` is the student folder from launch.

- **File the brief.** The helper writes `unassigned/brief.md`, then calls `essay.intake` with `name` `brief.md`, `module` `MOD1004AA`, `confirmPhase` `draft`, then `confirm`. The confirm path ends with `Essay-writer/MOD1004AA/brief.md`.
- **Open the sequence.** Call `essay.sequence.new` with `module` `MOD1004AA`, draft then confirm. `sequence_id` is `MOD1004AA-1`.
- **Gather.** Call `essay.dig` with `essay_id` `MOD1004AA-1`, `query` set to the question on the brief, and `confirmPhase` `draft`. Omit `smallerQuestions`. Send `confirm` with the draft's `cardDigest`. The command is `drive-research-gather`.
- **Catalogs.** OpenAlex `called` is true. When `CONSENSUS_API_KEY` is already set and `ESSAY_WRITER_CONSENSUS` is not `0`, Consensus `called` is true or the card records a refusal. When `ESSAY_WRITER_UNPAYWALL_EMAIL` is unset, Unpaywall stays off.
- **Count.** Read `dig-card.json`. Count distinct hits that have a title, an author, and a year. The card's `gather.floor` is 16, `gather.words` is 2000, and `gather.floor_from` is `word_rate`.
- **Citation list.** When `gather.blocked` is not true and dig saved an abstract or a PDF, call `essay.research.full` with the locators whose text uses a word from the question, `origin` `upload`, and each clarify field `{"leave_open": true}`. Draft, then confirm with `cardDigest`. The list file is `Essay-writer/MOD1004AA/sequences/1/citation-list.json`.
- **Floor.** If the distinct count is under 16 and `gather.further_page` is true, `citation-list.json` is not written and the sequence Word file `<sequence-id>.docx` is absent. `download-list.docx` is the gather's leftover list, not that draft. A written citation list or essay draft in that state fails the run.
- **Proof.** `research-gather.json` in `/opt/cursor/artifacts/verify-essay-writer/` names the distinct count, the floor, the catalog flags, and the citation-list result.

## Gotchas

- OpenAlex asks for five works per page and follows `next_cursor` until the floor is met or the page is short. A run under the floor with a cursor still available is not finished.
- Consensus turns to a later page only when `ESSAY_WRITER_CONSENSUS_PAID` is `1`. A free or unset plan keeps the first page and says this plan does not return another page.
- Unpaywall is not a question search. It runs per DOI only when an email is already stored. A missing email is `called` false, not an empty paper list.
- Confirm does not call OpenAlex, Consensus, or Unpaywall again. Count the stored card.
- A hit missing an author or a year is not a distinct work. Do not fill the missing field in.
- `essay.research.full` may refuse a file that is not tied to the assignment ask. Record that refusal. Do not invent a source to replace it.
- There is no floor switch. A run without a confirmed question asks for the question and does not search. A run with a confirmed question on the brief searches that question.
