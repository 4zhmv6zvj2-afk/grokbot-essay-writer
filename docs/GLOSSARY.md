# Glossary

The code and prompts use a small private vocabulary. It is consistent but not
obvious from the outside. This page maps it to plain terms; the module names
are unchanged.

| Word | Plain meaning | Where it lives |
| --- | --- | --- |
| **door** | One MCP tool. "Calling a door" means calling a tool. | `src/essay_writer/doors.py`, `src/essay_writer/prompts/front_office/tools.json` |
| **seat** | The prompt subset a specialist stage is allowed to read. The write seat reads Harvard referencing and a pointer to the writing helpers; the reviewer seat reads neither. | `src/essay_writer/seats.py`, `src/essay_writer/prompts/seats/` |
| **spine** | The ordered stage definitions, and the one rule that stage 5 stores on its draft and starts stage 6 without a confirm card. | `src/essay_writer/spine.py` |
| **shelf** | The local per-essay store for confirmed research packs (`essay.shelf.get` / `essay.shelf.put`). Both directions are draft-then-confirm. | `src/essay_writer/shelf.py` |
| **dig** | The research card: an OpenAlex lookup (no key), an optional Consensus lookup, and an Unpaywall lookup for free copies. Draft shows the card; confirm writes `dig-card.json` / `dig-card.md`. | `src/essay_writer/dig.py` |
| **canon** | Canonical JSON (sorted keys, no whitespace) plus SHA-256. It makes a Confirm identity: same arguments, same digest. | `src/essay_writer/canon.py` |
| **confirm / card** | The two-phase write protocol. A write call with `confirmPhase: "draft"` returns a card; the same call with `confirmPhase: "confirm"` writes, and only if the canonical digest and the on-disk file fingerprint still match. | `src/essay_writer/confirm.py` |
| **pack** | A validated research pack. A pack's ending is **noted** when it stands on gathered evidence, and **open** when it does not. The door never turns open into noted. | `src/essay_writer/research_packs.py`, `docs/workflow.md` |
| **mid-office** | The child process that serves the MCP tools over stdio. The "mid-office shell" is whichever host runs it (Cursor by default, or Grok Build). | `src/essay_writer/mid_spawn.py` |
| **Grok Build** | An alternative agent host to Cursor, selected by the operator. | `FIRST-RUN.txt` |
| **front office** | The chat-facing operator instructions, as opposed to file work. | `src/essay_writer/prompts/front_office/` |
| **landing / replies** | The two writers behind the stage runner: `stage_landing.py` stores a saved stage and attaches report bodies; `stage_replies.py` builds the draft and save reply dicts. | `src/essay_writer/stage_landing.py`, `src/essay_writer/stage_replies.py` |
| **stage context** | The typed values between the tool signature and the reply writers: `StageArgs` is the public `essay.stage` tool call; `StageContext` is one resolved stage call. | `src/essay_writer/stage_context.py` |
| **confirm state** | The resolved fields a confirm returns before the body is built (phase, text, pointer, and the draft fields). A refusal stays a plain dict. | `src/essay_writer/stage_context.py` |
| **stage_state** | The pointer, the commit journal, and the stage lock behind the stage runner. Imported by the runner; it never imports the runner back. | `src/essay_writer/stage_state.py` |
| **stage_note** | The tracking-note renderer and look reader. It returns the stage markdown and reads the working or final look back out of that markdown. It does not write the pointer or the commit journal, and it never imports the orchestrator. | `src/essay_writer/stage_note.py` |
| **stage_hold** | Held and refused replies for one stage save. It replays a Confirm card and commits the next card through the injected CardRun. The pointer write stays in stage_state. It never imports the orchestrator. | `src/essay_writer/stage_hold.py` |
| **stage 1–10** | The workflow steps: assignment, thesis/purpose, plan, annotated bibliography, critical review, first draft, feedback, edit, references, final Word. | `src/essay_writer/stage_track.py` |
| **AC1, AC2** | Stable local labels for acceptance criteria in test names and docstrings. They are not tracker ids. See `docs/testing.md`. | `tests/test_*.py` |
| **operator** | The person (or agent) setting the tool up on the computer, as opposed to the student writing the essay. | `FIRST-RUN.txt` |

If a term is missing here, treat the module docstring as the definition and
open an issue so this table can be extended.
