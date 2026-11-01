"""Essay door catalogue. Health and the MCP server both read this list."""

from __future__ import annotations

from typing import Any

from essay_writer.setup import CARD_RULES
from essay_writer.stage_llm import (
    stage_llm_suffix,
    stage_rule_suffix,
    stage_tool_description,
)
from essay_writer.writing_basics import basics_prompt_suffix

DOORS: tuple[dict[str, Any], ...] = (
    {
        "id": "health",
        "tool": "essay.health",
        "confirm": None,
        "read_only": True,
        "requires": [],
        "writes": None,
        "description": (
            "Essay: essay.health (read-only). The door is alive, and the essay doors "
            "and packs on disk are listed. No student names and no essay body."
        ),
    },
    {
        "id": "debug.wipe",
        "tool": "essay.debug.wipe",
        "confirm": None,
        "read_only": False,
        "requires": ["speech"],
        "writes": "clears operator run logs in the app folder",
        "description": (
            "Essay: essay.debug.wipe (operator speech only). "
            "When the operator asks to delete the logs, clear the run log, "
            "or clearly means wipe the shell logs in the app folder, "
            "call with speech set to what they said. "
            "One call clears the prose run log and the structured ML JSONL together. "
            "Draft-then-confirm does not apply. No chat card. "
            "Student chat does not name those files."
        ),
    },
    {
        "id": "debug.export",
        "tool": "essay.debug.export",
        "confirm": None,
        "read_only": False,
        "requires": [],
        "writes": "one zip of operator run logs already on disk",
        "description": (
            "Essay: essay.debug.export (operator). "
            "When the operator asks for the run logs in one file, call this. "
            "One call packs the logs that are already on disk. "
            "A missing log stays missing. An empty pack is refused. "
            "Draft-then-confirm does not apply. No chat card. "
            "Student chat does not name those files. "
            "Use zip-for-ferry. Do not paste a truncated run log into chat."
        ),
    },
    {
        "id": "originals",
        "tool": "essay.originals",
        "confirm": None,
        "read_only": True,
        "requires": ["essay_id"],
        "writes": None,
        "description": (
            "Essay: essay.originals (read-only). List or read uploads and the brief "
            "for one module, or for a sequence id such as MOD1011AA-5. "
            "Uploads and the brief are shared by every sequence of that module. "
            "A path that leaves that module is refused."
        ),
    },
    {
        "id": "research.summary",
        "tool": "essay.research.summary",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "topic", "confirmPhase"],
        "writes": "confirmed research summary",
        "description": (
            "Essay: essay.research.summary (Confirm two-step — draft, show the human, "
            "then the same arguments with confirmPhase confirm; never silent). "
            "essay_id is a sequence id such as MOD1011AA-5. A bare module code is refused "
            "and nothing is written beside sequences/. "
            "Say that reply to the user. File work does not own the chat. "
            "Choices are stored on that sequence. Uploads stay on the module. "
            "Summarises only gathered sources for this essay id. invent-forbid: do not "
            "invent authors, titles, years, quotations, pages, DOIs, or journals. "
            "Does not call a resolver. "
            "Confirm delivers annotation.docx in the chat, download-list.docx as Word "
            "(leftovers only — not citation lines already on annotation.docx or PDFs "
            "already in the zip), and a zip of real PDFs only. The reply includes a links card "
            "with a title and a URL for each source that still needs a PDF. A saved PDF is not "
            "on that card. Draft writes none of those files. "
            "The files are the same for either mid-office pick."
        ),
    },
    {
        "id": "research.full",
        "tool": "essay.research.full",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "topic", "confirmPhase", "clarify_context"],
        "writes": "confirmed full research",
        "description": (
            "Essay: essay.research.full (Confirm two-step — draft then confirm; never "
            "silent). confirmPhase and topic are required. clarify_context needs "
            "objective, background, issues, and guidance, each an answer or "
            "leave_open true. leave_open is the human's choice, never the model's default. "
            "packs is optional, at most two names from essay.health local_packs; never invent one. "
            "exclude_section_ids, industry, and host_voice are optional. "
            "Clarify answers, industry, host_voice, and a named pack are not evidence. "
            "Confirm writes one Word file per paper in critical-reviews.zip. "
            "Draft writes neither. The files are the same for either mid-office pick."
        ),
    },
    {
        "id": "pack.validate",
        "tool": "essay.pack.validate",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "pack", "confirmPhase", "confirmed research"],
        "writes": "validation record for this pack",
        "description": (
            "Essay: essay.pack.validate (Confirm two-step). Checks one essay pack "
            "before Word: one essay id, sources covered by confirmed research, "
            "invent-forbid, Harvard Referencing, no student name or number, "
            "and a human choice of noted or open conclusion. "
            "A noted conclusion needs gathered excerpt support; open is allowed when support is thin. "
            "The door does not change open into noted. A changed pack needs a fresh draft. "
            "The first draft is authored from the stage 4b critical-review markdowns, "
            "one markdown per paper. Pass critical_reviews on the pack. "
            "Re-open a source paper only with reopen when that markdown does not cover the gap."
        ),
    },
    {
        "id": "pack.restore",
        "tool": "essay.pack.restore",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "snapshot", "confirmPhase"],
        "writes": "restores one snapshot of pack JSON, annotation report, and review markdown",
        "description": (
            "Essay: essay.pack.restore (Confirm two-step). "
            "Restores one snapshot already stored under backups/<essay_id>/ "
            "so the pack and any critical-review markdowns are usable again. "
            "snapshot is the snapshot id. "
            "A missing snapshot is refused. A damaged snapshot is refused. "
            "Review text is copied from that snapshot only. "
            "Draft writes nothing. Confirm writes that snapshot only."
        ),
    },
    {
        "id": "pack.render_word",
        "tool": "essay.pack.render_word",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "pack", "confirmPhase", "confirmed validation"],
        "writes": "docx",
        "description": (
            "Essay: essay.pack.render_word (Confirm two-step). Draft writes nothing. "
            "Confirm writes a .docx only for the same pack after validation confirm. "
            "The essay id must be a sequence id. A bare module code is refused, so Word is not "
            "written at Essay-writer/<module>/output/. "
            "Say that reply to the user. File work does not own the chat. "
            "A sequence id writes that sequence's Word file, not the module's other sequences. "
            "Word only. No student name unless the assignment record requires it. "
            "When that record requires a registration number, print the number stored on the sequence. "
            "Do not invent it. Put the page number where the record says. "
            "Never confirm a changed pack. "
            "The first draft is authored from the stage 4b critical-review markdowns, "
            "one markdown per paper. Pass critical_reviews on the pack. "
            "Re-open a source paper only with reopen when that markdown does not cover the gap. "
            "Pass stage 6 for the first Word file or stage 9 for the final Word file. "
            "Those paths need an EQR PASS from the reviewer seat. This writer door does not review itself."
        ),
    },
    {
        "id": "stage",
        "tool": "essay.stage",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "stage", "confirmPhase"],
        "writes": "tracking/<stage>.md and tracking/stage.json on confirm",
        "description": stage_tool_description(),
    },
    {
        "id": "revise",
        "tool": "essay.revise",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "message", "confirmPhase", "a confirmed research or Word run"],
        "writes": "revision note",
        "description": (
            "Essay: essay.revise (Confirm two-step). The essay id is a sequence id. "
            "Records feedback on this same "
            "essay after research or Word confirm. Does not write a new .docx and "
            "does not replace the Word confirm. Invented citations in the note are refused."
        ),
    },
    {
        "id": "shelf.put",
        "tool": "essay.shelf.put",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "pack", "confirmPhase", "Word confirm for that pack"],
        "writes": "local shelf record",
        "description": (
            "Essay: essay.shelf.put (Confirm two-step). Stores a Word-confirmed pack "
            "on that sequence's shelf (Essay-writer/<module>/sequences/<n>/shelf), "
            "not on the module root. The essay id is a sequence id. It is local to that sequence. "
            "Say the draft path to the user."
        ),
    },
    {
        "id": "shelf.get",
        "tool": "essay.shelf.get",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "pack_id", "confirmPhase"],
        "writes": None,
        "description": (
            "Essay: essay.shelf.get (Confirm two-step). Draft returns the label for "
            "this essay id. Confirm returns the pack. Another essay's shelf is refused."
        ),
    },
    {
        "id": "setup",
        "tool": "essay.setup",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["confirmPhase"],
        "writes": "app folder, KB1 vault, door tree, setup record",
        "description": (
            "Essay: essay.setup (Confirm two-step). "
            "Say the reply to the user. File work does not own this chat. "
            "Draft writes nothing. Confirm creates the app folder, the KB1 vault, and "
            "the door folders later doors read (Essay-writer, uploads, unassigned) "
            "on the cloud computer when called with no paths. "
            "A named pair of paths saves on this computer. Only a path you name on this computer is accepted. "
            "Documents is not a fallback and is not labelled as the cloud. "
            "A Consensus key and an Unpaywall email are collected on the secret card and are not repeated. "
            "A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. "
            + CARD_RULES
            + " The file-work host is stored once and defaults to agent --version at setup. Pass "
            "the alternate only when the user asks for grok version instead. Change it only by "
            "running setup again. "
            "The version check matches that choice. This door reports that version. "
            "It does not install grok and does not install on the Mac. "
            "Does not write notes."
        ),
    },
    {
        "id": "projects",
        "tool": "essay.projects",
        "confirm": None,
        "read_only": True,
        "requires": ["view"],
        "optional": ["module"],
        "writes": None,
        "description": (
            "Essay: essay.projects (read-only). view continue lists every active module. "
            "Each row is the last-saved sequence id, such as MOD1011AA-5, on essay_id and "
            "sequence_id. If the last sequential id is a different sequence, both are shown. "
            "If they are the same, it is shown once. Rows with sequences offer roll_forward_ask "
            "and list sequences to copy. view roll-forward with module names one module and sets "
            "sequence_pick true so the user chooses a parent; the next id is last+1 on that module. "
            "Then call essay.sequence.new with that parent. "
            "A module with no sequence asks whether to start a new one. "
            "Say this list to the user. File work does not own the chat. "
            "view archive, delete, or unarchive lists module codes only."
        ),
    },
    {
        "id": "project.archive",
        "tool": "essay.project.archive",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["module", "confirmPhase"],
        "writes": "archive marker for every sequence of the module",
        "description": (
            "Essay: essay.project.archive (Confirm two-step). Hides one module and "
            "every sequence under it. The list is the module code, not each sequence id."
        ),
    },
    {
        "id": "project.unarchive",
        "tool": "essay.project.unarchive",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["module", "confirmPhase"],
        "writes": "removes the archive marker",
        "description": (
            "Essay: essay.project.unarchive (Confirm two-step). Returns one module "
            "to the continue list. Name the module code."
        ),
    },
    {
        "id": "project.delete",
        "tool": "essay.project.delete",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["module", "confirmPhase"],
        "writes": "removes the module workspace, named Word and zip copies, or both",
        "description": (
            "Essay: essay.project.delete (Confirm two-step). "
            "Ask which module, then where: grokbot (this essay workspace only), "
            "local (named Word and zip copies on the student's computer only), or both. "
            "Leaving where off stays workspace-only and does not remove files on the student's computer. "
            "Draft lists every sequence id and the upload, brief, and KB1 files when the workspace is in scope, "
            "and each localPaths Word or zip path when local is in scope. Draft writes nothing. "
            "This tool does not search the computer for copies. "
            "When where is both and localPaths is omitted, a Word or zip path already stored for that sequence is used, "
            "or the stored paths across the sequences when the whole module is removed, "
            "and the default handoff names when this computer can see the files. "
            "Ask for the path only when none are there. A path the caller names is the list. "
            "where local still needs each path the student names. Do not search the computer. "
            "The draft returns a Confirm card. Confirm deletes only after the person picks "
            "Confirm on that card, with cardAction confirm and cardDigest from the card. "
            "A typed yes does not remove anything. "
            "A local or both confirm must say those files on the student's computer will be removed. "
            "Never remove a local file unless where is local or both. "
            "A local file is removed only when it is a regular .docx or .zip this computer can already see. "
            "Pass sequence as one sequence id, such as MOD1004AA-2, to remove only that sequence "
            "after the same draft then confirm. Other sequences, the brief, and uploads stay. "
            "Omit sequence to remove the whole module."
        ),
    },
    {
        "id": "sequence.new",
        "tool": "essay.sequence.new",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["module", "confirmPhase"],
        "writes": "a new sequence cloned from the parent",
        "description": (
            "Essay: essay.sequence.new (Confirm two-step). Starts the next sequence "
            "id on the module (last folder number plus one). The parent is the last-saved "
            "sequence unless parent names another existing sequence id on that module. "
            "The new id is always last+1, not parent+1. Ask before confirm. "
            "The copy is published in one step; a failed copy is not kept. "
            "Copies the parent sequence's own files and updates them, including the "
            "sequence id on the Word cover. Uploads, "
            "the brief, and KB1 paper notes stay shared on the module. "
            "When a sequence opens, post only the Confirm card in that door result. "
            "That card's sequence id is the sequence that opened. "
            "Do not post a Confirm from another sequence. "
            "Ask the user before confirm. File work does not own the chat."
        ),
    },
    {
        "id": "unassigned.collect",
        "tool": "essay.unassigned.collect",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["confirmPhase"],
        "writes": "moves loose files into unassigned/",
        "description": (
            "Essay: essay.unassigned.collect (Confirm two-step). Draft lists loose "
            "files and writes nothing. Confirm moves files that are not inside a "
            "module folder into unassigned/. READMEs stay. Does not choose a module."
        ),
    },
    {
        "id": "dig",
        "tool": "essay.dig",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "query", "confirmPhase"],
        "writes": "dig-card.json and dig-card.md; real PDFs; download-list.docx for failed downloads; annotation.docx when the download path stops; papers.zip of real PDFs only",
        "description": (
            "Essay: essay.dig (Confirm two-step). Draft writes nothing. Confirm writes "
            "a local dig-card.json and dig-card.md on the sequence. OpenAlex runs without "
            "a key. Unpaywall runs only when an email is already stored; skipping the email "
            "is fine. A Consensus key turns Consensus on for the search. No key leaves Consensus off and the search stays on OpenAlex. "
            "ESSAY_WRITER_CONSENSUS=0 turns Consensus off. ESSAY_WRITER_CONSENSUS=1 turns it on when a key is present. "
            "Consensus Free or Pro is the tier the look-up returns. "
            "Confirm downloads an open copy only when the response is a real PDF "
            "(content-type and %PDF- magic). An HTML abstract page, a 404, a paywall, or an "
            "empty file is not a paper and is written to download-list.docx. Valid PDFs are kept. "
            "The same failed address stops after 3 tries. The path also stops when more than "
            "10 minutes pass with no new PDF. Confirm then writes annotation.docx and the "
            "download list from the files already saved, and names what is still missing. "
            "The annotation Word file is for the chat. download-list.docx is Word. "
            "The reply includes a links card with a title and a URL for each file that was not saved. "
            "A saved PDF is not on that card. "
            "The papers zip contains real PDFs only. "
            "Do not retry a stopped address. "
            "invent-forbid: hits are look-up records only. Do not invent a paper."
        ),
    },
    {
        "id": "download.leftovers",
        "tool": "essay.download.leftovers",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["essay_id", "confirmPhase"],
        "writes": "real PDFs and the download list for leftover addresses already stored",
        "description": (
            "Essay: essay.download.leftovers (Confirm two-step). After the annotated "
            "bibliography is confirmed, draft lists leftover free-alternative addresses "
            "already stored and writes nothing. Confirm fetches those stored addresses "
            "only. It does not open a new look-up. It does not call Consensus or Unpaywall. "
            "It does not invent an address. A real PDF is the only file kept."
        ),
    },
    {
        "id": "gates",
        "tool": "essay.gates",
        "confirm": None,
        "read_only": True,
        "requires": ["essay_id"],
        "writes": None,
        "description": (
            "Essay: essay.gates (read-only). Mechanical gates 1–11 and the unquoted-exact "
            "plagiarism blocker. This is not a review. The writer seat does not pass EQR here."
        ),
    },
    {
        "id": "intake",
        "tool": "essay.intake",
        "confirm": "draft-then-confirm",
        "read_only": False,
        "requires": ["name", "confirmPhase"],
        "writes": "shared upload, a rolled-forward sequence, or a new module from Word",
        "description": (
            "Essay: essay.intake (Confirm two-step). Say the reply to the user. "
            "File work does not own the chat. "
            "Call with the file name. A Word draft is matched to one module; say which module "
            "and ask the user to say yes, then roll forward onto that module's next sequence. "
            "The choice is the module. Do not ask for a sequence. "
            "If the file cannot be matched, the reply is the module list with no sequence id. "
            "The user picks a module and the upload rolls forward (rollForward true). "
            "If the user cannot identify a module, call with create true and the new module code. "
            "Say there is no saved research trail, next steps use an upload, a look-up, or a source card from here, "
            "research starts only if the user asks, the first draft is done, and the stage is their feedback. "
            "A supporting document is filed on the module for every sequence. "
            "A changed Word upload leaves the parent sequence in place. "
            "An unchanged Word file stays in unassigned/ and nothing is written. "
            "A PNG, JPEG, GIF, or WEBP photo is not a Word draft. When the result says "
            "needs_reading, look at the image in the tool result and call again with the "
            "same file name, the same module, confirmPhase draft, and reading set to only "
            "the words visible in the photo, including handwriting. Do not ask the student "
            "to copy those words from another program. Show that reading to the student. "
            "After an explicit yes, confirm files the photo and those words on the module "
            "for every sequence. An empty or unreadable photo is refused and nothing is filed."
        ),
    },
)

# The full notes stay on the writer instructions, once. Pasting them onto each
# door made tools/list about 230KB, and the host catalog then kept an older
# shorter list that omitted later doors.
_SEAT_LINE = {
    "essay.research.summary": (
        " The research seat reads the writing helpers in the server instructions. "
        "That note is not a source list."
    ),
    "essay.research.full": (
        " The research seat reads the writing helpers in the server instructions. "
        "That note is not a source list."
    ),
    "essay.pack.validate": (
        " The write seat reads the writing helpers and Harvard Referencing "
        "in the server instructions. Those notes are not a source list."
    ),
    "essay.pack.render_word": (
        " The write seat reads the writing helpers and Harvard Referencing "
        "in the server instructions. Those notes are not a source list."
    ),
}

for _door in DOORS:
    suffix = basics_prompt_suffix(_door["tool"])
    if suffix:
        _door["description"] = _door["description"] + suffix
    llm = stage_llm_suffix(_door["tool"])
    if llm:
        _door["description"] = _door["description"] + llm
    rule = stage_rule_suffix(_door["tool"])
    if rule:
        _door["description"] = _door["description"] + rule
    seat_line = _SEAT_LINE.get(_door["tool"])
    if seat_line:
        _door["description"] = _door["description"] + seat_line
