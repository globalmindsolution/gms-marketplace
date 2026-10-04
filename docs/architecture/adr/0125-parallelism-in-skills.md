# 0125 — Parallelism in skills: a cap setting, jobs beside the agents, checks beside the judge

**Status**: Accepted · **Date**: 2026-10-04

**Amends**: [0099](0099-review-is-a-step-not-a-phase.md) (the review's final gate
still runs once per iteration and its result is read last, but its commands start
beside the lenses), [0110](0110-parallel-fan-out-and-parallel-groups.md) (the cap
`max_parallel = 4` becomes the setting `parallel.max_agents`) and
[0121](0121-create-architecture-writes-the-hld-only.md) (the HLD's single write
architect becomes one write slice per HLD file group, with an integration pass on a
reported seam).

## Context

ADR-0110 made fan-out inside a skill the default and fixed the cap at four instances
per phase, written as a literal in every SKILL.md. Two kinds of serial time were left
on the table.

**Deterministic commands ran before or after the agents, never beside them.**
`/acs:review-code` ran build, lint and the full unit suite with coverage only after
adjudication had cleared every finding (ADR-0099: "once, last"); `/acs:create-impl-plan`'s
`tests` plan-review slice ran the repo's existing suite inside its own spawn, on every
iteration. On this repo the full suite takes **~415 s per instrumented run**
(`tests/acs/test_single_suite_run.py`), so the review's wall time was the lenses, then
the adjudicators, then seven more minutes; the plan review added a suite run to every
iteration. Neither command needs a model, and both run over a tree nothing else writes
while they run — read-only lenses and adjudicators, or a planner whose plan does not
change the existing suite command.

**$0 checks waited for a passing review.** `/acs:create-test-docs`,
`/acs:create-api-contract` and `/acs:analyze-requirements` ran `front_matter_check.py`
and `structure_lint.py` on the draft only after the judge passed, so a failure there
cost a whole extra iteration after a "pass"; `/acs:create-e2e-tests`' coverage grep
waited for the suite-runner; `/acs:create-prd` spawned an agent for a slice that is
entirely scripts.

Subagents themselves stay in the foreground (the 2026-09-15 release-gate finding:
background agents polled with `sleep` loops burned a whole setup budget), so the
answer cannot be "run the agents in the background".

## Decision

1. **The cap is a setting.** `settings.parallel.max_agents` (integer 1–16, default
   4; `acs_lib.settings`, `schemas/settings.schema.json`) is the most subagents a
   skill spawns in one message; beyond it, waves of that size. Every multi-agent
   skill's prose reads it instead of a literal. A skill's smaller structural cap
   stays (`code-small` 2, `code-trivial` 1, `create-docs`' doc sets 2), and
   `/acs:review-code`'s five lenses are one message whatever the setting.
2. **Jobs: commands beside the agents.** `acs.py job start --name N [--cwd D] --
   <command>` runs a deterministic command detached under `<run>/jobs/` and returns
   at once; `acs.py job wait --name N [--name M] [--timeout S]` is ONE blocking call
   (exit 0 all passed, 1 one failed or stopped, 3 timed out still running — call it
   again); `job status` and `job stop` complete the set (`acs_lib.jobs`). A job is
   not a background agent: it runs no model, and `wait` returns the moment it ends.
3. **`/acs:review-code`: the gate runs beside the review.** In the stage-1 lens turn
   the coordinator starts `gate-build` and `gate-lint` as separate jobs (they run
   concurrently) and the full unit suite with coverage as one job, `gate-suite`.
   After adjudication: nothing blocks → `job wait` and record `gate.json` from the
   jobs exactly as before; findings block → `job stop` and record the gate as not
   run. The gate's result is still read only by an iteration that survives review,
   and the suite still runs once per iteration. Adjudicators run in waves of the cap.
4. **`/acs:create-impl-plan`: the suite run is hoisted.** The coordinator starts the
   repo's existing suite command (or its `--collect-only` equivalent when long) as
   the `suite` job beside iteration 1's planner, once per run; the `tests` slice
   reads it with `job wait --name suite` and never runs the suite itself.
5. **Deterministic checks go beside the judge.** The $0 checks run as soon as the
   draft exists, in the same turn as the judge spawn, and a failure is a blocking
   finding of that iteration: `create-test-docs` and `create-api-contract`
   (front matter, structure), `analyze-requirements` (its controller runs them in
   `record-draft` and folds them into `record-review`; `publish` no longer runs
   them), `create-e2e-tests`' TC-id coverage grep (beside the suite-runner), and
   `create-prd`'s `floor` — no longer a reviewer slice: the coordinator runs the
   heading check, `prd_conformance_check.py` and `structure_lint.py` itself beside
   the two semantic slices, and dimension 7's semantic ceiling moves to `substance`.
6. **`/acs:create-api-contract` skips iteration 2+'s integration pass** when no seam
   finding is open and no re-run slice reports a seam.
7. **`/acs:create-architecture` writes in slices.** One write architect per HLD file
   group with a file to write (`write-context`, `write-structure`, `write-data`,
   `write-conventions`), all from the survey's notes, which pin the shared
   vocabulary; ONE integration architect runs alone only when a slice reports a seam
   (a name it needed that another group owns). The reviewer's `coherence` slice
   still judges cross-file naming.
8. **Batching in the inline and audit skills.** `/acs:audit-design` runs `acs.py
   design check` in the gap-analyst spawn turn; `/acs:create-pr` issues the branch
   check, base detect, label create and `gh pr list` as parallel Bash calls in one
   message, before the push; `/acs:ship`'s lockstep batches count against the cap.

**Not done, and why.**

- **Background subagents and pipelining across stages** (lenses → adjudicators
  streaming, a writer's next iteration starting while its judge runs): they need
  agents running in the background, which the foreground rule forbids.
- **Sliding windows** instead of waves (spawn the next instance when any one
  returns): the same — a coordinator can only react to a returned spawn by being
  idle in the foreground, so a wave is the unit.
- **`/acs:ship` lockstep → independent advancement of a parallel group's members**:
  each member's coordinator runs in the ship session; advancing one while another's
  agents run would need background agents.
- **Regrouping `ship.yaml`** into wider parallel groups: the members that could
  overlap already do (ADR-0110); the rest read each other's output.
- **Concurrent e2e suites** in `/acs:run-e2e-tests`: suites share ports, databases
  and fixtures far more often than not, so concurrency is not a clear win and a
  shared-state flake would read as a product failure.
- **`/acs:create-architecture`'s lints** stay in the `diagrams` and `coherence`
  review slices: they already run beside the other slices in the review turn, never
  after a pass, so moving them would re-partition dimensions without saving time.

## Consequences

- `/acs:review-code` spends a suite run on every iteration, including one that goes
  back to `/acs:code`, where it used to spend none; the run is stopped as soon as the
  adjudicators block, but up to its full length can be wasted. The pass case — the one
  that ends the loop — saves the whole suite's wall time.
- `/acs:create-impl-plan` runs the existing suite once per run instead of once per
  plan-review iteration.
- Job files (`<run>/jobs/<name>.json|.log|.exit`) live in the run directory beside the
  step state, outside the repo tree; a re-started job of the same name replaces a
  finished one.
- A consumer can trade wall time for token rate with one key; `1` is fully sequential.
- `/acs:create-architecture` spawns two to four write architects instead of one, plus
  an integration architect when a seam is reported; `/acs:create-prd`'s review spawns
  two agents instead of three.
