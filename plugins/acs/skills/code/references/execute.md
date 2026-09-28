# /acs:code — the implementer phase

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/execute.md`.*

Identical on every delivery path. What the path decides is HOW MANY
implementers (`acs:code-implementer`, one per file-map partition) run this,
and that is its own SKILL.md's to say.

---

## Implement (per iteration) — TDD

**Declare each task's file map before you spawn its implementer** (MAR-529) —
the `<task>` names it for the implementer to read, and this is what the
PreToolUse guard enforces while any `write`-kind agent runs,
so an undeclared map means no enforcement at all:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --iteration <n> --task <k> --file src/a.py --file tests/test_a.py
```

One call per implementer task, additive (declaring task 2 never erases task 1),
with the exact paths the plan's `## Executor tasks & file map` lists for that
task — you transcribe that table, you never widen it. `/acs:create-impl-plan`
already declared iteration 1's map when it published the plan; check it with
`acs.py filemap show --iteration 1` and declare it yourself when it is empty
(a hand-written plan, or one predating that skill). A write outside the
declared paths is then denied while an acs implementer
is running, with the implementer told to return `needs_input` for the file it
needs — you adjust the map, it does not improvise scope. Re-declare for the
iteration before dispatching remediation implementers; the guard reads the
highest declared iteration.

## Parallel implementers — one message, one slice per partition

**Whenever the plan's file map splits into disjoint partitions, the
implementers run in parallel from iteration 1.** That is the default, not an
optimisation a leg opts into; the leg's SKILL.md says how many partitions its
path allows, and the mechanics below are the same on every path that runs more
than one.

- **The partition rule.** One partition is one task `k` of the plan's
  `### Executor tasks & file map` table: exactly the files that row lists — the
  map you declared with `filemap set --task <k>`. The slice id is that task
  number `k` (`1`, `2`, …). Two tasks that name the same
  file — source, test or doc — or where one needs to read the other's edits
  mid-flight, are ONE partition: merge them into one task before declaring,
  never spawn them side by side. Check it mechanically before spawning:
  `acs.py filemap show --iteration <n>` lists every task's paths, and no path
  may appear under two tasks. That check is what guarantees two slices cannot
  overlap — the guard enforces the union of the maps, not each slice's own
  (see `acs_lib/filemap.py`), so disjointness is yours to establish.
- **One message.** Spawn every implementer of a wave in ONE message — one
  Agent call per slice, all in the same assistant message, in the foreground —
  then wait for ALL of them before anything else happens.
- **The slice travels on the wire.** Each task carries it,
  `<task skill="code" phase="implementer" slice="<k>" …>`, and the
  implementer echoes it on its `<result skill="code" phase="implementer"
  slice="<k>" …>`, so the SubagentStop hook files each slice's snapshot under
  its own name and parallel results never overwrite each other. A single,
  un-sliced implementer omits `slice` exactly as before.
- **One report per slice**: `steps/code/iter-<n>/implementer-<k>.json`; a
  single un-sliced implementer writes `iter-<n>/implementer.json`. The
  post-hook reads every `implementer*.json` of the iteration, so the per-slice
  reports are the join — nothing merges them by hand.
- **The cap.** At most `max_parallel = 4` implementers per message. More
  partitions than that run in waves of at most four, each wave one message,
  the next wave spawned only once every slice of the previous one returned.
- **One branch, one working tree.** Every slice commits on the run's branch.
  An implementer stages and commits ONLY its own file map's paths, by name —
  never `git add -A` or `git commit -a`, which would sweep up a sibling's work
  in flight — and on `index.lock` contention it waits briefly and retries the
  commit. Nothing is ever forced.
- **After the wave.** Every slice `completed` → the partition work is done. A
  slice that returned `needs_input` or `failed` does not undo its siblings'
  green commits: resolve that slice (answer its questions, adjust its file
  map) and re-run THAT slice alone, under the same `k`.
- **Then the seams — a join is not a synthesis.** Parallel slices can disagree
  where their partitions meet: a call site that crosses the boundary, a type
  or name both sides use, a migration and the code that reads it. Each
  implementer lists what it saw in its report's `seams` field. The integration
  slice, `slice="integration"`, is the one pass that reconciles them: ONE more
  implementer, spawned alone after every slice returned and before
  `/acs:review-code`, given every slice's report and the union of their diffs.
  It reconciles ONLY the seams — never a slice's substance — returns
  `needs_input` with a question on a conflict the evidence cannot settle, and
  writes `iter-<n>/implementer-integration.json` listing each seam it changed
  (file, what, why, which slices). Its map is declared as one more task
  (`filemap set --task <m>`, the next free number). Your leg's SKILL.md says
  whether it always runs (`complex`) or only when a slice reports a seam
  (`small`, `standard`); it is skipped whenever only one implementer ran.
- **Iteration 2+.** Group the verdict's confirmed findings by the partition
  that owns the file each one names; each group is one slice, spawned the same
  way. A seam finding — one whose file no partition owns, or that spans two
  partitions — goes to the integration slice, given the union of their maps —
  never to two implementers.

## Each implementer — in order

Send each implementer a `<task phase="implementer">` (with `slice="<k>"` when
several run) naming its spec file, the
resolved `plan.md`, `test-cases.md` when it exists, and its
file map (include `<constraint name="docs_only">true</constraint>` when it
applies). Each implementer (artifact `steps/code/iter-<n>/implementer.json`, or
`iter-<n>/implementer-<k>.json` in the same directory when several run in
parallel) must, in order:

1. **Write failing tests first** for the spec's Test plan, run them, confirm
   they fail for the right reason. **When `test-cases.md` exists** (written by
   `/acs:create-test-docs`), its `TC-n` rows for this task's scope ARE the test
   plan: write one test per case, name the `TC-n` id in the test's docstring,
   and report any case you could not write as a `problems` entry rather than
   silently dropping it. When the Test plan names e2e flows
   and `settings.e2e` is configured, the new/updated e2e tests are part of
   this step — same changeset, never a follow-up.
2. **Implement** until the tests pass, iterating against the TARGETED set the
   plan's test strategy names for that implementer's file map — `plan.md` is
   `/acs:create-impl-plan`'s output, so the scope is read, not re-derived.
   **Implementers never run the full unit suite.** It runs exactly once per
   iteration, in `/acs:review-code`'s final gate, and only once the review's
   reading stages come back clean: an iteration already going back to the
   implementer does not need a suite run to say so. The safety half is
   absolute — no zero-findings verdict without a green full-suite run on the
   iteration being passed.
   Code comments stay **minimal and idea-only**
   — one short single-responsibility line per new function (SOLID:
   one unit, one job), never a ticket id in source, and on edits only the
   comments the change actually invalidates (e.g. a changed parameter); no
   re-comment passes over unchanged logic. Test module filenames follow the
   same rule: they are named by the component/behavior under test, never by a ticket id;
   the originating ticket reference lives in the module docstring.
   The implementer also applies the **Simplicity First** and **Surgical
   Changes** authoring rules (see code-implementer.md Charter) throughout.
3. **Coverage** is measured in the review's final gate, off that same run,
   against `settings.test_coverage_percent`; implementers record
   `{"percent": null, "target": "measured in review"}`. When a spec's code
   genuinely cannot be covered (e.g. untestable generated code), the implementer
   says so in `problems` — that reason, not a number, is what you need for the
   hard-fail decision. See Coverage hard fail below.
4. **Reconcile product-doc facts — part of the change, not a follow-up**:

   **Product-doc factual reconciliation (also part of the change):** when the
   changeset makes a factual claim in `docs/product/prd.md` or
   `docs/product/roadmap.md` stale, reconcile it in the same diff. The
   factual-vs-intent boundary:

   - **Factual — sync autonomously:** agent/subagent counts; feature/epic
     shipped-vs-planned status; component topology; version numbers; file path
     references.
   - **Intent — flag in result document and PR body; NEVER rewrite:** goals;
     NFR (non-functional requirement) targets; scope statements; vision;
     requirements rationale.

   When the changeset contradicts stated intent, the implementer MUST flag the
   divergence in the implementer-report `problems` field so it surfaces in the
   coordinator's result document and the PR body. The implementer must NOT edit
   intent content. When the changeset alters no factual item in prd.md or
   roadmap.md, this step is a no-op for those files.

   **Boy-scout drift items — carried, never repaired here:** when the plan's
   `## Documentation map` names a doc section the plan's author found already
   disagreeing with the CURRENT code (its Boy-scout drift-repair survey), the
   implementer does NOT repair it in this step — it copies the item verbatim,
   with the cited doc section and `file:line` disagreement, into the
   implementer report's `problems` field, so `/acs:docs-sync` (which reads
   every implementer report's `problems` as a mandatory input) repairs it on
   the same branch/PR.
5. **Commit** the spec's work on the ticket branch per
   `formats.commit_message` (one or a few coherent commits per spec), staging
   only the implementer's own paths by name; on `index.lock` contention, wait
   briefly and retry. Never push, never force.
