# Design: split stage_state

This is a design for review. It does not move a function, change behaviour,
edit a prompt, edit `tools.json`, bump the package version, or cut a release.
`ARCHITECTURE.md` still describes the code as it is. A short pointer there
names this file. No implementation slice starts from this pull request.

Measured from commit `21a3da0a9f567956986051f3c6b2d095d4a1141c` on `main`.
`stage_state.py` is 1462 lines and defines 70 functions. The import walk is
the one already committed in `tests/test_import_graph.py`. At this commit
that walk reports 101 modules, 378 load edges, and 291 unique deferred
pairs. The checked-in breaker allowlist matches the measured breaker set
(28), and the checked-in mutual-pair allowlist matches the measured set
(46). `stage_state` appears in one breaker, `state` → `stage_state`, and in
no mutual pair.

The earlier design, `docs/design-import-graph-and-stage-runner.md`, measured
an older tree (99 modules) and left `stage_state.py` unsplit on purpose.
`stage_confirm.py` and `stage_body.py` have since landed. This document is
the next design. It does not rewrite that earlier note.

## What this split is for

`stage_state.py` holds four jobs that do not share one owner:

1. The pointer and the commit journal that publishes a note and a pointer
   together.
2. The stage lock that replays or quarantines that journal before a reader
   or a writer runs.
3. The tracking-note renderer, and the reader that pulls the working or
   final look back out of the headings that renderer writes.
4. The reply bodies a stage save returns when it is held or refused, and
   the next-card commit those bodies share.

The lock and the journal are one protocol. Splitting them would let a
reader observe a torn note and pointer. The note text does not write the
pointer. The reply bodies call the pointer API and do not own the journal.
Those are the seams. Line count is not one of them.

`stage_landing.py`, `stage_replies.py`, and `_run_stage` stay as they are.
That limit is repeated under non-goals so a review does not turn it into a
slice.

## 1. Inventory

Line numbers are the function's first and last line at this commit, from
the AST (`end_lineno`). "Calls" lists names defined in this file. External
callers are other package modules. Tests that import or patch a name are
in section 8, not in this table.

`TOOL` is the string `"essay.stage"`. `STAGE_COMMIT` is
`tracking/.stage.commit`. `_STAGE_NOTE_RELS` is the set of tracking-note
paths from `tracking_file`. `_LOCKS` is the thread-local set of sequence
ids whose lock this thread already holds. `_INHERITED_KEEP` is the flag
the landing layer sets around an inherited-lock keep. `_QUARANTINE_NOTICE`
carries the sentence `_stage_call` copies onto a result.
`DamagedStageCommit` is the exception that sentence comes from when a
damaged journal cannot be moved aside.

### Pointer, journal, and lock

These own the on-disk pair (the note file and `tracking/stage.json`) and
the lock around it. They stay in `stage_state.py`.

| Name | Lines | Owns | Calls in this file | External callers |
| --- | --- | --- | --- | --- |
| `_atomic` | 76–86 | Replace one file via a temp name | — | — (`tests/test_torn_confirm.py` patches it) |
| `_pointer_path` | 95–96 | Pointer path | — | — |
| `_commit_path` | 99–100 | Journal path | `STAGE_COMMIT` | — |
| `_pointer_text` | 103–104 | Pointer JSON | `Pointer` | — |
| `_note_rel` | 107–111 | Allowed note relative path | `_STAGE_NOTE_RELS` | — |
| `_apply_commit` | 114–132 | Publish one journal record, journal last | `_atomic`, `_pointer_text`, `STAGE_COMMIT` | — |
| `_quarantine_notice` | 135–139 | Notice sentence | — | — |
| `_commit_record_ok` | 152–166 | Journal shape check | `_STAGE_NOTE_RELS` | — |
| `_journal_damaged` | 169–181 | Present journal that is not a record | `_commit_record_ok` | — |
| `_quarantine_journal` | 184–206 | Rename a damaged journal, or raise | `DamagedStageCommit` | — |
| `_read_commit` | 209–216 | Read a healthy journal | `_journal_damaged`, `_commit_record_ok` | — |
| `_replay_commit` | 219–222 | Finish a torn journal | `_read_commit`, `_apply_commit` | — |
| `_note_path` | 225–229 | Path of one stage's tracking note | — | `stage_body`, `stage_replies` |
| `blank_pointer` | 265–280 | New sequence's pointer dict | — | — |
| `_clear_copied_writing` | 283–293 | Drop copied notes and drafts | `_STAGE_NOTE_RELS` | — |
| `init_cloned_sequence_pointer` | 296–312 | Child pointer after a parent copy | journal helpers, `blank_pointer`, `_clear_copied_writing` | `projects` (inside the clone function) |
| `rebind_cloned_confirms` | 315–379 | Copied draft digests for the child id | `_atomic`, `_pointer_text`, `TOOL` | `projects` (same function) |
| `_read_pointer_data` | 432–442 | Raw pointer JSON | `_pointer_path` | — |
| `load_pointer` | 445–452 | Normalized pointer, replaying a torn journal first | `_pointer_lock`, `_normalize_pointer`, `blank_pointer` | `health` (module level), `stage_track` (module level). Many tests import it; section 8 lists them |
| `_normalize_pointer` | 455–485 | Coerced pointer fields | `_waiting_pair`, `_revision` | — |
| `_room_state` | 488–493 | `room_grant`, `room_lock` | — | `stage_landing` |
| `_room_after_card_save` | 496–501 | Room fields after a card save | `_room_state` | `stage_replies` |
| `_saved_after_confirm` | 504–509 | `saved` with this stage appended once | — | `stage_landing`, `stage_replies` |
| `_room_blocks` | 512–517 | Room press blocks this stage | `_room_state` | `stage_confirm` |
| `_waiting_pair` | 520–525 | `waiting_stage`, `waiting_digest` | — | — |
| `_waiting_digest` | 528–533 | Digest stored for one stage | `_waiting_pair` | `stage_track`, `stage_replies` |
| `_revision` | 553–557 | Non-negative revision | — | — |
| `_held_locks` | 560–565 | Thread-local held set | `_LOCKS` | — |
| `require_fcntl` | 568–580 | POSIX `fcntl`, or a refusal that names the platform | — | `state._fcntl` (inside the function) |
| `_pointer_lock` | 584–608 | Exclusive lock; replay before the body | `require_fcntl`, `_replay_commit`, `_held_locks` | — |
| `stage_lock` | 611–613 | Public wrapper of `_pointer_lock` | `_pointer_lock` | `projects` (inside the clone function) |
| `_rolls_backward` | 616–628 | Proposed pointer drops saved stages, opens a closed sequence, or moves `current` earlier | — | — |
| `_commit_pointer` | 631–665 | One journal write of the note and the pointer, under the lock | `_pointer_lock`, `_rolls_backward`, `_apply_commit`, quarantine helpers | `stage_landing`, `stage_replies` import the name and call it. `_grant_room` and `_commit_with_next_card` call it as a global in this file |
| `_grant_room` | 1290–1295 | Write `room_grant` for this stage | `_commit_pointer` | `stage_confirm` |
| `_payload` | 1140–1141 | `{essay_id, stage, look}` | — | `stage_body`, `stage_landing` |
| `_revisit_window` | 1372–1379 | After 4b is saved and before stage 5 is saved | — | `stage_body` |
| `in_first_draft` | 1459–1462 | `current == "5"` and stage 5 is unsaved | `load_pointer` | `revise` (inside the function) |

`rebind_cloned_confirms` imports `essay_writer.canon.digest` inside the
function (line 324). That deferred pair stays. It is the hoist-safe pair
the earlier design listed as `stage_state` → `canon`. It is not a breaker
and not a mutual pair. This split leaves it deferred.

`_clear_copied_writing` imports `shutil` inside the function. That is a
standard-library import and stays where it is.

Types and module names that stay with this group: `fcntl`, `TOOL`,
`STAGE_COMMIT`, `_STAGE_NOTE_RELS`, `_LOCKS`, `_QUARANTINE_NOTICE`,
`_INHERITED_KEEP`, `DamagedStageCommit`, `Pointer`, `StageResult`.
`StageResult` is imported only by `stage_replies`. It stays because it
names the result shape and it has no behaviour. `Pointer` is the pointer
shape `load_pointer` and `_commit_pointer` already use.

Module-level imports this group needs after the reply functions have
left: `refuse_repo_write` from `known_paths`, `work_dir` from `paths`,
and `POINTER_FILE`, `STAGE_ORDER`, `tracking_file` from `stage_llm`.
`stage_state` load-imports `stage_llm` today (line 40). That edge is what
makes `state` → `stage_state` a breaker: `stage_llm` load-imports
`specialists.grok_bot`, which load-imports `state`. The edge stays, so
the breaker pair stays and the allowlist does not change identity.

### Tracking note

These own the markdown contract. `render_tracking` writes `## Final look`
or `## Working look`. `_note_look` reads the last of those headings. Neither
writes the pointer.

| Name | Lines | Owns | Calls in this file | External callers |
| --- | --- | --- | --- | --- |
| `_note_look` | 536–550 | Look text last written into the note | `_note_path` | `cite_fit` (three function-body imports, lines 211, 229, 353) |
| `render_tracking` | 1116–1137 | The note markdown | — | `stage_landing`, `stage_replies` |

`_note_look` is also called from `_superseded_card` and
`_stale_confirm_body` in this file. Those two move with the reply group,
so after the move the note module does not call a reply function, and the
reply module calls `_note_look`.

### Held and refused replies, and the next-card commit

These build reply dicts. They read the pointer through `load_pointer` and
the predicates above. The only pointer write in this group is the call to
`_commit_pointer` inside `_commit_with_next_card`. `_grant_room` is the
other pointer write and it stays with the journal, because it records a
room press and does not build a card.

`CardRun` (lines 53–67) is the protocol for that callback. The functions
below are the ones that call it. `_CARD_FIELDS` (line 1144) is the draft
fields `_hydrate_card` copies.

| Name | Lines | Owns | Calls in this file | External callers |
| --- | --- | --- | --- | --- |
| `_own_door_card` | 382–398 | Door card for this sequence and stage | — | — |
| `door_card_reply` | 401–429 | Confirm card for the open stage | `load_pointer`, `_replay_confirm_card`, `_own_door_card`, `_draft_next_card` | `projects` (inside the new-sequence function, lines 1459–1462), passing `_run_card_only` |
| `_pointer_lost` | 668–689 | Reply when the pointer moved | `load_pointer`, `_stage_refusal`, `_confirm_blocked` | `stage_confirm`, `stage_landing`, `stage_replies` |
| `_confirm_blocked` | 692–750 | Already-saved stage; card for `current` instead | `_replay_confirm_card` | `stage_track` |
| `_opening_look` | 753–766 | Cached basics look for a minted card | — | — (`tests/test_basics_pass_cache.py` calls it) |
| `_next_card_look` | 769–782 | Opening text of the next card | `_opening_look` | — |
| `_draft_next_card` | 785–801 | One card-only draft via `CardRun` | `_next_card_look` | — (`tests/test_confirm_atomic.py` patches it) |
| `_next_card_fields` | 804–821 | `card`, `cardAction`, `cardDigest` for the next stage | — | — |
| `_pending_inherited` | 824–830 | Parent save still waiting on copied stage 2 or 3 | — | — |
| `_name_inherited_lock` | 833–852 | Reply that names the parent save and drops the card | — | — |
| `_expects_next_card` | 855–859 | Following stage uses a Confirm card | — | — |
| `_mint_stage_allowed` | 862–869 | Mint is the next stage of an unsaved current | — | `stage_track` |
| `_hold_confirm` | 872–901 | Next card missing; pointer stays | `_reoffer_confirm` | — |
| `_attach_minted_card` | 904–925 | Minted card on a stored confirm | — | — |
| `_mark_explicit_end` | 928–935 | Advance with no card (`explicit_end`) | — | `stage_landing`, `stage_replies` |
| `_render_stage10_before_close` | 938–981 | Final Word file before the pointer may close; otherwise a held card | `_reoffer_confirm` | — (tests in section 8 read its source) |
| `_with_plan_encourage` | 984–995 | One plan question after stage 3 is stored | — | `stage_replies` |
| `_cache_approved_look` | 998–1003 | Remember an approved look, except stage 5 | — | `stage_replies` |
| `_snapshot_stage_save` | 1006–1014 | Pack snapshot after a stored save | — | `stage_landing`, `stage_replies` |
| `_commit_with_next_card` | 1017–1113 | Advance, or hold when the next card does not mint | the mint, hold, stage-10, inherited-lock, and explicit-end helpers; `_commit_pointer` | `stage_replies` |
| `_replay_confirm_card` | 1147–1187 | Waiting Confirm card | `_card_record`, `_waiting_digest`, `_confirm_line`, `_revisit_window` | `stage_replies` |
| `_stage7_skip_reply` | 1190–1221 | Skip does not save; questions again | — | `stage_confirm` (`_stage7_skip_request` returns it) |
| `_reoffer_confirm` | 1224–1251 | Confirm that does not save, card or next ask | `_replay_confirm_card` | `stage_confirm`, `stage_replies` |
| `_card_record` | 1254–1266 | Draft named by the card digest | `TOOL` | `stage_confirm`, `stage_track` |
| `_hydrate_card` | 1269–1287 | Fill omitted Confirm fields from the draft | `_CARD_FIELDS` | `stage_confirm` |
| `_superseded_card` | 1298–1320 | Card is an older draft than the waiting one | `_card_record`, `_waiting_digest`, `_note_look` | `stage_confirm` |
| `_older_card` | 1323–1340 | Reoffer after a superseded card | `_reoffer_confirm` | `stage_confirm`, `stage_replies` |
| `_stale_confirm_body` | 1343–1369 | Confirm is not the waiting draft's look | `_waiting_digest`, `_note_look` | `stage_replies` |
| `_stage_refusal` | 1382–1419 | Closed sequence, revisit order, already saved, or wrong current | `_revisit_window` | `stage_track` |
| `_stage5_held` | 1422–1450 | Failed stage-5 check; nothing stored | — | `stage_landing` |
| `_confirm_line` | 1453–1456 | Save line for the card | — | `stage_replies` |

Function-body imports in this group, by function. They move with the
function. They stay inside the function.

| Function | Import |
| --- | --- |
| `door_card_reply` | `spine.stage_uses_confirm_card` |
| `_confirm_blocked` | `specialists.grok_bot.missing_confirm_next`, `spine.stage_uses_confirm_card` |
| `_opening_look` | `specialists.grok_bot.attach_basics_pass`, `cached_approved_look` |
| `_next_card_look` | `brief_contract.opening_card_lines` |
| `_pending_inherited` | `fo_chat_locks.inherited_lock_pending` |
| `_name_inherited_lock` | `fo_chat_locks.prior_saved_lock_ask` |
| `_expects_next_card` | `spine.stage_uses_confirm_card` |
| `_render_stage10_before_close` | `late_chain.write_stage10` |
| `_with_plan_encourage` | `encourage.attach_plan_encourage` |
| `_cache_approved_look` | `specialists.grok_bot.remember_approved_look` |
| `_snapshot_stage_save` | `pack_backup.snapshot_after_stage_save` |
| `_commit_with_next_card` | `specialists.grok_bot.saved_next`, `late_chain.finish_stage_reply`, `specialists.grok_bot.critical_reviews_delivery_next` |
| `_replay_confirm_card` | `specialists.grok_bot.card_next`, `confirm_reply_fields`, `spine.stage_confirm_card` |
| `_stage7_skip_reply` | `specialists.grok_bot.stage7_lead`, `stage7.load_stage7`, `note_questions`, `questions_for` |
| `_reoffer_confirm` | `specialists.grok_bot.missing_confirm_next` |
| `_stage5_held` | `late_chain.stage5_chat_line` |
| `_confirm_line` | `spine.save_line` |

Names this group uses as globals, which the new module imports at load
time because the bodies keep calling them unqualified: `CONFIRM`,
`latest_draft`, `load_draft_by_digest`, and `refuse` from `confirm`;
`relative` from `paths`; `STAGE_ORDER`, `brief_genre`, `next_stage`, and
`stage_title` from `stage_llm`; `TOOL`, `Pointer`, `load_pointer`,
`_commit_pointer`, `_waiting_digest`, and `_revisit_window` from
`stage_state`; `_note_look` from the note module.

`stage_track` also imports `_QUARANTINE_NOTICE` and `DamagedStageCommit`
inside `_stage_call` (line 194). That import stays pointed at
`stage_state`.

## 2. Proposed modules

Two new modules. `stage_state.py` keeps the pointer, the journal, and the
lock.

### `stage_state.py`

Everything in the pointer table, plus the types and module names listed
under it. After both slices, the module docstring says this file owns the
pointer, the commit journal, and the stage lock, and that a note or a
reply that needs a card calls back through `CardRun` on the hold module.
The file still never imports `stage_track`.

It does not re-export a moved name. Callers change their imports in the
slice that moves the function.

### `stage_note.py`

`render_tracking` and `_note_look`.

The module docstring the slice adds:

```python
"""Tracking-note text for one stage.

stage_note renders the stage markdown and reads the working or final look
back out of that markdown. It does not write the pointer or the commit
journal. It never imports the orchestrator.
"""
```

Load imports: `stage_settings` and `stage_title` from `stage_llm`, and
`_note_path` from `stage_state`. No import of `stage_hold`, `stage_track`,
`stage_confirm`, `stage_body`, `stage_landing`, `stage_replies`, or
`stage_context`.

### `stage_hold.py`

`CardRun`, `_CARD_FIELDS`, and every function in the reply table.

The module docstring the slice adds:

```python
"""Held and refused replies for one stage save.

stage_hold builds the reply a save returns when it is held or refused,
replays a Confirm card, and commits the next card through the injected
CardRun. The pointer write stays in stage_state: this module calls
_commit_pointer and does not write the journal itself. It never imports
the orchestrator, the confirm path, or the body builder.
"""
```

`_commit_with_next_card` returns either a held reply or a stored reply.
The two returns are one function body. The stored return lives here with
the hold return so the slice can move the function without editing it.
The name `stage_hold` is the job the orchestrator already describes
("held or refused reply bodies"). Section 10 asks the reviewer to confirm
the name before a slice, because the glossary will freeze it.

Load imports are the globals listed at the end of section 1. Function-body
imports stay inside the moved functions. No import of `stage_track`,
`stage_confirm`, `stage_body`, `stage_landing`, `stage_replies`,
`stage_context`, or `projects`.

`stage_body` keeps importing `_INHERITED_KEEP`, `_note_path`, `_payload`,
and `_revisit_window` from `stage_state`. This design gives `stage_body`
no import of `stage_hold` or `stage_note`.

## 3. Dependency direction

Allowed load edges after both slices:

```
stage_track
  → stage_body, stage_confirm, stage_landing, stage_replies,
    stage_hold, stage_note, stage_state
stage_body
  → stage_confirm, stage_landing, stage_state
stage_confirm
  → stage_hold, stage_state
stage_replies
  → stage_landing, stage_hold, stage_note, stage_state
stage_landing
  → stage_hold, stage_note, stage_state
stage_hold
  → stage_note, stage_state, stage_llm, confirm, paths
stage_note
  → stage_state, stage_llm
stage_state
  → stage_llm, paths, known_paths
```

`stage_state`'s load import of `confirm`, and its imports of `relative`,
`brief_genre`, `next_stage`, `stage_settings`, and `stage_title`, leave
with the functions that use them. `POINTER_FILE`, `STAGE_ORDER`, and
`tracking_file` stay.

Direction rules:

1. The load graph stays a DAG. `stage_note` and `stage_hold` sit under
   the orchestrator. They load-import `stage_state`. `stage_state` does
   not import either of them.
2. `stage_hold` may be load-imported by `stage_track`, `stage_confirm`,
   `stage_landing`, and `stage_replies`. It does not import those modules.
   `stage_confirm` → `stage_hold` is the same direction as today's
   `stage_confirm` → `stage_state`. There is no reverse edge, so this does
   not disturb `stage_body` → `stage_confirm` with `stage_confirm` never
   importing `stage_body`.
3. `stage_note` may be load-imported by `stage_track`, `stage_landing`,
   `stage_replies`, and `stage_hold`. It does not import them.
4. None of `stage_state`, `stage_note`, `stage_hold`, `stage_landing`,
   `stage_replies`, `stage_confirm`, or `stage_body` import `stage_track`,
   at module level or inside a function.
5. `stage_note` and `stage_hold` do not import `stage_context`. The
   comment in `stage_context.py` (lines 10–11) stays true: the state side
   does not import that module, and no cycle opens through it.
6. `CardRun` remains the way a hold helper runs a card.
   `_run_card_only` and `_inherited_keep_confirm` stay in `stage_track.py`.
   `InheritedConfirm` stays in `stage_landing.py`. `projects.py` keeps the
   function-body import of `_run_card_only` and passes it into
   `door_card_reply`. That call stays deferred.

At this commit, none of `spine`, `specialists.grok_bot`, `brief_contract`,
`fo_chat_locks`, `late_chain`, `encourage`, `pack_backup`, `stage7`,
`confirm`, `stage_llm`, `canon`, `cite_fit`, `projects`, or `state`
load-reach `stage_track`, `stage_confirm`, `stage_landing`,
`stage_replies`, `stage_body`, or `stage_state`. A new module that is
only load-imported by those stage modules is therefore not load-reachable
from those deferred targets. That is why the new deferred edges in
section 5 are not breakers.

## 4. The boundary that stays intact

The journal boundary:

- `_pointer_lock` replays a healthy journal, or quarantines a damaged one,
  before the locked body runs. `load_pointer` and `_commit_pointer` both
  take that lock.
- `_commit_pointer` is the only function that writes a new journal record.
  It refuses a stale revision and a backward `current` or `saved` list,
  writes the note and the pointer into the journal, then `_apply_commit`
  publishes them and removes the journal last.
- `_atomic` is the only replace. It stays private to `stage_state.py`.
- `render_tracking` returns a string. The caller passes that string into
  `_commit_pointer`. The note module does not open the journal, the
  pointer file, or the lock.
- `stage_hold` calls `_commit_pointer` for the next-card advance. It does
  not write `tracking/.stage.commit`, the pointer file, or the note file
  itself.

The orchestrator boundary, already pinned, stays: the state side does not
import `stage_track`. A card is an injected `CardRun`. An inherited-lock
keep is the injected callable `stage_landing` already takes. This split
does not add a third callback and does not turn either callback into an
import.

The confirm and body boundary stays: `stage_hold` does not import
`stage_confirm` or `stage_body`. The stage-7 skip probe stays in
`stage_confirm.py` and still calls `_stage7_skip_reply`. Moving
`_stage7_skip_reply` into `stage7.py` would point a lower module at the
hold module. This design does not do that. `stage7.py` keeps
`answers_mean_skip` and the question text it already has.

## 5. Import guard

`tests/test_import_graph.py` keeps both allowlists at their current
members. This split does not add a breaker and does not add a mutual
pair, so neither list grows and neither list shrinks. A slice that
produced a new pair would stop. Justifying a new pair is not part of
this design.

Edges that move, and why they stay off both lists:

| Edge after the move | Why it is not a new breaker or a new mutual pair |
| --- | --- |
| `cite_fit` → `stage_note`, deferred (replaces `cite_fit` → `stage_state`) | `stage_note` load-imports `stage_llm` and `stage_state`. Neither load-reaches `cite_fit`. `stage_note` does not import `cite_fit`. |
| `projects` → `stage_hold`, deferred, for `door_card_reply` only | `projects` → `stage_state` stays for `init_cloned_sequence_pointer`, `rebind_cloned_confirms`, and `stage_lock`. `stage_hold` does not load-reach `projects`. `projects` does not gain a load import. |
| `stage_hold` → `spine`, `specialists.grok_bot`, `brief_contract`, `fo_chat_locks`, `late_chain`, `encourage`, `pack_backup`, `stage7`, all deferred | Each replaces the same deferred pair from `stage_state`. None of those targets load-reach the stage modules that will import `stage_hold`. None of them import `stage_hold`. |
| `stage_hold` → `stage_note`, `stage_state`, `stage_llm`, `confirm`, `paths`, all load | One direction. Those targets do not import `stage_hold`. |
| `stage_note` → `stage_state`, `stage_llm`, load | One direction. |
| `state` → `stage_state`, deferred | Unchanged. `require_fcntl` stays, and `stage_state` still load-imports `stage_llm`. This remains the one breaker that names `stage_state`. |
| `stage_state` → `canon`, deferred | Unchanged, inside `rebind_cloned_confirms`. |
| `stage_track` → `stage_state`, deferred | Unchanged, inside `_stage_call`, for the quarantine names. |

`stage_state` → `confirm` as a load edge disappears when the reply
functions leave, because no remaining function uses `confirm`. That pair
is not in either allowlist. Deleting it does not edit the lists.

The hoist that would grow the breaker list is named so a slice does not
do it. `fo_chat_locks` load-imports `projects`. `projects` will
deferred-import `stage_hold` for `door_card_reply`. Leaving
`inherited_lock_pending` and `prior_saved_lock_ask` inside the functions
that already import them keeps `stage_hold` from load-reaching
`projects`, so `projects` → `stage_hold` is not a breaker. Moving either
import to module level would make that deferred edge a breaker and the
28-pair allowlist would have to grow. This design does not hoist it, and
does not hoist the other function-body imports in the reply table.
Phase 4's rule that new modules use module-level imports except the 28
breakers applies to names the moved bodies already call as globals. It
does not apply to imports that already live inside those bodies.

`STAGE_LAYERS` in `tests/test_import_graph.py` gains `stage_note` and
`stage_hold`, so the guard's "stage layers do not import `stage_track`"
check covers them. That set is not an allowlist. Growing it is the
guard doing its job.

## 6. Behaviour the slices keep

The slices move functions and retarget imports. They do not edit a
function body. The public contract and the stage decisions stay where
they are.

### Confirm gate

`spine.AUTO_START` and `advances_without_confirm` stay in `spine.py`.
The stage-5 confirm refusal, the typed-save fallback, and the empty
confirm stay inside `_run_stage` in `stage_track.py`. `_confirm_path`
stays in `stage_confirm.py`, in the same order. It still calls
`_card_record`, `_grant_room`, `_hydrate_card`, `_older_card`,
`_pointer_lost`, `_reoffer_confirm`, `_room_blocks`, `_superseded_card`,
and `_stage7_skip_reply`. Only the module those names are imported from
changes. `_grant_room` and `_room_blocks` stay on `stage_state`. The
others move to `stage_hold`.

### Stage 5 draft exemption

The exemption path stays in the modules that already own it:

1. `advances_without_confirm("5")` still supplies the following stage
   from `spine`.
2. A confirm-phase call on stage 5 still returns inside `_run_stage`,
   before `_confirm_path`.
3. `_draft_reply` still calls `_store_stage` when that following stage
   is set.
4. `_store_stage` still calls `_stage5_held` on a failed check, still
   calls `_commit_pointer` for the store, and still calls
   `_mark_explicit_end`.

`_stage5_held`, `_mark_explicit_end`, and the no-card branch inside
`_commit_with_next_card` move as whole functions. Their bodies stay
byte-for-byte. Stage 5's store remains the landing path, not a new
branch in the hold module.

### Injected callbacks

`CardRun` moves to `stage_hold.py` next to the functions that call it.
The call shape stays: `card_run(essay_id, stage, look, minting=...)`.
`projects.door_card_reply` still receives `_run_card_only`.
`InheritedConfirm` and `_inherited_keep_confirm` stay where they are.
`_INHERITED_KEEP` stays on `stage_state`, which every current reader
already imports, so `stage_body` does not take a new dependency to read
the flag.

### Public `essay.stage` contract

`essay_stage` in `stage_track.py` stays the tool function. Its parameter
names stay (`confirmPhase`, `cardAction`, `cardDigest`, `encourageChoice`,
`paperChoice`, `lockChoice`, and the rest). `StageArgs` stays the schema
object. `server.HANDLERS["essay.stage"]` stays `essay_stage`. No slice
edits `prompts/front_office/tools.json` or a file under
`src/essay_writer/prompts/`.

### Mid-office

Mid-office behaviour would be unchanged by the later implementation of
this design.

`stage_state.py` does not mention `cursor_office`, `build_office`,
`mid_spawn`, or `mid_office_launch`. None of the functions that move
read the stored shell or start the child. The launch field stays in
`stage_body._attach_stage_reports`, which calls
`cursor_office.stage_host_launch`. The child start stays in
`stage_landing._attach_mid_run`. This design does not split those files
and does not edit those functions.

There is no residual mid-office change in the slices. A slice that
edited a moved body and called a shell from it would be outside this
design. The slice rule is to move the body unchanged, so that edit is
not part of the slice.

The tests that compare the two shells
(`tests/test_confirm_atomic.py`, `tests/test_stage10_sequence_write.py`,
`tests/test_word_manifest.py`, `tests/test_pack_backup_restore.py`, and
the `tests/test_mid_office_*.py` files) stay on the slice as regression
checks. Their launch assertions do not move.

## 7. Migration slices

Each slice is one commit, moves functions without editing their bodies,
and can be reverted on its own. A later slice starts only after the
previous one is green. No slice bumps the version, edits a prompt, or
edits `tools.json`. No slice re-exports a moved name from
`stage_state.py` or from `stage_track.py`.

Do not start slice 1 until section 10 is answered. This pull request
does not contain either slice.

### Slice 1 — note renderer

Create `stage_note.py` with `render_tracking` only.

`render_tracking` is a leaf. No function that remains in `stage_state.py`
calls it. `stage_note` load-imports `stage_settings` and `stage_title`.
It does not import `stage_state` yet, because `_note_look` is still in
`stage_state` and moving `_note_look` now would make the two files import
each other: `_note_look` calls `_note_path`, and `_superseded_card` and
`_stale_confirm_body` still call `_note_look`.

Retarget `render_tracking` in `stage_landing.py`, `stage_replies.py`,
and `tests/test_stage_card_ids.py`. `stage_settings` is only used by
`render_tracking`, so drop it from `stage_state.py`'s import list.
`stage_title` stays until slice 2, because the reply functions still
call it.

Add `stage_note` to `STAGE_LAYERS` and to the layer list in
`tests/test_stage_boundary.py`, including the subprocess import check.
Expect both allowlists unchanged.

`_note_look` stays in `stage_state.py` for this slice. `cite_fit` does
not change yet.

### Slice 2 — note reader and reply bodies

In the same commit:

- Move `_note_look` into `stage_note.py`. Add the load import of
  `_note_path`.
- Create `stage_hold.py` and move `CardRun`, `_CARD_FIELDS`, and every
  function in the reply table, bodies unchanged.
- Add the load imports listed in section 1. Leave every function-body
  import inside the function that already has it.
- Point external callers at the new modules (section 8).
- Drop the now-unused names from `stage_state.py`'s import list:
  `confirm`'s names, `relative`, `brief_genre`, `next_stage`, and
  `stage_title`. Keep `POINTER_FILE`, `STAGE_ORDER`, `tracking_file`,
  `work_dir`, and `refuse_repo_write`.
- Update the `stage_state` module docstring, the `stage_track` module
  docstring (lines 25–32), the `stage_replies` module docstring, the
  `stage_context` comment that names `essay_writer.stage_state` (lines
  10–11), and the layout bullets in `ARCHITECTURE.md`,
  `docs/GLOSSARY.md`, and `README.md` so they name `stage_note.py` and
  `stage_hold.py` and still describe `stage_state.py` as the pointer,
  journal, and lock. Keep the sentences `tests/test_stage_boundary.py`
  already requires in `ARCHITECTURE.md`. The `stage_context` comment
  keeps its claim: the state side does not import that module.

`_note_look` and its two callers (`_superseded_card`,
`_stale_confirm_body`) leave `stage_state.py` in this same commit, so
`stage_state` never imports `stage_note`.

Expect both allowlists unchanged. Expect no load cycle. Expect
`stage_hold` and `stage_note` to import `stage_track` zero times.

### Stop

After slice 2, stop. Do not split `_commit_pointer` from the lock. Do
not split `_run_stage`. Do not split `stage_landing.py` or
`stage_replies.py`. Do not hoist the deferred imports this design left
inside functions.

## 8. Tests and source pins to retarget

Pins stay source pins. A slice updates the module a pin reads. It does
not rewrite the pin into a behaviour assertion.

### Slice 1

| Pin | Retarget |
| --- | --- |
| `src/essay_writer/stage_landing.py` import of `render_tracking` | `stage_note` |
| `src/essay_writer/stage_replies.py` import of `render_tracking` | `stage_note` |
| `tests/test_stage_card_ids.py` import of `render_tracking` | `stage_note` |
| `tests/test_import_graph.py` `STAGE_LAYERS` | Add `stage_note` |
| `tests/test_stage_boundary.py` `LAYERS`, the subprocess import list, and the architecture-doc assertions if the docstring of that test names the layer set | Add `stage_note`. Keep the existing sentences |

`MOVED_NAMES` in `tests/test_stage_boundary.py` checks that
`stage_track` does not carry those attributes. It does not say which
file defines them. The list stays. It does not need a retarget to
remain true.

### Slice 2 — production imports

| Module | Names that move | Names that stay on `stage_state` |
| --- | --- | --- |
| `stage_track.py` load import | `CardRun`, `_card_record`, `_confirm_blocked`, `_mint_stage_allowed`, `_stage_refusal` → `stage_hold` | `_INHERITED_KEEP`, `TOOL`, `Pointer`, `_waiting_digest`, `load_pointer` |
| `stage_track.py` inside `_stage_call` | — | `_QUARANTINE_NOTICE`, `DamagedStageCommit` |
| `stage_confirm.py` | `CardRun`, `_card_record`, `_hydrate_card`, `_older_card`, `_pointer_lost`, `_reoffer_confirm`, `_stage7_skip_reply`, `_superseded_card` → `stage_hold` | `_INHERITED_KEEP`, `TOOL`, `_grant_room`, `_room_blocks` |
| `stage_landing.py` | `CardRun`, `_mark_explicit_end`, `_pointer_lost`, `_snapshot_stage_save`, `_stage5_held` → `stage_hold`. `render_tracking` already on `stage_note` from slice 1 | `_INHERITED_KEEP`, `TOOL`, `_commit_pointer`, `_payload`, `_room_state`, `_saved_after_confirm` |
| `stage_replies.py` | `CardRun` and the reply names → `stage_hold`: `_cache_approved_look`, `_commit_with_next_card`, `_confirm_line`, `_mark_explicit_end`, `_older_card`, `_pointer_lost`, `_reoffer_confirm`, `_replay_confirm_card`, `_snapshot_stage_save`, `_stale_confirm_body`, `_with_plan_encourage`. `render_tracking` is already on `stage_note` from slice 1. This file does not import `_note_look` | `_INHERITED_KEEP`, `TOOL`, `StageResult`, `_commit_pointer`, `_note_path`, `_room_after_card_save`, `_saved_after_confirm`, `_waiting_digest` |
| `stage_body.py` | none | `_INHERITED_KEEP`, `_note_path`, `_payload`, `_revisit_window` |
| `cite_fit.py` lines 211, 229, 353 | `_note_look` → `stage_note` | — |
| `projects.py` line 1459 | `door_card_reply` → `stage_hold` | lines 1311–1314: `init_cloned_sequence_pointer`, `rebind_cloned_confirms`, `stage_lock` |
| `state.py`, `health.py`, `revise.py` | none | `require_fcntl`, `load_pointer`, `in_first_draft` |

`stage_replies` keeps importing `StageResult` from `stage_state`. That
type stays.

### Slice 2 — tests that bind a moved name

| Test | What moves |
| --- | --- |
| `tests/test_cite_fit.py` | import `_note_look` → `stage_note` |
| `tests/test_cite_fit_restore.py` | import `_note_look` → `stage_note` |
| `tests/test_short_cites.py` | import `_note_look` → `stage_note` |
| `tests/test_basics_pass_cache.py` | import `_opening_look` → `stage_hold` |
| `tests/test_confirm_atomic.py` | import `_draft_next_card` → `stage_hold`. `monkeypatch.setattr("essay_writer.stage_state._draft_next_card", ...)` becomes the `stage_hold` path. `inspect.getsource(_draft_next_card)` follows the import. `TOOL` and `load_pointer` stay. The `getsource(_save_confirm)` assertion stays |
| `tests/test_word_manifest.py` | import and `getsource` of `_render_stage10_before_close` → `stage_hold` |
| `tests/test_word_references_4a.py` | import and `getsource` of `_render_stage10_before_close` → `stage_hold`. `load_pointer` stays |
| `tests/test_pack_backup_restore.py` | imports of `_commit_with_next_card` and `_snapshot_stage_save`, and their `getsource` checks → `stage_hold` |
| `tests/test_stage10_sequence_write.py` | import and `getsource` of `_commit_with_next_card` → `stage_hold`. The order assertion (`_render_stage10_before_close` before `_commit_pointer`) stays a source pin. `load_pointer` stays |
| `tests/test_layer5_callers.py` | The save-line count reads `stage_track.py` plus `stage_state.py` and expects `essay_writer.spine import save_line` once. That import lives in `_confirm_line` (line 1454). Include `stage_hold.py` in the read so the count stays 1 |
| `tests/test_stage_boundary.py` | Add `stage_hold` beside `stage_note` in `LAYERS` and in the subprocess import check. Extend the `_MINTING` file read to `stage_hold.py`, because `_draft_next_card` will live there and the current read only opens `stage_state.py` |
| `tests/test_import_graph.py` | Add `stage_hold` to `STAGE_LAYERS`. Leave `CYCLE_BREAKERS` and `MUTUAL_PAIRS` unchanged, including `("state", "stage_state")` |
| `tests/test_concurrent_confirm.py` | See the monkeypatch note below. `getsource(stage_state._commit_pointer)` stays. `load_pointer` stays |

### Monkeypatch of `_commit_pointer`

`tests/test_concurrent_confirm.py` replaces `stage_state._commit_pointer`.
That wraps calls which look the name up as a global inside
`stage_state.py`. Today those calls are `_grant_room` and
`_commit_with_next_card`.

`stage_landing._store_stage` and `stage_replies` (the draft note, and the
revisit save) import `_commit_pointer` at module level and call that
binding. Replacing the attribute on `stage_state` does not wrap those
calls today. The slices do not change that. They do not edit those
bodies to "fix" the patch.

After slice 2, `_grant_room` still looks the name up in `stage_state`,
and `_commit_with_next_card` looks it up in `stage_hold`. The slice
wraps both attributes with the same helper. The spy in AC5 has to
record the save whose proposed pointer advances `current`, which is the
`_commit_with_next_card` call, not only the room grant. Room grants also
carry `current` of `"1"` and `"2"`, so a spy left only on `stage_state`
can still satisfy `assert "1" in seen` and `assert "2" in seen` while
the save commit is unwrapped. That is the retarget. It stays a
monkeypatch of the same helper. It does not become a new behaviour
assertion.

`tests/test_torn_confirm.py` patches `stage_state._atomic` and
`stage_state.stage_lock`, and imports `STAGE_COMMIT`. Those names stay.
No retarget. `tests/test_hygiene.py` patches `stage_state.fcntl` and
calls `require_fcntl`, `stage_lock`, and `load_pointer`. Those stay.
No retarget.

### Imports of `load_pointer` that do not move

These tests import `load_pointer` from `stage_state` and do not import a
name this design moves. They need no retarget:

`tests/test_closed_parent_roll.py`, `tests/test_cold_e2e.py`,
`tests/test_confirm_bindings.py`, `tests/test_confirm_card.py`,
`tests/test_confirm_card_save.py`, `tests/test_confirm_next_card.py`,
`tests/test_confirm_pointer_word.py`, `tests/test_confirm_ux.py`,
`tests/test_digest_does_not_advance.py`, `tests/test_download_and_cite.py`,
`tests/test_encourage_voice.py`, `tests/test_first_run_blockers.py`,
`tests/test_fo_chat_locks.py`, `tests/test_harvard_ref_check.py`,
`tests/test_mid_office_dig.py`, `tests/test_mid_office_status_lines.py`,
`tests/test_refs_gate_and_annotation.py`, `tests/test_residual_spine.py`,
`tests/test_risk_lineage.py`, `tests/test_risk_stage.py`,
`tests/test_roll_forward.py`, `tests/test_stage10_cover_final.py`,
`tests/test_stage7_confirm_advance.py`, `tests/test_stage_confirm_isolation.py`,
`tests/test_stage_launch_status.py`.

`tests/test_title_door.py` imports `TOOL` and `load_pointer`. Both stay.
Its `getsource(_save_confirm)` pin stays, as do the same pins in
`tests/test_title_cover.py` and `tests/test_confirm_next_card.py`: they
read `_save_confirm` and the mid-office launch functions, which this
design does not move.

`tests/test_confirm_atomic.py` also pins `minting=True` and the absence
of `_MINTING` on `_draft_next_card`. That pin follows the function to
`stage_hold`. The assertion text stays.

## 9. Risks, non-goals, rollback

### Risks

- Moving `_note_look` in slice 1, while `_superseded_card` and
  `_stale_confirm_body` stay in `stage_state.py`, creates a load cycle
  between `stage_note` and `stage_state` and a new mutual pair. Slice 1
  moves only `render_tracking`. Slice 2 moves `_note_look` and those
  callers together.
- A moved body that gains or loses a line is a behaviour change. Review
  the diff as a relocation.
- Hoisting `stage_hold`'s import of `fo_chat_locks` adds a breaker
  (`projects` → `stage_hold`) and the 28-pair allowlist would grow.
  Section 5 forbids that hoist.
- The `_commit_pointer` spy, if left only on `stage_state` after slice 2,
  can stay green on room grants and stop wrapping the save. Section 8
  is the retarget that prevents that. Product code that is not under
  that patch still calls the same `_commit_pointer`.
- A new module that imports `stage_track` reopens the boundary the
  guard and `tests/test_stage_boundary.py` close. Both tests gain the
  new modules in the slice that creates them.
- Re-exporting a moved name from `stage_state` would make a missed
  caller look imported while the real global lives on the new module.
  The slices do not re-export.
- `stage_landing.py` and `stage_replies.py` stay large. This design is
  not a promise to split them.

### Non-goals

- No change to confirm order, the stage-5 exemption, the untrusted-content
  fence, or the `essay.stage` schema.
- No edit under `src/essay_writer/prompts/`, no edit of `tools.json`, no
  version bump, no tag, no release.
- No split of `stage_landing.py` or `stage_replies.py`.
- No further split of `_run_stage`. The early-tool order stays in
  `stage_track.py`. That split is out of this pass. It is not a slice
  waiting on a yes.
- No package-wide hoist of deferred imports, and no edit of the 28-pair
  or 46-pair allowlists.
- No change to mid-office launch, to `mid_spawn.py`, or to which shell
  `stage_host_launch` selects.
- No rename of public tools, `StageArgs` fields, or glossary words that
  already name a module. New glossary rows for `stage_note` and
  `stage_hold` are written in slice 2, when the modules exist.

### Rollback

Each slice is one commit. Revert that commit. There is no data migration
and no on-disk format change. The allowlists do not change, so a revert
does not restore a list. A reverted slice leaves `essay.stage` and the
stage files as they were.

## 10. Decisions from the independent reviewer

Q1, Q2, and Q3 are closed. The independent reviewer approved the seams.
None of these decisions starts an implementation slice. Q4 stays out of
this pass and is not proposed work.

**Q1.** Approved. `stage_note` stays a separate module.

**Q2.** Approved. `CardRun` lives on `stage_hold.py`.

**Q3.** Approved. The names `stage_note` and `stage_hold` are approved.

**Q4.** Out of this pass. Further splits of `_run_stage`, and any split
of `stage_landing.py` or `stage_replies.py`, are not proposed. A later
design would have to say so on its own. This document's slices stop
after the note module and the hold module. Q4 is not an approved
implementation slice.
