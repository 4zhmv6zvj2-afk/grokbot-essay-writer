# Harvard Referencing

Essay Writer uses **Harvard Referencing** (author and year). The full university handbook is not in this repository. Do not invent a source type that this note does not cover, and do not copy habits from old scripts as if they were the handbook.

The rules below are an author-date Harvard style. Where two examples in this note disagree, follow the later one.

## Where the style lives

- This note is the checked handbook.
- EndNote style to select: **Harvard**
- CSL file: none checked in. Do not invent a CSL file from memory or from an old script.
- The author-date rules in this note were adapted from a Cardiff University Library Service tutorial, CC BY 4.0.

APA is not this style.

## What the tutorial requires

Harvard here is an author-date system. Two parts: a citation in the text, and a full entry in a list headed **References**. The list contains the sources you cited, in the order you first cited them. A reader must be able to find the source from the entry.

### In the text

- Family name and year: `(Khan, 2021)` or `Khan (2021)`.
- A paraphrase or quotation of one particular point includes the page: `(Li, 2019, p. 32)` or `Li (2019, p. 32)`. A range is `pp. 31-32`.
- A summary of a whole article, report, or page can sit at the end of the sentence and does not need a page.
- Two or three authors: every family name, joined with **and**.
- Four or more authors: the first author and `et al.` every time you cite them. The reference list still names every author, unless the tutor has allowed `et al.` in the list for more than four.
- A brief that tells the student to spell every author in the text does not replace this rule. Two or three authors are still all named. Four or more still use `et al.` in the text. The reference list still names every author.
- Several sources in one pair of brackets, oldest first. Works from the same year go in alphabetical order: `(Midgley, 1994; Smith, 1994; UNCHS, 1996; Gandelsonas, 2002)`.
- No personal author: cite the organisation that produced the work.
- No author and no organisation: cite the title.
- A short quotation uses double quotation marks and includes the page. A longer quotation is indented, has no quotation marks, and includes the page. The library FAQ treats about three lines as the break.
- An omission inside a quotation is an ellipsis. Words you insert are in square brackets. Do not change the meaning.
- A source you have not read: find the original if you can. If you cannot, name it with “quoted in” or “cited in”, and put only the work you read in the reference list.
- Common knowledge in the subject need not be cited. If you are unsure, cite it. Ideas, quotations, and information that are not common knowledge are cited. The assignment sets how many sources, when it sets a number.

### Reference list

The later tutorial page is the one to follow. An earlier page in the same file still says `et al.` in the list after three authors, and `6th ed.` Ignore that earlier page.

- Heading: **References**.
- Order: entries stay in the order you first cited them. The tool does not sort the list, so do not describe it as alphabetical. It also does not add `2018a` / `2018b` for a repeated year. The tutorial sorts the list by family name; that is not what the Word file prints.
- Every author, in the order the source gives them.
- A second or later edition is written `2nd edn.`
- Italicise the title of a book, a report, or conference proceedings. An article title is in single quotation marks and is not italic. The journal title is italic, with the main words capitalised.
- A website or other web page ends with the access date in parentheses. An online journal article does not need an access date. A place or publisher on a web entry does not cancel the access date.
- Any web source, including an online journal article, uses **Available at:** before the URL or the DOI.

Patterns taken from that later page:

- Book: `Surname, Initial. (Year) Title. 6th edn. Place: Publisher.` The title is italic.
- Journal article: `Surname, Initial. (Year) 'Article title', Journal Title, volume(issue), pp. start-end. Available at: doi:10.xxxx/xxxxx` The journal title is italic.
- Organisation web page: `Organisation (Year) Title. Available at: URL (Accessed: 17 May 2022).` The title is italic.
- Chapter: `Surname, Initial. (Year) 'Chapter title', in Editor (ed.) Book title. 5th edn. Place: Publisher, pp. start-end.` The book title is italic.

Other source types (statute, thesis, dataset, social media, and the rest) are in Harvard Referencing online. This note does not invent a pattern for them.

The tutorial’s own exercise still prints one `et al.` list entry and one `6th ed.` chapter line. Those examples disagree with the later rules above. Follow the rules, not those two lines.

## What the Word file prints today

The printer in `src/essay_writer/textutil.py` and `src/essay_writer/word.py` emits the tutorial lines already recorded above. It does not add a source type this note does not record. The first student-facing Word file, including the stage 6 file, uses this same list. A surname alone is not an entry.

- Heading: **References**.
- A journal title is italic. A report title or a book title is italic. An article title is in single quotation marks and is not italic.
- A gathered DOI is `Available at: doi:` plus that DOI. A gathered web address is `Available at:` plus the address. A web page access date, when gathered, is `(Accessed: date)`.
- An article number stays in the article-number slot, after the volume and issue. A page from a matching look-up stays: a range is `pp. start-end` and a single page is `p. N`, even when the opened PDF has no lone printed page lines. A page value with no look-up mark that the opened file does not print stays blank. A look-up page value that is an article number, not a page, is stored and printed in the article-number slot. When neither a page nor an article number is on the opened file or the look-up, the page field stays blank. The PDF viewer index is not a page.
- Entries stay in file order. The tool does not assign `2018a` / `2018b`, does not sort, and does not rewrite four authors as `et al.`
- A missing page, DOI, volume, or journal stays blank. Do not invent it. A blank is an honest gap, not a guess.
- A figure or table source line is the gathered author and year. It is never a web address.

## Local subject notes

Optional module notes on this computer (a personal notes folder). Layout matches `Essay-writer/<module>/` (for example `Essay-writer/MOD1004AA/`). This tool does not invent that note. A passage from those notes may be cited only when it was read (`origin: kb1`, `read: true`, and the excerpt that was read).

## What a reference may contain

Fields from the gathered text, or blank locator fields filled by a matching free look-up on that same gathered source (Crossref, OpenAlex, doi.org, Unpaywall). A look-up fills a blank field only. When the gathered file prints its own value, the file's value is the one gathered.

Missing pages, DOIs, volumes, access dates, and journal titles stay blank when there is no gathered text and no matching look-up. The tool does not invent them.

## What is not a source

- `docs/samples-study.md` records synthetic teaching patterns for rubrics and feedback. Habits in that note, including reference-list lines, are not gathered sources and are not this style.
- Clarify answers (`objective`, `background`, `issues`, `guidance`) frame the question. They are not evidence.
- Student names and student numbers are not written.

Do not invent sources for any citation this tool emits.
