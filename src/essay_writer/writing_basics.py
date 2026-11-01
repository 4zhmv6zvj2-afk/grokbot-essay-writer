"""Writing-base checklists per stage.

Canonical prose, clue words, report sections, and source-use rules:
docs/academic-writing-helpers.md. This module is what the BO LLM sees on doors
and server instructions. The bullets match that note. They are not a paste of
the whole source page.
"""

from __future__ import annotations

from essay_writer.harvard_4a import ANNOTATION_SENTENCES, FOUR_A_FORMAT
from essay_writer.known_paths import KNOWN_PATHS_LINE

# Prompt text for stages 5–8. Not a hard fail and not a score target.
# Rules 4–5 of the late-stage craft live here with the glue ban: this argument's
# order, and a connective only when the relation is true. Not a pass/fail gate.
ANTI_GLUE = (
    "Keep the person the brief names. "
    "A diary keeps that brief voice and is not forced into third person. "
    "An essay or a report is not forced into first person to sound human. "
    "Ban AI-glue: do not pad with stock transitions, empty emphasis, or lines that could sit on any assignment. "
    "When no lecture, reading, or workplace detail is on the opened files, ask the student once for one real detail and use only that detail. "
    "Never invent a lecture, a reading, or a workplace detail. "
    "Do not open with a general sentence built only from the topic nouns. "
    "Do not close with an automatic In conclusion that only restates the topic. "
    "A paragraph closer must not only restate the topic sentence. "
    "Make it assignment-specific: a cited finding, a limit, or a figure. "
    "Use a connective only when the relation is true. "
    "However has to mark a real contrast. More connectives are not more coherence."
)

# Prompt text for stages 5–8, including a diary. Not a hard fail.
# Rule 3 of the late-stage craft: words the writer can define. Not a score target.
VOICE_LIMIT = (
    "Vary the sentence rhythm. "
    "Cut AI connectors such as Furthermore, Moreover, In conclusion, and It is important to note. "
    "Do not open a diary with a polished line such as In this reflective diary I will. "
    "A diary may be slightly fragmented. "
    "An essay or a report body stays academic and uses Harvard Referencing. "
    "Prefer a concrete detail over an abstract line. "
    "Do not plant grammar errors. "
    "Use words the writer can define out loud. "
    "Do not nominalize a verb into -ion, -ment, or -ance to sound scientific, "
    "and do not swap in a rarer synonym the writer does not use."
)

# Prompt text for stages 5–8, including a diary. Not a hard fail.
# Filler, empty intensifiers, and stacked hedges are named so a writer can cut them.
PLAIN_WORDS = (
    "Cut words that do no work in the sentence. "
    "Empty intensifiers such as very, really, quite, and extremely add nothing, "
    "and significantly adds nothing when no figure follows it. "
    "Filler phrases such as in order to, due to the fact that, and it is worth noting that "
    "have a short plain form: to, because, and nothing. "
    "Keep at most one hedge in a sentence. "
    "A stack such as it could perhaps be argued that or it may possibly be the case that "
    "is not more careful, it is only less clear. "
    "A single hedge stays only when the writer means it."
)

# Prompt text for stages 5–8, including a diary. Not a hard fail.
# A template opener repeats across paragraphs and could sit on any assignment.
TEMPLATE_OPENERS = (
    "Do not start more than one paragraph with the same words. "
    "An opener such as In today's world, Throughout history, or This essay will discuss "
    "could sit on any assignment, so cut it and start on the claim. "
    "Repeating a key term is not the same thing."
)

# Prompt text for stages 5–8, including a diary. Not a hard fail.
# Student prose speaks as the student, never as the writing tool that produced it.
NO_ASSISTANT_VOICE = (
    "Do not write as an assistant or as a model. "
    "No note that the writer is an AI, no apology for a model limit, and no offer to keep helping. "
    "The essay speaks as the student, not as a tool."
)

# Prompt text for stages 5 and 8, including a diary. Not a hard fail.
# A claim may not be stronger than the evidence under it. No invented limit.
EVIDENCE_STRENGTH = (
    "A claim is no stronger than the evidence under it. "
    "One case does not show a general trend, a correlation does not show a cause, "
    "and a small sample does not show a wide effect. "
    "Keep the limit the source states, and if it states none, "
    "write the claim at the size the evidence supports."
)

# Prompt text for stages 5 and 8, including a diary. Not a hard fail.
# An unsettled point is said out loud. The gap is not filled with a claim.
OPEN_GAP = (
    "When the sources you opened do not settle a point, say that the evidence is mixed or thin. "
    "Do not fill the gap with an assertion, and do not present one source as the settled view. "
    "A gap is part of the answer, not a line to hide."
)

# Prompt text for stages 5 and 8, including a diary. Not a hard fail.
# A part serves a listed criterion. No criterion or weighting is invented.
MARK_TABLE_LEAN = (
    "When the brief or the mark scheme lists marking criteria, each part of the draft serves one of them. "
    "Use the criteria it lists and no others: do not add a criterion, a weighting, or a band the brief does not print. "
    "A point that serves no listed criterion still has to answer the question."
)

# Rules 1, 2, 6, 7, and 8 for stages 5 and 8. Rules 3–5 sit in ANTI_GLUE and
# VOICE_LIMIT so stages 6 and 7 carry them too. Prompt text only. Not a hard fail.
CRAFT_COMMITMENT = (
    "Keep the commitment the writer means. "
    "Where they are unsure, keep a modal or an epistemic marker they would say. "
    "Where they endorse or resist a source, use a reporting verb that matches. "
    "Do not flatten a hedged claim into a bare assertion, and do not add a hedge they did not mean."
)
CRAFT_ANCHOR = (
    "Tie each claim to one thing the writer can point at: a passage, a figure, a date, a result, "
    "or a scene in the course text. "
    "If the sentence could open any essay on the topic, it is still a summary. "
    "Replace it with the specific thing this assignment is about."
)
CRAFT_REVISE = (
    "Revise for what a reader still cannot see: cut, reorder, and add. "
    "If a chatbot produced the paragraph, rewrite the ideas in the writer's sentences. "
    "Change the words, reorder, delete, and add. "
    "Do not polish the model's sentences in place."
)
CRAFT_SOURCES = (
    "Every source sentence comes from a source the writer opened. "
    "A paraphrase keeps that source's specific claim. "
    "Delete a citation or a paraphrase they cannot find in the opened file. "
    "Do not list a writing tool as an author."
)
CRAFT_REFUSAL = (
    "Write for the brief and the handbook. "
    "No planted errors, no forced slang, no forced first person, and no synonym spinning. "
    "Do not chase a third-party similarity or AI-score number; "
    "that number is not the target."
)
CRAFT_LINES: tuple[str, ...] = (
    CRAFT_COMMITMENT,
    CRAFT_ANCHOR,
    CRAFT_REVISE,
    CRAFT_SOURCES,
    CRAFT_REFUSAL,
)

# Prompt text only. A skipped plan ask stays empty. Not a hard fail.
ENCOURAGE_FACT_RULE = (
    "Use a section lean, an example, or a surprise only when the student gave that detail after the plan was saved. "
    "A skip or silence leaves that slot empty. Do not invent that detail."
)


def voice_limit_sha() -> str:
    """Stable id for the stage 5–8 voice limit. PR bodies cite this."""
    import hashlib

    return hashlib.sha256(VOICE_LIMIT.encode("utf-8")).hexdigest()

# Stage keys match checklist steps 1–10 (4a / 4b split at research).
CHECKLISTS: dict[str, tuple[str, ...]] = {
    "1": (
        "Respond to the question. Split the brief into task words, content words, and limiting words.",
        "The task word sets the shape of the answer. Use the clue-word list in docs/academic-writing-helpers.md. Discuss is for and against, then a conclusion. Compare is similarities and differences. Contrast is differences. Evaluate is a supported judgement with advantages and disadvantages. Do not treat clue words as the same job.",
        "Content words set the topic. Limiting words narrow it. The required length sets how much research and how deep.",
        "Note assessment rules and formatting from the course outline. The module brief still wins.",
        "Genre-from-brief: essay, report, or a reflective diary of entries (MOD1004AA = report). A reflective section inside an essay or a report stays that kind of writing. Do not default to essay shape.",
        "Marking guideline or rubric noted before you approve later saves.",
        "Listed mark-scheme sections and the brief's own word-count or section-length rules win over these helpers and sample notes. Do not invent a word budget or per-section count the brief and rubric do not state.",
        "If the brief names a database, keep that name and a slot for a file the student holds. Do not look that database up, and do not store a folder path.",
    ),
    "2": (
        "Record an initial response, possible answers, opinions, and what you already know, including related topics or frameworks, before the lock. An essay records this before the thesis is locked. A report records this before purpose and scope are locked.",
        "Question the terms. Is there an agreed approach? If not, how the approaches differ, which one you will use, and how the key concepts relate. On a report, those terms apply to purpose and scope.",
        "Broaden first (brainstorm, keep the ideas), then narrow. On an essay, the locked thesis is the narrowed claim. On a report, the locked purpose and scope is the narrowed claim.",
        "An essay thesis answers the question in one or two sentences you can discuss throughout. A report locks purpose and scope.",
        "The essay is balanced. Opposing views are examined only when a gathered source states them.",
        "Argument direction clear before you approve this save. Genre-from-brief still respected.",
    ),
    "3": (
        "An essay plan holds the thesis and the main points as the reasons for that answer, in logical order. A report plan holds the central theme and the headed sections that develop it.",
        "Scale the number of points to the length. An essay of about 1,000 to 1,500 words aims for 3 to 4 main points. A longer report scales its points to that length and to its sections.",
        "An essay plan outlines the introduction, the body, and the conclusion. A report plan uses the brief’s sections and the report section jobs in docs/academic-writing-helpers.md.",
        "Each main point has room for reasoning and gathered evidence, and names sources you expect to use.",
        "Revise the plan after research. If the plan is itself assessed, follow that assessment’s form.",
        "Genre-from-brief: essay flow versus report sections. Do not default to essay shape.",
        "Section headings and word weights in the plan follow only what the brief, rubric, or mark scheme lists. Do not invent a section list or word budget.",
        "When the student hands in an outline or their own prose, that outline is the plan. Keep its headings and their order, and do not add a section the outline does not name.",
    ),
    "4a": (
        "Gathered sources only (do not invent sources). Choose sources that answer the question, cover more than one view, and include the key works.",
        ANNOTATION_SENTENCES,
        "Evidence vs claim: what the source shows versus what you will argue.",
        FOUR_A_FORMAT,
        "download-list.docx is leftovers only: gathered sources not already in the papers zip, plus failed look-up addresses that are not saved PDFs. Do not repeat citation lines from annotation.docx.",
        "When you name other gathered sources or free alternatives already found after this save, speech only. Do not open a new look-up or free-alt download in this step.",
        "After this save is approved, a later download step can fetch leftover free alternatives already found. That step does not open a new look-up and does not invent an address.",
        "The citation year is the year in the PDF page title or header. Do not use the file's modified time as the year.",
        "An abstract-only source stays on download-list.docx until a PDF of that source is opened. It is not an annotated-bibliography entry before that PDF is opened.",
        "A PDF larger than 20MB is read in parts on this machine. Each part stays readable. A part that cannot be read is recorded for the later citation pass. The PDF bytes stay on this machine.",
        "Before a Word file or a zip is handed across, clear the Mac quarantine mark and the provenance mark on the Documents copy. If those marks are absent, leave the file unchanged.",
        "A database the brief names is not a look-up. The file the student holds fills that slot. Do not store a folder path.",
        KNOWN_PATHS_LINE,
    ),
    "4b": (
        "When you offer the step into critical review after 4a, include option C: Download leftovers first. The library guide is for after the person fetches those files; do not fetch those files for them during file work.",
        "Before the step into the critical review is saved, compare download-list.docx with PDF files already on disk and in Documents only when that path is already named. Do not search the home folder, whole Documents, or whole Volumes. Do not treat the papers zip as the only copy. When a listed source now has a PDF, refresh the annotated bibliography and the papers zip, say what is saved and what is still leftover, then ask to save. Include option C: Download leftovers first.",
        KNOWN_PATHS_LINE,
        "Open each critical-review markdown file on disk before that note is kept, including when a subagent writes the note. The critical note names grok-4.7.",
        "A critical review judges the text. It is not a negative attack. Read the content, the purpose, the audience, and how the text is built.",
        "Record the aim, the methods, the scope, what the text adds, what it leaves out, and whether the conclusions follow from the evidence.",
        "Evidence vs claim. Bias, validity, and reliability only from the gathered text. Opposing views only if a gathered source states them. Do not invent them.",
        "Fit to the argument on the papers you will use.",
        "When the assignment is itself a critical review: introduction with author, title, topic, aim, findings, and your overall judgement; a summary of about a quarter to a third; a critique ordered by importance or by criterion; a conclusion that restates the judgement. The brief wins on structure.",
    ),
    "5": (
        "Write the report or the essay as an argument that answers the question. The critical-review notes are evidence for that argument. Do not paste those notes in as the draft.",
        "The draft shows the framework, how you will answer, and which gathered evidence and examples you will use. It is not the final essay.",
        "Essay introduction follows this argument: a thesis that answers the question, and a road map of the main ideas. Do not open with a general sentence built only from the topic nouns.",
        "The body answers by developing the discussion. It shows grasp of what you read, with exposition, evidence, and relevant examples.",
        "If the question has more than one part, give each part its own stretch of the body.",
        "Each body paragraph is one idea: a topic sentence, supporting sentences, evidence or an example, and analysis of why that evidence matters. A paragraph closer must not only restate the topic sentence. Make it assignment-specific: a cited finding, a limit, or a figure.",
        "Essay conclusion stays with this argument and adds no new information. Do not close with an automatic In conclusion that only restates the topic. End on an assignment-specific cited finding, a limit, or a figure.",
        "Paraphrase, summary, and quotation follow the source-use note in docs/academic-writing-helpers.md.",
        "In-text citations are Harvard Referencing: family name and year. The first Word reference list uses each gathered source in full (author, year, title, and publisher or URL when that source has them). Do not leave a surname alone as the entry.",
        "Report briefs use the report section jobs in docs/academic-writing-helpers.md, not this essay shape. A reflection section uses the reflective-writing note. A case analysis uses the case-analysis note.",
        "Opposing views only from gathered material. Do not invent sources. Approve the draft before treating it as locked for Word.",
        "Do not set the conclusion label to noted or open on the Word cover. The person chooses that on validate before Word.",
        "Do not write an independent re-review or mark your own essay passed. Only the separate reviewer records a pass.",
        "The entire first-draft stage is AI-authored. The person does not read or edit Word in this stage.",
        "On first use in student-facing prose, gloss jargon and acronyms in plain English (for example GHG Scope 1, 2, and 3). The example is not a closed list.",
        "Plain-English gloss only. Do not invent a company's methods or data practices. Name a method only when an opened gathered file states it in a sentence you can point to.",
        "Chat for this step stays quiet. Do not paste this checklist into the chat, and do not name a file path. The person sees the finished first draft after the save. A middle pass stays quiet unless the draft is blocked.",
        "When the critical-review notes are too long for this step, drop only a repeated model line, then take whole notes in groups that fit, then re-open a source only for a gap that note does not cover. Do not cut off the end of a note without saying so. Do not invent a quotation that is not in the full note. Keep going while a group or a re-opened passage still fits. Stop and tell the person only when none of those ways fits.",
        "When the student supplied an outline or base prose, its headings and their order stay. Add no section and no body text around whatever was gathered, and weave a short cite only where a gathered paper supports the student's own sentence.",
        *CRAFT_LINES,
        EVIDENCE_STRENGTH,
        OPEN_GAP,
        MARK_TABLE_LEAN,
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
    ),
    "6": (
        "Stage 6 is the person's first read and local edit of the draft.",
        "Before a sequence rename or before choosing which Word file is the master copy, ask the person. Do not guess path or filename.",
        "The first read uses chat delivery, or a folder the student already named.",
        "If the expected draft is missing or renamed, ask which Word file is the master copy. Do not guess.",
        "The structure is clear: introduction, body, and conclusion, or the report’s sections. Ideas move in stages, and the link between major points is explicit.",
        "Each paragraph is one idea that supports the thesis or the report’s purpose, with a topic sentence. Transitions are varied.",
        "The question is still fully answered. Every major point relates to the question. Cut repetition and unrelated material.",
        "Evidence is relevant and tied to the argument. Quotes and paraphrases use Harvard Referencing in the text: family name and year, matching the reference list. The first Word file prints each gathered source as a full reference entry (author, year, title, and publisher or URL when that source has them). A surname alone is not an entry. Stage 9 still checks pages and the final list.",
        "Local Word edit. A changed Word upload leaves the parent sequence in place and rolls forward onto the next sequence.",
        "Do not tighten prose below what the opened Word file already says. Word-band cuts must not turn a true sentence into a false one.",
        "On first use in student-facing prose, gloss jargon and acronyms in plain English (for example GHG Scope 1, 2, and 3). The example is not a closed list.",
        "Plain-English gloss only. Do not invent a company's methods or data practices. Name a method only when an opened gathered file states it in a sentence you can point to.",
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
        "When the student supplied an outline or base prose, the structure stays theirs. A cited point stays to one or two sentences, and an ask to shorten the cites is answered on this save, not left for the reader to trim.",
    ),
    "7": (
        "Read the stage 6 draft, ask questions, then edit from those answers.",
        "Ask about structure, argument, and clarity before any later step. Feedback is tied to the brief or rubric. It is not evidence.",
        "A light check covers currency and academic tone and clarity. It does not open a new look-up.",
        "Heavy file work is a separate file step. Asking, the light check, and edits from answers stay in the chat.",
        "The delta lists every sentence whose claim or limit changed. A glossary line or a locator line is not the whole list.",
        "On this Word save, rewrite first-draft.md in the sequence folder from the saved Word file in the same step. Do not say that path in the chat.",
        "Do not start the later edit, references, or final Word from stage 6. Those steps wait until the questions are asked and the edits from the answers are saved. Each later step is its own run.",
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
    ),
    "8": (
        "Clarity: say the idea outright. Do not leave it to assumed knowledge. Tone is formal, objective, and evidence-based, and it keeps the commitment the writer means. If a chatbot produced a paragraph, rewrite it in the writer's sentences. Academic style is the list in docs/academic-writing-helpers.md.",
        "Paragraphs are in a logical order. Transitions vary. Grammar, spelling, tense, and punctuation are clean. No biased language.",
        "Listed mark-scheme sections and the brief's own word rules win over helper defaults. Do not invent a word budget.",
        "Word count: if under the band, the answer is complete and the evidence is enough. If over the band, cut repetition and detail that does not answer the question.",
        "Do not tighten prose below what the opened Word file already says. Word-band cuts must not turn a true sentence into a false one.",
        "On first use in student-facing prose, gloss jargon and acronyms in plain English (for example GHG Scope 1, 2, and 3). The example is not a closed list.",
        "Plain-English gloss only. Do not invent a company's methods or data practices. Name a method only when an opened gathered file states it in a sentence you can point to.",
        "Essay conclusion: no new information. Report conclusion: summarise and evaluate the findings, with limitations and recommendations only as the report note and the brief allow.",
        "Structure still matches the genre. Approve the save before the tool writes .docx when it does.",
        "This step is only the edit. It does not also write the references or the final Word. The next step is separate.",
        *CRAFT_LINES,
        EVIDENCE_STRENGTH,
        OPEN_GAP,
        MARK_TABLE_LEAN,
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
    ),
    "9": (
        "Final citations and the reference list follow Harvard Referencing in docs/referencing-harvard.md. Not APA and not another Harvard style.",
        "The EndNote style name and any CSL file are read from the checked handbook file docs/referencing-harvard.md. Do not take that name from memory, and do not invent a CSL file.",
        "In text: author and year. Add the page for a point or a quote only when the opened file prints that page. Four or more authors use et al. in the text. Several sources in one citation run from oldest to newest.",
        "The list includes every source you cited, with every author, in file order. The tool does not sort the list and does not add 2018a or 2018b. Do not invent a missing field.",
        "Open the gathered PDF, including a file larger than 2MB. Do not reject a .pdf or a file over 2MB. Verify the author, the year, and the page against the opened paper. A page with no extractable text is recorded and is not quoted. When pdf-read-gaps.json is present, use that record and do not quote the missing part.",
        "Keep the surname from the article's own author line when a download cover or a please-cite token inverts a compound surname. Fosso Wamba stays Fosso Wamba and must not become Wamba, S.F.",
        "Cite a printed page in the text only. An in-text page appears only when the opened file prints that page. In the reference entry, an article number stays in the article-number slot, after the volume and issue. A page from a matching look-up stays: a range is pp. start-end and a single page is p. N, even when the opened file has no lone printed page lines. A page value with no look-up mark that the opened file does not print stays blank. A look-up page value that is an article number, not a page, is stored and printed in the article-number slot. When neither a page nor an article number is on the opened file or the look-up, the page field stays blank. Do not cite the PDF viewer index as a page.",
        "The reference list heading is References. A journal title and a report title are italic. A gathered DOI is printed as Available at: doi:. A missing page, DOI, or other locator stays blank.",
        "Do not invent sources on every citation line.",
        "Do not approve a save if references are unchanged from the last saved draft bundle.",
        "When this save is done, the next step is the final Word, as its own step. A blocked independent review is shown before that Word is written.",
        "On this Word save, rewrite first-draft.md in the sequence folder from the saved Word file in the same step. Do not say that path in the chat.",
    ),
    "10": (
        "From the brief: due date and late penalty, where the work goes, and who receives it.",
        "A cover sheet only if the brief requires one. Formatting and a readable font as the brief requires.",
        "Keep your own copy. Out of MCP — the tool does not submit.",
        "Create Documents/<project>-10/ and a new final Word file there. The file name is not the first-draft name.",
        "Save the independent-review notes and the chat comments as a Word file in that same folder.",
        "The person sees that final Word. This step does not submit.",
    ),
}

STAGE_ORDER: tuple[str, ...] = (
    "1",
    "2",
    "3",
    "4a",
    "4b",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
)

DOOR_STAGES: dict[str, tuple[str, ...]] = {
    "essay.originals": ("1",),
    "essay.research.summary": ("4a",),
    "essay.research.full": ("4a", "4b"),
    "essay.pack.validate": ("5",),
    "essay.pack.render_word": ("5", "7", "8", "9"),
    "essay.revise": ("6", "7", "8"),
}

BASICS_MARKER = "Basics checklist"

# Agent rules for stage 7. Not a checklist bullet: door text cannot name the shells.
STAGE7_AGENT = (
    "Grok Bot reads the stage 6 draft, asks questions, then edits from those answers. "
    "A light check covers currency and academic tone and clarity. "
    "Cursor does heavy file work only. Asking, the light check, and edits from answers stay in the chat."
)

# Client speech lives on the Grok Bot specialist. Overlays still include it.
from essay_writer.specialists.grok_bot import CHECKLIST_WALK as CHECKLIST_WALK  # noqa: F401
from essay_writer.specialists.grok_bot import DOOR_WALK, MCP_DOWN_SPEECH

GENRE_LOCK_LINE = (
    "When the brief is a report, stage 2 locks purpose and scope and stage 3 holds the central theme. "
    "A report has no thesis. An essay keeps the thesis."
)

# Stage prompt and tracking. No save-label "Confirm" (student-surface ban).
SHARED_REVISIT = (
    "After the annotated bibliography and the critical review are saved, revisit the stage 3 plan before the first draft. "
    "Revisit stage 2 only if the research breaks that lock. "
    "On an essay the lock is the thesis. On a report the lock is purpose and scope. "
    "The report’s one-sentence answer is the central theme. A thin edit of that sentence is allowed. A break is not a thin edit. "
    "A report has no thesis. "
    "Check that the section arguments still hold, that the word weights still match the brief, and that each source type is a real title, with gaps named. "
    "The one-sentence answer should still be the best one. "
    "Leave out anything the research never showed. Do not invent sources. "
    "Use only the year printed in the opened source. Do not add a second year. "
    "If anything changes, show what changed and why, from the gathered sources, and record that in the tracking note. "
    "Approve that save again before the first draft. "
    "If the thesis breaks, or if purpose and scope or the central theme breaks, approve stage 2 again and then approve stage 3 again. "
    "Do not silently rewrite the plan into the draft."
)

REPORT_REVISIT = (
    "After the annotated bibliography and the critical review are saved, revisit the stage 3 plan before the first draft. "
    "Revisit purpose and scope only if the research breaks them. "
    "The central theme should still be the best one-sentence answer. A thin edit is allowed. A break is not a thin edit. "
    "A report has no thesis. "
    "Check that the section arguments still hold, that the word weights still match the brief, and that each source type is a real title, with gaps named. "
    "Leave out anything the research never showed. Do not invent sources. "
    "Use only the year printed in the opened source. Do not add a second year. "
    "If anything changes, show what changed and why, from the gathered sources, and record that in the tracking note. "
    "Approve that save again before the first draft. "
    "If purpose and scope or the central theme breaks, approve stage 2 again and then approve stage 3 again. "
    "Do not silently rewrite the plan into the draft."
)

ESSAY_REVISIT = (
    "After the annotated bibliography and the critical review are saved, revisit the stage 3 plan before the first draft. "
    "Revisit the thesis only if the research breaks it. "
    "The thesis should still be the best one-sentence answer. A thin edit is allowed. A break is not a thin edit. "
    "Check that the section arguments still hold, that the word weights still match the brief, and that each source type is a real title, with gaps named. "
    "Leave out anything the research never showed. Do not invent sources. "
    "Use only the year printed in the opened source. Do not add a second year. "
    "If anything changes, show what changed and why, from the gathered sources, and record that in the tracking note. "
    "Approve that save again before the first draft. "
    "If the thesis breaks, approve stage 2 again and then approve stage 3 again. "
    "Do not silently rewrite the plan into the draft."
)

# MCP door text. Confirm is the save label here.
REVISIT_DOOR = (
    "After 4a and 4b Confirm, revisit the stage 3 plan before stage 5. "
    "Revisit stage 2 only if research breaks that lock: the essay thesis, or the report purpose and scope. "
    "The report central theme is the one-sentence answer. A thin edit is allowed. A break is not a thin edit. "
    "Check that section arguments still hold, that word weights still match the brief, and that source types are real titles with gaps named. "
    "invent-forbid: nothing in the plan that the research never showed. "
    "Use only the year printed in the opened source. Do not add a second year. "
    "If anything changes, show the delta and why it comes from the gathered sources, update the tracking note, and Confirm again before stage 5. "
    "If the theme or the purpose breaks, Confirm stage 2 and then Confirm stage 3. "
    "An essay keeps the thesis. A report has no thesis. "
    "Do not silently rewrite the plan into the draft."
)

# Genre overlays for stages 2 and 3. The shared CHECKLISTS stay the router text.
REPORT_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "2": (
        "A report has no thesis. Lock purpose and scope.",
        "Record an initial response, possible answers, opinions, and what you already know, including related topics or frameworks, before purpose and scope are locked.",
        "Question the terms. Is there an agreed approach? If not, how the approaches differ, which one you will use, and how the key concepts relate. Those terms apply to purpose and scope.",
        "Broaden first (brainstorm, keep the ideas), then narrow. The locked purpose and scope is the narrowed claim.",
        "The lock is purpose and scope.",
        "Opposing views are examined only when a gathered source states them.",
        "Argument direction clear before you approve this save. Genre-from-brief still respected.",
    ),
    "3": (
        "A report has no thesis. The plan holds the central theme and the headed sections that develop it, in the brief’s order.",
        "Scale the points to the report’s length and to its sections. The 3 to 4 main points guide is for an essay of about 1,000 to 1,500 words. A longer report scales its points to that length and to its sections.",
        "Each section has room for reasoning and gathered evidence, and names sources you expect to use.",
        "Revise the plan after research. If the plan is itself assessed, follow that assessment’s form.",
        "Genre-from-brief: essay flow versus report sections. Do not default to essay shape.",
        "Section headings and word weights in the plan follow only what the brief, rubric, or mark scheme lists. Do not invent a section list or word budget.",
        "Approve the save before the plan is locked.",
    ),
}

ESSAY_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "2": (
        "Record an initial response, possible answers, opinions, and what you already know, including related topics or frameworks, before the thesis is locked.",
        "Question the terms. Is there an agreed approach? If not, how the approaches differ, which one you will use, and how the key concepts relate.",
        "Broaden first (brainstorm, keep the ideas), then narrow. The locked thesis is the narrowed claim.",
        "The thesis answers the question in one or two sentences you can discuss throughout.",
        "The essay is balanced. Opposing views are examined only when a gathered source states them.",
        "Approve the save before this thesis is treated as locked. Genre-from-brief still respected.",
    ),
    "3": (
        "The plan holds the thesis and the main points as the reasons for that answer, in logical order.",
        "Scale the number of points to the length. For about 1,000 to 1,500 words, aim for 3 to 4 main points.",
        "Outline the introduction, the body, and the conclusion.",
        "Each main point has room for reasoning and gathered evidence, and names sources you expect to use.",
        "Revise the plan after research. If the plan is itself assessed, follow that assessment’s form.",
        "Section headings and word weights in the plan follow only what the brief, rubric, or mark scheme lists. Do not invent a section list or word budget.",
        "Approve the save before the plan is locked.",
    ),
}


# Diary lines for the stages where a diary differs. Shared stages stay, with a diary test added.
DIARY_CHECKLISTS: dict[str, tuple[str, ...]] = {
    "1": (
        "When the brief has an Aim or an Assignment task, restate those words as the ask, including when they are not labelled Question or Task.",
        "How to score high is the top column the mark table prints. If that column cannot be read, leave the gap empty. Do not invent a band name.",
    ),
    "2": (
        "A diary has no thesis. There is no purpose-and-scope lock. Lock the entries the brief names.",
        "For each entry, record the decision or the learning event, the other option or the tension when there is one, and why this is the event to write about.",
        "Record what was done at the time and what would be done with what is known now, when the brief asks for that.",
        "Name the line of learning from the first entry to the last when the brief or the top band asks for learning across the entries.",
        "There is no single sentence the whole diary has to prove.",
        "Record an initial response, then narrow it to the lock. A mind map is not a required step.",
        "The lock is descriptive enough to see what happened, who was involved, and under what conditions. Feeling can be named. The lock is not a feelings diary.",
    ),
    "3": (
        "One part for each entry the brief names, in the brief’s order.",
        "Each part follows the chain, then adapted to the brief: the decision or the event; a theory, model, or source applied to it; the impact the brief asks for, including named goals only when the brief asks; a trade-off, limit, or other reading; what was learned.",
        "Drop a move the brief does not ask for. The moves are the contents of an entry. They are not extra headings.",
        "Only the headings the brief allows.",
        "Plan each entry at the length the brief gives. When the brief states a total and a length for each entry, keep both. When the brief states only a total, still plan a length for each section the brief names. That split is a plan the student can change before it is saved. It is not a rule the brief wrote, and it is not a mark band.",
        "If the per-entry lengths and the total cannot be added up, show the clash. Do not silently pick one.",
        "Sources are named as support for that entry. The plan is not a literature review.",
        "Approve the save before the plan is locked.",
    ),
    "5": (
        "The draft is the entries from the plan, in the voice the brief allows. Each entry walks the chain. Description opens the entry. Analysis applies theory or evidence to the decision or the event. Evaluation judges the impact, including a limit. The writer’s own response says what changed.",
        "In-text citations are Harvard Referencing: family name and year. The first Word reference list uses each gathered source in full (author, year, title, and publisher or URL when that source has them). Do not leave a surname alone as the entry.",
        "Only the headings the brief allows. Do not add an essay introduction and conclusion unless the brief asks for them. Do not add report sections. Do not include a marker comments block.",
        "Word counts follow the brief. An entry length stays on the entry, and the total stays on the whole body.",
        "Opposing views only from gathered material. Do not invent sources. Approve the draft before treating it as locked for Word.",
        "Do not write an independent re-review or mark your own essay passed. Only the separate reviewer records a pass.",
        "Chat for this step stays quiet. Do not paste this checklist into the chat, and do not name a file path. The person sees the finished first draft after the save. A middle pass stays quiet unless the draft is blocked.",
        "When the critical-review notes are too long for this step, drop only a repeated model line, then take whole notes in groups that fit, then re-open a source only for a gap that note does not cover. Do not cut off the end of a note without saying so. Do not invent a quotation that is not in the full note. Keep going while a group or a re-opened passage still fits. Stop and tell the person only when none of those ways fits.",
        *CRAFT_LINES,
        EVIDENCE_STRENGTH,
        OPEN_GAP,
        MARK_TABLE_LEAN,
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
    ),
    "6": (
        "On a diary, the read checks the headings the brief allows, the word counts, the chain in every entry, the voice the brief allows, and learning across the entries when that was asked for.",
    ),
    "7": (
        "On a diary, ask whether each decision or event is explicit and tied to the occasion the brief names, whether a theory or a source is applied to it, whether the impact the brief asks for is judged, including a limit where one is claimed, whether the reasoning holds inside the entry and across the entries, whether there are only the headings the brief allows, whether the word counts sit inside the brief’s allowance, and whether the title page and identity follow the brief.",
    ),
    "8": (
        "The edit improves the diary. It does not turn it into a third-person essay, and it does not add a report conclusion, unless the brief asked for that shape.",
        "Cuts remove repetition. They do not turn a true sentence into a false one.",
        "Entries that are over or under a per-entry allowance are brought inside it, and the whole piece is brought inside the overall allowance.",
        "The brief’s headings stay. Listed mark-scheme sections and the brief's own word rules win over helper defaults. Do not invent a word budget or a mark band.",
        "Approve the save before the tool writes .docx when it does.",
        "This step is only the edit. It does not also write the references or the final Word. The next step is separate.",
        *CRAFT_LINES,
        EVIDENCE_STRENGTH,
        OPEN_GAP,
        MARK_TABLE_LEAN,
        ANTI_GLUE,
        VOICE_LIMIT,
        PLAIN_WORDS,
        NO_ASSISTANT_VOICE,
        TEMPLATE_OPENERS,
        ENCOURAGE_FACT_RULE,
    ),
}

DIARY_REPLACE = frozenset({"2", "3", "5", "8"})

DIARY_REVISIT = (
    "After the annotated bibliography and the critical review are saved, revisit the stage 3 plan before the first draft. "
    "Revisit the entries only if the research breaks a decision or an event. "
    "A thin edit stays on the plan. A break is not a thin edit. "
    "A diary has no thesis. "
    "Check that each entry’s chain still holds, that the word weights still match the brief, and that each source type is a real title, with gaps named. "
    "Leave out anything the research never showed. Do not invent sources. "
    "Use only the year printed in the opened source. Do not add a second year. "
    "If anything changes, show what changed and why, from the gathered sources, and record that in the tracking note. "
    "Approve that save again before the first draft. "
    "If a decision or an event breaks, approve stage 2 again and then approve stage 3 again. "
    "Do not silently rewrite the plan into the draft."
)


def basics_lines(stage: str, genre: str | None = None) -> tuple[str, ...]:
    """Shared router bullets, or the essay, report, or diary lines for the stages that differ."""
    if genre == "diary":
        special = DIARY_CHECKLISTS.get(stage)
        if special and stage in DIARY_REPLACE:
            return special
        shared = CHECKLISTS.get(stage, ())
        if special:
            return shared + special
        return shared
    if genre == "report":
        special = REPORT_CHECKLISTS.get(stage)
        if special:
            return special
    elif genre == "essay":
        special = ESSAY_CHECKLISTS.get(stage)
        if special:
            return special
    return CHECKLISTS.get(stage, ())


def revisit_note(stage: str, genre: str | None = None) -> str:
    """Post-research plan check. Stage 2 reopens only when the research breaks the lock."""
    if stage not in {"2", "3", "4a", "4b", "5"}:
        return ""
    if stage == "2":
        if genre == "report":
            return (
                "After research is saved, reopen purpose and scope only if those gathered sources break them. "
                "A thin edit of the central theme stays on the plan. "
                "If purpose and scope or the central theme breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        if genre == "essay":
            return (
                "After research is saved, reopen the thesis only if those gathered sources break it. "
                "A thin edit stays on the plan. "
                "If the thesis breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        if genre == "diary":
            return (
                "After research is saved, reopen the entries only if those gathered sources break a decision or an event. "
                "A thin edit stays on the plan. "
                "If a decision or an event breaks, approve this stage again and then approve the plan again before the first draft. "
                "Do not silently rewrite the plan into the draft."
            )
        return (
            "After research is saved, reopen this lock only if those gathered sources break it. "
            "On an essay the lock is the thesis. On a report the lock is purpose and scope. "
            "A thin edit of the central theme stays on the plan. "
            "If the lock or the central theme breaks, approve this stage again and then approve the plan again before the first draft. "
            "Do not silently rewrite the plan into the draft."
        )
    if genre == "report":
        return REPORT_REVISIT
    if genre == "essay":
        return ESSAY_REVISIT
    if genre == "diary":
        return DIARY_REVISIT
    return SHARED_REVISIT


def genre_lock(stage: str, genre: str | None = None) -> str:
    """Front of the shared overlay. A known genre uses its own bullets instead."""
    if genre in {"essay", "report", "diary"} or stage not in {"2", "3"}:
        return ""
    if stage == "2":
        return (
            "Chat shows one label, the brief’s. "
            "An essay locks a thesis. "
            "A report locks purpose and scope. A report has no thesis."
        )
    return (
        "Chat shows one label, the brief’s. "
        "An essay plan holds the thesis. "
        "A report plan holds the central theme and the brief’s headed sections. "
        "A report has no thesis."
    )


def basics_block_markdown(stage: str) -> str:
    """Markdown block under a stage heading in docs."""
    lines = basics_lines(stage)
    if not lines:
        return ""
    bullets = "\n".join(f"- {line}" for line in lines)
    return f"**{BASICS_MARKER}:**\n{bullets}\n"


def basics_prompt_suffix(tool: str) -> str:
    """Short suffix for MCP door descriptions the BO LLM reads."""
    stages = DOOR_STAGES.get(tool, ())
    if not stages:
        return ""
    parts: list[str] = []
    for stage in stages:
        items = basics_lines(stage)
        if items:
            joined = "; ".join(items)
            parts.append(f"{BASICS_MARKER} (Basics {stage}): {joined}")
    if not parts:
        return ""
    text = " " + " ".join(parts) + " " + DOOR_WALK
    if set(stages) & {"4a", "4b", "5"}:
        text += " " + REVISIT_DOOR
    return text


SERVER_BASICS_NOTE = (
    MCP_DOWN_SPEECH
    + " "
    + "Before each stage save, the chat opens with a short Basics pass. "
    "The first three lines are what the mark scheme scores, the format the brief names, "
    "and the assignment question in the student's words. Later bullets stay short. "
    "Delivering annotation.docx alone is not this pass. "
    "The rest of the checklist is explicit in the stage prompt and in the tracking note. "
    "Record the answers in tracking/<stage>.md. "
    "Do not paste the rest of the Basics checklist into the student chat. "
    "Stage 5 stays quiet and does not paste the whole checklist. "
    "Student-facing chat is warm, helpful, encouraging, and concise: only what the person must know. "
    "A bullet list or a table is fine when the content is long. "
    "Limits the person must know, such as Stage 1 limiting conditions, always appear in that prose. "
    "The chat outcome is natural helper prose and a clean Confirm. "
    + GENRE_LOCK_LINE
    + " Chat shows one label, the brief’s. "
    "The rules are the Basics checklist for that stage "
    "(docs/academic-writing-helpers.md and essay_writer.writing_basics), "
    "loaded from stage_settings rules. Follow every line. "
    "The checklist is the writing base for the stage, not an optional note. "
    "Clue words, essay and report shape, source use, "
    "and academic style are in that note. References and the final citation pass are "
    "Harvard Referencing at stage 9, as in "
    "docs/referencing-harvard.md, not APA or another Harvard style."
)
