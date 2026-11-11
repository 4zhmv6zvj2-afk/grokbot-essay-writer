# Design: import graph and stage-runner split

This is a design for review. It does not change behaviour, prompts, the tool
schema, the package version, or a release. `ARCHITECTURE.md` still describes
the code as it is. This note proposes a later, review-first split of the
remaining stage decision tree, and a guard for the import graph.

Measured from commit `a9c3b83bc8a98288e8c4f2715ead37e350f78748` (tag `v0.9.0`,
`pyproject.toml` version `0.9.0`). After `git fetch origin main`, `origin/main`
and the tag both resolved to that commit. No open pull request was waiting.

An independent reviewer should agree the seams in this note before any of the
implementation slices below are started.

## How the numbers were measured

Static `ast` walk of all 99 modules under `src/essay_writer/` (including
`_vendor` and package `__init__` files). Nothing was executed, and the walk
is not committed.

A **load edge** is a module-level `import` or `from … import`:

- Function and class bodies are excluded.
- `if TYPE_CHECKING` is excluded. The only such import is
  `docx.document.Document` in `word.py`. No package module is imported that way.
- `from pkg import name` also counts as loading `pkg.name` when that submodule
  exists.
- Specialist `__getattr__` maps are applied when a module-level import asks
  for a mapped name. Those maps are `_HOME` in `specialists/researcher.py`,
  `_WORD` plus `first_draft_blockers` in `specialists/writer.py`, and `_REVIEW`
  in `specialists/eqr.py`. Example: `health.py` line 38 imports
  `consensus_status` from the researcher, and the map loads `dig.py` before
  `health` finishes importing.

A **deferred edge** is the same import written inside a function, plus every
`__getattr__` map entry (those fire on attribute access, not at module load).

Cycles are strongly connected components (Tarjan). A deferred pair **breaks a
load cycle** when the target can already reach the source through load edges
alone. Hoisting that one import to module level would add a cycle. The return
path quoted below is a shortest load path.

**Branch nodes** inside a function: one for each `if`, `for`, `while`,
conditional expression, `except`, `assert`, and `match`; one extra for each
additional value of a boolean `and`/`or`; one for each comprehension filter.
Spans are `end_lineno - lineno + 1` from the AST, so they include the `def`
line and the docstring and exclude blank lines between functions.

What this walk does not see: `exec`, non-literal `import_module` calls, and
imports built as strings. The vendored bootstrap formats an `import_module`
string for a caller-supplied module name. That string is not a package edge.
Simple cycles longer than two modules inside the large deferred component
were not enumerated; the direct pairs and the 27 hoist-breakers are the
reviewable sets.

## 1. Import graph, as measured

### Load time

| Measure | Value |
| --- | --- |
| Modules | 99 |
| Load edges | 367 |
| Load-time components with more than one module | 0 |
| Load-time self-imports | 0 |
| Longest load chain | 15 modules (rank 0 through 14) |

The longest chain, from a root up to an entry point, is:

`paths` → `known_paths` → `records` → `state` → `textutil` → `diary` →
`assignment_gate` → `specialists.eqr` → `review` → `word` → `downloads` →
`dig` → `health` → `server` → `tools` (and `__main__`, which also stops on
`server`).

Rank is only the longest load path into a module. It is not a package layout
the code declares. Edges already point from a higher rank to a lower rank,
because that is how the rank was computed. Selected ranks:

| Rank | Modules |
| --- | --- |
| 0 | `paths`, `canon`, `stage_context`, `mid_spawn`, `prompt_loader`, `safe_url`, `programme`, `quarantine`, `pdf_read`, `pdf_year`, `first_run_common`, `specialists.researcher`, package `__init__` |
| 3 | `confirm` |
| 7 | `spine`, `specialists.grok_bot`, `late_chain` |
| 8 | `stage_llm` |
| 9 | `stage_state`, `cursor_office`, `build_office`, `fo_chat_locks` |
| 10 | `stage_landing` |
| 11 | `stage_replies` |
| 12 | `stage_track` |
| 13 | `server` |
| 4 | `projects` |

`stage_track` load-imports only these eight, all of lower rank:
`confirm` (3), `known_paths` (1), `paths` (0), `stage_context` (0),
`stage_landing` (10), `stage_llm` (8), `stage_replies` (11), `stage_state` (9).

`server.py` line 51 is the only module-level import of `stage_track`
(`essay_stage`). `projects.py` line 1460 imports `_run_card_only` inside a
function. `stage_state.py`, `stage_landing.py`, and `stage_replies.py` do not
import `stage_track` at load time or inside a function. That boundary is
already pinned by `tests/test_stage_boundary.py`.

`specialists/researcher.py` is rank 0 because its module body does not import
the package. `server.py` lines 38–43 import `essay_dig`,
`essay_research_summary`, `essay_research_full`, and `essay_pack_render_word`
at load time, and those names pull `dig`, `research`, and `word` through
`__getattr__`. `server.py` line 37 likewise pulls `review` through
`eqr.__getattr__`. Those triggered edges are in the 367, and they do not
close a load cycle.

### Deferred imports

| Measure | Value |
| --- | --- |
| Internal deferred import sites (one recorded target each) | 442 |
| Unique internal deferred pairs | 281 |
| Pairs that break a load cycle if hoisted | 27 |
| Pairs with no path back even when deferred edges count | 22, plus one artifact |
| Direct two-module cycles (either direction may be deferred) | 46 |
| External deferred import sites | 59, of which 28 are `docx` |

The 231 other unique pairs sit in one 70-module component once every
function-body import is treated as a permanent edge. That component is
transitive. It is not 70 handwritten cycles, and it is not an import-time
failure: the load graph those modules use at startup is still a DAG. A second,
separate component is the three-module set `confirm` → `records` →
`known_paths`, closed by the deferred import in `guard_write_door`. That is
the same fact as row `known_paths` → `confirm` in the table below.

The one artifact pair is `specialists.eqr` → the package `__init__`, from
`from essay_writer import review` at `eqr.py` line 952. The real target of
that statement is `review`, which is already in the breaker table.

The source rarely says why an import is inside a function. The stage-layer
docstrings do: `stage_track.py` lines 25–36, `stage_state.py` lines 1–8,
`stage_landing.py` lines 9–11, `stage_replies.py` lines 9–10, and
`stage_context.py` lines 10–11. `first_run_common.py` lines 1–5 records the
same idea for the install split. Everywhere else the reason below is the
graph, not a comment.

#### The 27 imports that keep the load graph a DAG

Hoisting any one of these to module level cycles the load graph along the
return path. Sites are `function:line` in the source module.

| Deferred import | Sites | Shortest load path back |
| --- | --- | --- |
| `assignment_gate` → `brief_contract` | `assignment_silence_gaps:320`, `read_assignment:376` | `brief_contract:17` → `assignment_gate` |
| `assignment_gate` → `specialists.eqr` | `_reason:505` | `specialists.eqr:21` → `assignment_gate` |
| `assignment_gate` → `specialists.writer` | `_reason:506` | `specialists.writer:18` → `assignment_gate` |
| `build_office` → `first_run` | `_copy_many:251`, `build_deliverable_handoff:269` | `first_run:21` → `first_run_host:18` → `build_office` |
| `cite_open` → `research_packs` | `_opened_year_rows:489` | `research_packs:21` → `harvard_4a:14` → `cite_open` |
| `debug_log` → `health` | `_health_land_snapshot:224`, `_health_run_ids:285` | `health:38` imports `consensus_status`, which loads `dig`; `dig:33` → `setup:28` → `debug_log` |
| `debug_log` → `ml_events` | `note_call:1254` | `ml_events:21` → `debug_log` |
| `diary` → `assignment_gate` | `blocked_identity_keys:1523`, `cover_field_rows:1191`, `cover_lines_from_field_rows:1316`, `ensure_house_cover_lines:1337`, `layout_for:1418`, `missing_cover_fields:1463`, `section_plan_for:603` | `assignment_gate:21` → `diary` |
| `invent` → `validate` | `_lookup_kept:124` | `validate:26` → `invent` |
| `known_paths` → `confirm` | `guard_write_door:229` | `confirm:26` → `records:22` → `known_paths` |
| `pdf_read` → `downloads` | `readable_pdf:21` | `downloads:44` → `word:46` → `validate:9` → `cite_open:25` → `pdf_read` |
| `pdf_year` → `cite_open` | `citation_year:175` | `cite_open:26` → `pdf_year` |
| `projects` → `fo_chat_locks` | `clone_sequence:1332`, `essay_project_delete:843` | `fo_chat_locks:17` → `projects` |
| `setup` → `dig` | `essay_setup:517`, `essay_setup:518` | `dig:33` → `setup` |
| `specialists.eqr` → `review` | `__getattr__:952`, `submit_pass_unlocked:502` | `review:19` → `specialists.eqr` |
| `specialists.eqr` → `word` | `_save_findings_docx:389` | `word:37` → `review:19` → `specialists.eqr` |
| `specialists.grok_bot` → `fo_chat_locks` | `maybe_seed_basics_on_draft:464` | `fo_chat_locks:22` → `stage_llm:39` → `specialists.grok_bot` |
| `specialists.grok_bot` → `server` | `front_office_call:703` | `server:44` → `stage_llm:39` → `specialists.grok_bot` |
| `specialists.grok_bot` → `stage_llm` | `confirm_line:308` | `stage_llm:39` → `specialists.grok_bot` |
| `state` → `stage_state` | `_fcntl:27` | `stage_state:40` → `stage_llm:39` → `specialists.grok_bot:22` → `state` |
| `textutil` → `assignment_gate` | `genre_for:252`, `word_rules_for:323` | `assignment_gate:23` → `textutil` |
| `textutil` → `cite_fit` | `prepare_word_citations:1165` | `cite_fit:25` → `textutil` |
| `textutil` → `diary` | `genre_from_brief_text:134` | `diary:13` → `textutil` |
| `textutil` → `harvard_4a` | `reference_parts:1238` | `harvard_4a:15` → `textutil` |
| `textutil` → `specialists.writer` | `word_rules_for:318` | `specialists.writer:17` → `textutil` |
| `textutil` → `validate` | `prepare_word_citations:1150` | `validate:33` → `textutil` |
| `user_place` → `late_chain` | `finished_word_copies:118` | `late_chain:29` → `user_place` |

None of `stage_track`'s own function-body imports are in this set. The stage
split can give the new modules ordinary module-level imports of the helpers
they call, as long as those modules do not import `stage_track` and do not
add a load edge that turns one of the 27 into a new shape (see the stage-7
skip note in the target section).

`projects.py` → `stage_track._run_card_only` is a real upward call, from rank
4 to rank 12, and it is **not** in the 27. Hoisting it would still leave the
load graph acyclic, because `stage_track` does not load-reach `projects`.
It is the one call-time import of the orchestrator from outside `server.py`.
The call sits in the new-sequence path (`projects.py` 1459–1462): after the
child sequence is stored, `door_card_reply` mints the stage card through the
injected runner. That is the same `CardRun` the state layer already uses.
The stage slices leave this call where it is.

#### Direct two-module cycles

Each line is a mutual import. `load` is module level. `defer` is function
body or `__getattr__`. There is no `load`/`load` pair.

```
assignment_gate -defer- brief_contract -load- assignment_gate
assignment_gate -load- diary -defer- assignment_gate
assignment_gate -defer- specialists.eqr -load- assignment_gate
assignment_gate -defer- specialists.writer -load- assignment_gate
assignment_gate -load- textutil -defer- assignment_gate
assignment_handoff -defer- research_packs -defer- assignment_handoff
brief_contract -defer- validate -defer- brief_contract
build_office -defer- cursor_office -defer- build_office
build_status -defer- specialists.grok_bot -defer- build_status
cite_fit -load- textutil -defer- cite_fit
cite_fit -defer- word_references -defer- cite_fit
cite_open -load- pdf_year -defer- cite_open
cite_open -defer- research_packs -defer- cite_open
debug_log -defer- health -defer- debug_log
debug_log -defer- late_chain -defer- debug_log
debug_log -defer- ml_events -load- debug_log
diary -load- textutil -defer- diary
dig -load- setup -defer- dig
downloads -defer- pdf_read -defer- downloads
downloads -defer- research_packs -defer- downloads
downloads -defer- roll_forward -defer- downloads
fo_chat_locks -load- projects -defer- fo_chat_locks
gates -defer- specialists.writer -defer- gates
harvard_4a -load- textutil -defer- harvard_4a
harvard_ref_check -defer- late_chain -defer- harvard_ref_check
harvard_ref_check -defer- review -defer- harvard_ref_check
invent -defer- textutil -defer- invent
invent -defer- validate -load- invent
late_chain -defer- ml_events -defer- late_chain
late_chain -defer- review -defer- late_chain
late_chain -defer- specialists.eqr -defer- late_chain
late_chain -load- user_place -defer- late_chain
late_chain -defer- word -defer- late_chain
pack_backup -defer- validate -defer- pack_backup
projects -defer- specialists.grok_bot -defer- projects
research -load- specialists.researcher -defer- research
review -load- specialists.eqr -defer- review
rewrite_baseline -defer- specialists.writer -defer- rewrite_baseline
server -defer- shells -defer- server
specialists.eqr -defer- specialists.grok_bot -defer- specialists.eqr
specialists.eqr -defer- word -defer- specialists.eqr
specialists.grok_bot -defer- stage_llm -load- specialists.grok_bot
specialists.writer -load- textutil -defer- specialists.writer
specialists.writer -defer- validate -defer- specialists.writer
specialists.writer -defer- word -defer- specialists.writer
textutil -defer- validate -load- textutil
```

`build_office` ↔ `cursor_office` is in this list. Both mid-office shells
import each other only inside functions. The stage slices do not retie that
pair, and they do not give either shell a new import of the other.

#### Deferred imports that do not close a cycle

These 22 can be moved to module level one at a time, or all together, without
creating a load cycle. The walk shows no path from the target back to the
source even after deferred edges are included. They are not part of the stage
split. Listed so a later cleanup can tell habit from a real breaker.

| Pair | Sites |
| --- | --- |
| `build_office` → `mid_spawn` | `spawn_grok:185` |
| `build_status` → `paths` | `_index_path:976`, `_session_path:988` |
| `cite_open` → `known_paths` | `open_for_citation:298` |
| `cursor_office` → `mid_spawn` | `spawn_agent:220` |
| `debug_log` → `doors` | `_tool_count:718` |
| `debug_log` → `programme` | `_cover_audit_fields:786` |
| `diary` → `programme` | `cover_field_rows:1192`, `blocked_identity_keys:1524` |
| `downloads` → `known_paths` | `_save_state:222` |
| `first_run_mac` → `quarantine` | `_clear_delivered:674` |
| `harvard_ref_check` → `handbook` | `_handbook_problem:185` |
| `invent` → `known_paths` | `read_gathered_text:49` |
| `late_chain` → `programme` | `_programme_cover_lines:421` |
| `late_chain` → `quarantine` | `_deliver_stage10:1250` |
| `late_chain` → `student_turns` | `quiet_stage5:217` |
| `originals` → `known_paths` | `essay_originals:91` |
| `programme` → `handbook` | `referencing_record:24` |
| `python_bootstrap` → `first_run` | `_package_main:36` |
| `research_packs` → `known_paths` | `open_critical_markdown:607`, `ship_4b:639` |
| `specialists.grok_bot` → `student_turns` | `stage7_lead:193` |
| `stage_replies` → `canon` | `_draft_reply:90` |
| `stage_state` → `canon` | `rebind_cloned_confirms:324` |
| `stage_track` → `student_turns` | `_turn_redirect:246` |

`docx` (28 sites), `zipfile` (7), and the standard-library names in the other
external sites are local imports around file reads and writes. They are not
package cycles. Leave them deferred.

#### Where dependency injection is already doing the work

Two callbacks exist so a lower layer can re-enter the runner without
importing it:

- `CardRun` (`stage_state.py`) is `_run_card_only` from the orchestrator.
  The state layer uses it to mint the next card and to reopen a saved
  stage's card. `projects.py` passes the same function into
  `door_card_reply`.
- `InheritedConfirm` (`stage_landing.py` line 38) is
  `_inherited_keep_confirm`. The landing helper never imports the
  orchestrator; the orchestrator passes the public confirm call in.

`stage_context.py` stays a leaf (rank 0, standard library only) so
`stage_state` can avoid importing the context types. The comment at
`stage_context.py` lines 10–11 is accurate: the state layer does not import
that module.

## 2. Stage runner, as measured

File sizes at this commit:

| File | Lines | Role today |
| --- | --- | --- |
| `stage_track.py` | 1115 | Orchestrator. Public `essay_stage`, card runner, confirm resolution, body build. |
| `stage_state.py` | 1462 | Pointer, commit journal, stage lock, tracking-note render, held and refused replies. 70 functions, AST span sum 1196. |
| `stage_landing.py` | 401 | Store a no-card stage, reports, mid-run start, miss collection, inherited-lock keep. 11 functions, span sum 338. |
| `stage_replies.py` | 397 | `_noop_result` (21), `_draft_reply` (135), `_save_confirm` (191). |
| `stage_context.py` | 95 | `StageArgs`, `ConfirmState`, `StageContext`. |
| `spine.py` | 116 | `AUTO_START`, and thin forwards to specialists. 12 functions, span sum 77. |
| `stage_llm.py` | 366 | Stage settings, including the untrusted-content fence on `rules`. |
| `cursor_office.py` | 439 | Cursor mid-office launch and spawn. |
| `build_office.py` | 311 | Grok Build mid-office launch and spawn. |
| `mid_spawn.py` | 51 | Shared child-process opener. |

`stage_state.py` is larger than the orchestrator. This design does not split
it. The decision tree that is still one file is `stage_track.py`.

### Functions in `stage_track.py`

| Function | Lines | Span | Branch nodes | Job |
| --- | --- | --- | --- | --- |
| `_continues_inherited_lock` | 95–118 | 24 | 9 | A later call still belongs to the parent look. |
| `essay_stage` | 121–161 | 41 | 0 | Public tool. Builds `StageArgs`, calls `_stage_call`. |
| `_run_card_only` | 164–186 | 23 | 0 | Injected card runner. Always `confirmPhase=draft`, `card_only=True`. |
| `_inherited_keep_confirm` | 189–209 | 21 | 0 | Injected keep. Calls public `essay_stage` with `CARD_CONFIRM`. |
| `_stage_call` | 212–239 | 28 | 8 | Runs `_run_stage`. On `DamagedStageCommit`, returns a stage refusal. Copies a quarantine notice onto the result. |
| `_turn_redirect` | 242–258 | 17 | 2 | Short student ask becomes a `turn` refusal. |
| `_run_stage` | 261–483 | 223 | 66 | Ordered policy, then confirm resolution, then body, then draft or save. |
| `_confirm_path` | 486–683 | 198 | 47 | Turns a confirm call into a `ConfirmState`, or returns a refusal dict. |
| `_prepare_stage_text` | 686–747 | 62 | 9 | Basics seed, cite look, short cites, body cites, outline weave. |
| `_stage_body_fields` | 750–799 | 50 | 4 | Payload, fingerprint, note path, base reply, including `rules`. |
| `_attach_stage_reports` | 802–837 | 36 | 6 | Outline, cite, student facts, north star, basics, assignment gaps, mid-office launch. |
| `_attach_stage_databases` | 840–847 | 8 | 2 | Database view for stage 1, stage 4a, or a held file. |
| `_stage7_skip_request` | 850–870 | 21 | 3 | Stage 7 skip probe. Shared by the runner, the confirm path, and the stage-7 draft body. |
| `_stage7_draft_body` | 873–984 | 112 | 26 | Stage 7 draft: skip, "no change", edit note, cite refresh. |
| `_build_stage_body` | 987–1115 | 129 | 15 | Gates, reports, stage 6 master block, stage 10 review, stage 4b reconcile. Returns `StageContext` or a refusal. |

The three large functions plus their helpers (`_prepare_stage_text` through
`_build_stage_body`) are the decision tree. Entry points above `_run_stage`
are small and stay in the orchestrator.

### How control flows

`essay_stage` only packs arguments. `_stage_call` is the damage wrapper.
`_run_stage` is the policy, in this order (line numbers are the start of
each step):

1. **Card runner.** Line 271. `card_run` is `None` while minting, otherwise
   `_run_card_only`. Minting must not mint another card.
2. **Identity.** Lines 276–278. `sequence_write_error` refuses before any
   branch. `tests/test_stage_split.py` covers a bad id.
3. **Early tools, before a stage note.** Lines 279–298.
   `encourageChoice` may redirect or call `answer_encourage`.
   `paperChoice` calls `choose_paper`. `lockChoice` may refuse.
   Each of these returns without loading the stage pointer.
4. **Phase and door.** Lines 299–305. `phase_refusal`, then
   `guard_write_door` on the sequence folder.
5. **Stage id and look.** Lines 306–319. Unknown stage refuses. A non-string
   look refuses. A string look is stripped. `_turn_redirect` runs on the look
   and on `answers`.
6. **Pointer and stage block.** Lines 320–327. Load the pointer and the
   genre. `inherited_lock_pending`. `_stage_refusal` unless this call is a
   mint of an allowed stage. A blocked confirm goes to `_confirm_blocked`
   with `card_run`.
7. **Inherited lock.** Lines 330–375. `keep` calls `_inherited_lock_keep`
   with `_inherited_keep_confirm`. `revise` / `relock` may prepend the parent
   look and, when the waiting card does not carry that look, downgrade this
   call from confirm to draft and clear the card fields. A pending lock with
   no choice, outside a mint and outside a keep, returns
   `prior_saved_lock_ask` unless `_continues_inherited_lock`.
8. **Stage 5 has no confirm card.** Lines 376–390.
   `advances_without_confirm(stage)` is `"6"` for stage `"5"` and `None`
   otherwise (`spine.py` lines 13–20). A confirm call on that stage returns
   the fixed "no save-card between this step and the next" refusal and does
   not enter `_confirm_path`.
9. **Typed save fallback.** Lines 391–410. A confirm with no card fields, and
   a look that `typed_save_word` accepts, binds `CARD_CONFIRM` to the waiting
   digest. The card path stays preferred.
10. **Empty confirm.** Lines 411–418. Confirm, no waiting digest, no draft:
    `_noop_result`.
11. **Confirm resolution.** Line 426. `_confirm_path`. A dict return is a
    refusal and stops the call. A `ConfirmState` supplies the fields for the
    body.
12. **Stage 7 skip on the draft path.** Lines 438–449. Only when
    `stage == "7"` and the phase is still draft.
13. **Body.** Line 461. `_build_stage_body`. A dict return stops the call.
14. **Draft or save.** Lines 464–468. Draft calls `_draft_reply`. Any other
    phase calls `_save_confirm` with `card_run`. A mint is always a draft, so
    the save branch always has the runner.
15. **Lock bookkeeping.** Lines 469–482. After a stored success, mark the
    pending inherited lock resolved. An `OSError` sets a notice and still
    returns the stored result.

`_confirm_path` runs only for a call that reached step 11. Inside a confirm
phase (`stage_track.py` 513–672) the order is:

- Resolve a press from `cardAction`, then from `look`.
- Stage 7 skip probe. A skip returns immediately.
- "All fine" / `answers_mean_no_change`, with or without a matching card,
  downgrades the phase to draft and may restore the saved look from the
  waiting draft. That call does not save.
- Otherwise: a superseded card returns `_older_card`; a press for another
  stage returns `_reoffer_confirm`; a press for this stage with a matching
  card grants room and clears the look; a press for this stage without a
  match grants room and reoffers; a card mismatch or a room block reoffers;
  a typed save word clears the look; a missing card with an empty look
  reoffers.
- If the phase is still confirm and the card matches, answers, edits, the
  web check, and the look are cleared, then `_hydrate_card` fills the stored
  draft fields.

The function returns one `ConfirmState`. It does not write the pointer except
through `_grant_room` on a matching press.

`_build_stage_body` (`stage_track.py` 1012–1090), after the confirm path has
returned:

- `_prepare_stage_text` seeds basics (skipped for a mint, for stage 5, and
  for a non-draft by `maybe_seed_basics_on_draft` in
  `specialists/grok_bot.py`), runs `cite_look`, applies a short-cite request,
  and on `BODY_CITE_STAGES` runs `land_body_cites` and `weave_short_cites`.
  The set is `frozenset({"5", "6", "7", "8"})`, defined in `cite_fit.py` and
  imported by `specialists/writer.py`.
- `_collect_stage_misses` in `stage_landing.py`. A mint skips the student
  surface check and the contract check. Stage 5 uses `north_star` plus
  `stage5_draft_blockers`. Every other stage uses `gate_save`. A miss returns
  immediately.
- Stages 2 and 3 inside the revisit window refuse an empty note.
- `_stage_body_fields` copies `stage_settings` into the reply, including
  `rules` and `source`.
- `_attach_stage_reports` and `_attach_stage_databases`.
- Stage 6 merges `stage6_fields`. Confirm refuses when the master Word file
  is still unknown.
- `_stage7_draft_body` may return a skip or an edit refusal, and may rewrite
  answers, the edit, and the web check.
- Stage 10 confirm, when `chain_armed` is set, calls `spine.final_review`
  and refuses on a block.
- Stage 4b calls `spine.stage_reconcile` and stores `download_check`.
  `real_bib` goes onto the `StageContext` for the draft reply.
- Anything else returns a `StageContext`. The orchestrator then chooses
  `_draft_reply` or `_save_confirm`.

Stage 5's store is not in `_build_stage_body`. `_draft_reply`
(`stage_replies.py` 154–167) sees `auto_next` and calls `_store_stage`.
`_store_stage` (`stage_landing.py` 193–198) runs `quiet_stage5` for stage 5
and opens stage 6 when the following stage is `"6"`.

## 3. Behaviour the split has to keep

These are already implemented. Each slice keeps the same calls and the same
order. None of the slices edit prompt files, `tools.json`, or student-facing
sentences.

### Confirm gate

- `spine.AUTO_START` is `{"5": "6"}`. `stage_uses_confirm_card` is false only
  for a stage in that map. `advances_without_confirm("5") == "6"`, and it is
  `None` for 7, 8, and 9. Pinned by `tests/test_layer6_spine.py`,
  `tests/test_confirm_card.py`, `tests/test_stage_confirm_isolation.py`,
  `tests/test_digest_does_not_advance.py`, and `tests/test_confirm_bindings.py`.
- `_run_stage` steps 8–10 and 14 stay in the orchestrator, so a confirm on
  stage 5 still refuses before `_confirm_path`, and a save of any other stage
  still goes through `_save_confirm`.
- `_confirm_path` keeps the press, card match, superseded card, and room-block
  order in section 2. Moving the function means moving that block whole.
- `_draft_reply` still mints a confirm card when `auto_next` is absent, and
  still stores without a card when `auto_next` is set.

### Stage 5 draft exemption

The exemption is the whole path, not only the refusal string:

1. `advances_without_confirm("5")` supplies `auto_next == "6"`.
2. A confirm-phase call refuses at `_run_stage` lines 379–390.
3. A draft that passes `_collect_stage_misses` (north star and
   `stage5_draft_blockers`, not `gate_save`) is built with that `auto_next`
   on the `StageContext`.
4. `_draft_reply` calls `_store_stage` instead of minting a card.
5. `_store_stage` quiets the stage 5 reply and opens stage 6.

`tests/test_stage5_quiet_and_bot.py` is the behaviour file for that path.
The body builder must keep passing `auto_next` through. It must not start
treating stage 5 as a card save.

### Untrusted-content fence

`UNTRUSTED_FENCE` is `stage_llm.py` lines 92–97. `stage_rules` appends it
(line 264) and says the fence ends every rules value. `stage_settings`
puts that string on `rules` (line 278). `_stage_body_fields` copies
`item["rules"]` and `RULES_SOURCE` onto the reply (lines 784–785).

`tests/test_untrusted_content.py` pins the same sentences on the server
briefing, the write seat, and every stage rule from `stage_settings`. The
body slice keeps the two assignments. It does not reword the fence. Server
instructions and seat files are untouched because `stage_llm.py` is untouched.

### Public MCP tool

- `essay_stage` (`stage_track.py` 121–139) stays the tool function. Parameter
  names stay as they are (`confirmPhase`, `cardAction`, `cardDigest`,
  `encourageChoice`, `paperChoice`, `lockChoice`, and the rest).
- `StageArgs` in `stage_context.py` stays the schema object. The slices do
  not add or drop a field.
- `server.HANDLERS["essay.stage"]` stays `essay_stage` (`server.py` line 88).
  `tests/test_layer6_spine.py` and `tests/test_cite_fit.py` pin that identity,
  including both shells' handler maps.
- `prompts/front_office/tools.json` already says stage 5 stores on the draft
  and starts stage 6 with no Confirm card. That file is not part of any slice.

### Both mid-office shells

`_attach_stage_reports` (`stage_track.py` 835–837) sets
`mid_office_launch` from `cursor_office.stage_host_launch`. That function
(`cursor_office.py` 419–433) reads the stored shell. The Cursor shell gets
`cursor_stage_launch`. Any other stored shell gets `build_office.stage_launch`.
The docstring on 426 says Cursor and Grok Build share `stage_settings`.

`_attach_mid_run` (`stage_landing.py` 205–240) starts the child with
`start_4a_research` or `start_stage_mid`, passing that launch dict. The
docstring says both hosts share the decision. `mid_spawn.open_mid_child` is
the shared opener (`build_office.spawn_grok` line 185, `cursor_office.spawn_agent`
line 220).

The body slice keeps the call to `stage_host_launch`. It does not call
`cursor_stage_launch` from the stage body. `tests/test_cite_fit.py` AC5
already requires both shells to share the stage row and the cite gate.
`tests/test_mid_office_binary_resolve.py`, `test_mid_office_status_lines.py`,
`test_mid_office_dig.py`, `test_mid_office_stdio_exit.py`,
`test_mid_spawn_boundary.py`, and `test_build_office.py` stay on every slice
that moves the launch field. There is no residual shell: both hosts stay on
the existing branch. No slice adds a Cursor-only launch.

## 4. Target

### Dependency direction

Five rules. They describe the graph the slices are allowed to produce.

1. **The load graph stays a DAG.** New module-level imports may target
   anything that does not already load-reach the importer. The guard in
   section 6 fails the build on a new load cycle.
2. **A function-body import is required only for a pair in the 27.** New
   code uses a module-level import unless the guard would fail. The 22
   hoist-safe pairs may stay deferred; moving them is a different cleanup.
3. **`stage_track` is imported at module level only by `server.py`.**
   `projects.py` may keep the one function import of `_run_card_only` until
   a reviewer accepts a separate injection slice. `stage_state`,
   `stage_landing`, `stage_replies`, `stage_confirm`, and `stage_body` do
   not import `stage_track` at all.
4. **The new modules sit under the orchestrator.** `stage_track` load-imports
   them. They load-import the helpers they call. They do not import each
   other in a cycle. `stage_body` may load-import `stage_confirm` for the
   shared stage-7 skip probe. `stage_confirm` does not import `stage_body`.
5. **Injection stays where a callback would import the orchestrator.**
   `CardRun` and `InheritedConfirm` stay. `_run_card_only` and
   `_inherited_keep_confirm` stay in `stage_track.py` because they call back
   into `essay_stage` / `_stage_call`.

`cursor_office` and `build_office` stay peers. Both may keep their deferred
imports of `mid_spawn`. Neither gains a module-level import of the other as
part of this work. A stage module calls `stage_host_launch`, which already
chooses the shell.

Do not move `_stage7_skip_request` into `stage7.py` if that adds a
module-level import from `stage7` (rank 5) to `stage_state` (rank 9).
`stage_state` already imports `stage7` inside a function. A new load edge the
other way would put that existing import into the breaker set the moment
anyone hoists it, and it would be an upward load edge today if written at
module level. A function-body import the other way would only add another
mutual deferred pair. The target avoids both: the probe lives next to the
confirm path, and `stage7.py` keeps the question text and the skip matcher
it already has (`answers_mean_skip`).

### What moves, and what stays

Stay in `stage_track.py`:

- `essay_stage`, `_stage_call`, `_run_card_only`, `_inherited_keep_confirm`
- `_continues_inherited_lock`, `_turn_redirect`
- `_run_stage`, including steps 1–10 and 14–15 in section 2 (early tools,
  the stage-5 confirm refusal, the typed-save fallback, the empty confirm,
  the draft-versus-save branch, and the lock-resolved notice)

Move together into `stage_confirm.py`:

- `_confirm_path`, unchanged in order
- `_stage7_skip_request`, because `_confirm_path`, `_run_stage` step 12, and
  `_stage7_draft_body` all call it, and it cannot stay in `stage_track.py`
  once `_confirm_path` has moved (that would make `stage_confirm` import the
  orchestrator)

Move together into `stage_body.py`:

- `_prepare_stage_text`
- `_stage_body_fields`
- `_attach_stage_reports`
- `_attach_stage_databases`
- `_stage7_draft_body`
- `_build_stage_body`

`stage_body.py` imports `_stage7_skip_request` from `stage_confirm.py`.
`_build_stage_body` still calls `_collect_stage_misses`,
`_attach_outline_report`, `_attach_short_report`, and `_attach_cite_report`
in `stage_landing.py`. Those landing helpers stay where they are.

`stage_state.py`, `stage_replies.py`, `spine.py`, and `stage_llm.py` stay
put. `_draft_reply` and `_save_confirm` stay the only writers of a draft
card and a saved stage.

### How each seam keeps the current behaviour

**Confirm module.** `_confirm_path` is moved as one function. The orchestrator
calls it at the same point in `_run_stage` (today line 426) and still treats
a dict as a finished refusal and a `ConfirmState` as the input to the body.
Stage 5 never reaches it on a confirm phase, because step 8 stays in
`_run_stage`. The skip probe's body stays the same three checks: stage is
`"7"`, `answers_mean_skip` on the look or the answers, then
`_stage7_skip_reply` in the state layer.

**Body module.** `_build_stage_body` is moved as one function with its
helpers. `auto_next` remains an argument and is still stored on
`StageContext`. Stage 5 therefore still reaches `_store_stage` from
`_draft_reply`. `rules` and `source` are still copied from `stage_settings`,
so the fence still ends the rules string on the reply.
`mid_office_launch` is still `stage_host_launch(stage)`, so Cursor and Grok
Build still share that field. Stage 6's master-file refusal, stage 10's
`final_review`, and stage 4b's `stage_reconcile` stay in that function in
the same order. Cite landing still goes through `land_body_cites` when
`stage in BODY_CITE_STAGES`, which is the condition
`tests/test_cite_fit.py` AC4 reads off the source.

**Orchestrator.** The public signature does not change. The order of early
returns does not change. The quarantine wrapper does not change. The runners
passed into the state and landing layers do not change.

No slice re-exports the moved private names from `stage_track.py`.
`tests/test_stage_boundary.py` already rejects that pattern. Callers in
tests switch to the new module in the same slice that moves the function
(`tests/test_brief_contract.py` imports `_build_stage_body`;
`tests/test_cite_fit.py` imports `_prepare_stage_text` and
`_stage7_draft_body`).

## 5. Implementation slices

Each slice is one change, reviewable on its own, and safe to revert on its
own. A later slice starts only after the previous one is green. No slice
bumps the version, edits a prompt, or edits `tools.json`.

### Slice 1 — import guard, no moves

Add the test described in section 6. Allowlist the 27 pairs as they are
today. Do not move a function. The existing suite, including
`tests/test_stage_boundary.py`, stays green without edits.

This slice is the ratchet. Later slices may shrink the allowlist. They may
not grow it.

### Slice 2 — confirm path

Create `stage_confirm.py` and move `_confirm_path` and `_stage7_skip_request`
with their bodies unchanged. `stage_track.py` load-imports the new module and
calls the same names. Update any test import that named those functions on
`stage_track` (none do today; `_confirm_path` is not imported by the tests
that were searched).

Check before merging the slice:

- Load graph still a DAG, and the 27-pair allowlist is unchanged.
- `stage_confirm` does not import `stage_track`.
- `advances_without_confirm` is still called from `stage_track.py`
  (`tests/test_layer5_callers.py` reads that file for the name).
- Confirm-card tests, stage 7 confirm tests, and `tests/test_torn_confirm.py`
  pass with no assertion edits.
- Stage 5 tests pass. This slice does not move the stage-5 store.

### Slice 3 — body

Create `stage_body.py` and move the six body functions with their bodies
unchanged. `stage_body` load-imports `stage_confirm` for the skip probe.
Point `tests/test_brief_contract.py` and `tests/test_cite_fit.py` at the new
module. Keep the source assertions (`_collect_stage_misses` inside
`_build_stage_body`; `stage in BODY_CITE_STAGES` and `land_body_cites` inside
the prepare and stage-7 draft sources).

`tests/test_layer6_spine.py` requires the text `essay_writer.spine import
final_review` to appear in `stage_track.py`. After this move that import
lives in `stage_body.py`. Widen that read to the new file in this same
slice. Keep the count and the string. Do the same for any other source pin
that names a moved import. Known pins that read `stage_track.py` as text:

- `tests/test_layer5_callers.py` — `advances_without_confirm` must remain in
  `stage_track.py`. `gate_save` and `stage_bibliography` counts are across
  the orchestrator plus landing plus replies; this slice should not change
  those counts.
- `tests/test_layer6_spine.py` — `final_review` import, `assignment_gate`
  absent from the orchestrator, `quiet_stage5` still in the landing/reply
  side.

In this same slice, update `ARCHITECTURE.md` so it names `stage_confirm.py`
and `stage_body.py`, and update `tests/test_stage_boundary.py` so its
docstring pin matches the new sentences. The three existing layers stay
forbidden from importing `stage_track`. Add the two new modules to that
forbidden set.

Check before merging the slice:

- The confirm-gate, stage-5, fence, and handler-identity tests listed in
  section 3 pass.
- `tests/test_untrusted_content.py` passes without a fence edit.
- `tests/test_cite_fit.py` AC4 and AC5 pass, including the both-shells
  handler check.
- The mid-office files listed in section 3 pass. The launch call is still
  `stage_host_launch`.
- The import guard passes. Expect no new breaker. `stage_body` →
  `stage_confirm` is a new load edge and must not create a component.

### Slice 4 — stop

Do not keep splitting `_run_stage` in this pass. The early-tool order is the
product policy, and it is already a straight sequence of returns. A further
file would scatter that order without removing a second decision tree.

A follow-up, only if the reviewer asks for it in writing: change
`projects.py` to receive the card runner from the server (or from a tiny
leaf both can import) and delete the function import of `_run_card_only`.
That follow-up is not one of slices 1–3. It touches sequence creation, so
`tests/test_mac_sequence_folder.py` and the project tests have to be in its
own check list. It is optional because the current call does not break the
load DAG.

## 6. Test and guard plan

### Behaviour suite

Every slice runs the full suite (`pytest`) on the same Python floor the
package already requires (3.12+). The tests that define "this slice kept
the door" are the ones named in sections 3 and 5. A slice that only moves
code should not need assertion changes except:

- import paths of moved private helpers
- source pins that read a file the helper left
- the architecture-doc sentences in `tests/test_stage_boundary.py`, and only
  in slice 3

`tests/test_stage_split.py` (bad id, then draft-and-confirm on stage 1)
runs on slices 2 and 3 as the shortest routing check. Stage routing beyond
that file is the existing stage, confirm, and stage-5 files, not a new
parallel suite.

### Import guard

New test module, proposed path `tests/test_import_graph.py`. It reimplements
the walk in section 1 (load edges, triggered `__getattr__` names, deferred
edges) and asserts:

1. Every load-time component has one module. No self-import.
2. The set of deferred pairs that break a load cycle equals a checked-in
   allowlist of the 27 `(source, target)` pairs in section 1. Order does not
   matter. A new pair fails. Deleting a pair updates the allowlist in that
   same change, so the list can shrink on purpose.
3. The only imports of `stage_track` are `server.py` (module level,
   `essay_stage`) and `projects.py` (inside a function, name
   `_run_card_only`). Comments do not count; the walk uses `ast`.
4. `stage_state`, `stage_landing`, `stage_replies`, and, from slice 3,
   `stage_confirm` and `stage_body`, have zero imports of `stage_track`.

The guard does not forbid the 46 mutual pairs that already exist, and it
does not fail when a hoist-safe deferred import stays inside a function.
Growing a new direct two-module cycle that is entirely deferred would not
fail rule 2. That gap is an open question.

`tests/test_stage_boundary.py` stays. It is the runtime half: importing the
state, landing, and reply modules does not put `stage_track` in
`sys.modules`. Slice 3 extends that idea to the two new modules if the
reviewer wants the runtime check, not only the AST check. The AST check is
the one that sees function-body imports.

### Stage routing tests

No new routing framework. Slices 2 and 3 rely on:

| File | What it holds still |
| --- | --- |
| `tests/test_stage_split.py` | Bad id refuses before a branch. Stage 1 draft then confirm stores. |
| `tests/test_stage_confirm_isolation.py` | Confirm cards do not leak across stages. `AUTO_START` is stage 5 only. |
| `tests/test_stage_card_ids.py` | Card identity. |
| `tests/test_stage7_confirm_advance.py` | Stage 7 confirm. |
| `tests/test_stage5_quiet_and_bot.py` | Stage 5 stores on the draft and opens stage 6. |
| `tests/test_stage_launch_status.py` | Mid-office launch status on a stage reply. |
| `tests/test_torn_confirm.py` | A torn confirm does not save. |
| `tests/test_confirm_card.py`, `test_confirm_card_save.py`, `test_confirm_bindings.py` | Card press, digest binding, `advances_without_confirm`. |
| `tests/test_cite_fit.py` | Shared cite gate for stages 5–8, both shells. |
| `tests/test_untrusted_content.py` | Fence text on rules. |

## 7. Risks, non-goals, rollback

### Risks

- A move that reorders two `if` blocks inside `_confirm_path` or `_run_stage`
  changes who gets a card. The slice rule is to move a function without
  editing its body. Review the diff as a relocation, and treat any inserted
  line inside the function as a behaviour change that stops the slice.
- Source pins (`getsource`, whole-file reads) fail if the import string moves
  and the test is not updated in the same commit. Section 5 names the known
  pins. A missed pin fails CI; it does not silently change the product.
- Dropping `body["rules"] = item["rules"]` would take the fence off the
  stage reply even though `stage_settings` still appends it. The fence test
  reads `stage_settings`, not the reply body, so it would stay green. Slice
  3 review should look at that assignment directly. The open-question list
  asks whether a reply-body assertion should be added.
- Calling `cursor_stage_launch` from the body would drop Grok Build.
  `stage_host_launch` is the call that keeps both.
- A new module that imports `stage_track` reopens the boundary the last
  split closed. The guard's third and fourth assertions exist for that.
- `stage_state.py` (1462 lines) and `_save_confirm` (191 lines) remain large.
  This pass can be mistaken for a promise to split them. It is not.

### Non-goals

- No change to confirm semantics, the stage-5 exemption, the fence sentences,
  or the `essay.stage` schema.
- No edit under `src/essay_writer/prompts/`, no version bump, no tag, no
  release.
- No split of `stage_state.py`, `stage_replies.py`, or `stage_landing.py`.
- No package-wide removal of the 46 mutual pairs, and no drive to hoist the
  22 safe deferred imports.
- No Cursor-only mid-office path, and no change to `mid_spawn.py`.
- No rename of public tools, `StageArgs` fields, or module vocabulary already
  in `docs/GLOSSARY.md`.

### Rollback

Each slice is one commit that moves functions or adds a test. Revert that
commit. There is no data migration and no on-disk format change. The guard's
allowlist reverts with the commit that changed it. A reverted slice leaves
the public tool and the stage files as they were.

## 8. Open questions for the independent reviewer

1. Are the two new modules (`stage_confirm.py` for `_confirm_path` and
   `_stage7_skip_request`, `stage_body.py` for the six body functions) the
   right seams, with `_run_stage`'s early returns and the stage-5 confirm
   refusal staying in `stage_track.py`?
2. Is housing `_stage7_skip_request` in `stage_confirm.py` acceptable, given
   that `stage_body.py` then load-imports `stage_confirm.py` and
   `stage_confirm.py` does not import `stage_body.py`? The alternative on
   the table is to pass the probe into `_confirm_path` as an argument so the
   two new modules do not import each other. Putting the probe in `stage7.py`
   is the option this note rejects, for the rank reason in section 4.
3. Should the new modules use module-level imports except where the target
   is one of the 27 breaker pairs? This note says yes.
4. Is the guard allowed to freeze the 27 breaker pairs and to leave the 46
   existing mutual pairs unforbidden? Should a *new* direct two-module cycle
   fail the guard even when both directions are deferred?
5. Is `projects.py`'s function import of `_run_card_only` an accepted
   leftover, or should a separate slice (not slices 1–3) inject that runner?
6. Is the 70-module deferred component out of scope for this pass? This note
   treats it as out of scope. The direct pairs are listed so that decision
   is about a known set.
7. Source pins in `tests/test_layer5_callers.py`, `tests/test_layer6_spine.py`,
   `tests/test_cite_fit.py`, and `tests/test_brief_contract.py` get retargeted
   in the slice that moves the function, and `ARCHITECTURE.md` is updated in
   slice 3 together with `tests/test_stage_boundary.py`. Is that the right
   moment, rather than rewriting those pins into behaviour assertions first?
8. `tests/test_untrusted_content.py` pins `stage_settings`, not the `rules`
   field of a live stage reply. Should slice 3 add one assertion that a
   draft reply's `rules` still ends with `UNTRUSTED_FENCE`?
9. The walk is static. It does not execute the deferred imports, and it does
   not list simple cycles of length greater than two inside the 70-module
   component. Is that evidence enough to start slice 1, or should the guard
   be prototyped against this commit and the allowlist diffed before slice 2?

Slices 1–3 wait on answers to questions 1–4. Questions 5–9 can be answered
as "leave it as written" without changing the seams.
