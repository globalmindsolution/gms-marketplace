# /acs:ship — the two failure paths a step can carry

Open this when a step you invoked returned `failed` AND its `ready[]` entry
carries `on_fail` or `on_replan`. A pipeline whose steps all complete never
reads a line of it, and a step that fails carrying neither key is an ordinary
stop — handled by "Handling the handoff" in SKILL.md, not here.

The two are different failures, and telling them apart is the whole point:
`on_fail` is for work that is BROKEN, so the fix goes back through a named
step and the same step is tried again, up to a cap this skill keeps. Only a
`stop_reason` of exactly `plan_superseded` is the other kind — work that was
WRONG, so the artifact it was given is re-made rather than the step retried.

**Where the cross-references below point.** "Single mode", "Handling the
handoff" and the walk are SKILL.md's sections, and a bare "above" or "below"
naming one means there.

## Fix loop (`on_fail`)

A ready step may carry `on_fail: {relay_to: <step id>, max_loops: <int>}`.
That step is allowed to fail and be fixed: on a failing run, relay the
failure into the named step, re-run it, and try again — up to `max_loops`
times. `max_loops` arrives already resolved (ship.yaml may name a settings
key; the walk reads it for you). Resolve `relay_to`'s skill from
`acs.py workflow show` (`workflow.steps[].id` → `.skill`) — never assume the
id and the skill are spelled the same.

Every write below goes through the `pipeline-step.py` CLI — never embedded
Python (ADR 0001). `--set fix_loops=<n>` merges the counter onto the step
entry and `--unset fix_loops` removes it; the step's own `status` and
timestamps stay owned by the step's own run. Read the current value from
`statuses` / `<partition>/pipeline-state.json.steps.<step id>.fix_loops`
(default `0` when absent). `fix_loops` is independent of any step's own
internal iteration cap — the two counters never interact.

1. **Re-entry reset.** If the existing `steps.<step id>` entry is `failed`,
   this is a resumed run re-entering the step after a previous cap. Reset the
   counter first and treat `fix_loops` as `0` below:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pipeline-step.py" \
     --ticket <ticket-id> --skill <step id> --status in_progress --unset fix_loops
   ```

   Without this the resumed run re-reads the capped value, falls straight
   into case 4 on its first failure, and can never make progress.
2. **The step completed** → it recorded its own `completed` entry. Clear the
   counter and go back to the walk:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pipeline-step.py" \
     --ticket <ticket-id> --skill <step id> --status completed --unset fix_loops
   ```
3. **The step failed and `fix_loops < max_loops`** → increment the counter,
   then relay the failure output into `/acs:<relay_to skill> <ticket-id>`
   **exactly via the existing "Re-invoke after needs_input" pattern** (see
   "Single mode" above) — the failure output is the relayed context text, in
   place of `Q: ... A: ...` lines; it is not a new mechanism. When that run
   completes, go back to the walk, which offers the failed step again; this
   is the fix-and-re-try loop.

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pipeline-step.py" \
     --ticket <ticket-id> --skill <step id> --status in_progress \
     --set fix_loops=<fix_loops + 1>
   ```
4. **The step failed and `fix_loops == max_loops`** → record the cap on the
   step and STOP, mirroring the failed-handling shape below. A later resumed
   run clears the counter via the re-entry reset in case 1:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pipeline-step.py" \
     --ticket <ticket-id> --skill <step id> --status failed \
     --set fix_loops=<max_loops> --summary "fix_loops cap reached"
   ```

**Orchestration, not step-work.** The counter and its cap are /acs:ship's to
keep; the step's own pass/fail outcome is recorded by the run that produced
it. The split is what keeps the two from overwriting each other, and it is
consistent with "You orchestrate; you never implement" above — the step's
actual work stays entirely inside the step skill you invoked.

## Replan (`on_replan`)

A ready step may carry `on_replan: <step id>` — the step to re-run when this
one discovers that the work it was given is wrong rather than merely broken.
When such a step returns `failed` with `stop_reason: plan_superseded` (and
only then), do NOT stop the pipeline:

1. Resolve the named step's skill from `acs.py workflow show`, as above.
2. Invoke it directly (`acs:<skill> <ticket-id>`) so it produces a fresh
   artifact; the superseded one is preserved by that skill's own revocation
   path, not by you.
3. Go back to the walk. The boundary step is ready again — its own ledger
   entry says `failed` — and runs against the new artifact.

Any other `failed` reason is an ordinary stop (below). Do not re-run a step
more than once for the same `plan_superseded` reason: a second one means the
ticket needs a human, so stop and say so.
