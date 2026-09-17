# /acs:code — the execute phase

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/execute.md`.*

Identical on every delivery path. What the path decides is HOW MANY
executors run this, and that is its own SKILL.md's to say.

---

## Execute (per iteration) — TDD

**Declare each task's file map before you spawn its executor** (MAR-529) — the
`<task>` names it for the executor to read, and this is what the PreToolUse
guard enforces, so an undeclared map means no enforcement at all:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --iteration <n> --task <k> --file src/a.py --file tests/test_a.py
```

One call per executor task, additive (declaring task 2 never erases task 1),
with the exact paths the plan's `## Executor tasks & file map` lists for that
task — you transcribe that table, you never widen it. `/acs:create-impl-plan`
already declared iteration 1's map when it published the plan; check it with
`acs.py filemap show --iteration 1` and declare it yourself when it is empty
(a hand-written plan, or one predating that skill). A write outside the
declared paths is then denied while an acs executor
is running, with the executor told to return `needs_input` for the file it
needs — you adjust the map, it does not improvise scope. Re-declare for the
iteration before dispatching remediation executors; the guard reads the highest
declared iteration.

Send each executor a `<task phase="execute">` naming its spec file, the
resolved `plan.md`, `test-cases.md` when it exists, and its
file map (include `<constraint name="docs_only">true</constraint>` when it
applies). Each executor (artifact `<partition>/phases/code/iter-<n>-execute.json`,
or `iter-<n>-execute-<k>.json` when parallel) must, in order:

1. **Write failing tests first** for the spec's Test plan, run them, confirm
   they fail for the right reason. **When `test-cases.md` exists** (written by
   `/acs:create-test-docs`), its `TC-n` rows for this task's scope ARE the test
   plan: write one test per case, name the `TC-n` id in the test's docstring,
   and report any case you could not write as a `problems` entry rather than
   silently dropping it. When the Test plan names e2e flows
   and `settings.e2e` is configured, the new/updated e2e tests are part of
   this step — same changeset, never a follow-up.
2. **Implement** until the tests pass, iterating against the TARGETED set the
   plan's test strategy names for that executor's file map — `plan.md` is
   `/acs:create-impl-plan`'s output, so the scope is read, not re-derived.
   **Executors never run the full unit suite.** It runs exactly once per
   iteration, in verify, and only once the verifier's reading dimensions come
   back clean: an iteration already going back to the executor does not need
   a suite run to say so. The safety half is absolute — no zero-findings
   verdict without a green full-suite run on the iteration being passed.
   Code comments stay **minimal and idea-only**
   — one short single-responsibility line per new function (SOLID:
   one unit, one job), never a ticket id in source, and on edits only the
   comments the change actually invalidates (e.g. a changed parameter); no
   re-comment passes over unchanged logic. Test module filenames follow the
   same rule: they are named by the component/behavior under test, never by a ticket id;
   the originating ticket reference lives in the module docstring.
   The executor also applies the **Simplicity First** and **Surgical
   Changes** authoring rules (see code-executor.md Charter) throughout.
3. **Coverage** is measured in verify, off that same run, against
   `settings.test_coverage_percent`; executors record
   `{"percent": null, "target": "measured in verify"}`. When a spec's code
   genuinely cannot be covered (e.g. untestable generated code), the executor
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

   When the changeset contradicts stated intent, the executor MUST flag the
   divergence in the execute-report `problems` field so it surfaces in the
   coordinator's result document and the PR body. The executor must NOT edit
   intent content. When the changeset alters no factual item in prd.md or
   roadmap.md, this step is a no-op for those files.

   **Boy-scout drift items — carried, never repaired here:** when the plan's
   `## Documentation map` names a doc section the plan's author found already
   disagreeing with the CURRENT code (its Boy-scout drift-repair survey), the
   executor does NOT repair it in this step — it copies the item verbatim,
   with the cited doc section and `file:line` disagreement, into the execute
   report's `problems` field, so `/acs:docs-sync` (which reads every execute
   report's `problems` as a mandatory input) repairs it on the same
   branch/PR.
5. **Commit** the spec's work on the ticket branch per
   `formats.commit_message` (one or a few coherent commits per spec). Never
   push.
